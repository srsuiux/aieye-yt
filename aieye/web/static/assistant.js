/* Assistant page: the conversation, the assistant's visible work steps, and cards (video plan, upload) that the person confirms.
   The page only DRAWS what the server reports. Nothing is spent or published except by a button press on a card. */
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var root = $("#chat"), thread = $("#thread"), empty = $("#empty"), msg = $("#msg"), sendBtn = $("#send");
  var name = root.dataset.name, cid = null, after = 0, busy = false, timer = null;
  var nodes = {}, groups = {}, lastKind = null, lastGroup = null, userToggled = {};

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function money(n) { return "$" + Number(n).toFixed(2); }

  // ---- tiny, safe formatting: paragraphs, bullet lists, **bold**, `code` ----
  function inline(parent, s) {
    s.split(/(\*\*[^*]+\*\*|`[^`]+`)/).forEach(function (part) {
      if (/^\*\*[^*]+\*\*$/.test(part)) parent.appendChild(el("strong", "", part.slice(2, -2)));
      else if (/^`[^`]+`$/.test(part)) parent.appendChild(el("code", "", part.slice(1, -1)));
      else if (part) parent.appendChild(document.createTextNode(part));
    });
  }
  function format(box, text) {
    box.textContent = "";
    text.split(/\n{2,}/).forEach(function (block) {
      var lines = block.split("\n");
      if (lines.every(function (l) { return /^\s*[-*]\s+/.test(l); })) {
        var ul = el("ul"); lines.forEach(function (l) { var li = el("li"); inline(li, l.replace(/^\s*[-*]\s+/, "")); ul.appendChild(li); }); box.appendChild(ul);
      } else { var p = el("p"); lines.forEach(function (l, i) { if (i) p.appendChild(el("br")); inline(p, l); }); box.appendChild(p); }
    });
  }

  function nearBottom() { return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 140; }
  function toBottom() { thread.scrollTop = thread.scrollHeight; }

  // ---- messages ----
  function drawUser(ev) {
    var n = nodes[ev.id]; if (!n) { n = nodes[ev.id] = el("div", "msg user"); n.appendChild(el("div", "bubble")); thread.appendChild(n); }
    n.firstChild.textContent = ev.text;
  }
  function drawAssistant(ev) {
    var n = nodes[ev.id];
    if (!n) { n = nodes[ev.id] = el("div", "msg bot"); n.appendChild(el("span", "eye sm")); n.appendChild(el("div", "body")); thread.appendChild(n); }
    format(n.lastChild, ev.text || "");
  }
  function drawError(ev) {
    var n = nodes[ev.id]; if (!n) { n = nodes[ev.id] = el("div", "msg bot err"); n.appendChild(el("span", "eye sm")); n.appendChild(el("div", "body")); thread.appendChild(n); }
    n.lastChild.textContent = ev.text;
  }

  // ---- work steps: one group per run of steps, a header that says what is happening ----
  function drawStep(ev) {
    var row = nodes[ev.id], g;
    if (ev.status === "hidden") { if (row) { g = row._g; row.remove(); delete nodes[ev.id]; tidy(g); } return; }
    if (!row) {
      if (lastKind === "step" && lastGroup) g = lastGroup;
      else {
        g = el("div", "work open"); var head = el("button", "work-head"); head.type = "button"; head.setAttribute("aria-expanded", "true");
        head.appendChild(el("span", "spin")); head.appendChild(el("span", "wtitle")); head.appendChild(el("span", "chev"));
        head.addEventListener("click", function () { var o = g.classList.toggle("open"); head.setAttribute("aria-expanded", o); userToggled[g._id] = true; });
        g.appendChild(head); g.appendChild(el("ul", "steps")); g._id = ev.id; thread.appendChild(g);
      }
      row = nodes[ev.id] = el("li", "step"); row._g = g; row.appendChild(el("span", "dot")); row.appendChild(el("span", "slabel")); row.appendChild(el("span", "sdetail"));
      g.lastChild.appendChild(row); lastGroup = g;
    }
    row.className = "step " + ev.status; $(".slabel", row).textContent = ev.label + (ev.status === "running" ? "…" : ""); $(".sdetail", row).textContent = ev.detail || "";
    tidy(row._g);
  }
  function tidy(g) {
    if (!g) return;
    var rows = g.querySelectorAll(".step"), running = g.querySelectorAll(".step.running").length;
    if (!rows.length) { g.remove(); if (lastGroup === g) lastGroup = null; return; }
    g.classList.toggle("busy", running > 0);
    var t = $(".wtitle", g);
    if (running) { var r = g.querySelector(".step.running .slabel"); t.textContent = r ? r.textContent : "Working…"; }
    else { var failed = g.querySelectorAll(".step.failed").length; t.textContent = "Worked through " + rows.length + " step" + (rows.length > 1 ? "s" : "") + (failed ? " (" + failed + " had a problem)" : ""); }
    if (!running && !userToggled[g._id]) { g.classList.remove("open"); $(".work-head", g).setAttribute("aria-expanded", "false"); }
  }

  // ---- cards ----
  function row(label, value) { var r = el("div", "kv"); r.appendChild(el("span", "k", label)); r.appendChild(el("span", "v", value)); return r; }
  var SRC = { queue: "Next topic in your queue", trending: "What is trending on the web", top: "A top category", custom: "Your own topic" };

  function drawCard(ev) {
    var c = nodes[ev.id];
    if (!c) { c = nodes[ev.id] = el("div", "card-msg"); c.appendChild(el("span", "eye sm")); c._body = el("div", "agent-card"); c.appendChild(c._body); thread.appendChild(c); }
    var b = c._body;
    if (ev.status === "started") {
      if (!c._run) { b.textContent = ""; c._run = true; (ev.type === "video" ? runCard(b, ev) : uploadRun(b, ev)); }
      return;
    }
    b.textContent = "";
    if (ev.status === "discarded" || ev.status === "replaced") { b.className = "agent-card muted-card"; b.appendChild(el("p", "muted", ev.status === "discarded" ? "You discarded this plan." : "Replaced by a newer plan.")); return; }
    b.className = "agent-card";
    if (ev.type === "video") planCard(b, ev); else uploadCard(b, ev);
  }

  function planCard(b, ev) {
    var p = ev.params;
    b.appendChild(el("h3", "", "Video plan"));
    var kv = el("div", "kvs");
    kv.appendChild(row("Topic", p.source === "custom" ? p.topic : SRC[p.source]));
    kv.appendChild(row("How many", p.count === 1 ? "1 video" : p.count + " videos"));
    kv.appendChild(row("Languages", p.languages.join(", ")));
    kv.appendChild(row("Look", p.image_style + " · " + p.image_quality + " quality"));
    kv.appendChild(row("Narrator", p.tts_voice + (p.count > 1 && p.batch_voice === "shuffle" ? " (shuffled)" : "")));
    kv.appendChild(row("Upload", p.upload_privacy === "none" ? "No upload, keep the video here" : p.upload_privacy + (p.review ? ", after you review it" : ", right away")));
    b.appendChild(kv);
    var cost = el("p", "cost-line"); cost.appendChild(document.createTextNode("Estimated cost ")); cost.appendChild(el("strong", "", money(ev.est)));
    cost.appendChild(el("span", "muted small", p.count > 1 ? "  (" + money(ev.per) + " each)" : "")); b.appendChild(cost);
    var act = el("div", "actions"), go = el("button", "btn", "Make it · spend about " + money(ev.est)), no = el("button", "btn ghost", "Discard"), note = el("span", "note");
    go.type = no.type = "button";
    go.addEventListener("click", function () {
      if (p.upload_privacy === "public" && !p.review && !confirm("This will publish publicly as soon as it is made, with no review. Continue?")) return;
      go.disabled = no.disabled = true; note.textContent = "Starting…";
      post("/api/chat/" + cid + "/cards/" + ev.id + "/confirm", {}).then(function (d) { if (d.ok) poll(); else { note.textContent = d.message || "Could not start."; note.className = "note bad"; go.disabled = no.disabled = false; } });
    });
    no.addEventListener("click", function () { post("/api/chat/" + cid + "/cards/" + ev.id + "/discard", {}).then(poll); });
    act.appendChild(go); act.appendChild(no); act.appendChild(note); b.appendChild(act);
  }

  function uploadCard(b, ev) {
    b.appendChild(el("h3", "", "Upload to YouTube"));
    var t = el("input"); t.type = "text"; t.maxLength = 100; t.value = ev.title; t.setAttribute("aria-label", "Title");
    var sel = el("select"); ["private", "unlisted", "public"].forEach(function (o) { var op = el("option", "", o); op.value = o; sel.appendChild(op); }); sel.value = ev.privacy; sel.setAttribute("aria-label", "Who can watch it");
    var f1 = el("div", "field"); f1.appendChild(el("label", "", "Title")); f1.appendChild(t);
    var f2 = el("div", "field"); f2.appendChild(el("label", "", "Who can watch it")); f2.appendChild(sel);
    b.appendChild(f1); b.appendChild(f2);
    b.appendChild(document.getElementById("publish-note").content.cloneNode(true));
    var act = el("div", "actions"), go = el("button", "btn", "Upload"), no = el("button", "btn ghost", "Discard"), note = el("span", "note");
    go.type = no.type = "button";
    go.addEventListener("click", function () {
      if (sel.value === "public" && !confirm("This video will be public as soon as the upload finishes. Continue?")) return;
      go.disabled = no.disabled = true; note.textContent = "Starting…";
      post("/api/chat/" + cid + "/cards/" + ev.id + "/confirm", { title: t.value, privacy: sel.value }).then(function (d) {
        if (d.ok) poll(); else { note.textContent = d.message || "Could not start."; note.className = "note bad"; go.disabled = no.disabled = false; }
      });
    });
    no.addEventListener("click", function () { post("/api/chat/" + cid + "/cards/" + ev.id + "/discard", {}).then(poll); });
    act.appendChild(go); act.appendChild(no); act.appendChild(note); b.appendChild(act);
  }

  // ---- a started run, shown live inside its card ----
  var ALL = [["topic", "Choose the topic"], ["script", "Write the script"], ["pictures", "Draw the pictures"], ["voice", "Record the narration"],
             ["video", "Build the video"], ["review", "Your review"], ["upload", "Upload to YouTube"]];
  function sectionKey(title) {
    var t = title.toUpperCase();
    if (t.indexOf("STEP 0") === 0) return "topic"; if (t.indexOf("STEP 1") === 0) return "script"; if (t.indexOf("STEP 3") === 0) return "pictures";
    if (t.indexOf("STEP 2") === 0 || t.indexOf("STEP 4") === 0) return "voice"; if (t.indexOf("STEP 5") === 0) return "video"; if (t.indexOf("STEP 6") === 0) return "upload";
    return null;
  }
  function runCard(b, ev) { live(b, ev.job, ev.params.review && ev.params.upload_privacy !== "none", ev.params.upload_privacy !== "none", "Making your video"); }
  function uploadRun(b, ev) { live(b, ev.job, false, true, "Uploading", true); }

  function live(b, job, wantReview, wantUpload, title, uploadOnly) {
    var steps = uploadOnly ? [["upload", "Upload to YouTube"]] : ALL.filter(function (s) { return (s[0] !== "review" || wantReview) && (s[0] !== "upload" || wantUpload); });
    var head = el("div", "run-top"); var h = el("h3", "", title); var chip = el("span", "status", "Starting"); head.appendChild(h); head.appendChild(chip); b.appendChild(head);
    var bar = el("div", "bar"); var fill = el("i"); fill.style.width = "3%"; bar.appendChild(fill); b.appendChild(bar);
    var ol = el("ol", "tracker"), li = {}; steps.forEach(function (s) { var x = el("li", "pending"); x.appendChild(el("span", "dot")); x.appendChild(el("span", "", s[1])); x.appendChild(el("span", "sub")); ol.appendChild(x); li[s[0]] = x; }); b.appendChild(ol);
    var meta = el("p", "muted small"); var costEl = el("span", "", "$0.0000"); meta.appendChild(document.createTextNode("Cost so far ")); meta.appendChild(costEl); meta.appendChild(document.createTextNode(" · ")); var link = el("a", "", "Open the full run page"); link.href = aieye.url("/runs/" + job); meta.appendChild(link); b.appendChild(meta);
    var reviewBox = el("div", "review-box"); reviewBox.hidden = true; b.appendChild(reviewBox);
    var result = el("div", "run-result"); result.hidden = true; b.appendChild(result);
    var cancel = el("button", "btn ghost danger", "Cancel run"); cancel.type = "button"; b.appendChild(cancel);
    var cur = -1, aft = 0, uploadPct = null, lang = "", shown = null, done = false;
    function idx(k) { for (var i = 0; i < steps.length; i++) if (steps[i][0] === k) return i; return -1; }
    function setCur(k) { var i = idx(k); if (i >= 0 && i >= cur) { cur = i; uploadPct = null; } }
    function paint(state) {
      steps.forEach(function (s, i) {
        var x = li[s[0]], cls = "pending", sub = "";
        if (state === "done" || i < cur) cls = "done";
        else if (i === cur) { cls = state === "failed" || state === "cancelled" ? "stopped" : (state === "review" && s[0] === "review") ? "wait" : "active"; if (s[0] === "upload" && uploadPct !== null) sub = uploadPct + "%"; else if (lang && (s[0] === "voice" || s[0] === "video")) sub = lang; }
        x.className = cls; x.lastChild.textContent = sub;
      });
      var frac = state === "done" ? 1 : Math.max(0.03, (cur + (cur >= 0 ? 0.5 : 0)) / steps.length);
      if (uploadPct !== null && cur === idx("upload")) frac = (cur + uploadPct / 100) / steps.length;
      fill.style.width = Math.round(frac * 100) + "%";
      chip.textContent = { running: "Running", review: "Waiting for you", done: "Done", failed: "Failed", cancelled: "Cancelled" }[state] || state;
      chip.className = "status " + (state === "done" ? "ok" : state === "failed" ? "bad" : "");
      cancel.hidden = !(state === "running" || state === "review");
    }
    function showReview(r) {
      if (!r || shown === r.index) return; shown = r.index; reviewBox.hidden = false; reviewBox.textContent = "";
      reviewBox.appendChild(el("h4", "", "Review before upload" + (r.lang && r.lang !== "en" ? " (" + r.lang + ")" : "")));
      var v = el("video"); v.controls = true; v.playsInline = true; v.preload = "metadata"; v.src = "/jobs/" + job + "/review/" + r.index + "/video"; reviewBox.appendChild(v);
      var t = el("input"); t.type = "text"; t.maxLength = 100; t.value = r.meta.title; var d = el("textarea"); d.rows = 5; d.value = r.meta.description;
      var tg = el("input"); tg.type = "text"; tg.value = (r.meta.tags || []).join(", ");
      var pv = el("select"); ["private", "unlisted", "public"].forEach(function (o) { var op = el("option", "", o); op.value = o; pv.appendChild(op); }); pv.value = r.meta.privacy === "none" ? "private" : r.meta.privacy;
      [["Title", t], ["Description", d], ["Tags (comma separated)", tg], ["Who can watch it", pv]].forEach(function (p) { var f = el("div", "field"); f.appendChild(el("label", "", p[0])); f.appendChild(p[1]); reviewBox.appendChild(f); });
      reviewBox.appendChild(document.getElementById("publish-note").content.cloneNode(true));
      var act = el("div", "actions"), up = el("button", "btn", "Upload to YouTube"), sk = el("button", "btn ghost", "Skip upload, keep the video"), note = el("span", "note"); up.type = sk.type = "button";
      function answer(action) {
        if (action === "upload" && pv.value === "public" && !confirm("This video will be public as soon as the upload finishes. Continue?")) return;
        up.disabled = sk.disabled = true;
        post("/api/jobs/" + job + "/review/" + r.index, { action: action, meta: { title: t.value, description: d.value, tags: tg.value.split(","), privacy: pv.value } }).then(function (x) {
          if (x.ok) { reviewBox.hidden = true; v.pause(); } else { note.textContent = x.message || "Could not send."; note.className = "note bad"; up.disabled = sk.disabled = false; }
        });
      }
      up.addEventListener("click", function () { answer("upload"); }); sk.addEventListener("click", function () { answer("skip"); });
      act.appendChild(up); act.appendChild(sk); act.appendChild(note); reviewBox.appendChild(act);
    }
    function finish(st) {
      done = true; reviewBox.hidden = true; result.hidden = false; result.textContent = "";
      (st.results || []).forEach(function (r) {
        var p = el("p"); p.appendChild(document.createTextNode((r.ok ? "Done: " : "Problem: ") + (r.title || r.topic || "Video") + (r.cost ? " (" + money(r.cost) + ")" : "") + " "));
        if (r.url) { var a = el("a", "", "Watch on YouTube"); a.href = r.url; a.target = "_blank"; a.rel = "noopener"; p.appendChild(a); }
        else if (r.ok && r.path) p.appendChild(el("span", "muted small", "Kept on this computer, see Library."));
        result.appendChild(p); if (r.error) result.appendChild(el("p", "note bad", r.error));
      });
      if (st.error && !(st.results || []).length) result.appendChild(el("p", "note bad", st.error));
    }
    function tick() {
      if (done) return;
      get("/api/jobs/" + job + "?after=" + aft).then(function (d) {
        if (!d.status) { chip.textContent = d.message || "Not found"; done = true; return; }
        aft = d.next;
        d.events.forEach(function (e) {
          if (e.kind === "section") { var k = sectionKey(e.title); if (k) setCur(k); }
          else if (e.kind === "review") setCur("review");
          else if (e.kind === "video") cur = -1;
          else if (e.kind === "language") { lang = e.many ? e.name : ""; if (e.many && idx("pictures") >= 0) cur = Math.min(cur, idx("pictures")); }
          else if (e.kind === "cost") costEl.textContent = "$" + e.total.toFixed(4);
          else if (e.kind === "progress") uploadPct = e.percent;
        });
        var st = d.status; if (st.state === "review") showReview(d.review);
        paint(st.state);
        if (["done", "failed", "cancelled"].indexOf(st.state) >= 0) finish(st);
        if (!done) setTimeout(tick, 1000);
      });
    }
    cancel.addEventListener("click", function () { if (confirm("Cancel this run? Anything already spent stays spent.")) post("/api/jobs/" + job + "/cancel", {}); });
    paint("running"); tick();
  }

  // ---- talking to the server ----
  function get(url) { return aieye.api("GET", url); }
  function post(url, body) { return aieye.api("POST", url, body); }

  function draw(ev) {
    var stick = nearBottom(), isNew = !nodes[ev.id];
    if (ev.kind === "user") drawUser(ev); else if (ev.kind === "assistant") drawAssistant(ev); else if (ev.kind === "step") drawStep(ev);
    else if (ev.kind === "card") drawCard(ev); else if (ev.kind === "error") drawError(ev);
    if (isNew) { if (ev.kind !== "step") { lastKind = ev.kind; lastGroup = null; } else lastKind = "step"; }
    if (stick) toBottom();
  }
  function setBusy(b) { busy = b; sendBtn.disabled = b || root.dataset.hasKey !== "1"; root.classList.toggle("is-busy", b); var st = $("#state"); if (st) st.textContent = b ? "Working" : "Ready"; }
  function apply(d) {
    if (d.events && d.events.length) empty.hidden = true;
    d.events.forEach(draw); after = d.next; setBusy(!!d.busy);
  }
  function poll() {
    clearTimeout(timer);
    get("/api/chat/" + cid + "?after=" + after).then(function (d) {
      if (!d.ok) return; apply(d);
      if (busy) timer = setTimeout(poll, 550);
    });
  }

  function send(text) {
    text = (text || "").trim(); if (!text || busy) return;
    msg.value = ""; autosize(); setBusy(true);
    post("/api/chat/" + cid + "/message", { text: text }).then(function (d) {
      if (!d.ok) { setBusy(false); var e = { id: "local" + Date.now(), kind: "error", text: d.message || "Could not send." }; empty.hidden = true; draw(e); return; }
      poll();
    });
  }
  function autosize() { msg.style.height = "auto"; msg.style.height = Math.min(msg.scrollHeight, 160) + "px"; }

  // ---- voice dictation (browser speech recognition; text only, nothing is sent until you press Send) ----
  var mic = $("#mic"), SR = window.SpeechRecognition || window.webkitSpeechRecognition, rec = null, listening = false, base = "";
  function stopListening() { if (rec && listening) { try { rec.stop(); } catch (e) {} } }
  if (SR && mic) {
    mic.hidden = false;
    mic.addEventListener("click", function () {
      if (listening) { stopListening(); return; }
      rec = new SR(); rec.lang = navigator.language || "en-US"; rec.interimResults = true; rec.continuous = true;
      base = msg.value && !/\s$/.test(msg.value) ? msg.value + " " : msg.value;
      rec.onstart = function () { listening = true; mic.classList.add("on"); mic.setAttribute("aria-pressed", "true"); mic.title = "Stop dictation"; };
      rec.onresult = function (e) {
        var t = ""; for (var i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
        msg.value = base + t; autosize();
      };
      rec.onerror = function (e) {
        var m = { "not-allowed": "Microphone blocked. Allow it in your browser's site settings.", "service-not-allowed": "Microphone blocked. Allow it in your browser's site settings.", "no-speech": "", "aborted": "", "network": "Speech service unreachable. Check your connection." }[e.error];
        if (m == null) m = "Voice dictation failed (" + e.error + ")."; if (m && window.aieye) window.aieye.toast(m);
      };
      rec.onend = function () { listening = false; mic.classList.remove("on"); mic.setAttribute("aria-pressed", "false"); mic.title = "Dictate with your voice"; msg.focus(); };
      try { rec.start(); } catch (e) {}
    });
  }
  $("#composer").addEventListener("submit", function (e) { e.preventDefault(); stopListening(); send(msg.value); });
  msg.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); stopListening(); send(msg.value); } });
  msg.addEventListener("input", autosize);
  Array.prototype.forEach.call(document.querySelectorAll("#chips .start-card"), function (b) { b.addEventListener("click", function () { send(b.dataset.q); }); });
  $("#info-open").addEventListener("click", function () { $("#info-dialog").showModal(); });
  // what each starter card will act on, shown before you click
  get("/api/assistant/glance").then(function (g) {
    if (!g || g.limit == null) return;
    var cut = function (s) { return s.length > 70 ? s.slice(0, 68) + "..." : s; };
    $("#g-next").textContent = g.next_topic ? "Next: " + cut(g.next_topic) + (g.queued > 1 ? "  (+" + (g.queued - 1) + " more)" : "") : "Your queue is empty. I can find a topic.";
    var left = Math.max(0, g.limit - g.pushed);
    $("#g-limit").textContent = g.pushed + " of " + g.limit + " pushed today. " + left + " left.";
    $("#g-lib").textContent = g.waiting ? g.waiting + " waiting to upload. Latest: " + cut(g.waiting_first) : "Nothing waiting. All videos are uploaded.";
  }).catch(function () {});
  $("#new-chat").addEventListener("click", function () {
    if (busy && !confirm("I am still working. Start a new chat anyway?")) return;
    post("/api/chat/new", {}).then(function (d) {
      cid = d.chat; after = 0; nodes = {}; lastKind = lastGroup = null;
      Array.prototype.slice.call(thread.children).forEach(function (c) { if (c !== empty) c.remove(); }); empty.hidden = false; setBusy(false); msg.focus();
    });
  });

  get("/api/chat").then(function (d) { cid = d.chat; apply(d); toBottom(); if (busy) poll(); msg.focus(); });
  // a card that was confirmed in another tab or after a reload starts its live run view when the page next polls
  setInterval(function () { if (cid && !busy) poll(); }, 4000);
})();
