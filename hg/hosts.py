"""Hosts in the hand-drawn style of sketch.py. Round 1 (debug, cortex, neuro) was rejected; round 2 adds axon, puff and hoot.

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
        side = -1 if gx < 300 else 1
        p.shape(ellipse_pts(gx, 550, 40, 52, n=36), WHITE, 5)
        pr = 9 if expr != "surprised" else 6
        py = 570 if expr in ("worried", "sad") else 562
        p.d.ellipse([(gx - pr) * SS, (py - pr) * SS, (gx + pr) * SS, (py + pr) * SS], fill=INK)
        if expr == "smug":  # heavy lids
            lid = ellipse_pts(gx, 550, 47, 59, math.pi, 2 * math.pi, 30) + [(gx + 47, 556), (gx - 47, 556)]
            p.d.polygon([(x * SS, y * SS) for x, y in lid], fill=BRAIN)
            p.line([(gx - 38, 556), (gx + 38, 554)], 5)
        if expr in ("worried", "sad"):
            p.line([(gx - side * 30, 480), (gx + side * 22, 494)], 5)
        if expr == "sad":
            p.shape(bez((gx - side * 20, 610), (gx - side * 30, 640), (gx - side * 8, 648), (gx - side * 20, 610)), (150, 210, 255), 3)
    my = 630
    if expr == "happy":
        p.shape([(270, my - 6), (330, my - 6)] + bez((330, my - 6), (328, my + 26), (272, my + 26), (270, my - 6))[1:], (40, 26, 30), 4.5)
    elif expr == "surprised":
        p.shape(ellipse_pts(300, my + 4, 12, 16, n=24), (40, 26, 30), 4.5)
    elif expr == "worried":
        p.line([(280, my + 6), (290, my), (300, my + 6), (310, my), (320, my + 6)], 4.5)
    elif expr == "smug":
        p.line(bez((278, my + 4), (296, my + 10), (312, my + 6), (326, my - 8)), 5)
    elif expr == "sad":
        p.line(ellipse_pts(300, my + 14, 18, 12, math.pi * 1.15, math.pi * 1.85, 16), 5)
    else:
        p.line(ellipse_pts(300, my - 8, 16, 10, math.pi * 0.2, math.pi * 0.8, 16), 5)
    return img


HOSTS = {"debug": ("Dr. Debug", _debug), "cortex": ("Cortex", _cortex), "neuro": ("Neuro", _neuro)}


def draw(name: str, expression: str = "happy", height: int = 700) -> Image.Image:
    img = HOSTS[name][1](expression).crop((0, 0, W0 * SS, (860 if name == "neuro" else 690) * SS))
    return img.resize((int(height * img.width / img.height), height), Image.LANCZOS)


# ---------- second round of host ideas ----------

def _face_simple(p: Pencil, eyes, r, my, expr, lid_color):
    """Big round eyes + small mouth, shared by the creature hosts."""
    for gx, gy in eyes:
        if expr == "happy":
            p.line(ellipse_pts(gx, gy + 12, r[0] * 0.75, r[1] * 0.45, math.pi * 1.1, math.pi * 1.9, 20), 6)
            continue
        p.shape(ellipse_pts(gx, gy, r[0], r[1], n=36), WHITE, 5)
        pr = 9 if expr != "surprised" else 6
        p.d.ellipse([(gx - pr) * SS, (gy + 10 - pr) * SS, (gx + pr) * SS, (gy + 10 + pr) * SS], fill=INK)
        p.d.ellipse([(gx - 5) * SS, (gy + 2) * SS, (gx - 1) * SS, (gy + 6) * SS], fill=WHITE)
        if expr == "smug":
            lid = ellipse_pts(gx, gy, r[0] + 7, r[1] + 7, math.pi, 2 * math.pi, 30) + [(gx + r[0] + 7, gy + 4), (gx - r[0] - 7, gy + 4)]
            p.d.polygon([(x * SS, y * SS) for x, y in lid], fill=lid_color)
            p.line([(gx - r[0] + 4, gy + 4), (gx + r[0] - 4, gy + 2)], 5)
    if my is None:
        return
    if expr == "happy":
        p.shape([(272, my - 6), (328, my - 6)] + bez((328, my - 6), (326, my + 24), (274, my + 24), (272, my - 6))[1:], (40, 26, 30), 4.5)
    elif expr == "surprised":
        p.shape(ellipse_pts(300, my + 4, 11, 15, n=24), (40, 26, 30), 4.5)
    elif expr == "worried":
        p.line([(282, my + 6), (291, my), (300, my + 6), (309, my), (318, my + 6)], 4.5)
    elif expr == "smug":
        p.line(bez((280, my + 4), (296, my + 10), (312, my + 6), (324, my - 8)), 5)
    else:
        p.line(ellipse_pts(300, my - 8, 15, 10, math.pi * 0.2, math.pi * 0.8, 16), 5)


def _axon(expr: str) -> Image.Image:
    """Axon: a neuron. Dendrites for hair, a myelinated tail, sparks when it has an idea."""
    img = Image.new("RGBA", (W0 * SS, H0 * SS), (0, 0, 0, 0))
    p = Pencil(img, 31)
    body = GLITCH_BLUE
    # tail (axon) with myelin segments and terminals
    tail = bez((330, 600), (420, 700), (300, 780), (400, 840), 40)
    p.line(tail, 9, shade(body, 0.6))
    for k in (8, 18, 28):
        x, y = tail[k]
        p.shape(ellipse_pts(x, y, 20, 13, n=20), shade(body, 1.2), 3.5)
    ex, ey = tail[-1]
    for dx, dy in ((30, -10), (34, 14), (12, 30)):
        p.line([(ex, ey), (ex + dx, ey + dy)], 4)
        p.shape(ellipse_pts(ex + dx, ey + dy, 7, 7, n=12), body, 3)
    # dendrites
    for ang, ln in ((-150, 150), (-120, 175), (-90, 165), (-60, 175), (-30, 150), (-175, 120), (-5, 120)):
        t = math.radians(ang)
        x0, y0 = 300 + 140 * math.cos(t), 470 + 130 * math.sin(t)
        x1, y1 = 300 + (140 + ln) * math.cos(t), 470 + (130 + ln) * math.sin(t)
        mid = ((x0 + x1) / 2 + 18 * math.sin(t * 3), (y0 + y1) / 2)
        p.line(bez((x0, y0), mid, mid, (x1, y1), 14), 7, shade(body, 0.75))
        for s in (-1, 1):  # small forks
            fx, fy = x1 + s * 22 * math.cos(t + 1.2), y1 + 22 * math.sin(t + s * 0.6) - 10
            p.line([(x1, y1), (fx, fy)], 4.5, shade(body, 0.75))
            p.shape(ellipse_pts(fx, fy, 8, 8, n=12), body, 3)
    if expr in ("happy", "surprised"):  # spark of an idea
        sx, sy = 300 + 315 * math.cos(math.radians(-90)), 470 + 295 * math.sin(math.radians(-90))
        p.shape([(sx - 10, sy - 60), (sx + 18, sy - 60), (sx + 2, sy - 34), (sx + 22, sy - 34), (sx - 14, sy + 6), (sx - 2, sy - 24), (sx - 20, sy - 24)],
                (255, 222, 90), 3.5)
    # arms and soma
    for side in (-1, 1):
        p.line(bez((300 + side * 140, 520), (300 + side * 190, 540), (300 + side * 200, 580), (300 + side * 186, 610)), 6)
    p.shape(ellipse_pts(300, 470, 150, 140, n=90), body, 6)
    _face_simple(p, ((240, 450), (360, 450)), (44, 56), 540, expr, body)
    return img


def _puff(expr: str) -> Image.Image:
    """Puff: a living thought bubble that floats above people's heads."""
    img = Image.new("RGBA", (W0 * SS, H0 * SS), (0, 0, 0, 0))
    p = Pencil(img, 32)
    col = (236, 246, 255)
    for x, y, r in ((250, 760, 34), (210, 830, 20)):  # thought-bubble tail
        p.shape(ellipse_pts(x, y, r, r * 0.85, n=24), col, 4.5)
    lobes = [(200, 470, 90), (300, 420, 110), (410, 470, 92), (440, 570, 80), (360, 640, 90), (240, 640, 92), (160, 570, 80)]
    for x, y, r in lobes:
        p.shape(ellipse_pts(x, y, r, r * 0.9, n=40), col, 5.5)
    p.d.ellipse([170 * SS, 430 * SS, 430 * SS, 680 * SS], fill=col)  # fill the centre, hide inner strokes
    for side in (-1, 1):  # blush in brand blue
        p.d.ellipse([(300 + side * 110 - 24) * SS, 600 * SS, (300 + side * 110 + 24) * SS, 622 * SS], fill=(140, 210, 255))
    _face_simple(p, ((245, 540), (355, 540)), (40, 52), 620, expr, col)
    p.line(bez((396, 400), (420, 370), (450, 370), (470, 392)), 4, GLITCH_BLUE)  # little shine
    return img


def _owl(expr: str) -> Image.Image:
    """Dr. Hoot: an owl psychologist with a notebook, glasses on the beak."""
    img = Image.new("RGBA", (W0 * SS, H0 * SS), (0, 0, 0, 0))
    p = Pencil(img, 33)
    body, belly = GLITCH_BLUE, (214, 238, 255)
    for side in (-1, 1):  # ear tufts and feet
        p.shape([(300 + side * 110, 330), (300 + side * 170, 250), (300 + side * 150, 360)], shade(body, 0.85), 5)
        p.shape(ellipse_pts(300 + side * 60, 812, 34, 16, n=20), (250, 170, 70), 4)
    p.shape(ellipse_pts(300, 560, 190, 250, n=100), body, 6)
    p.shape(ellipse_pts(300, 650, 120, 150, n=60), belly, 4)
    for row, y in enumerate((600, 650, 700, 750)):  # feather marks
        for k in range(3 - row % 2):
            x = 250 + k * 50 + (25 if row % 2 else 0)
            p.line(ellipse_pts(x, y, 14, 9, math.pi * 0.15, math.pi * 0.85, 8), 3.5, shade(body, 0.7))
    for gx in (232, 368):  # facial discs
        p.shape(ellipse_pts(gx, 440, 78, 74, n=40), shade(body, 1.18), 4)
    _face_simple(p, ((232, 440), (368, 440)), (52, 54), None, expr, shade(body, 1.18))
    p.shape([(280, 500), (320, 500), (300, 540)], (250, 170, 70), 4)  # beak
    for gx in (262, 338):  # small half-moon glasses on the beak
        p.line(ellipse_pts(gx, 512, 26, 18, 0, math.pi, 16), 4.5)
    p.line([(288, 512), (312, 512)], 4)
    # wing holding a notebook and pen
    p.shape([(390, 560), (480, 540), (500, 680), (410, 700)], (250, 246, 230), 4.5)
    for y in (590, 615, 640, 665):
        p.line([(420, y), (480, y - 4)], 3, (120, 140, 180))
    p.line([(510, 520), (470, 640)], 6, (230, 70, 90))
    p.shape(ellipse_pts(150, 620, 40, 80, n=30), shade(body, 0.85), 4.5)  # other wing
    return img


HOSTS.update({"axon": ("Axon", _axon), "puff": ("Puff", _puff), "hoot": ("Dr. Hoot", _owl)})


def draw(name: str, expression: str = "happy", height: int = 700) -> Image.Image:  # noqa: F811 (extends the first draw)
    bottom = 690 if name in ("debug", "cortex") else 870
    img = HOSTS[name][1](expression).crop((0, 0, W0 * SS, bottom * SS))
    return img.resize((int(height * img.width / img.height), height), Image.LANCZOS)
