"""`aieye web`: a local web app. Bound to 127.0.0.1 by default; anything wider needs --host and asks for a token."""
import secrets, threading, webbrowser
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import envfile
from ..config import CHANNEL_FILE, DEFAULT_AUDIENCE_NOTES, DRAFT_DB, FINAL_DB, SETTINGS_FILE
from ..limits import DAILY_LIMIT, pushed_today
from ..store import load_db
from . import connections, data, docs

HERE = Path(__file__).resolve().parent
DEFAULT_PORT = 8420
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

NAV = [   # the rail: only pages that exist are listed
    {"href": "/",            "label": "Home",        "icon": "home"},
    {"href": "/topics",      "label": "Topics",      "icon": "list"},
    {"href": "/channel",     "label": "Channel",     "icon": "channel"},
    {"href": "/settings",    "label": "Settings",    "icon": "sliders"},
    {"href": "/connections", "label": "Connections", "icon": "link"},
    {"href": "/docs",        "label": "Docs",        "icon": "book"},
]

def create_app(token=None, bind_host="127.0.0.1"):
    app = FastAPI(title="AI Eye", docs_url=None, redoc_url=None, openapi_url=None)
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
    allowed_hosts = set(LOCAL_HOSTS) | ({bind_host} if bind_host not in ("0.0.0.0", "::") else set())

    def page(request, name, status=200, **ctx):
        ctx.update(nav=NAV, path=request.url.path, remote=bool(token), request=request)
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    # ── Guard: only this machine's own pages may talk to the app ───────────────────────────────────────────────
    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
        if bind_host in LOCAL_HOSTS:
            if host not in allowed_hosts:                       # blocks DNS-rebinding from a web page elsewhere
                return JSONResponse({"error": "Unknown host"}, status_code=403)
        if request.method not in ("GET", "HEAD"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"error": "Cross-site request blocked"}, status_code=403)
            if request.headers.get("x-requested-with") != "aieye":
                return JSONResponse({"error": "Missing header"}, status_code=403)
        if token:
            given = request.query_params.get("token")
            if given == token:
                resp = RedirectResponse(request.url.path or "/")
                resp.set_cookie("aieye_token", token, httponly=True, samesite="strict")
                return resp
            if request.cookies.get("aieye_token") != token and not request.url.path.startswith("/static"):
                return HTMLResponse("<h1>AI Eye</h1><p>Open the link printed in the terminal; it contains the access token.</p>",
                                    status_code=401)
        return await call_next(request)

    # ── Pages ─────────────────────────────────────────────────────────────────────────────────────────────────
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        final = load_db(FINAL_DB)
        recent = sorted(final, key=lambda e: e.get("completed_at", ""), reverse=True)[:8]
        for e in recent:
            ids = e.get("youtube_ids") or ({"en": e["youtube_id"]} if e.get("youtube_id") else {})
            e["link"] = f"https://youtube.com/shorts/{next(iter(ids.values()))}" if ids else None
            try:
                e["when"] = datetime.fromisoformat(e["completed_at"]).strftime("%b %d, %H:%M")
            except (KeyError, ValueError):
                e["when"] = ""
        pending = [t for t in load_db(DRAFT_DB) if t.get("status") == "pending"]
        yt = connections.youtube_status()
        checklist = [
            {"done": envfile.key_status("OPENAI_API_KEY")["set"], "label": "Add your OpenAI key", "href": "/connections",
             "help": "Needed for the script, voice and pictures."},
            {"done": yt["client_file"] and yt["signed_in"], "label": "Connect YouTube (optional)", "href": "/connections",
             "help": "Only needed to upload. You can render videos without it."},
            {"done": CHANNEL_FILE.exists(), "label": "Add your channel details (optional)", "href": "/channel",
             "help": "Handle, description and tags used on uploads."},
            {"done": SETTINGS_FILE.exists(), "label": "Save your default settings", "href": "/settings",
             "help": "Image style, quality, narrator and privacy."},
        ]
        return page(request, "home.html", title="Home", used=pushed_today(), limit=DAILY_LIMIT, recent=recent,
                    pending=len(pending), checklist=checklist, total=len(final))

    @app.get("/connections", response_class=HTMLResponse)
    def connections_page(request: Request):
        return page(request, "connections.html", title="Connections", keys=connections.keys_status(),
                    yt=connections.youtube_status())

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request):
        return page(request, "settings.html", title="Settings", d=data.defaults_view(), groups=data.tuning_view())

    @app.get("/channel", response_class=HTMLResponse)
    def channel_page(request: Request):
        return page(request, "channel.html", title="Channel", ch=data.channel_view())

    @app.get("/topics", response_class=HTMLResponse)
    def topics_page(request: Request):
        return page(request, "topics.html", title="Topics", t=data.topics_view())

    @app.get("/docs", response_class=HTMLResponse)
    def docs_index(request: Request):
        return RedirectResponse("/docs/overview")

    @app.get("/docs/{slug:path}", response_class=HTMLResponse)
    def docs_page(request: Request, slug: str):
        doc = docs.render(slug.strip("/"))
        if not doc:
            return page(request, "error.html", status=404, title="Not found",
                        message="That documentation page does not exist.", back=("/docs", "Back to the docs"))
        return page(request, "docs.html", title=doc["title"], doc=doc, docs_nav=docs.nav())

    # ── Connections API ───────────────────────────────────────────────────────────────────────────────────────
    def bad(msg, code=400):
        return JSONResponse({"ok": False, "message": msg}, status_code=code)

    @app.get("/api/connections")
    def api_connections():
        return {"keys": connections.keys_status(), "youtube": connections.youtube_status()}

    @app.put("/api/connections/keys/{name}")
    async def api_set_key(name: str, request: Request):
        body = await request.json()
        try:
            envfile.set_key(name, body.get("value", ""))
        except ValueError as e:
            return bad(str(e))
        return {"ok": True, "key": envfile.key_status(name)}

    @app.delete("/api/connections/keys/{name}")
    def api_delete_key(name: str):
        try:
            envfile.delete_key(name)
        except ValueError as e:
            return bad(str(e))
        return {"ok": True, "key": envfile.key_status(name)}

    @app.post("/api/connections/keys/{name}/test")
    def api_test_key(name: str):
        try:
            return connections.test_key(name)
        except ValueError as e:
            return bad(str(e))

    @app.put("/api/connections/youtube/client")
    async def api_youtube_client(request: Request):
        body = await request.json()
        try:
            connections.save_client_file(body.get("text", ""))
        except ValueError as e:
            return bad(str(e))
        return {"ok": True, "youtube": connections.youtube_status()}

    @app.post("/api/connections/youtube/sign-in")
    def api_youtube_sign_in():
        try:
            connections.start_sign_in()
        except ValueError as e:
            return bad(str(e))
        return {"ok": True, "youtube": connections.youtube_status()}

    @app.delete("/api/connections/youtube/sign-in")
    def api_youtube_sign_out():
        connections.sign_out()
        return {"ok": True, "youtube": connections.youtube_status()}

    # ── Settings, channel and topics API ──────────────────────────────────────────────────────────────────────
    @app.put("/api/settings/defaults")
    async def api_save_defaults(request: Request):
        try:
            data.save_defaults(await request.json())
        except ValueError as e:
            return bad(str(e))
        return {"ok": True, "message": "Saved. New videos use these defaults."}

    @app.put("/api/settings/advanced")
    async def api_save_advanced(request: Request):
        body = await request.json()
        try:
            data.save_tuning(body.get("values", {}))
        except ValueError as e:
            return bad(str(e))
        return {"ok": True, "message": "Saved. The next video you make uses these."}

    @app.post("/api/settings/advanced/reset")
    async def api_reset_advanced(request: Request):
        body = await request.json()
        data.reset_tuning(body.get("keys") or None)
        return {"ok": True}

    @app.get("/api/channel/default-audience")
    def api_default_audience():
        return {"text": DEFAULT_AUDIENCE_NOTES}

    @app.put("/api/channel")
    async def api_save_channel(request: Request):
        try:
            data.save_channel(await request.json())
        except ValueError as e:
            return bad(str(e))
        return {"ok": True, "message": "Channel details saved."}

    @app.post("/api/topics")
    async def api_add_topic(request: Request):
        body = await request.json()
        try:
            data.add_topic(body.get("title"), body.get("hook"), bool(body.get("force")))
        except data.DuplicateTopic as e:
            return JSONResponse({"ok": False, "duplicate": True, "message": str(e)}, status_code=409)
        except ValueError as e:
            return bad(str(e))
        return {"ok": True}

    @app.post("/api/topics/{topic_id}/{action}")
    def api_change_topic(topic_id: str, action: str):
        try:
            data.change_topic(topic_id, action)
        except ValueError as e:
            return bad(str(e))
        return {"ok": True}

    return app


def run(host="127.0.0.1", port=DEFAULT_PORT, open_browser=True):
    import uvicorn
    local = host in LOCAL_HOSTS
    token = None if local else secrets.token_urlsafe(16)
    app = create_app(token=token, bind_host=host)
    shown = "localhost" if local else host
    url = f"http://{shown}:{port}/" + (f"?token={token}" if token else "")
    print(f"\n  AI Eye web app:  {url}")
    if local:
        print("  Only this computer can open it. Press Ctrl+C to stop.\n")
    else:
        print(f"  Listening on {host}: anyone on your network with this link can use your API keys and upload.")
        print("  Share the link only with people you trust. Press Ctrl+C to stop.\n")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
