#!/usr/bin/env python3
"""tools/docs-diagrams/sandbox-states.py APP_CHECKOUT — draw sandbox-states.svg, chapter 5's Mermaid state diagram,
by hand (fixed coordinates, the site's line style: black strokes, white states with the hard shadow). Its <desc> is
the Mermaid source copied from the manual; tools/docs-build.py uses the SVG only while that source is unchanged, so
an edit to the diagram in the manual fails the docs build until this drawing is updated and re-run."""
import html, os, re, sys

app = os.path.abspath(sys.argv[1])
src = open(os.path.join(app, 'docs/manual/05-sandboxes-and-lifecycle.md'), encoding='utf-8').read()
merm = re.search(r'```mermaid\n(.*?)\n```', src, re.S).group(1)
SANS = "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
W, H = 850, 420
o = []


def state(x, y, w, h, name, notes=()):
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="#000"/>' % (x, y + 4, w, h))
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="#fff" stroke="#000" stroke-width="1.5"/>'
             % (x, y, w, h))
    cx = x + w / 2
    if notes:
        o.append('<text x="%g" y="%d" class="n">%s</text>' % (cx, y + 25, name))
        o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#000" stroke-opacity=".22"/>'
                 % (x + 14, y + 36, x + w - 14, y + 36))
        for k, t in enumerate(notes):
            o.append('<text x="%g" y="%d" class="t">%s</text>' % (cx, y + 56 + 17 * k, html.escape(t)))
    else:
        o.append('<text x="%g" y="%g" class="n">%s</text>' % (cx, y + h / 2 + 5.5, name))


def arrow(d):
    o.append('<path d="%s" fill="none" stroke="#000" stroke-width="1.5" marker-end="url(#a)"/>' % d)


def label(x, y, t, anchor='middle'):
    o.append('<text x="%g" y="%g" class="c" text-anchor="%s">%s</text>' % (x, y, anchor, html.escape(t)))


# the long way back, running -> off, drawn first (under everything)
arrow('M430,60 H82 Q70,60 70,72 V170'); label(250, 51, 'doz reset (a fresh disk)')
arrow('M430,120 H132 Q120,120 120,132 V170'); label(275, 111, 'doz shutdown')
state(20, 172, 150, 96, 'off', ['powered off', 'disks kept', 'programs ended'])
state(260, 200, 100, 40, 'booting')
state(260, 320, 100, 40, 'failed')
state(430, 30, 100, 380, 'running')
o.append('<circle cx="45" cy="372" r="9" fill="#000"/>')                     # [*] start
arrow('M45,362 V272'); label(53, 322, 'doz create', 'start')
arrow('M150,268 V356'); label(158, 316, 'doz rm', 'start')
o.append('<circle cx="150" cy="372" r="11" fill="#fff" stroke="#000" stroke-width="1.5"/>'
         '<circle cx="150" cy="372" r="6" fill="#000"/>')                   # [*] end
arrow('M170,220 H256'); label(215, 211, 'doz start')
arrow('M360,220 H426')
arrow('M295,240 V316')
arrow('M325,320 V244'); label(333, 286, 'doz start', 'start')
for top, name, notes, out, back in (
        (30, 'paused', ['frozen', 'memory kept', 'back in ~1 ms'], 'doz pause', 'doz resume'),
        (172, 'asleep', ['frozen and saved to disk', 'memory kept', 'back in ~0.3 s'], 'doz sleep', 'doz wake'),
        (314, 'hibernated', ['saved to disk', 'memory given back', 'back in ~0.3 s'], 'doz hibernate', 'doz wake')):
    c = top + 48
    arrow('M530,%d H646' % (c - 12)); label(590, c - 19, out)
    arrow('M650,%d H534' % (c + 12)); label(590, c + 30, back)
    state(650, top, 190, 96, name, notes)

title = ('The states of a sandbox. doz create makes it, off. doz start boots it: booting, then running (or failed; '
         'doz start tries again). From running: doz pause and doz resume (paused: frozen, memory kept, back in about '
         '1 ms); doz sleep and doz wake (asleep: frozen and saved to disk, memory kept, back in about 0.3 s); doz '
         'hibernate and doz wake (hibernated: saved to disk, memory given back, back in about 0.3 s); doz shutdown or '
         'doz reset (a fresh disk) back to off (powered off, disks kept, programs ended). doz rm removes it.')
svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-labelledby="t">
<title id="t">%s</title>
<desc>%s</desc>
<!-- Drawn by tools/docs-diagrams/sandbox-states.py from the Mermaid state diagram in docs/manual/05-sandboxes-and-lifecycle.md
     (the <desc> above is that source, verbatim: tools/docs-build.py fails when the manual's diagram changes). -->
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#000"/></marker></defs>
<style>
.n { font: 700 17px %s; text-anchor: middle; fill: #000; letter-spacing: -.01em; }
.t { font: 13.5px %s; text-anchor: middle; fill: #2b2b2d; }
.c { font: 600 13.5px %s; fill: #000; }
</style>
<rect width="%d" height="%d" fill="#fff"/>
%s
</svg>
''' % (W, H, W, H, html.escape(title), html.escape(merm), SANS, SANS, MONO, W, H, '\n'.join(o))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sandbox-states.svg')
open(out, 'w', encoding='utf-8').write(svg)
print('wrote', out)
