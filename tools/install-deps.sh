#!/usr/bin/env bash
# Install ffmpeg on a GitHub runner.
# 1. If the workflow restored ~/apt-debs from the GitHub cache, install those packages with dpkg:
#    no mirror needed, which avoids the apt hangs we kept seeing on some runners.
# 2. Otherwise use apt with hard time limits (needrestart and the man-db trigger switched off,
#    and a switch from the Azure mirror to archive.ubuntu.com on retries), and keep the
#    downloaded packages in ~/apt-debs so the workflow can cache them for the next runs.
# Brand fonts ship in assets/fonts and are registered for the user, so libass finds "Inter" by name.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEBS="$HOME/apt-debs"
mkdir -p "$HOME/.local/share/fonts" && cp "$ROOT"/assets/fonts/*.otf "$ROOT"/assets/fonts/*.ttf "$HOME/.local/share/fonts/"
timeout -k 10 120 fc-cache -f "$HOME/.local/share/fonts" || true

export DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l
sudo rm -f /var/lib/man-db/auto-update

if ls "$DEBS"/*.deb >/dev/null 2>&1; then
  echo "Installing $(ls "$DEBS"/*.deb | wc -l) cached packages"
  if sudo -E timeout -k 15 300 dpkg -i "$DEBS"/*.deb > /tmp/dpkg.log 2>&1 && command -v ffmpeg >/dev/null; then
    ffmpeg -hide_banner -version | head -1
    exit 0
  fi
  tail -20 /tmp/dpkg.log
  echo "Cached packages did not install; using apt"
  rm -rf "$DEBS"
fi

OPTS="-y --no-install-recommends -o DPkg::Lock::Timeout=60 -o Acquire::Retries=2 -o Acquire::http::Timeout=30"
for attempt in 1 2 3; do
  if [ "$attempt" -ge 2 ]; then
    echo "Switching apt to archive.ubuntu.com"
    sudo sed -i 's|http://azure.archive.ubuntu.com|http://archive.ubuntu.com|g' /etc/apt/sources.list.d/*.sources /etc/apt/sources.list 2>/dev/null || true
  fi
  sudo rm -f /var/cache/apt/archives/*.deb
  if sudo -E timeout -k 15 150 apt-get update -o Acquire::http::Timeout=30 < /dev/null &&
     sudo -E timeout -k 15 240 apt-get install --download-only $OPTS ffmpeg fonts-dejavu-core < /dev/null &&
     sudo -E timeout -k 15 240 apt-get install $OPTS ffmpeg fonts-dejavu-core < /dev/null; then
    mkdir -p "$DEBS" && cp /var/cache/apt/archives/*.deb "$DEBS/" 2>/dev/null || true
    ffmpeg -hide_banner -version | head -1
    exit 0
  fi
  echo "apt attempt $attempt failed, retrying..."
  sleep 5
done
exit 1
