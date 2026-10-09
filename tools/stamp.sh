#!/bin/bash
# tools/stamp.sh — run before every commit that changes site.css, site.js, headlines.js or headlines.txt.
#  1. Fingerprints their links in every page (?v=<8 hex of the file's sha256>): Cloudflare tells browsers to keep
#     these files for hours, so a page published with a NEW stylesheet was shown with the OLD one (2026-10-09).
#  2. Writes headlines.txt's FIRST headline into index.html's <h1 id="headline"> — what search engines and
#     visitors without JavaScript see; headlines.js cycles through the rest.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import hashlib, html, re, glob
def fp(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:8]
lines = [l.strip() for l in open('headlines.txt', encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
primary = '<br>'.join(re.sub(r'(\d) (ms|s)\b', r'\1&nbsp;\2', html.escape(p)) for p in re.split(r'\s+/\s+', lines[0]))
for page in glob.glob('*.html'):
    s = open(page, encoding='utf-8').read()
    for asset in ('site.css', 'site.js', 'headlines.js'):
        s = re.sub(r'(href|src)="%s(\?v=[0-9a-f]+)?"' % re.escape(asset), r'\1="%s?v=%s"' % (asset, fp(asset)), s)
    s = re.sub(r'data-headlines="headlines\.txt(\?v=[0-9a-f]+)?"', 'data-headlines="headlines.txt?v=%s"' % fp('headlines.txt'), s)
    s = re.sub(r'(<h1 id="headline"[^>]*>).*?(</h1>)', lambda m: m.group(1) + primary + m.group(2), s, flags=re.S)
    open(page, 'w', encoding='utf-8').write(s)
print('stamped: primary headline =', lines[0], '·', len(lines), 'headlines')
PY
