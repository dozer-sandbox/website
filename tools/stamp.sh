#!/bin/bash
# tools/stamp.sh — fingerprint site.css and site.js in every page (href="site.css?v=<8 hex of its sha256>").
# Cloudflare tells browsers to keep these files for hours, so a page published with a NEW stylesheet was shown
# with the OLD one from the browser's cache (2026-10-09: the comparison table rendered unstyled). A changed file
# gets a new URL, which a browser must fetch. Run before every commit that changes site.css or site.js.
set -euo pipefail
cd "$(dirname "$0")/.."
for asset in site.css site.js; do
    v="$(shasum -a 256 "$asset" | cut -c1-8)"
    for page in *.html; do
        sed -i '' -E "s#(href|src)=\"$asset(\\?v=[0-9a-f]+)?\"#\\1=\"$asset?v=$v\"#g" "$page"
    done
    echo "$asset → ?v=$v"
done
