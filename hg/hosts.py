"""Candidate hosts for the channel, in the hand-drawn style of sketch.py.

- debug:  Dr. Debug, a scientist in a lab coat who inspects minds with a magnifying glass.
- cortex: Cortex, a scientist whose head is a brain.
- neuro:  Neuro, a small brain mascot with lab goggles.
All use the Potencia People light blue as their signature colour.
"""
import math

from PIL import Image

from .sketch import (EYES, EYE_R, GLITCH_BLUE, H0, HEAD, INK, SS, W0, WHITE, Bean, Pencil, _arm, _bean, _brows,
                     _eyes, _mouth, _torso, bez, ellipse_pts, shade)

COAT = (246, 248, 252)
BRAIN = (247, 160, 178)


def _lab_coat(p: Pencil, shirt):
    """White coat panels and sleeves over the bean body, shirt and tie visible in the middle."""
    for side in (-1, 1):
        s = side
        panel = [(300 - s * 64, 396), (300 - s * 6, 486), (300 - s * 14, 700), (300 - s * 128, 700), (300 - s * 128, 450)]
        p.shape(panel, COAT, 5)
        lapel = [(300 - s * 64, 396), (300 - s * 8, 486), (300 - s * 50, 470)]
        p.shape(lapel, shade(COAT, 0.9), 4)
        p.shape(_arm(side), COAT, 5)
        p.shape(ellipse_pts(300 + side * 128, 618, 26, 24, n=28), shirt, 5)
    p.shape([(372, 520), (410, 520), (410, 566), (372, 566)], shade(COAT, 0.94), 3.5)  # pocket
    for x, c in ((380, (60, 90, 200)), (392, (230, 70, 90))):
        p.line([(x, 506), (x, 528)], 5, c)
    p.shape([(290, 430), (310, 430), (316, 520), (300, 544), (284, 520)], (40, 60, 110), 4)  # tie


def _magnifier(p: Pencil, hand=(428, 618)):
    hx, hy = hand
    p.line([(hx + 4, hy - 10), (hx + 44, hy - 100)], 12, (90, 60, 40))
    lens = (hx + 76, hy - 170)
    p.d.ellipse([(lens[0] - 66) * SS, (lens[1] - 66) * SS, (lens[0] + 66) * SS, (lens[1] + 66) * SS], fill=(210, 240, 255, 150))
    p.line(ellipse_pts(*lens, 66, 66, n=48), 9)
    p.line(ellipse_pts(lens[0] - 16, lens[1] - 16, 34, 34, math.pi * 1.1, math.pi * 1.5, 10), 5, WHITE)


def _debug(expr: str) -> Image.Image:
    b = Bean("Dr. Debug", "Host", GLITCH_BLUE, seed=21)

    def head(p: Pencil):
        cx, cy, rx, ry = HEAD
        _lab_coat(p, GLITCH_BLUE)
        hair = (70, 74, 90)
        for a in range(-200, 25, 22):  # wild scientist hair behind the head
            t = math.radians(a)
            x, y = cx + 150 * math.cos(t), cy - 10 + 140 * math.sin(t)
            p.shape(ellipse_pts(x, y, 46, 40, n=24), hair, 4.5)
        for side in (-1, 1):
            p.shape(ellipse_pts(300 + side * 146, 280, 18, 26, n=24), GLITCH_BLUE, 4.5)
        p.shape(ellipse_pts(cx, cy, rx, ry, n=90), GLITCH_BLUE, 6)
        _brows(p, expr)
        _eyes(p, expr, GLITCH_BLUE)
        _mouth(p, expr)
        p.shape(bez((262, 344), (280, 330), (320, 330), (338, 344)) + [(300, 352)], (70, 74, 90), 3.5)  # moustache
        for ex, ey in EYES:  # round glasses
            p.line(ellipse_pts(ex, ey, EYE_R[0] + 12, EYE_R[1] + 10), 5)
        p.line(bez((286, 262), (294, 248), (306, 248), (314, 262)), 5)
        _magnifier(p)

    return _bean(b, expr, head=head)


def _brain_outline(cx, cy, rx, ry, n=140):
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        top = max(0.0, -math.sin(t))
        bump = 1 + 0.045 * top * math.sin(11 * t) + 0.02 * math.sin(5 * t)
        pts.append((cx + rx * math.cos(t) * bump, cy + ry * math.sin(t) * bump))
    return pts


def _cortex(expr: str) -> Image.Image:
    b = Bean("Cortex", "Host", GLITCH_BLUE, seed=22)

    def head(p: Pencil):
        cx, cy, rx, ry = HEAD
        _lab_coat(p, GLITCH_BLUE)
        p.shape(_brain_outline(cx, cy - 4, rx + 8, ry + 6), BRAIN, 6)
        fold = shade(BRAIN, 0.7)
        p.line(bez((300, 120), (290, 150), (312, 170), (300, 200)), 4.5, fold)  # central fissure
        for pts in ((180, 190, 210, 150, 250, 180), (230, 140, 260, 170, 270, 130), (330, 135, 350, 175, 380, 140),
                    (360, 190, 400, 160, 420, 200), (170, 240, 190, 210, 215, 230), (390, 230, 410, 205, 432, 240)):
            a, b_, c = (pts[0], pts[1]), (pts[2], pts[3]), (pts[4], pts[5])
            p.line(bez(a, b_, b_, c, 12), 4, fold)
        _brows(p, expr)
        _eyes(p, expr, BRAIN)
        _mouth(p, expr)

    return _bean(b, expr, head=head)


def _neuro(expr: str) -> Image.Image:
    img = Image.new("RGBA", (W0 * SS, H0 * SS), (0, 0, 0, 0))
    p = Pencil(img, 23)
    for side in (-1, 1):  # little legs and shoes
        p.line([(300 + side * 60, 700), (300 + side * 64, 800)], 7)
        p.shape(ellipse_pts(300 + side * 78, 810, 36, 18, n=24), GLITCH_BLUE, 4.5)
    for side in (-1, 1):  # arms
        p.line(bez((300 + side * 190, 560), (300 + side * 240, 590), (300 + side * 250, 640), (300 + side * 230, 670)), 6)
        p.shape(ellipse_pts(300 + side * 230, 676, 20, 18, n=20), BRAIN, 4)
    p.shape(_brain_outline(300, 520, 210, 190), BRAIN, 6)
    fold = shade(BRAIN, 0.7)
    p.line(bez((300, 340), (286, 380), (316, 410), (300, 440)), 4.5, fold)
    for a, b_, c in (((160, 430), (190, 380), (230, 420)), ((230, 370), (262, 400), (272, 350)),
                     ((330, 360), (350, 400), (382, 362)), ((370, 420), (410, 390), (440, 430))):
        p.line(bez(a, b_, b_, c, 12), 4, fold)
    # goggles pushed up on the forehead
    p.line(bez((110, 470), (200, 430), (400, 430), (490, 470)), 9, GLITCH_BLUE)
    for gx in (250, 350):
        p.shape(ellipse_pts(gx, 440, 40, 32, n=30), (200, 236, 255), 5)
    # face
    for gx in (240, 360):
        if expr == "happy":
            p.line(ellipse_pts(gx, 560, 30, 22, math.pi * 1.1, math.pi * 1.9, 20), 6)
            continue
        p.shape(ellipse_pts(gx, 550, 40, 52, n=36), WHITE, 5)
        pr = 9 if expr != "surprised" else 6
        p.d.ellipse([(gx - pr) * SS, (562 - pr) * SS, (gx + pr) * SS, (562 + pr) * SS], fill=INK)
    my = 630
    if expr == "happy":
        p.shape([(270, my - 6), (330, my - 6)] + bez((330, my - 6), (328, my + 26), (272, my + 26), (270, my - 6))[1:], (40, 26, 30), 4.5)
    elif expr == "surprised":
        p.shape(ellipse_pts(300, my + 4, 12, 16, n=24), (40, 26, 30), 4.5)
    else:
        p.line(ellipse_pts(300, my - 8, 16, 10, math.pi * 0.2, math.pi * 0.8, 16), 5)
    return img


HOSTS = {"debug": ("Dr. Debug", _debug), "cortex": ("Cortex", _cortex), "neuro": ("Neuro", _neuro)}


def draw(name: str, expression: str = "happy", height: int = 700) -> Image.Image:
    img = HOSTS[name][1](expression).crop((0, 0, W0 * SS, (860 if name == "neuro" else 690) * SS))
    return img.resize((int(height * img.width / img.height), height), Image.LANCZOS)
