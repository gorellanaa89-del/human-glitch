"""Free stock footage from Pexels (needs a free PEXELS_API_KEY; skipped when absent)."""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.pexels.com/videos/search"


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


def fetch(keywords: str, count: int, out_dir: Path, used: set, orientation: str = "landscape") -> list[Path]:
    """Download up to `count` clips for the keywords, skipping video ids already in `used`."""
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
        if v["id"] in used or v.get("duration", 0) < 4:
            continue
        link = _best_file(v, orientation)
        if not link:
            continue
        dest = out_dir / f"pexels_{v['id']}.mp4"
        try:
            if not dest.exists():
                urllib.request.urlretrieve(link, dest)
            used.add(v["id"])
            clips.append(dest)
        except Exception as e:
            print(f"  pexels download failed: {e}")
    return clips
