"""AI video: topic -> pick a model -> script, voice, clips, captions -> one final mp4. One confirmation before spending."""
from .ui import c, fail, log, ok, prompt_choice, prompt_text, section

MODELS = [   # label, OpenRouter id, price per second of video (720p, no audio) for the estimate
    ("Grok Imagine Lite", "x-ai/grok-imagine-video-1.5-lite", "cheapest"),
    ("Veo 3.1 Lite",      "google/veo-3.1-lite",              "high quality, low price"),
    ("Veo 3.1 Fast",      "google/veo-3.1-fast",              "top quality of these, higher price"),
]
EST_SECONDS = 30      # a typical film


def make_video():
    from .client import get_client
    from .film import merge_final, run_film
    from .scriptlab import make_script

    topic = prompt_text("What should the video explain?", None)
    if not topic:
        return

    live = {}
    try:
        from .videxp import list_models
        live = {m["id"]: m for m in list_models()}
    except Exception:
        pass
    from .videxp import estimate_cost
    choices = []
    for label, mid, note in MODELS:
        e = estimate_cost(live[mid], "720p", EST_SECONDS, False) if mid in live else None
        choices.append((label, mid, f"{note}" + (f"  ·  about ${e + 0.3:.2f} for the whole video" if e else "")))
    model = prompt_choice("Video model", choices)

    try:
        ans = input(c("  Make it now? This spends credit.  Type y to go on, anything else cancels: ", "bold")).strip().lower()
    except (KeyboardInterrupt, EOFError):
        ans = ""
    if ans not in ("y", "yes"):
        log("Cancelled. Nothing was spent.", "dim", indent=1)
        return

    client = get_client()
    data, out_dir = make_script(client, topic)
    run_film(client, "", model, "720p", yes=True, resume=str(out_dir), qa=False)
    final = merge_final(out_dir)
    section("DONE")
    log(f"Video: {final}", "green", indent=1)


def main_menu():
    make_video()
