"""Write videos.json for the website from AI Eye's finished-video log.

Usage: python3 scripts/build_videos.py /path/to/aieye/data/db/final.json

Keeps only videos that have a YouTube id and that YouTube's public oEmbed
endpoint still serves (private or deleted videos are dropped).
"""
import json, sys, urllib.request, urllib.error

src = sys.argv[1]
rows = [r for r in json.load(open(src)) if r.get("youtube_id")]
out, seen = [], set()
for r in sorted(rows, key=lambda r: r.get("uploaded_at") or "", reverse=True):
    vid = r["youtube_id"]
    if vid in seen:
        continue
    seen.add(vid)
    url = "https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=" + vid
    try:
        urllib.request.urlopen(url, timeout=15).read()
    except urllib.error.URLError as e:
        print("skip", vid, getattr(e, "code", e), r["title"])
        continue
    out.append({"id": vid, "title": r["title"], "date": (r.get("uploaded_at") or "")[:10]})
json.dump(out, open("videos.json", "w"), indent=1, ensure_ascii=False)
print(len(out), "videos written")
