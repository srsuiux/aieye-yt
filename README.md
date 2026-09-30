# AI Eye — Shorts Pipeline

Turns a topic into a finished YouTube Short — script, narration, images, animated video with
highlighted captions — and uploads it. One command (or one double-click) makes 1 video or a batch of 5.

> **Channel:** [@AIEyeFacts](https://www.youtube.com/channel/UCLYrvFHE_D45TNq93qIprYw) · *"5 facts. 60 seconds. Mind blown."*

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
 (db/draft.json)   3 passes     per scene     per scene     ffmpeg       YouTube API
```

| Step | What happens | Model / tool |
|---|---|---|
| 0. Topic | Takes the next pending topic from the queue, or asks the model for 10 fresh ones (never repeating past titles). A custom topic can be given instead. | `gpt-6-luna` |
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
- *(Recommended)* `torch` + `torchaudio` for accurate caption timing. Without them captions still work using a less accurate estimate.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your OpenAI key
echo "OPENAI_API_KEY=sk-..." > .env

# 3. Choose your default settings (one time)
python3 ysa-cli.py --setup
```

The first video downloads the caption-timing model (~1.2 GB, once) into your torch cache.

### YouTube setup

Only needed if you want the pipeline to upload. Without it, choose **Don't upload** and the finished video is saved locally.

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable **YouTube Data API v3**.
2. Create an **OAuth client ID** of type **Desktop app**, download the JSON, and save it in this folder as `client_secrets.json`.
3. Run a video with uploading on. A browser window opens once to authorise; the login is stored in `youtube_token.pickle`.
   If it ever expires, the pipeline re-opens the browser automatically.

## Usage

### One click (macOS)

Double-click in Finder:

| File | Does |
|---|---|
| `make-1-video.command` | Makes 1 video with your saved defaults and uploads it |
| `make-5-videos.command` | Makes 5 videos back to back (different narrator each) and uploads them |
| `change-defaults.command` | Pick and save your default settings |

Each shows the settings and estimated cost, then starts after a 5-second countdown. **Ctrl+C in that window cancels.**
If macOS blocks the first launch: right-click the file → Open.

### Command line

```bash
python3 ysa-cli.py                       # interactive menu
python3 ysa-cli.py --quick               # 1 video, saved defaults, no questions
python3 ysa-cli.py --batch 8             # any number of videos, saved defaults
python3 ysa-cli.py --quick --topic "Why Do We Yawn"   # custom topic (single video)
python3 ysa-cli.py --quick --privacy none             # override privacy for this run only
python3 ysa-cli.py --setup               # choose and save defaults, then exit
```

| Flag | Meaning |
|---|---|
| `--quick` | Make 1 video with your saved defaults, no questions |
| `--batch N` | Make N videos with your saved defaults |
| `--setup` | Choose and save default settings, then exit |
| `--topic "…"` | Custom topic (single video only) |
| `--privacy {public,private,unlisted,none}` | Override the saved privacy for this run |
| `--quality {low,medium,high}` | Override the saved image quality for this run |
| `--yes` | Skip the 5-second countdown |

### Interactive menu

Running with no flags shows:

1. **Make 1 video** — with your saved defaults
2. **Make 5 videos** — with your saved defaults (narrators shuffled)
3. **Customize this run** — pick a topic and settings just for this run (and optionally save them)
4. **Change saved defaults**

## Settings

Saved in `aieye_settings.json` (edit through `--setup` or menu option 4).

| Setting | Options |
|---|---|
| **Image style** | `representational` (labelled diagrams, best for facts) · `realistic` (photographic) · `illustrated` |
| **Image quality** | `low` (~$0.005/image) · `medium` (~$0.010) · `high` (~$0.041) |
| **Upload privacy** | `public` · `private` · `unlisted` · `none` (render only, don't upload) |
| **Narrator voice** | `marin`, `cedar`, `nova`, `coral`, `sage`, `ash`, `ballad`, `verse`, `alloy`, `echo`, `fable`, `onyx`, `shimmer` |
| **Voices in a batch** | `shuffle` (a different narrator on every video) · `same` (use the narrator above) |

> ⚠️ If privacy is **public**, every finished video is published immediately — including all five in a batch.
> Use `private` until you trust the output, or `none` to review files first.

Audio samples of every voice (same line, same style) are in `voice_samples/` if you generated them — listen and edit `VOICE_POOL` to taste.

## Output & data

```
shorts_output/<timestamp>/
    short.mp4                 the finished video
    youtube_metadata.json     title + description that were uploaded
db/
    draft.json                topic queue (pending / in_progress)
    final.json                every completed video: title, cost, voice, scenes, YouTube link
aieye_settings.json           your saved defaults
```

Temporary files (audio, images, clips) are deleted after each successful run; only `short.mp4` and the metadata are kept.
An interrupted run leaves its partial files in its `shorts_output/<timestamp>/` folder; re-running starts a fresh folder (and a topic left `in_progress` in `db/draft.json` is skipped, not retried).

## Cost

Rough cost per video (about 11 pictures + script + narration):

| Image quality | Per video | 5-video batch |
|---|---|---|
| low | ~$0.16 | ~$0.80 |
| medium | ~$0.21 | ~$1.07 |
| high | ~$0.56 | ~$2.78 |

Images dominate the cost. A fresh picture costs ~$0.005 / $0.010 / $0.041 (low / medium / high) and each *reference
edit* (shots 2–3) costs the same **plus ~$0.014**, because the reference image is billed as input. A measured
medium-quality run with 10 pictures cost $0.187 in total. Fewer shots per scene = cheaper (`MAX_SHOTS`).
The pipeline prints the estimate before starting and the real image cost (from the API's token usage) after each video.
Narration cost is an estimate (the API doesn't report it).

## Customising

Everything below is a constant near the top of `ysa-cli.py` (or beside its section).

| What | Constant |
|---|---|
| Channel name, description, tags | `CHANNEL` |
| Scenes per video / topics per refill | `N_SCENES`, `N_TOPICS` |
| Pictures per scene (1 = old behaviour, cheapest) / shortest allowed shot | `MAX_SHOTS`, `MIN_SHOT_WORDS` |
| Scenes whose images generate at once (lower if you hit rate limits) | `IMAGE_WORKERS` |
| Crossfade length between pictures | `SHOT_XFADE` |
| Models | `GPT_MODEL`, `TTS_MODEL`, `IMAGE_MODEL` |
| Narrator direction (tone, pacing) | `TTS_STYLE` |
| Voices used when shuffling | `VOICE_POOL` |
| Zoom strength | `MOTION` = `"low"` · `"medium"` · `"high"` |
| Caption highlight style | `CAPTION_STYLE` = `"plate"` · `"text"` |
| Caption colours | `CAPTION_COLOR_MODE` (`"shuffle"` / `"fixed"`), `CAPTION_PALETTE` |
| Caption size of a card | `CAPTION_MAX_WORDS`, `CAPTION_MAX_CHARS` |
| How early captions appear | `CAPTION_LEAD_CARD`, `CAPTION_LEAD_WORD` |
| Scenes rendered at once | `RENDER_WORKERS` |
| Script style rules | the prompts inside `generate_script()` |

## Troubleshooting

| Problem | Fix |
|---|---|
| `insufficient_quota` / "no credits remaining" | Add credits at platform.openai.com → Billing. Newly added credits can take a few minutes; also check the key belongs to the same organisation/project. A batch stops itself when this happens. |
| "Rate limit on scene … waiting Ns" | Normal: the image API limits how fast pictures can be requested. The pipeline waits and retries by itself. If it keeps happening, lower `IMAGE_WORKERS` to 1–2 or `MAX_SHOTS` to 2. |
| `OPENAI_API_KEY not set` | Put it in `.env` next to `ysa-cli.py`. |
| `No saved defaults yet` | Run `python3 ysa-cli.py --setup` once. |
| `ffprobe: command not found` | Install ffmpeg (`brew install ffmpeg`) so `ffprobe` is on your PATH. |
| "Forced alignment unavailable … using estimated caption timing" | `torch`/`torchaudio` missing or the model couldn't download. Run `pip install torch torchaudio` and check your connection. Captions still work, just less precisely timed. |
| Upload fails | The video is still saved in `shorts_output/`. Check `client_secrets.json`; delete `youtube_token.pickle` to re-authorise. |
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

Never share or commit: `.env` (OpenAI key), `client_secrets.json` and `youtube_token.pickle` (YouTube access).
All three, plus outputs and settings, are listed in `.gitignore`. If a key is ever exposed (in a log, screenshot or chat), rotate it in the provider's dashboard.

## Project layout

```
ysa-cli.py                  the whole pipeline (CLI, settings, script, voice, images, video, upload)
requirements.txt            dependencies
make-1-video.command        double-click launchers (macOS)
make-5-videos.command
change-defaults.command
aieye_settings.json         your saved defaults            (created by --setup)
.env                        OPENAI_API_KEY                 (you create this)
client_secrets.json         Google OAuth client            (you create this)
youtube_token.pickle        YouTube login                  (created on first upload)
db/                         topic queue + history
shorts_output/              finished videos
voice_samples/              optional narrator samples
yt/                         channel branding assets (logo/banner prompts, metadata)
```
