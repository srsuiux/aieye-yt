"""Reading and writing the user's saved choices for the web app: defaults, advanced settings, channel, topic queue."""
import json, time
from datetime import datetime

from .. import tuning
from ..config import (DATA_DIR, CHANNEL, CHANNEL_FILE, DEFAULT_AUDIENCE_NOTES, DEFAULT_TOP_CATEGORIES, DRAFT_DB, FINAL_DB,
                      IMAGE_COST, SETTINGS_FILE)
from ..dedupe import history_texts, lexical_match
from ..limits import DAILY_LIMIT
from ..settings import BATCH_DEFAULT, OPTIONAL_SETTINGS, SETTING_CHOICES, est_cost_per_video, load_defaults
from ..store import load_db, save_db

FALLBACK_DEFAULTS = {"image_style": "representational", "image_quality": "medium", "upload_privacy": "private",
                     "tts_voice": "marin", "batch_voice": "shuffle"}
SETTING_INFO = {
    "image_style":    ("Image style", "representational: labelled diagrams, best for facts. realistic: photographic. illustrated: drawn."),
    "image_quality":  ("Image quality", "Pictures are most of the cost of a video."),
    "upload_privacy": ("Upload privacy", "none renders the video and keeps it on this computer. public publishes it the moment it is made."),
    "tts_voice":      ("Narrator voice", "The voice that reads the script."),
    "batch_voice":    ("Voices in a batch of 3", "shuffle: a different narrator on each video. same: the narrator above on all three."),
}

# ── Small UI memory (data/ui.json): has the welcome tour been finished or skipped? ──────────────────────────────
UI_FILE = DATA_DIR / "ui.json"

def ui_state():
    try:
        d = json.loads(UI_FILE.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}

def set_tour(state):
    if state not in ("done", "skipped"):
        raise ValueError("Unknown tour state")
    d = ui_state(); d["tour"] = state
    UI_FILE.parent.mkdir(parents=True, exist_ok=True)
    UI_FILE.write_text(json.dumps(d))

def is_fresh_install():
    """A brand-new install: no key, no saved settings, nothing made yet, tour never answered."""
    from .. import envfile
    return (not envfile.key_status("OPENAI_API_KEY")["set"] and not SETTINGS_FILE.exists()
            and not load_db(FINAL_DB) and "tour" not in ui_state())

# ── Defaults (data/settings.json) ──────────────────────────────────────────────────────────────────────────────
def defaults_view():
    saved = load_defaults()
    return {"values": saved or FALLBACK_DEFAULTS, "review": review_default(), "saved": bool(saved), "choices": SETTING_CHOICES, "info": SETTING_INFO,
            "cost": {q: {"one": round(est_cost_per_video(q), 2), "batch": round(est_cost_per_video(q) * BATCH_DEFAULT, 2)} for q in IMAGE_COST}}

def review_default():
    """Review a video before it uploads? True unless you turned it off. Stored with the defaults, used to pre-fill Create."""
    try:
        return bool(json.loads(SETTINGS_FILE.read_text()).get("review_before_upload", True))
    except (OSError, ValueError):
        return True

def save_defaults(values):
    clean = {}
    for k, ok_vals in SETTING_CHOICES.items():
        v = values.get(k, OPTIONAL_SETTINGS.get(k))
        if v not in ok_vals:
            raise ValueError(f"{SETTING_INFO[k][0]} must be one of: {', '.join(ok_vals)}.")
        clean[k] = v
    clean["review_before_upload"] = bool(values.get("review_before_upload", True))
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(clean, indent=2))
    return clean

# ── Advanced (data/config.json) ────────────────────────────────────────────────────────────────────────────────
def tuning_view():
    over, groups = tuning.load_overrides(), {}
    for key, spec in tuning.TUNABLES.items():
        item = {k: spec[k] for k in ("kind", "label", "help", "default") if k in spec}
        item.update(key=key, value=over.get(key, spec["default"]), changed=key in over)
        for k in ("choices", "min", "max"):
            if k in spec:
                item[k] = spec[k]
        groups.setdefault(spec["group"], []).append(item)
    return [{"group": g, "items": items} for g, items in groups.items()]

def save_tuning(values):
    current = {k: tuning.TUNABLES[k]["default"] for k in tuning.TUNABLES}
    current.update(tuning.load_overrides())
    current.update(values)
    return tuning.save_overrides(current)

def reset_tuning(keys=None):
    over = tuning.load_overrides()
    for k in (keys or list(over)):
        over.pop(k, None)
    tuning.TUNE_FILE.unlink(missing_ok=True)
    if over:
        tuning.save_overrides(over)

# ── Channel (data/channel.json) ────────────────────────────────────────────────────────────────────────────────
def _channel_file():
    try:
        d = json.loads(CHANNEL_FILE.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}

def channel_view():
    f = _channel_file()
    return {"exists": CHANNEL_FILE.exists(), "handle": f.get("handle", ""), "url": f.get("url", ""),
            "tags": f.get("tags", CHANNEL["tags"]), "description": f.get("description", CHANNEL["description"]),
            "audience_notes": f.get("audience_notes", DEFAULT_AUDIENCE_NOTES), "audience_default": "audience_notes" not in f,
            "top_categories": f.get("top_categories", DEFAULT_TOP_CATEGORIES), "categories_default": "top_categories" not in f}

def save_channel(v):
    handle = (v.get("handle") or "").strip()
    if handle and not handle.startswith("@"):
        handle = "@" + handle
    url = (v.get("url") or "").strip()
    if url and not url.startswith(("http://", "https://")):
        raise ValueError("The channel address must start with https://")
    tags = [t.strip().lstrip("#") for t in (v.get("tags") or []) if t.strip()]
    if len(tags) > 30 or sum(len(t) for t in tags) > 450:
        raise ValueError("Too many tags: YouTube allows about 500 characters in total.")
    desc = (v.get("description") or "").strip()
    if len(desc) > 4000:
        raise ValueError("The description is too long (4000 characters at most).")
    if "{scene_facts}" not in desc:
        raise ValueError("Keep {scene_facts} in the description: it is replaced by the facts from each video.")
    f = _channel_file()
    f.update(handle=handle, url=url, tags=tags, description=desc)
    notes = (v.get("audience_notes") or "").strip()
    if notes and notes != DEFAULT_AUDIENCE_NOTES.strip():
        f["audience_notes"] = notes
    else:
        f.pop("audience_notes", None)
    cats = [c.strip() for c in (v.get("top_categories") or []) if c.strip()]
    if cats and cats != DEFAULT_TOP_CATEGORIES:
        f["top_categories"] = cats
    else:
        f.pop("top_categories", None)
    CHANNEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHANNEL_FILE.write_text(json.dumps(f, indent=2, ensure_ascii=False))

# ── Topics (data/db/draft.json) ────────────────────────────────────────────────────────────────────────────────
def topics_view():
    queue = [t for t in load_db(DRAFT_DB) if t.get("status") in ("pending", "in_progress")]
    history = sorted(load_db(FINAL_DB), key=lambda e: e.get("completed_at", ""), reverse=True)[:30]
    for e in history:
        try:
            e["when"] = datetime.fromisoformat(e["completed_at"]).strftime("%b %d")
        except (KeyError, ValueError):
            e["when"] = ""
    return {"queue": queue, "history": history}

def add_topic(title, hook="", force=False):
    title, hook = (title or "").strip(), (hook or "").strip()
    if len(title) < 8:
        raise ValueError("Write the topic as a short question or sentence (at least 8 characters).")
    if len(title) > 140 or len(hook) > 400:
        raise ValueError("Keep the title under 140 characters and the hook under 400.")
    same = lexical_match(title, history_texts())
    if same and not force:
        raise DuplicateTopic(same)
    draft = load_db(DRAFT_DB)
    draft.append({"id": f"topic_{int(time.time())}_{len(draft)}", "title": title, "hook": hook, "status": "pending",
                  "created_at": datetime.now().isoformat()})
    save_db(DRAFT_DB, draft)

class DuplicateTopic(ValueError):
    def __init__(self, same):
        super().__init__(f"This looks like the same subject as \"{same}\", which is already made or queued.")
        self.same = same

def change_topic(topic_id, action):
    draft = load_db(DRAFT_DB)
    i = next((k for k, t in enumerate(draft) if t["id"] == topic_id), None)
    if i is None:
        raise ValueError("That topic is no longer in the queue.")
    if action == "delete":
        if draft[i].get("status") == "in_progress":
            raise ValueError("This topic is being made or was interrupted. Return it to the queue first.")
        draft.pop(i)
    elif action == "requeue":
        draft[i]["status"] = "pending"; draft[i].pop("started_at", None)
    elif action in ("up", "down"):
        j = i - 1 if action == "up" else i + 1
        while 0 <= j < len(draft) and draft[j].get("status") not in ("pending", "in_progress"):
            j += -1 if action == "up" else 1
        if 0 <= j < len(draft):
            draft[i], draft[j] = draft[j], draft[i]
    else:
        raise ValueError("Unknown action")
    save_db(DRAFT_DB, draft)
