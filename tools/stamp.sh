#!/bin/bash
# tools/stamp.sh — run before every commit that changes site.css, site.js, headlines.js, headlines.txt, docs/docs.css,
# docs/docs.js or the docs pages (tools/docs-build.py).
#  1. Fingerprints their links in every page — the root pages and docs/*.html, each by its own relative path
#     (?v=<8 hex of the file's sha256>): Cloudflare tells browsers to keep these files for hours, so a page
#     published with a NEW stylesheet was shown with the OLD one (2026-10-09).
#  3. Writes cli-commands.json (every doz command, its description and manual page — tools/cli-data.py makes it)
#     into the CLI section's terminal: links, then a hidden copy so the roll loops seamlessly.
#  2. Writes headlines.txt's FIRST headline into index.html's <h1 id="headline"> — what search engines and
#     visitors without JavaScript see; headlines.js cycles through the rest.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import hashlib, html, os, re, glob
def fp(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:8]
lines = [l.strip() for l in open('headlines.txt', encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
primary = '<br>'.join(re.sub(r'(\d) (ms|s)\b', r'\1&nbsp;\2', html.escape(p)) for p in re.split(r'\s+/\s+', lines[0]))
for page in sorted(glob.glob('*.html') + glob.glob('docs/*.html')):
    s = open(page, encoding='utf-8').read()
    for asset in ('site.css', 'site.js', 'headlines.js', 'cli.js', 'carousel.js', 'docs/docs.css', 'docs/docs.js'):
        rel = os.path.relpath(asset, os.path.dirname(page) or '.')
        s = re.sub(r'(href|src)="%s(\?v=[0-9a-f]+)?"' % re.escape(rel), r'\1="%s?v=%s"' % (rel, fp(asset)), s)
    s = re.sub(r'data-headlines="headlines\.txt(\?v=[0-9a-f]+)?"', 'data-headlines="headlines.txt?v=%s"' % fp('headlines.txt'), s)
    s = re.sub(r'(<h1 id="headline"[^>]*>).*?(</h1>)', lambda m: m.group(1) + primary + m.group(2), s, flags=re.S)
    if '<!--cli-commands-->' in s:
        import json
        cmds = json.load(open('cli-commands.json', encoding='utf-8'))
        line = lambda c, link: ('<a class="cmd" href="%s" data-desc="%s">%s</a>' % (html.escape(c['manual']), html.escape(c['desc']), html.escape(c['cmd']))
                                if link else '<p>%s</p>' % html.escape(c['cmd']))
        block = ('<div class="roll-set">' + ''.join(line(c, True) for c in cmds) + '</div>'
                 + '<div class="roll-set" aria-hidden="true">' + ''.join(line(c, False) for c in cmds) + '</div>')
        s = re.sub(r'<!--cli-commands-->.*?<!--/cli-commands-->', lambda m: '<!--cli-commands-->' + block + '<!--/cli-commands-->', s, flags=re.S)
    open(page, 'w', encoding='utf-8').write(s)
print('stamped: primary headline =', lines[0], '·', len(lines), 'headlines')
PY
