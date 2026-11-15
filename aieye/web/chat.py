"""Chat conversations with the assistant: stored in data/chat/, run in a background thread, read by the page by polling.

A conversation is a list of EVENTS the page draws: the person's messages, the assistant's replies, work steps, and cards
(a video plan, an upload). Events are updated in place (a reply grows as it streams, a step finishes, a card is confirmed), so
each event carries `seq`, the number of its last change, and the page asks for everything newer than the last seq it saw.
"""
import json, threading, time
from pathlib import Path

from .. import assistant, envfile
from ..config import DATA_DIR
from ..limits import DAILY_LIMIT, pushed_today
from ..settings import load_defaults
from ..store import load_db
from ..config import DRAFT_DB, FINAL_DB
from ..languages import LANGS
from . import connections, data, jobs, library

CHAT_DIR = DATA_DIR / "chat"
_CONVS, _LOCK = {}, threading.Lock()


class ChatError(ValueError):
    pass


def friendly(e):
    s = str(e)
    if "401" in s or "invalid_api_key" in s or "Incorrect API key" in s:
        return "OpenAI rejected your key. Check it on the Connections page."
    if "429" in s or "insufficient_quota" in s or "rate" in s.lower():
        return "OpenAI says you are out of quota or going too fast. Check your OpenAI billing, then try again."
    if "model" in s.lower() and ("not found" in s.lower() or "does not exist" in s.lower() or "access" in s.lower()):
        return "Your OpenAI account cannot use the assistant model. Pick another under Settings > Advanced > Models."
    if "connect" in s.lower() or "timeout" in s.lower():
        return "I could not reach OpenAI. Check your internet connection and try again."
    return "Something went wrong while I was working: " + s[:1200]       # long enough to include the provider's whole explanation


class Conversation:
    def __init__(self, cid):
        self.id, self.events, self.messages, self.seq = cid, [], [], 0
        self.busy, self.lock, self._n = False, threading.RLock(), 0
        self.path = CHAT_DIR / f"{cid}.json"
        try:
            d = json.loads(self.path.read_text())
            self.events, self.messages = d["events"], d["messages"]
            self.seq = max([e.get("seq", 0) for e in self.events] or [0])
            self._n = len(self.events)
            for e in self.events:                      # a step left running by a closed server is not running any more
                if e["kind"] == "step" and e.get("status") == "running":
                    e["status"] = "hidden" if e.get("think") else "failed"
        except (OSError, ValueError, KeyError):
            pass

    # ---- events ----
    def add(self, kind, **kw):
        with self.lock:
            self._n += 1
            ev = {"id": f"e{self._n}", "kind": kind, **kw}
            self.touch(ev)
            self.events.append(ev)
            return ev

    def touch(self, ev):
        with self.lock:
            self.seq += 1
            ev["seq"] = self.seq

    def since(self, after):
        with self.lock:
            return {"events": [e for e in self.events if e.get("seq", 0) > after], "next": self.seq, "busy": self.busy}

    def save(self):
        with self.lock:
            CHAT_DIR.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"events": self.events, "messages": self.messages}, ensure_ascii=False))
            tmp.replace(self.path)

    def find(self, eid):
        return next((e for e in self.events if e["id"] == eid), None)

    # ---- a turn ----
    def send(self, text):
        text = (text or "").strip()
        if not text:
            raise ChatError("Write a message first.")
        if len(text) > 4000:
            raise ChatError("That message is too long (4000 characters at most).")
        if not envfile.get_key("OPENAI_API_KEY"):
            raise ChatError("Add your OpenAI key on the Connections page first.")
        with self.lock:
            if self.busy:
                raise ChatError("I am still working on your last message.")
            self.busy = True
            self.add("user", text=text)
            self.messages.append({"role": "user", "content": text})
        threading.Thread(target=self._turn, daemon=True).start()

    def _turn(self):
        think = self.add("step", label="Thinking", status="running", think=True)
        state = {"reply": None}

        def on_text(t):
            if think["status"] == "running":
                think["status"] = "hidden"
                self.touch(think)
            if state["reply"] is None or state["reply"].get("closed"):
                state["reply"] = self.add("assistant", text=t)
            else:
                state["reply"]["text"] = t
                self.touch(state["reply"])

        steps = {}

        def on_step(sid, name, label, status, detail):
            if think["status"] == "running":
                think["status"] = "hidden"
                self.touch(think)
            if state["reply"]:
                state["reply"]["closed"] = True        # text after a tool call is a new message
            ev = steps.get(sid)
            if ev is None:
                ev = steps[sid] = self.add("step", label=label, status=status, detail=detail, tool=name)
            else:
                ev.update(status=status, detail=detail)
                self.touch(ev)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=envfile.get_key("OPENAI_API_KEY"))
            from ..tuning import tune
            system = assistant.system_prompt(data.brand_name(), data.defaults_view()["values"])
            assistant.run_turn(client, tune("ASSISTANT_MODEL"), system, self.messages, self.call_tool, on_text, on_step)
        except BaseException as e:
            if think["status"] == "running":
                think["status"] = "hidden"
                self.touch(think)
            self.add("error", text=friendly(e))
        finally:
            if state["reply"]:
                state["reply"].pop("closed", None)
            with self.lock:
                self.busy = False
            self.save()

    # ---- tools ----
    def call_tool(self, name, args):
        fn = getattr(self, "tool_" + name, None)
        if not fn:
            return {"error": f"Unknown tool {name}"}
        out = fn(**{k: v for k, v in args.items() if k in fn.__code__.co_varnames[:fn.__code__.co_argcount]})
        self.save()
        return out

    def tool_get_overview(self):
        queue = [t for t in load_db(DRAFT_DB) if t.get("status") == "pending"]
        act = jobs.active()
        yt = connections.youtube_status()
        d = data.defaults_view()
        return {"openai_key_saved": envfile.key_status("OPENAI_API_KEY")["set"], "openrouter_key_saved": envfile.key_status("OPENROUTER_API_KEY")["set"],
                "youtube_connected": bool(yt["signed_in"]), "videos_pushed_today": pushed_today(), "daily_limit": DAILY_LIMIT,
                "topics_in_queue": len(queue), "next_topic": queue[0]["title"] if queue else None,
                "saved_defaults": {**d["values"], "review_before_upload": d["review"]}, "defaults_saved_by_user": d["saved"],
                "language_codes": {k: v[0] for k, v in LANGS.items()},
                "run_in_progress": ({"id": act["id"], "state": act["state"]} if act else None)}

    def tool_get_queue(self, limit=8):
        limit = max(1, min(15, int(limit or 8)))
        v = data.topics_view()
        return {"queued": [t["title"] for t in v["queue"][:limit]], "recent_videos": [{"title": e.get("title") or e.get("topic"), "when": e.get("when")} for e in v["history"][:limit]]}

    def tool_get_runs(self):
        out = []
        for s in jobs.recent(6):
            out.append({"id": s["id"], "kind": s["kind"], "state": s["state"], "error": s.get("error"),
                        "results": [{"title": r.get("title"), "ok": r.get("ok"), "url": r.get("url")} for r in s.get("results", [])]})
        return {"runs": out}

    def tool_list_library(self):
        return {"videos": [{"id": v["id"], "title": v["title"], "size_mb": v["size"], "made": v["when"], "language": v["lang"]} for v in library.kept_videos()[:25]]}

    def tool_propose_video(self, source="queue", topic="", count=1, languages=None, image_style=None, image_quality=None, tts_voice=None,
                           upload_privacy=None, review=None):
        d = data.defaults_view()
        base = dict(d["values"])
        p = {"source": source, "topic": topic, "count": count, "languages": languages or ["en"], "review": d["review"] if review is None else bool(review),
             "image_style": image_style or base["image_style"], "image_quality": image_quality or base["image_quality"],
             "tts_voice": tts_voice or base["tts_voice"], "upload_privacy": upload_privacy or base["upload_privacy"],
             "batch_voice": base.get("batch_voice", "shuffle")}
        try:
            clean = jobs.validate(p)
        except (jobs.JobError, ValueError) as e:
            return {"error": str(e)}
        if not envfile.get_key("OPENAI_API_KEY"):
            return {"error": "The OpenAI key is not saved. Ask the person to add it on the Connections page."}
        left = DAILY_LIMIT - pushed_today()
        if clean["upload_privacy"] != "none" and left < clean["count"]:
            return {"error": f"Only {max(left, 0)} videos can still be pushed to YouTube today (limit {DAILY_LIMIT}). Suggest fewer videos or upload privacy none."}
        total, per = jobs.estimate(clean)
        with self.lock:
            for c in self.events:                      # a newer plan replaces an older one that was never answered
                if c["kind"] == "card" and c.get("type") == "video" and c["status"] == "pending":
                    c["status"] = "replaced"
                    self.touch(c)
            self.add("card", type="video", status="pending", params=clean, est=total, per=per)
        return {"status": "plan_shown_to_the_person", "estimated_cost_usd": total, "note": "Nothing has started. The person must press Make it."}

    def tool_propose_upload(self, id, privacy="private"):
        try:
            folder = library.kept_folder(id)
            meta = json.loads((folder / "youtube_metadata.json").read_text())
        except (LookupError, OSError, ValueError):
            return {"error": "That video is not in the Library any more. Call list_library again."}
        if privacy not in ("public", "private", "unlisted"):
            privacy = "private"
        with self.lock:
            self.add("card", type="upload", status="pending", video_id=id, title=meta.get("title", ""), description=meta.get("description", ""),
                     tags=meta.get("tags") or [], privacy=privacy)
        return {"status": "upload_shown_to_the_person", "title": meta.get("title"), "note": "Nothing has been uploaded. The person must press Upload."}

    # ---- the person's button presses ----
    def confirm(self, eid, body):
        with self.lock:
            card = self.find(eid)
            if not card or card["kind"] != "card" or card["status"] != "pending":
                raise ChatError("That plan was already answered or replaced.")
            try:
                if card["type"] == "video":
                    job = jobs.start_make(card["params"])
                else:
                    meta = {"title": body.get("title", card["title"]), "description": body.get("description", card["description"]),
                            "tags": body.get("tags", card["tags"]), "privacy": body.get("privacy", card["privacy"])}
                    job = jobs.start_upload(library.kept_folder(card["video_id"]), meta)
            except LookupError as e:
                raise ChatError(str(e))
            except (jobs.JobError, ValueError) as e:
                raise ChatError(str(e))
            card["status"], card["job"] = "started", job
            self.touch(card)
            self.save()
            return job

    def discard(self, eid):
        with self.lock:
            card = self.find(eid)
            if card and card["kind"] == "card" and card["status"] == "pending":
                card["status"] = "discarded"
                self.touch(card)
                self.save()


def new():
    cid = time.strftime("%Y%m%d-%H%M%S")
    with _LOCK:
        conv = _CONVS[cid] = Conversation(cid)
    conv.save()
    return conv


def get(cid):
    if not cid or "/" in cid or ".." in cid:
        raise ChatError("Unknown chat.")
    with _LOCK:
        if cid not in _CONVS:
            if not (CHAT_DIR / f"{cid}.json").exists():
                raise ChatError("That chat no longer exists.")
            _CONVS[cid] = Conversation(cid)
        return _CONVS[cid]


def latest():
    """The most recent conversation, or a new one."""
    files = sorted(CHAT_DIR.glob("*.json")) if CHAT_DIR.exists() else []
    return get(files[-1].stem) if files else new()
