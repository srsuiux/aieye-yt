/* Library page: upload a kept video (with edits) or delete it. */
(function () {
  function one(root, sel) { return root.querySelector(sel); }
  document.querySelectorAll(".kept-item").forEach(function (item) {
    var note = one(item, ".k-note");
    one(item, ".k-upload").addEventListener("click", function (e) {
      var privacy = one(item, ".k-privacy").value;
      if (privacy === "public" && !confirm("This video will be public as soon as the upload finishes. Continue?")) return;
      e.target.disabled = true; note.textContent = "Starting…"; note.className = "note";
      aieye.api("POST", "/api/library/upload", { id: item.dataset.id, meta: {
        title: one(item, ".k-title").value, description: one(item, ".k-desc").value, tags: one(item, ".k-tags").value.split(","), privacy: privacy } })
        .then(function (d) {
          if (d.ok) { location.href = aieye.url("/runs/" + d.job); return; }
          note.textContent = d.message || "Could not start the upload."; note.className = "note bad"; e.target.disabled = false;
        });
    });
    one(item, ".k-delete").addEventListener("click", function () {
      if (!confirm("Delete this video from your computer? This cannot be undone.")) return;
      aieye.api("POST", "/api/library/delete", { id: item.dataset.id }).then(function (d) { if (d.ok) item.remove(); else note.textContent = d.message; });
    });
  });
})();
