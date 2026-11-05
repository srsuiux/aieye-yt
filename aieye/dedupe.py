"""Strict duplicate-subject gate.

The old check only rejected an *identical title*, so "The Fish That Climbs Waterfalls" went out after
"The Fish That Climbs Waterfalls With Its Mouth" (1.1K views -> 61), and the same happened with galaxies,
axolotls, the Antikythera computer, Roman concrete... Every repeat did far worse than the original.

Two layers, both must pass:
  1. lexical  - free, instant: two titles that share 2+ meaningful word stems (or are >=40% alike) are the same topic
  2. LLM      - one cheap call: "is this the same animal / object / phenomenon as anything already made?"
"""
import json, re
from .config import FINAL_DB, DRAFT_DB, GPT_IN_COST, GPT_MODEL, GPT_OUT_COST
from .costs import track
from .store import load_db
from .ui import warn

_STOP = set("""a an the and or of to in on at for from with without by as is are was were be been being it its this that these those
how why what when where which who whom whose can could would should will does do did doesn done not no yes your you our we they
their them his her he she i me my so than then too very just only even still more most much many some any all one two three four
five six seven eight nine ten make makes made making get gets got have has had having keep keeps kept really actually real
about into over under up down out off back around across through between against during before after again once ever never
way ways thing things something anything everything look looks looking like seem seems also there here""".split())

_IRREGULAR = {"mice": "mouse", "geese": "goose", "teeth": "tooth", "feet": "foot", "men": "man", "children": "child"}

def _stem(w):
    w = _IRREGULAR.get(w, w)
    for suf, rep in (("ies", "y"), ("ing", ""), ("ers", ""), ("es", ""), ("ed", ""), ("er", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)] + rep
    return w

def keywords(text):
    words = re.findall(r"[a-z]+", text.lower().replace("’", "'"))
    return {_stem(w) for w in words if w not in _STOP and len(w) > 2}

def lexical_match(candidate, existing):
    """Return the first existing text that is the same topic as `candidate`, else None."""
    a = keywords(candidate)
    if not a:
        return None
    for e in existing:
        b = keywords(e)
        if not b:
            continue
        shared = a & b
        if len(shared) >= 2 or len(shared) / len(a | b) >= 0.4:
            return e
    return None

def history_texts():
    """Everything already made or queued: YouTube title + the original topic of each video, and queued topics."""
    out = []
    for e in load_db(FINAL_DB):
        out += [e.get("title", ""), e.get("topic", "")]
    for e in load_db(DRAFT_DB):
        if e.get("status") != "skipped_duplicate":
            out.append(e.get("title", ""))
    return list(dict.fromkeys(t for t in out if t))

def llm_duplicates(client, candidates, existing):
    """Indexes of `candidates` that cover the same animal / object / phenomenon as something in `existing`
    (or as an earlier candidate). Fails closed to 'no extra duplicates found' only if the call itself fails."""
    if not candidates:
        return set()
    prompt = f"""A YouTube Shorts channel must NEVER make two videos about the same subject.
Same subject = the same animal, object, place or phenomenon, even if the wording or angle differs
(e.g. "Fish that climbs waterfalls" and "How a tiny fish climbs a waterfall" are the same; so are
"The lizard that squirts blood" and "How a horned lizard makes a predator spit").

ALREADY MADE OR QUEUED:
{chr(10).join('- ' + t for t in existing) or '(none)'}

CANDIDATES:
{chr(10).join(f'{i}. {c}' for i, c in enumerate(candidates))}

Return ONLY JSON: {{"duplicates": [indexes of candidates that repeat an already-made subject, or repeat an
EARLIER candidate in this list]}}"""
    try:
        res = client.chat.completions.create(
            model=GPT_MODEL, messages=[{"role": "user", "content": prompt}],
            reasoning_effort="none", temperature=0, response_format={"type": "json_object"})
        u = res.usage
        track("gpt dedupe", (getattr(u, "prompt_tokens", 0) / 1e6 * GPT_IN_COST) +
                            (getattr(u, "completion_tokens", 0) / 1e6 * GPT_OUT_COST))
        return {int(i) for i in json.loads(res.choices[0].message.content).get("duplicates", [])}
    except Exception as e:
        warn(f"Duplicate check by AI unavailable ({str(e)[:60]}); using the word-match check only")
        return set()

def unique_only(client, candidates):
    """Keep only candidates (dicts with a 'title') that are new. Returns (kept, rejected[(title, why)])."""
    existing = history_texts()
    kept, rejected, seen = [], [], []
    for c in candidates:
        hit = lexical_match(c["title"], existing + seen)
        if hit:
            rejected.append((c["title"], f'too close to "{hit}"'))
        else:
            kept.append(c); seen.append(c["title"])
    bad = llm_duplicates(client, [c["title"] for c in kept], existing)
    final = []
    for i, c in enumerate(kept):
        if i in bad:
            rejected.append((c["title"], "same subject as an existing video"))
        else:
            final.append(c)
    return final, rejected
