"""Recurring characters drawn in code, so they look identical in every scene and every video.

Style: flat corporate illustration. Realistic bust proportions, no black outlines, two-tone
shading, small understated facial features and office clothing. Each person is recognizable by
a fixed palette, hairstyle and one signature detail (glasses, tie, pearls...).
GLITCH, the channel host, is a floating screen with a pixel face in light blue.
"""
import math
import random
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .config import CYAN, MAGENTA

SS = 3  # supersampling factor for smooth edges
BASE_W, BASE_H = 600, 900

# GLITCH uses the light blue of Potencia People (Giancarlo's consultancy); swap the hex here if the brand gives an exact one.
GLITCH_BLUE = (56, 182, 255)
GLITCH_DEEP = (12, 26, 46)

EXPRESSIONS = ("neutral", "happy", "worried", "surprised", "smug")


@dataclass(frozen=True)
class Person:
    name: str
    role: str
    skin: tuple
    hair: tuple
    outfit: str          # blazer | suit | sweater | cardigan
    jacket: tuple
    shirt: tuple
    accent: tuple        # signature colour (tie...), also the soft rim light
    hair_style: str      # long_side | side_part | long_middle | textured | bob
    glasses: bool = False
    beard: bool = False
    earrings: bool = False
    pearls: bool = False
    grey_temples: bool = False
    default: str = "neutral"


CAST = {
    # The overthinker: talented analyst, perfectionist, kind, always doubts herself.
    "sarah": Person("Sarah Collins", "Senior Analyst", skin=(226, 178, 148), hair=(78, 52, 40), outfit="blazer",
                    jacket=(28, 104, 96), shirt=(242, 244, 246), accent=(70, 210, 180), hair_style="long_side",
                    glasses=True, default="worried"),
    # The overconfident director: charismatic, decisive, rarely checks the data.
    "richard": Person("Richard Hale", "Operations Director", skin=(206, 156, 124), hair=(52, 46, 44), outfit="suit",
                      jacket=(32, 44, 76), shirt=(238, 242, 248), accent=(226, 170, 64), hair_style="side_part",
                      grey_temples=True, default="smug"),
    # The mentor: Head of People, calm, evidence first, asks the right question.
    "elena": Person("Elena Ruiz", "Head of People", skin=(176, 122, 92), hair=(34, 26, 24), outfit="blazer",
                    jacket=(122, 38, 58), shirt=(30, 30, 36), accent=(232, 112, 136), hair_style="long_middle",
                    earrings=True, default="happy"),
    # The new hire: bright, eager, says yes to everything, struggles to finish.
    "daniel": Person("Daniel Brooks", "Product Associate", skin=(132, 90, 66), hair=(28, 22, 20), outfit="sweater",
                     jacket=(92, 100, 112), shirt=(150, 196, 236), accent=(120, 190, 255), hair_style="textured",
                     default="surprised"),
    # The veteran: 25 years in the company, warm, reliable, resists every change.
    "margaret": Person("Margaret Lane", "Finance Manager", skin=(234, 196, 172), hair=(206, 206, 210), outfit="cardigan",
                       jacket=(96, 72, 120), shirt=(246, 240, 230), accent=(190, 150, 240), hair_style="bob",
                       glasses=True, pearls=True, default="smug"),
}


# ---------- geometry helpers ----------

def _bez(p0, p1, p2, p3, n=20):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _path(start, *segs):
    """Each seg is either a point (straight line) or (c1, c2, end) for a cubic curve."""
    pts, cur = [start], start
    for seg in segs:
        if isinstance(seg[0], tuple):
            pts += _bez(cur, *seg)[1:]
            cur = seg[2]
        else:
            pts.append(seg)
            cur = seg
    return pts


def _sc(pts):
    return [(x * SS, y * SS) for x, y in pts]


def _s(*v):
    return tuple(int(x * SS) for x in v)


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _mask(size, pts):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(_sc(pts), fill=255)
    return m


def _clip(base, mask, draw_fn):
    """Draw with draw_fn onto a layer, keep only what falls inside mask, composite onto base."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    layer.putalpha(ImageChops.darker(layer.getchannel("A"), mask))
    base.alpha_composite(layer)


def _egg(cx, cy, a, bt, bb, chin=0.22, n=72):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        s = math.sin(t)
        b = bb if s > 0 else bt
        pts.append((cx + a * math.cos(t) * (1 - chin * max(0.0, s) ** 3), cy + b * s))
    return pts


# ---------- person ----------

OUTFIT_LIFT = 32
FACE = _egg(300, 292, 94, 116, 126)
TORSO = _path((262, 468), ((262, 520), (150, 528), (98, 576)), ((58, 612), (46, 700), (42, 960)), (558, 960),
              ((554, 700), (542, 612), (502, 576)), ((450, 528), (338, 520), (338, 468)))


def _hair_back(d, p):
    h = p.hair
    if p.hair_style == "long_side":
        d.polygon(_sc(_path((206, 230), ((190, 330), (186, 470), (214, 548)), (386, 548),
                            ((414, 470), (410, 330), (394, 230)), ((370, 160), (230, 160), (206, 230)))), fill=h)
    elif p.hair_style == "long_middle":
        d.polygon(_sc(_path((204, 220), ((176, 330), (170, 520), (200, 610)), (400, 610),
                            ((430, 520), (424, 330), (396, 220)), ((370, 150), (230, 150), (204, 220)))), fill=h)
    elif p.hair_style == "bob":
        d.polygon(_sc(_path((204, 230), ((192, 300), (192, 380), (214, 410)), (386, 410),
                            ((408, 380), (408, 300), (396, 230)), ((370, 160), (230, 160), (204, 230)))), fill=h)


def _hair_front(img, p):
    d = ImageDraw.Draw(img)
    h = p.hair
    hl = _shade(h, 1.45) if sum(h) < 400 else _shade(h, 1.08)
    s = p.hair_style
    if s == "long_side":
        pts = _path((204, 300), ((198, 230), (236, 172), (300, 168)), ((366, 168), (404, 220), (400, 300)),
                    ((392, 262), (366, 228), (336, 214)), ((290, 228), (232, 250), (204, 300)))
    elif s == "long_middle":
        pts = _path((202, 330), ((196, 230), (240, 172), (300, 172)), ((360, 172), (404, 230), (398, 330)),
                    ((390, 270), (350, 214), (300, 204)), ((250, 214), (210, 270), (202, 330)))
    elif s == "side_part":
        pts = _path((208, 282), ((204, 214), (240, 170), (302, 166)), ((364, 166), (398, 210), (394, 282)),
                    ((388, 244), (372, 224), (346, 218)), ((300, 214), (254, 216), (230, 230)), (214, 282))
    elif s == "textured":
        pts = _path((210, 270), ((206, 210), (244, 166), (302, 160)), ((362, 162), (396, 206), (392, 270)),
                    (380, 236), (362, 226), (340, 230), (316, 220), (292, 228), (268, 222), (246, 234), (224, 244))
    else:  # bob with a soft fringe
        pts = _path((202, 330), ((196, 226), (240, 170), (300, 168)), ((362, 168), (406, 226), (398, 330)),
                    ((392, 290), (384, 254), (360, 246)), ((320, 252), (270, 236), (238, 250)),
                    ((214, 262), (206, 300), (202, 330)))
    d.polygon(_sc(pts), fill=h)
    _clip(img, _mask(img.size, pts), lambda dd: dd.polygon(_sc(_path(
        (230, 200), ((260, 176), (320, 170), (360, 186)), (352, 198), ((316, 186), (266, 190), (238, 212)))), fill=hl))
    if s == "side_part":
        d.line(_sc([(258, 176), (252, 214)]), fill=_shade(h, 0.7), width=3 * SS)
    if p.grey_temples:
        grey = (126, 124, 126)
        d.polygon(_sc(_path((208, 282), ((206, 262), (208, 246), (214, 236)), (222, 240), (216, 282))), fill=grey)
        d.polygon(_sc(_path((392, 282), ((394, 262), (392, 246), (386, 236)), (378, 240), (384, 282))), fill=grey)


def _brow(d, ex, side, color, tilt=0.0, lift=0.0):
    """side=-1 left eye, +1 right. tilt>0 raises the inner end (worried)."""
    y = 266 - lift
    inner, outer = ex - side * 22, ex + side * 22
    yi, yo = y - tilt * 10, y + tilt * 4
    d.polygon(_sc([(inner, yi - 3), (outer, yo - 2), (outer, yo + 2), (inner, yi + 4)]), fill=color)


def _face(img, p, expression):
    d = ImageDraw.Draw(img)
    dark = (44, 34, 34)
    brow = _shade(p.hair, 0.8) if sum(p.hair) < 450 else (120, 114, 114)
    lip = _shade(p.skin, 0.62)
    for side in (-1, 1):
        ex = 300 + side * 38
        tilt = {"worried": 1.0, "surprised": 0.2}.get(expression, 0.0)
        lift = {"surprised": 8, "happy": 3}.get(expression, 0)
        if expression == "smug" and side == 1:
            lift = 7
        _brow(d, ex, side, brow, tilt, lift)
        if expression == "happy":
            d.arc(_s(ex - 11, 292, ex + 11, 310), 200, 340, fill=dark, width=4 * SS)
        elif expression == "smug":
            d.chord(_s(ex - 9, 290, ex + 9, 310), 0, 180, fill=dark)
            d.line(_s(ex - 11, 300, ex + 11, 300), fill=_shade(p.skin, 0.7), width=3 * SS)
        else:
            r = 8 if expression == "surprised" else 6
            d.ellipse(_s(ex - r, 300 - r - 1, ex + r, 300 + r + 1), fill=dark)
    d.line(_sc(_bez((304, 300), (308, 316), (312, 326), (304, 334))), fill=_shade(p.skin, 0.8), width=3 * SS)  # nose
    my = 356
    if expression == "happy":
        d.chord(_s(282, my - 12, 318, my + 12), 0, 180, fill=_shade(p.skin, 0.45))
        d.chord(_s(286, my - 10, 314, my + 2), 0, 180, fill=(250, 250, 250))
    elif expression == "worried":
        d.arc(_s(286, my, 314, my + 14), 200, 340, fill=lip, width=4 * SS)
    elif expression == "surprised":
        d.ellipse(_s(292, my - 6, 308, my + 12), fill=_shade(p.skin, 0.45))
    elif expression == "smug":
        d.line(_sc(_bez((286, my + 2), (296, my + 4), (306, my + 2), (316, my - 6))), fill=lip, width=4 * SS)
    else:
        d.line(_sc(_bez((286, my), (294, my + 3), (306, my + 3), (314, my))), fill=lip, width=4 * SS)


def _outfit(img, p):
    d = ImageDraw.Draw(img)
    j, jd = p.jacket, _shade(p.jacket, 0.78)
    d.polygon(_sc(TORSO), fill=j)
    _clip(img, _mask(img.size, TORSO), lambda dd: dd.polygon(_sc([(420, 520), (600, 520), (600, 960), (470, 960)]), fill=jd))
    if p.outfit in ("blazer", "suit"):
        d.polygon(_sc([(262, 498), (338, 498), (326, 640), (300, 700), (274, 640)]), fill=p.shirt)
        if p.outfit == "suit":
            d.polygon(_sc([(262, 492), (292, 522), (272, 548)]), fill=_shade(p.shirt, 0.9))
            d.polygon(_sc([(338, 492), (308, 522), (328, 548)]), fill=_shade(p.shirt, 0.9))
            d.polygon(_sc([(290, 520), (310, 520), (306, 540), (294, 540)]), fill=_shade(p.accent, 0.85))
            d.polygon(_sc([(294, 540), (306, 540), (316, 660), (300, 690), (284, 660)]), fill=p.accent)
        d.polygon(_sc([(258, 500), (300, 700), (238, 640), (214, 566), (236, 552)]), fill=jd)  # lapels
        d.polygon(_sc([(342, 500), (300, 700), (362, 640), (386, 566), (364, 552)]), fill=_shade(j, 0.7))
        d.line(_sc([(300, 700), (300, 960)]), fill=_shade(j, 0.65), width=3 * SS)
    elif p.outfit == "sweater":
        d.polygon(_sc([(256, 486), (300, 520), (344, 486), (350, 512), (300, 548), (250, 512)]), fill=p.shirt)
        d.polygon(_sc([(300, 520), (276, 556), (256, 506)]), fill=_shade(p.shirt, 0.9))
        d.polygon(_sc([(300, 520), (324, 556), (344, 506)]), fill=_shade(p.shirt, 0.9))
        d.arc(_s(236, 470, 364, 572), 20, 160, fill=_shade(j, 0.8), width=10 * SS)
    else:  # cardigan over a blouse
        d.polygon(_sc([(256, 494), (344, 494), (318, 650), (300, 670), (282, 650)]), fill=p.shirt)
        d.polygon(_sc([(256, 494), (300, 670), (260, 960), (226, 960), (232, 560)]), fill=jd)
        d.polygon(_sc([(344, 494), (300, 670), (340, 960), (374, 960), (368, 560)]), fill=_shade(j, 0.7))
        for y in (690, 750, 810):
            d.ellipse(_s(312, y, 324, y + 12), fill=_shade(j, 1.3))
    if p.pearls:
        for k in range(15):
            t = math.pi * (0.15 + 0.7 * k / 14)
            x, y = 300 - 46 * math.cos(t), 500 + 40 * math.sin(t)
            d.ellipse(_s(x - 6, y - 6, x + 6, y + 6), fill=(246, 242, 236), outline=(200, 194, 186))


def _person(p: Person, expression: str) -> Image.Image:
    img = Image.new("RGBA", _s(BASE_W, BASE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    skin, skin_d = p.skin, _shade(p.skin, 0.84)
    _hair_back(d, p)
    d.polygon(_sc([(262, 370), (338, 370), (342, 490), (258, 490)]), fill=skin_d)  # neck, in shadow
    clothes = Image.new("RGBA", img.size, (0, 0, 0, 0))
    _outfit(clothes, p)
    img.alpha_composite(clothes, (0, -OUTFIT_LIFT * SS))  # shoulders sit higher: shorter neck
    d = ImageDraw.Draw(img)
    for side in (-1, 1):  # ears
        ex = 300 + side * 92
        d.ellipse(_s(ex - 16, 280, ex + 16, 330), fill=skin_d if side > 0 else skin)
        if p.earrings:
            d.ellipse(_s(ex - 5, 330, ex + 5, 340), fill=(232, 196, 96))
    d.polygon(_sc(FACE), fill=skin)
    fm = _mask(img.size, FACE)
    _clip(img, fm, lambda dd: dd.ellipse(_s(350, 150, 620, 470), fill=_shade(p.skin, 0.9)))  # shadow side of the face
    if p.beard:
        jaw = [pt for pt in FACE if pt[1] > 338]
        _clip(img, fm, lambda dd: dd.polygon(_sc(jaw), fill=_shade(p.hair, 1.8) + (120,)))
        _clip(img, fm, lambda dd: dd.ellipse(_s(280, 340, 320, 372), fill=skin))
    _face(img, p, expression)
    _hair_front(img, p)
    if p.glasses:
        d = ImageDraw.Draw(img)
        frame = (52, 52, 60)
        for side in (-1, 1):
            ex = 300 + side * 38
            d.rounded_rectangle(_s(ex - 27, 284, ex + 27, 316), radius=10 * SS, outline=frame, width=3 * SS)
        d.line(_s(289, 296, 311, 296), fill=frame, width=3 * SS)
    return img


# ---------- GLITCH ----------

def _glitch(expression: str) -> Image.Image:
    """GLITCH, the channel host: a floating screen with a pixel face."""
    img = Image.new("RGBA", _s(BASE_W, BASE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    B = GLITCH_BLUE
    d.line(_s(300, 214, 300, 270), fill=_shade(B, 0.8), width=6 * SS)
    d.ellipse(_s(286, 194, 314, 222), fill=B)
    d.ellipse(_s(190, 690, 410, 720), fill=(0, 0, 0, 90))  # floor shadow: it floats
    d.rounded_rectangle(_s(110, 270, 490, 590), radius=70 * SS, fill=GLITCH_DEEP, outline=B, width=7 * SS)
    d.rounded_rectangle(_s(146, 306, 454, 554), radius=44 * SS, fill=(4, 12, 24))
    for y in range(312, 550, 9):  # scanlines
        d.line(_s(152, y, 448, y), fill=(9, 24, 42), width=2 * SS)

    def px(x, y, w=16, h=16):
        d.rounded_rectangle(_s(x, y, x + w, y + h), radius=3 * SS, fill=B)

    L, R, ey = 236, 364, 396
    if expression == "happy":
        for ex in (L, R):
            d.arc(_s(ex - 30, ey - 22, ex + 30, ey + 26), 200, 340, fill=B, width=11 * SS)
    elif expression == "worried":
        for ex in (L, R):
            px(ex - 18, ey - 14, 36, 40)
        d.line(_s(204, ey - 26, 256, ey - 40), fill=B, width=7 * SS)
        d.line(_s(396, ey - 26, 344, ey - 40), fill=B, width=7 * SS)
    elif expression == "surprised":
        for ex in (L, R):
            px(ex - 24, ey - 30, 48, 58)
    elif expression == "smug":
        px(L - 22, ey + 2, 44, 22)
        px(R - 22, ey - 20, 44, 44)
    else:
        for ex in (L, R):
            px(ex - 20, ey - 24, 40, 48)
    my = 476
    if expression == "surprised":
        px(286, my - 8, 28, 28)
    elif expression == "worried":
        for k, x in enumerate(range(256, 344, 18)):
            px(x, my + (8 if k % 2 else 0), 14, 14)
    elif expression == "smug":
        for x, y in ((276, my + 8), (296, my + 8), (316, my), (334, my - 10)):
            px(x, y, 16, 14)
    else:
        for x, y in ((250, my - 10), (268, my + 4), (290, my + 10), (312, my + 10), (334, my + 4), (352, my - 10)):
            px(x, y, 16, 14)
    return img


# ---------- output ----------

def _finish(img: Image.Image, height: int, rim, split: bool = False) -> Image.Image:
    """Downsample and add a soft rim light (and, for GLITCH, a magenta/cyan split)."""
    w = int(height * BASE_W / BASE_H)
    img = img.resize((w, height), Image.LANCZOS)
    pad = height // 12
    out = Image.new("RGBA", (w + 2 * pad, height + 2 * pad), (0, 0, 0, 0))
    alpha = img.getchannel("A")
    g = Image.new("RGBA", img.size, rim + (0,))
    g.putalpha(alpha.point(lambda a: int(a * (0.6 if split else 0.3))))
    out.alpha_composite(g.filter(ImageFilter.GaussianBlur(max(2, height // 60))), (pad, pad))
    if split:
        shift = max(2, height // 240)
        for col, dx in ((MAGENTA, -shift), (CYAN, shift)):
            ghost = Image.new("RGBA", img.size, col + (0,))
            ghost.putalpha(alpha.point(lambda a: int(a * 0.4)))
            out.alpha_composite(ghost, (pad + dx, pad))
    out.alpha_composite(img, (pad, pad))
    return out


def draw(name: str, expression: str | None = None, height: int = 700) -> Image.Image:
    """Return the character as a transparent RGBA image, `height` pixels tall (plus glow padding).
    Without an expression, each character uses their default one (part of their personality)."""
    if name == "glitch":
        return _finish(_glitch(expression or "happy"), height, GLITCH_BLUE, split=True)
    p = CAST[name]
    return _finish(_person(p, expression or p.default), height, p.accent)


def slice_glitch(img: Image.Image, seed: int = 1, bands: int = 3) -> Image.Image:
    """Shift a few horizontal bands sideways, for a 'glitching' frame."""
    rnd = random.Random(seed)
    out = img.copy()
    w, h = img.size
    for _ in range(bands):
        y = rnd.randint(int(h * 0.2), int(h * 0.8))
        bh = rnd.randint(4, max(6, h // 40))
        band = img.crop((0, y, w, y + bh))
        out.paste((0, 0, 0, 0), (0, y, w, y + bh))
        out.alpha_composite(band, (rnd.choice([-1, 1]) * rnd.randint(8, 24), y))
    return out
