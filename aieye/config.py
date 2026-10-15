"""Settings, model names, prices and file locations."""
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

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
N_SCENES   = 5
MAX_SHOTS  = 3          # pictures per scene: the scene's narration is split into 2-3 shots, one image each
MIN_SHOT_WORDS = 5      # shorter shots are merged into a neighbour (too-short cuts read as flicker)
IMAGE_WORKERS = 3       # scenes whose images are generated at the same time (kept low: image APIs rate-limit quickly)
EXPECTED_SHOTS = 2.2    # average pictures per scene, used for the cost estimate only
EDIT_REF_COST  = 0.014  # extra cost of a reference-image edit vs a fresh picture (the reference is billed as input)
N_TOPICS   = 10

GPT_MODEL     = "gpt-6-luna"
# Pinned snapshot: measured with a "slow" vs "fast" instruction, the March 2025 snapshot changed
# pace ~2x and had the most natural pitch movement; the current alias and the 2025-12-15
# snapshot barely reacted to the instructions parameter. Falls back to the alias if retired.
TTS_MODEL     = "gpt-4o-mini-tts-2025-03-20"
TTS_FALLBACK  = "gpt-4o-mini-tts"
TTS_VOICE     = "marin"
TTS_STYLE     = ("Voice: a curious, warm storyteller talking to one friend, relaxed and natural, never an announcer. "
                 "Pacing: conversational and a little quick, with short pauses at sentence ends. "
                 "Emphasis: land on the surprising word. Avoid sing-song and forced excitement.")
IMAGE_MODEL   = "gpt-image-2.5-flare"
IMAGE_SIZE    = "1024x1536"

GPT_IN_COST  = 0.10
GPT_OUT_COST = 0.50
TTS_COST     = 16.70   # per 1M chars — estimate (~$0.015/min of speech); API returns no usage
IMAGE_COST   = {"low": 0.005, "medium": 0.010, "high": 0.041}   # 1024x1536 output tokens × $30/1M
IMAGE_OUT_COST, IMAGE_IN_COST, IMAGE_TEXT_IN_COST = 30.0, 8.0, 5.0   # $ per 1M tokens (gpt-image-2.5)

CHANNEL = {
    "handle": "@AIEyeFacts",
    "url":    "https://www.youtube.com/channel/UCLYrvFHE_D45TNq93qIprYw",
    "tags":   ["Shorts", "AI", "Facts", "YouTube Shorts", "Science", "Learning", "AIEye"],
    "description": (
        "5 facts. 60 seconds. Mind blown.\n\n"
        "Science, space, nature, history, psychology — "
        "the most fascinating things about our universe, "
        "explained simply and fast.\n\n"
        "Follow @AIEyeFacts — new Short every day.\n"
        "{scene_facts}\n\n"
        "#Shorts #AIEye #Facts #Science #Learning"
    ),
}

# Runtime config — set via CLI prompts
CFG = {
    "manual_topic":   None,
    "image_quality":  "medium",
    "image_style":    "representational",
    "upload_privacy": "public",
    "tts_voice":      TTS_VOICE,
    "batch_voice":    "shuffle",
}


