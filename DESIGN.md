# Docs design guide (dozersandbox.com/docs)

The rules for the user manual rendered as HTML pages on the site. `DESIGN.html` is the same guide as a living
specimen, built with `docs/docs.css` (a draft that sits on top of `site.css` and uses its tokens). This file is
the rules in words; where they differ, `DESIGN.html` and `docs/docs.css` are the detail.

## 1. Principles

1. **The same site.** Same header and footer as the home page, black on white, 1px black borders, pills, the hard
   black shadow, and the single accent `#ffd60a` with its tints. "Docs" is the current item in the header.
2. **Built for reading and scanning.** One column, 70ch wide, 17px body at line-height 1.65. A chapter sidebar and
   an on-page contents mean nobody scrolls to find a section.
3. **Fast.** Static HTML, `site.css` + `docs/docs.css`, nothing else. Readable with JavaScript off. No web fonts, no
   third-party scripts. The one script (`docs.js`, about 20 lines) adds Copy buttons and the current-section marker.
4. **Accessible.** Black on white (21:1); the lightest text is `#555` (7.5:1). 3px black focus ring (from
   `site.css`), skip link to `#main`, one `h1`, no skipped heading levels, scroll boxes (tables, code) are
   keyboard-focusable and labelled. Nothing is conveyed by colour alone.
5. **Works at 390px.** No sideways page scroll ever; wide content scrolls inside its own box.

## 2. Layout

- Header: the home page's `.nav` verbatim; *Docs* has `aria-current="page"`. Footer: the home page's.
- `.dlayout` is a grid: **sidebar (264px) | article (max 70ch) | on this page (224px)**, centred, max 1320px.
  - 1180px and up: all three; sidebar and contents are sticky under the 48px header.
  - 860-1179px: sidebar and article; the on-page contents is a collapsed `<details>` above the article.
  - Under 860px: one column with 16px gutters. The sidebar becomes a `<details class="chapters">` button
    ("Chapters", a pill with a +/-), closed by default. No JavaScript. On wide screens the same element is shown
    open via `::details-content`; a browser without it simply keeps the button.
- **Sidebar**: chapters grouped as the manual's README does (Start here, Install and set up, Using Dozer, Files
  and tools, Looking after sandboxes, Reference, Experimental). Group names are 12px small caps. The current
  chapter: `--tint` background, bold, a 3px black bar on its left, `aria-current="page"`. Hover: `--tint-soft`.
- **On this page**: all `h2`/`h3`, grey with a hairline rail; the section in view is black, bold with a 3px bar
  (script; harmless without it). Omitted when a chapter has under three headings.
- **Breadcrumb**: `Docs > Chapter title`, 14px; the last item is bold, not a link.
- **Chapter header**: accent pill "Chapter 7", `h1`, a one-line summary (grey, 18-21px) taken from the first
  sentence of the manual page's opening paragraph, then a 1px black rule.
- **Foot of every chapter**: previous/next cards (reading order of the manual, not sidebar order; `<small>`
  label + bold title, hover = accent), then "Edit this page on GitHub" (14px) linking to the `.md` on
  `dozer-sandbox/dozer-sandbox`, branch `main`.
- **Contents page `/docs/`**: the README's introduction, the "read these first" numbered list, every chapter as
  a card (mono number, bold title, the "read it when you want to..." line; hover = `--tint`), then Conventions.

## 3. Typography

System stacks only: `--font` and `--mono` from `site.css`.

| element | spec |
|---|---|
| `h1` | clamp(34px, 6vw, 46px), 700, -0.03em, line-height 1.06, balanced |
| `h2` | 28px, 700, -0.025em, 1.15; 1px hairline above, 2.2em space above |
| `h3` | 21px, 700, -0.015em; 1.9em above |
| `h4` | 17px bold; 1.6em above |
| body | 17px / 1.65, left-aligned, paragraphs 1.1em apart, `overflow-wrap: break-word` |
| table text | 15px / 1.45; captions 14px; small labels 12px |
| code | mono; inline 0.88em, blocks 14.5px (13px at 600px and under) |

Bold lead-ins stay bold. There is no visited-link colour and no italics-for-emphasis beyond what the manual has.

## 4. Components

- **Inline code**: 0.88em mono, black on `--tint-soft`, 5px radius, may wrap anywhere (long setting keys).
- **`<kbd>`**: white, 1px black border, 2px bottom, 6px radius, mono 600.
- **Code block** `figure.code`: white panel, 1px black border, 14px radius, `box-shadow: 0 4px 0 #000`. Caption
  bar (`--tint-soft`, black bottom rule): language label in lower-case mono (`sh`, `text`, `yaml`, `toml`; no
  language shows `text`) and a Copy pill (shown only when JS runs; becomes accent and says "Copied" for 1.5s).
  `pre` never wraps: it scrolls inside the block and is focusable. No syntax colours; only shell comments are
  grey `#555`. ASCII diagrams use `.code.diagram` (line-height 1.3). Mermaid (chapter 5's state diagram) is
  pre-rendered to SVG at build time (black strokes, accent states) with the source in a `<details>`.
- **Table** `.tablewrap`: 1px black border, 14px radius, `overflow-x: auto`, `tabindex=0`, `role=region`,
  `aria-label` from the preceding heading. Header row on `--tint` with a black rule; body hairlines `--hair`;
  every other row a 2.5% black wash; **first column sticky** and bold; `.wide` (5+ columns) has min-width 860px
  and the last column at least 22em. Code in cells does not wrap.
- **Blockquotes** (the converter classifies them):
  - *note*: starts with a bold lead-in -> 4px black left rule, no fill.
  - *warning*: lead-in in the converter's short list (e.g. "A convenience, not a security boundary", "Not in
    public releases", "Experimental") -> `.callout.warn`: `--tint` panel, 1px black border, 14px radius, black
    "Warning" pill. The only accent panel in the docs.
  - *example*: no bold lead-in (a prompt, expected output) -> mono on `--tint-soft`, 1px black border, 14px
    radius, small "Example" label.
- **Lists**: black discs; numbers bold and tabular; items 0.4em apart; nested lists indented 1.5em.
- **Links**: black, 1px underline, 3px offset; hover = accent highlight and 2px underline. Off-site links end in
  a small arrow. Cross-chapter links go to the chapter's page, with `#fragment` kept.
- **Heading anchors**: every `h2`-`h4` has an id (GitHub-style slug, so existing manual `#fragment` links keep
  working) and a `#` link after the text: invisible until hover/focus, 45% visible on touch. The target flashes
  `--tint` for 1.6s.
- **Figures** `figure.shot`: image in a 1px black frame, 14px radius, the hard shadow, full column width,
  `width`/`height` attributes set; caption (the Markdown alt text) 14px grey.
- **Print**: header, sidebar, contents, pager, Copy hidden; shadows removed.

## 5. Colour

Black, white, greys and the one accent. No other hue: no blue links, no red warnings, no syntax colours. The
accent stays `#ffd60a` (the picker is local to the home page and not loaded in the docs).

| token | value | used for |
|---|---|---|
| white | `#fff` | page, panels, code, table body |
| black | `#000` | text, borders, shadow, focus ring, Warning pill |
| `--ink-2` | `#2b2b2d` | summaries, captions, group names |
| grey | `#555` | shell comments, heading anchors (lightest text) |
| `--hair` | black 22% | row lines, h2 rules, contents rail |
| `--accent` | `#ffd60a` | chapter pill, link/button hover, Copy done |
| `--tint` | accent 55% | current chapter, table header, warning panel, card hover |
| `--tint-soft` | accent 24% | inline code, code caption, example quote, target flash |

## 6. URLs and structure

- `/docs/` = contents page (`docs/index.html`). Chapters: `/docs/<slug>.html`, where slug = the Markdown file name
  **without the number prefix and extension**: `07-terminals-and-sessions.md` -> `/docs/terminals-and-sessions.html`.
  Numbers stay out of URLs so chapters can be renumbered; the number is shown as "Chapter 7" and derived from the
  file name. (Same `.html` style as `timeline.html`.)
- Link rewriting (done by the converter): `NN-slug.md#x` -> `slug.html#x`; `README.md` -> `./`; `images/x.png` ->
  `images/x.png` (copied to `docs/images/`); links leaving the manual (`../CLI-USER-GUIDE.md`) -> absolute GitHub
  URLs. An unresolvable link or fragment fails the build.
- `tools/stamp.sh` must fingerprint `docs.css` (and `docs.js`) in every page under `docs/` (`?v=<hash>`; pages
  there use `../site.css`-relative or root-absolute paths consistently), and `sitemap.xml` lists every page.
- At launch the home page's "Docs" link, the footer's "Manual" link and the manual links in `cli-commands.json`
  (`tools/cli-data.py`) move from GitHub to `/docs/...`.

## 7. The build (proposal, not built)

`tools/docs-build.py APP_CHECKOUT` in the style of `tools/cli-data.py`: reads `APP_CHECKOUT/docs/manual/*.md`,
writes `docs/*.html` and `docs/images/`; then `tools/stamp.sh`; commit the generated pages (the manual in the app
repo stays the single source; pages are never hand-edited).

- **Converter**: pandoc, cmark and Python's `markdown` are not installed on this Mac. Write a small
  dependency-free converter (<400 lines) for the subset the manual uses: ATX headings, paragraphs, bold, italic,
  inline code, links, images, nested bullet/numbered lists, pipe tables, blockquotes, fenced code (`sh`, `yaml`,
  `toml`, `text`, `mermaid`), rules, dropped HTML comments. Verified against all 25 chapters. Fallback if the
  subset grows: vendor one MIT single-file library (e.g. markdown-it-py) into `tools/vendor/`, build-time only.
- **Fails loudly** on unknown syntax, broken chapter links/fragments, missing images, ragged table rows, skipped
  heading levels. **Self-checks** by parsing its output and comparing words and every code block with the source.
- **Sync**: takes the app checkout path like `cli-data.py`; stamps the app commit it built from into
  `docs/index.html`; run with the release's checkout so docs and binary match. Sidebar groups and prev/next
  order come from the manual's `README.md`; the page frame lives in `tools/docs-template.html`.
- **Mermaid**: needs a build-time renderer or a hand-drawn SVG for the single diagram; no library is shipped.
