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



# ---------- second round of drawn sets (2026-11-08) ----------

def _door(p, x0, y0, x1, y1, color, knob=True):
    _rect(p, x0 - 12, y0 - 12, x1 + 12, y1, (240, 236, 228))
    _rect(p, x0, y0, x1, y1, color)
    if knob:
        p.shape(ellipse_pts(x1 - 30, (y0 + y1) / 2 + 20, 11, 11, n=16), (230, 190, 90), 3)


def _frame(p, x0, y0, x1, y1, art=(150, 200, 230), seed=0):
    _rect(p, x0, y0, x1, y1, (230, 220, 200))
    _rect(p, x0 + 16, y0 + 16, x1 - 16, y1 - 16, art, 3)
    rnd = random.Random(seed)
    p.line(bez((x0 + 30, y1 - 30), (x0 + (x1 - x0) * 0.35, y0 + 40 + rnd.randint(0, 30)),
               (x0 + (x1 - x0) * 0.6, y1 - 60), (x1 - 30, y0 + 50)), 3.5)


def _monitor(p, x, y, w=200, h=130):
    _rect(p, x - w / 2, y - h, x + w / 2, y, (60, 66, 80))
    _rect(p, x - w / 2 + 10, y - h + 10, x + w / 2 - 10, y - 10, (150, 200, 230), 3)
    _rect(p, x - 14, y, x + 14, y + 22, (120, 120, 130), 3)


def _chair(p, x, y, color=(70, 80, 100)):
    p.shape([(x - 60, y - 150), (x + 60, y - 150), (x + 50, y - 40), (x - 50, y - 40)], color, LINE)
    _rect(p, x - 70, y - 40, x + 70, y - 14, shade(color, 1.15))
    p.line([(x, y - 14), (x, y + 40)], 6)
    p.line([(x - 50, y + 50), (x + 50, y + 50)], 6)


def _tree(p, x, y, s=1.0, leaf=(110, 160, 90), seed=1):
    p.shape([(x - 18 * s, y), (x + 18 * s, y), (x + 12 * s, y - 260 * s), (x - 12 * s, y - 260 * s)], (130, 95, 70), LINE)
    rnd = random.Random(seed)
    for k in range(5):
        cx = x + rnd.randint(-110, 110) * s
        cy = y - (300 + rnd.randint(-40, 80)) * s
        p.shape(ellipse_pts(cx, cy, 120 * s, 100 * s, n=40), shade(leaf, 0.9 + 0.05 * k), LINE)


def hallway():
    img, p = _base((226, 222, 236), (182, 176, 190), horizon=800, seed=31)
    # long corridor in perspective: back wall, side walls, ceiling lights
    _fill(p, [(760, 220), (1160, 220), (1160, 700), (760, 700)], (205, 200, 222))
    p.shape([(760, 220), (1160, 220), (1160, 700), (760, 700)], (205, 200, 222), LINE)
    for a, b in (((0, 0), (760, 220)), ((W, 0), (1160, 220)), ((0, 800), (760, 700)), ((W, 800), (1160, 700))):
        p.line([a, b], LINE)
    _door(p, 900, 430, 1020, 700, (120, 150, 200))
    _text(img, "EXIT", (960, 380), 34, (60, 150, 90))
    for k, (x0, x1, y0, y1) in enumerate(((250, 420, 330, 780), (520, 620, 290, 735))):
        p.shape([(x0, y0), (x1, y0 + 40), (x1, y1 - 30), (x0, y1)], (150, 120, 100), LINE)
    for k, (x0, x1, y0, y1) in enumerate(((1500, 1670, 370, 780), (1300, 1400, 330, 735))):
        p.shape([(x0, y0 + 40), (x1, y0), (x1, y1), (x0, y1 - 30)], (150, 120, 100), LINE)
    for x0, x1, y in ((800, 1120, 90), (860, 1060, 170)):
        _rect(p, x0, y, x1, y + 22, (250, 248, 220), 3)
    _frame(p, 120, 300, 200, 420, (240, 180, 150), 2)
    _plant(p, 1800, 900, 1.0)
    return img


def elevator():
    img, p = _base((210, 214, 222), (160, 160, 170), horizon=820, seed=32)
    for x0 in (330, 1290):  # two elevator doors with panels
        _rect(p, x0, 260, x0 + 300, 820, (190, 196, 206))
        p.line([(x0 + 150, 260), (x0 + 150, 820)], LINE)
        _rect(p, x0 + 90, 200, x0 + 210, 240, (40, 44, 56), 3)
        _text(img, "3", (x0 + 150, 220), 34, (250, 120, 90))
    _rect(p, 900, 480, 1020, 620, (200, 200, 210))
    for k in range(2):
        p.shape(ellipse_pts(960, 520 + k * 60, 20, 20, n=20), WHITE, 3)
    p.line([(950, 528), (960, 512), (970, 528)], 3)
    p.line([(950, 572), (960, 588), (970, 572)], 3)
    _plant(p, 120, 900, 1.1)
    _rect(p, 0, 0, W, 40, (240, 240, 245), 3)
    return img


def breakroom():
    img, p = _base((236, 236, 220), (190, 170, 150), horizon=820, seed=33)
    # upper cabinets and counter with coffee machine and microwave
    for k in range(5):
        _rect(p, 220 + k * 160, 160, 370 + k * 160, 360, (170, 200, 190))
        p.shape(ellipse_pts(355 + k * 160 - 20, 330, 8, 8, n=12), INK, 2)
    _rect(p, 200, 560, 1040, 600, (220, 210, 200))
    _rect(p, 220, 600, 1020, 820, (150, 180, 170))
    _rect(p, 300, 430, 440, 560, (60, 60, 70))
    _rect(p, 330, 470, 410, 520, (200, 90, 70), 3)
    _rect(p, 560, 470, 760, 560, (220, 220, 225))
    _rect(p, 580, 485, 700, 545, (60, 60, 70), 3)
    for k in range(3):
        p.shape([(860 + k * 45, 520), (892 + k * 45, 520), (887 + k * 45, 560), (865 + k * 45, 560)], (240, 120, 100) if k == 1 else WHITE, 3)
    # fridge and notice board
    _rect(p, 1560, 280, 1800, 820, (235, 238, 242))
    p.line([(1560, 480), (1800, 480)], LINE)
    _rect(p, 1580, 380, 1594, 450, (150, 150, 160), 2)
    _rect(p, 1210, 230, 1450, 420, (200, 160, 110))
    for k, c in enumerate([(250, 230, 120), (160, 210, 240), (250, 180, 190)]):
        _rect(p, 1235 + k * 70, 255 + (k % 2) * 40, 1295 + k * 70, 330 + (k % 2) * 40, c, 2.5)
    _clock(p, 1330, 120, 42)
    return img


def boss_office():
    img, p = _base((214, 206, 196), (120, 100, 90), horizon=830, seed=34)
    # big window with skyline, framed diploma, bookshelf, large desk at the back
    _window(p, 540, 130, 1380, 560, (175, 210, 236))
    _skyline(p, 554, 1366, 546, (140, 176, 206), seed=8)
    for x in (820, 1100):
        p.line([(x, 130), (x, 560)], 10, (250, 250, 250), wobble=0.4)
        p.line([(x, 130), (x, 560)], LINE)
    _rect(p, 1520, 180, 1820, 830, (150, 110, 80))
    for r in range(4):
        _rect(p, 1520, 330 + r * 150, 1820, 342 + r * 150, (120, 85, 60), 3)
        for k in range(6):
            _rect(p, 1540 + k * 44, 230 + r * 150, 1572 + k * 44, 330 + r * 150, shade((200, 120, 90), 0.8 + 0.08 * k), 2.5)
    _rect(p, 120, 260, 360, 420, (240, 235, 220))
    _text(img, "MBA", (240, 330), 44)
    _rect(p, 620, 640, 1300, 690, (110, 75, 55))
    _rect(p, 650, 690, 1270, 830, (130, 90, 65))
    _monitor(p, 1120, 640, 180, 110)
    _plant(p, 300, 900, 1.2)
    return img


def open_office():
    img, p = _base((226, 236, 236), (180, 186, 190), horizon=760, seed=35)
    # rows of desks with monitors fading to the back, pillars and big windows
    for k in range(4):
        _window(p, 120 + k * 450, 120, 440 + k * 450, 420, (200, 230, 245))
    for row, (y, s) in enumerate(((700, 0.7), (760, 1.0))):
        for k in range(6 if row == 0 else 4):
            x = (230 + k * 300) if row == 0 else (180 + k * 520)
            if 700 < x < 1220 and row == 1:
                continue
            _rect(p, x - 120 * s, y - 20 * s, x + 120 * s, y, (230, 230, 228), 3)
            _monitor(p, x, y - 20 * s, 120 * s, 80 * s)
    _rect(p, 920, 100, 1000, 760, (240, 240, 240))
    _plant(p, 1820, 920, 1.0)
    return img


def lobby():
    img, p = _base((236, 228, 216), (210, 200, 190), horizon=800, seed=36)
    _rect(p, 560, 160, 1360, 300, (58, 99, 216))
    _text(img, "WELCOME", (960, 230), 80, (250, 250, 250))
    _rect(p, 620, 560, 1300, 600, (230, 220, 205))
    _rect(p, 640, 600, 1280, 800, (190, 150, 110))
    _monitor(p, 760, 560, 140, 90)
    p.shape(ellipse_pts(1180, 548, 34, 12, n=20), (250, 210, 90), 3)
    for x in (140, 1560):  # glass doors / windows
        _rect(p, x, 200, x + 220, 800, (205, 228, 238))
        p.line([(x + 110, 200), (x + 110, 800)], LINE)
    _plant(p, 470, 900, 1.2)
    _plant(p, 1460, 900, 1.2)
    return img


def park():
    img = Image.new("RGBA", (W * SS, H * SS), (176, 214, 236, 255))
    p = Pencil(img, 37)
    for x, y in ((300, 160), (1500, 120)):
        p.shape(ellipse_pts(x, y, 110, 40, n=30), WHITE, 3)
        p.shape(ellipse_pts(x + 80, y - 20, 80, 36, n=30), WHITE, 3)
    hills = [(-20, 700)] + bez((-20, 700), (500, 620), (1200, 680), (1940, 640))[1:] + [(1940, 1100), (-20, 1100)]
    p.shape(hills, (150, 196, 120), LINE)
    path = [(860, 690), (1060, 690), (1500, 1100), (420, 1100)]
    p.shape(path, (226, 210, 180), LINE)
    _tree(p, 240, 760, 1.2, seed=3)
    _tree(p, 1700, 740, 1.1, (130, 170, 90), seed=4)
    _tree(p, 1260, 640, 0.6, seed=5)
    # bench and lamp post
    _rect(p, 1450, 800, 1800, 830, (170, 110, 80))
    _rect(p, 1450, 740, 1800, 770, (170, 110, 80))
    for x in (1480, 1770):
        p.line([(x, 830), (x, 900)], 8)
    p.line([(560, 900), (560, 520)], 8)
    p.shape(ellipse_pts(560, 500, 34, 34, n=24), (250, 230, 160), LINE)
    return img


def street():
    img = Image.new("RGBA", (W * SS, H * SS), (186, 220, 240, 255))
    p = Pencil(img, 38)
    cols = [(230, 170, 140), (210, 200, 180), (170, 190, 210), (230, 210, 150), (200, 160, 170)]
    x = -40
    for k in range(7):
        w = 300 + (k * 37) % 80
        top = 120 + (k * 53) % 140
        _rect(p, x, top, x + w, 800, cols[k % 5])
        for r in range(int((760 - top) / 110)):
            for c in range(2):
                _rect(p, x + 50 + c * (w / 2 - 20), top + 40 + r * 110, x + 50 + c * (w / 2 - 20) + 70, top + 110 + r * 110, (200, 225, 240), 3)
        x += w
    _fill(p, [(0, 800), (W, 800), (W, H), (0, H)], (150, 150, 158))
    p.line([(-10, 800), (W + 10, 800)], LINE)
    for k in range(7):
        _rect(p, 400 + k * 170, 900, 480 + k * 170, 1080, (240, 240, 240), 2.5)
    p.line([(1700, 820), (1700, 420)], 8)
    p.shape(ellipse_pts(1700, 400, 30, 30, n=24), (250, 230, 160), LINE)
    return img


def train():
    img, p = _base((226, 230, 220), (150, 156, 160), horizon=840, seed=39)
    # windows with a blurred city passing, grab rails and seats
    for k in range(4):
        x0 = 120 + k * 450
        _rect(p, x0, 260, x0 + 340, 520, (150, 190, 220))
        _skyline(p, x0 + 10, x0 + 330, 515, (120, 160, 196), seed=k + 11)
    p.line([(0, 150), (W, 150)], 8)
    for k in range(9):
        x = 100 + k * 220
        p.line([(x, 150), (x, 210)], 3)
        p.shape(ellipse_pts(x, 228, 18, 22, n=20), (250, 210, 90), 3)
    _rect(p, 0, 640, W, 700, (70, 110, 170))
    _rect(p, 0, 700, W, 760, (60, 95, 150))
    for x in (520, 1400):
        p.line([(x, 150), (x, 840)], 9, (200, 200, 205), wobble=0.3)
        p.line([(x, 150), (x, 840)], LINE)
    return img


def bedroom():
    img, p = _base((96, 104, 150), (110, 90, 96), horizon=830, seed=40)
    _window(p, 760, 170, 1160, 520, (40, 50, 90), (200, 196, 210))
    p.shape(ellipse_pts(1080, 250, 34, 34, n=24), (250, 240, 200), 3.5)
    p.shape([(1260, 640), (1900, 640), (1900, 900), (1260, 900)], (230, 230, 240), LINE)
    p.shape([(1240, 520), (1300, 520), (1300, 900), (1240, 900)], (150, 110, 90), LINE)
    p.shape(ellipse_pts(1400, 620, 90, 40, n=30), WHITE, 3.5)
    _rect(p, 1260, 700, 1900, 900, (120, 140, 200))
    _rect(p, 80, 720, 260, 860, (150, 110, 90))
    p.shape([(120, 720), (220, 720), (200, 640), (140, 640)], (250, 210, 140), LINE)
    p.line([(170, 640), (170, 600)], 4)
    _rect(p, 140, 690, 200, 714, (60, 60, 70), 2.5)  # phone on the night table
    return img


def home_day():
    img, p = _base((246, 236, 214), (190, 160, 130), horizon=830, seed=41)
    _window(p, 1240, 160, 1720, 560, (190, 225, 245), (250, 250, 250))
    _tree(p, 1480, 560, 0.5, seed=8)
    p.shape([(-20, 700), (440, 700), (460, 760), (460, 930), (-20, 930)], (110, 150, 190), LINE)
    p.shape([(-20, 780), (500, 780), (520, 820), (520, 940), (-20, 940)], (130, 170, 205), LINE)
    p.shape(ellipse_pts(360, 760, 60, 40, n=30), (250, 200, 120), 3.5)
    _frame(p, 640, 220, 900, 420, (240, 190, 140), 4)
    _rect(p, 1500, 780, 1820, 820, (200, 160, 120))
    _plant(p, 1660, 780, 0.7)
    return img


def kitchen():
    img, p = _base((240, 236, 226), (200, 180, 160), horizon=830, seed=42)
    for k in range(6):
        _rect(p, 120 + k * 180, 150, 290 + k * 180, 360, (230, 200, 160))
    _rect(p, 100, 570, 1220, 610, (240, 240, 236))
    _rect(p, 120, 610, 1200, 830, (220, 190, 150))
    _rect(p, 460, 520, 640, 570, (180, 180, 190))  # sink
    p.line(bez((550, 520), (550, 470), (590, 460), (600, 490)), 5)
    p.shape([(820, 520), (900, 520), (890, 570), (830, 570)], (240, 120, 100), 3)  # pot
    _window(p, 1380, 200, 1760, 520, (190, 225, 245))
    p.shape(ellipse_pts(1580, 900, 220, 40, n=40), (210, 170, 130), LINE)
    p.shape(ellipse_pts(1560, 868, 40, 14, n=20), WHITE, 3)
    return img


def restaurant():
    img, p = _base((150, 70, 60), (110, 80, 70), horizon=820, seed=43)
    _fill(p, [(0, 0), (W, 0), (W, 520), (0, 520)], (170, 90, 76))
    p.line([(-10, 520), (W + 10, 520)], LINE)
    for x in (360, 960, 1560):
        p.line([(x, 0), (x, 140)], 3)
        p.shape([(x - 70, 210), (x - 36, 140), (x + 36, 140), (x + 70, 210)], (250, 210, 120), LINE)
    for x in (220, 1700):  # tables with candles and wine glasses
        p.shape(ellipse_pts(x, 820, 200, 40, n=40), (245, 240, 230), LINE)
        _rect(p, x - 14, 860, x + 14, 1080, (80, 60, 50))
        p.line([(x, 800), (x, 770)], 6, (250, 240, 220))
        p.shape(ellipse_pts(x, 760, 6, 12, n=12), (250, 200, 80), 2)
    _frame(p, 760, 260, 1160, 460, (230, 180, 120), 6)
    return img


def rooftop():
    img = Image.new("RGBA", (W * SS, H * SS), (250, 196, 150, 255))
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        grad.putpixel((0, y), int(255 * max(0, 1 - y / 700)))
    img.paste(Image.new("RGBA", img.size, (150, 140, 200, 255)), (0, 0), grad.resize(img.size))
    p = Pencil(img, 44)
    p.shape(ellipse_pts(1400, 620, 90, 90, n=40), (255, 220, 150), LINE)
    _skyline(p, -20, W + 20, 700, (110, 100, 150), seed=13)
    _fill(p, [(0, 700), (W, 700), (W, H), (0, H)], (170, 150, 140))
    p.line([(-10, 700), (W + 10, 700)], LINE)
    p.line([(-10, 640), (W + 10, 640)], 6)
    for x in range(40, W, 120):
        p.line([(x, 640), (x, 700)], 4)
    for x in (260, 1660):
        p.line([(x, 400), (x, 700)], 3)
    p.line(bez((260, 410), (700, 470), (1200, 470), (1660, 410)), 3)
    for k in range(9):
        x = 360 + k * 140
        p.shape(ellipse_pts(x, 448 + 10 * math.sin(k), 14, 18, n=16), (255, 230, 150), 2.5)
    _plant(p, 140, 920, 1.1)
    return img


def home_office():
    img, p = _base((232, 226, 240), (180, 160, 140), horizon=830, seed=45)
    _window(p, 1360, 180, 1760, 520, (190, 225, 245))
    _rect(p, 1180, 600, 1820, 640, (210, 170, 125))
    _rect(p, 1200, 640, 1240, 830, (180, 140, 100))
    _rect(p, 1760, 640, 1800, 830, (180, 140, 100))
    p.shape([(1380, 520), (1620, 520), (1600, 600), (1400, 600)], (80, 86, 100), LINE)  # open laptop
    p.shape(ellipse_pts(1700, 590, 20, 14, n=16), WHITE, 3)
    _rect(p, 120, 200, 440, 216, (190, 150, 110))
    _rect(p, 120, 400, 440, 416, (190, 150, 110))
    for r in range(2):
        for k in range(5):
            _rect(p, 140 + k * 56, 120 + r * 200, 180 + k * 56, 200 + r * 200, shade((120, 170, 200), 0.8 + 0.08 * k), 2.5)
    _frame(p, 640, 220, 880, 400, (200, 220, 180), 7)
    _plant(p, 260, 900, 1.0)
    return img


SETS = {"office": office, "meeting": meeting, "cafe": cafe, "home_night": home_night, "savanna": savanna,
        "desk": office, "hallway": hallway, "elevator": elevator, "breakroom": breakroom,
        "boss_office": boss_office, "open_office": open_office, "lobby": lobby, "park": park, "street": street,
        "train": train, "bedroom": bedroom, "home_day": home_day, "kitchen": kitchen, "restaurant": restaurant,
        "rooftop": rooftop, "home_office": home_office,
        # photo-only names fall back to the closest drawing
        "office_evening": office, "glass_meeting": meeting, "bathroom": home_day}


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
