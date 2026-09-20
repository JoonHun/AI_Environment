/* Joons Wiki — interactions. No dependencies. */
(function () {
  "use strict";

  // ---- top-bar search: "/" focuses, Enter navigates ----
  var topSearch = document.querySelector('.top .search input');
  var sideSearch = document.querySelector('.side-search input');
  if (topSearch) {
    document.addEventListener('keydown', function (e) {
      var tag = (document.activeElement && document.activeElement.tagName) || '';
      if (e.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
        e.preventDefault(); topSearch.focus();
      }
      if (e.key === 'Enter' && document.activeElement === topSearch) {
        var q = topSearch.value.trim();
        if (q) location.href = '/search?q=' + encodeURIComponent(q);
      }
    });
  }
  if (sideSearch) {
    sideSearch.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        var q = sideSearch.value.trim();
        location.href = (q ? '/search?q=' : '/') + (q ? '' : '');
        if (q) location.href = '/search?q=' + encodeURIComponent(q);
      }
    });
  }

  // ---- reading progress (page.html only) ----
  var prog = document.getElementById('progress');
  if (prog) {
    var onScroll = function () {
      var h = document.documentElement;
      var max = (h.scrollHeight - h.clientHeight);
      var p = max > 0 ? (h.scrollTop / max) * 100 : 0;
      prog.style.width = p + '%';
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // ---- copy buttons on code blocks ----
  function mountCopy(pre) {
    if (!pre || pre.dataset.copied) return;
    pre.dataset.copied = '1';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'copy-btn';
    btn.textContent = 'copy';
    var code = pre.querySelector('code');
    btn.addEventListener('click', function () {
      var txt = code ? code.innerText : pre.innerText;
      navigator.clipboard && navigator.clipboard.writeText(txt).then(function () {
        btn.textContent = 'copied'; btn.classList.add('done');
        setTimeout(function () { btn.textContent = 'copy'; btn.classList.remove('done'); }, 1400);
      });
    });
    pre.appendChild(btn);
  }
  document.querySelectorAll('pre.wiki-code').forEach(mountCopy);

  // ---- TOC scroll-spy (page.html only) ----
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc-list a[data-anchor]'));
  if (tocLinks.length) {
    var heads = tocLinks.map(function (a) {
      var id = a.getAttribute('data-anchor');
      var el = document.getElementById(id);
      return el ? { a: a, el: el } : null;
    }).filter(Boolean);
    var current = null;
    function setActive(el) {
      if (el === current) return;
      current = el;
      heads.forEach(function (h) { h.a.classList.toggle('active', h === el); });
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          var match = heads.find(function (h) { return h.el === en.target; });
          if (match) setActive(match);
        }
      });
    }, { rootMargin: '0px 0px -68% 0px', threshold: 0 });
    heads.forEach(function (h) { io.observe(h.el); });
  }

  // ---- sidebar toggle (mobile) ----
  var menuBtn = document.querySelector('.iconbtn.menu');
  var sidebar = document.getElementById('sidebar');
  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', function () { sidebar.classList.toggle('closed'); });
  }
})();
