"""Starting, watching, cancelling and answering web jobs. A job is a folder in data/jobs/<id>/ (see aieye/webjob.py)."""
import json, os, shutil, signal, subprocess, sys, time
from pathlib import Path

from ..config import DATA_DIR, IMAGE_COST, OUTPUT_DIR, ROOT
from ..languages import LANGS
from ..limits import DAILY_LIMIT, pushed_today
from ..settings import BATCH_DEFAULT, SETTING_CHOICES, est_cost_per_video
from ..envfile import get_key

JOBS_DIR = DATA_DIR / "jobs"
KEEP_JOBS = 20
SOURCES = {"queue": "Next topic in the queue", "trending": "What is trending on the web", "top": "A top category",
           "custom": "My own topic"}
EXTRA_LANGUAGE_COST = 0.02


class JobError(ValueError):
    pass


def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def estimate(params):
    """(total cost estimate, per video)."""
    per = est_cost_per_video(params["image_quality"]) + EXTRA_LANGUAGE_COST * (len(params["languages"]) - 1)
    return round(per * params["count"], 2), round(per, 2)


def validate(p):
    """Clean the form values of a new 'make' job or raise JobError with a message to show."""
    count = int(p.get("count") or 1)
    if count not in (1, BATCH_DEFAULT):
        raise JobError(f"Make 1 or {BATCH_DEFAULT} videos. Nothing else is allowed.")
    source = p.get("source")
    if source not in SOURCES:
        raise JobError("Choose where the topic comes from.")
    topic = (p.get("topic") or "").strip()
    if source == "custom":
        if len(topic) < 5:
            raise JobError("Write your topic (at least 5 characters).")
        count = 1
    langs = [l for l in (p.get("languages") or ["en"]) if l in LANGS] or ["en"]
    clean = {"count": count, "source": source, "topic": topic if source == "custom" else "", "languages": list(dict.fromkeys(langs)),
             "review": bool(p.get("review"))}
    for k in ("image_style", "image_quality", "upload_privacy", "tts_voice", "batch_voice"):
        if p.get(k) not in SETTING_CHOICES[k]:
            raise JobError(f"Choose a valid value for {k.replace('_', ' ')}.")
        clean[k] = p[k]
    if clean["upload_privacy"] == "none":
        clean["review"] = False
    return clean


def start_make(p):
    params = validate(p)
    if not get_key("OPENAI_API_KEY"):
        raise JobError("Add your OpenAI key on the Connections page first.")
    left = DAILY_LIMIT - pushed_today()
    if left < params["count"]:
        raise JobError(f"Today's limit is {DAILY_LIMIT} videos pushed to YouTube and {pushed_today()} are done, so {left} left. "
                       "Make fewer videos, or try again tomorrow.")
    return _spawn("make", params)


def start_upload(folder, meta):
    folder = Path(folder).resolve()
    if OUTPUT_DIR.resolve() not in folder.parents or not (folder / "short.mp4").exists():
        raise JobError("That video is no longer on this computer.")
    privacy = meta.get("privacy")
    if privacy not in ("public", "private", "unlisted"):
        raise JobError("Choose public, private or unlisted.")
    title = (meta.get("title") or "").strip()
    if not title:
        raise JobError("The title cannot be empty.")
    clean = {"title": title[:100], "description": (meta.get("description") or "").strip()[:4900], "privacy": privacy,
             "tags": [t.strip().lstrip("#") for t in meta.get("tags", []) if t.strip()][:30]}
    if pushed_today() >= DAILY_LIMIT:
        raise JobError(f"Today's limit of {DAILY_LIMIT} videos pushed to YouTube is reached. Try again tomorrow.")
    return _spawn("upload", {"folder": str(folder), "meta": clean})


def _spawn(kind, params):
    if active():
        raise JobError("A video is already being made. Wait for it to finish, or cancel it.")
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = time.strftime("%Y%m%d-%H%M%S")
    d = JOBS_DIR / job_id
    d.mkdir()
    job = {"id": job_id, "kind": kind, "params": params, "created": time.time()}
    (d / "job.json").write_text(json.dumps(job, ensure_ascii=False))
    log = open(d / "out.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "aieye.webjob", str(d)], cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    job["pid"] = proc.pid
    (d / "job.json").write_text(json.dumps(job, ensure_ascii=False))
    _prune()
    return job_id


def _prune():
    dirs = sorted(p for p in JOBS_DIR.iterdir() if p.is_dir())
    for old in dirs[:-KEEP_JOBS]:
        shutil.rmtree(old, ignore_errors=True)


def job_dir(job_id):
    if not job_id or "/" in job_id or ".." in job_id:
        raise JobError("Unknown run.")
    d = JOBS_DIR / job_id
    if not (d / "job.json").exists():
        raise JobError("That run does not exist any more.")
    return d


def _pending_review(d):
    for r in sorted(d.glob("review_*.json")):
        n = r.stem.split("_")[1]
        if not (d / f"decision_{n}.json").exists():
            return int(n)
    return None


def status(job_id):
    d = job_dir(job_id)
    job = _read(d / "job.json", {})
    result = _read(d / "result.json")
    if result:
        state = result["status"]
    elif job.get("pid") and _alive(job["pid"]):
        state = "review" if _pending_review(d) else "running"
    else:
        state = "cancelled" if (d / "cancelled").exists() else "failed"
    out = {"id": job_id, "kind": job["kind"], "state": state, "params": job["params"], "created": job["created"],
           "review": _pending_review(d) if state == "review" else None}
    if result:
        out.update(error=result.get("error"), results=result.get("results", []))
    elif state == "failed":
        out["error"] = "The run stopped unexpectedly. Open the log below for details."
    return out


def active():
    if not JOBS_DIR.exists():
        return None
    for p in sorted((q for q in JOBS_DIR.iterdir() if q.is_dir()), reverse=True)[:5]:
        try:
            s = status(p.name)
        except JobError:
            continue
        if s["state"] in ("running", "review"):
            return s
    return None


def recent(limit=10):
    if not JOBS_DIR.exists():
        return []
    out = []
    for p in sorted((q for q in JOBS_DIR.iterdir() if q.is_dir()), reverse=True)[:limit]:
        try:
            out.append(status(p.name))
        except JobError:
            pass
    return out


def events(job_id, after=0):
    d = job_dir(job_id)
    evs = []
    try:
        lines = (d / "events.jsonl").read_text().splitlines()
    except OSError:
        lines = []
    for ln in lines[after:]:
        try:
            evs.append(json.loads(ln))
        except ValueError:
            pass
    return evs, len(lines)


def log_tail(job_id, n=40):
    d = job_dir(job_id)
    try:
        return "\n".join((d / "out.log").read_text(errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def cancel(job_id):
    d = job_dir(job_id)
    s = status(job_id)
    if s["state"] not in ("running", "review"):
        return
    (d / "cancelled").write_text("1")
    pid = _read(d / "job.json", {}).get("pid")
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)     # the run and every ffmpeg it started
    except OSError:
        pass
    (d / "result.json").write_text(json.dumps({"status": "cancelled", "error": "Cancelled.", "results": [], "finished_at": time.time()}))


def get_review(job_id, n):
    d = job_dir(job_id)
    info = _read(d / f"review_{n}.json")
    if not info:
        raise JobError("There is nothing to review.")
    return info


def review_video_path(job_id, n):
    info = get_review(job_id, n)
    p = Path(info["video_path"]).resolve()
    if OUTPUT_DIR.resolve() not in p.parents or not p.exists():
        raise JobError("The video file is no longer there.")
    return p


def decide(job_id, n, action, meta=None):
    d = job_dir(job_id)
    if (d / f"decision_{n}.json").exists():
        raise JobError("You already answered this one.")
    if action == "skip":
        data = {"action": "skip"}
    elif action == "upload":
        m = meta or {}
        title = (m.get("title") or "").strip()
        if not title:
            raise JobError("The title cannot be empty.")
        if m.get("privacy") not in ("public", "private", "unlisted"):
            raise JobError("Choose public, private or unlisted.")
        data = {"action": "upload", "meta": {"title": title[:100], "description": (m.get("description") or "").strip()[:4900],
                "tags": [t.strip().lstrip("#") for t in m.get("tags", []) if t.strip()][:30], "privacy": m["privacy"]}}
    else:
        raise JobError("Unknown choice.")
    (d / f"decision_{n}.json").write_text(json.dumps(data, ensure_ascii=False))
