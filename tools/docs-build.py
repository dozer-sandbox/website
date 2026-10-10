#!/usr/bin/env python3
"""tools/docs-build.py APP_CHECKOUT — build the user manual pages (docs/) from the app repo's docs/manual/*.md.

The manual in the app repo is the single source: these pages are generated and committed, never edited by hand
(DESIGN.md is the spec). Stdlib only — a converter for exactly the Markdown the manual uses, nothing more:
ATX headings, paragraphs, **bold**, *italic*, `code`, links, bare URLs, images (a paragraph of its own), nested
bullet/numbered lists, pipe tables, blockquotes, fenced code, rules and HTML comments (dropped).

It FAILS (exit 1, with file:line) on anything else: unknown syntax, a link or #fragment that resolves to nothing,
a missing image, a ragged table row, a skipped heading level, a Mermaid diagram with no matching hand-drawn SVG.
After writing, it reads the pages back and checks that every word and every code block of the source is there.

Writes docs/index.html, docs/<slug>.html (slug = the file name without its number), docs/images/, and the docs
entries of sitemap.xml. Then run tools/stamp.sh (it fingerprints site.css, docs.css and docs.js)."""
import html, os, posixpath, re, shutil, struct, subprocess, sys, unicodedata
from collections import Counter
from html.parser import HTMLParser

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SITE, 'docs')
TEMPLATE = os.path.join(SITE, 'tools', 'docs-template.html')
DIAGRAMS = os.path.join(SITE, 'tools', 'docs-diagrams')
BASE_URL = 'https://dozersandbox.com/docs/'
REPO = 'https://github.com/dozer-sandbox/dozer-sandbox'

# A blockquote whose bold lead-in is one of these is a warning callout (DESIGN.md §4); any other bold lead-in is a
# note, and a quote with no bold lead-in is an example. Compared without the trailing full stop.
WARNING_LEADS = (
    'A convenience, not a security boundary',     # 20 Workspace rules
    'Not in public releases',                     # 23 Audio
    'Experimental',
    'Experimental, and temporary in parts',       # 23 Audio
    'Not a security boundary',
)
# The sidebar: the groups and short labels of DESIGN.md §2 (the manual's README has no groups). Every chapter must
# be in exactly one group; a new chapter fails the build until it is placed here.
GROUPS = [
    ('Start here', [(1, 'Getting started'), (5, 'Sandboxes and their lifecycle'), (7, 'Terminals and sessions'),
                    (10, 'What the agent can do')]),
    ('Install and set up', [(2, 'Install, upgrade, uninstall'), (3, 'Setting up this Mac'), (4, 'Projects')]),
    ('Using Dozer', [(6, 'The dashboard'), (25, 'The dashboard on other devices'), (8, 'Images and bases'),
                     (9, 'Agents and accounts'), (24, 'Codex'), (11, 'Signing in from a sandbox'), (18, 'GitHub as you')]),
    ('Files and tools', [(19, 'The tools layer'), (20, 'Workspace rules'), (21, 'The workspace view'),
                         (22, 'Prompts for your agent')]),
    ('Looking after sandboxes', [(12, 'Restore points, duplicates, templates'), (13, 'Resources and disk space'),
                                 (14, 'Letting another agent drive')]),
    ('Reference', [(15, 'Settings reference'), (16, 'Security model'), (17, 'Troubleshooting and FAQ')]),
    ('Experimental', [(23, 'Audio sandboxes')]),
]
# The chapter header's summary is the opening sentence of the page (see summary_of); these pages open with a notice.
SUMMARY = {'23-audio-experimental.md': "This lets a sandbox use your Mac's microphone and speakers."}
KEY_RE = re.compile(r'^(?:(?:Ctrl|Cmd|Shift|Alt|Option)(?:[-+]\S+)*|Enter|Esc|Escape|Return|Tab)$')
PUNCT = set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')


class BuildError(Exception):
    pass


def fail(where, msg):
    raise BuildError('%s: %s' % (where, msg))


def esc(s):
    return html.escape(s, quote=True)


def slugify(text):
    """GitHub's heading id: lower case, keep letters/marks/numbers/connectors, spaces and hyphens; spaces -> '-'."""
    out = []
    for ch in text.lower():
        cat = unicodedata.category(ch)
        if ch in ' -' or cat[0] in 'LMN' or cat == 'Pc':
            out.append('-' if ch == ' ' else ch)
    return ''.join(out)


def strip_tags(h):
    return html.unescape(re.sub(r'<[^>]+>', '', h))


# ------------------------------------------------------------------------------------------------ inline Markdown
class Inline:
    def __init__(self, page, where):
        self.page, self.where = page, where

    def render(self, s):
        toks = self.tokens(s)
        self.emphasis(toks)
        out = []
        for t in toks:
            if t[0] == 'd':
                out.append(t[1]['pre'] + '*' * t[1]['n'] + t[1]['post'])
            else:
                out.append(t[1])
        return ''.join(out)

    def tokens(self, s):
        toks, buf, i, n = [], [], 0, len(s)

        def flush():
            if buf:
                toks.append(('h', esc(''.join(buf))))
                buf.clear()

        while i < n:
            c = s[i]
            if c == '\\' and i + 1 < n and s[i + 1] in PUNCT:
                buf.append(s[i + 1]); i += 2
            elif c == '`':
                j = i
                while j < n and s[j] == '`':
                    j += 1
                run = j - i
                m = re.compile(r'(?<!`)`{%d}(?!`)' % run).search(s, j)
                if not m:
                    fail(self.where, 'unclosed code span: %r' % s[i:i + 40])
                code = s[j:m.start()]
                if len(code) > 1 and code[0] == ' ' and code[-1] == ' ' and code.strip():
                    code = code[1:-1]
                flush(); toks.append(('h', '<code>%s</code>' % esc(code))); i = m.end()
            elif c == '!' and s.startswith('![', i):
                fail(self.where, 'an image inside text (images must be a paragraph of their own)')
            elif c == '[':
                end = self.close_bracket(s, i)
                if end is not None and end + 1 < n and s[end + 1] == '(':
                    close = s.find(')', end + 2)
                    url = s[end + 2:close] if close > 0 else ''
                    if close < 0 or not url or re.search(r'\s', url):
                        fail(self.where, 'a link whose target is not a plain URL: %r' % s[i:i + 60])
                    flush()
                    toks.append(('h', '<a href="%s">%s</a>' % (esc(self.page.link(url, self.where)),
                                                               Inline(self.page, self.where).render(s[i + 1:end]))))
                    i = close + 1
                else:
                    if s.startswith('](', i) or (end is not None and s[end + 1:end + 2] == '['):
                        fail(self.where, 'reference-style link: %r' % s[i:i + 40])
                    buf.append(c); i += 1
            elif c == '*':
                j = i
                while j < n and s[j] == '*':
                    j += 1
                before = s[i - 1] if i else ' '
                after = s[j] if j < n else ' '
                lf = not after.isspace() and (after not in PUNCT or before.isspace() or before in PUNCT)
                rf = not before.isspace() and (before not in PUNCT or after.isspace() or after in PUNCT)
                flush(); toks.append(('d', {'n': j - i, 'open': lf, 'close': rf, 'pre': '', 'post': '', 'at': i}))
                i = j
            elif c == '<' and s.startswith('<!--', i):
                fail(self.where, 'an HTML comment inside text')
            elif re.compile(r'https?://[\w-]').match(s, i) and (i == 0 or not s[i - 1].isalnum()) and \
                    (i == 0 or s[i - 1] not in '(<'):
                m = re.compile(r'https?://[^\s<]+').match(s, i)
                url = m.group(0)
                while url and (url[-1] in '.,:;!?\'"*' or (url[-1] == ')' and url.count('(') < url.count(')'))):
                    url = url[:-1]
                flush(); toks.append(('h', '<a href="%s">%s</a>' % (esc(url), esc(url)))); i += len(url)
            else:
                buf.append(c); i += 1
        flush()
        return toks

    def close_bracket(self, s, i):
        depth, j = 0, i
        while j < len(s):
            c = s[j]
            if c == '\\':
                j += 2; continue
            if c == '`':
                k = j
                while k < len(s) and s[k] == '`':
                    k += 1
                m = re.compile(r'(?<!`)`{%d}(?!`)' % (k - j)).search(s, k)
                j = m.end() if m else k
                continue
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return None

    def emphasis(self, toks):
        """CommonMark's delimiter matching for '*' runs (no '_' emphasis: the manual uses none)."""
        k = 0
        while k < len(toks):
            t = toks[k]
            if t[0] == 'd' and t[1]['close'] and t[1]['n']:
                o = k - 1
                while o >= 0:
                    d = toks[o]
                    if d[0] == 'd' and d[1]['open'] and d[1]['n']:
                        both = (d[1]['open'] and d[1]['close']) or (t[1]['open'] and t[1]['close'])
                        if not (both and (d[1]['n'] + t[1]['n']) % 3 == 0 and (d[1]['n'] % 3 or t[1]['n'] % 3)):
                            break
                    o -= 1
                if o >= 0:
                    d = toks[o]
                    for m in range(o + 1, k):        # delimiters in between can no longer match
                        if toks[m][0] == 'd':
                            toks[m] = ('h', toks[m][1]['pre'] + '*' * toks[m][1]['n'] + toks[m][1]['post'])
                    use = 2 if d[1]['n'] >= 2 and t[1]['n'] >= 2 else 1
                    inner = toks[o + 1:k]
                    if use == 2 and len(inner) == 1 and inner[0][0] == 'h' and KEY_RE.match(strip_tags(inner[0][1])) \
                            and '<' not in inner[0][1]:
                        key = html.unescape(inner[0][1])
                        parts = re.split(r'(?<=[A-Za-z])([-+])(?=.)', key)
                        toks[o + 1] = ('h', ''.join(esc(p) if p in '-+' else '<kbd>%s</kbd>' % esc(p) for p in parts))
                    else:
                        tag = 'strong' if use == 2 else 'em'
                        d[1]['post'] = '<%s>' % tag + d[1]['post']
                        t[1]['pre'] = t[1]['pre'] + '</%s>' % tag
                    d[1]['n'] -= use
                    t[1]['n'] -= use
                    continue                          # the closer may close more
            k += 1
        for t in toks:
            if t[0] == 'd' and t[1]['n'] and (t[1]['open'] or t[1]['close']):
                fail(self.where, 'an unmatched * (emphasis that does not close)')


# ------------------------------------------------------------------------------------------------- block Markdown
FENCE = re.compile(r'^(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$')
HEADING = re.compile(r'^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$')
BULLET = re.compile(r'^([-*+])( +)(?=\S)')
ORDERED = re.compile(r'^(\d{1,9})([.)])( +)(?=\S)')
HR = re.compile(r'^(?:-{3,}|\*{3,}|_{3,})\s*$')
TABLE_SEP = re.compile(r'^\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$')


def starts_block(lines, i, in_para):
    l = lines[i]
    if FENCE.match(l) or HEADING.match(l) or l.startswith('>') or HR.match(l) or l.startswith('<!--'):
        return True
    if BULLET.match(l):
        return True
    m = ORDERED.match(l)
    if m and (not in_para or m.group(1) == '1'):
        return True
    if l.startswith('|') and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]):
        return True
    return False


def parse_blocks(lines, ln0, page):
    """lines are already de-indented to this container's content column; ln0 = the source line of lines[0]."""
    blocks, i, n = [], 0, len(lines)
    where = lambda k: '%s:%d' % (page.name, ln0 + k)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1; continue
        if line[0] in ' \t':
            fail(where(i), 'unexpected indentation (an indented code block, or a lazy continuation line): %r' % line[:60])
        m = FENCE.match(line)
        if m:
            mark = m.group(1)
            j = i + 1
            while j < n and not re.match(r'^%s%s*\s*$' % (re.escape(mark), re.escape(mark[0])), lines[j]):
                j += 1
            if j >= n:
                fail(where(i), 'unclosed code fence')
            blocks.append({'t': 'code', 'lang': m.group(2).lower(), 'text': '\n'.join(lines[i + 1:j]), 'ln': ln0 + i})
            i = j + 1; continue
        m = HEADING.match(line)
        if m:
            blocks.append({'t': 'h', 'level': len(m.group(1)), 'src': m.group(2), 'ln': ln0 + i})
            i += 1; continue
        if line.startswith('#'):
            fail(where(i), 'a heading without a space after the #')
        if HR.match(line):
            blocks.append({'t': 'hr'}); i += 1; continue
        if line.startswith('<!--'):
            j = i
            while '-->' not in lines[j]:
                j += 1
                if j >= n:
                    fail(where(i), 'unclosed HTML comment')
            if not lines[j].rstrip().endswith('-->'):
                fail(where(j), 'text after an HTML comment')
            i = j + 1; continue
        if line.startswith('<') and re.match(r'<[A-Za-z/]', line):
            fail(where(i), 'raw HTML: %r' % line[:60])
        if line.startswith('>'):
            j, inner = i, []
            while j < n and lines[j].startswith('>'):
                inner.append(re.sub(r'^> ?', '', lines[j])); j += 1
            if j < n and lines[j].strip():
                fail(where(j), 'a lazy continuation line after a blockquote')
            blocks.append({'t': 'quote', 'children': parse_blocks(inner, ln0 + i, page), 'ln': ln0 + i,
                           'raw': inner})
            i = j; continue
        if line.startswith('|') and i + 1 < n and TABLE_SEP.match(lines[i + 1]):
            if ':' in lines[i + 1]:
                fail(where(i + 1), 'table column alignment is not supported')
            head = split_row(line)
            rows, j = [], i + 2
            while j < n and lines[j].startswith('|'):
                r = split_row(lines[j])
                if len(r) != len(head):
                    fail(where(j), 'a ragged table row: %d cells, the header has %d' % (len(r), len(head)))
                rows.append((r, ln0 + j)); j += 1
            if len(split_row(lines[i + 1])) != len(head):
                fail(where(i + 1), 'the table separator does not match the header')
            if j < n and lines[j].strip():
                fail(where(j), 'a line straight after a table that is not a table row')
            blocks.append({'t': 'table', 'head': head, 'rows': rows, 'ln': ln0 + i})
            i = j; continue
        if BULLET.match(line) or ORDERED.match(line):
            i = parse_list(lines, i, ln0, page, blocks); continue
        # a paragraph
        j = i + 1
        while j < n and lines[j].strip() and not starts_block(lines, j, True):
            if re.match(r'^(=+|-+)\s*$', lines[j]):
                fail(where(j), 'a setext heading (underlined)')
            if lines[j][0] in ' \t':
                fail(where(j), 'an indented continuation line in a paragraph')
            j += 1
        text = ' '.join(l.strip() for l in lines[i:j])
        img = re.match(r'^!\[([^\]]*)\]\(([^)\s]+)\)$', text)
        if img:
            blocks.append({'t': 'img', 'alt': img.group(1), 'src': img.group(2), 'ln': ln0 + i})
        else:
            blocks.append({'t': 'p', 'src': text, 'ln': ln0 + i})
        i = j
    return blocks


def split_row(line):
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    cells = re.split(r'(?<!\\)\|', s)
    return [c.strip().replace('\\|', '|') for c in cells]


def parse_list(lines, i, ln0, page, blocks):
    n = len(lines)
    first = BULLET.match(lines[i]) or ORDERED.match(lines[i])
    ordered = bool(ORDERED.match(lines[i]))
    kind = first.group(2) if ordered else first.group(1)
    items, loose, start = [], False, int(first.group(1)) if ordered else 1
    while i < n:
        m = (ORDERED.match(lines[i]) if ordered else BULLET.match(lines[i]))
        if not m or (m.group(2) if ordered else m.group(1)) != kind:
            break
        indent = len(m.group(0))
        if len(m.group(m.lastindex)) > 4:
            fail('%s:%d' % (page.name, ln0 + i), 'a list item with more than 4 spaces after its marker')
        body, j = [lines[i][indent:]], i + 1
        while j < n:
            l = lines[j]
            if not l.strip():
                body.append(''); j += 1; continue
            ind = len(l) - len(l.lstrip(' '))
            if ind >= indent:
                body.append(l[indent:]); j += 1; continue
            if lines[j - 1].strip() and ind == 0 and not (starts_block(lines, j, True) or ORDERED.match(l)):
                fail('%s:%d' % (page.name, ln0 + j), 'a lazy continuation line in a list item (indent it)')
            if ind > 0:
                fail('%s:%d' % (page.name, ln0 + j), 'a list line indented less than its item\'s text')
            break
        while body and not body[-1].strip():
            body.pop()
        if any(not b.strip() for b in body):
            loose = True
        items.append(parse_blocks(body, ln0 + i, page))
        k = j
        while k < n and not lines[k].strip():
            k += 1
        if k < n and k > j and (ORDERED.match(lines[k]) if ordered else BULLET.match(lines[k])):
            loose = True
        if k < n and (ORDERED.match(lines[k]) if ordered else BULLET.match(lines[k])):
            i = k
        else:
            i = j
            break
    blocks.append({'t': 'list', 'ordered': ordered, 'start': start, 'items': items, 'loose': loose})
    return i


# --------------------------------------------------------------------------------------------------------- pages
class Page:
    def __init__(self, build, path, num, slug):
        self.build, self.path, self.num, self.slug = build, path, num, slug
        self.name = os.path.basename(path)
        self.href = slug + '.html' if num else './'
        self.lines = open(path, encoding='utf-8').read().split('\n')
        self.blocks = parse_blocks(self.lines, 1, self)
        self.ids, self.headings = Counter(), []
        self.title_src = None
        self.code_blocks = []
        self.assign_ids(self.blocks)

    def assign_ids(self, blocks):
        last = 0
        for b in self.walk(blocks):
            if b['t'] != 'h':
                continue
            where = '%s:%d' % (self.name, b['ln'])
            if b['level'] == 1:
                if self.title_src is not None or b['ln'] != 1:
                    fail(where, 'one h1 per page, on the first line')
                self.title_src = b['src']
            elif b['level'] > last + 1:
                fail(where, 'a skipped heading level (h%d after h%d)' % (b['level'], last))
            last = b['level']
            plain = strip_tags(Inline(self, where).render(b['src']))
            base = slugify(plain)
            hid = base if not self.ids[base] else '%s-%d' % (base, self.ids[base])
            self.ids[base] += 1
            b['id'], b['plain'] = hid, plain
            if b['level'] > 1:
                self.headings.append(b)
        if self.title_src is None:
            fail(self.name, 'no h1 on the first line')

    @staticmethod
    def walk(blocks):
        for b in blocks:
            yield b
            if b['t'] == 'quote':
                yield from Page.walk(b['children'])
            elif b['t'] == 'list':
                for it in b['items']:
                    yield from Page.walk(it)

    def link(self, url, where):
        """Rewrite a manual link for the site, recording #fragments to check once every page is parsed."""
        if re.match(r'^(https?|mailto):', url):
            return url
        path, _, frag = url.partition('#')
        if not path:
            self.build.frags.append((self, frag, where))
            return '#' + frag
        full = posixpath.normpath(posixpath.join('docs/manual', path))
        target = self.build.by_file.get(full)
        if target is not None:
            if frag:
                self.build.frags.append((target, frag, where))
            return target.href + ('#' + frag if frag else '')
        if full.startswith('docs/manual/images/'):
            fail(where, 'a link to an image (use an image paragraph): %s' % url)
        disk = os.path.join(self.build.app, full)
        if full.startswith('..') or not os.path.exists(disk):
            fail(where, 'a link to nothing: %s' % url)
        if full.startswith('docs/manual/'):
            fail(where, 'a link into the manual that is not a chapter: %s' % url)
        return '%s/%s/main/%s%s' % (REPO, 'tree' if os.path.isdir(disk) else 'blob', full, '#' + frag if frag else '')

    # ---- rendering
    def inline(self, src, ln):
        return Inline(self, '%s:%d' % (self.name, ln)).render(src)

    def render(self, blocks, top=False):
        out, prev_heading = [], self.title_src
        for b in blocks:
            t = b['t']
            if t == 'h':
                if b['level'] == 1:
                    continue
                prev_heading = b['plain']
                tag = 'h%d' % b['level']
                out.append('<%s id="%s">%s<a class="anchor" href="#%s" aria-label="Link to this section">#</a></%s>'
                           % (tag, b['id'], self.inline(b['src'], b['ln']), b['id'], tag))
            elif t == 'p':
                out.append('<p>%s</p>' % self.inline(b['src'], b['ln']))
            elif t == 'hr':
                out.append('<hr>')
            elif t == 'code':
                out.append(self.code(b))
            elif t == 'img':
                out.append(self.image(b))
            elif t == 'table':
                out.append(self.table(b, prev_heading))
            elif t == 'quote':
                out.append(self.quote(b))
            elif t == 'list':
                out.append(self.list(b))
        return '\n'.join(out)

    def code(self, b):
        self.code_blocks.append(b['text'])
        if b['lang'] == 'mermaid':
            return self.build.diagram(self, b)
        lang = b['lang'] or 'text'
        body = esc(b['text'])
        if lang in ('sh', 'bash', 'shell', 'zsh'):
            body = '\n'.join(shell_line(l) for l in b['text'].split('\n'))
        diagram = not b['lang'] and re.search(r'[─│┌┐└┘├┤┬┴┼═║╔╗╚╝]', b['text'])
        return ('<figure class="code%s"><figcaption data-gen><span>%s</span><button class="copy" type="button">Copy'
                '</button></figcaption><pre tabindex="0" role="region" aria-label="Code (%s)"><code>%s</code></pre>'
                '</figure>' % (' diagram' if diagram else '', esc(lang), esc(lang), body))

    def image(self, b):
        where = '%s:%d' % (self.name, b['ln'])
        if not b['src'].startswith('images/') or '..' in b['src']:
            fail(where, 'an image outside images/: %s' % b['src'])
        src = os.path.join(os.path.dirname(self.path), b['src'])
        if not os.path.isfile(src):
            fail(where, 'a missing image: %s' % b['src'])
        w, h = png_size(src, where)
        self.build.images.add(b['src'])
        return ('<figure class="shot"><div class="frame"><img src="%s" alt="%s" width="%d" height="%d" loading="lazy" '
                'decoding="async"></div><figcaption>%s</figcaption></figure>'
                % (esc(b['src']), esc(strip_tags(self.inline(b['alt'], b['ln']))), w, h, self.inline(b['alt'], b['ln'])))

    def table(self, b, label):
        head = ''.join('<th scope="col">%s</th>' % self.inline(c, b['ln']) for c in b['head'])
        rows = ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % self.inline(c, ln) for c in r) for r, ln in b['rows'])
        wide = ' wide' if len(b['head']) >= 5 else ''
        return ('<div class="tablewrap%s" tabindex="0" role="region" aria-label="%s"><table>\n<thead><tr>%s</tr></thead>'
                '\n<tbody>\n%s\n</tbody></table></div>' % (wide, esc('Table: ' + label), head, rows))

    def quote(self, b):
        kids = b['children']
        first = kids[0] if kids else None
        lead = re.match(r'^\*\*(.+?)\*\*', first['src']) if first and first['t'] == 'p' else None
        inner = self.render(kids)
        if lead and lead.group(1).rstrip('.').strip() in WARNING_LEADS:
            self.build.warnings.append('%s: %s' % (self.name, lead.group(1)))
            return '<blockquote class="callout warn">\n%s\n</blockquote>' % inner
        return '<blockquote class="%s">\n%s\n</blockquote>' % ('note' if lead else 'example', inner)

    def list(self, b):
        tag = 'ol' if b['ordered'] else 'ul'
        attr = ' start="%d"' % b['start'] if b['ordered'] and b['start'] != 1 else ''
        items = []
        for it in b['items']:
            parts = []
            for k, c in enumerate(it):
                if c['t'] == 'p' and k == 0 and not b['loose']:
                    parts.append(self.inline(c['src'], c['ln']))
                else:
                    parts.append(self.render([c]))
            items.append('<li>%s</li>' % '\n'.join(parts))
        return '<%s%s>\n%s\n</%s>' % (tag, attr, '\n'.join(items), tag)


def shell_line(line):
    """Escape a shell line and grey its comment (a # at the start or after a space, outside quotes)."""
    q = None
    for k, c in enumerate(line):
        if q:
            if c == q:
                q = None
        elif c in '\'"':
            q = c
        elif c == '#' and (k == 0 or line[k - 1] in ' \t'):
            return esc(line[:k]) + '<span class="c">%s</span>' % esc(line[k:])
    return esc(line)


def png_size(path, where):
    with open(path, 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        fail(where, 'not a PNG: %s' % path)
    return struct.unpack('>II', head[16:24])


def summary_of(page):
    """The opening sentence of the page's first paragraph (before the first h2; inside a blockquote only when there is
    none outside one), without a bold lead-in; a first sentence under 50 characters takes the next one with it.
    SUMMARY names the sentence instead where the opening paragraph is a notice (it must be in the page)."""
    if page.name in SUMMARY:
        want = SUMMARY[page.name]
        if want not in ' '.join(page.lines):
            fail(page.name, 'the SUMMARY sentence is no longer in the page: %r' % want)
        return page.inline(want, 1)
    para = None
    for b in page.blocks:
        if b['t'] == 'h' and b['level'] == 2:
            break
        if b['t'] == 'p':
            para = b; break
    if para is None:
        for b in Page.walk(page.blocks):
            if b['t'] == 'p':
                para = b; break
    src = re.sub(r'^\*\*[^*]+\*\*\s*', '', para['src'])
    sentences = re.findall(r'.+?[.!?](?=\s+[A-Z`(*"]|$)|.+$', src)
    text = sentences[0].strip()
    if len(strip_tags(page.inline(text, para['ln']))) < 50 and len(sentences) > 1:
        text += ' ' + sentences[1].strip()
    return page.inline(re.sub(r':$', '.', text), para['ln'])


# --------------------------------------------------------------------------------------------------------- build
class Build:
    def __init__(self, app):
        self.app = app
        self.manual = os.path.join(app, 'docs', 'manual')
        self.frags, self.images, self.warnings, self.diagrams = [], set(), [], []
        self.sha = subprocess.run(['git', '-C', app, 'rev-parse', '--short', 'HEAD'], capture_output=True,
                                  text=True, check=True).stdout.strip()
        self.date = subprocess.run(['git', '-C', app, 'log', '-1', '--format=%cs'], capture_output=True,
                                   text=True, check=True).stdout.strip()
        files = sorted(f for f in os.listdir(self.manual) if re.match(r'^\d+-.+\.md$', f))
        self.by_file, self.chapters = {}, []
        specs = []
        for f in files:
            num = int(f.split('-', 1)[0])
            slug = re.sub(r'^\d+-', '', f)[:-3]
            specs.append((f, num, slug))
        nums = [s[1] for s in specs]
        if nums != list(range(1, len(nums) + 1)):
            fail('docs/manual', 'chapters are not numbered 1..N: %s' % nums)
        grouped = [n for _, items in GROUPS for n, _ in items]
        if sorted(grouped) != nums:
            fail('tools/docs-build.py GROUPS', 'the sidebar groups list %s, the manual has %s' % (sorted(grouped), nums))
        # pages refer to each other, so register every page before parsing any (links are resolved while parsing)
        for f, num, slug in specs:
            self.by_file['docs/manual/' + f] = _Lazy(f, num, slug)
        self.by_file['docs/manual/README.md'] = _Lazy('README.md', 0, 'index')
        for key, lazy in list(self.by_file.items()):
            page = Page(self, os.path.join(self.manual, lazy.name), lazy.num, lazy.slug)
            self.by_file[key] = page
        self.chapters = [self.by_file['docs/manual/' + f] for f, _, _ in specs]
        self.readme = self.by_file['docs/manual/README.md']
        # fragments recorded during parsing point at the placeholders: map them to the real pages
        names = {p.name: p for p in self.chapters + [self.readme]}
        for k, (target, frag, where) in enumerate(self.frags):
            self.frags[k] = (names[target.name], frag, where)

    def diagram(self, page, b):
        src = b['text'].strip()
        for f in sorted(os.listdir(DIAGRAMS)):
            if not f.endswith('.svg'):
                continue
            svg = open(os.path.join(DIAGRAMS, f), encoding='utf-8').read()
            m = re.search(r'<desc[^>]*>(.*?)</desc>', svg, re.S)
            if m and html.unescape(m.group(1)).strip() == src:
                w, h = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups()
                alt = html.unescape(re.search(r'<title[^>]*>(.*?)</title>', svg, re.S).group(1)).strip()
                self.diagrams.append(f)
                return ('<figure class="shot diagram"><div class="frame" tabindex="0" role="region" aria-label="Diagram: %s"><img src="images/%s" alt="%s" width="%s" '
                        'height="%s"></div>\n<details class="diagram-text"><summary data-gen>Show as text</summary>'
                        '<figure class="code"><figcaption data-gen><span>mermaid</span><button class="copy" '
                        'type="button">Copy</button></figcaption><pre tabindex="0" role="region" aria-label="Code '
                        '(mermaid)"><code>%s</code></pre></figure></details></figure>'
                        % (esc(page.title_src), esc(f), esc(alt), w, h, esc(b['text'])))
        fail('%s:%d' % (page.name, b['ln']), 'a Mermaid diagram with no hand-drawn SVG in tools/docs-diagrams/ whose '
             '<desc> is its source — redraw the diagram (the source changed)')

    def check_frags(self):
        for target, frag, where in self.frags:
            if not any(h.get('id') == frag for h in Page.walk(target.blocks)):
                fail(where, 'a link to #%s, which %s does not have' % (frag, target.name))

    # ---- page frame
    def sidebar(self, current):
        nums = {p.num: p for p in self.chapters}
        out = []
        for group, items in GROUPS:
            out.append('<h2>%s</h2><ol>' % esc(group))
            for n, label in items:
                p = nums[n]
                cur = ' aria-current="page"' if p is current else ''
                out.append('<li><a href="%s"%s>%s</a></li>' % (p.href, cur, esc(label)))
            out.append('</ol>')
        return '\n'.join(out)

    @staticmethod
    def toc(page):
        hs = [h for h in page.headings if h['level'] in (2, 3)]
        if len(hs) < 3:
            return '', ''
        out, open_sub = [], False
        for k, h in enumerate(hs):
            text = re.sub(r'<a [^>]*>|</a>', '', page.inline(h['src'], h['ln']))
            if h['level'] == 2:
                if open_sub:
                    out.append('</ol></li>'); open_sub = False
                elif k:
                    out.append('</li>')
                out.append('<li><a href="#%s">%s</a>' % (h['id'], text))
            else:
                if not open_sub:
                    if k == 0:
                        out.append('<li><ol>')
                    else:
                        out.append('<ol>')
                    open_sub = True
                out.append('<li><a href="#%s">%s</a></li>' % (h['id'], text))
        out.append('</ol></li>' if open_sub else '</li>')
        lst = '<ol>\n%s\n</ol>' % '\n'.join(out)
        return ('<nav class="toc" aria-label="On this page">\n<h2>On this page</h2>\n%s\n</nav>' % lst,
                '<details class="toc-m"><summary>On this page</summary>\n%s\n</details>' % lst)

    def frame(self, page, title, description, canonical, article, toc):
        tpl = open(TEMPLATE, encoding='utf-8').read()
        for k, v in (('TITLE', esc(title)), ('DESCRIPTION', esc(description)), ('CANONICAL', canonical),
                     ('SIDEBAR', self.sidebar(page)), ('TOC', toc), ('ARTICLE', article)):
            tpl = tpl.replace('{{%s}}' % k, v)
        return tpl

    def chapter_html(self, page):
        k = self.chapters.index(page)
        title_html = page.inline(page.title_src, 1)
        title = strip_tags(title_html)
        summary = summary_of(page)
        toc, toc_m = self.toc(page)
        prev = self.chapters[k - 1] if k else None
        nxt = self.chapters[k + 1] if k + 1 < len(self.chapters) else None
        pager = ['<ul class="pager">']
        if prev:
            pager.append('<li class="prev"><a href="%s" rel="prev"><small>&larr; Previous</small><b>%s</b></a></li>'
                         % (prev.href, strip_tags_keep_code(prev.inline(prev.title_src, 1))))
        else:
            pager.append('<li class="prev"><a href="./" rel="prev"><small>&larr; Contents</small><b>The Dozer Sandbox '
                         'manual</b></a></li>')
        if nxt:
            pager.append('<li class="next"><a href="%s" rel="next"><small>Next &rarr;</small><b>%s</b></a></li>'
                         % (nxt.href, strip_tags_keep_code(nxt.inline(nxt.title_src, 1))))
        pager.append('</ul>')
        article = '\n'.join([
            '<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="./">Docs</a></li><li aria-current="page">%s'
            '</li></ol></nav>' % strip_tags_keep_code(title_html),
            '<header class="chead">',
            '<p class="eyebrow">Chapter %d</p>' % page.num,
            '<h1>%s</h1>' % strip_tags_keep_code(title_html),
            '<p class="summary">%s</p>' % summary,
            '</header>',
            toc_m,
            '<div class="prose">',
            '<!-- manual text -->',
            page.render(page.blocks),
            '<!-- /manual text -->',
            '</div>',
            '\n'.join(pager),
            '<p class="edit"><a href="%s/blob/main/docs/manual/%s">Edit this page on GitHub</a> &middot; Chapter %d of %d'
            '</p>' % (REPO, page.name, page.num, len(self.chapters)),
        ])
        return self.frame(page, '%s — Dozer Sandbox docs' % title, strip_tags(summary), BASE_URL + page.href,
                          article, toc)

    def index_html(self):
        page = self.readme
        body, table_seen = [], False
        for b in page.blocks:
            if b['t'] == 'table':
                if table_seen:
                    fail(page.name, 'the contents page has more than one table')
                table_seen = True
                cards = []
                for cells, ln in b['rows']:
                    m = re.match(r'^\[(.+)\]\((\d+)-[^)]+\.md\)$', cells[0])
                    if not m:
                        fail('%s:%d' % (page.name, ln), 'a contents row whose first cell is not one chapter link')
                    href = page.link(re.match(r'^\[.+\]\(([^)]+)\)$', cells[0]).group(1), '%s:%d' % (page.name, ln))
                    cards.append('<li><a href="%s"><span class="n" data-gen>%02d</span><b>%s</b><span>%s</span></a></li>'
                                 % (href, int(m.group(2)), page.inline(m.group(1), ln), page.inline(cells[1], ln)))
                body.append('<ul class="chlist">\n%s\n</ul>' % '\n'.join(cards))
                self.index_header = b['head']
            else:
                body.append(page.render([b]))
        linked = set(re.findall(r'href="([a-z0-9-]+\.html)', '\n'.join(body)))
        missing = [p.name for p in self.chapters if p.href not in linked]
        if missing:
            fail(page.name, 'the contents page does not link to %s' % ', '.join(missing))
        article = '\n'.join([
            '<header class="chead">',
            '<p class="eyebrow">User manual</p>',
            '<h1>%s</h1>' % page.inline(page.title_src, 1),
            '<p class="summary">Every chapter of the Dozer Sandbox manual, for the <code>doz</code> command and its '
            'dashboard.</p>',
            '<p class="meta">%d chapters. Built from dozer-sandbox <a href="%s/commit/%s">%s</a>.</p>'
            % (len(self.chapters), REPO, self.sha, self.sha),
            '</header>',
            '<div class="prose">',
            '<!-- manual text -->',
            '\n'.join(body),
            '<!-- /manual text -->',
            '</div>',
            '<p class="edit"><a href="%s/blob/main/docs/manual/README.md">Edit this page on GitHub</a></p>' % REPO,
        ])
        return self.frame(page, 'The Dozer Sandbox manual — Dozer Sandbox docs',
                          'The user manual for Dozer Sandbox: install, set up, and run AI coding agents in fast, '
                          'resumable Linux sandboxes on your Mac, with the doz command or its dashboard.',
                          BASE_URL, article, '')

    def write(self):
        os.makedirs(os.path.join(OUT, 'images'), exist_ok=True)
        pages = {'index.html': self.index_html()}
        for p in self.chapters:
            pages[p.href] = self.chapter_html(p)
        self.check_frags()
        keep = set(pages) | {'docs.css', 'docs.js', 'images'}
        for f in os.listdir(OUT):          # a renamed chapter leaves no stale page behind
            if f.endswith('.html') and f not in keep:
                os.remove(os.path.join(OUT, f))
        for name, text in pages.items():
            old = open(os.path.join(OUT, name), encoding='utf-8').read() if os.path.exists(os.path.join(OUT, name)) else None
            # keep the fingerprints tools/stamp.sh added, so a rebuild of unchanged pages changes nothing
            if old:
                for asset in ('../site.css', 'docs.css', 'docs.js'):
                    m = re.search(r'="%s(\?v=[0-9a-f]+)"' % re.escape(asset), old)
                    if m:
                        text = text.replace('="%s"' % asset, '="%s%s"' % (asset, m.group(1)))
            with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
                f.write(text)
        wanted = {os.path.basename(i) for i in self.images} | set(self.diagrams)
        for f in os.listdir(os.path.join(OUT, 'images')):
            if f not in wanted:
                os.remove(os.path.join(OUT, 'images', f))
        for img in sorted(self.images):
            shutil.copyfile(os.path.join(self.manual, img), os.path.join(OUT, img))
        for f in self.diagrams:
            shutil.copyfile(os.path.join(DIAGRAMS, f), os.path.join(OUT, 'images', f))
        self.sitemap(pages)
        return pages

    def sitemap(self, pages):
        path = os.path.join(SITE, 'sitemap.xml')
        s = open(path, encoding='utf-8').read()
        s = re.sub(r'  <url><loc>https://dozersandbox\.com/docs/[^<]*</loc>.*?</url>\n', '', s)
        urls = ''.join('  <url><loc>%s%s</loc><lastmod>%s</lastmod></url>\n'
                       % (BASE_URL, '' if n == 'index.html' else n, self.date)
                       for n in ['index.html'] + [p.href for p in self.chapters])
        s = s.replace('</urlset>', urls + '</urlset>')
        open(path, 'w', encoding='utf-8').write(s)


class _Lazy:
    """A page before it is parsed: its href is all a link needs."""
    def __init__(self, name, num, slug):
        self.name, self.num, self.slug = name, num, slug
        self.href = slug + '.html' if num else './'


def strip_tags_keep_code(h):
    return re.sub(r'<(?!/?code\b)[^>]+>', '', h)


# ------------------------------------------------------------------------------------------------ the self-check
class TextOf(HTMLParser):
    """The words of the manual text region and its <pre> blocks, skipping what the build added (data-gen)."""
    VOID = {'img', 'br', 'hr', 'input', 'meta', 'link'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.text, self.pres, self.pre = [], [], [], None

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        a = dict(attrs)
        skip = 'data-gen' in a or bool(self.stack and self.stack[-1][1])
        self.stack.append((tag, skip))
        if tag == 'pre':
            self.pre = []

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        t, _ = self.stack.pop()
        if t != tag:
            raise BuildError('the output HTML is not well nested: </%s> closes <%s>' % (tag, t))
        if tag == 'pre':
            self.pres.append(''.join(self.pre)); self.pre = None

    def handle_data(self, data):
        if self.stack and self.stack[-1][1]:
            return
        if self.pre is not None:
            self.pre.append(data)
        else:
            self.text.append(data)


def words(s):
    return Counter(re.findall(r'\w+', s))


def source_text(page, skip_lines=()):
    """The manual page's words and code blocks, read straight from the Markdown (independently of the converter)."""
    text, codes, fence, buf = [], [], None, []
    for k, line in enumerate(page.lines, 1):
        if fence:
            if re.match(r'^\s*%s%s*\s*$' % (re.escape(fence), re.escape(fence[0])), line):
                codes.append('\n'.join(buf)); fence = None
            else:
                buf.append(line[indent:] if line[:indent].strip() == '' else line.lstrip())
            continue
        m = re.match(r'^(\s*(?:>\s?)?)(`{3,}|~{3,})', line)
        if m:
            fence, buf, indent = m.group(2), [], len(m.group(1))
            continue
        if k in skip_lines or TABLE_SEP.match(line.strip()) and '-' in line:
            continue
        line = re.sub(r'<!--.*?-->', '', line)
        line = re.sub(r'^\s*(?:>\s?)*\s*(?:[-*+]|\d+[.)])\s', ' ', line)
        line = re.sub(r'(!?)\[([^\]]*)\]\([^)\s]+\)', r'\2', line)
        text.append(line)
    # links whose text spans a line break: drop the (url) part too
    joined = re.sub(r'\]\((?:[^)\s]+)\)', ']', '\n'.join(text))
    return words(joined), codes


def self_check(build, pages):
    report = []
    for name, src_page, skip in [('index.html', build.readme, build.index_skip())] + \
            [(p.href, p, ()) for p in build.chapters]:
        out = open(os.path.join(OUT, name), encoding='utf-8').read()
        region = out.split('<!-- manual text -->', 1)[1].split('<!-- /manual text -->', 1)[0]
        h1 = re.search(r'<h1>(.*?)</h1>', out, re.S).group(1)
        parser = TextOf()
        parser.feed('<div>%s</div><div>%s</div>' % (h1, region))
        parser.close()
        if parser.stack:
            raise BuildError('%s: unclosed elements in the output' % name)
        got_words = words(' '.join(parser.text))
        got_codes = parser.pres
        want_words, want_codes = source_text(src_page, skip)
        if got_words != want_words:
            lost = want_words - got_words
            extra = got_words - want_words
            raise BuildError('%s: the words differ from %s — missing %s, extra %s'
                             % (name, src_page.name, dict(lost.most_common(12)), dict(extra.most_common(12))))
        if got_codes != want_codes:
            for a, b in zip(want_codes, got_codes + [''] * len(want_codes)):
                if a != b:
                    raise BuildError('%s: a code block differs from %s:\n%r\n%r' % (name, src_page.name, a, b))
            raise BuildError('%s: %d code blocks, the source has %d' % (name, len(got_codes), len(want_codes)))
        report.append((name, sum(want_words.values()), len(want_codes)))
    return report


def crawl():
    """Every href/src in docs/*.html that stays on the site resolves to a file, and every #fragment to an id."""
    ids, refs = {}, []
    for f in sorted(os.listdir(OUT)):
        if f.endswith('.html'):
            s = open(os.path.join(OUT, f), encoding='utf-8').read()
            ids[f] = set(re.findall(r'\sid="([^"]+)"', s))
            refs += [(f, r) for r in re.findall(r'\s(?:href|src)="([^"]+)"', s)]
    n = 0
    for f, r in refs:
        if re.match(r'^(https?:|mailto:)', r):
            continue
        path, _, frag = html.unescape(r).partition('#')
        path = path.split('?')[0]
        target = os.path.normpath(os.path.join(OUT, path)) if path else os.path.join(OUT, f)
        if os.path.isdir(target):
            target = os.path.join(target, 'index.html')
        if not os.path.exists(target) and os.path.exists(target + '.html'):
            continue  # a clean URL (GitHub Pages serves privacy.html at /privacy)
        if not os.path.exists(target):
            raise BuildError('docs/%s: a link to a missing file: %s' % (f, r))
        if frag:
            key = os.path.relpath(target, OUT)
            if key in ids and frag not in ids[key]:
                raise BuildError('docs/%s: a link to a missing #fragment: %s' % (f, r))
        n += 1
    return n


def _index_skip(self):
    """The README's table header row (its two column names) is the one piece of source text the contents page
    does not show: the table becomes chapter cards."""
    for k, line in enumerate(self.readme.lines, 1):
        if line.startswith('|') and k < len(self.readme.lines) and TABLE_SEP.match(self.readme.lines[k]):
            return (k,)
    return ()


Build.index_skip = _index_skip


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    app = os.path.abspath(sys.argv[1])
    try:
        build = Build(app)
        pages = build.write()
        report = self_check(build, pages)
        links = crawl()
    except BuildError as e:
        sys.exit('docs-build: FAILED: %s' % e)
    total_w = sum(r[1] for r in report)
    total_c = sum(r[2] for r in report)
    print('docs-build: %d pages from dozer-sandbox %s (%d chapters + contents), %d images, %d diagram'
          % (len(pages), build.sha, len(build.chapters), len(build.images), len(build.diagrams)))
    print('  self-check: %d words and %d code blocks of the source found in the pages (every page matches '
          'exactly)' % (total_w, total_c))
    print('  links: %d on-site links and #fragments resolve' % links)
    print('  warning callouts: %s' % ('; '.join(build.warnings) or 'none'))
    print('  now run tools/stamp.sh')


if __name__ == '__main__':
    main()
