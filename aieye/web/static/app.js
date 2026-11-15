/* Shared: menu, theme, toast, docs filter, copy buttons, and a small fetch helper used by every page. */
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  window.aieye = {
    url: function (p) { return (document.body.dataset.base || "") + p; },   // pages live under /@handle (or /new)
    api: function (method, url, body) {
      return fetch(url, { method: method, headers: { "Content-Type": "application/json", "X-Requested-With": "aieye" },
                          body: body === undefined ? undefined : JSON.stringify(body) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { d.httpOk = r.ok; return d; }); });
    },
    toast: function (msg) {
      var t = $("#toast"); t.textContent = msg; t.classList.add("show");
      clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove("show"); }, 2600);
    }
  };

  var rail = $("#rail-toggle");
  rail.addEventListener("click", function () {
    var narrow = window.matchMedia("(max-width: 760px)").matches;
    document.body.classList.toggle(narrow ? "rail-open" : "rail-closed");
  });

  $("#theme-toggle").addEventListener("click", function () {
    var root = document.documentElement;
    var dark = root.dataset.theme ? root.dataset.theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("aieye-theme", root.dataset.theme); } catch (e) {}
  });

  var f = $("#docs-filter");
  if (f) f.addEventListener("input", function () {
    var q = f.value.trim().toLowerCase();
    document.querySelectorAll(".docs-nav li").forEach(function (li) { li.hidden = q && li.textContent.toLowerCase().indexOf(q) < 0; });
    document.querySelectorAll(".docs-sec").forEach(function (s) { s.hidden = !s.querySelector("li:not([hidden])"); });
  });

  document.querySelectorAll(".prose pre").forEach(function (pre) {
    var b = document.createElement("button"); b.className = "copy"; b.type = "button"; b.textContent = "Copy";
    b.addEventListener("click", function () {
      var text = pre.querySelector("code") ? pre.querySelector("code").innerText : pre.innerText;
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(
        function () { b.textContent = "Copied"; setTimeout(function () { b.textContent = "Copy"; }, 1500); },
        function () { aieye.toast("Select the text and copy it with Ctrl+C"); });
    });
    pre.appendChild(b);
  });
})();
