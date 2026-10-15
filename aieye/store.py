import json
from datetime import datetime
from . import costs
from .config import DRAFT_DB, FINAL_DB
from .ui import ok

# DATABASE

def load_db(path):
    return json.load(open(path)) if path.exists() else []

def save_db(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")          # write-then-rename so a crash can't leave a half-written file
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    tmp.replace(path)

def all_used_titles():
    titles = set()
    for e in load_db(DRAFT_DB) + load_db(FINAL_DB):
        titles.add(e.get("title", "").lower())
    return titles

def get_pending():
    return [t for t in load_db(DRAFT_DB) if t.get("status") == "pending"]

def mark_in_progress(topic):
    draft = load_db(DRAFT_DB)
    for t in draft:
        if t["id"] == topic["id"]:
            t["status"]     = "in_progress"
            t["started_at"] = datetime.now().isoformat()
    save_db(DRAFT_DB, draft)

def mark_done(topic, script, video_id=None):
    """Move a topic from the queue to the history as ONE slim record.

    The history is only used to avoid repeating titles and to link back to the YouTube video, so it keeps
    just that — no scene text, no file paths (the video files are deleted after upload anyway)."""
    draft = [t for t in load_db(DRAFT_DB) if t["id"] != topic["id"]]
    save_db(DRAFT_DB, draft)
    final = load_db(FINAL_DB)
    entry = {
        "id":           topic["id"],
        "title":        script["title"],
        "topic":        topic["title"],
        "cost":         round(costs.total(), 4),
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }
    if video_id and video_id != "unknown":
        entry["youtube_id"] = video_id
    final.append(entry)
    save_db(FINAL_DB, final)
    ok(f"Logged to history — {len(final)} shorts completed total")

def save_ckpt(out_dir, name, data):
    with open(out_dir / f".ckpt_{name}.json", "w") as f:
        json.dump(data, f, indent=2)

def load_ckpt(out_dir, name):
    p = out_dir / f".ckpt_{name}.json"
    return json.load(open(p)) if p.exists() else None

