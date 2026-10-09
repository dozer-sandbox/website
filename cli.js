/* The CLI section's terminal: the commands roll fast; hovering the terminal stops them at once (and the mouse wheel
   scrolls them), leaving it waits 2 s and then slowly accelerates back. Hovering (or focusing) a command shows what it does and a link to its manual page.
   Without this file the roll is the plain CSS animation. */
(function () {
  'use strict';
  var term = document.getElementById('term');
  if (!term) return;
  var roll = term.querySelector('.term-roll'), screen = term.querySelector('.term-screen');
  var tip = term.querySelector('.term-tip'), tipText = tip.querySelector('span'), tipLink = tip.querySelector('a');
  var LOOP = 9;                 // seconds for one pass through every command at full speed
  var WAIT = 2000, RAMP = 2600; // after the pointer leaves: wait, then accelerate back over this long
  roll.style.animation = 'none';
  var y = 0, speed = 1, last = null, hovering = false, leftAt = 0, current = null, halfCache = 0;
  var sets = roll.querySelectorAll('.roll-set');
  // One pass = the second (hidden) copy's offset. Measured only while the popup is closed: the popup sits INSIDE
  // the list (between two commands) and would make one pass look longer.
  function half() { if (tip.hidden || !halfCache) halfCache = sets.length > 1 ? sets[1].offsetTop : roll.scrollHeight / 2; return halfCache; }

  function frame(t) {
    var h = half();
    if (last !== null && h > 0) {
      var target = hovering ? 0 : 1;
      if (!hovering) {
        var since = t - leftAt;
        target = leftAt === 0 ? 1 : since < WAIT ? 0 : Math.min(1, Math.pow((since - WAIT) / RAMP, 2));
      }
      speed = target;
      y -= speed * (h / LOOP) * (t - last) / 1000;
      if (-y >= h) y += h;
      roll.style.transform = 'translateY(' + y + 'px)';
    }
    last = t;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  function show(cmd) {
    if (current) current.classList.remove('on');
    current = cmd; cmd.classList.add('on');
    tipText.textContent = cmd.getAttribute('data-desc');
    tipLink.href = cmd.href;
    tipLink.setAttribute('aria-label', 'Manual: ' + cmd.textContent);
    half();                                         // measure the loop before the popup joins the list
    var before = cmd.getBoundingClientRect().top;
    // Inline, between commands: under the command (moving down reaches it), or — near the bottom of the window,
    // where it would not fit — above it. Either way nothing scrolls under the pointer.
    // After each move of the popup, shift the list so the command under the pointer stays exactly where it was.
    function settle() { y += before - cmd.getBoundingClientRect().top; roll.style.transform = 'translateY(' + y + 'px)'; }
    cmd.insertAdjacentElement('afterend', tip);
    tip.hidden = false;
    settle();
    if (cmd.getBoundingClientRect().bottom + tip.offsetHeight + 14 > screen.getBoundingClientRect().bottom) {
      cmd.insertAdjacentElement('beforebegin', tip);
      settle();
    }
  }
  function hide() { tip.hidden = true; if (current) current.classList.remove('on'); current = null; }

  // The mouse wheel (or a trackpad) scrolls the list while the pointer is inside — the page itself stays put.
  // The list wraps around in both directions; the description box closes (its command moved).
  function wrap() {
    var h = half();
    if (h > 0) { while (-y >= h) y += h; while (y > 0) y -= h; }
    roll.style.transform = 'translateY(' + y + 'px)';
  }
  term.addEventListener('wheel', function (e) {
    e.preventDefault();
    hovering = true;
    var lines = e.deltaMode === 1 ? 26 : e.deltaMode === 2 ? screen.clientHeight : 1;
    y -= e.deltaY * lines;
    wrap();
    hide();
  }, { passive: false });

  term.addEventListener('mouseenter', function () { hovering = true; });
  term.addEventListener('mouseleave', function () { hovering = false; leftAt = performance.now(); hide(); });
  roll.addEventListener('mouseover', function (e) {
    if (e.target.closest('.term-tip')) return;      // inside the popup: keep it
    var c = e.target.closest('.cmd'); if (c && c !== current) show(c);
  });
  term.addEventListener('focusin', function (e) {
    var c = e.target.closest('.cmd');
    hovering = true;
    if (c) { var s = screen.getBoundingClientRect(), r = c.getBoundingClientRect();
      if (r.top < s.top || r.bottom > s.bottom) { y -= (r.top - s.top) - s.height / 3; roll.style.transform = 'translateY(' + y + 'px)'; }
      show(c); }
  });
  term.addEventListener('focusout', function (e) {
    if (!term.contains(e.relatedTarget)) { hovering = false; leftAt = performance.now(); hide(); }
  });
})();
