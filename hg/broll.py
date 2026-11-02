"""Free stock footage from Pixabay or Pexels.

Uses PIXABAY_API_KEY and/or PEXELS_API_KEY (both free). With neither, scenes fall back to branded cards.
"""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.pexels.com/videos/search"
PIXABAY_API = "https://pixabay.com/api/videos/"


def _get(url: str, key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "human-glitch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _best_file(video: dict, orientation: str) -> str | None:
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
    if orientation == "portrait":
        files = [f for f in files if f["height"] >= f["width"]]
    else:
        files = [f for f in files if f["width"] >= f["height"]]
    files.sort(key=lambda f: abs(f["height"] - 1080))
    return files[0]["link"] if files else None


def _pixabay(keywords: str, count: int, out_dir: Path, used: set) -> list[Path]:
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key or not keywords or count <= 0:
        return []
    query = urllib.parse.urlencode({"key": key, "q": keywords[:100], "per_page": 50, "safesearch": "true"})
    try:
        req = urllib.request.Request(f"{PIXABAY_API}?{query}", headers={"User-Agent": "human-glitch/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            hits = json.load(r).get("hits", [])
    except Exception as e:
        print(f"  pixabay search failed for '{keywords}': {e}")
        return []
    clips = []
    for h in hits:
        if len(clips) >= count:
            break
        vid = f"pixabay_{h['id']}"
        if vid in used or h.get("duration", 0) < 4:
            continue
        files = [f for f in h.get("videos", {}).values() if f.get("url") and f.get("width", 0) >= f.get("height", 1)]
        if not files:
            continue
        files.sort(key=lambda f: abs(f["height"] - 1080))
        dest = out_dir / f"{vid}.mp4"
        try:
            if not dest.exists():
                req = urllib.request.Request(files[0]["url"], headers={"User-Agent": "human-glitch/1.0"})
                with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                    f.write(r.read())
            used.add(vid)
            clips.append(dest)
        except Exception as e:
            print(f"  pixabay download failed: {e}")
    return clips


def fetch(keywords: str, count: int, out_dir: Path, used: set, orientation: str = "landscape") -> list[Path]:
    """Download up to `count` clips for the keywords, skipping ids already in `used`."""
    clips = _pixabay(keywords, count, out_dir, used)
    return clips + _pexels(keywords, count - len(clips), out_dir, used, orientation)


def _pexels(keywords: str, count: int, out_dir: Path, used: set, orientation: str) -> list[Path]:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key or not keywords or count <= 0:
        return []
    query = urllib.parse.urlencode({"query": keywords, "orientation": orientation, "per_page": 30, "size": "medium"})
    try:
        videos = _get(f"{API}?{query}", key).get("videos", [])
    except Exception as e:  # network or quota problems fall back to branded cards
        print(f"  pexels search failed for '{keywords}': {e}")
        return []
    clips = []
    for v in videos:
        if len(clips) >= count:
            break
        if f"pexels_{v['id']}" in used or v.get("duration", 0) < 4:
            continue
        link = _best_file(v, orientation)
        if not link:
            continue
        dest = out_dir / f"pexels_{v['id']}.mp4"
        try:
            if not dest.exists():
                urllib.request.urlretrieve(link, dest)
            used.add(f"pexels_{v['id']}")
            clips.append(dest)
        except Exception as e:
            print(f"  pexels download failed: {e}")
    return clips
