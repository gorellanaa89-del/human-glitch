"""Check each external connection without producing or uploading anything.

Usage: python tools/check_connections.py voice|stock|youtube
Exits non-zero when the connection does not work, so each shows as its own step result in GitHub Actions.
"""
import asyncio
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path


def voice():
    import edge_tts

    from hg.config import VOICES

    for lang, v in VOICES.items():
        out = Path(tempfile.mkdtemp()) / f"{lang}.mp3"
        asyncio.run(edge_tts.Communicate("Human Glitch voice check.", v).save(str(out)))
        size = out.stat().st_size
        print(f"{lang} voice {v}: {size} bytes")
        if size < 1000:
            raise SystemExit(f"{lang} voice returned no audio")


def stock():
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        raise SystemExit("PIXABAY_API_KEY secret is not set")
    q = urllib.parse.urlencode({"key": key, "q": "office", "per_page": 3})
    req = urllib.request.Request(f"https://pixabay.com/api/videos/?{q}", headers={"User-Agent": "human-glitch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    print(f"Pixabay: {data.get('totalHits', 0)} videos available for 'office'")
    if not data.get("hits"):
        raise SystemExit("Pixabay answered but returned no videos")


def youtube():
    from hg import youtube as yt

    if not yt.configured():
        raise SystemExit("One of YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN is missing")
    resp = yt._service().channels().list(part="snippet,status", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise SystemExit("Login worked but this Google account has no YouTube channel")
    ch = items[0]
    print(f"YouTube channel: {ch['snippet']['title']} ({ch['snippet'].get('customUrl', '')})")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    {"voice": voice, "stock": stock, "youtube": youtube}[sys.argv[1]]()
