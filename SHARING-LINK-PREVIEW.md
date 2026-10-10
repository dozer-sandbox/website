# Sharing: the link preview (the thumbnail card)

What makes a dozersandbox.com link show a card — title, description and picture — when it is pasted into iMessage,
Slack, WhatsApp, Discord, Telegram, X, LinkedIn or Facebook, how it is set up here, how to check it, and how to make a
platform refresh a stale card. Set up and verified 2026-10-10 (commit c44a5e4).

## What a link preview needs

| Needed | Here |
|---|---|
| **Open Graph tags** in each page's `<head>` — read by iMessage, Slack, WhatsApp, Discord, Facebook, LinkedIn, Telegram | ✅ every page |
| **Twitter/X card tags** — `twitter:card = summary_large_image` and `twitter:image` | ✅ every page |
| **An image at an absolute `https://` URL, 1200×630**, under ~300 KB (WhatsApp is the strictest) | ✅ `og-image.png` 1200×630, 184 KB (also `og-image.jpg`, 130 KB) |
| **The crawlers can fetch the page and the image** — a CDN's bot protection can block them | ✅ all return 200 through Cloudflare (tested by user agent, below) |
| A small square icon — iMessage and iPhone home screens use it | ✅ `apple-touch-icon.png` 180×180, plus `favicon.png` |

## The tags on every page

Every page — `index.html`, `timeline.html`, `docs/index.html` and every chapter — carries:

- `<link rel="canonical">`, `<meta name="description">` (the page's own)
- `og:type` — `website` (home, timeline) or `article` (docs)
- `og:site_name` (Dozer Sandbox), `og:locale` (en_US)
- `og:title`, `og:description` — the page's own (a docs chapter: "Terminals and sessions — Dozer Sandbox docs")
- `og:url` — equal to the canonical URL
- `og:image` = `og:image:secure_url` = `https://dozersandbox.com/og-image.png`, `og:image:type` (image/png),
  `og:image:width` 1200, `og:image:height` 630, `og:image:alt`
- `twitter:card` (summary_large_image), `twitter:title`, `twitter:description`, `twitter:image`, `twitter:image:alt`
- `<link rel="icon" href="favicon.png">`, `<link rel="apple-touch-icon" href="apple-touch-icon.png">`

All pages share one picture. The **docs pages are generated**: their tags live in `tools/docs-template.html` (filled per
page by `tools/docs-build.py`) — change the template and rebuild, never the generated `docs/*.html`.

## The picture

- `og-image.png` — 1200×630: the sleeping dozer (black line art) on white, "Dozer Sandbox" and the first line ("Fast,
  resumable, secure Linux sandboxes for AI coding agents on your Mac — your API keys never go inside."), a yellow
  (#ffd60a) bar and a `dozersandbox.com` pill. `og-image.jpg` is a JPEG copy kept for platforms that prefer it.
- Its source is `og/og-image.html`, rendered with headless Chrome at 1200×630 (always a scratch profile:
  `--user-data-dir=<a temp dir> --no-first-run --no-default-browser-check --disable-component-update`). After editing
  the source or the first line, re-render both files and keep them under ~200 KB.
- `apple-touch-icon.png` — 180×180, the dozer on white, made from `dozer-sleeping.jpg`.

## Checking it

1. **Every page has the full set** — parse each page's `<head>` and assert the tags above are present, the image URLs
   are absolute `https://`, and `og:url` equals the canonical. (A script did this for all 28 pages: 0 problems.)
2. **The crawlers can fetch** — the page and the image with each crawler's user agent must return 200:
   ```sh
   for ua in "facebookexternalhit/1.1" "Twitterbot/1.0" "Slackbot-LinkExpanding 1.0" "LinkedInBot/1.0" \
             "Mozilla/5.0 (compatible; Discordbot/2.0)" "WhatsApp/2.23.20.0" "TelegramBot (like TwitterBot)"; do
     echo "$ua: page $(curl -s -o /dev/null -w '%{http_code}' -A "$ua" https://dozersandbox.com/)" \
          "image $(curl -s -o /dev/null -w '%{http_code}' -A "$ua" https://dozersandbox.com/og-image.png)"
   done
   ```
   Cloudflare's bot protection blocks some generic clients (Python's default user agent gets 403) but lets these
   crawlers through. If a platform stops showing cards, run this first.
3. **What a platform will show** — `https://api.microlink.io/?url=https://dozersandbox.com/` returns the title,
   description, image and logo a preview service extracts (no login). opengraph.xyz and metatags.io need a browser.

## When a card is stale or has no picture

Platforms cache a URL's card, often for days — a link pasted before the tags existed keeps its old card.

- **iMessage, Slack, WhatsApp, Discord, Telegram, X** cache per exact URL: paste it with a query string, e.g.
  `https://dozersandbox.com/?v=2`, and they fetch afresh. (X no longer has a card validator.)
- **Facebook:** https://developers.facebook.com/tools/debug/ — paste the URL, "Scrape Again".
- **LinkedIn:** https://www.linkedin.com/post-inspector/ — inspect the URL.

## Related

- `tools/stamp.sh` fingerprints the CSS/JS links and writes generated parts — run it after changes.
- `sitemap.xml` / `robots.txt` (search engines), the JSON-LD on the home page (rich results), `DESIGN.md` (the docs
  design).
