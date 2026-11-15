/* Library page: upload a kept video (with edits), or delete one, several or all of them after a clear confirmation. */
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var all = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  // ---- upload ----
  all(".kept-item").forEach(function (item) {
    var note = $(".k-note", item);
    $(".k-upload", item).addEventListener("click", function (e) {
      var privacy = $(".k-privacy", item).value;
      if (privacy === "public" && !confirm("This video will be public as soon as the upload finishes. Continue?")) return;
      e.target.disabled = true; note.textContent = "Starting…"; note.className = "note";
      aieye.api("POST", "/api/library/upload", { id: item.dataset.id, meta: {
        title: $(".k-title", item).value, description: $(".k-desc", item).value, tags: $(".k-tags", item).value.split(","), privacy: privacy } })
        .then(function (d) {
          if (d.ok) { location.href = aieye.url("/runs/" + d.job); return; }
          note.textContent = d.message || "Could not start the upload."; note.className = "note bad"; e.target.disabled = false;
        });
    });
    $(".k-delete", item).addEventListener("click", function () {
      ask({ ids: [item.dataset.id], count: 1, mb: +item.dataset.size, label: "this video" });
    });
  });

  // ---- selecting ----
  var selAll = $("#sel-all"), delSel = $("#del-selected"), delAll = $("#del-all"), count = $("#sel-count");
  function selected() { return all(".kept-item").filter(function (i) { return $(".k-sel", i).checked; }); }
  function refresh() {
    var s = selected(), mb = s.reduce(function (a, i) { return a + (+i.dataset.size || 0); }, 0);
    count.textContent = s.length ? s.length + " selected (" + mb.toFixed(0) + " MB)" : "None selected";
    delSel.disabled = !s.length; delSel.textContent = s.length ? "Delete selected (" + s.length + ")" : "Delete selected";
    selAll.checked = s.length && s.length === all(".kept-item").length;
  }
  if (selAll) {
    selAll.addEventListener("change", function () { all(".k-sel").forEach(function (c) { c.checked = selAll.checked; }); refresh(); });
    all(".k-sel").forEach(function (c) { c.addEventListener("change", refresh); });
    delSel.addEventListener("click", function () {
      var s = selected();
      ask({ ids: s.map(function (i) { return i.dataset.id; }), count: s.length, mb: s.reduce(function (a, i) { return a + (+i.dataset.size || 0); }, 0),
            label: s.length + " selected video" + (s.length > 1 ? "s" : "") });
    });
    delAll.addEventListener("click", function () {
      ask({ all: true, count: +delAll.dataset.count, mb: +delAll.dataset.mb, label: "all " + delAll.dataset.count + " videos in the Library", typed: true });
    });
  }

  // ---- the confirmation ----
  var dlg = $("#del-dialog"), pending = null;
  function ask(p) {
    pending = p;
    $("#del-text").textContent = "Delete " + p.label + " (about " + Math.max(1, Math.round(p.mb)) + " MB)?";
    $("#del-type").hidden = !p.typed; $("#del-word").value = ""; $("#del-note").textContent = ""; $("#del-go").disabled = !!p.typed;
    dlg.showModal(); (p.typed ? $("#del-word") : $("#del-cancel")).focus();
  }
  $("#del-word").addEventListener("input", function () { $("#del-go").disabled = this.value.trim().toLowerCase() !== "delete"; });
  $("#del-go").addEventListener("click", function () {
    var btn = this; btn.disabled = true;
    var body = pending.all ? { all: true } : { ids: pending.ids, id: pending.ids.length === 1 ? pending.ids[0] : undefined };
    aieye.api("POST", "/api/library/delete", body).then(function (d) {
      if (!d.ok) { $("#del-note").textContent = d.message || "Could not delete."; btn.disabled = false; return; }
      dlg.close(); aieye.toast("Deleted " + d.deleted + " video" + (d.deleted === 1 ? "" : "s") + ", freed " + d.freed_mb + " MB");
      setTimeout(function () { location.reload(); }, 700);
    });
  });
})();
