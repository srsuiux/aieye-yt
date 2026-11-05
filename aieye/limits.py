"""Hard daily limit (goal.txt): at most 3 videos PUSHED to YouTube a day, and a run is either 1 video or 3 videos."""
from datetime import date, datetime
from .config import FINAL_DB
from .store import load_db
from .ui import fail

DAILY_LIMIT    = 3
ALLOWED_COUNTS = (1, 3)

def pushed_today():
    """Videos pushed to YouTube today (local calendar day). One video = one topic, however many languages it was
    uploaded in. A video that was only rendered, or whose upload failed (no YouTube id), does not count."""
    today = date.today()
    n = 0
    for e in load_db(FINAL_DB):
        if not (e.get("youtube_id") or e.get("youtube_ids")):
            continue
        try:
            if datetime.fromisoformat(e["completed_at"]).date() == today:
                n += 1
        except (KeyError, ValueError):
            continue
    return n

def remaining_today():
    return max(0, DAILY_LIMIT - pushed_today())

def check_count_choice(count):
    """Only -1 or -3 exist. Anything else is refused outright."""
    if count not in ALLOWED_COUNTS:
        fail(f"I can only make 1 video or 3 videos at a time ({count} is not allowed). Never more than {DAILY_LIMIT} a day.")

def enforce_daily(count):
    """Refuse (and stop the run) if making `count` more videos would pass today's limit."""
    check_count_choice(count)
    made = pushed_today()
    if made + count > DAILY_LIMIT:
        left = DAILY_LIMIT - made
        if left <= 0:
            fail(f"I can't create more than {DAILY_LIMIT} videos a day, and {made} are already pushed to YouTube today. Try again tomorrow.")
        fail(f"I can't create {count} videos: {made} already pushed to YouTube today, the limit is {DAILY_LIMIT} a day "
             f"(only {left} left today). Make 1 video, or wait until tomorrow.")
