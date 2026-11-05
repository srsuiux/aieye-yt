import time, json
from datetime import datetime
from .config import AUDIENCE_NOTES, CFG, DRAFT_DB, FINAL_DB, GPT_IN_COST, GPT_MODEL, GPT_OUT_COST, N_TOPICS, TOP_CATEGORIES
from .costs import track
from .dedupe import unique_only
from .store import all_used_titles, get_pending, load_db, save_db
from .ui import fail, log, ok, section, spin, warn

# STEP 0 — TOPIC SELECTION

def generate_topics(client):
    used      = all_used_titles()
    used_list = "\n".join(f"- {t}" for t in sorted(used)) or "None yet."

    prompt = f"""You are a YouTube Shorts content strategist.
Generate exactly {N_TOPICS} unique viral-worthy YouTube Shorts topics for a general
audience — kids and adults. Categories: science, space, animals, nature, history,
technology, psychology, geography, math, physics.

{AUDIENCE_NOTES}

Already used — do NOT repeat, and do NOT re-angle: a different title about the same animal, object or
phenomenon counts as a repeat. Every topic must be about a subject not on this list:
{used_list}

Be specific: not "facts about space" but "5 ways neutron stars defy physics".

Return ONLY valid JSON:
{{
  "topics": [
    {{"title": "...", "hook": "one sentence why this is fascinating"}},
    ...
  ]
}}"""

    with spin("Generating fresh topics..."):
        res = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort="none",
            temperature=0.9,
            response_format={"type": "json_object"},
        )
    usage   = res.usage
    in_tok  = getattr(usage, "prompt_tokens",     0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    track("gpt topics", (in_tok/1e6*GPT_IN_COST)+(out_tok/1e6*GPT_OUT_COST))

    data   = json.loads(res.choices[0].message.content)
    topics = data.get("topics", [])
    fresh, rejected = unique_only(client, [t for t in topics if t.get("title")])
    for title, why in rejected:
        warn(f"Rejected repeat: \"{title}\" ({why})")
    ok(f"{len(fresh)} fresh topics generated")
    for i, t in enumerate(fresh):
        log(f"{i+1}. {t['title']}", "cyan", indent=2)
    return fresh

def refine_topic(client, raw):
    """Treat the user's topic as a reference: keep its subject and intent, rewrite it into an engaging Short topic."""
    prompt = f"""You are a YouTube Shorts hook writer for a facts channel (general audience, kids and adults).
The creator gave this rough topic as a REFERENCE: "{raw}"

{AUDIENCE_NOTES}

Keep its subject and what the creator wants to explore. Rewrite it into a topic that makes people stop scrolling:
a specific, curious, interactive framing (a question, a surprising contrast, or a "you've been wrong about this"
angle), under 80 characters, plain words, no clickbait lies, no emoji. Then give the angle the 5 facts should
take so the video stays on what the creator asked for.

Return ONLY JSON: {{"title": "...", "hook": "one sentence: the angle and why it is fascinating"}}"""
    with spin("Rewriting your topic to be more engaging..."):
        res = client.chat.completions.create(
            model=GPT_MODEL, messages=[{"role": "user", "content": prompt}],
            reasoning_effort="none", temperature=0.8, response_format={"type": "json_object"})
    u = res.usage
    track("gpt topic rewrite", (getattr(u, "prompt_tokens", 0) / 1e6 * GPT_IN_COST) +
                               (getattr(u, "completion_tokens", 0) / 1e6 * GPT_OUT_COST))
    out = json.loads(res.choices[0].message.content)
    return out["title"].strip().strip('"'), out.get("hook", "").strip()

_top_runs = 0
MAX_TRIES = 4

def unique_topic(client, make):
    """Ask `make(rejected_titles)` for one topic until it is not a repeat. Fails after MAX_TRIES (never ships a repeat)."""
    rejected = []
    for _ in range(MAX_TRIES):
        cand = make(rejected)
        kept, bad = unique_only(client, [cand])
        if kept:
            return cand
        warn(f"Rejected repeat: \"{cand['title']}\" ({bad[0][1]})")
        rejected.append(cand["title"])
    fail(f"Could not find a topic that isn't a repeat after {MAX_TRIES} tries. Nothing was made.")

def top_topic(client):
    """One topic from the top-performing categories, rotating so a batch covers all of them. Not stored in the queue."""
    global _top_runs
    start = _top_runs + (int(time.time()) % len(TOP_CATEGORIES) if _top_runs == 0 else 0)
    category = TOP_CATEGORIES[start % len(TOP_CATEGORIES)]
    _top_runs = start + 1

    def make(rejected):
        used = "\n".join(f"- {t}" for t in sorted(all_used_titles()) + rejected) or "None yet."
        prompt = f"""You are a YouTube Shorts content strategist for a kids' facts channel (core viewers: curious 8-12 year olds).
Write ONE topic in this category: {category}

{AUDIENCE_NOTES}
The topic must be highly VISUAL: one striking subject that looks amazing as a big, close-up photo.

Already used, do NOT repeat or re-angle (a different title about the same animal, object or phenomenon is a repeat):
{used}

Be specific (not "facts about the ocean"). Return ONLY JSON: {{"title": "...", "hook": "one sentence: the angle and why it is fascinating"}}"""
        with spin(f"Picking a top-category topic ({category.split(' (')[0]})..."):
            res = client.chat.completions.create(
                model=GPT_MODEL, messages=[{"role": "user", "content": prompt}],
                reasoning_effort="none", temperature=0.9, response_format={"type": "json_object"})
        u = res.usage
        track("gpt top topic", (getattr(u, "prompt_tokens", 0) / 1e6 * GPT_IN_COST) +
                               (getattr(u, "completion_tokens", 0) / 1e6 * GPT_OUT_COST))
        out = json.loads(res.choices[0].message.content)
        return {"title": out["title"].strip(), "hook": out.get("hook", "").strip()}

    out = unique_topic(client, make)
    log(f"Category: {category.split(' (')[0]}", "dim", indent=1)
    log(f"Topic: {out['title']}", "cyan", indent=1)
    return {"id": f"top_{int(time.time())}_{_top_runs}", "title": out["title"], "hook": out["hook"],
            "status": "manual", "created_at": datetime.now().isoformat()}

def drop_repeat_pending(client, pending):
    """Strictly re-check the queue against what has been made: repeats are marked 'skipped_duplicate' and never built."""
    if not pending:
        return pending
    from .dedupe import history_texts, lexical_match, llm_duplicates
    done = [t for e in load_db(FINAL_DB) for t in (e.get("title", ""), e.get("topic", "")) if t]
    queued = {t["id"] for t in pending}
    others = [t["title"] for t in load_db(DRAFT_DB) if t["id"] not in queued and t.get("status") != "skipped_duplicate"]
    bad_ids, seen = set(), []
    for t in pending:
        hit = lexical_match(t["title"], done + others + seen)
        if hit:
            warn(f"Skipping queued repeat: \"{t['title']}\" (too close to \"{hit}\")"); bad_ids.add(t["id"])
        else:
            seen.append(t["title"])
    rest = [t for t in pending if t["id"] not in bad_ids]
    for i in llm_duplicates(client, [t["title"] for t in rest], done + others):
        warn(f"Skipping queued repeat: \"{rest[i]['title']}\" (same subject as an existing video)"); bad_ids.add(rest[i]["id"])
    if bad_ids:
        draft = load_db(DRAFT_DB)
        for t in draft:
            if t["id"] in bad_ids:
                t["status"] = "skipped_duplicate"
        save_db(DRAFT_DB, draft)
    return [t for t in pending if t["id"] not in bad_ids]

def pick_topic(client):
    section("STEP 0  —  Topic Selection")

    if CFG.get("top") and not CFG["manual_topic"]:
        return top_topic(client)

    if CFG.get("trending") and not CFG["manual_topic"]:
        from .trending import trending_topic
        return trending_topic(client)

    if CFG["manual_topic"]:
        raw = CFG["manual_topic"]
        log(f"Your topic:  \"{raw}\"", "dim", indent=1)
        title, hook = raw, ""
        try:
            title, hook = refine_topic(client, raw)
            log(f"Rewritten:  \"{title}\"", "cyan", indent=1)
            log(f"Angle:      {hook}", "dim", indent=1)
        except Exception as e:
            warn(f"Could not rewrite the topic ({str(e)[:80]}) — using it as written")
        return {
            "id":         f"manual_{int(time.time())}",
            "title":      title,
            "hook":       hook or f"Based on the creator's idea: {raw}",
            "status":     "manual",
            "created_at": datetime.now().isoformat(),
        }

    pending = drop_repeat_pending(client, get_pending())
    if pending:
        topic = pending[0]
        log(f"From queue: \"{topic['title']}\"", "cyan", indent=1)
        log(f"{len(pending)-1} more pending after this", "dim", indent=1)
        return topic

    warn("Queue empty — generating new topics...")
    fresh = generate_topics(client)

    now     = datetime.now().isoformat()
    entries = [
        {"id": f"topic_{int(time.time())}_{i}", "title": t["title"],
         "hook": t.get("hook",""), "status": "pending", "created_at": now}
        for i, t in enumerate(fresh)
    ]
    save_db(DRAFT_DB, entries)
    ok(f"Saved {len(entries)} topics to queue")
    topic = entries[0]
    log(f"Starting: \"{topic['title']}\"", "cyan", indent=1)
    return topic

