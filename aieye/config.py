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

# Top-performing categories (from the channel analytics). `aieye run -top` rotates through these, one per video.
# Food/geography lists were tested and flopped (durian 16 views, chocolate 40, pancakes 2), so they are NOT here.
TOP_CATEGORIES = [
    "bizarre animals and animal adaptations (one striking animal, shown close up)",
    "space and astronomy at cosmic scale (planets, galaxies, black holes, nebulae)",
    "underwater and deep-sea creatures (ocean animals, reefs, trenches)",
    "everyday 'what if' and 'can you' puzzles with common objects (a straw, a pizza, a shadow, a spinning skater)",
]

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



# What works for THIS channel (YouTube Studio, Oct 2026) as PATTERNS, never as subjects to copy: naming the winners made
# the topic model re-make them (fish/lizard/galaxy repeats got 5-60x fewer views than the originals). Edit the text,
# not the code, when the analytics change.
AUDIENCE_NOTES = """AUDIENCE: curious kids aged 8 to 12 (and the grown-ups who watch with them). Every topic must make sense to
a fourth grader with no background. Family-safe, always.

What has worked on this channel (patterns only; never copy a subject that was already made):
- ONE striking thing a kid can picture in one second: a single animal, object or place, shown big and close.
- A question whose obvious answer feels wrong ("Would X notice if Y disappeared?", "Can N cuts make M pieces?").
- Weird animal bodies and behaviours. Gross-but-harmless is great; scary is not.
- Size, speed, age and distance a kid can feel, using comparisons to things they know (a school bus, a pizza).
- Everyday things kids have touched or seen: a straw in a glass, a shadow, a spinning chair.

What has NOT worked (avoid): abstract ideas with nothing to see (number theory, proofs, philosophy), food-and-travel
lists, generic "top 5" lists, anything aimed at adults (money, politics, news, celebrities).

STRICT RULES
- Every topic is a NEW subject: never an animal, object, place or phenomenon already made, even from a new angle.
- No death, injury to people, violence, war, disasters, disease, drugs, scary or gross-out-for-shock content.
- No medical or safety advice, no brands, no real private people.
- If a kid could not explain it back to a friend after one watch, it is too hard: pick something simpler."""

# Reading level and tone for the script (used in every script pass).
KID_RULES = """KID LEVEL (strict)
- Write for a curious 10-year-old. Use words a fourth grader already knows. If a science word is truly needed,
  explain it in the same sentence in plain words, and use at most one such word per video.
- Short sentences: most under 12 words, none over 20. One idea per sentence.
- Compare with things a kid knows (a school bus, a football field, a pizza, a pet), not with abstractions.
- Playful and a little funny, never babyish and never scary. Nothing about death, injury, violence or disasters.
- Ask the viewer one thing to picture or guess, early, then pay it off."""
