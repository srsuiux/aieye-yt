"""One web-app job, run in its own process:  python -m aieye.webjob <job_dir>

The web server starts this so a run can be cancelled cleanly and always sees your latest settings. It talks to the server
only through files in <job_dir>:
    job.json          what to do (written by the server)
    events.jsonl      one JSON event per line: logs, steps, cost, upload progress (written here, read by the page)
    review_N.json     a finished video waiting for your decision, and decision_N.json: your answer (upload or skip, edits)
    result.json       written last: status and the result of each video
"""
import json, sys, time
from pathlib import Path

from . import ui


def _listener(path):
    f = open(path, "a", buffering=1)
    def write(ev):
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return write


def _make_review(job_dir):
    counter = {"n": 0}
    def review(info):
        counter["n"] += 1
        n = counter["n"]
        (job_dir / f"review_{n}.json").write_text(json.dumps(info, ensure_ascii=False))
        ui.emit("review", index=n, title=info["title"], lang=info["lang"])
        ui.log("Waiting for your decision in the web app before uploading", "yellow")
        decision = job_dir / f"decision_{n}.json"
        deadline = time.time() + 6 * 3600
        while time.time() < deadline:
            if decision.exists():
                try:
                    return json.loads(decision.read_text())
                except ValueError:
                    pass
            time.sleep(1)
        ui.warn("No decision for 6 hours: the video is kept, not uploaded")
        return {"action": "skip"}
    return review


def run_make(job, job_dir):
    from .client import get_client
    from .config import CFG, DB_DIR, OUTPUT_DIR
    from .pipeline import run_batch
    p = job["params"]
    CFG.update(image_style=p["image_style"], image_quality=p["image_quality"], upload_privacy=p["upload_privacy"],
               tts_voice=p["tts_voice"], batch_voice=p["batch_voice"], languages=p["languages"],
               manual_topic=p.get("topic") or None, trending=p["source"] == "trending", top=p["source"] == "top")
    if CFG["top"]:
        CFG["image_style"] = "realistic"
    DB_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    client = get_client()
    review = _make_review(job_dir) if p.get("review") and p["upload_privacy"] != "none" else None
    return run_batch(client, p["count"], review)


def run_upload(job, job_dir):
    """Upload a video that was kept on disk (not uploaded earlier). Records the YouTube id in the history."""
    import shutil
    from .config import CFG
    from .store import load_db, save_db
    from .config import FINAL_DB
    from .youtube import upload_to_youtube
    p = job["params"]
    folder = Path(p["folder"])
    video = folder / "short.mp4"
    meta = {**json.loads((folder / "youtube_metadata.json").read_text()), **p["meta"]}
    CFG["upload_privacy"] = meta.get("privacy") or "private"
    vid = upload_to_youtube(video, meta)
    if not vid:
        ui.fail("The upload did not go through. The video is still saved.")
    final = load_db(FINAL_DB)
    title = meta["title"].replace(" #Shorts", "")
    for e in reversed(final):
        if e.get("title") == title and not e.get("youtube_id") and not e.get("youtube_ids"):
            e["youtube_id"] = vid
            break
    save_db(FINAL_DB, final)
    ui.ok(f"Recorded in your history: https://youtube.com/shorts/{vid}")
    shutil.rmtree(folder, ignore_errors=True)
    return [{"ok": True, "title": title, "url": f"https://youtube.com/shorts/{vid}", "cost": 0.0, "error": None}]


def main(job_dir):
    job_dir = Path(job_dir)
    job = json.loads((job_dir / "job.json").read_text())
    ui.add_listener(_listener(job_dir / "events.jsonl"))
    status, results, error = "done", [], None
    try:
        results = run_make(job, job_dir) if job["kind"] == "make" else run_upload(job, job_dir)
        if not results or not all(r["ok"] for r in results):
            status = "failed"
            error = next((r["error"] for r in results if r.get("error")), "No video was made.")
    except BaseException as e:                       # AieyeError is a SystemExit; KeyboardInterrupt/SIGTERM too
        status, error = "failed", getattr(e, "message", None) or f"{type(e).__name__}: {e}"
    (job_dir / "result.json").write_text(json.dumps({"status": status, "error": error, "results": results,
                                                     "finished_at": time.time()}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
