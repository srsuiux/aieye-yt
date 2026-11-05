import sys, time, json
from .config import SETTINGS_FILE, CFG, EDIT_REF_COST, EXPECTED_SHOTS, IMAGE_COST, N_SCENES
from .limits import DAILY_LIMIT, check_count_choice, enforce_daily, pushed_today
from .ui import c, fail, ok, prompt_choice, prompt_text

# SETTINGS — saved defaults, run modes

BATCH_DEFAULT = 3          # the only batch size; 1 or 3 videos per run, max 3 a day (aieye/limits.py)
SETTING_CHOICES = {
    "image_style":    ["representational", "realistic", "illustrated"],
    "image_quality":  list(IMAGE_COST),
    "upload_privacy": ["public", "private", "unlisted", "none"],
    "tts_voice":      ["marin", "cedar", "nova", "alloy", "echo", "fable", "onyx", "shimmer", "coral", "sage", "ash", "ballad", "verse"],
    "batch_voice":    ["shuffle", "same"],
}
OPTIONAL_SETTINGS = {"batch_voice": "shuffle"}     # missing in older settings files → use this
# Voices used when a batch shuffles narrators. Samples of every voice are in assets/voice_samples/ — edit to taste.
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
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
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
            ("Don't upload", "none", "Render only — saves short.mp4 in data/output/"),
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
    enforce_daily(count)                        # refuses (and exits) before anything is shown or started
    per   = est_cost_per_video(CFG["image_quality"])
    print()
    print(c("  ── Run Configuration ─────────────────────────", "cyan"))
    print(f"  Videos     {c(str(count), 'cyan')}   {c(f'(today: {pushed_today()} pushed, limit {DAILY_LIMIT} a day)', 'dim')}")
    print(f"  Topic      {c(CFG['manual_topic'] or ('Trending on the web' if CFG.get('trending') else 'Top categories' if CFG.get('top') else 'Auto from queue'), 'cyan')}")
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

def parse_run_flags(tokens):
    """`aieye run -trending -1 -def` → the same Namespace the normal flags produce.
        -trending   topic comes from what is trending on the web (queue/history not consulted)
        -top        topics from the top-performing categories (animals, space, underwater, everyday what-if puzzles), photo-real close-ups
        -1 / -3     make 1 or 3 videos (no other number; never more than 3 a day)
        -def        use saved defaults, no questions, narrator shuffled
        -custom ... your own topic (single video; -topic is the same)     -privacy P / -quality Q   per-run overrides"""
    import argparse
    ns = argparse.Namespace(languages=["en"], quick=False, batch=None, setup=False, yes=False, topic=None,
                            privacy=None, quality=None, trending=False, top=False, use_def=False)
    known = {"top", "trending", "trend", "def", "default", "defaults", "custom", "topic", "privacy", "quality", "y", "yes"}
    from .languages import lang_code
    is_flag = lambda t: t.startswith("-") and (t.lstrip("-").lower() in known or t.lstrip("-").isdigit()
                                               or lang_code(t) is not None)
    langs = []
    words, custom, i = [], False, 0
    while i < len(tokens):
        t, k = tokens[i], tokens[i].lstrip("-").lower()
        i += 1
        if k in ("trending", "trend"):
            ns.trending = True
        elif k == "top":
            ns.top = True
        elif k in ("def", "default", "defaults"):
            ns.use_def = True
        elif k.isdigit():
            check_count_choice(int(k))          # only -1 or -3
            ns.batch = int(k)
        elif t.startswith("-") and lang_code(k):
            langs.append(lang_code(k))
        elif k in ("custom", "topic"):
            custom = True                       # the words after it (quoted or not) are the topic
            while i < len(tokens) and not is_flag(tokens[i]):
                words.append(tokens[i]); i += 1
        elif k in ("privacy", "quality"):
            setattr(ns, k, tokens[i] if i < len(tokens) else None); i += 1
        elif k in ("y", "yes"):
            ns.yes = True
        elif custom:                            # anything else after -custom is part of the topic
            words.append(t.lstrip("-"))
            while i < len(tokens) and not is_flag(tokens[i]):
                words.append(tokens[i]); i += 1
        else:
            fail(f"Unknown option '{t}'.  Usage: aieye run [-trending|-top] [-N] [-def] [-custom your topic here]")
    ns.languages = list(dict.fromkeys(langs)) or ["en"]
    if custom:
        text = " ".join(words).strip()
        if text.lower().startswith("about "):
            text = text[6:]
        ns.topic = text or prompt_text("Enter your custom topic")
        if not ns.topic:
            fail("No custom topic given")
        ns.batch = 1                            # a custom topic is always a single video
    if ns.use_def or ns.batch:
        ns.quick, ns.yes = True, True
        ns.batch = ns.batch or 1
    return ns

def get_args():
    import argparse
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        return parse_run_flags(sys.argv[2:])
    ap = argparse.ArgumentParser(description="AI Eye Shorts pipeline")
    ap.add_argument("--quick", action="store_true", help="make 1 video with your saved defaults, no questions")
    ap.add_argument("--batch", type=int, choices=[1, 3], metavar="N", help="make 1 or 3 videos with your saved defaults, no questions (max 3 a day)")
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
        CFG["trending"] = getattr(args, "trending", False)
        CFG["top"] = getattr(args, "top", False)
        if CFG["top"]:
            CFG["image_style"] = "realistic"
        CFG["languages"] = getattr(args, "languages", ["en"])
        if getattr(args, "use_def", False):
            CFG["force_shuffle"] = True        # -def: a random narrator from the pool, even for one video
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
    CFG["trending"] = getattr(args, "trending", False)
    CFG["top"] = getattr(args, "top", False)
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

