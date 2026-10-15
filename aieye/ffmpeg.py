"""Locating ffmpeg and running it."""
import os
import subprocess

from .ui import fail, log


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


def run_cmd(cmd, label="ffmpeg"):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"{label} stderr:\n{r.stderr[-600:]}", "red")
        fail(f"{label} exited {r.returncode}")
    return r
