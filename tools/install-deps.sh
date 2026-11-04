#!/usr/bin/env bash
# Install ffmpeg and fonts on a GitHub runner. Retries with time limits, because apt sometimes
# hangs (a slow mirror, or the man-db trigger on ubuntu-24.04, which we switch off).
set -u
sudo rm -f /var/lib/man-db/auto-update
for attempt in 1 2 3; do
  if timeout 240 sudo apt-get update -qq -o Acquire::Retries=3 &&
     timeout 480 sudo apt-get install -y -qq --no-install-recommends ffmpeg fonts-dejavu-core; then
    timeout 240 sudo apt-get install -y -qq --no-install-recommends fonts-inter fonts-jetbrains-mono || true
    fc-cache -f
    exit 0
  fi
  echo "apt attempt $attempt failed, retrying..."
  sleep 10
done
exit 1
