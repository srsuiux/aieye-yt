/* Welcome tour: a short walk through the pages, one step at a time. Skippable, reopenable with the ? button. */
(function () {
  var STEPS = [
    { title: "Welcome to AI Eye", body: "AI Eye turns a topic into a finished YouTube Short: script, narration, pictures and captions. This one-minute tour shows what each page is for. You can skip it at any time.", center: true },
    { target: "connections", title: "Connections: start here", body: "Save your OpenAI key, which pays for the script, voice and pictures. Add YouTube later if you want uploads. Keys stay on this computer." },
    { target: "settings", title: "Settings", body: "Your defaults: picture style and quality, who can watch uploads, and the narrator. Advanced holds the models, the look of the video and the daily upload limit." },
    { target: "channel", title: "Channel", body: "Your channel's name, description and tags, added to every upload, plus notes on who your videos are for so topic ideas fit." },
    { target: "topics", title: "Topics", body: "The queue of ideas that videos are made from. Add your own, change the order, and see what has already been made, so nothing repeats." },
    { target: "create", title: "Create", body: "Make a video. Choose the topic, languages and look, see the cost, and confirm before anything is spent. Then watch each step and review the video before it uploads." },
    { target: "library", title: "Library", body: "Videos that are made but not uploaded yet, and the ones already live. Preview them, edit the title and description, and upload when you are ready." },
    { target: "studio", title: "Studio", body: "Optional experiments with AI video: make pictures, turn one into a clip, write only a script, or make a whole film. Each shows its cost before it spends anything." },
    { target: "docs", title: "Docs", body: "Guides for every page, how to get each key, how to set up YouTube, and fixes for common problems." },
    { title: "You are ready", body: "Add your OpenAI key to begin. Reopen this tour any time with the ? button at the top.", center: true, last: true }
  ];

  var layer, dim, spot, card, i = 0, hasKey = null, opener = null;

  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html) e.innerHTML = html; return e; }
  function save(state) { try { aieye.api("PUT", "/api/ui/tour", { state: state }); } catch (e) {} }

  function build() {
    layer = el("div", "tour-layer");
    dim = el("div", "tour-dim");
    spot = el("div", "tour-spot");
    card = el("div", "tour-card"); card.setAttribute("role", "dialog"); card.setAttribute("aria-modal", "true"); card.setAttribute("aria-labelledby", "tour-title");
    layer.appendChild(dim); layer.appendChild(spot); layer.appendChild(card); document.body.appendChild(layer);
    layer.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { end("skipped"); }
      else if (e.key === "ArrowRight") { next(); }
      else if (e.key === "ArrowLeft") { back(); }
      else if (e.key === "Tab") {
        var f = card.querySelectorAll("button"), first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    });
  }

  function place(step) {
    var narrow = window.matchMedia("(max-width: 760px)").matches;
    var t = step.target && document.querySelector('[data-tour="' + step.target + '"]');
    card.style.cssText = "";
    if (!t || step.center) {
      spot.style.display = "none"; dim.style.clipPath = "none";
      card.classList.add("center"); return;
    }
    card.classList.remove("center"); spot.style.display = "block";
    var r = t.getBoundingClientRect(), pad = 4;
    var x1 = r.left - pad, y1 = r.top - pad, x2 = r.right + pad, y2 = r.bottom + pad;
    dim.style.clipPath = "polygon(evenodd, 0 0, 100% 0, 100% 100%, 0 100%, 0 0, " + x1 + "px " + y1 + "px, " + x1 + "px " + y2 + "px, " + x2 + "px " + y2 + "px, " + x2 + "px " + y1 + "px, " + x1 + "px " + y1 + "px)";
    spot.style.left = (x1 - 2) + "px"; spot.style.top = (y1 - 2) + "px";        // the ring sits just outside the hole
    spot.style.width = (x2 - x1 + 4) + "px"; spot.style.height = (y2 - y1 + 4) + "px";
    if (narrow) { card.style.left = "16px"; card.style.right = "16px"; card.style.bottom = "16px"; return; }
    card.style.left = (r.right + 20) + "px";
    var top = Math.min(Math.max(16, r.top - 12), window.innerHeight - card.offsetHeight - 16);
    card.style.top = top + "px";
  }

  function render() {
    var s = STEPS[i], total = STEPS.length;
    var dots = ""; for (var k = 0; k < total; k++) dots += '<i class="' + (k === i ? "on" : k < i ? "past" : "") + '"></i>';
    var primary = s.last ? (hasKey ? "Close" : "Add my OpenAI key") : (i === 0 ? "Start the tour" : "Next");
    card.innerHTML = '<p class="tour-count">' + (i + 1) + ' of ' + total + '</p><h2 id="tour-title"></h2><p class="tour-body"></p>' +
      '<div class="tour-dots" aria-hidden="true">' + dots + '</div>' +
      '<div class="tour-actions"><button type="button" class="link-btn" data-skip>' + (s.last ? "" : "Skip tour") + '</button><span class="grow"></span>' +
      (i > 0 ? '<button type="button" class="btn ghost" data-back>Back</button>' : "") + '<button type="button" class="btn" data-next></button></div>';
    card.querySelector("h2").textContent = s.title; card.querySelector(".tour-body").textContent = s.body;
    card.querySelector("[data-next]").textContent = primary;
    var skip = card.querySelector("[data-skip]"); if (s.last) skip.remove();
    card.querySelector("[data-next]").addEventListener("click", function () { s.last ? finish() : next(); });
    if (skip.parentNode) skip.addEventListener("click", function () { end("skipped"); });
    var b = card.querySelector("[data-back]"); if (b) b.addEventListener("click", back);
    place(s);
    card.querySelector("[data-next]").focus();
  }

  function next() { if (i < STEPS.length - 1) { i++; render(); } }
  function back() { if (i > 0) { i--; render(); } }
  function finish() { end("done"); if (!hasKey) location.href = aieye.url("/connections"); }
  function end(state) {
    save(state);
    document.body.classList.remove("rail-open");
    if (layer) { layer.remove(); layer = null; }
    window.removeEventListener("resize", onResize);
    if (opener && opener.focus) opener.focus();
  }
  function onResize() { if (layer) place(STEPS[i]); }

  function start(from) {
    if (layer) return;
    opener = from || null; i = 0;
    var rail = document.querySelector(".rail");
    if (window.matchMedia("(max-width: 760px)").matches) document.body.classList.add("rail-open");
    else document.body.classList.remove("rail-closed");
    if (rail) rail.hidden = false;
    build(); window.addEventListener("resize", onResize);
    aieye.api("GET", "/api/connections").then(function (d) {
      hasKey = (d.keys || []).some(function (k) { return k.name === "OPENAI_API_KEY" && k.set; });
    }).catch(function () { hasKey = false; }).then(render);
  }

  document.getElementById("tour-start").addEventListener("click", function (e) { start(e.currentTarget); });
  document.querySelectorAll("[data-start-tour]").forEach(function (b) { b.addEventListener("click", function () { start(b); }); });
  if (document.body.dataset.autoTour === "1") setTimeout(function () { start(null); }, 500);
})();
