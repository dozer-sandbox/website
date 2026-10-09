/* Screenshot carousel: buttons, dots and arrow keys over a CSS scroll-snap strip.
   Without this file the strip is still scrollable. */
(function () {
  'use strict';
  var track = document.getElementById('car-track');
  if (!track) return;
  var slides = Array.prototype.slice.call(track.querySelectorAll('.slide'));
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
    var left = slides[i].offsetLeft - track.offsetLeft - 4;
    track.scrollTo({ left: left, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
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
  window.addEventListener('resize', paint);
  paint();
})();
