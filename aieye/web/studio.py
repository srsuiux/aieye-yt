"""Studio: the AI video experiments (stills, clip, script, film) as web pages. Reads live model prices, validates the
forms, and finds the files a run produced. The work itself is done by aieye/imgexp.py, videxp.py, scriptlab.py and film.py."""
import time
from pathlib import Path

from ..config import DATA_DIR, IMAGE_COST
from ..envfile import get_key

EXP = DATA_DIR / "experiments"
IMG_DIR, CLIP_DIR, FILM_DIR = EXP / "images", EXP / "videos", EXP / "film"

TOOLS = {
    "stills": {"label": "Stills", "title": "Make pictures", "needs": ["OPENAI_API_KEY"],
               "blurb": "1 to 4 sharp, centre-focused 9:16 pictures to feed an image-to-video model.",
               "cost": "about $0.04 a picture at high quality"},
    "clip":   {"label": "Clip", "title": "Turn a picture into a clip", "needs": ["OPENROUTER_API_KEY"],
               "blurb": "Animate one of your stills with an image-to-video model. Saves the clip and its last frame.",
               "cost": "priced by the model, usually under $1"},
    "script": {"label": "Script", "title": "Write only the script", "needs": ["OPENAI_API_KEY"],
               "blurb": "A reasoning model researches and drafts; a stronger one judges it against a strict rubric and it is revised.",
               "cost": "up to a few dollars; no video is made"},
    "film":   {"label": "Film", "title": "Make a whole film", "needs": ["OPENAI_API_KEY", "OPENROUTER_API_KEY"],
               "blurb": "The full pipeline with AI video: shot list, voice, one clip per scene, captions, loudness-normalised 9:16 video.",
               "cost": "the most expensive tool: about $0.30 plus the price of about 30 seconds of footage"},
}

FILM_MODELS = [   # label, OpenRouter id, advice
    ("Veo 3.1 Lite", "google/veo-3.1-lite", "Default. Best anatomy and action per dollar in our tests."),
    ("Veo 3.1 Fast", "google/veo-3.1-fast", "Higher quality, higher price."),
    ("Grok Imagine Lite", "x-ai/grok-imagine-video-1.5-lite", "Cheapest, but it drew wrong animals in our test."),
    ("Seedance 2.0 Fast", "bytedance/seedance-2.0-fast", "Untested here."),
    ("Kling 3.0", "kwaivgi/kling-v3.0-std", "Untested here."),
]
FILM_SECONDS, FILM_BASE_COST = 30, 0.30      # a typical film: footage seconds, and script + voice
RES = ["480p", "720p", "1080p"]


class StudioError(ValueError):
    pass


def missing_keys(tool):
    return [k for k in TOOLS[tool]["needs"] if not get_key(k)]


def live_models():
    """(models list, error text). The price list is a free public request."""
    try:
        from ..videxp import list_models
        return list_models(), None
    except Exception as e:                      # offline, or the service is down
        return [], f"Could not load live prices ({type(e).__name__}). Check your internet connection."


def prices(models):
    """{model id: {res: {sec, img}}}: dollars per second of footage, and the extra for a start picture. None = priced another way."""
    from ..videxp import estimate_cost
    out = {}
    for m in models:
        per = {}
        for res in m.get("supported_resolutions") or RES:
            sec = estimate_cost(m, res, 1, False)
            per[res] = {"sec": None if sec is None else round(sec, 4), "img": round((estimate_cost(m, res, 0, True) or 0), 4)}
        out[m["id"]] = per
    return out


def clip_models(models):
    return [m for m in models if "first_frame" in (m.get("supported_frame_images") or [])]


def film_models(models):
    ids = {m["id"]: m for m in models}
    return [(l, i, a) for l, i, a in FILM_MODELS if not models or i in ids]


def stills():
    """Newest first: [{name, url}] of the 1080x1920 stills made by the Stills tool."""
    files = sorted(IMG_DIR.glob("*_1080x1920.png"), key=lambda p: p.stat().st_mtime, reverse=True) if IMG_DIR.exists() else []
    return [{"name": p.name, "url": f"/studio/file/images/{p.name}"} for p in files[:24]]


def recent():
    def listing(folder, pattern, kind, base):
        if not folder.exists():
            return []
        fs = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)[:8]
        return [{"name": p.name, "url": f"/studio/file/{base}/{p.relative_to(folder).as_posix()}", "kind": kind,
                 "when": time.strftime("%b %d, %H:%M", time.localtime(p.stat().st_mtime))} for p in fs]
    return {"stills": listing(IMG_DIR, "*_1080x1920.png", "image", "images"),
            "clips": listing(CLIP_DIR, "*.mp4", "video", "videos"),
            "films": listing(FILM_DIR, "*/film_9x16.mp4", "video", "film"),
            "scripts": listing(FILM_DIR, "*/script.md", "text", "film")}


def file_path(rel):
    p = (EXP / rel).resolve()
    if EXP.resolve() not in p.parents or not p.is_file() or p.suffix.lower() not in (".png", ".mp4", ".md", ".json", ".jpg"):
        raise StudioError("File not found")
    return p


def _text(v, lo, hi, what):
    v = (v or "").strip()
    if not lo <= len(v) <= hi:
        raise StudioError(f"{what}: write between {lo} and {hi} characters.")
    return v


def validate(tool, p, models=None):
    """Clean the form values of a Studio run or raise StudioError with a message to show."""
    if tool not in TOOLS:
        raise StudioError("Unknown tool.")
    gone = missing_keys(tool)
    if gone:
        raise StudioError("Add your " + " and ".join("OpenAI" if k.startswith("OPENAI") else "OpenRouter" for k in gone) +
                          " key on the Connections page first.")
    if tool == "stills":
        q = p.get("quality")
        if q not in IMAGE_COST:
            raise StudioError("Choose low, medium or high quality.")
        return {"tool": tool, "prompt": _text(p.get("prompt"), 5, 400, "Picture description"),
                "count": max(1, min(4, int(p.get("count") or 1))), "quality": q}
    if tool == "script":
        return {"tool": tool, "topic": _text(p.get("topic"), 5, 200, "Topic"), "notes": (p.get("notes") or "").strip()[:6000]}
    models = models if models is not None else live_models()[0]
    ids = {m["id"]: m for m in models}
    res = p.get("res")
    if res not in RES:
        raise StudioError("Choose 480p, 720p or 1080p.")
    model = p.get("model")
    if ids and model not in ids:
        raise StudioError("That model is not in the live price list. Pick another.")
    info = ids.get(model, {})
    if info.get("supported_resolutions") and res not in info["supported_resolutions"]:
        raise StudioError(f"That model supports {', '.join(info['supported_resolutions'])}, not {res}.")
    if tool == "clip":
        dur = int(p.get("dur") or 5)
        if not 1 <= dur <= 10:
            raise StudioError("Clip length is 1 to 10 seconds.")
        if info.get("supported_durations") and dur not in info["supported_durations"]:
            raise StudioError(f"That model makes clips of {', '.join(map(str, info['supported_durations']))} seconds.")
        image = p.get("image") or ""
        if image and not (IMG_DIR / image).is_file():
            raise StudioError("That picture is no longer there.")
        if not image and not stills():
            raise StudioError("Make a picture first on the Stills page.")
        return {"tool": tool, "prompt": _text(p.get("prompt"), 5, 400, "Motion description"), "image": image,
                "model": model, "res": res, "dur": dur}
    if model not in {i for _, i, _ in FILM_MODELS}:
        raise StudioError("Choose one of the listed models.")
    return {"tool": tool, "topic": _text(p.get("topic"), 5, 200, "Topic"), "notes": (p.get("notes") or "").strip()[:6000],
            "model": model, "res": res, "ambient": bool(p.get("ambient")), "qa": bool(p.get("qa"))}
