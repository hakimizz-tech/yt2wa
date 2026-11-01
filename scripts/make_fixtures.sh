#!/usr/bin/env bash
# Generate small test videos in tests/fixtures (needs ffmpeg with libx264).
set -euo pipefail

out="$(dirname "$0")/../tests/fixtures"
mkdir -p "$out"
src="testsrc=duration=3:size=854x480:rate=30"
tone="sine=frequency=440:duration=3"

# A file that already matches the WhatsApp profile.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "$src" -f lavfi -i "$tone" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -ac 2 -ar 48000 \
  -movflags +faststart "$out/h264_aac_compliant.mp4"

# moov atom at the end (no faststart).
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "$src" -f lavfi -i "$tone" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -ac 2 -ar 48000 \
  "$out/moov_at_end.mp4"

# Mono audio at 22.05 kHz.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "$src" -f lavfi -i "$tone" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -ac 1 -ar 22050 \
  -movflags +faststart "$out/mono_22khz.mp4"

# Not H.264 and not AAC.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "$src" -f lavfi -i "$tone" \
  -c:v mpeg4 -c:a libmp3lame "$out/mpeg4_mp3.mkv"

echo "Fixtures written to $out"
