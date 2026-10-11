#!/usr/bin/env python3
"""tools/blog-build.py POSTS_REPO [--drafts --out DIR] — build the blog (blog/) from the private posts repository.

POSTS_REPO/posts/YYYY-MM-DD-slug/index.md is one post: a front matter block, then Markdown, plus its images beside it
(see the posts repo's README). This tool reads ONLY `status: published` posts; the posts repository is private and
drafts never reach the public website repository. Stdlib only. The Markdown is rendered by docs-build.py's renderer
(imported, not copied), so a post is written in the same dialect as the manual, and it FAILS (exit 1, file:line) on
anything that dialect rejects, on a bad front matter and on a missing image.

Writes, into the website (or --out):
  blog/index.html            the list, newest first
  blog/<slug>.html           one page per post (served at /blog/<slug>)
  blog/images/<slug>/…       the post's images
  blog/feed.xml              Atom, full content, absolute URLs
and rewrites the blog entries of sitemap.xml (the other entries are kept). Everything under blog/ is generated and
rebuilt from scratch each run: never edit it by hand. Then run tools/stamp.sh (it fingerprints the CSS/JS links).

--drafts also builds `status: draft` posts, for a local preview; --out is then REQUIRED and must be outside the website
repository, so a draft can never be committed here. A preview copy of the site's CSS/JS is written beside it."""
import argparse, datetime, html, importlib.util, os, re, shutil, struct, sys, types

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://dozersandbox.com/'
TOPICS = {'release-news': 'Release news', 'early-access': 'Early access', 'tips': 'Tips and tricks'}
KEYS = ('title', 'date', 'topics', 'summary', 'email', 'status')
REPO = 'https://github.com/dozer-sandbox/dozer-sandbox'

_spec = importlib.util.spec_from_file_location('docs_build', os.path.join(SITE, 'tools', 'docs-build.py'))
docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docs)
esc = docs.esc


class BuildError(Exception):
    pass


def fail(where, msg):
    raise BuildError('%s: %s' % (where, msg))


# ---------------------------------------------------------------------------------------------------- front matter
def parse_front(path, name):
    lines = open(path, encoding='utf-8').read().split('\n')
    if not lines or lines[0].strip() != '---':
        fail(name + ':1', 'a post starts with a --- front matter block')
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
    if end is None:
        fail(name + ':1', 'the front matter block is never closed with ---')
    fm = {}
    for i in range(1, end):
        raw = lines[i]
        if not raw.strip():
            continue
        m = re.match(r'^([a-z]+):\s*(.*?)\s*$', raw)
        if not m:
            fail('%s:%d' % (name, i + 1), 'not a "key: value" line: %r' % raw)
        key, val = m.group(1), m.group(2)
        if key not in KEYS:
            fail('%s:%d' % (name, i + 1), 'unknown front matter key %r (allowed: %s)' % (key, ', '.join(KEYS)))
        if key in fm:
            fail('%s:%d' % (name, i + 1), 'duplicate key %r' % key)
        if key in ('topics', 'email', 'status', 'date'):
            val = re.sub(r'\s+#.*$', '', val).strip()         # a trailing comment
        fm[key] = (val, i + 1)
    for key in KEYS:
        if key not in fm:
            fail(name, 'missing front matter key %r' % key)
    f = {k: v[0] for k, v in fm.items()}
    if not f['title'] or not f['summary']:
        fail(name, 'title and summary must not be empty')
    try:
        datetime.date.fromisoformat(f['date'])
    except ValueError:
        fail('%s:%d' % (name, fm['date'][1]), 'date must be YYYY-MM-DD, got %r' % f['date'])
    if not re.match(r'^\[[^\]]*\]$', f['topics']):
        fail('%s:%d' % (name, fm['topics'][1]), 'topics must be a list like [release-news, tips]')
    topics = [t.strip() for t in f['topics'][1:-1].split(',') if t.strip()]
    if not topics or len(set(topics)) != len(topics) or any(t not in TOPICS for t in topics):
        fail('%s:%d' % (name, fm['topics'][1]), 'topics must be a non-empty set of %s, got %s' % (
            ' | '.join(TOPICS), topics))
    f['topics'] = [t for t in TOPICS if t in topics]       # canonical order
    if f['email'] not in ('true', 'false'):
        fail('%s:%d' % (name, fm['email'][1]), 'email must be true or false')
    f['email'] = f['email'] == 'true'
    if f['status'] not in ('draft', 'published'):
        fail('%s:%d' % (name, fm['status'][1]), 'status must be draft or published')
    return f, lines[end + 1:], end + 2


# ------------------------------------------------------------------------------------------------------ rendering
def image_size(path, where):
    with open(path, 'rb') as fh:
        head = fh.read(32)
        if head[:8] == b'\x89PNG\r\n\x1a\n':
            return struct.unpack('>II', head[16:24])
        if head[:2] == b'\xff\xd8':
            fh.seek(2)
            while True:
                b = fh.read(1)
                while b and b != b'\xff':
                    b = fh.read(1)
                while b == b'\xff':
                    b = fh.read(1)
                if not b:
                    break
                marker = b[0]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    continue
                n = struct.unpack('>H', fh.read(2))[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    seg = fh.read(5)
                    h, w = struct.unpack('>HH', seg[1:5])
                    return w, h
                fh.seek(n - 2, 1)
    fail(where, 'an image that is not a PNG or JPEG: %s' % os.path.basename(path))


class Post(docs.Page):
    """docs-build.py's Page, adapted to one post: no h1 in the body (the title is front matter), plain image file
    names beside index.md, absolute links only."""

    def __init__(self, folder, slug, body, line0):
        self.build = types.SimpleNamespace(warnings=[], frags=[], images=set(), diagram=None)
        self.folder, self.slug = folder, slug
        self.path = os.path.join(folder, 'index.md')
        self.name = os.path.basename(folder) + '/index.md'
        self.lines = body
        self.images = []
        self.blocks = docs.parse_blocks(body, line0, self)
        self.ids, self.headings, self.code_blocks = docs.Counter(), [], []
        self.fragments = []
        self.title_src = ''
        last = 1
        for b in self.walk(self.blocks):
            if b['t'] != 'h':
                continue
            where = '%s:%d' % (self.name, b['ln'])
            if b['level'] == 1:
                fail(where, 'no h1 in a post body: the title comes from the front matter')
            if b['level'] > last + 1:
                fail(where, 'a skipped heading level (h%d after h%d)' % (b['level'], last))
            last = b['level']
            plain = docs.strip_tags(docs.Inline(self, where).render(b['src']))
            base = docs.slugify(plain)
            hid = base if not self.ids[base] else '%s-%d' % (base, self.ids[base])
            self.ids[base] += 1
            b['id'], b['plain'] = hid, plain

    def link(self, url, where):
        if re.match(r'^(https?|mailto):', url):
            return url
        if url.startswith('#'):
            self.fragments.append((url[1:], where))
            return url
        fail(where, 'a link must be an absolute https:// URL (or a #heading of this post): %s' % url)

    def code(self, b):
        if b['lang'] == 'mermaid':
            fail('%s:%d' % (self.name, b['ln']), 'no Mermaid diagrams in a post')
        return docs.Page.code(self, b)

    def image(self, b):
        where = '%s:%d' % (self.name, b['ln'])
        src = b['src']
        if '/' in src or src.startswith('.') or not re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]*$', src):
            fail(where, 'an image must be a plain file name beside index.md: %s' % src)
        disk = os.path.join(self.folder, src)
        if not os.path.isfile(disk):
            fail(where, 'a missing image: %s' % src)
        w, h = image_size(disk, where)
        if src not in self.images:
            self.images.append(src)
        alt = self.inline(b['alt'], b['ln'])
        return ('<figure class="shot"><div class="frame"><img src="images/%s/%s" alt="%s" width="%d" height="%d" '
                'loading="lazy" decoding="async"></div></figure>'
                % (self.slug, esc(src), esc(docs.strip_tags(alt)), w, h))

    def check_fragments(self):
        have = set(self.ids)
        have |= {k if n == 1 else k for k, n in self.ids.items()}
        ids = {b['id'] for b in self.walk(self.blocks) if b['t'] == 'h'}
        for frag, where in self.fragments:
            if frag not in ids:
                fail(where, 'a link to #%s, which is not a heading of this post' % frag)

    def body_html(self):
        return self.render(self.blocks)


# --------------------------------------------------------------------------------------------------------- pages
ALT = ('The Dozer Sandbox sleeping bulldozer, with the name and the line: Fast, resumable, secure Linux sandboxes '
       'for AI coding agents on your Mac.')


def fmt_date(d):
    d = datetime.date.fromisoformat(d)
    return '%d %s %d' % (d.day, d.strftime('%B'), d.year)


def chips(topics):
    return ''.join('<span class="chip">%s</span>' % esc(TOPICS[t]) for t in topics)


def head(title, desc, url, kind, extra=''):
    t, d = esc(title), esc(desc)
    return '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#ffffff">
<meta property="og:type" content="{kind}">
<meta property="og:site_name" content="Dozer Sandbox">
<meta property="og:locale" content="en_US">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{base}og-image.png">
<meta property="og:image:secure_url" content="{base}og-image.png">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{base}og-image.png">
<meta name="twitter:image:alt" content="{alt}">
{extra}<link rel="alternate" type="application/atom+xml" title="Dozer Sandbox blog" href="feed.xml">
<link rel="icon" type="image/png" href="../favicon.png">
<link rel="apple-touch-icon" href="../apple-touch-icon.png">
<link rel="stylesheet" href="../site.css">
<script src="../nav.js"></script>
<link rel="stylesheet" href="../docs/docs.css">
<script defer src="../docs/docs.js"></script>
<script defer src="../signup.js"></script>
</head>
'''.format(t=t, d=d, url=url, kind=kind, base=BASE, alt=esc(ALT), extra=extra)


def site_chrome():
    """The header and footer of the root pages (privacy.html), with their links made relative to /blog/."""
    s = open(os.path.join(SITE, 'privacy.html'), encoding='utf-8').read()
    header = s[s.index('<header class="nav">'):s.index('</header>') + len('</header>')]
    footer = s[s.index('<footer class="foot">'):s.index('</footer>') + len('</footer>')]

    def up(m):
        url = m.group(2)
        if re.match(r'^(https?:|mailto:)', url) or url.startswith('#'):
            return m.group(0)
        url = url[2:] if url.startswith('./') else url
        return '%s="../%s"' % (m.group(1), url)

    header = re.sub(r'(href)="([^"]*)"', up, header)
    footer = re.sub(r'(href)="([^"]*)"', up, footer)
    header = header.replace('<a href="../blog/">Blog</a>', '<a href="./" aria-current="page">Blog</a>')
    return header, footer


def signup_box(prefix, checked):
    def box(value, label, hint):
        c = ' checked' if value in checked else ''
        return ('    <label class="check"><input type="checkbox" name="interests" value="%s"%s><span><b>%s</b>'
                '<small>%s</small></span></label>\n' % (value, c, label, hint))
    return '''<div class="signup-box signup" data-signup-root>
<noscript><p class="note">This form needs JavaScript &mdash; or run <code>doz signup</code> in Terminal.</p></noscript>
<form data-signup action="#" method="post">
  <div class="field"><label for="{p}email">Email</label>
  <input id="{p}email" name="email" type="email" autocomplete="email" inputmode="email" required maxlength="254" placeholder="you@example.com"></div>
  <fieldset><legend>What would you like to hear about? <span class="muted">Choose at least one.</span></legend>
{boxes}  </fieldset>
  <p class="msg" data-signup-error role="alert" hidden></p>
  <button class="pill big" type="submit">Sign up</button>
  <p class="fine-s">Email only. We confirm by email, and every email has a one-click unsubscribe. <a href="../privacy">Privacy &rarr;</a></p>
</form>
<div class="result" data-signup-result role="status" aria-live="polite" tabindex="-1" hidden><p class="result-title" data-signup-title></p><p data-signup-text></p></div>
</div>'''.format(p=prefix, boxes=box('release-news', 'Release news', 'New versions and what changed.')
                + box('early-access', 'Early access', 'Try beta and canary builds before they are released.')
                + box('tips', 'Tips and tricks', 'Ways to get more out of Dozer, now and then.'))


def post_page(p, header, footer):
    f = p['fm']
    url = BASE + 'blog/' + p['slug']
    title = '%s — Dozer Sandbox blog' % f['title']
    extra = ('<meta property="article:published_time" content="%s">\n' % f['date']
             + ''.join('<meta property="article:tag" content="%s">\n' % esc(TOPICS[t]) for t in f['topics']))
    topics = ', '.join(TOPICS[t] for t in f['topics'])
    return (head(title, f['summary'], url, 'article', extra) + '<body class="docs blog">\n'
            '<a class="skip" href="#main">Skip to the post</a>\n' + header + '\n<main id="main">\n'
            '<article class="prose article post">\n'
            '<p class="crumbs"><a href="./">&lsaquo; All posts</a></p>\n'
            '<header class="post-head"><p class="post-meta"><time datetime="%s">%s</time> %s</p>\n<h1>%s</h1>\n'
            '<p class="post-summary">%s</p></header>\n%s\n</article>\n'
            '<aside class="post-sub" aria-labelledby="sub-h"><div class="post-sub-in">\n'
            '<h2 id="sub-h">Get posts like this by email</h2>\n'
            '<p>%s. <a href="./">Read past issues &rarr;</a></p>\n%s\n</div></aside>\n</main>\n%s\n</body>\n</html>\n'
            % (f['date'], fmt_date(f['date']), chips(f['topics']), esc(f['title']), esc(f['summary']), p['html'],
               esc(topics), signup_box('post-', f['topics']), footer))


def index_page(posts, header, footer):
    items = ''
    for p in posts:
        f = p['fm']
        items += ('<article class="post-item"><p class="post-meta"><time datetime="%s">%s</time> %s</p>\n'
                  '<h2><a href="%s">%s</a></h2>\n<p>%s</p></article>\n'
                  % (f['date'], fmt_date(f['date']), chips(f['topics']), p['slug'], esc(f['title']), esc(f['summary'])))
    if not items:
        items = '<p>No posts yet.</p>\n'
    desc = 'News, early access and tips and tricks from Dozer Sandbox. Also sent by email to anyone who signs up.'
    return (head('Blog — Dozer Sandbox', desc, BASE + 'blog/', 'website') + '<body class="docs blog">\n'
            '<a class="skip" href="#main">Skip to the posts</a>\n' + header + '\n<main id="main">\n'
            '<div class="prose blog-list">\n<h1>Blog</h1>\n'
            '<p class="post-summary">News, early access and tips and tricks. Every post is also sent by email to '
            'the people who asked for that kind of news. <a href="feed.xml">Atom feed</a></p>\n'
            '<div class="post-items">\n%s</div>\n</div>\n'
            '<aside class="post-sub" aria-labelledby="sub-h"><div class="post-sub-in">\n'
            '<h2 id="sub-h">Get these by email</h2>\n%s\n</div></aside>\n</main>\n%s\n</body>\n</html>\n'
            % (items, signup_box('blog-', ()), footer))


# --------------------------------------------------------------------------------------------------------- feed
def absolutize(body, slug):
    body = re.sub(r'(<img src=")images/', r'\1' + BASE + 'blog/images/', body)
    body = re.sub(r'(<a class="anchor" href=")#', r'\1' + BASE + 'blog/' + slug + '#', body)
    return re.sub(r'(<a href=")#', r'\1' + BASE + 'blog/' + slug + '#', body)


def x(s):
    return html.escape(s, quote=False)


def feed(posts):
    updated = (posts[0]['fm']['date'] if posts else '2026-01-01') + 'T00:00:00Z'
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<feed xmlns="http://www.w3.org/2005/Atom">',
           '  <title>Dozer Sandbox blog</title>',
           '  <subtitle>News, early access and tips and tricks from Dozer Sandbox.</subtitle>',
           '  <id>%sblog/</id>' % BASE,
           '  <link rel="self" type="application/atom+xml" href="%sblog/feed.xml"/>' % BASE,
           '  <link rel="alternate" type="text/html" href="%sblog/"/>' % BASE,
           '  <updated>%s</updated>' % updated,
           '  <author><name>Dozer Sandbox</name><uri>%s</uri></author>' % BASE]
    for p in posts:
        f = p['fm']
        url = BASE + 'blog/' + p['slug']
        out += ['  <entry>', '    <title>%s</title>' % x(f['title']), '    <id>%s</id>' % url,
                '    <link rel="alternate" type="text/html" href="%s"/>' % url,
                '    <published>%sT00:00:00Z</published>' % f['date'],
                '    <updated>%sT00:00:00Z</updated>' % f['date'],
                '    <summary>%s</summary>' % x(f['summary'])]
        out += ['    <category term="%s" label="%s"/>' % (t, TOPICS[t]) for t in f['topics']]
        out += ['    <content type="html">%s</content>' % x(absolutize(p['html'], p['slug'])), '  </entry>']
    out.append('</feed>')
    return '\n'.join(out) + '\n'


# --------------------------------------------------------------------------------------------------------- main
def load_posts(repo, drafts):
    root = os.path.join(repo, 'posts')
    if not os.path.isdir(root):
        fail(repo, 'no posts/ folder')
    posts, seen = [], set()
    for d in sorted(os.listdir(root)):
        folder = os.path.join(root, d)
        if not os.path.isdir(folder) or d.startswith('.'):
            continue
        m = re.match(r'^(\d{4}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$', d)
        if not m:
            fail('posts/' + d, 'the folder must be named YYYY-MM-DD-slug (lower case, digits, hyphens)')
        slug = m.group(2)
        if slug in ('index', 'feed', 'images') or slug in seen:
            fail('posts/' + d, 'a reserved or duplicate slug: %s' % slug)
        seen.add(slug)
        if not os.path.isfile(os.path.join(folder, 'index.md')):
            fail('posts/' + d, 'no index.md')
        fm, body, line0 = parse_front(os.path.join(folder, 'index.md'), d + '/index.md')
        if fm['date'] != m.group(1):
            fail(d + '/index.md', 'the front matter date %s differs from the folder date %s' % (fm['date'], m.group(1)))
        if fm['status'] != 'published' and not drafts:
            continue
        post = Post(folder, slug, body, line0)
        post.check_fragments()
        if not ''.join(body).strip():
            fail(d + '/index.md', 'an empty post')
        posts.append({'slug': slug, 'fm': fm, 'html': post.body_html(), 'images': post.images, 'folder': folder})
    posts.sort(key=lambda p: (p['fm']['date'], p['slug']), reverse=True)
    return posts


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def sitemap(posts):
    path = os.path.join(SITE, 'sitemap.xml')
    s = open(path, encoding='utf-8').read()
    s = re.sub(r'  <url><loc>%sblog[^<]*</loc>[^\n]*\n' % re.escape(BASE), '', s)
    lines = []
    if posts:
        lines.append('  <url><loc>%sblog/</loc><lastmod>%s</lastmod></url>\n' % (BASE, posts[0]['fm']['date']))
    for p in posts:
        lines.append('  <url><loc>%sblog/%s</loc><lastmod>%s</lastmod></url>\n' % (BASE, p['slug'], p['fm']['date']))
    s = s.replace('</urlset>', ''.join(lines) + '</urlset>')
    open(path, 'w', encoding='utf-8').write(s)


def main():
    ap = argparse.ArgumentParser(description='Build the blog from the private posts repository.')
    ap.add_argument('repo', help='the posts repository (has posts/)')
    ap.add_argument('--drafts', action='store_true', help='also build drafts (preview only; needs --out)')
    ap.add_argument('--out', help='write here instead of the website (required with --drafts; outside the website repo)')
    a = ap.parse_args()
    out = SITE
    if a.drafts:
        if not a.out:
            fail('--drafts', '--out DIR is required (drafts are never built into the website repository)')
    if a.out:
        out = os.path.realpath(a.out)
        site = os.path.realpath(SITE)
        if a.drafts and (out == site or out.startswith(site + os.sep)):
            fail('--out', 'must be outside the website repository when building drafts: %s' % out)
    posts = load_posts(os.path.realpath(a.repo), a.drafts)
    header, footer = site_chrome()
    blog = os.path.join(out, 'blog')
    if os.path.isdir(blog):
        shutil.rmtree(blog)
    write(os.path.join(blog, 'index.html'), index_page(posts, header, footer))
    write(os.path.join(blog, 'feed.xml'), feed(posts))
    for p in posts:
        write(os.path.join(blog, p['slug'] + '.html'), post_page(p, header, footer))
        for img in p['images']:
            dest = os.path.join(blog, 'images', p['slug'], img)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(p['folder'], img), dest)
    if out == SITE:
        sitemap(posts)
    else:                                  # a preview copy: the page assets the pages link to
        for f in ('site.css', 'site.js', 'signup.js', 'nav.js', 'favicon.png', 'apple-touch-icon.png', 'og-image.png',
                  'docs/docs.css', 'docs/docs.js'):
            os.makedirs(os.path.dirname(os.path.join(out, f)) or out, exist_ok=True)
            shutil.copyfile(os.path.join(SITE, f), os.path.join(out, f))
    print('blog-build: %d post%s%s -> %s' % (len(posts), '' if len(posts) == 1 else 's',
                                             ' (drafts included)' if a.drafts else '', blog))
    if out == SITE:
        print('  now run tools/stamp.sh')


if __name__ == '__main__':
    try:
        main()
    except BuildError as e:
        print('blog-build: FAILED: %s' % e, file=sys.stderr)
        sys.exit(1)
