"""Videos that were made but not uploaded yet (data/output/<folder>/short.mp4), shared by the Library page and the assistant."""
import json
from datetime import datetime

from ..config import CHANNEL, OUTPUT_DIR
from ..languages import LANGS
from . import jobs


def kept_videos():
    act = jobs.active()
    items = []
    for video in sorted(OUTPUT_DIR.glob("*/short.mp4")) + sorted(OUTPUT_DIR.glob("*/*/short.mp4")):
        folder = video.parent
        if act and folder.stat().st_mtime >= act["created"] - 5:
            continue                                # still being made or waiting for review
        try:
            meta = json.loads((folder / "youtube_metadata.json").read_text())
        except (OSError, ValueError):
            continue
        items.append({"id": str(folder.relative_to(OUTPUT_DIR)), "title": meta.get("title", folder.name), "meta": meta,
                      "when": datetime.fromtimestamp(video.stat().st_mtime).strftime("%b %d, %H:%M"),
                      "size": round(video.stat().st_size / 1e6, 1), "lang": LANGS.get(meta.get("lang", "en"), ("English",))[0],
                      "tags": meta.get("tags") or CHANNEL["tags"]})
    return list(reversed(items))


def kept_folder(folder_id):
    p = (OUTPUT_DIR / folder_id).resolve()
    if OUTPUT_DIR.resolve() not in p.parents or not (p / "short.mp4").exists():
        raise LookupError("That video is no longer on this computer.")
    return p
