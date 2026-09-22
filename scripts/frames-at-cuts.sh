#!/usr/bin/env bash
# Extracts a frame ±0.1 s around each scene cut of the last render → review/
# Usage: npm run frames [renders/reel.mp4]
set -euo pipefail
cd "$(dirname "$0")/.."
VIDEO="${1:-renders/reel.mp4}"
[ -f "$VIDEO" ] || { echo "render not found: $VIDEO (run npm run render first)"; exit 1; }
mkdir -p review
rm -f review/cut-*.jpg
# the cuts = data-start of each scene on track 1 in index.html
CUTS=$(grep -o 'data-track-index="1"[^>]*' index.html | grep -o 'data-start="[0-9.]*"' | grep -o '[0-9.]*' | sort -n | uniq)
# fallback: data-start may come before data-track-index in the tag
[ -n "$CUTS" ] || CUTS=$(grep -o '<[^>]*data-track-index="1"[^>]*>' index.html | grep -o 'data-start="[0-9.]*"' | grep -o '[0-9.]*' | sort -n | uniq)
i=0
for t in $CUTS; do
  for d in -0.1 0.1; do
    at=$(python3 -c "print(max(0, $t + ($d)))")
    ffmpeg -v error -y -ss "$at" -i "$VIDEO" -frames:v 1 -q:v 2 "review/cut-$(printf '%02d' $i)-at-${at}s.jpg"
    i=$((i+1))
  done
done
ffmpeg -v error -y -i "$VIDEO" -vf "fps=1,scale=270:-1,tile=8x4" -frames:v 1 review/contact-sheet.jpg
echo "$i frames in review/ + review/contact-sheet.jpg"
