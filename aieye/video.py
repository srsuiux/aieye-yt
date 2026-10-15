import time, subprocess
from pathlib import Path
from .audio import speechify
from .captions import CAPTION_ACCENT, CAPTION_COLOR_MODE, CAPTION_LEAD_CARD, CAPTION_PALETTE, CAPTION_TOP, align_words, caption_events, find_caption_font, group_cards, render_card
from .config import MAX_SHOTS
from .ffmpeg import FFMPEG, run_cmd
from .ui import fail, log, ok, section, skip, spin, warn


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

