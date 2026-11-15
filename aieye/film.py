"""Experiment: the WHOLE pipeline with text-to-video.  `aieye run -film "how a fox hunts in the snow"`

   DIRECTOR   one LLM call writes a kid-level, fact-checked script as a paced shot list: per scene the narration, what
              we SEE, the camera, and the speed (slow motion on the peak moment, real time elsewhere)
   VOICE      the existing TTS narration (per-scene delivery notes), polished and measured
   CLIPS      text-to-video per scene (no start image). Every prompt begins with the same "world" paragraph so the
              subject, place and light stay identical from clip to clip. Clip length is chosen from the narration length
              and the scene's speed, so slow motion is a real time-stretch of normal-speed action.
   CAPTIONS   the existing word-timed highlight captions, drawn on every scene
   FINISH     scenes joined, loudness normalised to -14 LUFS, 1080x1920 for Shorts

Nothing here touches the topic queue, the daily limit or YouTube. Runs are resumable: pass -resume <folder>.
"""
import json, re, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from .audio import generate_audio, get_durations, speechify
from .captions import (CAPTION_ACCENT, CAPTION_COLOR_MODE, CAPTION_PALETTE, CAPTION_TOP, align_words,
                       caption_events, find_caption_font, group_cards, render_card)
from .config import CFG, DATA_DIR, GPT_IN_COST, GPT_MODEL, GPT_OUT_COST, KID_RULES
from . import costs
from .costs import track
from .ffmpeg import FFMPEG, run_cmd
from .ui import c, fail, log, ok, section, spin, warn
from .videxp import API, DEFAULT_MODEL, DEFAULT_RES, _key, estimate_cost, generate_clip, list_models

FILM_DIR = DATA_DIR / "experiments" / "film"
W, H, FPS = 1080, 1920, 30
SPEEDS = (0.5, 0.75, 1.0)
STYLE = ("Photorealistic wildlife documentary footage, shot on a cinema camera, natural motion, vertical 9:16, "
         "no text, no captions, no watermark, no people.")
AMBIENT_VOLUME = 0.14


# ── 1. SCRIPT: see scriptlab.py (research, draft, critic, revise) ───────────────────────────────────────────
def scene_prompt(data, s):
    """The full text-to-video prompt: the shared setting and cast looks first (keeps subjects identical), then the
    action, then how the shot opens and ends (keeps cuts clean)."""
    if data.get("cast"):
        ids = s.get("characters") or [x["id"] for x in data["cast"]]
        looks = " ".join(f"{x['id'].capitalize()}: {x['look'].strip()}" for x in data["cast"] if x["id"] in ids)
        parts = [data.get("setting", "").strip(), looks, s["action"].strip()]
        if s.get("start_state"):
            parts.append(f"The shot opens on: {s['start_state'].strip()}")
        if s.get("end_state"):
            parts.append(f"It ends on: {s['end_state'].strip()}")
        parts += [f"Camera: {s['camera'].strip()}.", STYLE]
        return " ".join(p for p in parts if p)
    return f"{data['world'].strip()} {s['action'].strip()} Camera: {s['camera'].strip()}. {STYLE}"


def plan_clip(dur, speed, allowed=None):
    """(seconds of source footage to generate, time-stretch factor). Slow motion = generate less, stretch more.
    Some models only make fixed lengths (Veo: 4, 6 or 8 s): then the nearest allowed length is used."""
    want = dur * speed
    if allowed:
        gen = int(min(allowed, key=lambda a: (abs(a - want), a)))
    else:
        gen = int(max(2, min(15, round(want))))
    return gen, dur / gen


# ── 1b. FRAME QA: a vision model checks every generated clip before it is used ───────────────────────────────
MAX_RETRY = 2          # extra attempts per clip (each costs one more clip); the best attempt is kept


def _frames(clip, times, tag, tmp):
    import base64
    out = []
    for k, t in enumerate(times):
        p = tmp / f"qa_{tag}_{k}.jpg"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1",
                        "-vf", "scale=512:-1", str(p)], check=True)
        out.append("data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode())
        p.unlink(missing_ok=True)
    return out


def qa_clip(client, clip, gen, data, s, tmp):
    """Look at 4 frames of a clip. Returns {"pass": bool, "problems": [...], "retry_hint": str}. Never raises."""
    from .scriptlab import WRITER_MODEL, PRICES
    sec = (data.get("brief") or {}).get("secret") or {}
    words = [w for w in (sec.get("words") or []) if w] + ([sec["id"]] if sec.get("id") else [])
    reveal = int(data.get("reveal_scene") or len(data["scenes"]))
    forbid = ", ".join(words) if (words and s["scene"] < reveal) else ""
    cast = "; ".join(f"{x['id']}: {x['look']}" for x in data.get("cast", []) if x["id"] in (s.get("characters") or []))
    text = f"""You are a strict QA checker for ONE AI-generated video clip. You see 4 frames in time order.
SCENE SPEC
 what must happen: {s['action']}
 opens on: {s.get('start_state', '')}
 ends on: {s.get('end_state', '')}
 cast on screen: {cast}
FORBIDDEN TO BE VISIBLE IN ANY FRAME (a spoiler: the film must not reveal it yet): {forbid or 'nothing special'}
ALWAYS FORBIDDEN: any text, caption, arrow, line, diagram or graphic drawn over the picture; people; extra animals;
the wrong species; merged, extra or missing limbs; a face or body that melts or distorts.
Judge the frames honestly. Pass ONLY if the frames match the spec and nothing forbidden appears.
Return ONLY JSON: {{"pass": true or false, "problems": ["short specific problems"],
"retry_hint": "ONE sentence to add to the prompt that would avoid these problems"}}"""
    try:
        content = [{"type": "text", "text": text}] + [
            {"type": "image_url", "image_url": {"url": u}}
            for u in _frames(clip, [0.3, gen * 0.4, gen * 0.75, max(0.4, gen - 0.35)], f"{s['scene']}", tmp)]
        res = client.chat.completions.create(model=WRITER_MODEL, reasoning_effort="medium",
                                             response_format={"type": "json_object"},
                                             messages=[{"role": "user", "content": content}])
        u = res.usage
        pin, pout = PRICES.get(WRITER_MODEL, (2.0, 10.0))
        track(f"qa scene {s['scene']}", getattr(u, "prompt_tokens", 0) / 1e6 * pin + getattr(u, "completion_tokens", 0) / 1e6 * pout)
        out = json.loads(res.choices[0].message.content)
        return {"pass": bool(out.get("pass")), "problems": out.get("problems") or [], "retry_hint": out.get("retry_hint") or ""}
    except Exception as e:
        warn(f"Frame check unavailable for scene {s['scene']} ({str(e)[:60]}); accepting the clip")
        return {"pass": True, "problems": [], "retry_hint": ""}


# ── 2. SCENE RENDER: clip + speed ramp + captions + voice ────────────────────────────────────────────────────
def _render_scene(raw, audio, dur, stretch, narration, idx, out, palette, color_offset, ambient):
    from PIL import Image
    words  = align_words(speechify(narration), audio)
    cards  = group_cards(words)
    events = caption_events(words, max(0.5, dur - 0.12))
    cache  = {}

    def card_img(ci, wi):
        if (ci, wi) not in cache:
            cache[(ci, wi)] = render_card(cards[ci], wi, None, palette[(color_offset + ci) % len(palette)])
        return cache[(ci, wi)]

    # slow motion: stretch time, then let motion interpolation fill the in-between frames (smooth, not stuttery)
    smooth = ",minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1" if stretch > 1.3 else ",fps=30"
    vf = f"setpts={stretch:.4f}*PTS{smooth},scale={W}:{H}:flags=lanczos"
    dec = subprocess.Popen([FFMPEG, "-v", "error", "-i", str(raw), "-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    enc_in = [FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio)]
    if ambient:                                   # the clip's own sound, very low, under the narration
        enc_in += ["-i", str(raw), "-filter_complex",
                   f"[2:a]aresample=48000,volume={AMBIENT_VOLUME},atrim=0:{dur:.3f},apad=whole_dur={dur:.3f}[amb];"
                   f"[1:a]aresample=48000[nar];[nar][amb]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v", "-map", "[a]"]
    else:
        enc_in += ["-map", "0:v", "-map", "1:a"]
    enc_in += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{dur:.3f}", str(out)]
    log_path = out.with_suffix(".log")
    n, size, ptr, last = max(2, int(round(dur * FPS))), W * H * 3, 0, None
    with open(log_path, "wb") as lf:
        enc = subprocess.Popen(enc_in, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=lf)
        try:
            for fno in range(n):
                buf = dec.stdout.read(size)
                if buf and len(buf) == size:
                    last = buf
                elif last is None:
                    raise RuntimeError(f"scene {idx + 1}: the clip has no frames")
                frame = Image.frombytes("RGB", (W, H), last)          # past the end of the clip: hold the last frame
                t = fno / FPS
                while ptr + 1 < len(events) and events[ptr + 1][3] <= t:
                    ptr += 1
                if events and events[0][3] <= t < events[-1][4]:
                    ci, _, wi, _, _ = events[ptr]
                    card = card_img(ci, wi)
                    frame.paste(card, (0, CAPTION_TOP), card)
                try:
                    enc.stdin.write(frame.tobytes())
                except (BrokenPipeError, OSError):
                    break
        finally:
            try:
                enc.stdin.close()
            except Exception:
                pass
            dec.kill()
        rc = enc.wait()
    if rc != 0:
        raise RuntimeError(f"scene {idx + 1} render failed:\n{log_path.read_text(errors='ignore')[-500:]}")
    log_path.unlink(missing_ok=True)
    return len(cards)


# ── 3. THE FILM ──────────────────────────────────────────────────────────────────────────────────────────────
def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "film"


def print_direction(data, plan):
    print()
    print(c("  ── DIRECTION SHEET ───────────────────────────────────────────", "cyan"))
    for s, (dur, gen, f) in zip(data["scenes"], plan):
        mode = "SLOW-MO" if s["speed"] < 1 else "real time"
        print(f"  {c(str(s['scene']), 'bold')} {c(s['beat'].upper().ljust(7), 'yellow')} {dur:4.1f}s  "
              f"{mode:<9} {s.get('energy', ''):<6}  gen {gen}s x{f:.2f}  | {s['camera'][:44]}")
        print(f"      {c('say', 'dim')}  {s['narration']}")
        print(f"      {c('see', 'dim')}  {s['action']}")
    print()


def run_film(client, topic, model=DEFAULT_MODEL, res=DEFAULT_RES, yes=False, ambient=False, resume=None, notes=None, qa=True):
    key = _key()
    costs.reset()
    t0 = time.time()
    if resume:
        out_dir = Path(resume).expanduser()
        if not (out_dir / "script.json").exists():
            fail(f"Nothing to resume in {out_dir} (no script.json).")
        data = json.loads((out_dir / "script.json").read_text())
        topic = data.get("topic", topic)
        section(f"FILM  —  resuming  \"{data['title']}\"")
    else:
        if not (topic or "").strip():
            fail('No topic.  Usage: aieye run -film "how a fox hunts in the snow"')
        section(f"FILM  —  full pipeline, text-to-video  ({model} · {res})")
        log(f"Topic: {topic}", "cyan", indent=1)
        from .scriptlab import make_script
        data, out_dir = make_script(client, topic, notes)
        section(f"FILM  —  text-to-video  ({model} · {res})")
    from .scriptlab import sanitize_for_video
    data = sanitize_for_video(data)             # nothing but what a camera sees reaches the video model
    log(f"Folder: {out_dir}", "dim", indent=1)
    if not find_caption_font():
        warn("No bold caption font found; using Pillow's built-in font")

    # voice first: its length decides how long each scene is
    audio_paths = generate_audio(client, data, out_dir)
    durations   = get_durations(audio_paths, out_dir)
    info = next((m for m in list_models() if m.get("id") == model), None)
    if info is None:
        fail(f"Unknown model '{model}'. See ids with:  aieye models")
    plan = [(d, *plan_clip(d, s["speed"], info.get("supported_durations"))) for d, s in zip(durations, data["scenes"])]
    print_direction(data, plan)
    if res not in (info.get("supported_resolutions") or [res]):
        fail(f"{model} supports {info.get('supported_resolutions')}, not {res}.")
    todo = [i for i in range(len(plan)) if not (out_dir / f"scene_{i + 1}_raw.mp4").exists()]
    est = sum((estimate_cost(info, res, plan[i][1], False) or 0) for i in todo)
    log(f"Clips to generate: {len(todo)} of {len(plan)}   estimated {'$%.2f' % est if est else 'unknown'} "
        f"for {sum(plan[i][1] for i in todo)}s of footage (+ about $0.02 for script and voice)", "yellow", indent=1)
    if todo and not yes:                       # never spend on a countdown: an explicit yes is required
        try:
            ans = input(c(f"  Generate {len(todo)} clips for about ${est + 0.02:.2f}?  Type y to spend, anything else cancels: ", "bold"))
        except (KeyboardInterrupt, EOFError):
            ans = ""
        if ans.strip().lower() not in ("y", "yes"):
            fail("Cancelled. Nothing was spent on clips; the script and voice are saved, so you can resume later.")

    # CLIPS — text to video, 3 at a time; finished clips are saved at once so a failure never wastes paid ones
    clip_cost, qa_log = {}, {}
    def make(i):
        s = data["scenes"][i]
        base_prompt, hints, spent, best = scene_prompt(data, s), [], 0.0, None
        for attempt in range(1 + (MAX_RETRY if qa else 0)):
            prompt = base_prompt + (" AVOID: " + " ".join(hints) if hints else "")
            got, last_err = None, None
            for tries in range(3):             # a transient API failure must never lose the whole batch
                try:
                    got = generate_clip(key, model, res, plan[i][1], prompt)
                    break
                except (RuntimeError, SystemExit) as e:
                    last_err = str(e) or f"exit {getattr(e, 'code', '')}"
                    log(f"Scene {i + 1}: clip request failed ({last_err[:120]}); retry {tries + 1}/3", "yellow", indent=1)
                    time.sleep(15 * (tries + 1))
            if got is None:
                raise RuntimeError(f"scene {i + 1}: {last_err}")
            spent += float(got["cost"]) if got["cost"] is not None else (estimate_cost(info, res, plan[i][1], False) or 0)
            tmp_clip = out_dir / f"scene_{i + 1}_try{attempt + 1}.mp4"
            tmp_clip.write_bytes(got["content"])
            verdict = qa_clip(client, tmp_clip, plan[i][1], data, s, out_dir) if qa else {"pass": True, "problems": []}
            qa_log.setdefault(i + 1, []).append({"attempt": attempt + 1, "pass": verdict["pass"], "problems": verdict["problems"]})
            if best is None or len(verdict["problems"]) < best[1]:
                best = (got["content"], len(verdict["problems"]))
            tmp_clip.unlink(missing_ok=True)
            if verdict["pass"]:
                best = (got["content"], 0)
                break
            if verdict.get("retry_hint"):
                hints.append(verdict["retry_hint"])
        (out_dir / f"scene_{i + 1}_raw.mp4").write_bytes(best[0])
        return i, spent
    if todo:
        errors = []
        with spin(f"Generating {len(todo)} text-to-video clips ({sum(plan[i][1] for i in todo)}s of footage)..."):
            with ThreadPoolExecutor(max_workers=2) as ex:
                futs = [ex.submit(make, i) for i in todo]
                for fu in futs:
                    try:
                        i, cost = fu.result()
                        clip_cost[i] = cost
                    except (RuntimeError, SystemExit) as e:
                        errors.append(str(e) or repr(e))
        for i, cost in sorted(clip_cost.items()):
            track(f"clip {i + 1}", float(cost) if cost is not None else (estimate_cost(info, res, plan[i][1], False) or 0))
        if errors:
            fail(f"{len(errors)} clip(s) failed: {errors[0]}\n  Finished clips are saved. Re-run with:  "
                 f"aieye run -film -resume \"{out_dir}\"  (only the missing clips are generated and billed)")
        (out_dir / "qa.json").write_text(json.dumps(qa_log, indent=2, ensure_ascii=False))
        for k, tries in sorted(qa_log.items()):
            last = tries[-1]
            redo = len(tries) - 1
            msg = f"Scene {k}: {'passed' if last['pass'] else 'KEPT BEST OF ' + str(len(tries)) + ' (still flagged: ' + '; '.join(last['problems'])[:90] + ')'}" \
                  + (f" after {redo} redo{'s' if redo > 1 else ''}" if redo else " first time")
            (ok if last["pass"] else warn)(msg)
        ok(f"{len(todo)} clips ready")

    # RENDER — speed ramp + captions + voice, scene by scene (3 at a time)
    import random
    palette = (random.Random(int(time.time())).sample(CAPTION_PALETTE, len(CAPTION_PALETTE))
               if CAPTION_COLOR_MODE == "shuffle" else [CAPTION_ACCENT])
    offsets, run = [], 0
    with spin("Aligning captions to the voice..."):
        for i, s in enumerate(data["scenes"]):
            offsets.append(run)
            run += len(group_cards(align_words(speechify(s["narration"]), audio_paths[i])))
    finals = [out_dir / f"scene_{i + 1}_final.mp4" for i in range(len(plan))]
    with spin("Rendering scenes: speed ramps, captions, voice..."):
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(_render_scene, out_dir / f"scene_{i + 1}_raw.mp4", audio_paths[i], plan[i][0], plan[i][2],
                              s["narration"], i, finals[i], palette, offsets[i], ambient)
                    for i, s in enumerate(data["scenes"])]
            for fu in futs:
                fu.result()
    ok(f"{len(finals)} scenes rendered")

    # FINISH — join + loudness
    lst = out_dir / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in finals))
    film = out_dir / "film_9x16.mp4"
    with spin("Joining scenes and normalising loudness (-14 LUFS)..."):
        run_cmd([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy",
                 "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                 "-movflags", "+faststart", str(film)], label="join")
    total = sum(durations)
    (out_dir / "report.json").write_text(json.dumps({
        "topic": topic, "title": data["title"], "model": model, "resolution": res, "ambient_sound": ambient,
        "narration_seconds": round(total, 2), "cost_usd_this_run": round(costs.total(), 4),
        "scenes": [{"scene": s["scene"], "beat": s["beat"], "speed": s["speed"], "narration_s": round(d, 2),
                    "generated_s": g, "stretch": round(f, 2)} for s, (d, g, f) in zip(data["scenes"], plan)],
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    print()
    print(c("═" * 60, "bold"))
    print(c(f"  FILM READY  —  {data['title']}", "bold"))
    print(c("═" * 60, "bold"))
    print(f"  {c('Video ', 'dim')}  {c(str(film), 'cyan')}")
    print(f"  {c('Length', 'dim')}  {total:.1f}s   9:16 {W}x{H}   {film.stat().st_size / 1e6:.1f} MB")
    print(f"  {c('Cost  ', 'dim')}  {c('$%.2f' % costs.total(), 'yellow')} this run   ·   {time.time() - t0:.0f}s")
    print()
    return film


def merge_final(folder, out_name="final_with_audio.mp4"):
    """Free, offline: join the finished scene clips (picture + captions + voice) into one compatible file.
    H.264 + stereo AAC 48 kHz, loudness-normalised, faststart. Makes no API call."""
    folder = Path(folder)
    scenes = sorted(folder.glob("scene_*_final.mp4"), key=lambda p: int(p.stem.split("_")[1]))
    if not scenes:
        fail(f"No scene_N_final.mp4 files in {folder}. Run the film step first (-film -resume).")
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    for p in scenes:
        cmd += ["-i", str(p)]
    n = len(scenes)
    fc = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n)) + (f"concat=n={n}:v=1:a=1[v][a0];"
         "[a0]aresample=48000,loudnorm=I=-14:TP=-1.5:LRA=11,pan=stereo|c0=c0|c1=c0[a]")
    out = folder / out_name
    run_cmd(cmd + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                   "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                   "-movflags", "+faststart", str(out)], "final merge")
    ok(f"{out.name}  ({out.stat().st_size / 1e6:.1f} MB)")
    return out
