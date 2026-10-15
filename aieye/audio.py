import re, subprocess
from .config import CFG, TTS_COST, TTS_FALLBACK, TTS_MODEL, TTS_STYLE
from .costs import track
from .ffmpeg import FFMPEG, run_cmd
from .store import load_ckpt, save_ckpt
from .ui import log, ok, section, skip, spin, warn

# STEP 2 — AUDIO

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

