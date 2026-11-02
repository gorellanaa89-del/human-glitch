"""Recurring characters drawn in code, so they look identical in every scene and every video.

Each human character is a flat bust (head and shoulders) built from simple shapes; what makes
them recognizable is a fixed palette plus one or two signature traits (Sarah's glasses and bob).
GLITCH is the channel's own character: a little CRT terminal with a pixel face.
"""
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter

from .config import CYAN, GREEN, MAGENTA

SS = 3  # supersampling factor for smooth edges
INK = (8, 10, 14)
BASE_W, BASE_H = 600, 900


@dataclass(frozen=True)
class Person:
    name: str
    skin: tuple
    hair: tuple
    top: tuple
    jacket: tuple
    hair_style: str = "bob"  # bob | short
    glasses: bool = False


CAST = {
    "sarah": Person("Sarah", skin=(214, 160, 128), hair=(58, 38, 32), top=(236, 240, 244),
                    jacket=(22, 96, 86), hair_style="bob", glasses=True),
    "boss": Person("The boss", skin=(176, 124, 96), hair=(70, 70, 76), top=(200, 210, 222),
                   jacket=(40, 44, 58), hair_style="short"),
}


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
        elif expression == "happy":
            d.arc(_s(ex - 24, eye_y - 64, ex + 24, eye_y - 40), 200, 340, fill=INK, width=lw)
        else:
            d.line(_s(ex - 24, eye_y - 50, ex + 24, eye_y - 50), fill=INK, width=lw)
        if expression == "happy":
            d.arc(_s(ex - 16, eye_y - 10, ex + 16, eye_y + 14), 200, 340, fill=INK, width=lw + SS)
        else:
            d.ellipse(_s(ex - 11, eye_y - 13, ex + 11, eye_y + 13), fill=INK)
            d.ellipse(_s(ex - 3, eye_y - 8, ex + 4, eye_y - 1), fill=(255, 255, 255))
    d.arc(_s(cx - 12, eye_y + 22, cx + 12, eye_y + 44), 20, 160, fill=INK, width=lw - SS)  # nose
    my = eye_y + 82
    if expression == "happy":
        d.chord(_s(cx - 38, my - 30, cx + 38, my + 22), 0, 180, fill=INK)
    elif expression == "worried":
        d.arc(_s(cx - 26, my, cx + 26, my + 30), 200, 340, fill=INK, width=lw)
    else:
        d.line(_s(cx - 22, my + 4, cx + 22, my + 4), fill=INK, width=lw)


def _person(p: Person, expression: str) -> Image.Image:
    img = Image.new("RGBA", _s(BASE_W, BASE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ow = 6 * SS
    if p.hair_style == "bob":  # hair behind the head
        d.rounded_rectangle(_s(158, 170, 442, 540), radius=130 * SS, fill=p.hair, outline=INK, width=ow)
    # body: jacket with a lighter top showing in a V
    d.rounded_rectangle(_s(90, 560, 510, 1010), radius=150 * SS, fill=p.jacket, outline=INK, width=ow)
    d.polygon(_s(236, 568, 364, 568, 300, 730), fill=p.top, outline=INK)
    d.rectangle(_s(262, 450, 338, 580), fill=p.skin)
    d.line(_s(262, 450, 262, 570), fill=INK, width=ow)
    d.line(_s(338, 450, 338, 570), fill=INK, width=ow)
    # head and ears
    for ex in (184, 416):
        d.ellipse(_s(ex - 22, 300, ex + 22, 360), fill=p.skin, outline=INK, width=ow)
    d.ellipse(_s(186, 180, 414, 470), fill=p.skin, outline=INK, width=ow)
    # hair on top
    if p.hair_style == "bob":
        d.pieslice(_s(176, 160, 424, 380), 180, 360, fill=p.hair, outline=INK, width=ow)
        d.polygon(_s(178, 270, 300, 270, 196, 330), fill=p.hair)  # side-swept fringe
    else:
        d.rounded_rectangle(_s(180, 172, 420, 300), radius=90 * SS, fill=p.hair, outline=INK, width=ow)
        d.ellipse(_s(194, 232, 406, 330), fill=p.skin)  # hairline
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
    d.line(_s(300, 150, 300, 230), fill=GREEN, width=7 * SS)
    d.ellipse(_s(282, 120, 318, 156), fill=MAGENTA)
    # body and legs
    d.rounded_rectangle(_s(220, 600, 380, 780), radius=36 * SS, fill=(20, 30, 36), outline=GREEN, width=7 * SS)
    for lx in (255, 345):
        d.line(_s(lx, 780, lx, 850), fill=GREEN, width=9 * SS)
        d.line(_s(lx - 20, 850, lx + 20, 850), fill=GREEN, width=9 * SS)
    arm_up = expression == "happy"
    d.line(_s(220, 650, 150, 560 if arm_up else 720), fill=GREEN, width=9 * SS)
    d.line(_s(380, 650, 450, 560 if arm_up else 720), fill=GREEN, width=9 * SS)
    # monitor head with a screen
    d.rounded_rectangle(_s(120, 220, 480, 560), radius=60 * SS, fill=(26, 36, 42), outline=GREEN, width=8 * SS)
    d.rounded_rectangle(_s(160, 260, 440, 520), radius=34 * SS, fill=(6, 18, 14))
    for y in range(266, 516, 10):  # scanlines
        d.line(_s(166, y, 434, y), fill=(10, 30, 22), width=SS * 2)
    px = 22
    if expression == "happy":
        for ex in (236, 364):
            d.arc(_s(ex - 34, 330, ex + 34, 390), 200, 340, fill=GREEN, width=12 * SS)
    elif expression == "worried":
        for ex in (236, 364):
            d.rectangle(_s(ex - px, 340, ex + px, 384), fill=GREEN)
        d.line(_s(200, 330, 262, 314), fill=GREEN, width=8 * SS)
        d.line(_s(400, 330, 338, 314), fill=GREEN, width=8 * SS)
    else:
        for ex in (236, 364):
            d.rectangle(_s(ex - px, 330, ex + px, 384), fill=GREEN)
    if expression == "worried":
        for k, x in enumerate(range(250, 352, 17)):
            y = 456 + (8 if k % 2 else 0)
            d.rectangle(_s(x, y, x + 12, y + 12), fill=GREEN)
    else:  # pixel smile
        for x, y in ((240, 432), (258, 450), (282, 460), (306, 460), (330, 450), (348, 432)):
            d.rectangle(_s(x, y, x + 14, y + 14), fill=GREEN)
    return img


def _finish(img: Image.Image, height: int, glow: bool = True) -> Image.Image:
    """Downsample, add a soft green rim glow and a subtle magenta/cyan split."""
    w = int(height * BASE_W / BASE_H)
    img = img.resize((w, height), Image.LANCZOS)
    pad = height // 10
    out = Image.new("RGBA", (w + 2 * pad, height + 2 * pad), (0, 0, 0, 0))
    alpha = img.getchannel("A")
    if glow:
        g = Image.new("RGBA", img.size, GREEN + (0,))
        g.putalpha(alpha.point(lambda a: int(a * 0.55)))
        out.alpha_composite(g.filter(ImageFilter.GaussianBlur(height // 40)), (pad, pad))
        shift = max(2, height // 220)
        for col, dx in ((MAGENTA, -shift), (CYAN, shift)):
            ghost = Image.new("RGBA", img.size, col + (0,))
            ghost.putalpha(alpha.point(lambda a: int(a * 0.5)))
            out.alpha_composite(ghost, (pad + dx, pad))
    out.alpha_composite(img, (pad, pad))
    return out


def draw(name: str, expression: str = "neutral", height: int = 700) -> Image.Image:
    """Return the character as a transparent RGBA image, `height` pixels tall (plus glow padding)."""
    raw = _glitch(expression) if name == "glitch" else _person(CAST[name], expression)
    return _finish(raw, height)


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
