#!/bin/sh
set -eu

node /opt/bgutil/server/build/main.js &
provider_pid=$!

attempt=0
until curl --silent --fail http://127.0.0.1:4416/ping >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 20 ]; then
        echo "BgUtils provider failed to become ready on http://127.0.0.1:4416/ping"
        kill "$provider_pid" 2>/dev/null || true
        exit 1
    fi
    sleep 0.5
done

echo "BgUtils provider is ready on http://127.0.0.1:4416/ping"
(
    python -m yt_dlp --verbose --simulate "https://www.youtube.com/watch?v=jNQXAC9IVRw" 2>&1 \
        | grep -E "PO Token Providers|bgutil" \
        || echo "WARNING: yt-dlp did not report a BgUtils PO Token provider"
) &

exec python main.py
