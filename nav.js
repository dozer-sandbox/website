/* Header menu on narrow screens: a button that opens the site links as a panel. Runs in <head>, not deferred, so the
   page never paints the wide header first. Without it the links stay visible (wrapped) in the header. */
(function () {
  'use strict';
  var root = document.documentElement;
  root.classList.add('js-nav');
  function init() {
    var nav = document.querySelector('.nav');
    var btn = nav && nav.querySelector('.nav-toggle');
    var panel = document.getElementById('nav-panel');
    if (!btn || !panel) return;
    var open = false;
    function set(on, refocus) {
      open = on;
      nav.classList.toggle('open', on);
      btn.setAttribute('aria-expanded', on ? 'true' : 'false');
      if (!on && refocus) btn.focus();
    }
    btn.addEventListener('click', function () { set(!open, false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && open) { e.preventDefault(); set(false, true); }
    });
    document.addEventListener('click', function (e) { if (open && !nav.contains(e.target)) set(false, false); });
    panel.addEventListener('click', function (e) { if (e.target.closest && e.target.closest('a')) set(false, false); });
    if (window.matchMedia) {
      var mq = matchMedia('(min-width: 1001px)');
      var close = function (e) { if (e.matches && open) set(false, false); };
      if (mq.addEventListener) mq.addEventListener('change', close); else if (mq.addListener) mq.addListener(close);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
