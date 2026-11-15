# AI Eye — Shorts Pipeline

Turns a topic into a finished YouTube Short — script, narration, images, animated video with
highlighted captions — and uploads it. One command (or one double-click) makes 1 video or a batch of 3 (it refuses to push
more than 3 videos to YouTube in one day).

> A framework you run yourself with your own API keys. Your channel's name, description and stats stay on your machine in
> git-ignored files (see [Your channel](#your-channel)); nothing about anyone's channel ships with the code.

## Quick start

```bash
git clone https://github.com/srsuiux/aieye-yt.git && cd aieye-yt
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env               # your own key
cp channel.example.json data/channel.json         # optional: your channel's name, tags, description
python3 aieye-cli.py --setup                        # pick defaults once (use upload privacy "none" to just render)
python3 aieye-cli.py --quick                        # make 1 video
```

Install the short `aieye` command with `ln -sf "$PWD/start-script.sh" ~/.local/bin/aieye`, then run `aieye help`.

**Web app:** `aieye web` opens the same tool in your browser (local only by default): create videos and watch them being made (with an optional review step before upload), manage topics,
channel details, defaults and advanced settings (models, scenes, caption look), keep or upload finished videos, save API keys and
the YouTube sign-in, and read the docs. The documentation lives in [`docs/`](docs/overview.md) and is also served at `/docs` in the app.

**Contents:** [What it makes](#what-it-makes) · [How it works](#how-it-works) · [Requirements](#requirements) · [Setup](#setup) ·
[The `aieye` command](#the-aieye-command) · [Experiments](#experiments-optional-not-part-of-the-daily-pipeline) · [Usage](#usage) ·
[Settings](#settings) · [Output & data](#output--data) · [Cost](#cost) · [Customising](#customising) ·
[Troubleshooting](#troubleshooting) · [Design notes](#design-notes) · [Project layout](#project-layout)

---

## What it makes

A ~45–55 second vertical video (1080×1920, 30 fps, H.264 + AAC) with:

- a **5-scene script** written to sound spoken, not read (one story thread, contractions, varied rhythm)
- a **natural narrator voice**, directed scene by scene
- **10–12 AI images, a new picture every 3–5 seconds**: each scene is split into 2–3 shots (one per sentence group),
  and the extra shots are generated *from the first shot as a reference*, so the subject, setting and look stay the
  same while the camera angle changes
- a **slow, smooth zoom** on every picture (in on one, out on the next) with a short crossfade as each new sentence begins, over a blurred backdrop
- **word-highlighted captions** — 3–5 words on screen, the spoken word highlighted, a different highlight colour on each card
- loudness normalised to **−14 LUFS** (YouTube's target)

## How it works

```
 topic queue ──► 1. Script ──► 2. Voice ──► 3. Images ──► 4. Video ──► 5. Upload
 (data/db/draft.json)   3 passes     per scene     per scene     ffmpeg       YouTube API
```

| Step | What happens | Model / tool |
|---|---|---|
| 0. Topic | Takes the next pending topic from the queue, or asks the model for 10 fresh ones aimed at curious kids (8–12). A **strict duplicate gate** rejects any topic about the same animal, object or phenomenon as an earlier video (cheap word-overlap check, then one model check). A custom or trending topic can be given instead. | `gpt-6-luna` |
| 1. Script | **Research** (fact-checked, with a through-line) → **Draft** (spoken-word rules, delivery note per scene, shared visual style, each scene split into 2–3 *shots* with their own picture prompt) → **Read-aloud edit** (removes AI-sounding phrases, softens shaky claims, fixes speakability). | `gpt-6-luna` |
| 2. Voice | One request per scene, with a base style plus that scene's delivery note. Silence trimmed at both ends. | `gpt-4o-mini-tts-2025-03-20` |
| 3. Images | One 1024×1536 image per **shot**. Shot 1 of each scene is generated fresh; shots 2–3 are *edited from shot 1 as a reference* (same subject/lighting/look, new camera angle). Scenes run 3 at a time, with automatic waiting and retry on rate limits. All share the script's visual style and leave the bottom third clear for captions. | `gpt-image-2.5-flare` |
| 4. Video | Word timing from **forced alignment** (script vs. real audio). Each scene is rendered frame by frame: every picture gets its own slow zoom and the pictures crossfade as the next sentence starts; captions are laid on top. Scenes are stitched and loudness normalised. | torchaudio `MMS_FA`, Pillow, ffmpeg |
| 5. Upload | Uploads with title, description, tags. Privacy comes from your settings. | YouTube Data API v3 |

## Requirements

- **Python 3.10+** (developed on macOS with Anaconda Python 3.13)
- **An OpenAI API key** with credits
- **`ffprobe`** on your PATH (comes with a normal ffmpeg install, e.g. `brew install ffmpeg`).
  The `ffmpeg` used for rendering is the newer 7.x build bundled with `imageio-ffmpeg`; the pipeline uses it automatically and falls back to the system `ffmpeg`.
- *(Optional, for uploading)* a Google Cloud OAuth client — see [YouTube setup](#youtube-setup)
- *(Optional, experiments only)* an OpenRouter API key for `-vid`, `-film` and `aieye menu`
- *(Recommended)* `torch` + `torchaudio` for accurate caption timing. Without them captions still work using a less accurate estimate.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your OpenAI key
echo "OPENAI_API_KEY=sk-..." > .env

# (optional, experiments only) echo "OPENROUTER_API_KEY=sk-or-..." >> .env

# 3. Choose your default settings (one time)
python3 aieye-cli.py --setup
```

The first video downloads the caption-timing model (~1.2 GB, once) into your torch cache.

### Your channel

Video descriptions and tags come from `data/channel.json`, which is git-ignored. Without it, generic defaults are used.
The same file can also hold `audience_notes` (who the videos are for and what has worked for you) and `top_categories`
(for `-top`), so your own analytics never need to go in the code.

```bash
cp channel.example.json data/channel.json    # then edit handle, url, tags and description
```

`{scene_facts}` in the description is replaced by the video's facts. Personal files (`.env`, `data/`, `assets/channel/`,
`yt-analysis/` for your own channel stats) are all git-ignored.

### YouTube setup

Only needed if you want the pipeline to upload. Without it, choose **Don't upload** and the finished video is saved locally.

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable **YouTube Data API v3**.
2. Create an **OAuth client ID** of type **Desktop app**, download the JSON, and save it as `data/credentials/client_secrets.json`.
3. Run a video with uploading on. A browser window opens once to authorise; the login is stored in `data/credentials/youtube_token.pickle`.
   If it ever expires, the pipeline re-opens the browser automatically.

## The `aieye` command

`start-script.sh` is the single launcher; it is symlinked to `~/.local/bin/aieye`
(`ln -sf "$PWD/start-script.sh" ~/.local/bin/aieye`).

```bash
aieye run -trending -1 -def   # 1 video, topic from what is trending on the web, saved defaults, random narrator
aieye run -top -3 -def        # 3 videos from the top categories (animals, space, underwater, everyday what-if puzzles), photo-real close-ups
aieye run -1 -def -en -hindi "topic"   # one video per language (see Languages)
aieye run -3 -def             # 3 videos from the queue, saved defaults, shuffled narrators
aieye run -trending -3 -def   # 3 videos, each on a different trend
aieye run -custom -1 -def -custom Why do we yawn   # your own topic (quotes optional)
aieye setup                   # choose and save defaults
aieye trends                  # just list what is trending (free)
aieye web                     # the web app (local only; --port N, --no-open, --host to share with a token)
aieye models                  # list image-to-video models and live prices (free; experiments)
aieye menu                    # AI video studio (experiments; spends OpenRouter credit)
aieye                         # interactive menu
```

`-trending` reads Google Trends (US) and Wikipedia's most-read pages, asks the model to pick the best fit for a
facts Short (skipping tragedies, politics, gossip), and builds the video from it. It does not read or write the topic
queue. The facts themselves still come from the model, not from the web page text.

### Languages

`aieye run -custom -1 -def -en -hindi "topic"` makes one video per language. The script and pictures are made once
in English; each extra language gets the narration re-written as a native speaker would say it (not a word-for-word
translation), its own voice track and captions, and is uploaded as its own Short with the right language tag.
Hindi captions are shaped with macOS CoreText (Pillow can't shape Devanagari without raqm). Languages are listed in
`aieye/languages.py`. Costs ~$0.02 extra per added language (no extra images).

### Experiments (optional, not part of the daily pipeline)

Side tools for trying AI video. They never touch the topic queue, the 3-a-day limit or YouTube, and nothing is uploaded.
All output goes to `data/experiments/` (git-ignored). The video modes need `OPENROUTER_API_KEY` in `.env`
(key from [openrouter.ai/keys](https://openrouter.ai/keys)); `-img` and `-script` only need your OpenAI key.
**None of the video models are free**: each command shows a price first, and `-y` skips that pause, so use it with care.

| Command | What it does | Output |
|---|---|---|
| `aieye run -img [N] "prompt"` | 1-4 high-definition, centre-focus 9:16 stills (quality defaults to `high`; `-quality low\|medium\|high`) | `data/experiments/images/` (+ raw original and a `.json` with prompt and cost) |
| `aieye run -vid [still.png] "motion"` | Turns a still (default: the newest `-img` still) into a short clip | `data/experiments/videos/`: clip, its **last frame** (start of the next clip) and the real cost |
| `aieye run -script "topic" [-notes file]` | Script only: a reasoning model drafts it, a stronger one judges it against a strict rubric, revised up to 2 rounds. `-notes` supplies verified facts | `data/experiments/film/<run>/` (`script.json`, `script.md`, `script_report.json`) |
| `aieye run -film "topic"` | The full pipeline with text-to-video: director's shot list, voice, one clip per scene, word-timed captions, loudness-normalised 1080x1920 output | `data/experiments/film/<run>/` |
| `aieye menu` | Guided studio: asks for a topic and a model, shows an estimated price, asks for `y`, then runs script, film and merge | same as `-film` |

| Option | Applies to | Meaning |
|---|---|---|
| `-model ID` | `-vid`, `-film` | Shortcuts for `-film`: `grok`, `veo`, `veo-fast`, `seedance`, `kling`; or any OpenRouter model id. Default `google/veo-3.1-lite` (best anatomy and action per dollar in our test; Grok Lite is cheaper but drew wrong animals). Full list with live prices: `aieye models` |
| `-res 480p\|720p\|1080p` | `-vid`, `-film` | Clip resolution (default `720p`) |
| `-dur S` | `-vid` | Clip length in seconds, 1-10 (default 5) |
| `-ambient` | `-film` | Keep the clips' own sound, quietly |
| `-qa` | `-film` | Frame checks by a vision model (spoilers, drawn graphics, wrong content); failing clips are regenerated up to 2 times, so it can cost up to 3x the clip price. Off by default |
| `-resume DIR` | `-film`, `-script` | `-film`: finish a saved run, generating only missing clips. `-script`: re-judge and improve a script (the old one is kept as `script_prev.json`) |
| `-y` | `-vid`, `-film` | Skip the 3-second cancel window |

Typical flow: `-script "topic"` (cheap, review the script) then `-film -resume <run>` (spends on video).

## Usage

### One click (macOS)

Double-click in Finder:

| File | Does |
|---|---|
| `launchers/make-1-video.command` | Makes 1 video with your saved defaults and uploads it |
| `launchers/make-3-videos.command` | Makes 3 videos back to back (different narrator each) and uploads them |
| `launchers/change-defaults.command` | Pick and save your default settings |

Each shows the settings and estimated cost, then starts after a 5-second countdown. **Ctrl+C in that window cancels.**
If macOS blocks the first launch: right-click the file → Open.

### Command line

```bash
python3 aieye-cli.py                       # interactive menu
python3 aieye-cli.py --quick               # 1 video, saved defaults, no questions
python3 aieye-cli.py --batch 3             # 3 videos (only 1 or 3 allowed), saved defaults
python3 aieye-cli.py --quick --topic "Why Do We Yawn"   # custom topic (single video)
python3 aieye-cli.py --quick --privacy none             # override privacy for this run only
python3 aieye-cli.py --setup               # choose and save defaults, then exit
```

| Flag | Meaning |
|---|---|
| `--quick` | Make 1 video with your saved defaults, no questions |
| `--batch 1\|3` | Make 1 or 3 videos with your saved defaults. **Hard limit: 3 videos a day**; asking for more is refused |
| `--setup` | Choose and save default settings, then exit |
| `--topic "…"` | Custom topic (single video only) |
| `--privacy {public,private,unlisted,none}` | Override the saved privacy for this run |
| `--quality {low,medium,high}` | Override the saved image quality for this run |
| `--yes` | Skip the 5-second countdown |

### Interactive menu

Running with no flags shows:

1. **Make 1 video** — with your saved defaults
2. **Make 3 videos** — with your saved defaults (narrators shuffled)
3. **Customize this run** — pick a topic and settings just for this run (and optionally save them)
4. **Change saved defaults**
5. **Make an AI video** — the experimental text-to-video studio (needs `OPENROUTER_API_KEY`, spends credit; see [Experiments](#experiments-optional-not-part-of-the-daily-pipeline))

## Settings

Saved in `data/settings.json` (edit through `--setup` or menu option 4).

| Setting | Options |
|---|---|
| **Image style** | `representational` (labelled diagrams, best for facts) · `realistic` (photographic) · `illustrated` |
| **Image quality** | `low` (~$0.005/image) · `medium` (~$0.010) · `high` (~$0.041) |
| **Upload privacy** | `public` · `private` · `unlisted` · `none` (render only, don't upload) |
| **Narrator voice** | `marin`, `cedar`, `nova`, `coral`, `sage`, `ash`, `ballad`, `verse`, `alloy`, `echo`, `fable`, `onyx`, `shimmer` |
| **Voices in a batch** | `shuffle` (a different narrator on every video) · `same` (use the narrator above) |

> ⚠️ If privacy is **public**, every finished video is published immediately — including all three in a batch.
> Use `private` until you trust the output, or `none` to review files first.

Audio samples of every voice (same line, same style) are in `assets/voice_samples/` if you generated them — listen and edit `VOICE_POOL` to taste.

## Output & data

```
data/output/<timestamp>/      one folder per video while it is being built / waiting to upload
data/db/draft.json            topic queue (pending / in_progress)
data/db/final.json            one slim line per finished video: title, topic, cost, date, YouTube id
data/settings.json            your saved defaults
```

Once a video is **posted to YouTube**, its whole `data/output/<timestamp>/` folder is deleted. If the upload is skipped
or fails, `short.mp4` + `youtube_metadata.json` are kept so you can upload by hand; delete the folder when done.
The history (`final.json`) deliberately stores no scene text or file paths, so it stays small (~200 bytes per video).
An interrupted run leaves its partial files in its `data/output/<timestamp>/` folder; re-running starts a fresh folder (and a topic left `in_progress` in `data/db/draft.json` is skipped, not retried).

## Cost

Rough cost per video (about 11 pictures + script + narration):

| Image quality | Per video | 3-video batch |
|---|---|---|
| low | ~$0.16 | ~$0.48 |
| medium | ~$0.21 | ~$0.64 |
| high | ~$0.56 | ~$1.67 |

Images dominate the cost. A fresh picture costs ~$0.005 / $0.010 / $0.041 (low / medium / high) and each *reference
edit* (shots 2–3) costs the same **plus ~$0.014**, because the reference image is billed as input. A measured
medium-quality run with 10 pictures cost $0.187 in total. Fewer shots per scene = cheaper (`MAX_SHOTS`).
The pipeline prints the estimate before starting and the real image cost (from the API's token usage) after each video.
Narration cost is an estimate (the API doesn't report it).

## Customising

Everything below is a constant in `aieye/config.py` (or at the top of the module for that step).

| What | Constant |
|---|---|
| Channel name, description, tags | `data/channel.json` (see [Your channel](#your-channel)) |
| Scenes per video / topics per refill | `N_SCENES`, `N_TOPICS` |
| Pictures per scene (1 = old behaviour, cheapest) / shortest allowed shot | `MAX_SHOTS`, `MIN_SHOT_WORDS` |
| Scenes whose images generate at once (lower if you hit rate limits) | `IMAGE_WORKERS` |
| Crossfade length between pictures | `SHOT_XFADE` |
| Models | Settings page > Advanced (saved in `data/config.json`); defaults in `aieye/tuning.py` |
| Narrator direction (tone, pacing) | `TTS_STYLE` |
| Voices used when shuffling | `VOICE_POOL` |
| Zoom strength | `MOTION` = `"low"` · `"medium"` · `"high"` |
| Caption highlight style | `CAPTION_STYLE` = `"plate"` · `"text"` |
| Caption colours | `CAPTION_COLOR_MODE` (`"shuffle"` / `"fixed"`), `CAPTION_PALETTE` |
| Caption size of a card | `CAPTION_MAX_WORDS`, `CAPTION_MAX_CHARS` |
| How early captions appear | `CAPTION_LEAD_CARD`, `CAPTION_LEAD_WORD` |
| Scenes rendered at once | `RENDER_WORKERS` |
| Audience and topic taste (who the videos are for, what to prefer or avoid) | `"audience_notes"` in `data/channel.json` (default: `AUDIENCE_NOTES` in `config.py`) |
| Reading level and safety rules for scripts | `KID_RULES` |
| Categories that `-top` rotates through | `"top_categories"` in `data/channel.json` (default: `TOP_CATEGORIES`) |
| Daily upload cap / allowed batch sizes | `DAILY_LIMIT`, `ALLOWED_COUNTS` in `aieye/limits.py` |
| Script style rules | the prompts inside `generate_script()` |

## Troubleshooting

| Problem | Fix |
|---|---|
| `insufficient_quota` / "no credits remaining" | Add credits at platform.openai.com → Billing. Newly added credits can take a few minutes; also check the key belongs to the same organisation/project. A batch stops itself when this happens. |
| "Rate limit on scene … waiting Ns" | Normal: the image API limits how fast pictures can be requested. The pipeline waits and retries by itself. If it keeps happening, lower `IMAGE_WORKERS` to 1–2 or `MAX_SHOTS` to 2. |
| `OPENAI_API_KEY not set` | Put it in `.env` in the project root (next to `aieye-cli.py`). |
| `OPENROUTER_API_KEY is not set` / OpenRouter `402` | Experiments only. Add the key to `.env`, or add credits at openrouter.ai/credits. |
| `No saved defaults yet` | Run `python3 aieye-cli.py --setup` once. |
| `ffprobe: command not found` | Install ffmpeg (`brew install ffmpeg`) so `ffprobe` is on your PATH. |
| "Forced alignment unavailable … using estimated caption timing" | `torch`/`torchaudio` missing or the model couldn't download. Run `pip install torch torchaudio` and check your connection. Captions still work, just less precisely timed. |
| Upload fails | The video is still saved in `data/output/`. Check `data/credentials/client_secrets.json`; delete `data/credentials/youtube_token.pickle` to re-authorise. |
| A video in a batch failed | The others carry on; the summary at the end lists each result and where the file is. |
| TTS model error | The pinned snapshot may have been retired; the pipeline falls back to `gpt-4o-mini-tts` automatically (less controllable — see notes). |

## Design notes

- **Why a pinned TTS snapshot?** The default `gpt-4o-mini-tts` and its Dec 2025 snapshot barely respond to the `instructions` parameter (a "slow" vs "fast" direction changed pace by ~5%). The March 2025 snapshot follows it (~2× pace change) and has more natural pitch movement.
- **Why several pictures per scene, built from a reference?** A new picture every few seconds is what makes a Short feel
  dynamic. Generating each shot independently produced a *different* subject each time (a different tower, a different cat).
  Editing shots 2–3 from shot 1 keeps the same subject, lighting and colour grade while the camera moves, which reads as a
  second camera angle. The trade-off is cost (see above) and slightly more similar composition between the shots of a scene.
- **Why local caption timing?** OpenAI's only word-timestamp endpoint (`whisper-1`) is retired on 2027-02-26 and its replacement doesn't document word timestamps. Forced alignment against the known script runs locally and is more accurate.
- **Why Pillow frame rendering, not ffmpeg's `zoompan`?** `zoompan` jitters at slow zoom speeds. Rendering each frame with a sub-pixel transform gives a clean, smooth zoom.
- **Image model:** `gpt-image-1` shuts down on 2026-12-01; `gpt-image-2.5-flare` replaces it.

## Security

Never share or commit: `.env` (OpenAI and OpenRouter keys), `data/credentials/` (YouTube access).
All three, plus outputs and settings, are listed in `.gitignore`. If a key is ever exposed (in a log, screenshot or chat), rotate it in the provider's dashboard.

## Project layout

```
aieye-cli.py                  entry point (python3 aieye-cli.py, or python3 -m aieye)
aieye/                      the pipeline, one module per step
    config.py                 models, prices, channel info, file locations
    ui.py                     colours, logging, spinner, prompts
    settings.py               saved defaults, CLI args, run setup
    store.py                  topic queue + history (data/db), checkpoints
    costs.py                  running API cost
    client.py                 OpenAI client
    topics.py                 step 0  topic selection
    script.py                 step 1  3-pass script
    audio.py                  step 2  narration + durations
    images.py                 step 3  images
    captions.py               word alignment + caption cards
    video.py                  step 4  render + assemble
    ffmpeg.py                 ffmpeg lookup / runner
    youtube.py                step 5  upload
    pipeline.py               run_one / run_batch / main, cleanup after posting
    webjob.py                 one web-app run in its own process: events, review pause, upload
    tuning.py                 advanced settings: defaults, limits, validation (your changes: data/config.json)
    imgexp.py                 experiment  -img   stills
    videxp.py                 experiment  -vid   image-to-video via OpenRouter, model list and prices
    scriptlab.py              experiment  -script   research, draft, critic, revise
    film.py                   experiment  -film   full text-to-video pipeline, clip QA, final merge
    menu.py                   experiment  menu   guided AI video studio
aieye/web/                  the web app: server.py (routes + guard), jobs.py (runs), data.py (settings/channel/topics), connections.py, docs.py, templates/, static/
docs/                       documentation as Markdown (docs/nav.json = order); served at /docs by the web app
launchers/                  double-click launchers (macOS)
start-script.sh             the `aieye` command (symlinked to ~/.local/bin/aieye)
requirements.txt            dependencies
.env                        OPENAI_API_KEY, optional OPENROUTER_API_KEY                (you create this; see .env.example)
assets/voice_samples/       optional narrator samples      (git-ignored)
assets/channel/             channel branding assets        (git-ignored)
data/                       everything generated/personal  (git-ignored)
    settings.json, db/, output/, credentials/, experiments/
```
