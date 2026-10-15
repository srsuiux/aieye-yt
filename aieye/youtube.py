import time, pickle
from .config import CLIENT_SECRETS, YOUTUBE_TOKEN, CFG, CHANNEL
from .ui import c, fail, log, ok, section, skip, spin, warn

# STEP 6 — YOUTUBE UPLOAD

def get_youtube_creds(secrets, token, force_reauth=False):
    """Load cached OAuth creds, refresh if expired, re-run browser auth if the
    refresh token is expired/revoked (e.g. 'invalid_grant' after weeks idle)."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds  = None

    if token.exists() and not force_reauth:
        try:
            with open(token, "rb") as f:
                creds = pickle.load(f)
        except Exception:
            warn("Cached YouTube token unreadable — re-authorizing")
            creds = None

    if creds and not set(SCOPES).issubset(set(creds.scopes or [])):
        creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            with spin("Refreshing OAuth token..."):
                creds.refresh(Request())
        except RefreshError as e:
            warn(f"YouTube token expired or revoked ({e}) — re-authorizing")
            creds = None
    else:
        creds = None

    if not creds:
        token.unlink(missing_ok=True)
        log("Opening browser for YouTube authorization...", "yellow", indent=1)
        flow  = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
        # offline + consent guarantees a fresh refresh_token is issued
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    with open(token, "wb") as f:
        pickle.dump(creds, f)
    ok("OAuth token saved → data/credentials/")
    return creds

def upload_to_youtube(video_path, meta):
    section("STEP 6  —  YouTube Upload")

    if CFG["upload_privacy"] == "none":
        skip("Upload skipped — video saved locally")
        return None

    secrets = CLIENT_SECRETS
    token   = YOUTUBE_TOKEN

    if not secrets.exists():
        warn("credentials/client_secrets.json not found — skipping upload")
        return None

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        import google_auth_oauthlib  # noqa: F401
    except ImportError:
        fail("pip install google-api-python-client google-auth-oauthlib")

    creds   = get_youtube_creds(secrets, token)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title":           meta["title"][:100],
            "description":     meta["description"],
            "tags":            CHANNEL["tags"],
            "categoryId":      "28",
            "defaultLanguage": meta.get("lang", "en"),
            "defaultAudioLanguage": meta.get("lang", "en"),
        },
        "status": {
            "privacyStatus":           CFG["upload_privacy"],
            "selfDeclaredMadeForKids": False,
        },
    }

    log(f"Uploading: {meta['title'][:70]}", indent=1)
    log(f"Privacy:   {CFG['upload_privacy'].upper()}", "yellow", indent=1)

    from googleapiclient.errors import HttpError
    from google.auth.exceptions import RefreshError

    def new_request(yt):
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        return yt.videos().insert(part="snippet,status", body=body, media_body=media)

    request  = new_request(youtube)
    t0 = time.time()
    response = None
    reauthed = False
    while response is None:
        try:
            status, response = request.next_chunk()
        except (RefreshError, HttpError) as e:
            auth_err = isinstance(e, RefreshError) or getattr(e, "status_code", getattr(e.resp, "status", None)) == 401
            if not auth_err or reauthed:
                raise
            print()
            warn("YouTube rejected the token — re-authorizing and retrying upload")
            reauthed = True
            creds    = get_youtube_creds(secrets, token, force_reauth=True)
            youtube  = build("youtube", "v3", credentials=creds)
            request  = new_request(youtube)
            continue
        if status:
            pct = int(status.progress() * 100)
            print(f"\r  {c('↑','cyan')} Uploading... {c(str(pct)+'%','yellow')}   ", end="", flush=True)
    print()

    video_id = response.get("id","unknown") if isinstance(response, dict) else "unknown"
    ok(f"Uploaded in {time.time()-t0:.1f}s → https://youtube.com/shorts/{video_id}")
    return video_id

