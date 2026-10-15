"""Supported narration languages and the turn-an-English-script-into-another-language step."""
import json

from .config import GPT_IN_COST, GPT_MODEL, GPT_OUT_COST
from .costs import track
from .ui import fail, ok, spin

# code → (name, how the language should sound, needs a romanised copy for caption timing)
LANGS = {
    "en": ("English", "", False),
    "hi": ("Hindi", "natural spoken Hindi in Devanagari, the way a friendly Indian presenter talks; common English "
                    "words (like ISS, satellite, gravity) stay as people actually say them", True),
    "es": ("Spanish", "natural neutral Latin-American Spanish", False),
    "fr": ("French", "natural spoken French", False),
    "de": ("German", "natural spoken German", False),
    "pt": ("Portuguese", "natural Brazilian Portuguese", False),
    "it": ("Italian", "natural spoken Italian", False),
    "id": ("Indonesian", "natural spoken Indonesian", False),
    "tr": ("Turkish", "natural spoken Turkish", False),
}
ALIASES = {n.lower(): code for code, (n, _, _) in LANGS.items()}
ALIASES.update({"hindi": "hi", "spanish": "es", "espanol": "es", "english": "en"})

def lang_code(token):
    """'-hindi' / 'hi' / 'Hindi' → 'hi', or None if it is not a language."""
    t = token.lstrip("-").lower()
    return t if t in LANGS else ALIASES.get(t)

def localize_script(client, script, code):
    """Same story, same pictures, same shot structure — narration rewritten in `code` as a person would SAY it
    (not a word-for-word translation). Returns a new script dict; visual prompts are untouched."""
    name, tone, needs_roman = LANGS[code]
    shots_in = [[sh["narration"] for sh in s["shots"]] for s in script["scenes"]]
    roman_rule = ('For every shot also give "roman": the same words written in Latin letters exactly as they '
                  'sound, ONE roman word per spoken word, same word count as "narration" (no punctuation).'
                  if needs_roman else "")
    prompt = f"""You adapt a YouTube Shorts narration into {name} — {tone or name}.
Do NOT translate word for word: say it the way a native speaker would tell a friend. Keep the same facts,
the same order, the same hook, same tone and rhythm (short and long sentences mixed).

Rules
- Keep exactly the same scenes and the same number of shots per scene; shot N still says what shot N says.
- Spoken language: contractions, no stiff written style. A voice will read it, so write numbers as words,
  no symbols, no parentheses, no dashes, no ellipses, no exclamation marks.
- End sentences with a full stop "." or "?" (use "." even for Hindi, not the danda).
- Each shot 1-2 sentences, similar length to the original.
- "title": under 60 characters in {name}, curious and honest, no all caps.
{roman_rule}

English script (shots per scene):
{json.dumps({"title": script["title"], "scenes": shots_in}, ensure_ascii=False, indent=1)}

Return ONLY JSON: {{"title": "...", "scenes": [[{{"narration": "...", "roman": "..."}}, ...], ...]}}
(one inner list per scene, one object per shot, same counts as the input)"""
    with spin(f"Adapting the script to {name}..."):
        res = client.chat.completions.create(
            model=GPT_MODEL, messages=[{"role": "user", "content": prompt}],
            reasoning_effort="none", temperature=0.5, response_format={"type": "json_object"})
    u = res.usage
    track(f"gpt {name}", (getattr(u, "prompt_tokens", 0) / 1e6 * GPT_IN_COST) +
                         (getattr(u, "completion_tokens", 0) / 1e6 * GPT_OUT_COST))
    data = json.loads(res.choices[0].message.content)
    scenes_out = data.get("scenes", [])
    if len(scenes_out) != len(script["scenes"]) or any(len(a) != len(b) for a, b in zip(scenes_out, shots_in)):
        fail(f"{name} adaptation changed the scene/shot structure — try again")

    new = dict(script)
    new["title"] = (data.get("title") or script["title"]).strip()
    new["lang"]  = code
    new["scenes"] = []
    for s, outs in zip(script["scenes"], scenes_out):
        shots = []
        for sh, o in zip(s["shots"], outs):
            shots.append({"narration": (o.get("narration") or sh["narration"]).strip(),
                          "visual_prompt": sh["visual_prompt"], "roman": (o.get("roman") or "").strip()})
        s2 = dict(s)
        s2["shots"]     = shots
        s2["narration"] = " ".join(x["narration"] for x in shots)
        s2["roman"]     = " ".join(x["roman"] for x in shots) if needs_roman else None
        new["scenes"].append(s2)
    ok(f"{name} script ready: \"{new['title']}\"")
    return new
