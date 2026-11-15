"""Experiment mode: `aieye run -img 1 "image prompt"` makes high-definition, centre-focused 9:16 stills.

Purpose: feed the pictures to outside image-to-video tools and compare which gives the best result for the
lowest price. It never touches the topic queue, the history, the daily video limit or YouTube.
"""
import base64, json, re, time
from datetime import datetime

from .config import DATA_DIR, IMAGE_MODEL, IMAGE_SIZE
from .costs import track
from .images import call_with_retry, image_call_cost
from .ui import c, fail, log, ok, section, spin

EXP_DIR    = DATA_DIR / "experiments" / "images"
MAX_IMAGES = 4                     # per command, to keep experiment spend small
OUT_W, OUT_H = 1080, 1920          # 9:16, the size image-to-video tools and Shorts expect

# Centre focus: the subject sits dead centre with generous margin, so the 9:16 crop never clips it and a slow
# zoom / parallax / camera move has room to travel. A clean, separable background helps depth-based animation.
CENTER_SUFFIX = (
    "Vertical 9:16 portrait composition, ultra high definition, razor-sharp detail, natural photographic lighting. "
    "ONE hero subject placed dead centre of the frame, large and unmistakable, occupying the middle 60% of the width "
    "and the middle 60% of the height, with generous empty margin on all four sides (nothing important within 15% "
    "of any edge). Clear separation between subject and a simple, softly blurred background with visible depth "
    "(foreground, subject, background). No text, no captions, no watermark, no borders."
)

def _crop_9x16(img):
    """Centre-crop to exactly 9:16 (a 2:3 image is wider, so trim the sides equally)."""
    w, h = img.size
    new_w = round(h * 9 / 16)
    if new_w <= w:
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    new_h = round(w * 16 / 9)                 # image already narrower than 9:16: trim top and bottom
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))

def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "image"

def run_image_experiment(client, prompt, count, quality):
    from PIL import Image
    import io
    if not prompt.strip():
        fail('No prompt given.  Usage: aieye run -img 1 "a red fox in fresh snow"')
    count = max(1, min(count, MAX_IMAGES))
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    section(f"EXPERIMENT  —  {count} centre-focus 9:16 image(s)  ({IMAGE_MODEL} · {quality})")
    log(f"Prompt: {prompt}", "cyan", indent=1)

    full_prompt = f"{prompt.strip()}. {CENTER_SUFFIX}"
    stamp, total, saved = datetime.now().strftime("%Y%m%d_%H%M%S"), 0.0, []
    for i in range(1, count + 1):
        with spin(f"Generating image {i} of {count}..."):
            res = call_with_retry(
                lambda: client.images.generate(model=IMAGE_MODEL, prompt=full_prompt, size=IMAGE_SIZE,
                                               quality=quality, n=1),
                f"image {i}")
        if not res.data or not res.data[0].b64_json:
            fail(f"Image {i}: empty response from the API")
        raw = base64.b64decode(res.data[0].b64_json)
        cost = image_call_cost(res, quality)
        total += cost

        base = EXP_DIR / f"{stamp}_{_slug(prompt)}_{i}"
        raw_path = base.with_name(base.name + "_raw.png")
        raw_path.write_bytes(raw)                                    # exactly what the API returned
        src = Image.open(io.BytesIO(raw)).convert("RGB")
        final = _crop_9x16(src).resize((OUT_W, OUT_H), Image.LANCZOS)
        final_path = base.with_name(base.name + f"_{OUT_W}x{OUT_H}.png")
        final.save(final_path, optimize=True)
        base.with_suffix(".json").write_text(json.dumps({
            "prompt": prompt, "full_prompt": full_prompt, "model": IMAGE_MODEL, "quality": quality,
            "api_size": IMAGE_SIZE, "source_px": list(src.size), "output_px": [OUT_W, OUT_H],
            "cost_usd": round(cost, 4), "created_at": datetime.now().isoformat(timespec="seconds"),
        }, indent=2, ensure_ascii=False))
        saved.append(final_path)
        ok(f"Image {i}: {src.size[0]}x{src.size[1]} -> {OUT_W}x{OUT_H}   ${cost:.3f}   {final_path.name}")
    track(IMAGE_MODEL, total)

    print()
    print(c("  Saved in:", "bold"), c(str(EXP_DIR), "cyan"))
    for p in saved:
        print("   ", p.name)
    print(c(f"  Cost: ${total:.3f}  (${total / count:.3f} each)", "yellow"))
    print(c("  Note: the 1080x1920 file is the API picture cropped to 9:16 and upscaled; the _raw.png is the untouched original.", "dim"))
    print()
