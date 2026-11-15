/* Settings page: save the defaults and the advanced values; reset one field or all of them. */
(function () {
  var q = function (s, r) { return (r || document).querySelector(s); };
  var qa = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function note(el, ok, msg) { el.textContent = msg; el.className = "note " + (ok ? "ok" : "bad"); }

  var priv = q("#d-upload_privacy"), warn = q("#public-warn");
  function showWarn() { warn.hidden = priv.value !== "public"; }
  priv.addEventListener("change", showWarn); showWarn();

  q("#defaults-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var v = {};
    qa("#defaults-form [data-key]").forEach(function (el) { v[el.dataset.key] = el.value; });
    aieye.api("PUT", "/api/settings/defaults", v).then(function (d) {
      note(q("#defaults-note"), !!d.ok, d.message || "Could not save.");
      if (d.ok) aieye.toast("Defaults saved");
    });
  });

  function read(f) {
    var el = q("[data-key]", f);
    if (f.dataset.kind === "voices") return qa("input:checked", el).map(function (i) { return i.value; });
    return el.value;
  }
  function write(f, val) {
    var el = q("[data-key]", f);
    if (f.dataset.kind === "voices") qa("input", el).forEach(function (i) { i.checked = val.indexOf(i.value) >= 0; });
    else el.value = val;
  }
  function mark(f, changed) { q(".changed", f).hidden = !changed; q("[data-reset]", f).hidden = !changed; }
  function isDefault(f) { return JSON.stringify(read(f)) === JSON.stringify(JSON.parse(f.dataset.default)) || String(read(f)) === String(JSON.parse(f.dataset.default)); }

  q("#adv-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var v = {};
    qa("#adv-form .field").forEach(function (f) { v[f.dataset.field] = read(f); });
    aieye.api("PUT", "/api/settings/advanced", { values: v }).then(function (d) {
      note(q("#adv-note"), !!d.ok, d.message || "Could not save.");
      if (d.ok) { aieye.toast("Advanced settings saved"); qa("#adv-form .field").forEach(function (f) { mark(f, !isDefault(f)); }); }
    });
  });
  qa("#adv-form [data-reset]").forEach(function (b) {
    b.addEventListener("click", function () {
      var f = b.closest(".field");
      aieye.api("POST", "/api/settings/advanced/reset", { keys: [f.dataset.field] }).then(function () {
        write(f, JSON.parse(f.dataset.default)); mark(f, false); aieye.toast("Back to the default");
      });
    });
  });
  q("#adv-reset-all").addEventListener("click", function () {
    if (!confirm("Reset every advanced setting to its default?")) return;
    aieye.api("POST", "/api/settings/advanced/reset", {}).then(function () {
      qa("#adv-form .field").forEach(function (f) { write(f, JSON.parse(f.dataset.default)); mark(f, false); });
      aieye.toast("All advanced settings reset");
    });
  });
})();
