"""Download candidate photo backgrounds from Pixabay (free licence, no attribution needed).

Usage: python tools/fetch_backgrounds.py OUT_DIR
Saves OUT_DIR/<set>/<n>-<pixabay id>.jpg for each query below, plus OUT_DIR/<set>.jpg,
a numbered contact sheet to pick from. Needs PIXABAY_API_KEY.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

QUERIES = {
    "office": "empty modern office interior",
    "desk": "office desk laptop window",
    "meeting": "empty meeting room conference table",
    "cafe": "coffee shop interior empty",
    "home_day": "living room sofa interior",
    "home_night": "living room night lamp",
    "bedroom": "bedroom interior night",
    "kitchen": "home kitchen interior",
    "street": "city street sidewalk day",
    "savanna": "african savanna landscape",
}
# Second round (2026-11-08): more places, so episodes don't repeat the same rooms. `python ... OUT more`
MORE = {
    "hallway": "empty office corridor hallway",
    "elevator": "elevator interior empty",
    "breakroom": "office kitchen break room",
    "lobby": "modern office lobby empty",
    "office_night": "empty office at night city lights",
    "glass_meeting": "glass meeting room modern office",
    "open_office": "open plan office empty desks",
    "window_city": "office window city skyline view",
    "rooftop": "rooftop terrace city empty",
    "park": "city park bench path empty",
    "train": "empty train interior seats",
    "car": "car interior dashboard steering wheel",
    "stairs": "modern staircase interior empty",
    "restaurant": "empty restaurant interior tables",
    "bathroom_mirror": "bathroom mirror sink interior",
    "home_office": "home office desk room",
}
PER = 12


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "inside-voice/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main(out: Path, group: str = "first"):
    key = os.environ["PIXABAY_API_KEY"].strip()
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except OSError:
        font = ImageFont.load_default(40)
    queries = MORE if group == "more" else QUERIES
    for name, q in queries.items():
        params = urllib.parse.urlencode({"key": key, "q": q, "image_type": "photo", "orientation": "horizontal",
                                         "min_width": 1920, "safesearch": "true", "per_page": PER})
        hits = json.loads(get(f"https://pixabay.com/api/?{params}"))["hits"]
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        thumbs = []
        for n, h in enumerate(hits, 1):
            path = d / f"{n:02d}-{h['id']}.jpg"
            path.write_bytes(get(h["largeImageURL"]))
            im = Image.open(path).convert("RGB")
            im.thumbnail((480, 270))
            tile = Image.new("RGB", (480, 270), (20, 20, 20))
            tile.paste(im, ((480 - im.width) // 2, (270 - im.height) // 2))
            ImageDraw.Draw(tile).text((12, 8), str(n), font=font, fill=(255, 230, 0), stroke_width=3, stroke_fill=(0, 0, 0))
            thumbs.append(tile)
            print(name, n, h["id"], h["pageURL"])
        sheet = Image.new("RGB", (480 * 4, 270 * ((len(thumbs) + 3) // 4)), (0, 0, 0))
        for i, t in enumerate(thumbs):
            sheet.paste(t, ((i % 4) * 480, (i // 4) * 270))
        sheet.save(out / f"{name}.jpg", quality=80)


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "first")
