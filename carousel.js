/* Screenshot carousel: buttons, dots and arrow keys over a CSS scroll-snap strip.  The mouse wheel over the
   screenshots moves the slides (see below). Without this file the strip is still scrollable. */
(function () {
  'use strict';
  var track = document.getElementById('car-track');
  if (!track) return;
  var slides = Array.prototype.slice.call(track.querySelectorAll('.slide'));
  // The browser's lazy loading does not reliably load images inside a sideways-scrolling strip (slides 3–7 stayed
  // blank in a real Chrome run): keep the page light on arrival, but load every screenshot once the section is
  // near the screen.
  (function eagerWhenNear() {
    var imgs = track.querySelectorAll('img[loading="lazy"]');
    function load() { Array.prototype.forEach.call(imgs, function (im) { im.loading = 'eager'; }); }
    if (!('IntersectionObserver' in window)) { load(); return; }
    var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { load(); io.disconnect(); } },
                                      { rootMargin: '800px 0px' });
    io.observe(track);
  })();
  if (slides.length < 2) return;
  var NS = 'http://www.w3.org/2000/svg';
  function arrow(dir) {
    var s = document.createElementNS(NS, 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('aria-hidden', 'true');
    var p = document.createElementNS(NS, 'path'); p.setAttribute('d', dir < 0 ? 'M15 5l-7 7 7 7' : 'M9 5l7 7-7 7');
    s.appendChild(p); return s;
  }
  function btn(cls, label) {
    var b = document.createElement('button'); b.type = 'button'; b.className = cls; b.setAttribute('aria-label', label); return b;
  }
  var ui = document.createElement('div'); ui.className = 'car-ui';
  var prev = btn('car-btn', 'Previous screenshot'); prev.appendChild(arrow(-1));
  var next = btn('car-btn', 'Next screenshot'); next.appendChild(arrow(1));
  var dots = document.createElement('div'); dots.className = 'car-dots';
  var count = document.createElement('span'); count.className = 'car-count'; count.setAttribute('aria-live', 'polite');
  var dotEls = slides.map(function (s, i) {
    var d = btn('car-dot', 'Go to screenshot ' + (i + 1)); d.addEventListener('click', function () { go(i); }); dots.appendChild(d); return d;
  });
  ui.appendChild(prev); ui.appendChild(dots); ui.appendChild(count); ui.appendChild(next);
  track.parentNode.appendChild(ui);

  var cur = 0, raf = 0;
  function index() {
    var left = track.getBoundingClientRect().left, best = 0, bd = Infinity;
    slides.forEach(function (s, i) { var d = Math.abs(s.getBoundingClientRect().left - left - 4); if (d < bd) { bd = d; best = i; } });
    var atEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
    return atEnd ? slides.length - 1 : best;
  }
  function paint() {
    cur = index();
    dotEls.forEach(function (d, i) { if (i === cur) d.setAttribute('aria-current', 'true'); else d.removeAttribute('aria-current'); });
    prev.disabled = cur === 0; next.disabled = cur === slides.length - 1;
    count.textContent = (cur + 1) + ' / ' + slides.length;
  }
  function go(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    var left = Math.min(slides[i].offsetLeft - track.offsetLeft - 4, track.scrollWidth - track.clientWidth);
    track.scrollTo({ left: left, behavior: 'smooth' });
  }
  prev.addEventListener('click', function () { go(cur - 1); });
  next.addEventListener('click', function () { go(cur + 1); });
  track.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') { e.preventDefault(); go(cur + 1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); go(cur - 1); }
    else if (e.key === 'Home') { e.preventDefault(); go(0); }
    else if (e.key === 'End') { e.preventDefault(); go(slides.length - 1); }
  });
  track.addEventListener('scroll', function () { cancelAnimationFrame(raf); raf = requestAnimationFrame(paint); }, { passive: true });

  // ---- the mouse wheel over the screenshots (owner: "only hovering over carousel images activates the horizontal
  // scroll … otherwise there is no way to escape") ----
  // While the pointer is over the band of screenshots AND it is fully on screen, the wheel (or a trackpad's
  // vertical swipe) moves the slides sideways. Anywhere else — the captions, below, beside — the page scrolls. At the
  // first or last slide the wheel goes back to the page, so it never traps the reader. When the wheel stops, the
  // strip settles on the nearest slide.
  var settle = 0;
  function navH() { var n = document.querySelector('.nav'); return n ? n.getBoundingClientRect().height : 0; }
  track.addEventListener('wheel', function (e) {
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;             // a sideways trackpad swipe scrolls the strip itself
    // The screenshots' band: from the top to the bottom of the images, across the whole strip (the gaps between
    // slides included, or a still pointer would fall into a gap as the slides move and the page would take over).
    var t = track.getBoundingClientRect(), r = slides[0].querySelector('.frame').getBoundingClientRect();
    if (e.clientX < t.left || e.clientX > t.right || e.clientY < r.top || e.clientY > r.bottom) return;   // captions etc.
    if (r.top < navH() - 1 || r.bottom > window.innerHeight + 1) return;   // not fully on screen: let the page bring it in
    var d = e.deltaY * (e.deltaMode === 1 ? 32 : e.deltaMode === 2 ? track.clientWidth : 1);
    var max = track.scrollWidth - track.clientWidth;
    if ((d > 0 && track.scrollLeft >= max - 1) || (d < 0 && track.scrollLeft <= 1)) return;   // at an end: the page
    e.preventDefault();
    track.style.scrollSnapType = 'none'; track.style.scrollBehavior = 'auto';
    track.scrollLeft = Math.max(0, Math.min(max, track.scrollLeft + d));
    clearTimeout(settle);
    settle = setTimeout(function () { track.style.scrollBehavior = ''; track.style.scrollSnapType = ''; go(index()); }, 160);
  }, { passive: false });
  window.addEventListener('resize', paint);
  paint();
})();
