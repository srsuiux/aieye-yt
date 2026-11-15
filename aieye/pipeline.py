import os, sys, time, json, shutil
from datetime import datetime
from . import costs
from .audio import generate_audio, get_durations
from .client import get_client
from .config import CFG, CHANNEL, DB_DIR, OUTPUT_DIR
from .images import generate_images
from .limits import DAILY_LIMIT, pushed_today
from .languages import LANGS, localize_script
from .script import generate_script
from .settings import get_args, setup_run, shuffled_voices
from .store import get_pending, mark_done, mark_in_progress
from .topics import pick_topic
from .ui import c, fail, log, ok, section, spin, warn
from .video import assemble_video
from .youtube import upload_to_youtube

# CLEANUP

MODEL_ALIASES = {"grok": "x-ai/grok-imagine-video-1.5-lite", "veo": "google/veo-3.1-lite", "veo-fast": "google/veo-3.1-fast",
                 "seedance": "bytedance/seedance-2.0-fast", "kling": "kwaivgi/kling-v3.0-std"}

def keep_only_final(out_dir):
    """Not uploaded (yet): drop the intermediates but keep short.mp4 + youtube_metadata.json."""
    section("CLEANUP")
    keep    = {"short.mp4", "youtube_metadata.json"}
    deleted = 0
    for item in list(out_dir.iterdir()):
        if item.is_dir() and item.name in LANGS:          # a language folder: same rule inside it
            for sub in list(item.iterdir()):
                if sub.name not in keep:
                    shutil.rmtree(sub) if sub.is_dir() else sub.unlink()
                    deleted += 1
            continue
        if item.name in keep:
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()
        deleted += 1
    ok(f"Removed {deleted} temp items — kept short.mp4 + youtube_metadata.json (not uploaded)")

def remove_output(out_dir):
    """Posted to YouTube: the whole run folder (video, metadata, temp files) is deleted."""
    section("CLEANUP")
    shutil.rmtree(out_dir, ignore_errors=True)
    ok(f"Posted — removed {out_dir.name}/")

def print_upload_metadata(meta):
    """Print the uploaded title/description/tags as plain text for copy-paste
    (e.g. into TikTok). No colour codes inside the block so it copies clean."""
    print()
    print(c("── Metadata (copy-paste) " + "─"*35, "cyan"))
    print(f"TITLE:\n{meta['title']}\n")
    print(f"DESCRIPTION:\n{meta['description']}\n")
    print(f"TAGS:\n{' '.join('#' + t.replace(' ', '') for t in CHANNEL['tags'])}")
    print(c("─"*60, "cyan"))
    print()

def run_one(client, review=None):
    """Build (and upload) one video. Never raises: returns a result dict so a batch can carry on.

    review: optional callback(info) used by the web app to pause before each upload. info has "lang", "video_path",
    "meta" (title, description, tags, privacy) and "title". It returns {"action": "upload", "meta": {...edited...}}
    or {"action": "skip"}. Without it (the terminal) videos upload straight away, as before."""
    costs.reset()
    t0  = time.time()
    res = {"ok": False, "title": None, "topic": None, "url": None, "path": None,
           "cost": 0.0, "seconds": 0.0, "error": None, "abort": False}
    try:
        # 1. Pick topic
        topic = pick_topic(client)
        res["topic"] = topic["title"]
        if topic["status"] != "manual":
            mark_in_progress(topic)

        out_dir = OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir.mkdir(parents=True, exist_ok=True)

        print()
        log(f"  Building: \"{topic['title']}\"", "cyan")
        log(f"  Output:   {out_dir}", "dim")

        # 2. Script (English) and pictures are made once; every language reuses the same pictures
        langs = CFG.get("languages") or ["en"]
        script      = generate_script(client, topic, out_dir)
        img_paths   = generate_images(client, script, out_dir)
        res["title"] = script["title"]

        # 3. One finished video per requested language
        outcomes = []
        for code in langs:
            lang_script, lang_dir = script, out_dir
            if code != "en":
                lang_script = localize_script(client, script, code)
                lang_dir    = out_dir / code
                lang_dir.mkdir(exist_ok=True)
            tag = f"[{LANGS[code][0]}] " if len(langs) > 1 else ""
            log(f"{tag}Building the {LANGS[code][0]} video", "cyan")
            audio_paths = generate_audio(client, lang_script, lang_dir)
            durations   = get_durations(audio_paths, lang_dir)
            video_path  = assemble_video(img_paths, audio_paths, durations, lang_dir, lang_script)
            res["path"] = res["path"] or str(video_path)

            scene_facts = "\n".join(f"{s['scene']}. {s['narration']}" for s in lang_script["scenes"])
            meta = {
                "title":       lang_script["title"] + " #Shorts",
                "description": CHANNEL["description"].replace("{scene_facts}", scene_facts),
                "lang":        code,
            }
            with open(lang_dir / "youtube_metadata.json", "w") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

            # 4. Upload (a failed upload keeps the rendered video and does not stop the others)
            video_id = None
            try:
                if review and CFG.get("upload_privacy") != "none":
                    decision = review({"lang": code, "video_path": str(video_path), "title": meta["title"],
                                       "meta": {**meta, "tags": CHANNEL["tags"], "privacy": CFG["upload_privacy"]}})
                    if (decision or {}).get("action") == "upload":
                        meta = {**meta, **decision.get("meta", {})}
                        with open(lang_dir / "youtube_metadata.json", "w") as f:
                            json.dump(meta, f, indent=2, ensure_ascii=False)
                        video_id = upload_to_youtube(video_path, meta)
                    else:
                        log(f"{tag}Upload skipped after review — video kept locally", "yellow")
                else:
                    video_id = upload_to_youtube(video_path, meta)
            except Exception as e:
                warn(f"{tag}Upload failed: {str(e)[:200]}")
                res["error"] = f"upload failed ({code}): {str(e)[:100]}"
            outcomes.append((code, lang_script, meta, video_path, video_id))
            if video_id and not res["url"]:
                res["url"] = f"https://youtube.com/shorts/{video_id}"

        # 5. Summary
        print()
        print(c("═"*60, "bold"))
        print(c("  PIPELINE COMPLETE", "bold"))
        print(c("═"*60, "bold"))
        print(f"  {c('Topic  ','dim')}  {c(topic['title'], 'cyan')}")
        for code, ls, _m, vp, vid in outcomes:
            print(f"  {c(LANGS[code][0][:7].ljust(7),'dim')}  {c(ls['title'], 'cyan')}")
        print(f"  {c('Style  ','dim')}  {c(CFG['image_style'], 'white')}  ·  {c(CFG['image_quality'], 'white')}  ·  {c(CFG['tts_voice'], 'white')}")
        print(f"  {c('Time   ','dim')}  {c(f'{time.time()-t0:.1f}s', 'green')}")
        print(f"  {c('Cost   ','dim')}  {c(f'${costs.total():.4f}', 'yellow')}")
        print(f"  {c('Queue  ','dim')}  {c(str(len(get_pending()))+' topics pending', 'dim')}")
        print(c("═"*60, "bold"))
        print()

        # 6. Finalize: log it; once every video is really on YouTube the local files are no longer needed
        ids = {code: vid for code, _s, _m, _v, vid in outcomes if vid and vid != "unknown"}
        mark_done(topic, script, ids.get("en") or next(iter(ids.values()), None), ids if len(langs) > 1 else None)
        if len(ids) == len(langs):
            remove_output(out_dir)
        else:
            keep_only_final(out_dir)

        for code, _s, meta, _v, vid in outcomes:
            if vid:
                print(f"  {c('▶  Live at:','green')} {c(f'https://youtube.com/shorts/{vid}','cyan')}  ({LANGS[code][0]})")
            print_upload_metadata(meta)
        res["ok"] = res["error"] is None
    except SystemExit:
        res["error"] = res["error"] or "stopped (see the error above)"
    except Exception as e:
        import traceback
        msg = f"{type(e).__name__}: {e}"
        res["error"] = msg[:200]
        log(f"❌  {msg[:400]}", "red")
        log("".join(traceback.format_exc().splitlines(True)[-6:]), "dim")
        if "insufficient_quota" in msg or "credit_balance_exhausted" in msg:
            res["abort"] = True      # no point trying the next video
    res["cost"], res["seconds"] = costs.total(), time.time() - t0
    return res

def print_batch_summary(results, seconds):
    good = sum(1 for r in results if r["ok"])
    print()
    print(c("═"*60, "bold"))
    print(c(f"  BATCH COMPLETE  —  {good}/{len(results)} succeeded", "bold"))
    print(c("═"*60, "bold"))
    for i, r in enumerate(results, 1):
        mark  = c("✅", "green") if r["ok"] else c("❌", "red")
        title = r["title"] or r["topic"] or "(no title)"
        where = r["url"] or (r["path"] if r["path"] else "")
        if r["error"]:
            where = f"{where}  {c(r['error'], 'red')}".strip()
        voice = c(f"[{r.get('voice', '')}]", "dim")
        print(f"  {mark} {i}. {title[:40]:40s} {voice:>17s} {c('$%.3f' % r['cost'], 'yellow')}  {where}")
    total = sum(r["cost"] for r in results)
    print(c("  ────────────────────────────────────────────────", "cyan"))
    print(f"  Total cost {c('$%.3f' % total, 'yellow')}   ·   Time {c(f'{seconds/60:.1f} min', 'green')}   ·   Queue {c(str(len(get_pending()))+' pending', 'dim')}")
    print(c("═"*60, "bold"))
    print()

def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("web", "-web", "--web"):    # the local web app (see aieye/web/server.py)
        import argparse
        ap = argparse.ArgumentParser(prog="aieye web", description="AI Eye web app")
        ap.add_argument("--host", default="127.0.0.1", help="address to listen on (default: this computer only)")
        ap.add_argument("--port", type=int, default=8420)
        ap.add_argument("--no-open", action="store_true", help="do not open the browser")
        a = ap.parse_args(argv[1:])
        try:
            from .web.server import run
        except ImportError:
            fail("The web app needs: pip install fastapi uvicorn jinja2 markdown")
        run(a.host, a.port, open_browser=not a.no_open)
        return
    if argv == ["menu"]:                        # straight into the AI video studio (also reachable from the main menu)
        from .menu import main_menu
        main_menu()
        return
    args  = get_args()
    if getattr(args, "img", False):             # experiment mode: stills only; no queue, no daily limit, no upload
        from .imgexp import run_image_experiment
        client = get_client()
        run_image_experiment(client, args.img_prompt, args.img_count, args.quality or "high")
        return
    if getattr(args, "script", False):          # experiment mode: the script only; no video, no audio, no upload
        from .scriptlab import make_script
        make_script(get_client(), args.script_topic, args.notes, resume=args.resume)
        return
    if getattr(args, "film", False):            # experiment mode: whole pipeline with text-to-video; nothing is uploaded
        from .film import run_film
        from .videxp import DEFAULT_MODEL, DEFAULT_RES
        run_film(get_client(), args.film_topic, MODEL_ALIASES.get((args.model or "").lower(), args.model) or DEFAULT_MODEL, args.res or DEFAULT_RES,
                 yes=args.yes, ambient=args.ambient, resume=args.resume, notes=args.notes, qa=args.qa and not args.noqa)
        return
    if getattr(args, "vid", False):             # experiment mode: one clip from a still; no queue, no daily limit, no upload
        from .videxp import DEFAULT_MODEL, DEFAULT_RES, DEFAULT_DUR, run_video_experiment
        run_video_experiment(args.vid_prompt, args.vid_image, args.model or DEFAULT_MODEL,
                             args.res or DEFAULT_RES, args.dur or DEFAULT_DUR, yes=args.yes)
        return
    count = setup_run(args)

    DB_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    with spin("Initializing OpenAI client..."):
        client = get_client()
    ok("OpenAI client ready")

    voices     = shuffled_voices(count) if ((count > 1 or CFG.get("force_shuffle")) and CFG["batch_voice"] == "shuffle") else None
    base_voice = CFG["tts_voice"]
    results, t0 = [], time.time()
    for n in range(1, count + 1):
        if pushed_today() >= DAILY_LIMIT:
            warn(f"I can't create more than {DAILY_LIMIT} videos a day: today's limit is reached. Stopping here.")
            break
        if voices:
            CFG["tts_voice"] = voices[n - 1]
        if count > 1:
            print()
            print(c("█"*60, "cyan"))
            print(c(f"  VIDEO {n} of {count}   ·   narrator: {CFG['tts_voice']}", "bold"))
            print(c("█"*60, "cyan"))
        results.append(run_one(client))
        results[-1]["voice"] = CFG["tts_voice"]
        CFG["manual_topic"] = None            # a custom topic only ever applies to the first video
        if results[-1]["abort"]:
            warn("OpenAI credits exhausted — stopping the batch here")
            break

    CFG["tts_voice"] = base_voice
    if count > 1:
        print_batch_summary(results, time.time() - t0)
    else:
        print(f"  {c('Run again to build the next topic automatically.','dim')}")
        print()
    if not all(r["ok"] for r in results):
        sys.exit(1)

if __name__ == "__main__":
    main()
