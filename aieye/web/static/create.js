/* Create page: live cost estimate, two-step confirmation, start the run. */
(function () {
  var q = function (s) { return document.querySelector(s); };
  var qa = function (s) { return Array.prototype.slice.call(document.querySelectorAll(s)); };
  var form = q("#create-form");
  var cost = JSON.parse(form.dataset.cost), left = parseInt(form.dataset.left, 10), extra = parseFloat(form.dataset.extra);
  var signed = form.dataset.signed === "1";

  function val(name) { var el = q("[name=" + name + "]:checked") || q("[name=" + name + "]"); return el ? el.value : ""; }
  function langs() { return qa("[name=lang]:checked").map(function (i) { return i.value; }); }

  function params() {
    return {
      count: parseInt(val("count"), 10), source: val("source"), topic: q("#topic").value, languages: langs(),
      image_quality: val("image_quality"), image_style: val("image_style"), tts_voice: val("tts_voice"), batch_voice: val("batch_voice"),
      upload_privacy: val("upload_privacy"), review: q("#f-review").checked
    };
  }
  function summary() {
    var p = params();
    if (p.source === "custom") { p.count = 1; q("[name=count][value='1']").checked = true; }
    var per = cost[p.image_quality].one + extra * Math.max(0, p.languages.length - 1);
    return { p: p, per: per, total: per * p.count };
  }
  function render() {
    var s = summary(), p = s.p;
    q("#topic-wrap").hidden = p.source !== "custom";
    qa("[name=count][value='3']").forEach(function (i) { i.disabled = p.source === "custom"; });
    q("#est").textContent = "$" + s.total.toFixed(2);
    q("#est-note").textContent = p.count > 1 ? "about $" + s.per.toFixed(2) + " each, an estimate" : "an estimate, shown again before you start";
    q("#limit-note").textContent = left + " of today's upload slots left.";
    var rev = q("#f-review"), none = p.upload_privacy === "none";
    rev.disabled = none; if (none) rev.checked = false;
    q("#review-hint").style.opacity = none ? ".5" : "1";
    var w = q("#pub-warn");
    if (p.upload_privacy === "public" && !p.review) { w.hidden = false; w.textContent = "Public with no review: each video is published the moment it is made."; }
    else if (p.upload_privacy !== "none" && !signed) { w.hidden = false; w.textContent = "YouTube is not connected, so the upload step will fail."; }
    else w.hidden = true;
    q("#go").textContent = p.count > 1 ? "Make " + p.count + " videos" : "Make video";
  }
  form.addEventListener("input", function () { q("#confirm").hidden = true; q("#form-error").textContent = ""; render(); });
  render();

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var s = summary(), p = s.p, err = q("#form-error");
    if (!p.languages.length) { err.textContent = "Choose at least one language."; return; }
    if (p.source === "custom" && p.topic.trim().length < 5) { err.textContent = "Write your topic first."; return; }
    var up = p.upload_privacy === "none" ? "It will not be uploaded." : p.review ? "You review each one before it uploads (" + p.upload_privacy + ")." : "It uploads as " + p.upload_privacy + " when made.";
    q("#confirm-text").textContent = "This spends about $" + s.total.toFixed(2) + " of your credit. " + up;
    q("#confirm").hidden = false; q("#go").hidden = true;
  });
  q("#confirm-cancel").addEventListener("click", function () { q("#confirm").hidden = true; q("#go").hidden = false; });
  q("#confirm-go").addEventListener("click", function () {
    var btn = q("#confirm-go"); btn.disabled = true; btn.textContent = "Starting…";
    aieye.api("POST", "/api/jobs", params()).then(function (d) {
      if (d.ok) { location.href = "/runs/" + d.job; return; }
      q("#form-error").textContent = d.message || "Could not start."; q("#confirm").hidden = true; q("#go").hidden = false;
      btn.disabled = false; btn.textContent = "Start and spend";
    });
  });
})();
