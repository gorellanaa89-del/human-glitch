"""Recurring characters drawn in code, so they look identical in every scene and every video.

Each human character is a flat bust (head and shoulders) built from simple shapes; what makes
them recognizable is a fixed palette plus one or two signature traits (Sarah's glasses and bob).
GLITCH is the channel's own character: a little CRT terminal with a pixel face, in light blue.
"""
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter

from .config import CYAN, GREEN, MAGENTA

SS = 3  # supersampling factor for smooth edges
INK = (8, 10, 14)
BASE_W, BASE_H = 600, 900


# GLITCH uses the light blue of Potencia People (Giancarlo's consultancy); swap the hex here if the brand gives an exact one.
GLITCH_BLUE = (56, 182, 255)
GLITCH_DEEP = (14, 34, 58)


@dataclass(frozen=True)
class Person:
    name: str
    skin: tuple
    hair: tuple
    top: tuple
    jacket: tuple
    accent: tuple  # signature colour, also used for the rim glow
    hair_style: str = "bob"  # bob | quiff | bun | curly | short
    glasses: bool = False
    tie: bool = False
    earrings: bool = False
    headphones: bool = False
    scarf: bool = False
    default: str = "neutral"


CAST = {
    # the overthinker: junior analyst, perfectionist, kind, doubts herself
    "sarah": Person("Sarah", skin=(214, 160, 128), hair=(58, 38, 32), top=(236, 240, 244),
                    jacket=(22, 96, 86), accent=(64, 214, 170), hair_style="bob", glasses=True, default="worried"),
    # the overconfident manager: charismatic, talks big, loves meetings
    "marcus": Person("Marcus", skin=(176, 124, 96), hair=(34, 30, 30), top=(236, 240, 244),
                     jacket=(30, 42, 78), accent=(255, 176, 60), hair_style="quiff", tie=True, default="smug"),
    # the mentor: senior, calm, evidence first, asks the right question
    "priya": Person("Priya", skin=(150, 100, 72), hair=(26, 20, 22), top=(250, 236, 214),
                    jacket=(196, 140, 40), accent=(255, 214, 90), hair_style="bun", earrings=True, default="happy"),
    # the new guy: enthusiastic intern, starts ten things, finishes two
    "leo": Person("Leo", skin=(236, 196, 164), hair=(150, 84, 40), top=(60, 64, 72),
                  jacket=(214, 70, 70), accent=(255, 110, 110), hair_style="curly", headphones=True, default="surprised"),
    # the veteran: 25 years in the company, warm but resists every change
    "rosa": Person("Rosa", skin=(222, 178, 150), hair=(196, 198, 204), top=(240, 236, 230),
                   jacket=(110, 70, 120), accent=(200, 140, 255), hair_style="short", glasses=True, scarf=True, default="smug"),
}

EXPRESSIONS = ("neutral", "happy", "worried", "surprised", "smug")


def _s(*v):
    return tuple(int(x * SS) for x in v)


def _face(d, expression, eye_y=318, cx=300):
    lw = 5 * SS
    # eyebrows: worried tilts up toward the middle, happy lifts them
    for side in (-1, 1):
        ex = cx + side * 50
        if expression == "worried":
            # inner end (toward the nose) higher than the outer end
            inner, outer = (ex + side * -24, ex + side * 24)
            d.line(_s(inner, eye_y - 60, outer, eye_y - 46), fill=INK, width=lw)
        elif expression == "surprised":
            d.arc(_s(ex - 24, eye_y - 76, ex + 24, eye_y - 50), 200, 340, fill=INK, width=lw)
        elif expression == "smug":
            y = eye_y - 62 if side > 0 else eye_y - 48  # one raised brow
            d.line(_s(ex - 24, y + 6, ex + 24, y), fill=INK, width=lw)
        elif expression == "happy":
            d.arc(_s(ex - 24, eye_y - 64, ex + 24, eye_y - 40), 200, 340, fill=INK, width=lw)
        else:
            d.line(_s(ex - 24, eye_y - 50, ex + 24, eye_y - 50), fill=INK, width=lw)
        if expression == "happy":
            d.arc(_s(ex - 16, eye_y - 10, ex + 16, eye_y + 14), 200, 340, fill=INK, width=lw + SS)
        elif expression == "smug":
            d.chord(_s(ex - 12, eye_y - 12, ex + 12, eye_y + 14), 0, 180, fill=INK)  # half-closed eyes
            d.line(_s(ex - 14, eye_y, ex + 14, eye_y), fill=INK, width=lw)
        else:
            r = 14 if expression == "surprised" else 11
            d.ellipse(_s(ex - r, eye_y - r - 2, ex + r, eye_y + r + 2), fill=INK)
            d.ellipse(_s(ex - 3, eye_y - 8, ex + 4, eye_y - 1), fill=(255, 255, 255))
    d.arc(_s(cx - 12, eye_y + 22, cx + 12, eye_y + 44), 20, 160, fill=INK, width=lw - SS)  # nose
    my = eye_y + 82
    if expression == "happy":
        d.chord(_s(cx - 38, my - 30, cx + 38, my + 22), 0, 180, fill=INK)
    elif expression == "worried":
        d.arc(_s(cx - 26, my, cx + 26, my + 30), 200, 340, fill=INK, width=lw)
    elif expression == "surprised":
        d.ellipse(_s(cx - 16, my - 14, cx + 16, my + 24), fill=INK)
    elif expression == "smug":
        d.arc(_s(cx - 30, my - 26, cx + 30, my + 10), 20, 110, fill=INK, width=lw)  # lopsided smile
    else:
        d.line(_s(cx - 22, my + 4, cx + 22, my + 4), fill=INK, width=lw)


def _person(p: Person, expression: str) -> Image.Image:
    img = Image.new("RGBA", _s(BASE_W, BASE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ow = 6 * SS
    # hair behind the head
    if p.hair_style == "bob":
        d.rounded_rectangle(_s(158, 170, 442, 540), radius=130 * SS, fill=p.hair, outline=INK, width=ow)
    elif p.hair_style == "bun":
        d.ellipse(_s(240, 92, 360, 200), fill=p.hair, outline=INK, width=ow)
    elif p.hair_style == "curly":
        for cx, cy in ((196, 230), (240, 178), (300, 160), (360, 178), (404, 230), (420, 290), (180, 290)):
            d.ellipse(_s(cx - 52, cy - 52, cx + 52, cy + 52), fill=p.hair, outline=INK, width=ow)
    # body: jacket with a lighter top showing in a V
    d.rounded_rectangle(_s(90, 560, 510, 1010), radius=150 * SS, fill=p.jacket, outline=INK, width=ow)
    d.polygon(_s(236, 568, 364, 568, 300, 730), fill=p.top, outline=INK)
    if p.tie:
        d.polygon(_s(286, 590, 314, 590, 324, 700, 300, 728, 276, 700), fill=p.accent, outline=INK)
    d.rectangle(_s(262, 450, 338, 580), fill=p.skin)
    d.line(_s(262, 450, 262, 570), fill=INK, width=ow)
    d.line(_s(338, 450, 338, 570), fill=INK, width=ow)
    if p.scarf:
        d.rounded_rectangle(_s(232, 540, 368, 600), radius=28 * SS, fill=p.accent, outline=INK, width=ow)
        d.polygon(_s(320, 590, 352, 590, 360, 690, 326, 690), fill=p.accent, outline=INK)
    if p.headphones:
        d.arc(_s(200, 520, 400, 660), 0, 180, fill=(30, 30, 36), width=14 * SS)
        for ex in (204, 396):
            d.ellipse(_s(ex - 26, 560, ex + 26, 620), fill=p.accent, outline=INK, width=ow)
    # head and ears
    for ex in (184, 416):
        d.ellipse(_s(ex - 22, 300, ex + 22, 360), fill=p.skin, outline=INK, width=ow)
    if p.earrings:
        for ex in (184, 416):
            d.ellipse(_s(ex - 9, 362, ex + 9, 380), fill=p.accent, outline=INK, width=2 * SS)
    d.ellipse(_s(186, 180, 414, 470), fill=p.skin, outline=INK, width=ow)
    # hair on top
    if p.hair_style == "bob":
        d.pieslice(_s(176, 160, 424, 380), 180, 360, fill=p.hair, outline=INK, width=ow)
        d.polygon(_s(178, 270, 300, 270, 196, 330), fill=p.hair)  # side-swept fringe
    elif p.hair_style == "quiff":
        d.rounded_rectangle(_s(180, 172, 420, 300), radius=90 * SS, fill=p.hair, outline=INK, width=ow)
        d.ellipse(_s(194, 236, 406, 330), fill=p.skin)
        # swept-up pompadour, higher on one side
        d.polygon(_s(186, 262, 192, 196, 236, 140, 312, 118, 392, 136, 424, 186, 420, 252, 392, 214, 318, 200, 250, 214),
                  fill=p.hair, outline=INK)
        d.line(_s(250, 214, 330, 150), fill=(90, 84, 84), width=4 * SS)  # shine
    elif p.hair_style == "bun":
        d.pieslice(_s(182, 168, 418, 360), 180, 360, fill=p.hair, outline=INK, width=ow)
        d.line(_s(300, 176, 300, 262), fill=INK, width=3 * SS)  # centre parting
    elif p.hair_style == "curly":
        for cx in (226, 272, 318, 364):
            d.ellipse(_s(cx - 34, 196, cx + 34, 262), fill=p.hair, outline=INK, width=ow)
    else:  # short
        d.rounded_rectangle(_s(180, 172, 420, 300), radius=90 * SS, fill=p.hair, outline=INK, width=ow)
        d.ellipse(_s(194, 232, 406, 330), fill=p.skin)
    _face(d, expression)
    if p.glasses:
        for ex in (250, 350):
            d.rounded_rectangle(_s(ex - 38, 290, ex + 38, 346), radius=14 * SS, outline=INK, width=5 * SS)
        d.line(_s(286, 312, 314, 312), fill=INK, width=5 * SS)
    return img


def _glitch(expression: str) -> Image.Image:
    """GLITCH, the channel character: a small CRT terminal with a pixel face."""
    img = Image.new("RGBA", _s(BASE_W, BASE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # antenna
    d.line(_s(300, 150, 300, 230), fill=GLITCH_BLUE, width=7 * SS)
    d.ellipse(_s(282, 120, 318, 156), fill=MAGENTA)
    # body and legs
    d.rounded_rectangle(_s(220, 600, 380, 780), radius=36 * SS, fill=GLITCH_DEEP, outline=GLITCH_BLUE, width=7 * SS)
    for lx in (255, 345):
        d.line(_s(lx, 780, lx, 850), fill=GLITCH_BLUE, width=9 * SS)
        d.line(_s(lx - 20, 850, lx + 20, 850), fill=GLITCH_BLUE, width=9 * SS)
    arm_up = expression == "happy"
    d.line(_s(220, 650, 150, 560 if arm_up else 720), fill=GLITCH_BLUE, width=9 * SS)
    d.line(_s(380, 650, 450, 560 if arm_up else 720), fill=GLITCH_BLUE, width=9 * SS)
    # monitor head with a screen
    d.rounded_rectangle(_s(120, 220, 480, 560), radius=60 * SS, fill=GLITCH_DEEP, outline=GLITCH_BLUE, width=8 * SS)
    d.rounded_rectangle(_s(160, 260, 440, 520), radius=34 * SS, fill=(4, 12, 24))
    for y in range(266, 516, 10):  # scanlines
        d.line(_s(166, y, 434, y), fill=(10, 26, 44), width=SS * 2)
    px = 22
    if expression == "surprised":
        for ex in (236, 364):
            d.rectangle(_s(ex - 28, 318, ex + 28, 392), fill=GLITCH_BLUE)
        d.rectangle(_s(282, 440, 318, 476), fill=GLITCH_BLUE)
        return img
    if expression == "smug":
        d.rectangle(_s(214, 352, 258, 384), fill=GLITCH_BLUE)
        d.rectangle(_s(342, 330, 386, 384), fill=GLITCH_BLUE)
        for x, y in ((280, 456), (304, 456), (328, 446), (352, 432)):
            d.rectangle(_s(x, y, x + 14, y + 14), fill=GLITCH_BLUE)
        return img
    if expression == "happy":
        for ex in (236, 364):
            d.arc(_s(ex - 34, 330, ex + 34, 390), 200, 340, fill=GLITCH_BLUE, width=12 * SS)
    elif expression == "worried":
        for ex in (236, 364):
            d.rectangle(_s(ex - px, 340, ex + px, 384), fill=GLITCH_BLUE)
        d.line(_s(200, 330, 262, 314), fill=GLITCH_BLUE, width=8 * SS)
        d.line(_s(400, 330, 338, 314), fill=GLITCH_BLUE, width=8 * SS)
    else:
        for ex in (236, 364):
            d.rectangle(_s(ex - px, 330, ex + px, 384), fill=GLITCH_BLUE)
    if expression == "worried":
        for k, x in enumerate(range(250, 352, 17)):
            y = 456 + (8 if k % 2 else 0)
            d.rectangle(_s(x, y, x + 12, y + 12), fill=GLITCH_BLUE)
    else:  # pixel smile
        for x, y in ((240, 432), (258, 450), (282, 460), (306, 460), (330, 450), (348, 432)):
            d.rectangle(_s(x, y, x + 14, y + 14), fill=GLITCH_BLUE)
    return img


def _finish(img: Image.Image, height: int, glow_color=GREEN, glow: bool = True) -> Image.Image:
    """Downsample, add a soft rim glow in the character's colour and a subtle magenta/cyan split."""
    w = int(height * BASE_W / BASE_H)
    img = img.resize((w, height), Image.LANCZOS)
    pad = height // 10
    out = Image.new("RGBA", (w + 2 * pad, height + 2 * pad), (0, 0, 0, 0))
    alpha = img.getchannel("A")
    if glow:
        g = Image.new("RGBA", img.size, glow_color + (0,))
        g.putalpha(alpha.point(lambda a: int(a * 0.55)))
        out.alpha_composite(g.filter(ImageFilter.GaussianBlur(height // 40)), (pad, pad))
        shift = max(2, height // 220)
        for col, dx in ((MAGENTA, -shift), (CYAN, shift)):
            ghost = Image.new("RGBA", img.size, col + (0,))
            ghost.putalpha(alpha.point(lambda a: int(a * 0.5)))
            out.alpha_composite(ghost, (pad + dx, pad))
    out.alpha_composite(img, (pad, pad))
    return out


def draw(name: str, expression: str | None = None, height: int = 700) -> Image.Image:
    """Return the character as a transparent RGBA image, `height` pixels tall (plus glow padding).
    Without an expression, each character uses their default one (part of their personality)."""
    if name == "glitch":
        return _finish(_glitch(expression or "happy"), height, GLITCH_BLUE)
    p = CAST[name]
    return _finish(_person(p, expression or p.default), height, p.accent)


def slice_glitch(img: Image.Image, seed: int = 1, bands: int = 3) -> Image.Image:
    """Shift a few horizontal bands sideways, for a 'glitching' frame."""
    import random

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
