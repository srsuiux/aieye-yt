/* Channel page: save the details; put the built-in audience text back. */
(function () {
  var q = function (s) { return document.querySelector(s); };
  var note = q("#channel-note");
  q("#channel-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var body = {
      handle: q("#c-handle").value, url: q("#c-url").value, description: q("#c-desc").value,
      tags: q("#c-tags").value.split(","), audience_notes: q("#c-audience").value,
      top_categories: q("#c-cats").value.split("\n")
    };
    aieye.api("PUT", "/api/channel", body).then(function (d) {
      note.textContent = d.message || "Could not save."; note.className = "note " + (d.ok ? "ok" : "bad");
      if (d.ok) aieye.toast("Channel saved");
    });
  });
  q("#c-audience-reset").addEventListener("click", function () {
    if (!confirm("Replace the text with the built-in default? Save to keep it.")) return;
    aieye.api("GET", "/api/channel/default-audience").then(function (d) { if (d.text) q("#c-audience").value = d.text; });
  });
})();
