/* Connections page: save, test and remove keys; add the YouTube client file; sign in and out. */
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  function note(el, ok, msg) { el.textContent = msg; el.className = "note " + (ok ? "ok" : "bad"); }
  function setStatus(card, k) {
    var s = $("[data-status]", card);
    s.textContent = k.set ? "Saved " + k.hint : "Not set"; s.className = "status " + (k.set ? "ok" : "off");
    $("[data-test]", card).disabled = !k.set; $("[data-remove]", card).disabled = !k.set;
    $("input", card).placeholder = k.set ? "Paste a new key to replace it" : "Paste your key";
  }

  document.querySelectorAll(".conn[data-key]").forEach(function (card) {
    var name = card.dataset.key, input = $("input", card), n = $("[data-note]", card);
    $("[data-key-form]", card).addEventListener("submit", function (e) {
      e.preventDefault();
      aieye.api("PUT", "/api/connections/keys/" + name, { value: input.value }).then(function (d) {
        if (!d.ok) return note(n, false, d.message || "Could not save the key.");
        input.value = ""; setStatus(card, d.key); note(n, true, "Saved to .env. Press Test to check it works."); aieye.toast("Key saved");
      });
    });
    $("[data-test]", card).addEventListener("click", function () {
      note(n, true, "Checking…");
      aieye.api("POST", "/api/connections/keys/" + name + "/test").then(function (d) { note(n, !!d.ok, d.message || "No answer."); });
    });
    $("[data-remove]", card).addEventListener("click", function () {
      if (!confirm("Remove this key from .env?")) return;
      aieye.api("DELETE", "/api/connections/keys/" + name).then(function (d) {
        if (d.ok) { setStatus(card, d.key); note(n, true, "Key removed."); }
      });
    });
  });

  var yt = $("#youtube"); if (!yt) return;
  var file = $("#yt-file"), save = $("#yt-save"), signin = $("#yt-signin"), signout = $("#yt-signout"), n = $("[data-yt-note]", yt), badge = $("[data-yt-status]", yt);
  function render(s) {
    var full = s.client_file && s.signed_in;
    badge.textContent = full ? "Signed in" : s.client_file ? "Client file saved" : "Not set"; badge.className = "status " + (full ? "ok" : "off");
    signin.disabled = !s.client_file || s.sign_in.state === "waiting"; signout.disabled = !s.signed_in;
    if (s.sign_in.state === "waiting") note(n, true, s.sign_in.message);
    if (s.sign_in.state === "error") note(n, false, s.sign_in.message);
  }
  file.addEventListener("change", function () { save.disabled = !file.files.length; });
  save.addEventListener("click", function () {
    var fr = new FileReader();
    fr.onload = function () {
      aieye.api("PUT", "/api/connections/youtube/client", { text: String(fr.result) }).then(function (d) {
        if (!d.ok) return note(n, false, d.message || "Could not save the file.");
        note(n, true, "Client file saved. Now sign in."); render(d.youtube); file.value = ""; save.disabled = true;
      });
    };
    fr.readAsText(file.files[0]);
  });
  var poll;
  function watch() {
    clearInterval(poll);
    poll = setInterval(function () {
      aieye.api("GET", "/api/connections").then(function (d) {
        render(d.youtube);
        if (d.youtube.sign_in.state !== "waiting") { clearInterval(poll); if (d.youtube.sign_in.state === "done") note(n, true, "Signed in to YouTube."); }
      });
    }, 1500);
  }
  signin.addEventListener("click", function () {
    aieye.api("POST", "/api/connections/youtube/sign-in").then(function (d) {
      if (!d.ok) return note(n, false, d.message); render(d.youtube); watch();
    });
  });
  signout.addEventListener("click", function () {
    aieye.api("DELETE", "/api/connections/youtube/sign-in").then(function (d) { render(d.youtube); note(n, true, "Signed out. The client file is still saved."); });
  });
  aieye.api("GET", "/api/connections").then(function (d) { render(d.youtube); if (d.youtube.sign_in.state === "waiting") watch(); });
})();
