"""Read and write API keys in the local .env file (the web app's "Connections" page uses this).

Keys are only ever written to .env on this machine. Nothing here returns a full key: callers get set / not set and the
last 4 characters, so a page can show "sk-…abcd" without exposing the secret.
"""
import os, re
from pathlib import Path
from .config import ROOT

ENV_FILE = Path(os.environ.get("AIEYE_ENV_FILE") or ROOT / ".env")
KNOWN_KEYS = {
    "OPENAI_API_KEY":     "OpenAI (script, voice, images)",
    "OPENROUTER_API_KEY": "OpenRouter (AI video experiments, optional)",
}
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")

def _read_lines():
    try:
        return ENV_FILE.read_text().splitlines()
    except OSError:
        return []

def get_key(name):
    """The value from the environment (which .env feeds), or None."""
    return os.getenv(name) or None

def key_status(name):
    v = get_key(name)
    return {"name": name, "label": KNOWN_KEYS.get(name, name), "set": bool(v), "hint": f"…{v[-4:]}" if v and len(v) >= 8 else ""}

def all_status():
    return [key_status(k) for k in KNOWN_KEYS]

def set_key(name, value):
    """Save NAME=value into .env (other lines untouched) and into this process, so no restart is needed."""
    if name not in KNOWN_KEYS:
        raise ValueError(f"Unknown key '{name}'")
    value = (value or "").strip().strip('"').strip("'")
    if not value or any(ch in value for ch in "\r\n"):
        raise ValueError("The key is empty or has line breaks")
    lines, done = _read_lines(), False
    for i, ln in enumerate(lines):
        m = _LINE.match(ln)
        if m and m.group(1) == name:
            lines[i], done = f"{name}={value}", True
    if not done:
        lines.append(f"{name}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n")
    try:
        ENV_FILE.chmod(0o600)
    except OSError:
        pass
    os.environ[name] = value

def delete_key(name):
    if name not in KNOWN_KEYS:
        raise ValueError(f"Unknown key '{name}'")
    lines = [ln for ln in _read_lines() if not ((m := _LINE.match(ln)) and m.group(1) == name)]
    ENV_FILE.write_text("\n".join(lines) + ("\n" if lines else ""))
    os.environ.pop(name, None)
