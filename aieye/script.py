import re, json
from .config import CFG, KID_RULES, GPT_IN_COST, GPT_MODEL, GPT_OUT_COST, MAX_SHOTS, MIN_SHOT_WORDS, N_SCENES
from .costs import track
from .store import load_ckpt, save_ckpt
from .ui import fail, log, ok, section, skip, spin, warn

# STEP 1 — SCRIPT

def build_visual_prompt_style():
    """Return style instructions based on user's image style choice."""
    if CFG["image_style"] == "realistic":
        return (
            "Style: photorealistic, cinematic, dramatic lighting, razor-sharp high detail. "
            "Image-focused: ONE hero subject, shot as an extreme close-up or tight macro so it fills most of the frame, "
            "big, bold and instantly clear on a phone screen. Shallow depth of field, blurred simple background. "
            "No text overlays needed — pure visual storytelling."
        )
    elif CFG["image_style"] == "illustrated":
        return (
            "Style: bold graphic illustration, vivid saturated colors, strong outlines. "
            "Comic-book meets science poster aesthetic. "
            "May include short labels or title text if it adds clarity."
        )
    else:  # representational
        return (
            "Style: scientific textbook diagram, NASA explainer infographic. "
            "Dark navy background (#0a0a1a), bold accent colors, high contrast. "
            "MUST include: labeled arrows (thick), callout boxes, annotated parts. "
            "All label text: short (1-4 words), large, bold, clearly legible. "
            "Name every element — what shape, what color, what label, where arrows point."
        )

BANNED = [
    "delve", "tapestry", "testament", "realm", "unveil", "unleash", "game-changer", "game changer",
    "mind-blowing", "little-known", "forever", "shocking", "stunning", "let that sink in",
    "buckle up", "imagine a world", "iconic", "numerous", "it's not just", "not just a",
    "in conclusion", "reminds us", "remind us",
]

CONTRACTIONS = [
    (r"\bit is\b", "it's"), (r"\bthat is\b", "that's"), (r"\bthere is\b", "there's"),
    (r"\bwhat is\b", "what's"), (r"\bhere is\b", "here's"), (r"\bwho is\b", "who's"),
    (r"\bdoes not\b", "doesn't"), (r"\bdo not\b", "don't"), (r"\bdid not\b", "didn't"),
    (r"\bis not\b", "isn't"), (r"\bare not\b", "aren't"), (r"\bwas not\b", "wasn't"),
    (r"\bcannot\b", "can't"), (r"\bcan not\b", "can't"), (r"\bwill not\b", "won't"),
    (r"\bthey are\b", "they're"), (r"\bwe are\b", "we're"), (r"\byou are\b", "you're"),
    (r"\bit has\b(?= (?:been|a|an|the|no)\b)", "it's"),
]

def contract(text):
    """Turn stiff 'It is' / 'does not' into how people actually talk (keeps capitalisation)."""
    for pat, rep in CONTRACTIONS:
        text = re.sub(pat, lambda m: rep.capitalize() if m.group(0)[0].isupper() else rep,
                      text, flags=re.IGNORECASE)
    return text

def merge_shots(shots):
    """Keep at most MAX_SHOTS shots and none shorter than MIN_SHOT_WORDS (too-short shots become a flicker).
    Merged narration is never dropped: it joins the neighbouring shot."""
    out = []
    for sh in shots:
        if out and len(sh["narration"].split()) < MIN_SHOT_WORDS:
            out[-1] = {"narration": out[-1]["narration"] + " " + sh["narration"], "visual_prompt": out[-1]["visual_prompt"]}
        else:
            out.append(dict(sh))
    if len(out) > 1 and len(out[0]["narration"].split()) < MIN_SHOT_WORDS:
        out[1] = {"narration": out[0]["narration"] + " " + out[1]["narration"], "visual_prompt": out[0]["visual_prompt"]}
        out.pop(0)
    while len(out) > MAX_SHOTS:
        last = out.pop()
        out[-1] = {"narration": out[-1]["narration"] + " " + last["narration"], "visual_prompt": out[-1]["visual_prompt"]}
    return out

def scan_script(data):
    """Warn about AI-sounding phrases and length problems (does not modify the script)."""
    total = 0
    for s in data["scenes"]:
        text = s["narration"].lower()
        words = len(text.split())
        total += words
        hits = [b for b in BANNED if b in text]
        if hits:
            warn(f"Scene {s['scene']}: AI-sounding phrase(s): {', '.join(hits)}")
        if any(ch in s["narration"] for ch in "—–…!%&()"):
            warn(f"Scene {s['scene']}: contains characters TTS reads badly (— … ! % & parentheses)")
        sents = [x for x in re.split(r"(?<=[.?])\s+", s["narration"].strip()) if x]
        long_s = [x for x in sents if len(x.split()) > 20]
        if long_s:
            warn(f"Scene {s['scene']}: sentence over 20 words (kid level): \"{long_s[0][:50]}...\"")
        hard = sorted({w for w in re.findall(r"[a-z]+", text) if len(w) >= 12})
        if hard:
            warn(f"Scene {s['scene']}: long word(s) a kid may not know: {', '.join(hard)}")
        if not 12 <= words <= 34:
            warn(f"Scene {s['scene']}: {words} words (target 14-30)")
    if not 100 <= total <= 150:
        warn(f"Total narration {total} words (target 110-135)")
    return total

def generate_script(client, topic, out_dir):
    section("STEP 1  —  Script Generation  (3-pass agent)")

    cached = load_ckpt(out_dir, "script")
    if cached:
        skip(f"Script: \"{cached['title']}\"")
        return cached

    log(f"Topic: {topic['title']}", indent=1)
    style_instructions = build_visual_prompt_style()

    # ── PASS 1: Research, fact safety, through-line ──────
    log("Pass 1/3 — Researching facts...", "dim", indent=1)
    research_prompt = f"""You are a careful fact-checker who is also a great science storyteller.
Topic: "{topic['title']}"
{('Angle to take (keep the facts on this): ' + topic['hook']) if topic.get('hook') else ''}

Find the {N_SCENES} most surprising facts about this topic, and one through-line that ties them together.

Rules:
- Include a fact ONLY if you are highly confident it is true and widely documented.
  If you're unsure of an exact number, describe it loosely ("roughly", "more than", "about")
  or drop the fact. Never invent statistics, dates, studies or quotes.
- Prefer facts a 10-year-old could repeat to a friend at lunch. No fact may involve death, injury, violence or disaster.
- Prefer physical, everyday comparisons (a football field, a thumbnail, a car) over abstractions.
- Skip anything that's just a scary headline. We want wonder, not doom.

For each fact give:
1. The fact, stated precisely
2. Why it violates intuition
3. The best everyday comparison
4. Confidence: high or medium

Then write:
THROUGH-LINE: one question or tension the Short can open in its first line and pay off in its last.

{KID_RULES}

Plain text, numbered 1-{N_SCENES}. No JSON."""

    with spin("Researching facts..."):
        research_res = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": research_prompt}],
            reasoning_effort="low",   # reasoning models only accept default temperature
        )
    research     = research_res.choices[0].message.content
    usage        = research_res.usage
    in_tok       = getattr(usage, "prompt_tokens",     0) if usage else 0
    out_tok      = getattr(usage, "completion_tokens", 0) if usage else 0
    track("gpt research", (in_tok/1e6*GPT_IN_COST)+(out_tok/1e6*GPT_OUT_COST))
    ok("Facts researched")

    # ── PASS 2: Write the script draft ───────────────────
    log("Pass 2/3 — Writing script draft...", "dim", indent=1)
    draft_prompt = f"""You are writing the voiceover for a YouTube Short, the way a smart, funny friend
would tell it out loud. A text-to-speech voice will read it, so write for the EAR, not the eye.

Topic: "{topic['title']}"

Researched facts and through-line:
{research}

STRUCTURE ({N_SCENES} scenes)
- Scene 1 (hook): open with the most surprising fact, and open the through-line as a question or
  tension. No greeting, no "did you know", no "welcome".
- Scenes 2-{N_SCENES-1}: one fact each. Each scene must pick up from the one before it with a natural
  hand-off, and never reuse the same hand-off ("Here's the weird part." / "But it gets stranger." /
  "So why doesn't it fall?").
- Scene {N_SCENES}: pay off the through-line with a specific image or a small twist.
  No moral, no summary, no "this reminds us".

{KID_RULES}

SOUND HUMAN
- Talk to one person. Use "you" and contractions (it's, doesn't, that's, can't).
- Vary rhythm: include a very short sentence (2-5 words) and a longer one (up to 18 words, never more than 20).
  Don't give every sentence the same shape.
- 14-30 words per scene (all its shots together), about 110-135 words in total.
- Concrete beats abstract: a number plus a comparison beats an adjective.
- Sentence fragments are fine when a person would say them ("Not even close.").
- No headline voice. Not "Toxic oceans threaten life." Say what happens the way you'd tell a friend.
- Never use: delve, tapestry, testament, realm, unveil, unleash, game-changer, mind-blowing,
  little-known, forever, shocking, stunning, iconic, numerous, "let that sink in", "buckle up",
  "imagine a world", "it's not just X, it's Y", or a tidy list of three.

MAKE IT SPEAKABLE (the voice reads exactly what you write)
- Write numbers the way they're said: "sixty percent", "twenty sixty", "five thousand years",
  "C O two". No symbols (% & °), no parentheses, no abbreviations, no em dashes.
- Use commas and periods for rhythm; a comma is a small breath.
  No ellipses and no exclamation marks; the voice overacts on them.

STYLE REFERENCE ONLY (never reuse these facts)
  Headline voice: "Cacao flowers sprout directly from the trunk. Tiny midges pollinate them."
  Spoken voice:   "Cacao flowers don't grow on branches. They grow straight out of the trunk. And the only thing that pollinates them is a midge smaller than a grain of rice."
  Headline voice: "Toxic oceans threaten life. Coral reefs suffocate under rising CO2 levels."
  Spoken voice:   "The ocean is getting more acidic, and coral skeletons are starting to dissolve."

SHOTS (a new picture every few seconds)
- Split every scene into 2-{MAX_SHOTS} shots, only at sentence boundaries. Each shot has its own "narration"
  (1-2 sentences, about 6-16 words) and its own "visual_prompt" showing what THAT part says.
  The scene's spoken narration is simply its shots' narrations read in order; there is no separate scene text.
- Vary the framing between shots (wide establishing view, then close-up, then a detail, comparison or
  consequence) while keeping the same subject, setting and look. Shots 2-{MAX_SHOTS} are generated from
  shot 1 as a reference image, so write them as "the same scene, now ..." (what changes: angle, distance, detail).
- Each shot must be a picture that could be held on screen for 2-4 seconds: one clear subject, no clutter.

DELIVERY: for each scene write a "delivery" note, 4-12 words, telling the voice actor how to
perform THAT scene (for example "quiet and intrigued, slow down on the last word" or
"quicker, a little amused"). Vary them; at most one scene may be "excited".

VISUALS
{style_instructions}
- "visual_style": one short paragraph describing the look ALL {N_SCENES} images share (palette, rendering
  style, any recurring motif), so the set feels like one video.
- Each "visual_prompt" describes only what's specific to that shot. Be literal: name every element,
  label, arrow, color and position.
- Zoomed in: make the subject LARGE. It fills at least 70% of the frame width and the upper two-thirds of the
  height (close-up, macro or tight crop; never a small subject in a big empty scene). Wide establishing shots
  still frame the hero subject big and clear.
- Layout: keep the bottom third free of key details (soft, dark or blurred continuation of the scene, no text)
  because captions go there.
  Keep any label inside the central 80% of the width.

TITLE: under 60 characters, curious and honest. No "You Won't Believe", no all caps.

Return ONLY valid JSON:
{{
  "title": "...",
  "visual_style": "...",
  "scenes": [
    {{"scene": 1, "delivery": "...", "shots": [
        {{"narration": "...", "visual_prompt": "..."}},
        {{"narration": "...", "visual_prompt": "..."}}
    ]}},
    ... one object per scene, {N_SCENES} in total, each with 2-{MAX_SHOTS} shots ...
  ]
}}"""

    with spin("Writing first draft..."):
        draft_res = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": draft_prompt}],
            reasoning_effort="none",
            temperature=0.85,
            response_format={"type": "json_object"},
        )
    draft_data = json.loads(draft_res.choices[0].message.content)
    usage      = draft_res.usage
    in_tok     = getattr(usage, "prompt_tokens",     0) if usage else 0
    out_tok    = getattr(usage, "completion_tokens", 0) if usage else 0
    track("gpt draft", (in_tok/1e6*GPT_IN_COST)+(out_tok/1e6*GPT_OUT_COST))
    ok("Draft written")

    # ── PASS 3: Read-aloud edit ──────────────────────────
    log("Pass 3/3 — Read-aloud edit...", "dim", indent=1)
    critique_prompt = f"""You are a veteran voiceover director. A text-to-speech voice will read this
script aloud, and it must sound like a real person telling a friend something amazing.

Draft:
{json.dumps(draft_data, indent=2)}

{KID_RULES}

Read every narration aloud in your head and fix:
0. Kid level: any word a fourth grader would not know is replaced with a simpler one (or explained at once);
   any sentence over 20 words is split; anything scary, violent or about death/injury is removed.
1. Written, not spoken: headline fragments, noun-stack openers, formal words (threaten, surge,
   numerous, iconic), passive voice. Rewrite the way a person would actually say it.
2. AI tells: banned words (delve, tapestry, unveil, unleash, mind-blowing, forever, shocking, stunning),
   tidy lists of three, "not just X but Y", every scene the same length or shape,
   a moral or summary in the last scene.
3. Flow: does each scene pick up from the previous one with a varied hand-off? Does the last scene
   pay off the tension opened in scene 1?
4. Truth: any statistic, date or claim you are not sure about becomes softer ("roughly", "more than")
   or is replaced with something you're sure of. Never add new unverified numbers.
5. Speakability: numbers written as words; no symbols, dashes, parentheses, ellipses or exclamation
   marks; reword anything hard to pronounce.
6. Length: 14-30 words per scene, 110-135 total.
7. Delivery notes: concrete, varied, 4-12 words each.
8. Visuals: keep visual_style and visual_prompts, but make sure the bottom third of every image is
   plain and uncluttered and the subject is upper-middle. Make prompts more literal where vague.
9. Shots: every scene keeps 2-{MAX_SHOTS} shots split only at sentence boundaries, each shot 1-2 sentences.
   Shots 2-{MAX_SHOTS} must read as "the same scene, now ..." (new angle, distance or detail, same subject and look).
   Do not add a separate scene-level narration; the shots' narrations are the script.

Return ONLY the improved script as valid JSON, same structure (title, visual_style, scenes with
scene, delivery, shots[narration, visual_prompt])."""

    with spin("Editing for spoken delivery..."):
        final_res = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": critique_prompt}],
            reasoning_effort="medium",
            response_format={"type": "json_object"},
        )
    data    = json.loads(final_res.choices[0].message.content)
    usage   = final_res.usage
    in_tok  = getattr(usage, "prompt_tokens",     0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    track("gpt rewrite", (in_tok/1e6*GPT_IN_COST)+(out_tok/1e6*GPT_OUT_COST))

    # ── Validate ─────────────────────────────────────────
    if len(data.get("scenes", [])) != N_SCENES:
        fail(f"Expected {N_SCENES} scenes, got {len(data.get('scenes',[]))}")
    data["visual_style"] = (data.get("visual_style") or "").strip()
    for s in data["scenes"]:
        shots = s.get("shots") or [{"narration": s.get("narration", ""), "visual_prompt": s.get("visual_prompt", "")}]
        shots = [{"narration": contract((sh.get("narration") or "").strip()),
                  "visual_prompt": (sh.get("visual_prompt") or "").strip()}
                 for sh in shots if (sh.get("narration") or "").strip()]
        if not shots:
            fail(f"Scene {s.get('scene')}: no narration in the script")
        shots = merge_shots(shots)
        s["shots"]         = shots
        s["narration"]     = " ".join(sh["narration"] for sh in shots)     # what the voice reads for the whole scene
        s["visual_prompt"] = shots[0]["visual_prompt"]
        s["delivery"]      = (s.get("delivery") or "").strip()

    total_words = scan_script(data)
    n_shots = sum(len(s["shots"]) for s in data["scenes"])
    ok(f"Script ready: \"{data['title']}\"  ({total_words} words, {n_shots} shots)")
    for s in data["scenes"]:
        log(f"Scene {s['scene']} [{len(s['shots'])} shots]: {s['narration'][:62]}", indent=2)

    save_ckpt(out_dir, "script", data)
    return data

