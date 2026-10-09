/* docs.js — progressive enhancement for /docs/ (the pages read fully without it): Copy buttons on code blocks and
   the current-section marker in "On this page". */
(function () {
  'use strict';
  document.body.classList.add('js');
  document.querySelectorAll('.code .copy').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = b.closest('.code').querySelector('code').textContent.replace(/\n$/, '');
      (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () {
        b.textContent = 'Copied'; b.setAttribute('data-done', '');
        setTimeout(function () { b.textContent = 'Copy'; b.removeAttribute('data-done'); }, 1500);
      }, function () { b.textContent = 'Press ⌘C'; });
    });
  });
  var links = {};
  document.querySelectorAll('.toc a').forEach(function (a) { links[a.getAttribute('href').slice(1)] = a; });
  if (!('IntersectionObserver' in window) || !Object.keys(links).length) return;
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting || !links[e.target.id]) return;
      Object.keys(links).forEach(function (k) { links[k].removeAttribute('aria-current'); });
      links[e.target.id].setAttribute('aria-current', 'true');
    });
  }, { rootMargin: '-10% 0px -80% 0px' });
  document.querySelectorAll('.prose h2[id], .prose h3[id]').forEach(function (h) { io.observe(h); });
})();
