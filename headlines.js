/* The hero's cycling headlines. The list is headlines.txt (one per line, " / " between its two lines, # for notes);
   the first is already in the page (tools/stamp.sh writes it). Each enters by crashing down from the top, stays 5 s,
   winds up a little to the right and is flung off to the left — for everyone, whatever the system's reduced-motion
   setting (owner's choice). Paused while the tab is hidden. Optional: delete this file and its <script> tag, and the page keeps the primary headline. */
(function () {
  'use strict';
  var h = document.getElementById('headline');
  if (!h || !window.fetch) return;
  var src = h.getAttribute('data-headlines');
  if (!src) return;
  var HOLD = 5000, IN = 760, OUT = 640;

  function parse(text) {
    return text.split('\n').map(function (s) { return s.trim(); })
      .filter(function (s) { return s && s.charAt(0) !== '#'; })
      .map(function (s) { return s.split(/\s+\/\s+/); });
  }
  function render(lines) {
    while (h.firstChild) h.removeChild(h.firstChild);
    lines.forEach(function (line, i) {
      if (i) h.appendChild(document.createElement('br'));
      h.appendChild(document.createTextNode(line.replace(/(\d) (ms|s)\b/g, '$1 $2')));
    });
  }
  function play(cls, ms, then) {
    h.classList.remove('hl-in', 'hl-out');
    void h.offsetWidth;                       // restart the animation
    h.classList.add(cls);
    setTimeout(then, ms);
  }

  fetch(src).then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); }).then(function (text) {
    var list = parse(text);
    if (list.length < 2) return;
    var i = 0;
    function next() {
      if (document.hidden) { setTimeout(next, 1000); return; }
      play('hl-out', OUT, function () {
        i = (i + 1) % list.length;
        render(list[i]);
        play('hl-in', IN, function () { setTimeout(next, HOLD); });
      });
    }
    setTimeout(next, HOLD);
  }).catch(function () { /* the primary stays */ });
})();
