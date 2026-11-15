"""Experiment mode: `aieye run -vid [still.png] "motion prompt"` turns a still into a short clip via OpenRouter.

Purpose: compare image-to-video models on quality and price with ONE request format. Change the model with
`-model <id>`; list ids with `aieye models`. Nothing here touches the topic queue, the daily video limit or YouTube.
Every clip is saved with its real cost, and its LAST FRAME is saved too so the next clip can start exactly where
this one ended (clean connections between 5-second clips).
"""
import base64, io, json, os, re, time
from datetime import datetime

from .config import DATA_DIR
from .costs import track
from .ffmpeg import FFMPEG, run_cmd
from .ui import c, fail, log, ok, section, spin, warn

API          = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/veo-3.1-lite"     # best anatomy/action per dollar in our A/B (Grok Lite was cheaper but drew rats and sat for crouches)
DEFAULT_RES, DEFAULT_DUR, ASPECT = "720p", 5, "9:16"
MAX_DUR       = 10                                      # per command, to keep experiment spend small
POLL_EVERY, POLL_TIMEOUT = 5, 15 * 60
IMG_DIR = DATA_DIR / "experiments" / "images"
OUT_DIR = DATA_DIR / "experiments" / "videos"
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


def _key():
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        fail("OPENROUTER_API_KEY is not set. Create a key at openrouter.ai/keys, add a line "
             "OPENROUTER_API_KEY=... to .env, then run again.")
    return key


def _req(method, url, key=None, **kw):
    import requests
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    r = requests.request(method, url, headers=headers, timeout=kw.pop("timeout", 60), **kw)
    if r.status_code == 402:
        fail("OpenRouter says insufficient credits (402). Add credits at openrouter.ai/credits.")
    if r.status_code == 401:
        fail("OpenRouter rejected the key (401). Check OPENROUTER_API_KEY in .env.")
    return r


def list_models():
    """Live list of video models with their prices (public endpoint, no key needed)."""
    r = _req("GET", f"{API}/videos/models")
    r.raise_for_status()
    d = r.json()
    return d.get("data", d) if isinstance(d, dict) else d


def estimate_cost(model_info, res, dur, with_image):
    """Dollars from the model's live price table, or None when the model prices another way (e.g. per token).
    Models name their prices differently: cents per output second, or dollars per second (with/without resolution)."""
    sku = model_info.get("pricing_skus") or {}
    for key, unit in ((f"duration_seconds_without_audio_{res}", 1.0), (f"cents_per_video_output_second_{res}", 0.01), (f"duration_seconds_{res}", 1.0),
                      ("duration_seconds", 1.0), ("cents_per_second_output", 0.01)):
        if sku.get(key) is not None:
            extra = float(sku.get("cents_per_image_input", 0)) / 100 if with_image else 0.0
            return float(sku[key]) * unit * dur + extra
    return None


def latest_still():
    files = sorted(IMG_DIR.glob("*_1080x1920.png"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _image_data_url(path):
    """JPEG data URL, 9:16-sized at most 1080x1920, so the request body stays small."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((1080, 1920))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "clip"


def last_frame(video, out_png):
    """Save the final frame of a clip (the starting still for the next clip)."""
    run_cmd([FFMPEG, "-y", "-loglevel", "error", "-sseof", "-0.15", "-i", str(video),
             "-frames:v", "1", "-update", "1", str(out_png)], "last-frame")
    return out_png


def generate_clip(key, model, res, dur, prompt, image=None, aspect=ASPECT, retries=3, audio=False):
    """Submit one job, wait for it, download it. Text-to-video when `image` is None, image-to-video otherwise.
    Returns {"content": mp4 bytes, "cost": dollars or None, "job_id": id}. Raises RuntimeError on any failure
    (safe to call from worker threads)."""
    body = {"model": model, "prompt": prompt.strip(), "duration": int(dur), "resolution": res, "aspect_ratio": aspect}
    body["generate_audio"] = bool(audio)      # we add our own narration; silent clips are cheaper on some models
    if image:
        body["frame_images"] = [{"type": "image_url", "image_url": {"url": _image_data_url(image)}, "frame_type": "first_frame"}]
    for attempt in range(retries):
        r = _req("POST", f"{API}/videos", key, json=body)
        if r.status_code == 429 and attempt + 1 < retries:
            time.sleep(20 * (attempt + 1))
            continue
        break
    if r.status_code == 429:
        raise RuntimeError("OpenRouter rate limit (429)")
    if r.status_code >= 300:
        raise RuntimeError(f"OpenRouter refused the request ({r.status_code}): {r.text[:300]}")
    job = r.json()
    job_id = job["id"]
    poll_url = job.get("polling_url") or f"{API}/videos/{job_id}"
    t0 = time.time()
    while True:
        time.sleep(POLL_EVERY)
        j = _req("GET", poll_url, key).json()
        status = j.get("status")
        if status in ("completed", "failed", "cancelled", "expired"):
            break
        if time.time() - t0 > POLL_TIMEOUT:
            raise RuntimeError(f"gave up after {POLL_TIMEOUT // 60} minutes (job {job_id} may still finish)")
    if status != "completed":
        raise RuntimeError(f"generation {status}: {j.get('error') or 'no details'} (failed generations are not billed)")
    urls = j.get("unsigned_urls") or [f"{API}/videos/{job_id}/content?index=0"]
    url = urls[0] if urls[0].startswith("http") else "https://openrouter.ai" + urls[0]
    dl = _req("GET", url, key, timeout=300)
    if dl.status_code != 200 or not dl.content:
        raise RuntimeError(f"could not download the clip ({dl.status_code})")
    return {"content": dl.content, "cost": (j.get("usage") or {}).get("cost"), "job_id": job_id}


def run_video_experiment(prompt, image, model, res, dur, yes=False):
    key = _key()
    if not prompt.strip():
        fail('No motion prompt.  Usage: aieye run -vid [still.png] "slow push-in, the fox turns its head"')
    dur = int(dur)
    if not 1 <= dur <= MAX_DUR:
        fail(f"-dur must be 1 to {MAX_DUR} seconds (got {dur}); this is an experiment, so clips stay short.")
    image = image or latest_still()
    if image is None:
        fail('No still found. Make one first:  aieye run -img 1 "your image prompt"   or pass a path:  -vid my.png "prompt"')
    image = os.path.expanduser(str(image))
    if not os.path.isfile(image):
        fail(f"Image not found: {image}")

    section(f"EXPERIMENT  —  image to video  ({model} · {res} · {dur}s · {ASPECT})")
    info = next((m for m in list_models() if m.get("id") == model), None)
    if info is None:
        fail(f"Unknown model '{model}'. See the current ids with:  aieye models")
    if res not in (info.get("supported_resolutions") or [res]):
        fail(f"{model} supports {info.get('supported_resolutions')}, not {res}.")
    if ASPECT not in (info.get("supported_aspect_ratios") or [ASPECT]):
        fail(f"{model} does not support {ASPECT}.")
    if "first_frame" not in (info.get("supported_frame_images") or []):
        fail(f"{model} cannot start from an image (no first_frame support). Pick another with -model.")
    if info.get("supported_durations") and dur not in info["supported_durations"]:
        fail(f"{model} supports durations {info['supported_durations']}, not {dur}.")

    est = estimate_cost(info, res, dur, True)
    log(f"Still:  {image}", "dim", indent=1)
    log(f"Prompt: {prompt}", "cyan", indent=1)
    log(f"Estimated cost: {'$%.3f' % est if est is not None else 'unknown (this model is priced another way, e.g. per token)'}"
        "  (live price table; the real cost is saved after)", "yellow", indent=1)
    if not yes:
        from .settings import confirm_start
        confirm_start(3)

    t0 = time.time()
    try:
        with spin("Generating the clip (usually 30 seconds to 4 minutes)..."):
            got = generate_clip(key, model, res, dur, prompt, image=image)
    except RuntimeError as e:
        fail(str(e))
    content, cost, job_id = got["content"], got["cost"], got["job_id"]
    log(f"Job {job_id} done", "dim", indent=1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = OUT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{_slug(prompt)}"
    mp4 = base.with_suffix(".mp4")
    mp4.write_bytes(content)
    last = last_frame(mp4, base.with_name(base.name + "_last.png"))
    track(model, float(cost) if cost is not None else (est or 0.0))
    secs = time.time() - t0
    base.with_suffix(".json").write_text(json.dumps({
        "model": model, "prompt": prompt, "still": image, "duration_s": dur, "resolution": res, "aspect_ratio": ASPECT,
        "estimated_cost_usd": est, "actual_cost_usd": cost, "generation_seconds": round(secs),
        "job_id": job_id, "created_at": datetime.now().isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))

    ok(f"Saved {mp4.name}  ({len(content) // 1024} KB, {secs:.0f}s to generate)")
    print()
    print(c("  Clip:       ", "bold"), c(str(mp4), "cyan"))
    print(c("  Last frame: ", "bold"), c(str(last), "cyan"), c(" <- use as the still for the next clip", "dim"))
    print(c(f"  Cost: {'$%.3f' % float(cost) if cost is not None else 'not reported (estimate $%.3f)' % (est or 0)}"
            f"   ({model}, {res}, {dur}s)", "yellow"))
    print()
