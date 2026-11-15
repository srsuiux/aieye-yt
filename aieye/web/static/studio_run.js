/* Studio run page: shows progress lines and cost, then the files that were made. */
(function () {
  var root = document.getElementById("srun"), id = root.dataset.id, $ = function (s) { return document.getElementById(s); };
  var after = 0, timer, startedAt = null, done = false;
  var NAMES = { running: "Running", done: "Done", failed: "Failed", cancelled: "Cancelled", review: "Running" };
  function handle(ev) {
    if (ev.kind === "cost") $("cost").textContent = "$" + ev.total.toFixed(4);
    else if (ev.kind === "log") {
      var pre = $("log"); pre.textContent += "[" + (ev.time || "").slice(11, 19) + "] " + ev.message + "\n"; pre.scrollTop = pre.scrollHeight;
      $("now").textContent = ev.message.slice(0, 140);
    } else if (ev.kind === "section") $("now").textContent = ev.title;
  }
  function show(st, log) {
    done = true; clearInterval(timer); $("bar").className = ""; $("bar").style.width = st.state === "done" ? "100%" : "0%";
    $("cancel").hidden = true; $("now").textContent = "";
    $("run-title").textContent = st.state === "done" ? "Finished" : st.state === "cancelled" ? "Cancelled" : "This run did not finish";
    $("result-title").textContent = $("run-title").textContent; $("result").hidden = false;
    (st.results || []).forEach(function (r) {
      (r.files || []).forEach(function (f) {
        var fig = document.createElement("figure"), el;
        if (f.kind === "video") { el = document.createElement("video"); el.controls = true; el.playsInline = true; el.preload = "metadata"; el.src = f.url; }
        else if (f.kind === "image") { el = document.createElement("a"); el.href = f.url; el.target = "_blank"; el.rel = "noopener"; var im = document.createElement("img"); im.src = f.url; im.alt = f.name; el.appendChild(im); }
        else { el = document.createElement("a"); el.href = f.url; el.target = "_blank"; el.rel = "noopener"; el.className = "file-link"; el.textContent = "Open the script"; }
        fig.appendChild(el);
        if (f.kind !== "text") { var cap = document.createElement("figcaption"); cap.textContent = f.name; fig.appendChild(cap); }
        $("files").appendChild(fig);
      });
    });
    if (st.state !== "done") { $("err").textContent = st.error || ""; if (log) { $("log").textContent += "\n--- output ---\n" + log; $("logbox").open = true; } }
  }
  function poll() {
    if (done) return;
    aieye.api("GET", "/api/jobs/" + id + "?after=" + after).then(function (d) {
      if (!d.status) { $("run-status").textContent = d.message || "Not found"; clearInterval(timer); return; }
      after = d.next; startedAt = startedAt || d.status.created; d.events.forEach(handle);
      var st = d.status; $("run-status").textContent = NAMES[st.state] || st.state; $("run-status").className = "status " + (st.state === "done" ? "ok" : st.state === "failed" ? "bad" : "");
      if (st.state === "done" || st.state === "failed" || st.state === "cancelled") show(st, d.log);
    });
  }
  $("cancel").addEventListener("click", function () {
    if (!confirm("Cancel this run? Anything already spent stays spent.")) return;
    aieye.api("POST", "/api/jobs/" + id + "/cancel").then(poll);
  });
  timer = setInterval(function () {
    poll();
    if (startedAt) { var s = Math.max(0, Math.floor(Date.now() / 1000 - startedAt)); $("clock").textContent = Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }
  }, 1000);
  poll();
})();
