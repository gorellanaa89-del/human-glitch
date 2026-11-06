"""Hand-drawn backgrounds (sets) for Human Glitch scenes.

Same pencil style as the cast: flat muted colours, wobbly ink outlines, few details, and an open
area in the middle so the characters stand out. 1920x1080, characters' feet around y=1000.
"""
import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .sketch import HAND_FONT, INK, SS, WHITE, Pencil, bez, ellipse_pts, shade

W, H = 1920, 1080
LINE = 4.0


def _rect(p, x0, y0, x1, y1, fill, width=LINE):
    p.shape([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, width)


def _fill(p, pts, fill):
    p.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill)


def _base(wall, floor, horizon=820, seed=1):
    img = Image.new("RGBA", (W * SS, H * SS), wall + (255,))
    p = Pencil(img, seed)
    _fill(p, [(0, horizon), (W, horizon), (W, H), (0, H)], floor)
    p.line([(-10, horizon), (W + 10, horizon)], LINE)
    return img, p


def _plant(p, x, y, s=1.0, pot=(200, 110, 80), leaf=(90, 160, 100)):
    for k, a in enumerate((-60, -30, 0, 30, 60, -45, 45)):
        r = math.radians(a - 90)
        L = (150 if k < 5 else 110) * s
        tip = (x + math.cos(r) * L * 0.7, y - 60 * s + math.sin(r) * L)
        mid = ((x + tip[0]) / 2, (y - 60 * s + tip[1]) / 2)
        n = (-(tip[1] - (y - 60 * s)), tip[0] - x)
        ln = math.hypot(*n) or 1
        w = 26 * s
        pts = bez((x, y - 60 * s), (mid[0] + n[0] / ln * w, mid[1] + n[1] / ln * w), (mid[0] + n[0] / ln * w * 0.6, mid[1] + n[1] / ln * w * 0.6), tip) \
            + bez(tip, (mid[0] - n[0] / ln * w * 0.6, mid[1] - n[1] / ln * w * 0.6), (mid[0] - n[0] / ln * w, mid[1] - n[1] / ln * w), (x, y - 60 * s))[1:]
        p.shape(pts, shade(leaf, 0.9 + 0.05 * (k % 3)), 3.5)
    p.shape([(x - 55 * s, y - 70 * s), (x + 55 * s, y - 70 * s), (x + 42 * s, y + 40 * s), (x - 42 * s, y + 40 * s)], pot, LINE)


def _window(p, x0, y0, x1, y1, sky, frame=(250, 250, 250), night=False):
    _rect(p, x0 - 14, y0 - 14, x1 + 14, y1 + 14, frame)
    _rect(p, x0, y0, x1, y1, sky)
    p.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], 10, frame, wobble=0.4)
    p.line([(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)], 10, frame, wobble=0.4)
    p.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], LINE)
    p.line([(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)], LINE)
    _rect(p, x0 - 30, y1 + 14, x1 + 30, y1 + 36, frame)


def _skyline(p, x0, x1, base, color, seed=3):
    rnd = random.Random(seed)
    x = x0
    while x < x1:
        w = rnd.randint(40, 90)
        h = rnd.randint(60, 200)
        _fill(p, [(x, base - h), (min(x + w, x1), base - h), (min(x + w, x1), base), (x, base)], color)
        x += w + rnd.randint(2, 12)


def _clock(p, x, y, r=50):
    p.shape(ellipse_pts(x, y, r, r, n=40), WHITE, LINE)
    p.line([(x, y), (x, y - r * 0.65)], 4)
    p.line([(x, y), (x + r * 0.45, y + r * 0.2)], 4)


def _text(img, txt, xy, size, color=INK, anchor="mm"):
    ImageDraw.Draw(img).text((xy[0] * SS, xy[1] * SS), txt, font=ImageFont.truetype(str(HAND_FONT), int(size * SS)), fill=color, anchor=anchor)


# ---------- sets ----------

def office():
    img, p = _base((222, 232, 242), (196, 178, 160))
    _window(p, 110, 150, 560, 560, (190, 225, 245))
    _skyline(p, 124, 546, 546, (160, 196, 222))
    for line in (((335, 150), (335, 560)), ((110, 355), (560, 355))):
        p.line(line, 10, (250, 250, 250), wobble=0.4)
        p.line(line, LINE)
    _clock(p, 960, 190)
    # shelf with binders, right
    _rect(p, 1440, 300, 1800, 316, (190, 150, 110))
    for k, c in enumerate([(240, 120, 100), (90, 150, 210), (250, 200, 90), (120, 180, 140), (170, 140, 220)]):
        _rect(p, 1460 + k * 50, 190, 1500 + k * 50, 300, c, 3.5)
    _plant(p, 1740, 880, 1.1)
    # desk front-left with monitor
    _rect(p, -20, 760, 520, 800, (205, 160, 115))
    _rect(p, 20, 800, 60, 1080, (180, 135, 95))
    _rect(p, 440, 800, 480, 1080, (180, 135, 95))
    _rect(p, 170, 590, 410, 740, (60, 66, 80))
    _rect(p, 182, 602, 398, 728, (150, 200, 230), 3)
    _rect(p, 270, 740, 310, 760, (120, 120, 130), 3)
    p.shape(ellipse_pts(470, 740, 22, 18, n=20), WHITE, 3.5)
    return img


def meeting():
    img, p = _base((238, 228, 214), (170, 150, 135), horizon=800, seed=2)
    _rect(p, 600, 140, 1320, 470, WHITE)
    p.line([(680, 420), (680, 200)], 4)
    p.line([(680, 420), (1240, 420)], 4)
    for k, (h, c) in enumerate(((90, (90, 150, 210)), (150, (90, 150, 210)), (120, (90, 150, 210)), (210, (240, 120, 100)))):
        _rect(p, 740 + k * 120, 420 - h, 820 + k * 120, 420, c, 3.5)
    _text(img, "Q3 results", (960, 175), 38)
    _rect(p, 590, 470, 1330, 486, (200, 200, 205), 3)
    _window(p, 1520, 180, 1800, 560, (190, 225, 245))
    _plant(p, 260, 860, 1.2)
    return img


def meeting_front():
    """Conference table drawn over the characters, so they stand behind it."""
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    p = Pencil(img, 21)
    _fill(p, [(-20, 900), (W + 20, 900), (W + 20, H + 10), (-20, H + 10)], (150, 110, 80))
    p.shape([(-20, 880), (W + 20, 880), (W + 20, 920), (-20, 920)], (185, 140, 100), LINE)
    for x in (380, 1540):
        p.shape(ellipse_pts(x, 872, 40, 12, n=24), WHITE, 3.5)
    _rect(p, 1080, 862, 1260, 878, WHITE, 3)
    return img


def cafe():
    img, p = _base((246, 226, 204), (176, 132, 100), horizon=840, seed=3)
    # menu board
    _rect(p, 700, 120, 1220, 360, (52, 78, 66))
    _text(img, "COFFEE", (960, 180), 64, (240, 240, 230))
    for k, (a, b) in enumerate((("espresso", "2.50"), ("latte", "3.80"), ("tea", "2.20"))):
        _text(img, a, (800, 240 + k * 38), 32, (230, 230, 220), "lm")
        _text(img, b, (1120, 240 + k * 38), 32, (230, 230, 220), "rm")
    # pendant lamps
    for x in (420, 1500):
        p.line([(x, 0), (x, 150)], 3)
        p.shape([(x - 60, 220), (x - 30, 150), (x + 30, 150), (x + 60, 220)], (250, 200, 90), LINE)
    # counter at the back
    _rect(p, 560, 560, 1360, 600, (210, 170, 130))
    _rect(p, 580, 600, 1340, 840, (190, 120, 90))
    for x in range(640, 1340, 120):
        p.line([(x, 620), (x, 820)], 2.5, shade((190, 120, 90), 0.8))
    _rect(p, 640, 440, 780, 560, (120, 120, 130))
    _rect(p, 670, 470, 750, 520, (60, 60, 70), 3)
    for k in range(3):
        p.shape([(1150 + k * 50, 520), (1186 + k * 50, 520), (1180 + k * 50, 560), (1156 + k * 50, 560)], WHITE, 3)
    _plant(p, 160, 900, 1.0, (120, 150, 180))
    # small round table, front right
    p.shape(ellipse_pts(1640, 900, 170, 36, n=40), (230, 220, 210), LINE)
    _rect(p, 1625, 936, 1655, 1080, (110, 100, 100))
    for dx in (-60, 50):
        p.shape([(1640 + dx - 22, 860), (1640 + dx + 22, 860), (1640 + dx + 16, 892), (1640 + dx - 16, 892)], WHITE, 3)
    return img


def home_night():
    img, p = _base((70, 84, 124), (96, 78, 78), horizon=830, seed=4)
    _window(p, 1300, 160, 1720, 540, (30, 40, 80), (200, 196, 210))
    p.shape(ellipse_pts(1610, 250, 40, 40, n=30), (250, 240, 200), 3.5)
    for x, y in ((1380, 220), (1460, 300), (1420, 440), (1660, 440), (1540, 200)):
        p.line([(x - 8, y), (x + 8, y)], 2.5, (250, 240, 200))
        p.line([(x, y - 8), (x, y + 8)], 2.5, (250, 240, 200))
    # lamp with warm glow
    glow = Image.new("L", img.size, 0)
    ImageDraw.Draw(glow).ellipse([(260 - 300) * SS, (420 - 300) * SS, (260 + 300) * SS, (420 + 300) * SS], fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(120 * SS))
    img.paste(Image.new("RGBA", img.size, (255, 210, 140, 255)), (0, 0), glow)
    p = Pencil(img, 44)
    p.line([(260, 470), (260, 830)], 6)
    p.shape([(200, 830), (320, 830), (300, 850), (220, 850)], (60, 60, 70), 3.5)
    p.shape([(190, 470), (330, 470), (295, 370), (225, 370)], (250, 210, 140), LINE)
    # sofa left
    p.shape([(-20, 700), (420, 700), (440, 760), (440, 930), (-20, 930)], (170, 90, 90), LINE)
    p.shape([(-20, 780), (460, 780), (480, 820), (480, 940), (-20, 940)], (190, 105, 100), LINE)
    p.shape(ellipse_pts(330, 760, 60, 40, n=30), (240, 200, 120), 3.5)
    # picture frame
    _rect(p, 760, 220, 1000, 400, (230, 220, 200))
    p.line(bez((790, 370), (840, 290), (900, 330), (970, 260)), 3.5)
    return img


def savanna():
    img = Image.new("RGBA", (W * SS, H * SS), (250, 210, 150, 255))
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        grad.putpixel((0, y), int(255 * max(0, 1 - y / 760)))
    grad = grad.resize(img.size)
    img.paste(Image.new("RGBA", img.size, (245, 160, 110, 255)), (0, 0), grad)
    p = Pencil(img, 5)
    p.shape(ellipse_pts(1300, 470, 120, 120, n=50), (255, 225, 140), LINE)
    hills = [(-20, 760)] + bez((-20, 760), (300, 640), (700, 700), (1000, 720))[1:] + bez((1000, 720), (1300, 740), (1600, 650), (1940, 720))[1:] + [(1940, 1100), (-20, 1100)]
    p.shape(hills, (200, 160, 110), LINE)
    ground = [(-20, 840)] + bez((-20, 840), (600, 800), (1200, 860), (1940, 820))[1:] + [(1940, 1100), (-20, 1100)]
    p.shape(ground, (226, 186, 110), LINE)
    # acacia tree
    p.shape([(1580, 840), (1610, 840), (1614, 560), (1590, 560)], (110, 80, 60), LINE)
    p.line(bez((1600, 640), (1560, 600), (1520, 560), (1470, 540)), 10)
    p.line(bez((1604, 620), (1650, 580), (1700, 560), (1760, 545)), 10)
    canopy = ellipse_pts(1610, 510, 260, 60, n=60)
    p.shape(canopy, (110, 140, 70), LINE)
    rnd = random.Random(9)
    for _ in range(26):
        x, y = rnd.randint(0, W), rnd.randint(880, 1060)
        for dx in (-10, 0, 10):
            p.line([(x, y), (x + dx * 1.6, y - 26)], 3, shade((150, 130, 60), 1.0))
    return img


SETS = {"office": office, "meeting": meeting, "cafe": cafe, "home_night": home_night, "savanna": savanna,
        # sets that only exist as photos fall back to the closest drawing
        "desk": office, "home_day": home_night, "bedroom": home_night}


FRONT = {"meeting": meeting_front}


# Photo backgrounds (Pixabay, free licence): used when an episode sets `backgrounds: photo` in meta.yaml.
PHOTOS = Path(__file__).resolve().parent.parent / "assets" / "backgrounds"
MODE = os.environ.get("HG_BACKGROUNDS", "drawn")


def photo(name: str) -> Image.Image | None:
    """A real photo, softened so the drawn characters stay in front: cover-fit, light blur (depth of field),
    a little less colour and contrast, and a soft vignette."""
    path = PHOTOS / f"{name}.jpg"
    if not path.exists():
        return None
    im = Image.open(path).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x0, y0 = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x0, y0, x0 + W, y0 + H)).filter(ImageFilter.GaussianBlur(3.2))
    im = ImageEnhance.Color(im).enhance(0.85)
    im = ImageEnhance.Contrast(im).enhance(0.9)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.15, -H * 0.25, W * 1.15, H * 1.25), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(W // 10))
    im = Image.composite(im, ImageEnhance.Brightness(im).enhance(0.72), vig)
    return im.convert("RGBA")


def draw(name: str) -> Image.Image:
    """Return a set as a 1920x1080 RGBA image."""
    if MODE == "photo":
        img = photo(name)
        if img is not None:
            return img
    return SETS[name]().resize((W, H), Image.LANCZOS)


def front(name: str) -> Image.Image | None:
    """Foreground layer to composite over the characters, if the set has one."""
    if MODE == "photo" and (PHOTOS / f"{name}.jpg").exists():
        return None
    return FRONT[name]().resize((W, H), Image.LANCZOS) if name in FRONT else None
