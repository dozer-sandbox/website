/* Screenshot carousel: buttons, dots and arrow keys over a CSS scroll-snap strip. On a wide screen with a mouse or
   trackpad it is PINNED (owner: "scrolling the page will get to the carousel and continuing to scroll will scroll
   horizontally until the end and then the page will resume scrolling vertically"): the carousel sticks under the
   header and the page's own vertical scroll moves the slides sideways, one pixel for one pixel — wheel, trackpad,
   keyboard or scrollbar alike, and backwards too. It pins only when it fits in the window; on phones and touch
   screens it stays a swipe strip. Without this file the strip is still scrollable. */
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
    if (pin.on) { window.scrollTo({ top: pin.start + left, behavior: 'smooth' }); return; }
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

  // ---- pinned mode ----
  var carousel = track.closest('.carousel');
  var spacer = document.createElement('div'); spacer.className = 'car-spacer'; spacer.setAttribute('aria-hidden', 'true');
  carousel.parentNode.insertBefore(spacer, carousel.nextSibling);
  var pin = { on: false, start: 0, extra: 0, top: 0 };
  var wide = window.matchMedia('(min-width: 861px) and (pointer: fine)');
  function navH() { var n = document.querySelector('.nav'); return n ? n.getBoundingClientRect().height : 0; }
  function layout() {
    var was = pin.on;
    pin.on = false; carousel.classList.remove('pinned'); spacer.style.height = '0px';
    track.style.scrollSnapType = ''; track.style.overflowX = '';
    pin.top = navH() + 24;
    var fits = carousel.offsetHeight <= window.innerHeight - pin.top - 16;
    pin.extra = track.scrollWidth - track.clientWidth;
    if (wide.matches && fits && pin.extra > 0) {
      pin.on = true;
      carousel.classList.add('pinned');
      carousel.style.top = pin.top + 'px';
      track.style.scrollSnapType = 'none'; track.style.overflowX = 'hidden';
      spacer.style.height = pin.extra + 'px';
      // The page's scroll position at which the carousel reaches its pinned place.
      pin.start = carousel.getBoundingClientRect().top + window.scrollY - pin.top;
      sync();
    } else if (was) { track.scrollLeft = 0; }
    paint();
  }
  function sync() {
    if (!pin.on) return;
    var x = Math.max(0, Math.min(pin.extra, window.scrollY - pin.start));
    if (Math.abs(track.scrollLeft - x) > 0.5) track.scrollLeft = x;
  }
  window.addEventListener('scroll', function () { sync(); }, { passive: true });
  window.addEventListener('resize', function () { cancelAnimationFrame(raf); raf = requestAnimationFrame(layout); });
  if (wide.addEventListener) wide.addEventListener('change', layout);
  Array.prototype.forEach.call(track.querySelectorAll('img'), function (im) { if (!im.complete) im.addEventListener('load', layout, { once: true }); });
  layout();
})();
