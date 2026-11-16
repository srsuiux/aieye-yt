/* Run page: polls the run once a second, shows the step tracker, running cost and log, handles the review step and the result. */
(function () {
  var q = function (s) { return document.querySelector(s); };
  var root = q("#run"), id = root.dataset.id, kind = root.dataset.kind;
  var wantReview = root.dataset.review === "1", wantUpload = root.dataset.upload === "1";

  // [key, step, who is doing it, what they do]
  var ALL = [["topic", "Choose the topic", "Scout", "Picks what the video is about"], ["script", "Write the script", "Writer", "Researches the facts and writes the narration"],
             ["pictures", "Draw the pictures", "Illustrator", "Paints one picture for every shot"], ["voice", "Record the narration", "Narrator", "Reads the script aloud and times each line"],
             ["video", "Build the video", "Editor", "Adds motion and captions, then renders the video"], ["review", "Your review", "You", "Check the video before it goes out"],
             ["upload", "Upload to YouTube", "Publisher", "Sends the video and its details to your channel"]];
  var steps = kind === "upload" ? [["upload", "Upload to YouTube", "Publisher", "Sends the video and its details to your channel"]] : ALL.filter(function (s) {
    return (s[0] !== "review" || wantReview) && (s[0] !== "upload" || wantUpload);
  });
  function idx(key) { for (var i = 0; i < steps.length; i++) if (steps[i][0] === key) return i; return -1; }

  var tracker = q("#tracker"), nodes = {};
  var feeds = {}, started = {}, activity = {};
  steps.forEach(function (s) {
    var li = document.createElement("li"); li.className = "pending";
    li.innerHTML = '<div class="row"><span class="dot" aria-hidden="true"></span><span class="who"></span><span class="lbl"></span><span class="sub"></span></div>' +
      '<p class="role"></p><div class="live" hidden><span class="typing" aria-hidden="true"><i></i><i></i><i></i></span><span class="doing"></span></div><ul class="feed"></ul>';
    li.querySelector(".who").textContent = s[2]; li.querySelector(".lbl").textContent = s[1]; li.querySelector(".role").textContent = s[3];
    li.addEventListener("click", function (e) { if (e.target.closest("a")) return; li.classList.toggle("open"); });
    tracker.appendChild(li); nodes[s[0]] = li; feeds[s[0]] = [];
  });
  var stageImgs = [], stageVideo = null, stageScript = null;

  var cur = -1, after = 0, timer = null, shown = null, uploadPct = null, videoLabel = "", langLabel = "", terminal = false, startedAt = null;
  var STATE_TEXT = { running: "Running", review: "Waiting for you", done: "Done", failed: "Failed", cancelled: "Cancelled" };

  function section(title) {
    var t = title.toUpperCase();
    if (t.indexOf("STEP 0") === 0) return "topic";
    if (t.indexOf("STEP 1") === 0) return "script";
    if (t.indexOf("STEP 3") === 0) return "pictures";
    if (t.indexOf("STEP 2") === 0 || t.indexOf("STEP 4") === 0) return "voice";
    if (t.indexOf("STEP 5") === 0) return "video";
    if (t.indexOf("STEP 6") === 0) return "upload";
    return null;
  }
  function setCur(key) { var i = idx(key); if (i >= 0 && i >= cur) { if (i !== cur) started[key] = Date.now(); cur = i; uploadPct = null; } }
  function curKey() { return steps[cur >= 0 ? cur : 0][0]; }

  function handle(ev) {
    if (ev.kind === "section") { var k = section(ev.title); if (k) setCur(k); }
    else if (ev.kind === "review") setCur("review");
    else if (ev.kind === "topic") q("#run-topic").textContent = ev.title;
    else if (ev.kind === "video") { cur = -1; videoLabel = ev.count > 1 ? "Video " + ev.index + " of " + ev.count : ""; langLabel = ""; }
    else if (ev.kind === "language") { langLabel = ev.many ? ev.name : ""; if (ev.many && idx("pictures") >= 0) cur = Math.min(cur, idx("pictures")); }
    else if (ev.kind === "cost") q("#cost").textContent = "$" + ev.total.toFixed(4);
    else if (ev.kind === "progress") uploadPct = ev.percent;
    else if (ev.kind === "log") { addLog(ev); addFeed(ev); }
    else if (ev.kind === "spin") { var key = curKey(); if (ev.state === "start") activity[key] = ev.label; else delete activity[key]; }
    else if (ev.kind === "artifact") artifact(ev);
  }
  function addFeed(ev) {
    var m = (ev.message || "").trim();
    if (!m || /^Output:/.test(m)) return;
    var f = feeds[curKey()]; f.push({ text: m.replace(/^Building: /, "Working on "), tone: ev.color });
    if (f.length > 60) f.shift();
  }
  function mediaUrl(p) { return "/jobs/" + id + "/media?p=" + encodeURIComponent(p); }
  function artifact(ev) {
    if (ev.what === "script") stageScript = ev;
    else if (ev.what === "image" && ev.path) { if (stageImgs.indexOf(ev.path) < 0) stageImgs.push(ev.path); }
    else if (ev.what === "video" && ev.path) stageVideo = ev.path;
    drawStage();
  }
  function drawStage() {
    var idle = q("#stage-idle"), sc = q("#stage-script"), im = q("#stage-img"), vd = q("#stage-video"), cap = q("#stage-cap");
    idle.hidden = !!(stageScript || stageImgs.length || stageVideo);
    sc.hidden = !(stageScript && !stageImgs.length && !stageVideo);
    im.hidden = !(stageImgs.length && !stageVideo);
    vd.hidden = !stageVideo;
    if (stageScript && !sc.dataset.done) {
      sc.dataset.done = "1"; q("#s-title").textContent = stageScript.title;
      var ol = q("#s-scenes"); ol.innerHTML = "";
      stageScript.scenes.forEach(function (s, i) { var li = document.createElement("li"); li.textContent = s.text; li.style.animationDelay = (i * 0.12) + "s"; ol.appendChild(li); });
    }
    if (stageImgs.length) { var last = mediaUrl(stageImgs[stageImgs.length - 1]); if (im.dataset.src !== last) { im.dataset.src = last; im.src = last; } }
    if (stageVideo) { var v = mediaUrl(stageVideo); if (vd.dataset.src !== v) { vd.dataset.src = v; vd.src = v; vd.play().catch(function () {}); } }
    var th = q("#thumbs");
    if (th.children.length !== stageImgs.length) {
      th.innerHTML = ""; stageImgs.forEach(function (p) { var i = document.createElement("img"); i.src = mediaUrl(p); i.alt = ""; i.loading = "lazy"; th.appendChild(i); });
    }
    cap.textContent = stageVideo ? "Finished video" : stageImgs.length ? stageImgs.length + " picture" + (stageImgs.length > 1 ? "s" : "") + " made so far" : stageScript ? "Script: " + stageScript.scenes.length + " scenes" : "Waiting to start";
  }
  function addLog(ev) {
    var pre = q("#log"), t = (ev.time || "").slice(11, 19);
    pre.textContent += "[" + t + "] " + new Array((ev.indent || 0) + 1).join("  ") + ev.message + "\n";
    if (pre.textContent.length > 60000) pre.textContent = pre.textContent.slice(-40000);
    pre.scrollTop = pre.scrollHeight;
  }

  function paint(state) {
    var done = state === "done";
    steps.forEach(function (s, i) {
      var li = nodes[s[0]], sub = li.querySelector(".sub"), cls = "pending", text = "";
      if (done || i < cur) cls = "done";
      else if (i === cur) {
        cls = state === "failed" || state === "cancelled" ? "stopped" : (state === "review" && s[0] === "review") ? "wait" : "active";
        if (s[0] === "upload" && uploadPct !== null) text = uploadPct + "%";
        if (s[0] === "voice" || s[0] === "video" || s[0] === "upload") text = text || langLabel;
      }
      li.className = cls + (li.classList.contains("open") ? " open" : ""); sub.textContent = text;
      var key = s[0], feed = feeds[key], live = li.querySelector(".live"), list = li.querySelector(".feed");
      var working = cls === "active";
      live.hidden = !working;
      if (working) {
        var secs = started[key] ? Math.floor((Date.now() - started[key]) / 1000) : 0;
        live.querySelector(".doing").textContent = (activity[key] || (feed.length ? feed[feed.length - 1].text : s[3])) + (secs > 4 ? "  " + secs + "s" : "");
        li.classList.add("open");
      } else if (cls === "pending") li.classList.remove("open");
      var shown = li.classList.contains("open") ? (working ? feed.slice(-4) : feed) : [];
      var sig = shown.length + ":" + (shown.length ? shown[shown.length - 1].text : "");
      if (list.dataset.sig !== sig) {
        list.dataset.sig = sig; list.innerHTML = "";
        shown.forEach(function (f) { var it = document.createElement("li"); it.textContent = f.text; if (f.tone) it.className = f.tone; list.appendChild(it); });
      }
    });
    var frac = done ? 1 : steps.length ? Math.max(0.03, (cur + (cur >= 0 ? 0.5 : 0)) / steps.length) : 0.03;
    if (uploadPct !== null && cur === idx("upload")) frac = (cur + uploadPct / 100) / steps.length;
    q("#bar").style.width = Math.round(frac * 100) + "%";
    var cap = q("#stage-cap"); if (!stageVideo && cur >= 0 && state === "running") cap.textContent = steps[cur][2] + " is working: " + steps[cur][1].toLowerCase();
    var chip = q("#run-status"); chip.textContent = (STATE_TEXT[state] || state) + (videoLabel && state === "running" ? " · " + videoLabel : "");
    chip.className = "status " + (state === "done" ? "ok" : state === "failed" ? "bad" : "");
    q("#cancel").hidden = state !== "running" && state !== "review";
    if (state === "done") q("#run-title").textContent = kind === "upload" ? "Uploaded" : "Your video is ready";
  }

  function showReview(r) {
    if (!r || shown === r.index) return;
    shown = r.index;
    q("#review").hidden = false; q("#r-note").textContent = "";
    q("#review-lang").textContent = r.lang && r.lang !== "en" ? "(" + r.lang + ")" : "";
    q("#review-video").src = "/jobs/" + id + "/review/" + r.index + "/video";
    q("#r-title").value = r.meta.title; q("#r-desc").value = r.meta.description; q("#r-tags").value = (r.meta.tags || []).join(", ");
    q("#r-privacy").value = r.meta.privacy === "none" ? "private" : r.meta.privacy;
    q("#r-upload").disabled = false; q("#r-skip").disabled = false;
    q("#review").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function answer(action) {
    var note = q("#r-note");
    var meta = { title: q("#r-title").value, description: q("#r-desc").value, tags: q("#r-tags").value.split(","), privacy: q("#r-privacy").value };
    q("#r-upload").disabled = true; q("#r-skip").disabled = true;
    aieye.api("POST", "/api/jobs/" + id + "/review/" + shown, { action: action, meta: meta }).then(function (d) {
      if (d.ok) { q("#review").hidden = true; q("#review-video").pause(); }
      else { note.textContent = d.message || "Could not send your answer."; note.className = "note bad"; q("#r-upload").disabled = false; q("#r-skip").disabled = false; }
    });
  }
  q("#r-upload").addEventListener("click", function () { answer("upload"); });
  q("#r-skip").addEventListener("click", function () { answer("skip"); });
  q("#cancel").addEventListener("click", function () {
    if (!confirm("Cancel this run? Anything already spent stays spent, and the topic goes back to Topics as interrupted.")) return;
    aieye.api("POST", "/api/jobs/" + id + "/cancel").then(poll);
  });

  function finish(st, log) {
    terminal = true; clearInterval(timer); q("#review").hidden = true;
    var box = q("#result"), list = q("#result-list"); list.innerHTML = "";
    q("#result-title").textContent = st.state === "done" ? "Finished" : st.state === "cancelled" ? "Cancelled" : "This run did not finish";
    (st.results || []).forEach(function (r) {
      var li = document.createElement("li");
      var a = document.createElement("span"); a.textContent = (r.ok ? "Done: " : "Problem: ") + (r.title || r.topic || "Video") + (r.cost ? "  ($" + r.cost.toFixed(2) + ")" : "");
      li.appendChild(a);
      if (r.url) { var l = document.createElement("a"); l.href = r.url; l.target = "_blank"; l.rel = "noopener"; l.textContent = "Watch on YouTube"; li.appendChild(document.createTextNode(" ")); li.appendChild(l); }
      else if (r.ok && r.path) { var s = document.createElement("span"); s.className = "muted small"; s.textContent = " Kept on this computer (see Library)"; li.appendChild(s); }
      if (r.error) { var e = document.createElement("div"); e.className = "note bad"; e.textContent = r.error; li.appendChild(e); }
      list.appendChild(li);
    });
    if (st.error && !(st.results || []).length) { var li = document.createElement("li"); li.innerHTML = '<div class="note bad"></div>'; li.firstChild.textContent = st.error; list.appendChild(li); }
    box.hidden = false;
    if (log && st.state === "failed") { q("#log").textContent += "\n--- output ---\n" + log; q("#logbox").open = true; }
    paint(st.state);
  }

  function tick() {
    if (startedAt) { var s = Math.max(0, Math.floor(Date.now() / 1000 - startedAt)); q("#clock").textContent = Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }
  }
  function poll() {
    if (terminal) return;
    aieye.api("GET", "/api/jobs/" + id + "?after=" + after).then(function (d) {
      if (!d.status) { q("#run-status").textContent = d.message || "Not found"; clearInterval(timer); return; }
      after = d.next; startedAt = startedAt || d.status.created;
      d.events.forEach(handle);
      var st = d.status;
      if (st.state === "review") showReview(d.review);
      paint(st.state);
      if (st.state === "done" || st.state === "failed" || st.state === "cancelled") finish(st, d.log);
    });
  }
  timer = setInterval(function () { poll(); tick(); }, 1000);
  poll();
  window.addEventListener("beforeunload", function () { clearInterval(timer); });
})();
