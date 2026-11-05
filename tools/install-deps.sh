#!/usr/bin/env bash
# Install ffmpeg on a GitHub runner. apt sometimes hangs there on a slow mirror, so every call has a
# hard time limit, needrestart and the man-db trigger are switched off, and after a failed attempt
# the next one switches from the Azure mirror to archive.ubuntu.com.
# Brand fonts ship in assets/fonts and are registered for the user, so libass finds "Inter" by name.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HOME/.local/share/fonts" && cp "$ROOT"/assets/fonts/*.otf "$ROOT"/assets/fonts/*.ttf "$HOME/.local/share/fonts/"
timeout -k 10 120 fc-cache -f "$HOME/.local/share/fonts" || true

export DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l
sudo rm -f /var/lib/man-db/auto-update
OPTS="-y --no-install-recommends -o DPkg::Lock::Timeout=60 -o Acquire::Retries=2 -o Acquire::http::Timeout=30"
for attempt in 1 2 3 4; do
  if [ "$attempt" -ge 2 ]; then
    echo "Switching apt to archive.ubuntu.com"
    sudo sed -i 's|http://azure.archive.ubuntu.com|http://archive.ubuntu.com|g' /etc/apt/sources.list.d/*.sources /etc/apt/sources.list 2>/dev/null || true
  fi
  if sudo -E timeout -k 15 150 apt-get update -o Acquire::http::Timeout=30 < /dev/null &&
     sudo -E timeout -k 15 300 apt-get install $OPTS ffmpeg fonts-dejavu-core < /dev/null; then
    ffmpeg -hide_banner -version | head -1
    exit 0
  fi
  echo "apt attempt $attempt failed, retrying..."
  sleep 5
done
exit 1
