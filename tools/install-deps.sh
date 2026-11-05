#!/usr/bin/env bash
# Install ffmpeg and fonts on a GitHub runner. apt sometimes hangs there: needrestart waits after an
# install, and the man-db trigger is slow on ubuntu-24.04. Both are switched off, every call has a hard
# time limit, and the whole thing is retried.
set -u
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l
sudo rm -f /var/lib/man-db/auto-update
sudo mkdir -p /etc/needrestart/conf.d && echo '$nrconf{restart} = "l"; $nrconf{kernelhints} = 0;' | sudo tee /etc/needrestart/conf.d/99-ci.conf >/dev/null
APT="sudo -E timeout -k 20"
OPTS="-y -qq --no-install-recommends -o DPkg::Lock::Timeout=120 -o Acquire::Retries=3"
for attempt in 1 2 3; do
  if $APT 240 apt-get update -qq -o Acquire::Retries=3 &&
     $APT 480 apt-get install $OPTS ffmpeg fonts-dejavu-core fonts-inter fonts-jetbrains-mono; then
    timeout -k 10 120 fc-cache -f || true
    exit 0
  fi
  echo "apt attempt $attempt failed, retrying..."
  sleep 10
done
exit 1
