/* Studio tool pages: live cost, an explicit spend confirmation, then start the run. */
(function () {
  var form = document.getElementById("studio-form"); if (!form) return;
  var tool = form.dataset.tool, prices = JSON.parse(form.dataset.prices || "{}"), models = JSON.parse(form.dataset.models || "[]");
  var icost = JSON.parse(form.dataset.icost || "{}"), fsec = +form.dataset.fsec, fbase = +form.dataset.fbase;
  var $ = function (id) { return document.getElementById(id); };
  var money = function (n) { return "$" + n.toFixed(2); };
  var amount = null;

  function fill(sel, items) {
    var old = sel.value; sel.innerHTML = "";
    items.forEach(function (it) { var o = document.createElement("option"); o.value = it.v; o.textContent = it.t; sel.appendChild(o); });
    if (items.some(function (i) { return String(i.v) === String(old); })) sel.value = old;
  }
  function current() { return models.filter(function (m) { return m.id === $("f-model").value; })[0] || {}; }
  function setupModels() {
    if (!$("f-model")) return;
    if (tool === "clip") {   // models with a known price first, cheapest first; per-token models last
      var rate = function (m) { var r = prices[m.id] || {}, k = r["720p"] ? "720p" : Object.keys(r)[0]; return k && r[k].sec !== null ? r[k].sec : 1e9; };
      models.sort(function (a, b) { return (a.id === "google/veo-3.1-lite" ? -1 : rate(a)) - (b.id === "google/veo-3.1-lite" ? -1 : rate(b)); });   // the tested default first
    }
    fill($("f-model"), models.map(function (m) { return { v: m.id, t: m.label }; }));
    refreshModel();
    $("f-model").addEventListener("change", refreshModel);
  }
  function refreshModel() {
    var m = current();
    fill($("f-res"), (m.res || []).filter(function (r) { return ["480p", "720p", "1080p"].indexOf(r) >= 0; }).map(function (r) { return { v: r, t: r }; }));
    if ($("f-dur")) {
      var d = (m.dur && m.dur.length ? m.dur : [3, 4, 5, 6, 8, 10]).filter(function (x) { return x <= 10; }).sort(function (a, b) { return a - b; });   // shortest (cheapest) first
      fill($("f-dur"), d.map(function (x) { return { v: x, t: x + " seconds" }; }));
    }
    if ($("f-model-note")) $("f-model-note").textContent = m.note || "";
    recalc();
  }
  function recalc() {
    var note = "";
    amount = null;
    if (tool === "stills") { amount = icost[$("f-quality").value] * +$("f-count").value; note = "Billed by OpenAI for the pictures."; }
    else if (tool === "script") { amount = 1.5; note = "Usually $0.50 to $3. No video is made."; }
    else {
      var p = (prices[$("f-model").value] || {})[$("f-res").value];
      if (!p || p.sec === null) { $("cost").textContent = "Unknown"; $("cost-note").textContent = "This model is priced another way, such as per token. The real cost is shown after the run."; return; }
      if (tool === "clip") { amount = p.sec * +$("f-dur").value + p.img; note = "From the model's live price list. The real cost is shown after."; }
      else {
        amount = fbase + p.sec * fsec;
        var worst = fbase + p.sec * fsec * ($("f-qa").checked ? 3 : 1);
        note = "About " + fsec + " seconds of footage plus the script and voice." + ($("f-qa").checked ? " If every clip is redone twice it could reach " + money(worst) + "." : "");
      }
    }
    $("cost").textContent = (tool === "script" ? "About " : "") + money(amount); $("cost-note").textContent = note;
  }

  function params() {
    var p = { tool: tool };
    if ($("f-prompt")) p.prompt = $("f-prompt").value;
    if ($("f-topic")) p.topic = $("f-topic").value;
    if ($("f-notes")) p.notes = $("f-notes").value;
    if (tool === "stills") { p.count = +$("f-count").value; p.quality = $("f-quality").value; }
    if (tool === "clip") { var im = form.querySelector("input[name=image]:checked"); p.image = im ? im.value : ""; p.dur = +$("f-dur").value; }
    if ($("f-model")) { p.model = $("f-model").value; p.res = $("f-res").value; }
    if (tool === "film") { p.qa = $("f-qa").checked; p.ambient = $("f-ambient").checked; }
    return p;
  }
  function note(t) { $("note").textContent = t || ""; $("note").className = "note" + (t ? " bad" : ""); }

  $("go").addEventListener("click", function () {
    note("");
    var p = params();
    if ((p.prompt !== undefined && p.prompt.trim().length < 5) || (p.topic !== undefined && p.topic.trim().length < 5)) { note("Write a few words first (at least 5 characters)."); return; }
    $("confirm-text").textContent = amount === null ? "This will spend money at the model's own price. Continue?" : "This will spend " + (tool === "script" ? "about " : "") + money(amount) + " from your account. Continue?";
    $("confirm").hidden = false; $("go").hidden = true; $("yes").focus();
  });
  $("no").addEventListener("click", function () { $("confirm").hidden = true; $("go").hidden = false; });
  $("yes").addEventListener("click", function () {
    $("yes").disabled = true;
    aieye.api("POST", "/api/studio", params()).then(function (d) {
      if (d.ok) { location.href = "/runs/" + d.job; return; }
      note(d.message || "Could not start."); $("yes").disabled = false; $("confirm").hidden = true; $("go").hidden = false;
    });
  });
  form.addEventListener("input", recalc); form.addEventListener("change", recalc);
  setupModels(); recalc();
})();
