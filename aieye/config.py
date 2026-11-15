"""Settings, model names, prices and file locations."""
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from .tuning import tune

ROOT       = Path(__file__).resolve().parent.parent
DATA_DIR   = ROOT / "data"                     # everything generated or personal lives here (git-ignored)
OUTPUT_DIR = DATA_DIR / "output"               # one folder per video; deleted once the video is posted
DB_DIR     = DATA_DIR / "db"
DRAFT_DB   = DB_DIR / "draft.json"             # topic queue
FINAL_DB   = DB_DIR / "final.json"             # one slim line per finished video
SETTINGS_FILE = DATA_DIR / "settings.json"     # your saved defaults
CREDS_DIR      = DATA_DIR / "credentials"
CLIENT_SECRETS = CREDS_DIR / "client_secrets.json"
YOUTUBE_TOKEN  = CREDS_DIR / "youtube_token.pickle"
N_SCENES   = tune("N_SCENES")
MAX_SHOTS  = tune("MAX_SHOTS")          # pictures per scene: the scene's narration is split into 2-3 shots, one image each
MIN_SHOT_WORDS = tune("MIN_SHOT_WORDS")      # shorter shots are merged into a neighbour (too-short cuts read as flicker)
IMAGE_WORKERS = tune("IMAGE_WORKERS")       # scenes whose images are generated at the same time (kept low: image APIs rate-limit quickly)
EXPECTED_SHOTS = 2.2    # average pictures per scene, used for the cost estimate only
EDIT_REF_COST  = 0.014  # extra cost of a reference-image edit vs a fresh picture (the reference is billed as input)
N_TOPICS   = tune("N_TOPICS")

# Categories `aieye run -top` rotates through, one per video. Override with "top_categories" in data/channel.json.
TOP_CATEGORIES = [
    "bizarre animals and animal adaptations (one striking animal, shown close up)",
    "space and astronomy at cosmic scale (planets, galaxies, black holes, nebulae)",
    "underwater and deep-sea creatures (ocean animals, reefs, trenches)",
    "everyday 'what if' and 'can you' puzzles with common objects (a straw, a pizza, a shadow, a spinning skater)",
]

GPT_MODEL     = tune("GPT_MODEL")
# Pinned snapshot: measured with a "slow" vs "fast" instruction, the March 2025 snapshot changed
# pace ~2x and had the most natural pitch movement; the current alias and the 2025-12-15
# snapshot barely reacted to the instructions parameter. Falls back to the alias if retired.
TTS_MODEL     = tune("TTS_MODEL")
TTS_FALLBACK  = "gpt-4o-mini-tts"
TTS_VOICE     = "marin"
TTS_STYLE     = tune("TTS_STYLE")
IMAGE_MODEL   = tune("IMAGE_MODEL")
IMAGE_SIZE    = "1024x1536"

GPT_IN_COST  = 0.10
GPT_OUT_COST = 0.50
TTS_COST     = 16.70   # per 1M chars — estimate (~$0.015/min of speech); API returns no usage
IMAGE_COST   = {"low": 0.005, "medium": 0.010, "high": 0.041}   # 1024x1536 output tokens × $30/1M
IMAGE_OUT_COST, IMAGE_IN_COST, IMAGE_TEXT_IN_COST = 30.0, 8.0, 5.0   # $ per 1M tokens (gpt-image-2.5)

CHANNEL_FILE = DATA_DIR / "channel.json"       # YOUR channel's identity (git-ignored); copy channel.example.json to start
CHANNEL = {                                    # generic defaults, so the framework works out of the box
    "handle": "",
    "url":    "",
    "tags":   ["Shorts", "Facts", "Science", "Learning"],
    "description": (
        "Science, space, nature, history, psychology: "
        "the most fascinating things about our universe, explained simply and fast.\n"
        "{scene_facts}\n\n"
        "#Shorts #Facts #Science #Learning"
    ),
}
try:
    import json as _json
    CHANNEL.update(_json.loads(CHANNEL_FILE.read_text()))
except (OSError, ValueError):
    pass

# Runtime config — set via CLI prompts
CFG = {
    "manual_topic":   None,
    "image_quality":  "medium",
    "image_style":    "representational",
    "upload_privacy": "public",
    "tts_voice":      TTS_VOICE,
    "batch_voice":    "shuffle",
}



# Who the videos are for and what topics to prefer or avoid. Used in every topic prompt. Override the whole text with
# "audience_notes" in data/channel.json (e.g. paste in what has worked on YOUR channel); the default is generic.
AUDIENCE_NOTES = """AUDIENCE: curious kids aged 8 to 12 (and the grown-ups who watch with them). Every topic must make sense to
a fourth grader with no background. Family-safe, always.

What tends to work (patterns only; never copy a subject that was already made):
- ONE striking thing a kid can picture in one second: a single animal, object or place, shown big and close.
- A question whose obvious answer feels wrong.
- Weird animal bodies and behaviours. Gross-but-harmless is great; scary is not.
- Size, speed, age and distance a kid can feel, using comparisons to things they know.
- Everyday things kids have touched or seen.

What tends not to work (avoid): abstract ideas with nothing to see, generic "top 5" lists, anything aimed at adults.

STRICT RULES
- Every topic is a NEW subject: never an animal, object, place or phenomenon already made, even from a new angle.
- No death, injury to people, violence, war, disasters, disease, drugs, scary or gross-out-for-shock content.
- No medical or safety advice, no brands, no real private people.
- If a kid could not explain it back to a friend after one watch, it is too hard: pick something simpler."""
DEFAULT_AUDIENCE_NOTES, DEFAULT_TOP_CATEGORIES = AUDIENCE_NOTES, list(TOP_CATEGORIES)   # the generic defaults (the channel file may replace them)
AUDIENCE_NOTES = CHANNEL.get("audience_notes", AUDIENCE_NOTES)
TOP_CATEGORIES = CHANNEL.get("top_categories", TOP_CATEGORIES)

# Reading level and tone for the script (used in every script pass).
KID_RULES = tune("KID_RULES")
