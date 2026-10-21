#!/usr/bin/env bash
# Copyright (c) 2026 Srimukessh Subramanian. All rights reserved.
# Reference/portfolio viewing only — NOT open source. No permission to copy, use,
# run, modify, or redistribute. See LICENSE. Contact: srimukessh1994@gmail.com
#
# Per-show speed folders. Each show has a 1x/ folder of full-speed masters;
# this derives a <speed>x/ folder beside it for every speed listed below.
# Only re-times (preserves pitch) — no ElevenLabs credits are spent here.
#
#   episodes/<show>/1x/     <- masters (rendered by generate_podcast.py)
#   episodes/<show>/1.4x/   <- derived here
set -euo pipefail
cd "$(dirname "$0")"

SPEEDS=(1.25 1.5)   # add/remove speeds here

shopt -s nullglob
for show in episodes/*/; do
  src="${show}1x"
  [ -d "$src" ] || continue          # skip folders without a 1x master set (e.g. quiz/)
  for speed in "${SPEEDS[@]}"; do
    dst="${show}${speed}x"
    mkdir -p "$dst"
    for base in "$src"/*.mp3; do
      name="$(basename "$base" .mp3)"
      ffmpeg -y -i "$base" -filter:a "atempo=${speed}" -q:a 4 "$dst/$name (${speed}x).mp3" 2>/dev/null
    done
  done
  echo "built speeds for: $show"
done

echo; echo "=== episodes tree ==="
for d in episodes/*/; do
  echo "$d"
  for s in "$d"*/; do echo "  $(basename "$s")/ ($(ls -1 "$s" 2>/dev/null | wc -l | tr -d ' ') files)"; done
done
