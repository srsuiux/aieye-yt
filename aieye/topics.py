import time, json
from datetime import datetime
from .config import CFG, DRAFT_DB, GPT_IN_COST, GPT_MODEL, GPT_OUT_COST, N_TOPICS
from .costs import track
from .store import all_used_titles, get_pending, save_db
from .ui import log, ok, section, spin, warn

# STEP 0 — TOPIC SELECTION

def generate_topics(client):
    used      = all_used_titles()
    used_list = "\n".join(f"- {t}" for t in sorted(used)) or "None yet."

    prompt = f"""You are a YouTube Shorts content strategist.
Generate exactly {N_TOPICS} unique viral-worthy YouTube Shorts topics for a general
audience — kids and adults. Categories: science, space, animals, nature, history,
technology, psychology, geography, math, physics.

Already used — do NOT repeat:
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
    fresh  = [t for t in topics if t["title"].lower() not in used]
    ok(f"{len(fresh)} fresh topics generated")
    for i, t in enumerate(fresh):
        log(f"{i+1}. {t['title']}", "cyan", indent=2)
    return fresh

def refine_topic(client, raw):
    """Treat the user's topic as a reference: keep its subject and intent, rewrite it into an engaging Short topic."""
    prompt = f"""You are a YouTube Shorts hook writer for a facts channel (general audience, kids and adults).
The creator gave this rough topic as a REFERENCE: "{raw}"

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

def pick_topic(client):
    section("STEP 0  —  Topic Selection")

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

    pending = get_pending()
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

