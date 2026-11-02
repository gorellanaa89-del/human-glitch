"""Cartoon cast: expressive people with big heads and eyes, plus the "bugs", little creatures
that personify each mental glitch (the Impostor, the Overthinker...). Original designs drawn in
code so they stay identical across videos. GLITCH (the host) comes from characters.py.
"""
import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

from .characters import GLITCH_BLUE, _bez, _clip, _finish, _glitch, _mask, _path, _s, _sc, _shade

SS = 3
BASE_W, BASE_H = 600, 900
EXPRESSIONS = ("neutral", "happy", "worried", "surprised", "smug")
WHITE = (255, 255, 255)


def _ol(c):
    """Soft outline colour: a darker shade of the fill instead of black."""
    return _shade(c, 0.55)


@dataclass(frozen=True)
class Toon:
    name: str
    role: str
    skin: tuple
    hair: tuple
    eyes: tuple
    top: tuple
    collar: tuple
    accent: tuple
    hair_style: str  # long | spiky | wavy | short | bun
    glasses: bool = False
    tie: bool = False
    default: str = "neutral"


TOONS = {
    "sarah": Toon("Sarah Collins", "Senior Analyst", (250, 214, 190), (96, 62, 48), (92, 64, 44),
                  (46, 150, 136), (250, 250, 250), (90, 220, 190), "long", glasses=True, default="worried"),
    "richard": Toon("Richard Hale", "Operations Director", (236, 190, 160), (60, 54, 56), (60, 70, 96),
                    (44, 62, 108), (245, 245, 250), (240, 180, 70), "spiky", tie=True, default="smug"),
    "elena": Toon("Elena Ruiz", "Head of People", (212, 158, 124), (40, 30, 30), (70, 44, 30),
                  (170, 60, 90), (40, 40, 48), (240, 120, 150), "wavy", default="happy"),
    "daniel": Toon("Daniel Brooks", "Product Associate", (170, 116, 86), (30, 24, 24), (50, 34, 24),
                   (120, 170, 230), (250, 250, 250), (130, 200, 255), "short", default="surprised"),
    "margaret": Toon("Margaret Lane", "Finance Manager", (250, 220, 200), (214, 214, 222), (90, 110, 130),
                     (130, 100, 170), (250, 244, 236), (200, 160, 250), "bun", glasses=True, default="smug"),
}

HEAD = (300, 300)


def _head_shape():
    cx, cy = HEAD
    pts = []
    for i in range(80):
        t = 2 * math.pi * i / 80
        s = math.sin(t)
        rx, ry = 150, (150 if s > 0 else 140)
        squeeze = 1 - 0.18 * max(0.0, s) ** 4
        pts.append((cx + rx * math.cos(t) * squeeze, cy + ry * s))
    return pts


HEAD_PTS = _head_shape()
BODY = _path((236, 452), ((210, 470), (150, 486), (130, 540)), ((112, 600), (104, 760), (100, 960)), (500, 960),
             ((496, 760), (488, 600), (470, 540)), ((450, 486), (390, 470), (364, 452)))


def _eye(d, cx, cy, t: Toon, expression, side):
    ink = (40, 30, 34)
    if expression == "happy":
        d.arc(_s(cx - 30, cy - 18, cx + 30, cy + 30), 200, 340, fill=ink, width=8 * SS)
        return
    w, h = (30, 40) if expression != "surprised" else (34, 46)
    d.ellipse(_s(cx - w, cy - h, cx + w, cy + h), fill=WHITE, outline=ink, width=4 * SS)
    ir = 18 if expression != "surprised" else 13
    d.ellipse(_s(cx - ir, cy - ir - 4, cx + ir, cy + ir + 8), fill=t.eyes)
    d.ellipse(_s(cx - ir + 6, cy - ir + 2, cx + ir - 6, cy + ir + 2), fill=_shade(t.eyes, 0.45))
    d.ellipse(_s(cx - 12, cy - 22, cx - 1, cy - 11), fill=WHITE)  # highlights
    d.ellipse(_s(cx + 6, cy + 6, cx + 12, cy + 12), fill=WHITE)
    # upper lash line
    d.arc(_s(cx - w - 2, cy - h - 2, cx + w + 2, cy + h + 2), 200, 340, fill=ink, width=8 * SS)
    if expression == "smug":  # heavy lid
        d.chord(_s(cx - w - 4, cy - h - 6, cx + w + 4, cy + h - 10), 180, 360, fill=t.skin)
        d.line(_s(cx - w, cy - 6, cx + w, cy - 6), fill=ink, width=7 * SS)


def _brows(d, t, expression):
    col = _shade(t.hair, 0.8) if sum(t.hair) < 450 else (150, 146, 150)
    for side in (-1, 1):
        ex = 300 + side * 62
        y = 248
        if expression == "worried":
            d.line(_s(ex - side * 24, y - 14, ex + side * 22, y + 2), fill=col, width=7 * SS)
        elif expression == "surprised":
            d.arc(_s(ex - 26, y - 26, ex + 26, y + 4), 200, 340, fill=col, width=7 * SS)
        elif expression == "smug" and side == 1:
            d.arc(_s(ex - 26, y - 22, ex + 26, y + 6), 200, 340, fill=col, width=7 * SS)
        else:
            d.line(_s(ex - 22, y - 2, ex + 22, y - 4), fill=col, width=7 * SS)


def _mouth(d, t, expression):
    ink, inside = (60, 34, 40), (150, 60, 70)
    y = 392
    if expression == "happy":
        d.chord(_s(270, y - 22, 330, y + 20), 0, 180, fill=inside, outline=ink, width=4 * SS)
        d.chord(_s(282, y + 2, 318, y + 22), 180, 360, fill=(240, 120, 130))
    elif expression == "worried":
        d.arc(_s(282, y, 318, y + 22), 200, 340, fill=ink, width=5 * SS)
    elif expression == "surprised":
        d.ellipse(_s(288, y - 8, 312, y + 20), fill=inside, outline=ink, width=4 * SS)
    elif expression == "smug":
        d.line(_sc(_bez((280, y + 4), (296, y + 8), (312, y + 4), (324, y - 8))), fill=ink, width=5 * SS)
    else:
        d.arc(_s(286, y - 10, 314, y + 8), 30, 150, fill=ink, width=5 * SS)


def _hair_back(d, t):
    h, o = t.hair, _ol(t.hair)
    if t.hair_style == "long":
        d.rounded_rectangle(_s(140, 190, 460, 600), radius=150 * SS, fill=h, outline=o, width=5 * SS)
    elif t.hair_style == "wavy":
        pts = _path((150, 260), ((120, 380), (150, 500), (120, 620)), ((200, 650), (400, 650), (480, 620)),
                    ((450, 500), (480, 380), (450, 260)), ((420, 140), (180, 140), (150, 260)))
        d.polygon(_sc(pts), fill=h, outline=o)
    elif t.hair_style == "bun":
        d.ellipse(_s(240, 92, 360, 200), fill=h, outline=o, width=5 * SS)


def _hair_front(img, t):
    d = ImageDraw.Draw(img)
    h, o = t.hair, _ol(t.hair)
    hl = _shade(h, 1.5) if sum(h) < 400 else _shade(h, 1.08)
    s = t.hair_style
    if s == "long":  # side-swept fringe
        pts = _path((150, 300), ((140, 190), (220, 140), (310, 142)), ((400, 144), (460, 200), (452, 300)),
                    ((430, 250), (390, 220), (350, 212)), ((300, 250), (220, 268), (150, 300)))
    elif s == "spiky":
        pts = [(150, 290), (146, 220), (170, 170), (200, 150), (210, 120), (250, 136), (280, 106), (316, 132),
               (356, 110), (380, 146), (420, 150), (440, 196), (456, 290), (430, 240), (380, 222), (320, 230),
               (260, 222), (200, 236)]
    elif s == "wavy":  # middle parting
        pts = _path((148, 320), ((140, 200), (220, 148), (300, 150)), ((380, 148), (460, 200), (452, 320)),
                    ((430, 250), (360, 200), (300, 196)), ((240, 200), (170, 250), (148, 320)))
    elif s == "short":
        pts = _path((152, 280), ((148, 190), (220, 142), (300, 140)), ((380, 142), (452, 190), (448, 280)),
                    (430, 240), (400, 226), (370, 236), (340, 220), (310, 234), (280, 218), (250, 234), (220, 222),
                    (190, 240), (168, 250))
    else:  # bun with soft fringe
        pts = _path((150, 300), ((146, 200), (220, 150), (300, 150)), ((380, 150), (454, 200), (450, 300)),
                    ((430, 240), (380, 226), (330, 236)), ((290, 222), (220, 230), (150, 300)))
    d.polygon(_sc(pts), fill=h, outline=o)
    m = _mask(img.size, pts)
    _clip(img, m, lambda dd: dd.polygon(_sc(_path((210, 176), ((250, 156), (330, 150), (380, 168)), (372, 182),
                                                  ((330, 168), (256, 172), (220, 196)))), fill=hl))
    ImageDraw.Draw(img).line(_sc(pts + [pts[0]]), fill=o, width=5 * SS)


def _person(t: Toon, expression: str) -> Image.Image:
    img = Image.new("RGBA", _s(BASE_W, BASE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _hair_back(d, t)
    # body and neck
    d.rectangle(_s(270, 420, 330, 480), fill=_shade(t.skin, 0.88))
    d.polygon(_sc(BODY), fill=t.top, outline=_ol(t.top))
    d.line(_sc(BODY), fill=_ol(t.top), width=5 * SS)
    d.polygon(_sc([(250, 456), (300, 500), (272, 524)]), fill=t.collar, outline=_ol(t.collar))
    d.polygon(_sc([(350, 456), (300, 500), (328, 524)]), fill=t.collar, outline=_ol(t.collar))
    for side in (-1, 1):  # arms resting at the sides
        x = 300 + side * 168
        arm = _path((x - side * 14, 520), ((x + side * 30, 560), (x + side * 40, 680), (x + side * 34, 760)),
                    (x - side * 30, 760), ((x - side * 30, 680), (x - side * 40, 580), (x - side * 14, 520)))
        d.polygon(_sc(arm), fill=_shade(t.top, 0.86))
        d.line(_sc(arm), fill=_ol(t.top), width=4 * SS)
    if t.tie:
        d.polygon(_sc([(290, 498), (310, 498), (318, 610), (300, 636), (282, 610)]), fill=t.accent, outline=_ol(t.accent))
    # ears and head
    for side in (-1, 1):
        ex = 300 + side * 146
        d.ellipse(_s(ex - 24, 290, ex + 24, 350), fill=t.skin, outline=_ol(t.skin), width=4 * SS)
    d.polygon(_sc(HEAD_PTS), fill=t.skin)
    d.line(_sc(HEAD_PTS + [HEAD_PTS[0]]), fill=_ol(t.skin), width=5 * SS)
    # blush
    blush = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush)
    for side in (-1, 1):
        ex = 300 + side * 92
        bd.ellipse(_s(ex - 26, 360, ex + 26, 384), fill=(255, 120, 130, 70))
    img.alpha_composite(blush)
    d = ImageDraw.Draw(img)
    for side in (-1, 1):
        _eye(d, 300 + side * 62, 318, t, expression, side)
    _brows(d, t, expression)
    d.arc(_s(292, 352, 308, 366), 20, 160, fill=_shade(t.skin, 0.7), width=4 * SS)  # nose
    _mouth(d, t, expression)
    if expression == "worried":  # sweat drop
        d.polygon(_sc(_path((430, 220), ((420, 246), (414, 262), (430, 266)), ((446, 262), (440, 246), (430, 220)))),
                  fill=(150, 210, 255), outline=(80, 140, 200))
    _hair_front(img, t)
    if t.glasses:
        d = ImageDraw.Draw(img)
        fr = (60, 50, 60)
        for side in (-1, 1):
            ex = 300 + side * 62
            d.rounded_rectangle(_s(ex - 48, 276, ex + 48, 360), radius=26 * SS, outline=fr, width=4 * SS)
        d.arc(_s(282, 300, 318, 330), 200, 340, fill=fr, width=5 * SS)
    return img


# ---------- the bugs: one creature per mental glitch ----------

BUGS = {
    "impostor": ("The Impostor", (150, 110, 220), "whispers that you don't deserve it"),
    "overthinker": ("The Overthinker", (250, 180, 70), "replays every conversation at 3 a.m."),
    "procrastinator": ("The Procrastinator", (80, 200, 180), "'five more minutes'"),
    "perfectionist": ("The Perfectionist", (240, 90, 100), "nothing is ever good enough"),
}


def _bug(kind: str, expression: str) -> Image.Image:
    img = Image.new("RGBA", _s(BASE_W, BASE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _, c, _ = BUGS[kind]
    o, belly = _ol(c), _shade(c, 1.25)
    ink = (36, 28, 40)
    droop = kind == "procrastinator"
    # antennae
    for side in (-1, 1):
        tip = (300 + side * 110, 230 if not droop else 330)
        d.line(_sc(_bez((300 + side * 40, 360), (300 + side * 60, 300), (tip[0] - side * 10, tip[1] + 30), tip)),
               fill=o, width=8 * SS)
        d.ellipse(_s(tip[0] - 20, tip[1] - 20, tip[0] + 20, tip[1] + 20), fill=c, outline=o, width=5 * SS)
    # feet
    for side in (-1, 1):
        d.ellipse(_s(300 + side * 70 - 44, 760, 300 + side * 70 + 44, 810), fill=_shade(c, 0.8), outline=o, width=5 * SS)
    # body
    if kind == "perfectionist":
        d.rounded_rectangle(_s(140, 360, 460, 790), radius=90 * SS, fill=c, outline=o, width=6 * SS)
    else:
        d.ellipse(_s(130, 350, 470, 800), fill=c, outline=o, width=6 * SS)
    d.ellipse(_s(210, 560, 390, 760), fill=belly)
    # arms
    for side in (-1, 1):
        d.line(_sc(_bez((300 + side * 160, 580), (300 + side * 200, 600), (300 + side * 210, 640), (300 + side * 196, 680))),
               fill=o, width=10 * SS)
    # eyes
    eyes = [(-62, 470), (62, 470)] if kind != "overthinker" else [(-80, 480), (0, 450), (80, 480)]
    for dx, ey in eyes:
        ex = 300 + dx
        if expression == "happy":
            d.arc(_s(ex - 26, ey - 14, ex + 26, ey + 28), 200, 340, fill=ink, width=8 * SS)
            continue
        r = 30 if kind != "overthinker" else 24
        d.ellipse(_s(ex - r, ey - r, ex + r, ey + r), fill=WHITE, outline=ink, width=4 * SS)
        pr = r // 2
        oy = 6 if kind == "procrastinator" else 0
        d.ellipse(_s(ex - pr, ey - pr + oy, ex + pr, ey + pr + oy), fill=ink)
        d.ellipse(_s(ex - pr + 4, ey - pr + 2 + oy, ex - pr + 12, ey - pr + 10 + oy), fill=WHITE)
        if kind == "procrastinator" or expression == "smug":  # sleepy / smug lids
            d.chord(_s(ex - r - 3, ey - r - 3, ex + r + 3, ey + r + 3), 180, 360, fill=c)
            d.line(_s(ex - r, ey, ex + r, ey), fill=ink, width=5 * SS)
    # mouth
    my = 560
    if expression == "happy":
        d.chord(_s(266, my - 20, 334, my + 24), 0, 180, fill=(120, 40, 60), outline=ink, width=4 * SS)
    elif expression == "worried":
        d.arc(_s(280, my, 320, my + 20), 200, 340, fill=ink, width=6 * SS)
    elif kind == "impostor" or expression == "smug":
        d.line(_sc(_bez((270, my + 4), (290, my + 10), (316, my + 6), (334, my - 8))), fill=ink, width=6 * SS)
    else:
        d.arc(_s(280, my - 14, 320, my + 10), 30, 150, fill=ink, width=6 * SS)
    # signature props
    if kind == "impostor":  # little eye mask
        d.rounded_rectangle(_s(206, 438, 394, 500), radius=30 * SS, fill=(40, 30, 50, 235))
        for dx in (-62, 62):
            d.ellipse(_s(300 + dx - 20, 452, 300 + dx + 20, 488), fill=WHITE)
            d.ellipse(_s(300 + dx - 9, 461, 300 + dx + 9, 479), fill=ink)
    elif kind == "overthinker":  # thought loop above the head
        for k in range(3):
            d.arc(_s(240 + k * 10, 150 + k * 14, 360 - k * 10, 230 - k * 6), 30 + k * 40, 330 + k * 20, fill=o, width=6 * SS)
    elif kind == "procrastinator":  # zzz
        for k, (x, y, sz) in enumerate(((410, 300, 26), (448, 250, 34), (492, 190, 44))):
            d.line(_s(x, y, x + sz, y), fill=o, width=5 * SS)
            d.line(_s(x + sz, y, x, y + sz), fill=o, width=5 * SS)
            d.line(_s(x, y + sz, x + sz, y + sz), fill=o, width=5 * SS)
    elif kind == "perfectionist":  # tiny ruler in hand
        d.rounded_rectangle(_s(470, 600, 500, 720), radius=4 * SS, fill=(250, 230, 150), outline=o, width=3 * SS)
        for y in range(612, 712, 14):
            d.line(_s(470, y, 484, y), fill=o, width=2 * SS)
    return img


def draw(name: str, expression: str | None = None, height: int = 700) -> Image.Image:
    """People (TOONS), bugs (BUGS) or 'glitch'. Without an expression each uses its default."""
    if name == "glitch":
        return _finish(_glitch(expression or "happy"), height, GLITCH_BLUE, split=True)
    if name in BUGS:
        return _finish(_bug(name, expression or "neutral"), height, BUGS[name][1])
    t = TOONS[name]
    img = _person(t, expression or t.default).crop((0, 0, BASE_W * SS, 720 * SS))  # bust: big head, short body
    return _finish(img, height, t.accent)
