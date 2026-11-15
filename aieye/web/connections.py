"""Everything the Connections page needs: API key status/test, and the YouTube client file + sign-in."""
import json, threading
from .. import envfile
from ..config import CLIENT_SECRETS, CREDS_DIR, YOUTUBE_TOKEN

TESTS = {
    "OPENAI_API_KEY":     ("https://api.openai.com/v1/models", "OpenAI"),
    "OPENROUTER_API_KEY": ("https://openrouter.ai/api/v1/key", "OpenRouter"),
}

def keys_status():
    return envfile.all_status()

def test_key(name):
    """A free request that only checks the key is accepted. Returns {ok, message}."""
    import requests
    if name not in TESTS:
        raise ValueError("Unknown key")
    key = envfile.get_key(name)
    if not key:
        return {"ok": False, "message": "No key saved yet."}
    url, label = TESTS[name]
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=15)
    except requests.RequestException as e:
        return {"ok": False, "message": f"Could not reach {label}: {type(e).__name__}. Check your internet connection."}
    if r.status_code == 200:
        return {"ok": True, "message": f"{label} accepted the key."}
    if r.status_code in (401, 403):
        return {"ok": False, "message": f"{label} rejected the key. Copy it again from the {label} dashboard."}
    return {"ok": False, "message": f"{label} answered with status {r.status_code}."}

# ── YouTube ─────────────────────────────────────────────────────────────────────────────────────────────────────
_yt = {"state": "idle", "message": ""}      # idle | waiting | done | error  (the sign-in runs in a background thread)
_yt_lock = threading.Lock()

def youtube_status():
    has_secrets = CLIENT_SECRETS.exists()
    kind = None
    if has_secrets:
        try:
            kind = next(iter(json.loads(CLIENT_SECRETS.read_text())), None)
        except (OSError, ValueError):
            kind = "unreadable"
    return {"client_file": has_secrets, "client_kind": kind, "signed_in": YOUTUBE_TOKEN.exists(),
            "sign_in": dict(_yt), "path": str(CLIENT_SECRETS)}

def save_client_file(text):
    """Validate and save the OAuth client JSON downloaded from Google Cloud."""
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("That is not a JSON file. Download the OAuth client JSON from Google Cloud and try again.")
    inner = data.get("installed") if isinstance(data, dict) else None
    if not isinstance(inner, dict):
        raise ValueError("This is not a Desktop app OAuth client. In Google Cloud, create an OAuth client ID of type "
                         "Desktop app and download that JSON.")
    if not (inner.get("client_id") and inner.get("client_secret")):
        raise ValueError("The file has no client_id or client_secret.")
    CREDS_DIR.mkdir(parents=True, exist_ok=True)
    CLIENT_SECRETS.write_text(json.dumps(data, indent=2))
    try:
        CLIENT_SECRETS.chmod(0o600)
    except OSError:
        pass
    YOUTUBE_TOKEN.unlink(missing_ok=True)       # a new client needs a new sign-in

def start_sign_in():
    """Open Google's sign-in in a browser on THIS machine. Returns at once; poll youtube_status()."""
    if not CLIENT_SECRETS.exists():
        raise ValueError("Add the client file first.")
    with _yt_lock:
        if _yt["state"] == "waiting":
            return
        _yt.update(state="waiting", message="Finish signing in in the browser window that just opened.")

    def work():
        try:
            from ..youtube import get_youtube_creds
            get_youtube_creds(CLIENT_SECRETS, YOUTUBE_TOKEN, force_reauth=True)
            _yt.update(state="done", message="Signed in.")
        except BaseException as e:               # AieyeError is a SystemExit
            _yt.update(state="error", message=(getattr(e, "message", None) or str(e) or type(e).__name__)[:200])
    threading.Thread(target=work, daemon=True).start()

def sign_out():
    YOUTUBE_TOKEN.unlink(missing_ok=True)
    _yt.update(state="idle", message="")
