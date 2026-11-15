"""Advanced settings: models, script size, look of the video. One place for every default and its limits.

Defaults live here. Your changes are saved in data/config.json (git-ignored) and only the values you changed are stored,
so a framework update can still improve the defaults you did not touch. Modules read a value with `tune("NAME")`.
Values are read when the program starts, so a change applies to the NEXT video, not to one already running.
"""
import json, re
from pathlib import Path

TUNE_FILE = Path(__file__).resolve().parent.parent / "data" / "config.json"

_VOICES = ["marin", "cedar", "nova", "coral", "sage", "ash", "ballad", "verse", "alloy", "echo", "fable", "onyx", "shimmer"]

TTS_STYLE = ("Voice: a curious, warm storyteller talking to one friend, relaxed and natural, never an announcer. "
             "Pacing: conversational and a little quick, with short pauses at sentence ends. "
             "Emphasis: land on the surprising word. Avoid sing-song and forced excitement.")

KID_RULES = """KID LEVEL (strict)
- Write for a curious 10-year-old. Use words a fourth grader already knows. If a science word is truly needed,
  explain it in the same sentence in plain words, and use at most one such word per video.
- Short sentences: most under 12 words, none over 20. One idea per sentence.
- Compare with things a kid knows (a school bus, a football field, a pizza, a pet), not with abstractions.
- Playful and a little funny, never babyish and never scary. Nothing about death, injury, violence or disasters.
- Ask the viewer one thing to picture or guess, early, then pay it off."""

# kind: text | longtext | int | float | choice | color | voices. group order is the order shown on the page.
TUNABLES = {
    "GPT_MODEL":     dict(group="Models", kind="text", default="gpt-6-luna", label="Script model",
                          help="Writes topics and scripts. Any OpenAI chat model you can use."),
    "TTS_MODEL":     dict(group="Models", kind="text", default="gpt-4o-mini-tts-2025-03-20", label="Voice model",
                          help="Speaks the script. The March 2025 snapshot follows delivery notes best; falls back to the plain model if retired."),
    "IMAGE_MODEL":   dict(group="Models", kind="text", default="gpt-image-2.5-flare", label="Image model",
                          help="Draws the pictures."),
    "N_SCENES":      dict(group="Script and pictures", kind="int", default=5, min=3, max=7, label="Scenes per video",
                          help="More scenes make a longer video and cost more."),
    "MAX_SHOTS":     dict(group="Script and pictures", kind="int", default=3, min=1, max=3, label="Pictures per scene (most)",
                          help="1 is the cheapest (one picture per scene). 2 or 3 gives a new picture every few seconds."),
    "MIN_SHOT_WORDS": dict(group="Script and pictures", kind="int", default=5, min=2, max=12, label="Shortest picture, in words",
                          help="Shorter pieces are merged into a neighbour, because very short cuts look like flicker."),
    "IMAGE_WORKERS": dict(group="Script and pictures", kind="int", default=3, min=1, max=6, label="Scenes drawn at once",
                          help="Lower this if you see rate-limit messages."),
    "N_TOPICS":      dict(group="Script and pictures", kind="int", default=10, min=3, max=20, label="Topics added when the queue is empty",
                          help="How many new topic ideas the model writes at a time."),
    "DAILY_LIMIT":   dict(group="Limits", kind="int", default=3, min=1, max=10, label="Videos pushed to YouTube per day",
                          help="A safety brake: AI Eye refuses a run that would push more than this many videos today. Runs are still 1 or 3 videos at a time."),
    "TTS_STYLE":     dict(group="Narration", kind="longtext", default=TTS_STYLE, label="Narrator direction",
                          help="Tone and pacing instructions sent with every line of narration."),
    "VOICE_POOL":    dict(group="Narration", kind="voices", default=["marin", "cedar", "nova", "coral", "sage", "ash", "ballad", "verse"],
                          choices=_VOICES, label="Voices used when shuffling",
                          help="A batch with shuffled voices picks from these. Keep at least two."),
    "KID_RULES":     dict(group="Narration", kind="longtext", default=KID_RULES, label="Reading level and tone rules",
                          help="Rules every script follows. Change them if your audience is not 8 to 12 years old."),
    "MOTION":        dict(group="Look", kind="choice", default="medium", choices=["low", "medium", "high"], label="Zoom strength",
                          help="How far the slow zoom travels on every picture."),
    "SHOT_XFADE":    dict(group="Look", kind="float", default=0.28, min=0.0, max=0.6, label="Crossfade length (seconds)",
                          help="Blend between two pictures of the same scene."),
    "CAPTION_STYLE": dict(group="Look", kind="choice", default="plate", choices=["plate", "text"], label="Caption highlight",
                          help="plate: the spoken word sits on a coloured plate. text: the word itself is coloured."),
    "CAPTION_COLOR_MODE": dict(group="Look", kind="choice", default="shuffle", choices=["shuffle", "fixed"], label="Caption colours",
                          help="shuffle: a new highlight colour on each caption. fixed: always the accent colour."),
    "CAPTION_ACCENT": dict(group="Look", kind="color", default="#FFD93B", label="Caption accent colour",
                          help="Used when caption colours are fixed."),
    "CAPTION_MAX_WORDS": dict(group="Look", kind="int", default=5, min=2, max=8, label="Words per caption",
                          help="Most words on screen at once."),
    "RENDER_WORKERS": dict(group="Look", kind="int", default=3, min=1, max=6, label="Scenes rendered at once",
                          help="Higher is faster but needs more memory."),
}

def validate(key, value):
    """The cleaned value, or ValueError with a message the user can act on."""
    spec = TUNABLES.get(key)
    if not spec:
        raise ValueError(f"Unknown setting {key}")
    kind, label = spec["kind"], spec["label"]
    try:
        if kind == "int":
            v = int(value)
        elif kind == "float":
            v = round(float(value), 2)
        elif kind in ("text", "longtext"):
            v = str(value).strip()
            if not v:
                raise ValueError(f"{label} cannot be empty. Use Reset to go back to the default.")
            if kind == "text" and (len(v) > 80 or re.search(r"\s", v)):
                raise ValueError(f"{label} must be one word or id, like gpt-image-2.5-flare.")
            if len(v) > 4000:
                raise ValueError(f"{label} is too long (4000 characters at most).")
        elif kind == "choice":
            v = str(value)
            if v not in spec["choices"]:
                raise ValueError(f"{label} must be one of: {', '.join(spec['choices'])}.")
        elif kind == "color":
            v = str(value).strip()
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                raise ValueError(f"{label} must look like #FFD93B.")
            v = v.upper()                      # the colour picker sends lowercase; keep one spelling so "unchanged" stays unchanged
        elif kind == "voices":
            v = [x for x in value if x in spec["choices"]]
            if len(set(v)) < 2:
                raise ValueError(f"{label}: pick at least two voices.")
            v = list(dict.fromkeys(v))
    except (TypeError, ValueError) as e:
        raise ValueError(str(e) if "cannot" in str(e) or "must" in str(e) or "pick" in str(e) or "long" in str(e) else f"{label}: that is not a valid value.")
    if kind in ("int", "float") and not (spec["min"] <= v <= spec["max"]):
        raise ValueError(f"{label} must be between {spec['min']} and {spec['max']}.")
    return v

def load_overrides():
    """Saved changes, with anything invalid dropped (so a hand-edited file can never break a run)."""
    try:
        raw = json.loads(TUNE_FILE.read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in (raw.items() if isinstance(raw, dict) else []):
        try:
            out[k] = validate(k, v)
        except ValueError:
            pass
    return out

_OVER = load_overrides()

def tune(key):
    """The value to use: your saved change, else the default."""
    return _OVER.get(key, TUNABLES[key]["default"])

def save_overrides(values):
    """Save only what differs from the defaults. `values` maps key -> value; raises ValueError on the first bad one."""
    clean = {}
    for k, v in values.items():
        v = validate(k, v)
        if v != TUNABLES[k]["default"]:
            clean[k] = v
    TUNE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if clean:
        TUNE_FILE.write_text(json.dumps(clean, indent=2, ensure_ascii=False))
    else:
        TUNE_FILE.unlink(missing_ok=True)
    return clean
