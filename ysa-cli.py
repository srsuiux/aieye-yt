import os, re, sys, time, json, base64, subprocess, shutil, pickle, threading
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ════════════════════════════════════════════════════════════
# CONFIG — internals, do not touch
# ════════════════════════════════════════════════════════════

def _find_ffmpeg():
    """Prefer the ffmpeg 7.x bundled with imageio-ffmpeg (installed with moviepy): ~40% faster renders
    than ffmpeg 4.3 and it includes libass. Falls back to whatever `ffmpeg` is on PATH."""
    cands = [os.getenv("AIEYE_FFMPEG")]
    try:
        import imageio_ffmpeg
        cands.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    cands.append("ffmpeg")
    for c in cands:
        if not c:
            continue
        try:
            if subprocess.run([c, "-version"], capture_output=True).returncode == 0:
                return c
        except Exception:
            continue
    return "ffmpeg"

FFMPEG = _find_ffmpeg()

OUTPUT_DIR = Path("shorts_output")
DB_DIR     = Path("db")
DRAFT_DB   = DB_DIR / "draft.json"
FINAL_DB   = DB_DIR / "final.json"
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

_total_cost = 0.0

# ════════════════════════════════════════════════════════════
# COLOURS & LOGGING
# ════════════════════════════════════════════════════════════

C = {
    "reset":  "\033[0m",
    "cyan":   "\033[96m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "bold":   "\033[1m",
    "dim":    "\033[2m",
    "white":  "\033[97m",
    "purple": "\033[95m",
}

def c(text, col): return f"{C.get(col,'')}{text}{C['reset']}"

def log(msg, color="reset", indent=0):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{c(f'[{ts}]','dim')} {'  '*indent}{c(msg, color)}")

def section(title):
    print()
    print(c("─"*60, "cyan"))
    print(c(f"  {title}", "bold"))
    print(c("─"*60, "cyan"))

def ok(msg):   log(f"✅  {msg}", "green")
def warn(msg): log(f"⚠️   {msg}", "yellow")
def skip(msg): log(f"⏭   {msg} (cached)", "dim")
def fail(msg):
    log(f"❌  {msg}", "red")
    sys.exit(1)

def track(label, amount):
    global _total_cost
    _total_cost += amount
    log(f"💰  [{label}] ${amount:.4f}  |  total: ${_total_cost:.4f}", "yellow")

# ════════════════════════════════════════════════════════════
# SPINNER — shows while any blocking call runs
# ════════════════════════════════════════════════════════════

class Spinner:
    FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

    def __init__(self, label):
        self.label   = label
        self._stop   = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            print(f"\r  {c(frame,'cyan')} {c(self.label,'dim')}   ", end="", flush=True)
            time.sleep(0.08)
            i += 1
        print(f"\r{' '*60}\r", end="", flush=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()


def spin(label):
    """Use as: with spin('Doing thing...'): do_thing()"""
    return Spinner(label)

# ════════════════════════════════════════════════════════════
# CLI PROMPT — interactive setup
# ════════════════════════════════════════════════════════════

def prompt_choice(question, choices):
    """Show numbered choices, return selected value."""
    print()
    print(c(f"  {question}", "bold"))
    for i, (label, value, hint) in enumerate(choices, 1):
        print(f"  {c(str(i),'cyan')}  {c(label,'white')}  {c(hint,'dim')}")
    print()
    while True:
        try:
            raw = input(c("  → Enter number: ", "yellow")).strip()
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                label, value, _ = choices[idx]
                ok(f"Selected: {label}")
                return value
            print(c("  Invalid choice — try again", "red"))
        except (ValueError, KeyboardInterrupt):
            print(c("  Invalid — try again", "red"))

def prompt_text(question, default=None):
    """Free text input. Returns None if blank and default is None."""
    print()
    hint = f" (leave blank to {default or 'skip'})" if default else " (leave blank to skip)"
    print(c(f"  {question}{hint}", "bold"))
    try:
        raw = input(c("  → ", "yellow")).strip()
        return raw if raw else default
    except KeyboardInterrupt:
        return default

# ════════════════════════════════════════════════════════════
# SETTINGS — saved defaults, run modes
# ════════════════════════════════════════════════════════════

SETTINGS_FILE = Path(__file__).resolve().parent / "aieye_settings.json"
BATCH_DEFAULT = 5
SETTING_CHOICES = {
    "image_style":    ["representational", "realistic", "illustrated"],
    "image_quality":  list(IMAGE_COST),
    "upload_privacy": ["public", "private", "unlisted", "none"],
    "tts_voice":      ["marin", "cedar", "nova", "alloy", "echo", "fable", "onyx", "shimmer", "coral", "sage", "ash", "ballad", "verse"],
    "batch_voice":    ["shuffle", "same"],
}
OPTIONAL_SETTINGS = {"batch_voice": "shuffle"}     # missing in older settings files → use this
# Voices used when a batch shuffles narrators. Samples of every voice are in voice_samples/ — edit to taste.
VOICE_POOL = ["marin", "cedar", "nova", "coral", "sage", "ash", "ballad", "verse"]

def shuffled_voices(count):
    """`count` narrators from VOICE_POOL: no repeats until the pool is used up, never the same twice in a row."""
    import random
    out = []
    while len(out) < count:
        round_ = random.sample(VOICE_POOL, len(VOICE_POOL))
        if out and round_[0] == out[-1] and len(round_) > 1:
            round_.append(round_.pop(0))
        out += round_
    return out[:count]

def load_defaults():
    """Saved defaults, or None if never saved. Invalid/unknown values are dropped."""
    try:
        raw = json.load(open(SETTINGS_FILE))
    except Exception:
        return None
    saved = {}
    for k, ok_vals in SETTING_CHOICES.items():
        if raw.get(k) in ok_vals:
            saved[k] = raw[k]
        elif k in OPTIONAL_SETTINGS:
            saved[k] = OPTIONAL_SETTINGS[k]
        else:
            return None
    return saved

def save_defaults():
    data = {k: CFG[k] for k in SETTING_CHOICES}
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    ok(f"Defaults saved → {SETTINGS_FILE.name}")

def describe(cfg, batch=False):
    privacy = {"none": "no upload"}.get(cfg["upload_privacy"], cfg["upload_privacy"])
    voice   = "shuffled voices" if batch and cfg.get("batch_voice") == "shuffle" else cfg["tts_voice"]
    return f"{cfg['image_style']} · {cfg['image_quality']} · {voice} · {privacy}"

def est_cost_per_video(quality):
    # One fresh picture per scene, plus reference edits for the extra shots. An edit costs a fresh picture plus
    # ~$0.014 for the reference image it is billed for as input (measured). Plus script + narration.
    base = IMAGE_COST[quality]
    extra_shots = N_SCENES * (EXPECTED_SHOTS - 1)
    return base * N_SCENES + (base + EDIT_REF_COST) * extra_shots + 0.02

def print_header():
    print()
    print(c("═"*60, "bold"))
    print(c("  AI Eye  —  Shorts Pipeline", "bold"))
    print(c("  Production-ready YouTube Shorts automation", "dim"))
    print(c("═"*60, "bold"))

def prompt_settings(ask_topic=True):
    """Ask for every setting (topic optional) and store it in CFG."""
    if ask_topic:
        manual = prompt_text(
            "Enter a custom topic, or leave blank to auto-pick from queue"
        )
        CFG["manual_topic"] = manual or None

    CFG["image_style"] = prompt_choice(
        "Image style?",
        [
            ("Representational + Labels",
             "representational",
             "Diagrams, infographics, labeled arrows — best for facts"),
            ("Realistic",
             "realistic",
             "Photorealistic scenes — cinematic, immersive"),
            ("Illustrated",
             "illustrated",
             "Bold graphic art, vivid colors, stylised visuals"),
        ]
    )

    CFG["image_quality"] = prompt_choice(
        "Image quality?",
        [
            ("Low",    "low",    f"~${IMAGE_COST['low']:.3f}/image  —  fast, cost-efficient"),
            ("Medium", "medium", f"~${IMAGE_COST['medium']:.3f}/image  —  recommended, clear labels"),
            ("High",   "high",   f"~${IMAGE_COST['high']:.3f}/image  —  sharpest text and detail"),
        ]
    )

    CFG["upload_privacy"] = prompt_choice(
        "YouTube upload privacy?",
        [
            ("Public",   "public",   "Goes live immediately after upload"),
            ("Private",  "private",  "Only you can see it — review first"),
            ("Unlisted", "unlisted", "Anyone with the link can watch"),
            ("Don't upload", "none", "Render only — saves short.mp4 in shorts_output/"),
        ]
    )

    CFG["tts_voice"] = prompt_choice(
        "Narrator voice?",
        [
            ("Marin",   "marin",   "Natural, lively female  —  OpenAI's best-quality voice (default)"),
            ("Cedar",   "cedar",   "Natural, grounded male  —  OpenAI's best-quality voice"),
            ("Nova",    "nova",    "Warm, upbeat female"),
            ("Alloy",   "alloy",   "Neutral, balanced  —  clear and professional"),
            ("Echo",    "echo",    "Smooth male  —  calm and authoritative"),
            ("Fable",   "fable",   "Expressive British  —  storytelling feel"),
            ("Onyx",    "onyx",    "Deep, rich male  —  dramatic and bold"),
            ("Shimmer", "shimmer", "Soft, gentle female  —  friendly and warm"),
            ("Coral",   "coral",   "Warm, friendly female"),
            ("Sage",    "sage",    "Calm, thoughtful"),
            ("Ash",     "ash",     "Clear, steady male"),
            ("Ballad",  "ballad",  "Smooth, expressive"),
            ("Verse",   "verse",   "Bright, dynamic"),
        ]
    )

    CFG["batch_voice"] = prompt_choice(
        "Voices when making several videos?",
        [
            ("Shuffle",    "shuffle", f"A different narrator on each video (pool of {len(VOICE_POOL)}: {', '.join(VOICE_POOL)})"),
            ("Same voice", "same",    "Use the narrator chosen above for every video"),
        ]
    )

def print_run_config(count):
    per   = est_cost_per_video(CFG["image_quality"])
    print()
    print(c("  ── Run Configuration ─────────────────────────", "cyan"))
    print(f"  Videos     {c(str(count), 'cyan')}")
    print(f"  Topic      {c(CFG['manual_topic'] or 'Auto from queue', 'cyan')}")
    print(f"  Style      {c(CFG['image_style'], 'cyan')}")
    img_cost = IMAGE_COST[CFG["image_quality"]]
    print(f"  Quality    {c(CFG['image_quality'], 'cyan')}  {c('(~$%.3f/image)' % img_cost, 'dim')}")
    voice_line = "shuffled — a different narrator on each video" if (count > 1 and CFG["batch_voice"] == "shuffle") else CFG["tts_voice"]
    print(f"  Voice      {c(voice_line, 'cyan')}")
    print(f"  Privacy    {c(CFG['upload_privacy'], 'cyan')}")
    total = f"~${per*count:.2f}" if count > 1 else f"~${per:.2f}"
    print(f"  Est. cost  {c(total, 'yellow')}" + (c(f"  (~${per:.2f} each)", "dim") if count > 1 else ""))
    if CFG["upload_privacy"] == "public":
        who, when = ("These", "they finish") if count > 1 else ("This", "it finishes")
        print(c(f"  ⚠  {who} will be published publicly as soon as {when}.", "yellow"))
    print(c("  ────────────────────────────────────────────────", "cyan"))
    print()

def confirm_start(wait=None):
    """wait=None → press ENTER; wait=N → N-second cancel window (Ctrl+C to stop)."""
    try:
        if wait:
            for s in range(wait, 0, -1):
                print(f"\r  {c('Starting in', 'bold')} {c(str(s), 'yellow')}{c('…  (Ctrl+C to cancel)', 'dim')}   ", end="", flush=True)
                time.sleep(1)
            print()
        else:
            input(c("  Press ENTER to start, or Ctrl+C to cancel  ", "bold"))
    except KeyboardInterrupt:
        print()
        print(c("  Cancelled.", "dim"))
        sys.exit(0)

def get_args():
    import argparse
    ap = argparse.ArgumentParser(description="AI Eye Shorts pipeline")
    ap.add_argument("--quick", action="store_true", help="make 1 video with your saved defaults, no questions")
    ap.add_argument("--batch", type=int, metavar="N", help="make N videos with your saved defaults, no questions")
    ap.add_argument("--setup", action="store_true", help="choose and save your default settings, then exit")
    ap.add_argument("--yes", action="store_true", help="skip the countdown before starting")
    ap.add_argument("--topic", help="custom topic (single video only)")
    ap.add_argument("--privacy", choices=SETTING_CHOICES["upload_privacy"],
                    help="override the saved privacy for this run only")
    ap.add_argument("--quality", choices=SETTING_CHOICES["image_quality"],
                    help="override the saved image quality for this run only")
    return ap.parse_args()

def setup_run(args):
    """Decide the settings and how many videos to make. Returns the video count."""
    saved = load_defaults()
    print_header()

    if args.setup:
        print(c("\n  Choose your default settings.", "white"))
        prompt_settings(ask_topic=False)
        save_defaults()
        print(f"\n  {c('Saved:', 'green')} {describe(CFG)}\n")
        sys.exit(0)

    # ── Non-interactive: one command / one click ──────────
    if args.quick or args.batch:
        if not saved:
            fail("No saved defaults yet. Run once:  python3 ysa-cli.py --setup")
        CFG.update(saved)
        if args.privacy:
            CFG["upload_privacy"] = args.privacy
        if args.quality:
            CFG["image_quality"] = args.quality
        count = max(1, args.batch or 1)
        if args.topic and count == 1:
            CFG["manual_topic"] = args.topic
        print_run_config(count)
        if not args.yes:
            confirm_start(5)
        return count

    # ── Interactive ───────────────────────────────────────
    if not saved:
        print(c("\n  First run — let's set your default settings (one time).", "white"))
        prompt_settings(ask_topic=False)
        save_defaults()
        count = prompt_choice("How many videos?", [
            ("1 video", 1, "One Short"),
            (f"{BATCH_DEFAULT} videos", BATCH_DEFAULT, "A batch, back to back"),
        ])
        print_run_config(count)
        confirm_start()
        return count

    while True:
        CFG.update(saved)
        per = est_cost_per_video(saved["image_quality"])
        mode = prompt_choice("What would you like to do?", [
            ("Make 1 video", "one", f"{describe(saved)}  ·  ~${per:.2f}"),
            (f"Make {BATCH_DEFAULT} videos", "batch", f"{describe(saved, batch=True)}  ·  ~${per*BATCH_DEFAULT:.2f}"),
            ("Customize this run", "custom", "Pick a topic and settings just for this run"),
            ("Change saved defaults", "defaults", "Edit and save the settings used by the options above"),
        ])
        if mode == "defaults":
            prompt_settings(ask_topic=False)
            save_defaults()
            saved = load_defaults()
            continue
        break

    if mode in ("one", "batch"):
        count = 1 if mode == "one" else BATCH_DEFAULT
        if args.privacy:
            CFG["upload_privacy"] = args.privacy
        print_run_config(count)
        confirm_start(3)
        return count

    prompt_settings(ask_topic=True)
    count = 1
    if not CFG["manual_topic"]:
        count = prompt_choice("How many videos?", [
            ("1 video", 1, "One Short"),
            (f"{BATCH_DEFAULT} videos", BATCH_DEFAULT, "A batch, back to back"),
        ])
    if prompt_choice("Save these settings as your defaults?", [
        ("No",  False, "Use them for this run only"),
        ("Yes", True,  "Replace the saved defaults"),
    ]):
        save_defaults()
    print_run_config(count)
    confirm_start()
    return count

# ════════════════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════════════════

def load_db(path):
    return json.load(open(path)) if path.exists() else []

def save_db(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

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

def mark_done(topic, out_dir, script):
    draft = [t for t in load_db(DRAFT_DB) if t["id"] != topic["id"]]
    save_db(DRAFT_DB, draft)
    final = load_db(FINAL_DB)
    final.append({
        "id":           topic["id"],
        "title":        script["title"],
        "topic":        topic["title"],
        "video":        str(out_dir / "short.mp4"),
        "metadata":     str(out_dir / "youtube_metadata.json"),
        "cost":         round(_total_cost, 4),
        "quality":      CFG["image_quality"],
        "style":        CFG["image_style"],
        "voice":        CFG["tts_voice"],
        "privacy":      CFG["upload_privacy"],
        "completed_at": datetime.now().isoformat(),
        "scenes":       [{"scene": s["scene"], "narration": s["narration"]} for s in script["scenes"]],
    })
    save_db(FINAL_DB, final)
    ok(f"Logged to final DB — {len(final)} shorts completed total")

def log_youtube_id(topic_id, video_id):
    final = load_db(FINAL_DB)
    for e in final:
        if e.get("id") == topic_id:
            e["youtube_id"]  = video_id
            e["youtube_url"] = f"https://youtube.com/shorts/{video_id}"
    save_db(FINAL_DB, final)

# ════════════════════════════════════════════════════════════
# CHECKPOINTS
# ════════════════════════════════════════════════════════════

def save_ckpt(out_dir, name, data):
    with open(out_dir / f".ckpt_{name}.json", "w") as f:
        json.dump(data, f, indent=2)

def load_ckpt(out_dir, name):
    p = out_dir / f".ckpt_{name}.json"
    return json.load(open(p)) if p.exists() else None

# ════════════════════════════════════════════════════════════
# OPENAI CLIENT
# ════════════════════════════════════════════════════════════

def get_client():
    try:
        from openai import OpenAI
    except ImportError:
        fail("pip install openai")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        fail("OPENAI_API_KEY not set in .env or environment")
    return OpenAI(api_key=key)

# ════════════════════════════════════════════════════════════
# STEP 0 — TOPIC SELECTION
# ════════════════════════════════════════════════════════════

def generate_topics(client):
    used      = all_used_titles()
    used_list = "\n".join(f"- {t}" for t in sorted(used)) or "None yet."

    prompt = f"""You are a YouTube Shorts content strategist.
Generate exactly {N_TOPICS} unique viral-worthy YouTube Shorts topics for a general
audience — kids and adults. Categories: science, space, animals, nature, history,
technology, psychology, geography, math, physics.

Already used — do NOT repeat:
{used_list}

Be specific: not "facts about space" but "5 ways neutron stars defy physics".

Return ONLY valid JSON:
{{
  "topics": [
    {{"title": "...", "hook": "one sentence why this is fascinating"}},
    ...
  ]
}}"""

    with spin("Generating fresh topics..."):
        res = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort="none",
            temperature=0.9,
            response_format={"type": "json_object"},
        )
    usage   = res.usage
    in_tok  = getattr(usage, "prompt_tokens",     0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    track("gpt topics", (in_tok/1e6*GPT_IN_COST)+(out_tok/1e6*GPT_OUT_COST))

    data   = json.loads(res.choices[0].message.content)
    topics = data.get("topics", [])
    fresh  = [t for t in topics if t["title"].lower() not in used]
    ok(f"{len(fresh)} fresh topics generated")
    for i, t in enumerate(fresh):
        log(f"{i+1}. {t['title']}", "cyan", indent=2)
    return fresh

def pick_topic(client):
    section("STEP 0  —  Topic Selection")

    if CFG["manual_topic"]:
        log(f"Manual: \"{CFG['manual_topic']}\"", "cyan", indent=1)
        return {
            "id":         f"manual_{int(time.time())}",
            "title":      CFG["manual_topic"],
            "hook":       "",
            "status":     "manual",
            "created_at": datetime.now().isoformat(),
        }

    pending = get_pending()
    if pending:
        topic = pending[0]
        log(f"From queue: \"{topic['title']}\"", "cyan", indent=1)
        log(f"{len(pending)-1} more pending after this", "dim", indent=1)
        return topic

    warn("Queue empty — generating new topics...")
    fresh = generate_topics(client)

    now     = datetime.now().isoformat()
    entries = [
        {"id": f"topic_{int(time.time())}_{i}", "title": t["title"],
         "hook": t.get("hook",""), "status": "pending", "created_at": now}
        for i, t in enumerate(fresh)
    ]
    save_db(DRAFT_DB, entries)
    ok(f"Saved {len(entries)} topics to queue")
    topic = entries[0]
    log(f"Starting: \"{topic['title']}\"", "cyan", indent=1)
    return topic

# ════════════════════════════════════════════════════════════
# STEP 1 — SCRIPT
# ════════════════════════════════════════════════════════════

def build_visual_prompt_style():
    """Return style instructions based on user's image style choice."""
    if CFG["image_style"] == "realistic":
        return (
            "Style: photorealistic, cinematic, dramatic lighting, high detail. "
            "Real-world scene that illustrates the fact visually. "
            "No text overlays needed — pure visual storytelling."
        )
    elif CFG["image_style"] == "illustrated":
        return (
            "Style: bold graphic illustration, vivid saturated colors, strong outlines. "
            "Comic-book meets science poster aesthetic. "
            "May include short labels or title text if it adds clarity."
        )
    else:  # representational
        return (
            "Style: scientific textbook diagram, NASA explainer infographic. "
            "Dark navy background (#0a0a1a), bold accent colors, high contrast. "
            "MUST include: labeled arrows (thick), callout boxes, annotated parts. "
            "All label text: short (1-4 words), large, bold, clearly legible. "
            "Name every element — what shape, what color, what label, where arrows point."
        )

BANNED = [
    "delve", "tapestry", "testament", "realm", "unveil", "unleash", "game-changer", "game changer",
    "mind-blowing", "little-known", "forever", "shocking", "stunning", "let that sink in",
    "buckle up", "imagine a world", "iconic", "numerous", "it's not just", "not just a",
    "in conclusion", "reminds us", "remind us",
]

CONTRACTIONS = [
    (r"\bit is\b", "it's"), (r"\bthat is\b", "that's"), (r"\bthere is\b", "there's"),
    (r"\bwhat is\b", "what's"), (r"\bhere is\b", "here's"), (r"\bwho is\b", "who's"),
    (r"\bdoes not\b", "doesn't"), (r"\bdo not\b", "don't"), (r"\bdid not\b", "didn't"),
    (r"\bis not\b", "isn't"), (r"\bare not\b", "aren't"), (r"\bwas not\b", "wasn't"),
    (r"\bcannot\b", "can't"), (r"\bcan not\b", "can't"), (r"\bwill not\b", "won't"),
    (r"\bthey are\b", "they're"), (r"\bwe are\b", "we're"), (r"\byou are\b", "you're"),
    (r"\bit has\b(?= (?:been|a|an|the|no)\b)", "it's"),
]

def contract(text):
    """Turn stiff 'It is' / 'does not' into how people actually talk (keeps capitalisation)."""
    for pat, rep in CONTRACTIONS:
        text = re.sub(pat, lambda m: rep.capitalize() if m.group(0)[0].isupper() else rep,
                      text, flags=re.IGNORECASE)
    return text

def merge_shots(shots):
    """Keep at most MAX_SHOTS shots and none shorter than MIN_SHOT_WORDS (too-short shots become a flicker).
    Merged narration is never dropped: it joins the neighbouring shot."""
    out = []
    for sh in shots:
        if out and len(sh["narration"].split()) < MIN_SHOT_WORDS:
            out[-1] = {"narration": out[-1]["narration"] + " " + sh["narration"], "visual_prompt": out[-1]["visual_prompt"]}
        else:
            out.append(dict(sh))
    if len(out) > 1 and len(out[0]["narration"].split()) < MIN_SHOT_WORDS:
        out[1] = {"narration": out[0]["narration"] + " " + out[1]["narration"], "visual_prompt": out[0]["visual_prompt"]}
        out.pop(0)
    while len(out) > MAX_SHOTS:
        last = out.pop()
        out[-1] = {"narration": out[-1]["narration"] + " " + last["narration"], "visual_prompt": out[-1]["visual_prompt"]}
    return out

def scan_script(data):
    """Warn about AI-sounding phrases and length problems (does not modify the script)."""
    total = 0
    for s in data["scenes"]:
        text = s["narration"].lower()
        words = len(text.split())
        total += words
        hits = [b for b in BANNED if b in text]
        if hits:
            warn(f"Scene {s['scene']}: AI-sounding phrase(s): {', '.join(hits)}")
        if any(ch in s["narration"] for ch in "—–…!%&()"):
            warn(f"Scene {s['scene']}: contains characters TTS reads badly (— … ! % & parentheses)")
        if not 12 <= words <= 34:
            warn(f"Scene {s['scene']}: {words} words (target 14-30)")
    if not 100 <= total <= 150:
        warn(f"Total narration {total} words (target 110-135)")
    return total

def generate_script(client, topic, out_dir):
    section("STEP 1  —  Script Generation  (3-pass agent)")

    cached = load_ckpt(out_dir, "script")
    if cached:
        skip(f"Script: \"{cached['title']}\"")
        return cached

    log(f"Topic: {topic['title']}", indent=1)
    style_instructions = build_visual_prompt_style()

    # ── PASS 1: Research, fact safety, through-line ──────
    log("Pass 1/3 — Researching facts...", "dim", indent=1)
    research_prompt = f"""You are a careful fact-checker who is also a great science storyteller.
Topic: "{topic['title']}"

Find the {N_SCENES} most surprising facts about this topic, and one through-line that ties them together.

Rules:
- Include a fact ONLY if you are highly confident it is true and widely documented.
  If you're unsure of an exact number, describe it loosely ("roughly", "more than", "about")
  or drop the fact. Never invent statistics, dates, studies or quotes.
- Prefer facts a 12-year-old could repeat to a friend at lunch.
- Prefer physical, everyday comparisons (a football field, a thumbnail, a car) over abstractions.
- Skip anything that's just a scary headline. We want wonder, not doom.

For each fact give:
1. The fact, stated precisely
2. Why it violates intuition
3. The best everyday comparison
4. Confidence: high or medium

Then write:
THROUGH-LINE: one question or tension the Short can open in its first line and pay off in its last.

Plain text, numbered 1-{N_SCENES}. No JSON."""

    with spin("Researching facts..."):
        research_res = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": research_prompt}],
            reasoning_effort="low",   # reasoning models only accept default temperature
        )
    research     = research_res.choices[0].message.content
    usage        = research_res.usage
    in_tok       = getattr(usage, "prompt_tokens",     0) if usage else 0
    out_tok      = getattr(usage, "completion_tokens", 0) if usage else 0
    track("gpt research", (in_tok/1e6*GPT_IN_COST)+(out_tok/1e6*GPT_OUT_COST))
    ok("Facts researched")

    # ── PASS 2: Write the script draft ───────────────────
    log("Pass 2/3 — Writing script draft...", "dim", indent=1)
    draft_prompt = f"""You are writing the voiceover for a YouTube Short, the way a smart, funny friend
would tell it out loud. A text-to-speech voice will read it, so write for the EAR, not the eye.

Topic: "{topic['title']}"

Researched facts and through-line:
{research}

STRUCTURE ({N_SCENES} scenes)
- Scene 1 (hook): open with the most surprising fact, and open the through-line as a question or
  tension. No greeting, no "did you know", no "welcome".
- Scenes 2-{N_SCENES-1}: one fact each. Each scene must pick up from the one before it with a natural
  hand-off, and never reuse the same hand-off ("Here's the weird part." / "But it gets stranger." /
  "So why doesn't it fall?").
- Scene {N_SCENES}: pay off the through-line with a specific image or a small twist.
  No moral, no summary, no "this reminds us".

SOUND HUMAN
- Talk to one person. Use "you" and contractions (it's, doesn't, that's, can't).
- Vary rhythm: include a very short sentence (2-5 words) and a longer flowing one (14-22 words).
  Don't give every sentence the same shape.
- 14-30 words per scene (all its shots together), about 110-135 words in total.
- Concrete beats abstract: a number plus a comparison beats an adjective.
- Sentence fragments are fine when a person would say them ("Not even close.").
- No headline voice. Not "Toxic oceans threaten life." Say what happens the way you'd tell a friend.
- Never use: delve, tapestry, testament, realm, unveil, unleash, game-changer, mind-blowing,
  little-known, forever, shocking, stunning, iconic, numerous, "let that sink in", "buckle up",
  "imagine a world", "it's not just X, it's Y", or a tidy list of three.

MAKE IT SPEAKABLE (the voice reads exactly what you write)
- Write numbers the way they're said: "sixty percent", "twenty sixty", "five thousand years",
  "C O two". No symbols (% & °), no parentheses, no abbreviations, no em dashes.
- Use commas and periods for rhythm; a comma is a small breath.
  No ellipses and no exclamation marks; the voice overacts on them.

STYLE REFERENCE ONLY (never reuse these facts)
  Headline voice: "Cacao flowers sprout directly from the trunk. Tiny midges pollinate them."
  Spoken voice:   "Cacao flowers don't grow on branches. They grow straight out of the trunk. And the only thing that pollinates them is a midge smaller than a grain of rice."
  Headline voice: "Toxic oceans threaten life. Coral reefs suffocate under rising CO2 levels."
  Spoken voice:   "The ocean is getting more acidic, and coral skeletons are starting to dissolve."

SHOTS (a new picture every few seconds)
- Split every scene into 2-{MAX_SHOTS} shots, only at sentence boundaries. Each shot has its own "narration"
  (1-2 sentences, about 6-16 words) and its own "visual_prompt" showing what THAT part says.
  The scene's spoken narration is simply its shots' narrations read in order; there is no separate scene text.
- Vary the framing between shots (wide establishing view, then close-up, then a detail, comparison or
  consequence) while keeping the same subject, setting and look. Shots 2-{MAX_SHOTS} are generated from
  shot 1 as a reference image, so write them as "the same scene, now ..." (what changes: angle, distance, detail).
- Each shot must be a picture that could be held on screen for 2-4 seconds: one clear subject, no clutter.

DELIVERY: for each scene write a "delivery" note, 4-12 words, telling the voice actor how to
perform THAT scene (for example "quiet and intrigued, slow down on the last word" or
"quicker, a little amused"). Vary them; at most one scene may be "excited".

VISUALS
{style_instructions}
- "visual_style": one short paragraph describing the look ALL {N_SCENES} images share (palette, rendering
  style, any recurring motif), so the set feels like one video.
- Each "visual_prompt" describes only what's specific to that shot. Be literal: name every element,
  label, arrow, color and position.
- Layout: the main subject sits in the upper-middle of the frame. Keep the bottom third simple and
  uncluttered (plain background, no text, no key objects) because captions go there.
  Keep any label inside the central 80% of the width.

TITLE: under 60 characters, curious and honest. No "You Won't Believe", no all caps.

Return ONLY valid JSON:
{{
  "title": "...",
  "visual_style": "...",
  "scenes": [
    {{"scene": 1, "delivery": "...", "shots": [
        {{"narration": "...", "visual_prompt": "..."}},
        {{"narration": "...", "visual_prompt": "..."}}
    ]}},
    ... one object per scene, {N_SCENES} in total, each with 2-{MAX_SHOTS} shots ...
  ]
}}"""

    with spin("Writing first draft..."):
        draft_res = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": draft_prompt}],
            reasoning_effort="none",
            temperature=0.85,
            response_format={"type": "json_object"},
        )
    draft_data = json.loads(draft_res.choices[0].message.content)
    usage      = draft_res.usage
    in_tok     = getattr(usage, "prompt_tokens",     0) if usage else 0
    out_tok    = getattr(usage, "completion_tokens", 0) if usage else 0
    track("gpt draft", (in_tok/1e6*GPT_IN_COST)+(out_tok/1e6*GPT_OUT_COST))
    ok("Draft written")

    # ── PASS 3: Read-aloud edit ──────────────────────────
    log("Pass 3/3 — Read-aloud edit...", "dim", indent=1)
    critique_prompt = f"""You are a veteran voiceover director. A text-to-speech voice will read this
script aloud, and it must sound like a real person telling a friend something amazing.

Draft:
{json.dumps(draft_data, indent=2)}

Read every narration aloud in your head and fix:
1. Written, not spoken: headline fragments, noun-stack openers, formal words (threaten, surge,
   numerous, iconic), passive voice. Rewrite the way a person would actually say it.
2. AI tells: banned words (delve, tapestry, unveil, unleash, mind-blowing, forever, shocking, stunning),
   tidy lists of three, "not just X but Y", every scene the same length or shape,
   a moral or summary in the last scene.
3. Flow: does each scene pick up from the previous one with a varied hand-off? Does the last scene
   pay off the tension opened in scene 1?
4. Truth: any statistic, date or claim you are not sure about becomes softer ("roughly", "more than")
   or is replaced with something you're sure of. Never add new unverified numbers.
5. Speakability: numbers written as words; no symbols, dashes, parentheses, ellipses or exclamation
   marks; reword anything hard to pronounce.
6. Length: 14-30 words per scene, 110-135 total.
7. Delivery notes: concrete, varied, 4-12 words each.
8. Visuals: keep visual_style and visual_prompts, but make sure the bottom third of every image is
   plain and uncluttered and the subject is upper-middle. Make prompts more literal where vague.
9. Shots: every scene keeps 2-{MAX_SHOTS} shots split only at sentence boundaries, each shot 1-2 sentences.
   Shots 2-{MAX_SHOTS} must read as "the same scene, now ..." (new angle, distance or detail, same subject and look).
   Do not add a separate scene-level narration; the shots' narrations are the script.

Return ONLY the improved script as valid JSON, same structure (title, visual_style, scenes with
scene, delivery, shots[narration, visual_prompt])."""

    with spin("Editing for spoken delivery..."):
        final_res = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": critique_prompt}],
            reasoning_effort="medium",
            response_format={"type": "json_object"},
        )
    data    = json.loads(final_res.choices[0].message.content)
    usage   = final_res.usage
    in_tok  = getattr(usage, "prompt_tokens",     0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    track("gpt rewrite", (in_tok/1e6*GPT_IN_COST)+(out_tok/1e6*GPT_OUT_COST))

    # ── Validate ─────────────────────────────────────────
    if len(data.get("scenes", [])) != N_SCENES:
        fail(f"Expected {N_SCENES} scenes, got {len(data.get('scenes',[]))}")
    data["visual_style"] = (data.get("visual_style") or "").strip()
    for s in data["scenes"]:
        shots = s.get("shots") or [{"narration": s.get("narration", ""), "visual_prompt": s.get("visual_prompt", "")}]
        shots = [{"narration": contract((sh.get("narration") or "").strip()),
                  "visual_prompt": (sh.get("visual_prompt") or "").strip()}
                 for sh in shots if (sh.get("narration") or "").strip()]
        if not shots:
            fail(f"Scene {s.get('scene')}: no narration in the script")
        shots = merge_shots(shots)
        s["shots"]         = shots
        s["narration"]     = " ".join(sh["narration"] for sh in shots)     # what the voice reads for the whole scene
        s["visual_prompt"] = shots[0]["visual_prompt"]
        s["delivery"]      = (s.get("delivery") or "").strip()

    total_words = scan_script(data)
    n_shots = sum(len(s["shots"]) for s in data["scenes"])
    ok(f"Script ready: \"{data['title']}\"  ({total_words} words, {n_shots} shots)")
    for s in data["scenes"]:
        log(f"Scene {s['scene']} [{len(s['shots'])} shots]: {s['narration'][:62]}", indent=2)

    save_ckpt(out_dir, "script", data)
    return data

# ════════════════════════════════════════════════════════════
# STEP 2 — AUDIO
# ════════════════════════════════════════════════════════════

def speechify(text):
    """Make narration safe for a TTS voice: no dashes/symbols it would read oddly."""
    t = text.replace("—", ", ").replace("–", ", ").replace("…", ".")
    t = re.sub(r"\s*&\s*", " and ", t).replace("%", " percent")
    t = re.sub(r"\bCO2\b", "C O two", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.?])", r"\1", t)
    t = re.sub(r",\s*,", ",", t)
    return t.strip()

def polish_audio(raw, out):
    """Trim dead air at both ends, gentle compression, tiny pad so scene cuts breathe."""
    sil = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04"
    run_cmd([
        FFMPEG, "-y", "-i", str(raw),
        "-af", f"{sil},areverse,{sil},areverse,"
               "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=80,"
               "afade=t=in:d=0.01,apad=pad_dur=0.12",
        "-ar", "48000", "-ac", "1", str(out),
    ], label="audio polish")

def tts_request(client, model, text, instructions):
    return client.audio.speech.create(
        model=model, voice=CFG["tts_voice"], input=text,
        instructions=instructions, response_format="wav",
    )

def generate_audio(client, script, out_dir):
    section(f"STEP 2  —  Audio Generation  ({TTS_MODEL} · {CFG['tts_voice']})")
    paths = []
    model = TTS_MODEL
    for s in script["scenes"]:
        label = s["scene"]
        path  = out_dir / f"frame_{label}_audio.wav"
        if path.exists():
            skip(f"frame_{label}_audio.wav")
            paths.append(path)
            continue
        text  = speechify(s["narration"])
        instr = TTS_STYLE + (f" For this line: {s['delivery']}." if s.get("delivery") else "")
        with spin(f"Generating audio — frame {label}..."):
            try:
                res = tts_request(client, model, text, instr)
            except Exception as e:
                if model == TTS_FALLBACK:
                    raise
                warn(f"{model} unavailable ({str(e)[:80]}) — falling back to {TTS_FALLBACK}")
                model = TTS_FALLBACK
                res = tts_request(client, model, text, instr)
            raw = out_dir / f"frame_{label}_audio_raw.wav"
            raw.write_bytes(res.read())
        polish_audio(raw, path)
        raw.unlink()
        track(f"tts {label}", (len(text)/1e6)*TTS_COST)
        ok(f"frame_{label}_audio.wav")
        paths.append(path)
    ok(f"{len(paths)} audio files ready")
    return paths

# ════════════════════════════════════════════════════════════
# STEP 3 — IMAGES
# ════════════════════════════════════════════════════════════

LAYOUT_SUFFIX = ("Vertical 2:3 composition: main subject in the upper-middle of the frame; keep the bottom "
                 "third plain and uncluttered (no text, no key objects); keep all labels inside the central 80% width.")

def call_with_retry(fn, what="request", tries=8):
    """Run an API call; on a rate limit (429) wait as long as the API asks (or back off) and try again.
    Out-of-credits errors are not rate limits and are raised immediately."""
    import random
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if "insufficient_quota" in msg or "credit_balance_exhausted" in msg:
                raise
            if e.__class__.__name__ != "RateLimitError" and "429" not in msg:
                raise
            m = re.search(r"try again in\s*([0-9.]+)\s*(ms|s|m)\b", msg)
            asked = 0.0
            if m:
                asked = float(m.group(1)) * {"ms": 0.001, "s": 1, "m": 60}[m.group(2)]
            wait = min(65.0, max(asked + 1.0, 6.0 * (attempt + 1))) + random.uniform(0, 2)
            warn(f"Rate limit on {what} — waiting {wait:.0f}s (attempt {attempt + 1}/{tries})")
            time.sleep(wait)
    raise RuntimeError(f"{what}: rate limit did not clear after {tries} tries")

def image_call_cost(res, quality):
    """Real cost of one image call from the API's token usage; falls back to the table if usage is missing."""
    try:
        u = res.usage
        return (u.input_tokens_details.image_tokens / 1e6 * IMAGE_IN_COST
                + u.input_tokens_details.text_tokens / 1e6 * IMAGE_TEXT_IN_COST
                + u.output_tokens / 1e6 * IMAGE_OUT_COST)
    except Exception:
        return IMAGE_COST[quality]

def generate_images(client, script, out_dir):
    """One picture per shot. Shot 1 of a scene is generated fresh; shots 2+ are edited from shot 1 as a
    reference so the subject, setting and look stay the same while the camera changes. Scenes run in parallel.
    Returns a list (per scene) of lists of image paths."""
    section(f"STEP 3  —  Image Generation  ({IMAGE_MODEL} · {CFG['image_quality']} · {CFG['image_style']})")

    clarity_suffix = (
        " All text labels must be large, bold, clearly legible. "
        "Short labels only (1-4 words). Thick visible arrows. High contrast."
        if CFG["image_style"] == "representational" else ""
    )
    quality = CFG["image_quality"]

    def one_scene(s):
        label, paths, cost, made = s["scene"], [], 0.0, 0
        shots = s.get("shots") or [{"narration": s["narration"], "visual_prompt": s["visual_prompt"]}]
        first = None
        for k, shot in enumerate(shots):
            path = out_dir / f"frame_{label}_shot{k + 1}_image.png"
            paths.append(path)
            if path.exists():
                first = first or path
                continue
            prompt = " ".join(x for x in [
                script.get("visual_style", ""), shot["visual_prompt"], clarity_suffix.strip(), LAYOUT_SUFFIX,
            ] if x)
            res = None
            if first is not None:
                try:
                    def edit_call():
                        with open(first, "rb") as ref:
                            return client.images.edit(
                                model=IMAGE_MODEL, image=ref, size=IMAGE_SIZE, quality=quality,
                                prompt=("Keep the same subject(s), setting, lighting, colour grade and visual style as the "
                                        "reference image, but show a different camera shot of this same scene. New shot: " + prompt),
                            )
                    res = call_with_retry(edit_call, f"scene {label} shot {k + 1} (edit)")
                except Exception as e:
                    if "insufficient_quota" in str(e) or "credit_balance_exhausted" in str(e):
                        raise
                    warn(f"Scene {label} shot {k + 1}: reference edit failed ({str(e)[:80]}) — generating it directly")
                    res = None
            if res is None:
                res = call_with_retry(
                    lambda: client.images.generate(model=IMAGE_MODEL, prompt=prompt, size=IMAGE_SIZE, quality=quality, n=1),
                    f"scene {label} shot {k + 1}")
            if not res.data or not res.data[0].b64_json:
                fail(f"Scene {label} shot {k + 1}: empty response from API")
            path.write_bytes(base64.b64decode(res.data[0].b64_json))
            cost += image_call_cost(res, quality)
            made += 1
            first = first or path
        return paths, cost, made

    from concurrent.futures import ThreadPoolExecutor
    total_shots = sum(len(s.get("shots") or [1]) for s in script["scenes"])
    with spin(f"Generating {total_shots} images ({len(script['scenes'])} scenes in parallel)..."):
        with ThreadPoolExecutor(max_workers=IMAGE_WORKERS) as ex:
            results = list(ex.map(one_scene, script["scenes"]))

    all_paths, cost, made = [], 0.0, 0
    for s, (paths, c_, m_) in zip(script["scenes"], results):
        all_paths.append(paths)
        cost += c_; made += m_
        ok(f"Scene {s['scene']}: {len(paths)} image(s)  " + "  ".join(f"{p.stat().st_size//1024} KB" for p in paths))
    if made:
        track(IMAGE_MODEL, cost)
    ok(f"{sum(len(p) for p in all_paths)} images ready")
    return all_paths

# ════════════════════════════════════════════════════════════
# STEP 4 — AUDIO DURATIONS
# ════════════════════════════════════════════════════════════

def get_durations(audio_paths, out_dir):
    section("STEP 4  —  Audio Durations  (ffprobe)")
    cached = load_ckpt(out_dir, "durations")
    if cached:
        skip(f"Durations for {len(cached)} clips")
        return cached

    durations = []
    for path in audio_paths:
        r = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ], capture_output=True, text=True)
        dur = float(r.stdout.strip())
        log(f"{path.name}: {dur:.2f}s", indent=2)
        durations.append(dur)

    save_ckpt(out_dir, "durations", durations)
    ok("All durations measured")
    return durations

# ════════════════════════════════════════════════════════════
# STEP 5 — VIDEO ASSEMBLY
# ════════════════════════════════════════════════════════════

def run_cmd(cmd, label="ffmpeg"):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"{label} stderr:\n{r.stderr[-600:]}", "red")
        fail(f"{label} exited {r.returncode}")
    return r

# ════════════════════════════════════════════════════════════
# CAPTIONS — word alignment + rendered highlight cards
# ════════════════════════════════════════════════════════════

CAPTION_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/Library/Fonts/Arial Black.ttf",
    str(Path.home() / "Library/Fonts/Arial Black.ttf"),
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
CAPTION_STYLE     = "plate"     # "plate" = highlighted word on a coloured plate, "text" = coloured word
CAPTION_ACCENT    = "#FFD93B"
CAPTION_COLOR_MODE = "shuffle"  # "shuffle" = a different highlight colour on each caption card, "fixed" = CAPTION_ACCENT
CAPTION_PALETTE   = ["#FFD93B", "#5CF28E", "#4FD8FF", "#FF6FB5", "#FF9A3C", "#B69CFF"]  # yellow, green, cyan, pink, orange, lilac
CAPTION_LEAD_CARD = 0.10        # seconds a new caption card appears before its first word is spoken
CAPTION_LEAD_WORD = 0.04        # seconds the highlight moves onto a word before it is spoken
CAPTION_MAX_WORDS = 5
CAPTION_MAX_CHARS = 32
CAPTION_MAX_W     = 940         # px, inside the 1080 frame (Shorts side buttons live on the right)
CAPTION_CANVAS    = (1080, 400)
CAPTION_TOP       = 1230        # y of the card canvas on the 1920 frame → text sits ~y1430, above the Shorts UI

def _word_weight(w):
    letters = re.sub(r"[^A-Za-z0-9]", "", w)
    return max(1, len(re.findall(r"[aeiouy]+", letters.lower()))) + 0.25 * len(letters)

def _speech_profile(wav_path):
    """Return (speech_start, speech_end, gaps[(start, end)]) measured from the real audio."""
    import numpy as np
    r = subprocess.run([FFMPEG, "-v", "error", "-i", str(wav_path), "-f", "s16le", "-ac", "1",
                        "-ar", "16000", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    hop, win = 160, 320                       # 10 ms hop, 20 ms window
    frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop]
    rms    = np.sqrt((frames ** 2).mean(axis=1))
    thr    = max(0.004, 0.08 * float(np.percentile(rms, 90)))
    idx    = np.where(rms > thr)[0]
    if len(idx) == 0:
        raise ValueError("no speech detected")
    first, last = int(idx[0]), int(idx[-1])
    gaps, run = [], None
    for i in range(first, last + 1):
        if rms[i] <= thr:
            run = i if run is None else run
        elif run is not None:
            if i - run >= 9:                  # ≥ 90 ms of silence inside speech
                gaps.append((run * 0.01, i * 0.01))
            run = None
    return first * 0.01, (last + 1) * 0.01, gaps

def _align_heuristic(text, wav_path):
    """Estimate (word, start, end) for each word by pinning punctuation to the audio's real pauses.
    Independent of any transcription API (whisper-1 is being retired); words between two
    detected pauses are spread by syllable-ish weight."""
    words = text.split()
    n = len(words)
    try:
        t0, t1, gaps = _speech_profile(wav_path)
    except Exception:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "default=nw=1:nk=1", str(wav_path)], capture_output=True, text=True).stdout or 3)
        t0, t1, gaps = 0.0, max(0.5, dur - 0.12), []

    W      = [_word_weight(w) for w in words]
    pause  = [0.32 if w[-1] in ".?!" else 0.16 if w[-1] in ",;:" else 0.0 for w in words]
    pause[-1] = 0.0
    speech_time = max(0.3, (t1 - t0) - sum(pause))
    rate   = sum(W) / speech_time             # weight units per second

    # Pure-estimate word starts (used to predict where each punctuation pause should fall).
    start, acc = [], t0
    for i in range(n):
        start.append(acc)
        acc += W[i] / rate + pause[i]
    bounds = [i for i in range(n - 1) if pause[i] > 0]
    pred   = [start[i + 1] - pause[i] / 2 for i in bounds]

    # Monotonic matching of punctuation boundaries → detected gaps (DP, small sizes).
    B, G, INF, SKIP = len(bounds), len(gaps), 1e9, 0.5
    dp = [[INF] * (G + 1) for _ in range(B + 1)]
    bk = [[None] * (G + 1) for _ in range(B + 1)]
    for j in range(G + 1):
        dp[0][j] = 0.0
    for b in range(1, B + 1):
        for j in range(G + 1):
            best, how = dp[b - 1][j] + SKIP, "skipb"
            if j > 0:
                if dp[b][j - 1] < best:
                    best, how = dp[b][j - 1], "skipg"
                d = abs(pred[b - 1] - (gaps[j - 1][0] + gaps[j - 1][1]) / 2)
                if d < 1.0 and dp[b - 1][j - 1] + d < best:
                    best, how = dp[b - 1][j - 1] + d, "match"
            dp[b][j], bk[b][j] = best, how
    matched, b, j = {}, B, G
    while b > 0:
        how = bk[b][j]
        if how == "match":
            matched[bounds[b - 1]] = gaps[j - 1]; b -= 1; j -= 1
        elif how == "skipg":
            j -= 1
        else:
            b -= 1

    # Walk the words in segments delimited by matched pauses; spread each segment by weight.
    out, seg_start, i = [], t0, 0
    while i < n:
        j = i
        while j < n - 1 and j not in matched:
            j += 1
        seg_end = matched[j][0] if j in matched else t1
        ws = [W[k] + (pause[k] * rate if (k != j and k in bounds) else 0.0) for k in range(i, j + 1)]
        total, t = sum(ws), seg_start
        for k, wk in zip(range(i, j + 1), ws):
            share = (seg_end - seg_start) * wk / total
            out.append([words[k], t, t + share]); t += share
        seg_start = matched[j][1] if j in matched else t1
        i = j + 1
    for k in range(n - 1):                    # a word stays "active" until the next one starts
        out[k][2] = out[k + 1][1]
    return [tuple(o) for o in out]

_FA = {}

def _load_forced_aligner():
    """torchaudio's MMS_FA model (built for forced alignment; ~1.2 GB, downloaded once and cached)."""
    if "model" not in _FA:
        import torchaudio
        bundle = torchaudio.pipelines.MMS_FA
        _FA["model"] = bundle.get_model(with_star=False).eval()
        _FA["dict"]  = bundle.get_dict(star=None)
    return _FA["model"], _FA["dict"]

def _align_forced(text, wav_path):
    """Word timings by CTC forced alignment of the known script against the real audio (~30-50 ms accurate).
    Runs locally: no API call, nothing to be retired. Raises if torch/torchaudio are missing."""
    import numpy as np, torch, torchaudio
    model, dic = _load_forced_aligner()
    words = text.split()
    clean = [re.sub(r"[^a-z']", "", w.lower()) for w in words]
    idx   = [i for i, c in enumerate(clean) if c]
    if len(idx) < max(2, len(words) // 2):
        raise ValueError("too few alignable words")
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(wav_path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True).stdout
    wav = torch.from_numpy(np.frombuffer(raw, dtype=np.float32).copy()).unsqueeze(0)
    with torch.inference_mode():
        emission, _ = model(wav)
    targets = torch.tensor([[dic[ch] for i in idx for ch in clean[i]]], dtype=torch.int32)
    aligned, scores = torchaudio.functional.forced_align(emission, targets, blank=0)
    spans  = torchaudio.functional.merge_tokens(aligned[0], scores[0].exp())
    stride = wav.shape[1] / emission.shape[1] / 16000
    got, k = {}, 0
    for i in idx:
        n = len(clean[i]); sp = spans[k:k + n]; k += n
        got[i] = (sp[0].start * stride, sp[-1].end * stride)

    total = wav.shape[1] / 16000
    out = [[w, *(got[i] if i in got else (None, None))] for i, w in enumerate(words)]
    for i, o in enumerate(out):                       # digits etc. with no letters: share the time between neighbours
        if o[1] is None:
            j = i
            while j < len(out) and out[j][1] is None:
                j += 1
            left  = out[i - 1][2] if i > 0 else 0.0
            right = out[j][1] if j < len(out) else total
            step  = (right - left) / (j - i + 1)
            for m in range(i, j):
                out[m][1], out[m][2] = left + step * (m - i), left + step * (m - i + 1)
    try:                                              # safety net: no word may start inside a real silence
        _, _, gaps = _speech_profile(wav_path)
        for g0, g1 in gaps:
            for o in out:
                if g0 + 0.05 < o[1] < g1 - 0.03:
                    o[1] = g1
    except Exception:
        pass
    for k in range(len(out) - 1):                     # a word stays "active" until the next one starts
        out[k][2] = max(out[k + 1][1], out[k][1] + 0.05)
    return [tuple(o) for o in out]

_ALIGN_WARNED = False

def align_words(text, wav_path):
    """Forced alignment when torch/torchaudio are available, otherwise the pause-anchored estimate."""
    global _ALIGN_WARNED
    try:
        return _align_forced(text, wav_path)
    except Exception as e:
        if not _ALIGN_WARNED:
            warn(f"Forced alignment unavailable ({type(e).__name__}: {str(e)[:80]}) — using estimated caption timing")
            _ALIGN_WARNED = True
        return _align_heuristic(text, wav_path)

def group_cards(words):
    """Caption cards of up to CAPTION_MAX_WORDS words / CAPTION_MAX_CHARS characters.
    A card never spans a sentence end (so cards line up with the picture changes), and a long sentence is
    cut into even pieces, preferably right after a comma, instead of leaving a 1-word straggler."""
    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if w[0][-1] in ".?!":
            sentences.append(cur); cur = []
    if cur:
        sentences.append(cur)

    def chars(ws):
        return sum(len(x[0]) + 1 for x in ws) - 1

    cards = []
    for s in sentences:
        n = len(s)
        for k in range(1, n + 1):                                    # fewest pieces that all fit
            base, extra = divmod(n, k)
            sizes = [base + (1 if i < extra else 0) for i in range(k)]
            cuts, acc = [], 0
            for sz in sizes[:-1]:
                acc += sz
                cuts.append(acc)
            for ci, cut in enumerate(cuts):                          # nudge a cut to sit right after a comma if one is adjacent
                lo = (cuts[ci - 1] if ci else 0) + 1
                hi = (cuts[ci + 1] if ci + 1 < len(cuts) else n) - 1
                for cand in (cut, cut - 1, cut + 1):
                    if lo <= cand <= hi and s[cand - 1][0][-1] in ",;:":
                        cuts[ci] = cand
                        break
            pieces = [s[a:b] for a, b in zip([0] + cuts, cuts + [n])]
            if all(len(p) <= CAPTION_MAX_WORDS and chars(p) <= CAPTION_MAX_CHARS for p in pieces) or k == n:
                cards += pieces
                break
    return cards

def find_caption_font():
    return next((f for f in CAPTION_FONTS if Path(f).exists()), None)

def _font(size):
    from PIL import ImageFont
    path = find_caption_font()
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default(size)

def _layout(labels):
    """Pick the largest font size where the card fits in ≤2 balanced lines. Returns (size, [[idx..], ..])."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for size in (84, 78, 72, 66, 60, 54):
        f     = _font(size)
        space = d.textlength(" ", font=f)
        wid   = [d.textlength(t, font=f) for t in labels]
        def width(ix): return sum(wid[k] for k in ix) + space * (len(ix) - 1)
        allw = list(range(len(labels)))
        if width(allw) <= CAPTION_MAX_W and len(labels) <= 3:
            return size, [allw]
        best = None
        for cut in range(1, len(labels)):
            a, b = allw[:cut], allw[cut:]
            m = max(width(a), width(b))
            if best is None or m < best[0]:
                best = (m, [a, b])
        if best and best[0] <= CAPTION_MAX_W:
            return size, best[1]
    return 54, [allw[:len(allw) // 2 or 1], allw[len(allw) // 2 or 1:]] if len(allw) > 1 else [allw]

def render_card(card, active, path, color=CAPTION_ACCENT):
    """Render one caption state (all words visible, word #active highlighted) to a transparent PNG."""
    from PIL import Image, ImageDraw, ImageFilter
    labels = [w[0].upper().rstrip(",.;:") for w in card]
    size, lines = _layout(labels)
    f      = _font(size)
    W, H   = CAPTION_CANVAS
    d0     = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    space  = d0.textlength(" ", font=f)
    lh     = int(size * 1.22)
    top    = (H - lh * len(lines)) // 2
    plates, texts = [], []
    for li, ix in enumerate(lines):
        widths = [d0.textlength(labels[k], font=f) for k in ix]
        x      = (W - (sum(widths) + space * (len(ix) - 1))) / 2
        base   = top + li * lh + int(size * 0.9)
        for k, wd in zip(ix, widths):
            texts.append((k, x, base, wd))
            x += wd + space
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    plate  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    main   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, dp_, dm = ImageDraw.Draw(shadow), ImageDraw.Draw(plate), ImageDraw.Draw(main)
    for k, x, base, wd in texts:
        is_act = (k == active)
        ds.text((x, base + 7), labels[k], font=f, fill=(0, 0, 0, 200), anchor="ls", stroke_width=9, stroke_fill=(0, 0, 0, 200))
        if is_act and CAPTION_STYLE == "plate":
            pad = int(size * 0.16)
            dp_.rounded_rectangle((x - pad, base - size * 0.86 - pad * 0.3, x + wd + pad, base + size * 0.22 + pad * 0.3),
                                  radius=int(size * 0.24), fill=color)
            dm.text((x, base), labels[k], font=f, fill="#14141c", anchor="ls")
        elif is_act:
            dm.text((x, base), labels[k], font=f, fill=color, anchor="ls", stroke_width=8, stroke_fill="black")
        else:
            dm.text((x, base), labels[k], font=f, fill="white", anchor="ls", stroke_width=8, stroke_fill="black")
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    out = Image.alpha_composite(Image.alpha_composite(shadow, plate), main)
    if path is not None:
        out.save(path)
    return out

def caption_events(words, speech_end):
    """Return (card_index, card, active_word_index, t_start, t_end) for every highlight state."""
    # Captions lead the voice slightly: a caption that appears a beat early is invisible to the viewer,
    # one that appears late reads as lag. Each state runs until the next state starts (no gaps, no overlaps).
    events = []
    cards  = group_cards(words)
    starts = [[max(0.0, w[1] - (CAPTION_LEAD_CARD if wi == 0 else CAPTION_LEAD_WORD)) for wi, w in enumerate(card)]
              for card in cards]
    for ci, card in enumerate(cards):
        card_end = starts[ci + 1][0] if ci + 1 < len(cards) else speech_end + 0.1
        for wi, w in enumerate(card):
            a = starts[ci][wi]
            b = starts[ci][wi + 1] if wi + 1 < len(card) else card_end
            events.append((ci, card, wi, a, max(b, a + 0.05)))
    return events

MOTION = "medium"                       # "low" | "medium" | "high" — how far the slow zoom travels

# ── Smooth motion: ONE slow, eased zoom per scene (in on one scene, out on the next) ─────
MOTION_CAP = {"low": 0.06, "medium": 0.10, "high": 0.14}      # extra zoom reached over a full-length scene
RENDER_WORKERS = 3                                              # scenes rendered at the same time

def _smootherstep(p):
    p = min(1.0, max(0.0, p))
    return p * p * p * (p * (6 * p - 15) + 10)               # zero speed at both ends → no jolt

def zoom_at(t, dur, idx):
    cap = MOTION_CAP[MOTION]
    amp = min(cap, max(cap * 0.55, cap * dur / 9.0))         # short scenes move a little less
    e   = _smootherstep(t / dur)
    return 1.0 + amp * (e if idx % 2 == 0 else 1.0 - e)      # even scenes zoom in, odd scenes zoom out

def focus_at(t, dur, idx):
    """Where in the picture the zoom is aimed: a very slow drift around the upper-middle."""
    e = _smootherstep(t / dur) - 0.5
    return 0.5 + 0.05 * e * (1 if idx % 4 < 2 else -1), 0.42 + 0.06 * e * (1 if idx % 2 == 0 else -1)

SHOT_XFADE = 0.28      # seconds of crossfade between two pictures of the same scene

def shot_starts(words, shots, dur):
    """[(start_time, shot_index)]: each picture appears as its sentence begins (a touch early, like the captions).
    A cut that would land too close to the previous one or to the end of the scene is dropped."""
    starts, wi = [(0.0, 0)], 0
    for k, sh in enumerate(shots[:-1]):
        wi += len(speechify(sh["narration"]).split())
        if wi >= len(words):
            break
        t = max(0.0, words[wi][1] - CAPTION_LEAD_CARD)
        if t - starts[-1][0] >= 1.4 and dur - t >= 1.0:
            starts.append((t, k + 1))
    return starts

def _prep_shot(path, W, H):
    """Load one picture and build its blurred, darkened backdrop (done once per picture)."""
    from PIL import Image, ImageFilter, ImageEnhance
    src    = Image.open(path).convert("RGB")
    sw, sh = src.size
    k      = max(W / sw, H / sh)
    cover  = src.resize((max(W, round(sw * k)), max(H, round(sh * k))), Image.BILINEAR)
    left, top = (cover.width - W) // 2, (cover.height - H) // 2
    small  = cover.crop((left, top, left + W, top + H)).resize((W // 4, H // 4), Image.BILINEAR)
    bg     = ImageEnhance.Brightness(small.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BICUBIC)).enhance(0.85)
    return src, sw, sh, bg

def build_clip_v2(imgs, audio, dur, narration, idx, tmp, clip, palette=None, color_offset=0, seed=0, words=None, shots=None):
    """Render one scene frame by frame with Pillow and pipe raw frames to ffmpeg.
    A scene can hold several pictures (shots): each gets its own slow zoom and they crossfade as the
    narration moves from one sentence to the next. Sub-pixel zoom, blurred backdrop, highlighted captions.
    Returns the number of caption cards."""
    from PIL import Image
    W, H, FH, FPS = 1080, 1920, 1620, 30
    words      = words or align_words(speechify(narration), audio)
    speech_end = max(0.5, dur - 0.12)
    cards      = group_cards(words)
    events     = caption_events(words, speech_end)
    palette    = palette or [CAPTION_ACCENT]

    imgs   = [imgs] if isinstance(imgs, (str, Path)) else list(imgs)
    starts = shot_starts(words, shots, dur) if (shots and len(imgs) > 1) else [(0.0, 0)]
    assets = [_prep_shot(imgs[min(si, len(imgs) - 1)], W, H) for _, si in starts]
    XF     = SHOT_XFADE
    spans  = []                                          # time window in which each picture is moving
    for j, (t0, _) in enumerate(starts):
        a = 0.0 if j == 0 else t0 - XF / 2
        b = dur if j == len(starts) - 1 else starts[j + 1][0] + XF / 2
        spans.append((a, b))

    def shot_frame(j, t):
        a, b   = spans[j]
        L      = max(b - a, 0.5)
        tau    = min(max(t - a, 0.0), L)
        gi     = idx * MAX_SHOTS + j                     # alternates zoom-in / zoom-out from picture to picture
        z      = zoom_at(tau, L, gi)
        fx, fy = focus_at(tau, L, gi)
        src, sw, sh, bg_j = assets[j]
        cw, ch = sw / z, sh / z                          # crop window inside the source
        x0, y0 = (sw - cw) * fx, (sh - ch) * fy
        fg = src.transform((W, FH), Image.AFFINE, (cw / W, 0, x0, 0, ch / FH, y0), resample=Image.BICUBIC)
        fr = bg_j.copy()
        fr.paste(fg, (0, (H - FH) // 2))
        return fr

    cache = {}
    def card_img(ci, wi):
        if (ci, wi) not in cache:
            cache[(ci, wi)] = render_card(cards[ci], wi, None, palette[(color_offset + ci) % len(palette)])
        return cache[(ci, wi)]

    n   = max(2, int(round(dur * FPS)))
    cmd = [FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{dur:.3f}", str(clip)]
    log_path = tmp / f"ffmpeg_clip{idx+1}.log"
    with open(log_path, "wb") as lf:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=lf)
        ptr = 0
        try:
            for f in range(n):
                t   = f / FPS
                cur = 0                                            # newest picture that has begun (incl. its crossfade)
                for j in range(1, len(starts)):
                    if t >= starts[j][0] - XF / 2:
                        cur = j
                if cur > 0 and t < starts[cur][0] + XF / 2:        # inside a crossfade: blend old and new picture
                    alpha = _smootherstep((t - (starts[cur][0] - XF / 2)) / XF)
                    frame = Image.blend(shot_frame(cur - 1, t), shot_frame(cur, t), alpha)
                else:
                    frame = shot_frame(cur, t)
                while ptr + 1 < len(events) and events[ptr + 1][3] <= t:
                    ptr += 1
                if events and events[0][3] <= t < events[-1][4]:
                    ci, _, wi, _, _ = events[ptr]
                    card = card_img(ci, wi)
                    frame.paste(card, (0, CAPTION_TOP), card)
                try:
                    proc.stdin.write(frame.tobytes())
                except (BrokenPipeError, OSError):
                    break                                  # ffmpeg exited early; its log is reported below
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
        rc = proc.wait()
    if rc != 0:
        log(f"clip {idx+1} ffmpeg log:\n{log_path.read_text(errors='ignore')[-600:]}", "red")
        fail(f"clip {idx+1} exited {rc}")
    return len(cards)

def assemble_video(img_paths, audio_paths, durations, out_dir, script):
    section("STEP 5  —  Video Assembly  (ffmpeg · motion + highlighted captions)")
    video_path = out_dir / "short.mp4"

    if video_path.exists():
        skip(f"Video: {video_path.name}")
        return video_path

    if not find_caption_font():
        warn("No bold caption font found — using Pillow's built-in font")

    tmp = out_dir / "tmp_clips"
    tmp.mkdir(exist_ok=True)
    clip_paths = []

    import random
    seed    = int(time.time())                      # new motion + colour order for every video
    palette = (random.Random(seed).sample(CAPTION_PALETTE, len(CAPTION_PALETTE))
               if CAPTION_COLOR_MODE == "shuffle" else [CAPTION_ACCENT])
    # Word timing for every scene first (fast, sequential); it also tells us how many caption cards each
    # scene has, so the highlight colours keep cycling across scene cuts while the scenes render in parallel.
    with spin("Aligning captions to the voice..."):
        all_words = [align_words(speechify(s["narration"]), audio_paths[i]) for i, s in enumerate(script["scenes"])]
    offsets, run = [], 0
    for w in all_words:
        offsets.append(run)
        run += len(group_cards(w))

    from concurrent.futures import ThreadPoolExecutor
    todo = []
    for i, (img, audio, dur) in enumerate(zip(img_paths, audio_paths, durations)):
        clip = tmp / f"frame_{i+1}_clip.mp4"
        clip_paths.append(clip)
        if clip.exists():
            skip(f"frame_{i+1}_clip.mp4")
        else:
            todo.append((i, img, audio, dur, clip))
    if todo:
        with spin(f"Rendering {len(todo)} clip(s) in parallel..."):
            with ThreadPoolExecutor(max_workers=RENDER_WORKERS) as ex:
                futs = [ex.submit(build_clip_v2, img, audio, dur, script["scenes"][i]["narration"], i, tmp, clip,
                                  palette=palette, color_offset=offsets[i], seed=seed, words=all_words[i],
                                  shots=script["scenes"][i].get("shots"))
                        for i, img, audio, dur, clip in todo]
                for fu in futs:
                    fu.result()                      # re-raises any failure
        for i, *_rest, clip in todo:
            ok(f"Clip {i+1} → {clip.name}")

    concat_list = tmp / "concat.txt"
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")

    with spin("Stitching clips + normalising loudness (-14 LUFS)..."):
        run_cmd([
            FFMPEG, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:v", "copy",
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            str(video_path),
        ], label="concat")

    size_mb = video_path.stat().st_size / (1024*1024)
    ok(f"Video ready → {video_path.name}  ({size_mb:.1f} MB)")
    return video_path

# ════════════════════════════════════════════════════════════
# STEP 6 — YOUTUBE UPLOAD
# ════════════════════════════════════════════════════════════

def get_youtube_creds(secrets, token, force_reauth=False):
    """Load cached OAuth creds, refresh if expired, re-run browser auth if the
    refresh token is expired/revoked (e.g. 'invalid_grant' after weeks idle)."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds  = None

    if token.exists() and not force_reauth:
        try:
            with open(token, "rb") as f:
                creds = pickle.load(f)
        except Exception:
            warn("Cached YouTube token unreadable — re-authorizing")
            creds = None

    if creds and not set(SCOPES).issubset(set(creds.scopes or [])):
        creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            with spin("Refreshing OAuth token..."):
                creds.refresh(Request())
        except RefreshError as e:
            warn(f"YouTube token expired or revoked ({e}) — re-authorizing")
            creds = None
    else:
        creds = None

    if not creds:
        token.unlink(missing_ok=True)
        log("Opening browser for YouTube authorization...", "yellow", indent=1)
        flow  = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
        # offline + consent guarantees a fresh refresh_token is issued
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    with open(token, "wb") as f:
        pickle.dump(creds, f)
    ok("OAuth token saved → youtube_token.pickle")
    return creds

def upload_to_youtube(video_path, meta):
    section("STEP 6  —  YouTube Upload")

    if CFG["upload_privacy"] == "none":
        skip("Upload skipped — video saved locally")
        return None

    secrets = Path("client_secrets.json")
    token   = Path("youtube_token.pickle")

    if not secrets.exists():
        warn("client_secrets.json not found — skipping upload")
        return None

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        import google_auth_oauthlib  # noqa: F401
    except ImportError:
        fail("pip install google-api-python-client google-auth-oauthlib")

    creds   = get_youtube_creds(secrets, token)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title":           meta["title"][:100],
            "description":     meta["description"],
            "tags":            CHANNEL["tags"],
            "categoryId":      "28",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus":           CFG["upload_privacy"],
            "selfDeclaredMadeForKids": False,
        },
    }

    log(f"Uploading: {meta['title'][:70]}", indent=1)
    log(f"Privacy:   {CFG['upload_privacy'].upper()}", "yellow", indent=1)

    from googleapiclient.errors import HttpError
    from google.auth.exceptions import RefreshError

    def new_request(yt):
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        return yt.videos().insert(part="snippet,status", body=body, media_body=media)

    request  = new_request(youtube)
    t0 = time.time()
    response = None
    reauthed = False
    while response is None:
        try:
            status, response = request.next_chunk()
        except (RefreshError, HttpError) as e:
            auth_err = isinstance(e, RefreshError) or getattr(e, "status_code", getattr(e.resp, "status", None)) == 401
            if not auth_err or reauthed:
                raise
            print()
            warn("YouTube rejected the token — re-authorizing and retrying upload")
            reauthed = True
            creds    = get_youtube_creds(secrets, token, force_reauth=True)
            youtube  = build("youtube", "v3", credentials=creds)
            request  = new_request(youtube)
            continue
        if status:
            pct = int(status.progress() * 100)
            print(f"\r  {c('↑','cyan')} Uploading... {c(str(pct)+'%','yellow')}   ", end="", flush=True)
    print()

    video_id = response.get("id","unknown") if isinstance(response, dict) else "unknown"
    ok(f"Uploaded in {time.time()-t0:.1f}s → https://youtube.com/shorts/{video_id}")
    return video_id

# ════════════════════════════════════════════════════════════
# CLEANUP
# ════════════════════════════════════════════════════════════

def cleanup(out_dir):
    section("CLEANUP")
    keep    = {"short.mp4", "youtube_metadata.json"}
    deleted = 0
    for item in list(out_dir.iterdir()):
        if item.name in keep:
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()
        deleted += 1
    ok(f"Removed {deleted} temp items — kept short.mp4 + youtube_metadata.json")

def print_upload_metadata(meta):
    """Print the uploaded title/description/tags as plain text for copy-paste
    (e.g. into TikTok). No colour codes inside the block so it copies clean."""
    print()
    print(c("── Metadata (copy-paste) " + "─"*35, "cyan"))
    print(f"TITLE:\n{meta['title']}\n")
    print(f"DESCRIPTION:\n{meta['description']}\n")
    print(f"TAGS:\n{' '.join('#' + t.replace(' ', '') for t in CHANNEL['tags'])}")
    print(c("─"*60, "cyan"))
    print()

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def run_one(client):
    """Build (and upload) one video. Never raises: returns a result dict so a batch can carry on."""
    global _total_cost
    _total_cost = 0.0
    t0  = time.time()
    res = {"ok": False, "title": None, "topic": None, "url": None, "path": None,
           "cost": 0.0, "seconds": 0.0, "error": None, "abort": False}
    try:
        # 1. Pick topic
        topic = pick_topic(client)
        res["topic"] = topic["title"]
        if topic["status"] != "manual":
            mark_in_progress(topic)

        out_dir = OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir.mkdir(parents=True, exist_ok=True)

        print()
        log(f"  Building: \"{topic['title']}\"", "cyan")
        log(f"  Output:   {out_dir}", "dim")

        # 2. Pipeline
        script      = generate_script(client, topic, out_dir)
        audio_paths = generate_audio(client, script, out_dir)
        img_paths   = generate_images(client, script, out_dir)
        durations   = get_durations(audio_paths, out_dir)
        video_path  = assemble_video(img_paths, audio_paths, durations, out_dir, script)
        res["title"] = script["title"]
        res["path"]  = str(video_path)

        # 3. Metadata
        scene_facts = "\n".join(f"Fact {s['scene']}: {s['narration']}" for s in script["scenes"])
        meta = {
            "title":       script["title"] + " #Shorts",
            "description": CHANNEL["description"].replace("{scene_facts}", scene_facts),
        }
        with open(out_dir / "youtube_metadata.json", "w") as f:
            json.dump(meta, f, indent=2)

        # 4. Summary
        print()
        print(c("═"*60, "bold"))
        print(c("  PIPELINE COMPLETE", "bold"))
        print(c("═"*60, "bold"))
        print(f"  {c('Topic  ','dim')}  {c(topic['title'], 'cyan')}")
        print(f"  {c('Title  ','dim')}  {c(script['title'], 'cyan')}")
        print(f"  {c('Style  ','dim')}  {c(CFG['image_style'], 'white')}  ·  {c(CFG['image_quality'], 'white')}  ·  {c(CFG['tts_voice'], 'white')}")
        print(f"  {c('Time   ','dim')}  {c(f'{time.time()-t0:.1f}s', 'green')}")
        print(f"  {c('Cost   ','dim')}  {c(f'${_total_cost:.4f}', 'yellow')}")
        print(f"  {c('Queue  ','dim')}  {c(str(len(get_pending()))+' topics pending', 'dim')}")
        print(c("═"*60, "bold"))
        print()

        # 5. Upload (a failed upload keeps the rendered video and does not stop a batch)
        video_id = None
        try:
            video_id = upload_to_youtube(video_path, meta)
        except Exception as e:
            warn(f"Upload failed: {str(e)[:200]}")
            res["error"] = f"upload failed: {str(e)[:120]}"
        if video_id:
            log_youtube_id(topic["id"], video_id)
            res["url"] = f"https://youtube.com/shorts/{video_id}"

        # 6. Finalize
        mark_done(topic, out_dir, script)
        cleanup(out_dir)

        print()
        if video_id:
            print(f"  {c('▶  Live at:','green')} {c(res['url'],'cyan')}")
        print_upload_metadata(meta)
        res["ok"] = res["error"] is None
    except SystemExit:
        res["error"] = res["error"] or "stopped (see the error above)"
    except Exception as e:
        import traceback
        msg = f"{type(e).__name__}: {e}"
        res["error"] = msg[:200]
        log(f"❌  {msg[:400]}", "red")
        log("".join(traceback.format_exc().splitlines(True)[-6:]), "dim")
        if "insufficient_quota" in msg or "credit_balance_exhausted" in msg:
            res["abort"] = True      # no point trying the next video
    res["cost"], res["seconds"] = _total_cost, time.time() - t0
    return res

def print_batch_summary(results, seconds):
    good = sum(1 for r in results if r["ok"])
    print()
    print(c("═"*60, "bold"))
    print(c(f"  BATCH COMPLETE  —  {good}/{len(results)} succeeded", "bold"))
    print(c("═"*60, "bold"))
    for i, r in enumerate(results, 1):
        mark  = c("✅", "green") if r["ok"] else c("❌", "red")
        title = r["title"] or r["topic"] or "(no title)"
        where = r["url"] or (r["path"] if r["path"] else "")
        if r["error"]:
            where = f"{where}  {c(r['error'], 'red')}".strip()
        voice = c(f"[{r.get('voice', '')}]", "dim")
        print(f"  {mark} {i}. {title[:40]:40s} {voice:>17s} {c('$%.3f' % r['cost'], 'yellow')}  {where}")
    total = sum(r["cost"] for r in results)
    print(c("  ────────────────────────────────────────────────", "cyan"))
    print(f"  Total cost {c('$%.3f' % total, 'yellow')}   ·   Time {c(f'{seconds/60:.1f} min', 'green')}   ·   Queue {c(str(len(get_pending()))+' pending', 'dim')}")
    print(c("═"*60, "bold"))
    print()

def main():
    args  = get_args()
    count = setup_run(args)

    DB_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    with spin("Initializing OpenAI client..."):
        client = get_client()
    ok("OpenAI client ready")

    voices     = shuffled_voices(count) if (count > 1 and CFG["batch_voice"] == "shuffle") else None
    base_voice = CFG["tts_voice"]
    results, t0 = [], time.time()
    for n in range(1, count + 1):
        if voices:
            CFG["tts_voice"] = voices[n - 1]
        if count > 1:
            print()
            print(c("█"*60, "cyan"))
            print(c(f"  VIDEO {n} of {count}   ·   narrator: {CFG['tts_voice']}", "bold"))
            print(c("█"*60, "cyan"))
        results.append(run_one(client))
        results[-1]["voice"] = CFG["tts_voice"]
        CFG["manual_topic"] = None            # a custom topic only ever applies to the first video
        if results[-1]["abort"]:
            warn("OpenAI credits exhausted — stopping the batch here")
            break

    CFG["tts_voice"] = base_voice
    if count > 1:
        print_batch_summary(results, time.time() - t0)
    else:
        print(f"  {c('Run again to build the next topic automatically.','dim')}")
        print()
    if not all(r["ok"] for r in results):
        sys.exit(1)

if __name__ == "__main__":
    main()