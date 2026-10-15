import re, time, base64
from .config import CFG, IMAGE_COST, IMAGE_IN_COST, IMAGE_MODEL, IMAGE_OUT_COST, IMAGE_SIZE, IMAGE_TEXT_IN_COST, IMAGE_WORKERS
from .costs import track
from .ui import fail, ok, section, spin, warn

# STEP 3 — IMAGES

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

