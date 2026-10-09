/* Accent colour picker. Optional: delete this file and its <script> tag to remove it
   (and the ".accent-picker" block in site.css). Without it the page keeps its default accent. */
(function () {
  'use strict';
  var KEY = 'dozer-accent';
  var PRESETS = [
    ['ffd60a', 'warm yellow'], ['ffa63d', 'orange'], ['ff8a7a', 'coral'], ['ff9ccf', 'pink'],
    ['c9f23c', 'lime'], ['7fe3b5', 'mint'], ['6ec6ff', 'sky blue'], ['c4a8ff', 'lavender']
  ];
  var root = document.documentElement;

  function clean(v) {
    if (!v) return null;
    v = String(v).trim().replace(/^#/, '').toLowerCase();
    if (/^[0-9a-f]{3}$/.test(v)) v = v.replace(/./g, '$&$&');
    return /^[0-9a-f]{6}$/.test(v) ? v : null;
  }
  function lum(r, g, b) {
    function f(c) { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  // Black text must stay readable on the accent: a colour too dark is lightened toward white.
  function readable(hex) {
    var c = [0, 2, 4].map(function (i) { return parseInt(hex.slice(i, i + 2), 16); });
    for (var i = 0; i < 20 && lum(c[0], c[1], c[2]) < 0.35; i++) {
      c = c.map(function (x) { return Math.round(x + (255 - x) * 0.12); });
    }
    return c.map(function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
  }
  function apply(hex) {
    var h = readable(hex);
    root.style.setProperty('--accent', '#' + h);
    return h;
  }
  function read(fn) { try { return fn(); } catch (e) { return null; } }

  var fromUrl = clean(new URLSearchParams(location.search).get('accent')) ||
                clean((location.hash.match(/accent=([0-9a-fA-F#]+)/) || [])[1]);
  var saved = fromUrl || clean(read(function () { return localStorage.getItem(KEY); }));
  if (saved) apply(saved);

  function remember(hex) {
    read(function () { localStorage.setItem(KEY, hex); });
    read(function () {
      var u = new URL(location.href);
      u.searchParams.set('accent', hex);
      history.replaceState(null, '', u.toString());
    });
  }

  function build() {
    var box = document.createElement('div');
    box.className = 'accent-picker';
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', 'Accent colour');
    var lbl = document.createElement('span');
    lbl.className = 'lbl'; lbl.textContent = 'Colour';
    box.appendChild(lbl);
    var buttons = [];
    function mark(hex) {
      buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.hex === hex)); });
    }
    PRESETS.forEach(function (p) {
      var b = document.createElement('button');
      b.type = 'button'; b.dataset.hex = p[0];
      b.style.background = '#' + p[0];
      b.setAttribute('aria-label', 'Accent colour: ' + p[1]);
      b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', function () { apply(p[0]); remember(p[0]); mark(p[0]); input.value = '#' + p[0]; });
      buttons.push(b); box.appendChild(b);
    });
    var input = document.createElement('input');
    input.type = 'color'; input.title = 'Any colour'; input.value = '#' + (saved || PRESETS[0][0]);
    input.setAttribute('aria-label', 'Choose any accent colour');
    input.addEventListener('input', function () {
      var hex = clean(input.value); if (!hex) return;
      apply(hex); remember(hex); mark(hex);
    });
    box.appendChild(input);
    mark(saved || PRESETS[0][0]);
    document.body.appendChild(box);
  }
  function copyButton() {
    var code = document.getElementById('oneliner');
    if (!code) return;
    var wrap = code.closest('.oneline');
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'copy'; b.textContent = 'Copy';
    b.setAttribute('aria-label', 'Copy the install command');
    var t;
    b.addEventListener('click', function () {
      var text = code.textContent;
      function done() { b.textContent = 'Copied'; clearTimeout(t); t = setTimeout(function () { b.textContent = 'Copy'; }, 1800); }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { select(); });
      } else { select(); }
      function select() {
        var r = document.createRange(); r.selectNodeContents(code);
        var s = getSelection(); s.removeAllRanges(); s.addRange(r);
        try { if (document.execCommand('copy')) done(); } catch (e) {}
      }
    });
    wrap.appendChild(b);
  }
  // The latest STABLE version, from our own update feed. The HTML carries the current value as the fallback.
  function stableVersion() {
    var el = document.getElementById('stable-version');
    if (!el || !window.fetch) return;
    function parse(v) {
      var m = /^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$/.exec(v || '');
      return m ? { n: [+m[1], +m[2], +m[3]], pre: m[4] || '' } : null;
    }
    function newer(a, b) {
      for (var i = 0; i < 3; i++) if (a.n[i] !== b.n[i]) return a.n[i] > b.n[i];
      return !a.pre && !!b.pre;
    }
    fetch('https://updates.dozersandbox.com/v1/feed.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (feed) {
        var best = null;
        (feed.entries || []).forEach(function (e) {
          if (e.channel !== 'stable') return;
          var p = parse(e.version);
          if (p && (!best || newer(p, best.p))) best = { p: p, v: e.version };
        });
        if (best) el.textContent = 'v' + best.v;
      })
      .catch(function () {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { build(); copyButton(); stableVersion(); }); else { build(); copyButton(); stableVersion(); }
})();
