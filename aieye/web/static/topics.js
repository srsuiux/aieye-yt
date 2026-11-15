/* Topics page: add (with a duplicate warning), reorder, remove, return an interrupted topic to the queue. */
(function () {
  var q = function (s) { return document.querySelector(s); };
  var note = q("#topic-note"), box = q("#dup-box");
  function add(force) {
    aieye.api("POST", "/api/topics", { title: q("#t-title").value, hook: q("#t-hook").value, force: !!force }).then(function (d) {
      if (d.ok) return location.reload();
      if (d.duplicate) { q("#dup-msg").textContent = d.message; box.hidden = false; note.textContent = ""; return; }
      box.hidden = true; note.textContent = d.message || "Could not add."; note.className = "note bad";
    });
  }
  q("#topic-form").addEventListener("submit", function (e) { e.preventDefault(); add(false); });
  q("#dup-force").addEventListener("click", function () { add(true); });
  document.querySelectorAll("[data-act]").forEach(function (b) {
    b.addEventListener("click", function () {
      var id = b.closest(".qitem").dataset.id, act = b.dataset.act;
      if (act === "delete" && !confirm("Remove this topic from the queue?")) return;
      aieye.api("POST", "/api/topics/" + id + "/" + act).then(function (d) {
        if (d.ok) location.reload(); else aieye.toast(d.message || "Could not do that.");
      });
    });
  });
})();
