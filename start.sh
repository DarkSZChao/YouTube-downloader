#!/bin/sh
set -eu

node --version
test -f /opt/bgutil/server/build/main.js
echo "BgUtils script provider is available at /opt/bgutil/server"
(
    python -m yt_dlp --verbose --js-runtimes node --simulate \
        "https://www.youtube.com/watch?v=jNQXAC9IVRw" 2>&1 \
        | grep -E "JS runtimes|JS Challenge Providers|PO Token Providers|bgutil" \
        || echo "WARNING: yt-dlp did not report Node/EJS or a BgUtils PO Token provider"
) &

exec python main.py
