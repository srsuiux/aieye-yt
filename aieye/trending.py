"""Trending topics from the live web (no API keys): Google Trends + Wikipedia's most-read pages."""
import json, re, time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from .config import GPT_IN_COST, GPT_MODEL, GPT_OUT_COST
from .costs import track
from .ui import fail, log, ok, section, spin, warn

UA = {"User-Agent": "Mozilla/5.0 (AIEye shorts pipeline)"}
_WIKI_SKIP = re.compile(r"^(Main_Page|Special:|Wikipedia:|Portal:|Help:|File:|Category:|Template:|Talk:|-$|Deaths_in|List_of)")
_used_this_run = []          # trends already turned into a video in this run (so a batch gets different ones)


def _google_trends(limit=25):
    import requests
    r = requests.get("https://trends.google.com/trending/rss?geo=US", headers=UA, timeout=15)
    r.raise_for_status()
    ns  = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        title = (it.findtext("title") or "").strip()
        news  = [n.findtext("ht:news_item_title", namespaces=ns) for n in it.findall("ht:news_item", ns)][:2]
        if title:
            out.append({"source": "Google Trends", "title": title,
                        "context": " | ".join(n for n in news if n)})
    return out[:limit]


def _wikipedia(limit=25):
    import requests
    for back in (1, 2, 3):                      # yesterday's data is sometimes not published yet
        d = datetime.utcnow() - timedelta(days=back)
        url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/"
               f"{d:%Y/%m/%d}")
        r = requests.get(url, headers=UA, timeout=15)
        if r.ok:
            arts = r.json()["items"][0]["articles"]
            names = [a["article"] for a in arts if not _WIKI_SKIP.match(a["article"])]
            return [{"source": "Wikipedia most-read", "title": n.replace("_", " "), "context": ""}
                    for n in names[:limit]]
    return []


def fetch_trends():
    items = []
    for fn in (_google_trends, _wikipedia):
        try:
            items += fn()
        except Exception as e:
            warn(f"{fn.__name__.strip('_')} unavailable: {str(e)[:80]}")
    return items


def trending_topic(client):
    """Fetch what is trending now and turn the best fit into a Short topic. Does not touch the DB."""
    section("STEP 0  —  Trending topic (web)")
    with spin("Checking what is trending..."):
        items = fetch_trends()
    if not items:
        fail("Could not reach any trending source (check your internet connection)")
    ok(f"{len(items)} trending items found")

    listing = "\n".join(f"{i+1}. [{t['source']}] {t['title']}" + (f" — {t['context']}" if t["context"] else "")
                        for i, t in enumerate(items))
    avoid = "\n".join(f"- {t}" for t in _used_this_run) or "None."
    prompt = f"""You run a YouTube Shorts channel of surprising facts for a general audience (kids and adults).
Below is what is trending on the web right now. Pick the ONE item that makes the best "5 surprising facts" Short.

Good: science, space, nature, animals, history, technology, psychology, geography, health, culture, famous
places/people from history, big events with a fascinating story behind them.
Skip: tragedies and deaths, crimes, politics and elections, sexual or graphic content, gambling, gossip about
living private people, anything where facts could be unsettled or unverifiable.

Already used in this run (do not pick again):
{avoid}

Trending items:
{listing}

Write the topic as a specific, curiosity-driven title (not just the trend name), with an angle built on
well-established facts, not on unconfirmed news. Return ONLY JSON:
{{"trend": "the item you chose", "title": "the Short's topic", "hook": "one sentence: why people care right now"}}"""
    with spin("Picking the best trend for a Short..."):
        res = client.chat.completions.create(
            model=GPT_MODEL, messages=[{"role": "user", "content": prompt}],
            reasoning_effort="none", temperature=0.7, response_format={"type": "json_object"})
    u = res.usage
    track("gpt trending", (getattr(u, "prompt_tokens", 0) / 1e6 * GPT_IN_COST) +
                          (getattr(u, "completion_tokens", 0) / 1e6 * GPT_OUT_COST))
    pick = json.loads(res.choices[0].message.content)
    _used_this_run.append(pick.get("trend", pick["title"]))
    log(f"Trend: {pick.get('trend','?')}", "dim", indent=1)
    log(f"Topic: {pick['title']}", "cyan", indent=1)
    return {"id": f"trending_{int(time.time())}", "title": pick["title"], "hook": pick.get("hook", ""),
            "status": "manual",            # "manual" = not from the queue: no queue/history bookkeeping on pick
            "created_at": datetime.now().isoformat()}
