"""Script lab: a reasoning-model pipeline that writes a COMPLETE, kid-level, video-ready script.

  1 RESEARCH   (writer model)  verified facts -> a story spine: ONE question the film opens and the answer it must SHOW
  2 DRAFT      (writer model)  a shot list: narration + what we see + camera + speed, with start/end states per scene
  3 CRITIC     (critic model)  an independent, stronger model scores it against a strict rubric and lists must-fix items
  4 REVISE     (writer model)  fixes every blocker/major item; the critic re-checks; best version wins (max MAX_ROUNDS)
  + plain code checks (length, word level, speeds, required fields) run before every critique

`aieye run -script "topic" [-notes facts.txt]` runs only this (a few dollars at most, no video). The result is saved as
script.json (the same file `aieye run -film -resume <folder>` turns into the video), script.md (easy to read) and
script_report.json (scores and cost).
"""
import os, json, re, time
from datetime import datetime

from . import costs
from .config import DATA_DIR, KID_RULES
from .costs import track
from .script import BANNED, contract
from .ui import c, fail, log, ok, section, spin, warn

FILM_DIR     = DATA_DIR / "experiments" / "film"
WRITER_MODEL = "gpt-6.1-sol"      # research, draft, revisions: strong reasoning at $2 / $10 per 1M tokens
CRITIC_MODEL = os.getenv("AIEYE_CRITIC", "gpt-6.1-sol")   # judge; was gpt-6-astra ($10/$50 per 1M) which made each script ~$1. Set AIEYE_CRITIC=gpt-6-astra for the top tier
EFFORT       = "high"
PRICES       = {"gpt-6.1-sol": (2.0, 10.0), "gpt-6-sol": (2.0, 10.0), "gpt-6-astra": (10.0, 50.0),
                "gpt-6.1-terra": (1.0, 5.0), "gpt-6-luna": (0.10, 0.50)}
MAX_ROUNDS   = 1                  # critique+revise rounds after the first draft
PASS_SCORE   = 8                  # every rubric score must reach this (out of 10), with no blocker or major issue
WPS          = 2.5                # narration words per second (measured on the pipeline's voice)
SPEEDS       = (0.5, 0.75, 1.0)
SCORES       = ["completeness", "story_chain", "facts", "kid_level", "narration_visual_match", "video_feasibility",
                "continuity", "pacing", "hook_and_loop", "no_spoilers", "speakability_length", "safety"]


# ── model calls ──────────────────────────────────────────────────────────────────────────────────────────────
def _chat(client, model, prompt, label):
    """One JSON reasoning call with cost tracking. Falls back to the writer model if the critic is unavailable."""
    for m in (model, WRITER_MODEL) if model != WRITER_MODEL else (model,):
        try:
            t = time.time()
            res = client.chat.completions.create(model=m, reasoning_effort=EFFORT, response_format={"type": "json_object"},
                                                 messages=[{"role": "user", "content": prompt}])
            u = res.usage
            pin, pout = PRICES.get(m, (2.0, 10.0))
            cost = getattr(u, "prompt_tokens", 0) / 1e6 * pin + getattr(u, "completion_tokens", 0) / 1e6 * pout
            track(f"{label} ({m}, {time.time() - t:.0f}s)", cost)
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            if m == WRITER_MODEL or "insufficient_quota" in str(e):
                raise
            warn(f"{m} unavailable for {label} ({str(e)[:70]}); using {WRITER_MODEL}")
    raise RuntimeError("unreachable")


# ── stage 1: research brief ──────────────────────────────────────────────────────────────────────────────────
RESEARCH = """You are a science researcher and a documentary story editor. A 30-40 second vertical YouTube Short will EXPLAIN
this to curious kids aged 8-12:

TOPIC: "@@TOPIC@@"

@@NOTES@@
FACT RULES (strict)
- Use only facts that are VERIFIED (in the notes above) or that you are highly confident are true and widely documented.
- Anything uncertain gets confidence "hedge" and must be worded "scientists think" or "may". No invented numbers,
  percentages, depths, distances, studies or quotes. When in doubt leave it out.

Your job is the STORY SPINE, the idea the whole film hangs on:
- ONE question the film opens in its first line and ANSWERS ON SCREEN by its end. The answer must be something a viewer
  can SEE happen, not only hear (for a hunting story, the film must show the animal actually finding what it hunts).
- The mechanism as a chain of causes, in order, each step making the next one necessary ("but" / "therefore").
- Anything hidden (underground, inside the body, too small or too fast) needs a visible way to show it: a cutaway or
  cross-section. List these as set pieces.
- A cast of at most 3 characters, each with a concrete, repeatable look (species, size, colour, markings) so an AI video
  model draws them the same way every time.

- SECRET: if the story is a hunt, a search or a mystery, name the hidden target (its cast id) and the words that would
  give it away on screen (its names, its hiding place, its tunnel). The film keeps it UNSEEN until the reveal. The ending
  shows the catch or discovery PLAINLY and gently (nothing graphic).

Return ONLY JSON:
{"question": "...", "answer": "one sentence", "payoff_image": "the final image that visibly answers the question",
 "mechanism": [{"step": "...", "fact": "...", "confidence": "verified|high|hedge", "source": "notes|general knowledge"}],
 "cast": [{"id": "lowercase one word", "role": "...", "look": "30-50 words of concrete visual detail"}],
 "setting": "one paragraph, 40-70 words: ONE location, weather, time of day, light direction, colour grade; no action",
 "secret": {"id": "cast id of the hidden target, or empty if none", "words": ["names and hiding-place words that would give it away"]},
 "set_pieces": ["visual moments that make the mechanism visible, including cutaways"],
 "avoid": ["claims or images to keep out"]}"""


# ── stage 2: draft ───────────────────────────────────────────────────────────────────────────────────────────
DRAFT = """You are a wildlife-documentary DIRECTOR and screenwriter. Write the complete script for a 30-40 second vertical
YouTube Short for curious kids aged 8-12, from this research brief. Every scene will be made by a text-to-video AI model
(one continuous shot per scene, no start image), narrated by a text-to-speech voice, and captioned word by word.

BRIEF (trusted)
@@BRIEF@@

@@KID_RULES@@

THE FILM MUST BE COMPLETE
- Scene 1 opens the brief's question in its first words (a question or a surprise). The PAYOFF scene must show the CATCH or
  DISCOVERY plainly (the hunter holding what it found, gently, both clearly in frame). A viewer who sees only the pictures must understand what happened and see how it ended.
- Chain the scenes with cause and effect ("but", "so", "then"): each scene is made necessary by the one before.
- Every narration line must be TRUE and SHOWN. The picture proves the words (field "proof" names the visible evidence).
  Facts about hidden things are paired with a cutaway that shows them.
- Pay off about 2-3 seconds before the end, then close with a short line that echoes the opening so the Short loops.
  No sign-off, joke or filler line; every sentence teaches or advances the story.

NO SPOILERS (strict)
- The brief's secret must be UNSEEN in every picture until the reveal, which is the payoff scene. Before it show only
  clues: the hunter's behaviour, the untouched surface, small signs. Never the secret itself, its hiding place, its
  position, a cutaway of it, or anything drawn that points at it. The narration may name it; the pictures may not show it.
- Hidden mechanisms are explained by the narration over pictures that give nothing away (the hunter listening, ears
  turning, snow undisturbed).
- THE CATCH: the payoff shows it gently: the hunter lifts its head out of the opened ground holding the prey softly in its
  mouth, both clearly visible. No blood, no injury, no struggle, no close-up of suffering.

STRUCTURE: 6 scenes (7 only if the story truly needs it). Beats, in order: hook, build, build, turn, action, payoff.
PACE LIKE A FILM
- GIVE THE PAYOFF ROOM: the action and payoff scenes together carry at least 40% of the narration words and the film's
  longest runtime; the hook, build and turn scenes together stay under 55%. Never spend most of the film on a creature
  standing still: each build scene must show a NEW visible step that moves the story forward.
- Calm facts breathe at normal speed (speed 1.0). The single PEAK ACTION scene is slow motion (speed 0.5) so kids can see
  it; the "turn" before it may be 0.75. No other slow motion. Energy rises toward the action, then releases.
- Vary the camera: wide, medium, low angle, tracking, cutaway. Never two scenes in a row with the same framing.
- Keep subjects BIG (at least a third of the frame height). No extreme close-ups of faces (AI video warps them).

MAKE IT FILMABLE FOR TEXT-TO-VIDEO
- "action": 25-45 words, present tense, ONE continuous motion that fits in the scene's seconds: body position, the exact
  movement, what the snow or surroundings do, where the subject sits in the frame. At most two characters per shot.
- "start_state" / "end_state": one sentence each describing the first and last frame. The end_state of a scene must
  match the start_state of the next, or be an intentional cutaway. This is what makes the cuts feel clean.
- "characters": ids from the brief's cast that are on screen. No text, signs, captions or people in the picture.
- KEEP PRODUCTION TALK OUT. "action", "camera", "start_state" and "end_state" go straight to the video model, so they
  describe ONLY what a camera sees in ONE generated shot. Never mention captions, caption bands, overlays, diagrams
  added later, compositing, editing, cuts, post-production, sound design, reference images, plates, approvals,
  timelines, phone size or planning. If an idea cannot be filmed as one AI-generated shot, change the idea (show a hidden
  tunnel with a clean cross-section shot that is itself a normal picture, not a diagram added later).
- "camera": at most 12 words, lens/angle/movement only, for example "low tracking shot, slow push-in".
- CINEMATIC MOVEMENT: at least 4 scenes have deliberate camera movement (push-in, tracking, tilt, pull-back, drift); at
  most 2 scenes are locked-off, and never two locked-off scenes in a row. Calm does not mean static.
- The listening beat is a MEDIUM shot with the head and ears big enough to read on a phone (the turn of the head is
  the picture), not a full-body or wide shot.

SAFETY: gentle nature-documentary tone. Show the behaviour, never blood, injury, suffering or a frightening close-up.
Cut away or end the shot at the moment of contact.

NARRATION: 10-22 words per scene, 75-100 words in total (about 30-40 seconds), speakable (numbers as words, no symbols,
dashes, parentheses or exclamation marks), contractions, varied sentence length, none over 18 words.

Return ONLY JSON:
{"title": "under 60 characters, curious and honest", "hook_question": "...", "answer_line": "...", "reveal_scene": 6,
 "scenes": [{"scene": 1, "beat": "hook|build|turn|action|payoff", "cause_link": "opens|but|so|then|answers",
   "narration": "...", "delivery": "4-12 words telling the narrator how to perform it", "action": "...",
   "start_state": "...", "end_state": "...", "camera": "max 12 words", "speed": 1.0, "energy": "low|medium|high",
   "characters": ["fox"], "proof": "the visible evidence for the narration"}]}"""


# ── stage 3: critic ──────────────────────────────────────────────────────────────────────────────────────────
CRITIC = """You are the strictest editor in a documentary studio. Judge this script for a vertical YouTube Short for kids aged 8-12
that will be made with a text-to-video AI model (one continuous shot per scene), a text-to-speech voice and word-by-word
captions. Be specific and demanding; praise nothing that does not earn it.

RESEARCH BRIEF (trusted facts)
@@BRIEF@@

SCRIPT
@@SCRIPT@@

MECHANICAL REPORT (measured by code)
@@MECH@@

Score each 1-10 (8 = good enough to film, 10 = flawless):
 completeness            Is the opening question answered ON SCREEN by the end? Would someone who only watched the
                         pictures understand what happened, including the key discovery? Is anything left hanging?
 story_chain             Is each scene made necessary by the one before (but / so / then)? Any filler or jump?
 facts                   Every claim true, hedged where uncertain, nothing outside the brief, no numbers or percentages?
 kid_level               Words and sentences a fourth grader gets at once? Tone playful, never babyish or scary?
 narration_visual_match  Does each line's "proof" truly appear in that scene's action? Any line the picture cannot show?
 video_feasibility       Can a text-to-video model do each scene as ONE continuous 4-8 second shot (clips come in 4, 6 or 8 s)?
                         A whole action (crouch, leap, headfirst dive, coming up with the prey) is best ONE shot, never split across cuts.
                         Underground cutaways and cross-sections do NOT work; fail them (use above-ground views only). Flag anything that needs
                         a cut, tiny details, two characters interacting in a complex way, faces up close, or text.
                         ALSO fail any production or post-production instruction inside action, camera or states
                         (captions, overlays, diagrams, compositing, editing, sound design, approvals, references):
                         those go straight to the video model and must be only what a camera sees.
 continuity              Same cast and setting? Does each end_state flow into the next start_state (or an intentional cutaway)?
 pacing                  Energy curve, one slow-motion peak only, varied camera, scene lengths that fit the words?
                         At least 4 scenes with camera movement and at most 2 locked-off? A film of locked shots is dull.
 hook_and_loop           Does the first line stop a scroll? Is the payoff early enough, and does the last line echo the opening?
 no_spoilers            Is the secret UNSEEN in every picture (action, start/end states, characters) before the payoff? Does the payoff
                         show the catch clearly and gently? Any cutaway, diagram or clue that gives the answer away early = 3 or less.
 speakability_length     Easy to speak, 75-100 words, each scene 10-22 words, no tongue-twisters?
 safety                  Gentle for kids, nothing graphic, no blood or suffering?

Then list MUST-FIX items. severity: "blocker" (film would be wrong or incomplete), "major" (clearly weak), "minor"
(polish). Each item names the scene (0 = whole script), the problem, and a concrete fix.

Return ONLY JSON:
{"scores": {"completeness": 0, "story_chain": 0, "facts": 0, "kid_level": 0, "narration_visual_match": 0,
            "video_feasibility": 0, "continuity": 0, "pacing": 0, "hook_and_loop": 0, "no_spoilers": 0, "speakability_length": 0, "safety": 0},
 "must_fix": [{"scene": 0, "severity": "blocker|major|minor", "problem": "...", "fix": "..."}],
 "strengths": ["..."], "verdict": "pass|revise"}"""


# ── stage 4: revise ──────────────────────────────────────────────────────────────────────────────────────────
REVISE = """You are the screenwriter. An editor reviewed your script. Produce the improved FULL script.

BRIEF (trusted)
@@BRIEF@@

CURRENT SCRIPT
@@SCRIPT@@

EDITOR'S SCORES AND MUST-FIX LIST
@@REVIEW@@

MECHANICAL REPORT
@@MECH@@

Rules: fix EVERY blocker and major item; fix minor items when it costs nothing; do not weaken anything that scored 9 or
10. Keep the same JSON structure and every field (scene, beat, cause_link, narration, delivery, action, start_state,
end_state, camera, speed, energy, characters, proof), plus title, hook_question, answer_line. Keep 6 scenes (7 only if
the editor demanded it), 75-100 narration words, exactly one slow-motion peak scene. @@KID_RULES@@
Also: keep the secret UNSEEN in every picture before the payoff scene, and make the payoff show the catch gently.
Also: remove ALL production talk from action, camera, start_state and end_state (captions, overlays, compositing,
editing, post-production, sound design, approvals, references, timelines); keep camera to 12 words and action to
25-55 words; keep at least 4 scenes with camera movement and at most 2 locked-off scenes.
Return ONLY the improved script JSON."""


def _fill(template, **kw):
    for k, v in kw.items():
        template = template.replace(f"@@{k}@@", v)
    return template


# ── mechanical checks ────────────────────────────────────────────────────────────────────────────────────────
LEAK   = re.compile(r"\b(captions?|composit(?:e|es|ed|ing)|post[- ]?production|overlays?|diagrams?|editing|edits?|cut to|approv\w*|"
                    r"reference[- ]images?|references?|plates?|layers?|sound\w*|audio|timeline|planned duration|previsuali\w*|"
                    r"phone size|platform|playback|in post|arcs?)\b", re.I)
STATIC = re.compile(r"\b(locked|static|fixed|tripod|no camera movement|stationary)\b", re.I)
REQUIRED = ("scene", "beat", "narration", "delivery", "action", "start_state", "end_state", "camera", "speed", "energy",
            "characters", "proof")

def normalise(script, brief):
    """Clean the model's output in place so later code can trust it."""
    sc = script.get("scenes") or []
    cast_ids = {x["id"] for x in brief.get("cast", [])}
    for i, s in enumerate(sc, 1):
        s["scene"] = i
        s["narration"] = contract(" ".join(str(s.get("narration", "")).split()))
        s["action"] = re.sub(r"\s*No (cuts|text)[^.]*\.", "", str(s.get("action", ""))).strip()
        try:
            sp = float(s.get("speed", 1.0))
        except (TypeError, ValueError):
            sp = 1.0
        s["speed"] = min(SPEEDS, key=lambda x: abs(x - sp))
        s["characters"] = [x for x in (s.get("characters") or []) if x in cast_ids] or sorted(cast_ids)[:1]
        s["shots"] = [{"narration": s["narration"], "visual_prompt": s["action"]}]      # compatible with the main pipeline
    return script

def mechanical(script, brief=None):
    """(issues, stats). Issues are measurable problems; they are passed to the critic and to the reviser."""
    sc, issues = script.get("scenes") or [], []
    words = [len(s.get("narration", "").split()) for s in sc]
    total = sum(words)
    if not 5 <= len(sc) <= 7:
        issues.append(f"{len(sc)} scenes (want 6, at most 7)")
    if not 70 <= total <= 105:
        issues.append(f"narration is {total} words (want 75-100, about 30-40 s)")
    for s, w in zip(sc, words):
        if not 9 <= w <= 24:
            issues.append(f"scene {s['scene']}: {w} words (want 10-22)")
        for sent in re.split(r"(?<=[.?])\s+", s["narration"]):
            if len(sent.split()) > 20:
                issues.append(f"scene {s['scene']}: a sentence is over 20 words")
        low = s["narration"].lower()
        hits = [b for b in BANNED if b in low]
        if hits:
            issues.append(f"scene {s['scene']}: AI-sounding words: {', '.join(hits)}")
        if any(ch in s["narration"] for ch in "—–…!%&()"):
            issues.append(f"scene {s['scene']}: symbols the voice reads badly")
        if re.search(r"\d", s["narration"]):
            issues.append(f"scene {s['scene']}: digits in narration (write numbers as words)")
        longw = sorted({w_ for w_ in re.findall(r"[a-z]+", low) if len(w_) >= 12})
        if longw:
            issues.append(f"scene {s['scene']}: long words for kids: {', '.join(longw)}")
        for f in REQUIRED:
            if not s.get(f):
                issues.append(f"scene {s['scene']}: missing '{f}'")
        for fld in ("action", "camera", "start_state", "end_state"):
            leak = LEAK.findall(s.get(fld, ""))
            if leak:
                issues.append(f"scene {s['scene']}: production talk in {fld}: {', '.join(sorted(set(x.lower() for x in leak)))}")
        if len(s.get("camera", "").split()) > 14:
            issues.append(f"scene {s['scene']}: camera is {len(s['camera'].split())} words (max 12)")
        if len(s.get("action", "").split()) > 60:
            issues.append(f"scene {s['scene']}: action is {len(s['action'].split())} words (max 55)")
        if len(s.get("action", "").split()) < 18:
            issues.append(f"scene {s['scene']}: action is too thin ({len(s.get('action', '').split())} words)")
    locked = [s["scene"] for s in sc if STATIC.search(s.get("camera", ""))]
    if len(locked) > 2:
        issues.append(f"{len(locked)} locked-off scenes {locked} (max 2): the film would feel static")
    slow = [s["scene"] for s in sc if s.get("speed", 1) <= 0.5]
    if len(slow) != 1:
        issues.append(f"slow motion (0.5) on scenes {slow or 'none'}: want exactly one, the peak action")
    elif sc[slow[0] - 1].get("beat") != "action":
        issues.append(f"the slow-motion scene {slow[0]} is not the 'action' beat")
    wc = lambda x: len(x.get("narration", "").split())
    total_w = sum(wc(x) for x in sc) or 1
    end_w = sum(wc(x) for x in sc if x.get("beat") in ("action", "payoff"))
    if end_w / total_w < 0.38:
        issues.append(f"the action+payoff scenes carry only {round(100 * end_w / total_w)}% of the words (want 40%+): the ending is rushed")
    if sc and sc[0].get("beat") != "hook":
        issues.append("scene 1 is not the hook")
    if sc and sc[-1].get("beat") != "payoff":
        issues.append("the last scene is not the payoff")
    if sc and "?" not in sc[0].get("narration", "") and len(sc[0].get("narration", "").split()) > 14:
        issues.append("scene 1 does not open with a short question or surprise")
    sec = (brief or script.get("brief") or {}).get("secret") or {}
    sw = [w.lower() for w in (sec.get("words") or []) if w] + ([sec["id"].lower()] if sec.get("id") else [])
    reveal = int(script.get("reveal_scene") or len(sc) or 1)
    for s in sc:
        if s["scene"] < reveal and sw:
            vis = " ".join(str(s.get(f, "")) for f in ("action", "start_state", "end_state", "camera")).lower()
            hit = sorted({w for w in sw if re.search(r"\b" + re.escape(w) + r"s?\b", vis)})
            if hit or sec.get("id") in (s.get("characters") or []):
                issues.append(f"scene {s['scene']}: SPOILER before the reveal (scene {reveal}): shows {hit or [sec.get('id')]}")
    if sc and sec.get("id"):
        last = sc[-1]
        if sec["id"] not in (last.get("characters") or []) or not re.search(
                r"\b(hold|holds|holding|held|carr\w+|mouth|catch\w*|caught|grab\w*|lifts?)\b", last.get("action", ""), re.I):
            issues.append("the payoff does not show the catch (the hunter holding the secret, both in frame)")
    stats = {"words": total, "est_seconds": round(total / WPS, 1), "scenes": len(sc)}
    return issues, stats


def sanitize_for_video(script):
    """Last line of defence, in plain code: only what a camera sees may reach the video model. Drops sentences that talk
    about captions, editing, overlays, sound design and the like, and cuts a bloated camera note to its first clause."""
    def clean(text):
        sents = re.split(r"(?<=[.!?])\s+", str(text).strip())
        return " ".join(x for x in sents if not LEAK.search(x)).strip()
    sec = ((script.get("brief") or {}).get("secret")) or {}
    sw = [w.lower() for w in (sec.get("words") or []) if w] + ([sec["id"].lower()] if sec.get("id") else [])
    reveal = int(script.get("reveal_scene") or len(script["scenes"]))
    spoil = re.compile(r"\b(" + "|".join(re.escape(w) for w in sw) + r")s?\b", re.I) if sw else None
    for s in script["scenes"]:
        cam = str(s.get("camera", ""))
        if len(cam.split()) > 12:
            cam = re.sub(r"^\s*Vertical 9:16,?\s*", "", cam)
            cam = re.split(r"[;.]", cam)[0]
            cam = " ".join(cam.split()[:12])
        s["camera"] = cam.strip(" ,") or "medium shot"
        for f in ("action", "start_state", "end_state"):
            s[f] = clean(s.get(f, "")) or s.get(f, "")
            if spoil and s["scene"] < reveal:
                s[f] = " ".join(x for x in re.split(r"(?<=[.!?])\s+", s[f]) if not spoil.search(x)).strip()
    return script


def _worst(review):
    sc = review.get("scores") or {}
    return min((float(sc.get(k, 0)) for k in SCORES), default=0.0), sum(float(sc.get(k, 0)) for k in SCORES)

def _passes(review):
    low, _ = _worst(review)
    bad = [m for m in review.get("must_fix", []) if m.get("severity") in ("blocker", "major")]
    return low >= PASS_SCORE and not bad


# ── the pipeline ─────────────────────────────────────────────────────────────────────────────────────────────
def make_script(client, topic, notes_path=None, out_dir=None, resume=None):
    """Returns (script dict, folder). The script is saved as script.json / script.md / script_report.json."""
    loaded = None
    if resume:
        from pathlib import Path
        out_dir = Path(resume).expanduser()
        try:
            loaded = json.loads((out_dir / "script.json").read_text())
        except (OSError, ValueError):
            fail(f"Nothing to resume in {out_dir} (no readable script.json).")
        topic = loaded.get("topic") or topic
        if not loaded.get("brief"):
            fail("That script has no saved research brief, so it cannot be resumed.")
    if not (topic or "").strip():
        fail('No topic.  Usage: aieye run -script "how a fox hunts in the snow" [-notes facts.txt]')
    costs.reset()
    t0 = time.time()
    notes = ""
    if notes_path:
        try:
            notes = open(notes_path).read().strip()
        except OSError as e:
            fail(f"Cannot read the notes file: {e}")
    section(f"SCRIPT LAB  —  {WRITER_MODEL} writes, {CRITIC_MODEL} judges  (effort {EFFORT})")
    log(f"Topic: {topic}", "cyan", indent=1)
    log(f"Notes: {notes_path or 'none (the model uses only facts it is highly sure of)'}", "dim", indent=1)

    if loaded:
        brief = loaded["brief"]
        brief_txt = json.dumps(brief, indent=1, ensure_ascii=False)
        script = normalise(loaded, brief)
        (out_dir / "script_prev.json").write_text(json.dumps(loaded, indent=2, ensure_ascii=False))
        ok(f"Resuming \"{loaded.get('title')}\" with the stricter rules (previous version kept as script_prev.json)")
    else:
        with spin("1/4  Researching the story spine..."):
            brief = _chat(client, WRITER_MODEL, _fill(RESEARCH, TOPIC=topic,
                          NOTES=("VERIFIED NOTES (trust these; they were checked against sources):\n" + notes + "\n") if notes else ""),
                          "research")
        if not brief.get("question") or not brief.get("cast"):
            fail("The research step returned no question or cast. Run again.")
        ok(f"Question: {brief['question']}")
        log(f"Answer shown on screen: {brief.get('payoff_image', '')}", "dim", indent=1)
        brief_txt = json.dumps(brief, indent=1, ensure_ascii=False)

        with spin("2/4  Writing the first draft..."):
            script = normalise(_chat(client, WRITER_MODEL, _fill(DRAFT, BRIEF=brief_txt, KID_RULES=KID_RULES), "draft"), brief)

    history, best = [], None
    for rnd in range(1, MAX_ROUNDS + 2):
        issues, stats = mechanical(script, brief)
        mech = json.dumps({"stats": stats, "issues": issues or ["none"]}, indent=1)
        with spin(f"3/4  {CRITIC_MODEL} is judging the script (round {rnd})..."):
            review = _chat(client, CRITIC_MODEL, _fill(CRITIC, BRIEF=brief_txt, MECH=mech,
                           SCRIPT=json.dumps(script, indent=1, ensure_ascii=False)), f"critic r{rnd}")
        low, total = _worst(review)
        blockers = [m for m in review.get("must_fix", []) if m.get("severity") in ("blocker", "major")]
        log(f"Round {rnd}: lowest score {low:g}/10, total {total:g}/{10 * len(SCORES)}, "
            f"{len(blockers)} blocker/major, {len(issues)} mechanical", "cyan", indent=1)
        history.append({"round": rnd, "scores": review.get("scores"), "must_fix": review.get("must_fix"),
                        "mechanical": issues, "stats": stats})
        key = (not blockers and not issues, low, total, -len(issues))      # clean first, then lowest score, then total
        if best is None or key > best[5]:
            best = (json.loads(json.dumps(script)), low, total, issues, review, key)
        if _passes(review) and not issues:
            ok(f"Passed the editor in round {rnd}")
            break
        if rnd > MAX_ROUNDS:
            warn("Out of rounds; keeping the best version")
            break
        with spin(f"4/4  Revising to fix {len(blockers)} blocker/major item(s) and {len(issues)} mechanical issue(s)..."):
            script = normalise(_chat(client, WRITER_MODEL, _fill(REVISE, BRIEF=brief_txt, KID_RULES=KID_RULES,
                               SCRIPT=json.dumps(script, indent=1, ensure_ascii=False),
                               REVIEW=json.dumps({"scores": review.get("scores"), "must_fix": review.get("must_fix")}, indent=1),
                               MECH=mech), f"revise r{rnd}"), brief)

    script, low, total, issues, review, _key = best
    script["topic"] = topic
    script["brief"] = brief
    script["setting"] = brief.get("setting", "")
    script["cast"] = brief.get("cast", [])
    script["world"] = (script["setting"] + " " + " ".join(f"{x['id'].capitalize()}: {x['look']}" for x in script["cast"])).strip()
    stats = mechanical(script, brief)[1]
    out_dir = out_dir or FILM_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:40]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
    (out_dir / "script.md").write_text(to_markdown(script, review, stats))
    (out_dir / "script_report.json").write_text(json.dumps({
        "topic": topic, "writer": WRITER_MODEL, "critic": CRITIC_MODEL, "effort": EFFORT, "rounds": history,
        "final_scores": review.get("scores"), "remaining_must_fix": review.get("must_fix"),
        "remaining_mechanical": issues, "stats": stats, "cost_usd": round(costs.total(), 4),
        "seconds": round(time.time() - t0), "created_at": datetime.now().isoformat(timespec="seconds")},
        indent=2, ensure_ascii=False))
    print_script(script, review, stats, out_dir, costs.total(), time.time() - t0)
    return script, out_dir


# ── presentation ─────────────────────────────────────────────────────────────────────────────────────────────
def to_markdown(script, review, stats):
    L = [f"# {script['title']}", "", f"**Question:** {script.get('hook_question', '')}  ",
         f"**Answer shown:** {script.get('answer_line', '')}  ",
         f"**Length:** {stats['words']} words, about {stats['est_seconds']} s  ", "",
         "## Look", "", script.get("setting", ""), ""]
    for x in script.get("cast", []):
        L.append(f"- **{x['id']}** ({x.get('role', '')}): {x['look']}")
    L += ["", "## Scenes", ""]
    for s in script["scenes"]:
        mode = "SLOW MOTION" if s["speed"] < 1 else "real time"
        L += [f"### {s['scene']}. {s['beat'].upper()}  ·  {mode}  ·  {s['energy']} energy  ·  {s['cause_link'] if 'cause_link' in s else ''}",
              f"**Say:** {s['narration']}  ", f"*Delivery: {s['delivery']}*  ",
              f"**See:** {s['action']}  ", f"**Opens on:** {s['start_state']}  ", f"**Ends on:** {s['end_state']}  ",
              f"**Camera:** {s['camera']}  ", f"**Proof on screen:** {s['proof']}", ""]
    L += ["## Editor's scores", ""] + [f"- {k}: {v}" for k, v in (review.get("scores") or {}).items()]
    return "\n".join(L) + "\n"


def print_script(script, review, stats, out_dir, cost, secs):
    print()
    print(c("═" * 64, "bold"))
    print(c(f"  {script['title']}", "bold"))
    print(c("═" * 64, "bold"))
    print(f"  {c('Opens ', 'dim')} {script.get('hook_question', '')}")
    print(f"  {c('Answer', 'dim')} {script.get('answer_line', '')}")
    print(f"  {c('Length', 'dim')} {stats['words']} words, about {stats['est_seconds']} s, {stats['scenes']} scenes")
    for s in script["scenes"]:
        mode = c("SLOW-MO", "yellow") if s["speed"] < 1 else c("real time", "dim")
        print()
        print(f"  {c(str(s['scene']), 'bold')} {c(s['beat'].upper(), 'cyan')}  {mode}  {c(s['energy'] + ' energy', 'dim')}  {c(s['camera'], 'dim')}")
        print(f"     {c('SAY ', 'green')} {s['narration']}")
        print(f"     {c('SEE ', 'green')} {s['action']}")
        print(f"     {c('ENDS', 'green')} {s['end_state']}")
    print()
    sc = review.get("scores") or {}
    print("  " + c("Editor:", "bold") + "  " + "  ".join(f"{k.split('_')[0]} {sc.get(k, '?')}" for k in SCORES))
    left = [m for m in (review.get("must_fix") or []) if m.get("severity") in ("blocker", "major")]
    for m in left:
        print(c(f"  ! scene {m.get('scene')}: {m.get('problem')}", "yellow"))
    print(f"  {c('Saved ', 'dim')} {c(str(out_dir), 'cyan')}")
    print(f"  {c('Cost  ', 'dim')} {c('$%.2f' % cost, 'yellow')}   ·   {secs:.0f}s")
    print()
