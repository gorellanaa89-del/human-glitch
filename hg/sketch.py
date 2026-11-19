"""Hand-drawn cast for Human Glitch.

Simple "bean" people with round heads, huge eyes and one solid colour each, drawn with wobbly
pencil-like outlines so they look sketched by hand. Plus GLITCH (a bean with a screen for a head)
and the bugs, the little creatures that personify each mental glitch.
Everything is generated from fixed rules and seeds, so each character looks the same in every video.
"""
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 2
W0, H0 = 600, 900
INK = (34, 30, 38)
WHITE = (255, 255, 255)
HAND_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "PatrickHand-Regular.ttf"
GLITCH_BLUE = (90, 183, 230)  # Potencia People light blue #5AB7E6
EXPRESSIONS = ("neutral", "happy", "worried", "surprised", "smug", "sad")
_BLINK = False  # set by draw(blink=True): eyes drawn closed, everything else unchanged


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


# ---------- pencil drawing ----------

class Pencil:
    def __init__(self, img: Image.Image, seed: int):
        self.img, self.d = img, ImageDraw.Draw(img)
        self.rnd = random.Random(seed)

    def _noise(self):
        waves = [(self.rnd.uniform(0.01, 0.03), self.rnd.uniform(0, 6.3), self.rnd.uniform(0.5, 1.0)) for _ in range(3)]
        return lambda s: sum(a * math.sin(f * s + p) for f, p, a in waves) / 1.6

    def line(self, pts, width=5.0, color=INK, closed=False, wobble=1.6):
        """Wobbly stroke through pts (base units). Closed shapes overshoot a little at the join."""
        pts = list(pts)
        if closed:
            k = max(2, len(pts) // 25)
            pts = pts + pts[:k]
        # resample
        res, acc = [pts[0]], 0.0
        for a, b in zip(pts, pts[1:]):
            seg = math.dist(a, b)
            n = max(1, int(seg / 5))
            for i in range(1, n + 1):
                res.append((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n))
        off, wid = self._noise(), self._noise()
        out, s = [], 0.0
        for i, p in enumerate(res):
            q = res[min(i + 1, len(res) - 1)]
            r = res[max(i - 1, 0)]
            nx, ny = -(q[1] - r[1]), q[0] - r[0]
            ln = math.hypot(nx, ny) or 1
            if i:
                s += math.dist(res[i - 1], p)
            o = off(s) * wobble
            out.append((p[0] + nx / ln * o, p[1] + ny / ln * o, width * (0.85 + 0.3 * wid(s))))
        # taper both ends
        n = len(out)
        for i, (x, y, w) in enumerate(out):
            t = min(i, n - 1 - i) / max(1, min(8, n // 4))
            out[i] = (x, y, w * (0.45 + 0.55 * min(1.0, t)))
        for (x0, y0, w0), (x1, y1, w1) in zip(out, out[1:]):
            w = (w0 + w1) / 2 * SS
            self.d.line([(x0 * SS, y0 * SS), (x1 * SS, y1 * SS)], fill=color, width=max(1, int(w)))
            r = w / 2
            self.d.ellipse([x1 * SS - r, y1 * SS - r, x1 * SS + r, y1 * SS + r], fill=color)

    def shape(self, pts, fill, width=5.0, color=INK, wobble=1.6):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill)
        self.line(pts, width, color, closed=True, wobble=wobble)

    def hatch(self, x0, y0, x1, y1, n=4, width=2.5, color=INK):
        for i in range(n):
            t = i / max(1, n - 1)
            x = x0 + (x1 - x0) * t
            self.line([(x, y0), (x + 12, y1)], width, color, wobble=0.6)


def ellipse_pts(cx, cy, rx, ry, a0=0.0, a1=2 * math.pi, n=64):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


# ---------- cast ----------

@dataclass(frozen=True)
class Bean:
    name: str
    role: str
    color: tuple
    hair: str = "none"            # none | long | sidepart | bun | crop | bob
    extras: tuple = field(default_factory=tuple)  # glasses, tie, badge, earrings, pearls
    default: str = "neutral"
    seed: int = 1
    hair_color: tuple | None = None  # defaults to a darker shade of the body colour


CAST = {
    "sarah": Bean("Sarah Collins", "Senior Analyst", (64, 190, 170), "long", ("glasses",), "worried", 11),
    "richard": Bean("Richard Hale", "Operations Director", (245, 150, 60), "sidepart", ("tie",), "smug", 12),
    "elena": Bean("Elena Ruiz", "Head of People", (236, 104, 140), "bun", ("earrings",), "happy", 13),
    "daniel": Bean("Daniel Brooks", "Product Associate", (250, 206, 70), "crop", ("badge",), "surprised", 14),
    "margaret": Bean("Margaret Lane", "Finance Manager", (170, 140, 230), "bob", ("glasses", "pearls"), "smug", 15, (226, 224, 232)),
}

# Scientists and volunteers for the moments a video talks about a study (2026-11-09). Not real
# likenesses: a generic researcher in a lab coat, and plain extras for the people in an experiment.
CAST.update({
    "scientist": Bean("The researcher", "Psychologist", (226, 190, 160), "sidepart", ("glasses", "labcoat"), "neutral", 21, (90, 80, 80)),
    "scientist2": Bean("The researcher", "Neuroscientist", (200, 160, 130), "bun", ("glasses", "labcoat"), "happy", 22, (60, 50, 50)),
    "volunteer": Bean("A volunteer", "Student", (120, 170, 220), "crop", (), "worried", 23, (90, 70, 60)),
    "extra1": Bean("A student", "Actor", (150, 150, 160), "sidepart", (), "neutral", 24, (80, 80, 90)),
    "extra2": Bean("A student", "Actor", (170, 160, 140), "bob", (), "neutral", 25, (90, 70, 60)),
    "extra3": Bean("A student", "Actor", (140, 160, 150), "crop", (), "smug", 26, (70, 70, 70)),
})
# Family of the cast (2026-11-19, episode 6): Sarah's mother and Daniel's grandfather, for scenes outside the office.
CAST.update({
    "mom": Bean("Linda Collins", "Sarah's mom", (110, 200, 220), "bob", ("earrings", "pearls"), "smug", 31, (205, 205, 210)),
    "grandpa": Bean("Walter Brooks", "Daniel's grandpa", (150, 176, 112), "none", ("glasses", "tufts", "mustache"), "smug", 32, (215, 215, 220)),
})
COAT = (246, 246, 242)

HEAD = (300, 250, 150, 138)  # cx, cy, rx, ry
EYES = ((232, 262), (368, 262))
EYE_R = (60, 80)


def _torso():
    return (bez((236, 396), (200, 410), (176, 440), (172, 520)) + bez((172, 520), (168, 640), (176, 800), (182, 900))[1:]
            + [(418, 900)] + bez((418, 900), (424, 800), (432, 640), (428, 520))[1:]
            + bez((428, 520), (424, 440), (400, 410), (364, 396))[1:])


def _arm(side):
    s = side
    x = 300 + s * 112
    outer = bez((x, 430), (x + s * 40, 470), (x + s * 46, 540), (x + s * 34, 600))
    inner = bez((x - s * 8, 612), (x - s * 4, 560), (x - s * 10, 500), (x - s * 24, 470))
    return outer + inner


# Arm poses: (upper arm, forearm) angles in degrees from hanging straight down, positive = away from the body.
UPPER, FORE, ARM_R = 95, 90, 19
REST = (16, -4)
POSES = {
    "rest": (REST, REST),
    "wave": (REST, (150, 172)),         # second entry is the arm on the right of the picture
    "point": (REST, (82, 92)),
    "shrug": ((38, 105), (38, 105)),
    "cheer": ((150, 168), (150, 168)),
    "panic": ((145, 185), (145, 185)),  # hands on the head
    "explain": (REST, (40, 75)),
    "clasp": ((-12, -45), (-12, -45)),  # hands together in front, nervous
    "stop": ((60, 160), REST),          # palm up: "wait"
}


def _capsule(a, b, r, n=10):
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    pts = []
    for (cx, cy), start in ((b, ang - math.pi / 2), (a, ang + math.pi / 2)):
        for k in range(n + 1):
            t = start + math.pi * k / n
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def _limb(side, upper, fore):
    """Shoulder, elbow and hand points for one arm (side -1 = picture left)."""
    sh = (300 + side * 104, 450)
    u, f = math.radians(upper), math.radians(fore)
    el = (sh[0] + side * UPPER * math.sin(u), sh[1] + UPPER * math.cos(u))
    hd = (el[0] + side * FORE * math.sin(f), el[1] + FORE * math.cos(f))
    return sh, el, hd


def _hose(sh, el, hd, r0=31, r1=25, n=26):
    """Rubber-hose arm: a soft curve from shoulder to hand (bent towards the elbow), tapering, round ends."""
    bp = lambda t: tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t * t * c for a, b, c in zip(sh, el, hd))
    left, right = [], []
    for k in range(n + 1):
        t = k / n
        x, y = bp(t)
        dx = 2 * (1 - t) * (el[0] - sh[0]) + 2 * t * (hd[0] - el[0])
        dy = 2 * (1 - t) * (el[1] - sh[1]) + 2 * t * (hd[1] - el[1])
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        r = r0 + (r1 - r0) * t
        left.append((x + nx * r, y + ny * r))
        right.append((x - nx * r, y - ny * r))
    def cap(c, r, a0):  # half circle, turning the same way at both ends so the outline never crosses
        return [(c[0] + r * math.cos(a0 - math.pi * k / 10), c[1] + r * math.sin(a0 - math.pi * k / 10)) for k in range(1, 10)]
    a_end = math.atan2(left[-1][1] - hd[1], left[-1][0] - hd[0])
    a_start = math.atan2(right[0][1] - sh[1], right[0][0] - sh[0])
    return left + cap(hd, r1, a_end) + right[::-1] + cap(sh, r0, a_start)


def _arms(p: Pencil, col, arms, sleeve=None):
    for side, (upper, fore) in zip((-1, 1), arms):
        sh, el, hd = _limb(side, upper, fore)
        el = (el[0] + (el[0] - (sh[0] + hd[0]) / 2) * 0.3, el[1] + (el[1] - (sh[1] + hd[1]) / 2) * 0.3)  # keep the bend visible
        p.shape(_hose(sh, el, hd), sleeve or shade(col, 0.93), 5)
        p.shape(ellipse_pts(hd[0], hd[1], 27, 25, n=28), col, 5)


def _eyes(p: Pencil, expr, col):
    (lx, ly), (rx, ry) = EYES
    ex, ey = EYE_R
    if _BLINK and expr != "happy":
        for cx, cy in EYES:
            p.line(ellipse_pts(cx, cy + 20, 44, 18, math.pi * 0.1, math.pi * 0.9, 20), 6)
        return
    for i, (cx, cy) in enumerate(EYES):
        side = -1 if i == 0 else 1
        if expr == "happy":
            p.line(ellipse_pts(cx, cy + 18, 38, 30, math.pi * 1.1, math.pi * 1.9), 7)
            continue
        p.shape(ellipse_pts(cx, cy, ex, ey), WHITE, 5.5)
        if expr == "surprised":
            pr, dx, dy = (7, 9), 0, 0
        elif expr in ("worried", "sad"):
            pr, dx, dy = (9, 14), -side * 14, 46
        elif expr == "smug":
            pr, dx, dy = (10, 13), -side * 6, 34
        else:
            pr, dx, dy = (10, 15), -side * 16, 36
        px, py = cx + dx, cy + dy
        p.d.ellipse([(px - pr[0]) * SS, (py - pr[1]) * SS, (px + pr[0]) * SS, (py + pr[1]) * SS], fill=INK)
        p.d.ellipse([(px - 4) * SS, (py - pr[1] + 2) * SS, (px) * SS, (py - pr[1] + 7) * SS], fill=WHITE)
        if expr == "smug":  # heavy lids
            lid = ellipse_pts(cx, cy, ex + 7, ey + 7, math.pi, 2 * math.pi) + [(cx + ex + 7, cy + 6), (cx - ex - 7, cy + 6)]
            p.d.polygon([(x * SS, y * SS) for x, y in lid], fill=col)
            p.line([(cx - ex + 4, cy + 6), (cx + ex - 4, cy + 4)], 6)
        if expr == "sad":
            p.d.polygon([(x * SS, y * SS) for x, y in bez((cx - side * 30, cy + 70), (cx - side * 40, cy + 100),
                                                         (cx - side * 20, cy + 110), (cx - side * 30, cy + 70))],
                        fill=(150, 210, 255))


def _brows(p: Pencil, expr):
    for i, (cx, cy) in enumerate(EYES):
        side = -1 if i == 0 else 1
        y = cy - EYE_R[1] - 14
        if expr in ("worried", "sad"):
            p.line([(cx - side * 30, y - 10), (cx + side * 22, y + 8)], 5)
        elif expr == "surprised":
            p.line(ellipse_pts(cx, y + 6, 30, 16, math.pi * 1.15, math.pi * 1.85, 16), 5)
        elif expr == "smug" and side == 1:
            p.line(ellipse_pts(cx, y + 2, 30, 14, math.pi * 1.15, math.pi * 1.85, 16), 5)
        elif expr == "happy":
            p.line(ellipse_pts(cx, y + 30, 26, 14, math.pi * 1.2, math.pi * 1.8, 16), 5)
        else:
            p.line([(cx - 22, y + 4), (cx + 22, y)], 5)


def _mouth(p: Pencil, expr):
    y = 362
    if expr == "happy":
        pts = [(268, y - 8), (332, y - 8)] + bez((332, y - 8), (330, y + 30), (270, y + 30), (268, y - 8))[1:]
        p.shape(pts, (40, 26, 30), 5)
        p.d.ellipse([(286) * SS, (y + 6) * SS, (314) * SS, (y + 22) * SS], fill=(236, 110, 120))
    elif expr == "worried":
        p.line([(282, y + 6), (292, y), (302, y + 6), (312, y), (320, y + 6)], 4.5)
    elif expr == "surprised":
        p.shape(ellipse_pts(300, y + 4, 12, 16, n=24), (40, 26, 30), 4.5)
    elif expr == "smug":
        p.line(bez((280, y + 4), (296, y + 10), (312, y + 6), (324, y - 8)), 5)
    elif expr == "sad":
        p.line(ellipse_pts(300, y + 18, 18, 12, math.pi * 1.15, math.pi * 1.85, 16), 5)
    else:
        p.line(ellipse_pts(300, y - 8, 14, 10, math.pi * 0.2, math.pi * 0.8, 16), 5)


def _hair(p: Pencil, b: Bean, front: bool):
    hc = b.hair_color or shade(b.color, 0.62)
    cx, cy, rx, ry = HEAD
    if b.hair == "long" and not front:
        p.shape(bez((158, 230), (130, 380), (150, 470), (190, 500)) + [(410, 500)] +
                bez((410, 500), (450, 470), (470, 380), (442, 230))[1:] + ellipse_pts(cx, cy, 142, 132, 0, -math.pi, 40)[::-1],
                hc, 5)
    if b.hair == "bun" and not front:
        p.shape(ellipse_pts(300, 100, 54, 46), hc, 5)
    if not front:
        return
    if b.hair == "long":
        p.shape(ellipse_pts(cx, cy, rx + 6, ry + 6, math.pi * 1.0, math.pi * 2.0, 40) +
                bez((456, 250), (420, 200), (360, 180), (330, 170)) + bez((330, 170), (280, 210), (200, 230), (144, 250)), hc, 5)
    elif b.hair == "sidepart":
        p.shape(ellipse_pts(cx, cy, rx + 4, ry + 4, math.pi * 1.04, math.pi * 1.96, 40) +
                bez((446, 200), (400, 150), (300, 150), (250, 168)) + bez((250, 168), (210, 160), (175, 178), (156, 210)), hc, 5)
        p.line(bez((250, 168), (262, 140), (300, 122), (340, 118)), 4)
    elif b.hair == "bun":
        p.shape(ellipse_pts(cx, cy, rx + 4, ry + 4, math.pi * 1.06, math.pi * 1.94, 40) +
                bez((440, 196), (390, 160), (330, 150), (300, 160)) + bez((300, 160), (270, 150), (210, 160), (160, 196)), hc, 5)
    elif b.hair == "crop":
        top = ellipse_pts(cx, cy, rx + 4, ry + 4, math.pi * 1.1, math.pi * 1.9, 40)
        zig = [(430, 170), (404, 160), (380, 172), (352, 158), (326, 170), (300, 156), (274, 170), (248, 158), (222, 172), (196, 162), (172, 172)]
        p.shape(top + zig, hc, 5)
    elif b.hair == "bob":
        p.shape(ellipse_pts(cx, cy, rx + 14, ry + 10, math.pi * 0.85, math.pi * 2.15, 50) +
                bez((450, 320), (430, 230), (400, 200), (370, 196)) + bez((370, 196), (320, 220), (240, 206), (200, 214)) +
                bez((200, 214), (170, 240), (156, 280), (150, 320)), hc, 5)


def _extras(p: Pencil, b: Bean):
    if "glasses" in b.extras:
        for cx, cy in EYES:
            p.line(ellipse_pts(cx, cy, EYE_R[0] + 12, EYE_R[1] + 10), 5, INK)
        p.line(bez((292, 250), (296, 238), (304, 238), (308, 250)), 5)
    if "tie" in b.extras:
        p.shape([(288, 410), (312, 410), (318, 520), (300, 548), (282, 520)], (60, 70, 120), 4)
    if "badge" in b.extras:
        p.line(bez((262, 400), (270, 480), (290, 520), (300, 540)), 3.5, (60, 90, 200))
        p.line(bez((338, 400), (330, 480), (310, 520), (300, 540)), 3.5, (60, 90, 200))
        p.shape([(276, 540), (324, 540), (324, 600), (276, 600)], WHITE, 4)
        p.line([(284, 560), (316, 560)], 3)
        p.line([(284, 576), (308, 576)], 3)
    if "earrings" in b.extras:
        for side in (-1, 1):
            x = 300 + side * 148
            p.shape(ellipse_pts(x, 318, 9, 9, n=20), (250, 214, 90), 3)
    if "tufts" in b.extras:  # a bald head with grey hair left at the sides (an older man)
        hc = b.hair_color or shade(b.color, 0.62)
        for side in (-1, 1):
            x = 300 + side * 138
            p.shape(ellipse_pts(x, 236, 22, 50, n=30), hc, 4)
    if "mustache" in b.extras:
        hc = b.hair_color or shade(b.color, 0.62)
        p.shape(bez((300, 352), (270, 336), (236, 340), (222, 362)) + bez((222, 362), (260, 366), (284, 362), (300, 358)) +
                bez((300, 358), (316, 362), (340, 366), (378, 362)) + bez((378, 362), (364, 340), (330, 336), (300, 352)), hc, 4)
    if "pearls" in b.extras:
        for k in range(11):
            t = math.pi * (0.2 + 0.6 * k / 10)
            x, y = 300 - 60 * math.cos(t), 396 + 34 * math.sin(t)
            p.shape(ellipse_pts(x, y, 7, 7, n=14), (250, 248, 240), 2.5)


def _bean(b: Bean, expr: str, head=None, arms=None) -> Image.Image:
    img = Image.new("RGBA", (W0 * SS, H0 * SS), (0, 0, 0, 0))
    p = Pencil(img, b.seed)
    col = b.color
    _hair(p, b, front=False)
    p.shape([(284, 370), (316, 370), (318, 410), (282, 410)], shade(col, 0.85), 4)  # neck
    coat = COAT if "labcoat" in b.extras else None
    p.shape(_torso(), coat or col, 5.5)
    if coat:  # lab coat: open collar showing the shirt, lapels and a pocket
        p.shape([(262, 398), (338, 398), (300, 560)], col, 4)
        p.line([(262, 398), (300, 560)], 4)
        p.line([(338, 398), (300, 560)], 4)
        p.line([(300, 560), (300, 900)], 3.5)
        p.shape([(340, 600), (400, 600), (398, 660), (342, 660)], coat, 3.5)
        p.line([(356, 600), (360, 570)], 4, (60, 90, 200))
    if arms is None:
        for side in (-1, 1):
            p.shape(_arm(side), coat or shade(col, 0.93), 5)
            hx = 300 + side * 128
            p.shape(ellipse_pts(hx, 618, 26, 24, n=28), col, 5)
    p.hatch(286, 396, 306, 414, 3, 2.5)
    _extras_body = [e for e in b.extras if e in ("tie", "badge", "pearls")]
    if _extras_body:
        _extras(p, Bean(b.name, b.role, col, extras=tuple(_extras_body), seed=b.seed))
    if head:
        head(p)
        return img
    cx, cy, rx, ry = HEAD
    for side in (-1, 1):  # ears
        p.shape(ellipse_pts(300 + side * 146, 280, 18, 26, n=24), col, 4.5)
    p.shape(ellipse_pts(cx, cy, rx, ry, n=90), col, 6)
    if "earrings" in b.extras:
        _extras(p, Bean(b.name, b.role, col, extras=("earrings",), seed=b.seed))
    _hair(p, b, front=True)
    _brows(p, expr)
    _eyes(p, expr, col)
    _mouth(p, expr)
    face = tuple(e for e in ("glasses", "tufts", "mustache") if e in b.extras)
    if face:
        _extras(p, Bean(b.name, b.role, col, extras=face, seed=b.seed, hair_color=b.hair_color))
    if expr == "worried":
        p.shape(bez((452, 150), (440, 180), (436, 196), (452, 198)) + bez((452, 198), (468, 196), (464, 180), (452, 150))[1:],
                (170, 220, 255), 3.5)
    if arms is not None:  # posable arms go on top, so a hand can reach the face
        _arms(p, col, arms, coat)
    return img


def _glitch(expr: str) -> Image.Image:
    """GLITCH: a light-blue bean whose head is an old screen with a pixel face."""
    b = Bean("GLITCH", "Host", GLITCH_BLUE, seed=7)

    def head(p: Pencil):
        p.line([(300, 112), (300, 70)], 5)
        p.shape(ellipse_pts(300, 62, 14, 14, n=20), (255, 90, 150), 4)
        p.shape([(170, 120), (430, 120), (450, 140), (450, 360), (430, 380), (170, 380), (150, 360), (150, 140)], GLITCH_BLUE, 6)
        p.d.rounded_rectangle([186 * SS, 150 * SS, 414 * SS, 350 * SS], radius=26 * SS, fill=(20, 34, 56))
        px = lambda x, y, w=18, h=18: p.d.rectangle([x * SS, y * SS, (x + w) * SS, (y + h) * SS], fill=(150, 230, 255))
        L, R, ey = 246, 334, 222
        if expr == "happy":
            for ex in (L, R):
                px(ex - 18, ey + 8, 14, 14), px(ex - 4, ey - 6, 14, 14), px(ex + 10, ey + 8, 14, 14)
        elif expr == "surprised":
            for ex in (L, R):
                px(ex - 14, ey - 16, 28, 40)
        elif expr == "worried":
            for ex in (L, R):
                px(ex - 10, ey, 20, 28)
            px(L - 22, ey - 22, 30, 8), px(R - 8, ey - 22, 30, 8)
        elif expr == "smug":
            px(L - 14, ey + 10, 28, 12), px(R - 14, ey - 4, 28, 26)
        else:
            for ex in (L, R):
                px(ex - 10, ey - 8, 20, 32)
        my = 300
        if expr == "surprised":
            px(290, my - 10, 20, 20)
        elif expr == "worried":
            for k, x in enumerate(range(262, 340, 16)):
                px(x, my + (6 if k % 2 else 0), 12, 12)
        else:
            for x, y in ((258, my - 8), (274, my + 4), (294, my + 10), (314, my + 4), (330, my - 8)):
                px(x, y, 14, 12)

    return _bean(b, expr, head=head)


BUGS = {
    "impostor": ("The Impostor", (150, 110, 220)),
    "overthinker": ("The Overthinker", (250, 170, 60)),
    "procrastinator": ("The Procrastinator", (90, 200, 170)),
    "perfectionist": ("The Perfectionist", (240, 90, 100)),
}


def _bug(kind: str, expr: str) -> Image.Image:
    img = Image.new("RGBA", (W0 * SS, H0 * SS), (0, 0, 0, 0))
    p = Pencil(img, 40 + list(BUGS).index(kind))
    col = BUGS[kind][1]
    droop = kind == "procrastinator"
    for side in (-1, 1):
        tip = (300 + side * 110, 300 if not droop else 420)
        p.line(bez((300 + side * 50, 470), (300 + side * 70, 400), (tip[0], tip[1] + 50), tip), 5)
        p.shape(ellipse_pts(*tip, 18, 18, n=20), col, 4.5)
    for side in (-1, 1):
        p.shape(ellipse_pts(300 + side * 70, 830, 44, 24, n=28), shade(col, 0.8), 4.5)
    body = (ellipse_pts(300, 640, 170, 200, n=90) if kind != "perfectionist"
            else [(150, 470), (450, 470), (470, 490), (470, 820), (450, 840), (150, 840), (130, 820), (130, 490)])
    p.shape(body, col, 6)
    p.shape(ellipse_pts(300, 720, 90, 90, n=50), shade(col, 1.22), 3.5, wobble=1.0)
    for side in (-1, 1):
        p.line(bez((300 + side * 168, 660), (300 + side * 210, 680), (300 + side * 214, 720), (300 + side * 196, 750)), 6)
    eyes = [(240, 590), (360, 590)] if kind != "overthinker" else [(220, 600), (300, 570), (380, 600)]
    r = (44, 56) if kind != "overthinker" else (34, 44)
    for i, (cx, cy) in enumerate(eyes):
        if expr == "happy":
            p.line(ellipse_pts(cx, cy + 14, 30, 22, math.pi * 1.1, math.pi * 1.9, 20), 6)
            continue
        p.shape(ellipse_pts(cx, cy, *r, n=40), WHITE, 5)
        pr = 9 if expr != "surprised" else 6
        dy = 20 if not droop else 26
        p.d.ellipse([(cx - pr) * SS, (cy + dy - pr) * SS, (cx + pr) * SS, (cy + dy + pr) * SS], fill=INK)
        if droop or expr == "smug":
            lid = ellipse_pts(cx, cy, r[0] + 7, r[1] + 7, math.pi, 2 * math.pi, 30) + [(cx + r[0] + 7, cy + 4), (cx - r[0] - 7, cy + 4)]
            p.d.polygon([(x * SS, y * SS) for x, y in lid], fill=col)
            p.line([(cx - r[0] + 4, cy + 4), (cx + r[0] - 4, cy + 2)], 5)
    my = 690
    if expr == "happy":
        p.shape([(270, my - 6), (330, my - 6)] + bez((330, my - 6), (328, my + 26), (272, my + 26), (270, my - 6))[1:], (40, 26, 30), 4.5)
    elif expr == "worried":
        p.line([(280, my + 6), (290, my), (300, my + 6), (310, my), (320, my + 6)], 4.5)
    elif kind == "impostor" or expr == "smug":
        p.line(bez((276, my + 4), (294, my + 10), (312, my + 6), (326, my - 8)), 5)
    else:
        p.line(ellipse_pts(300, my - 8, 14, 10, math.pi * 0.2, math.pi * 0.8, 16), 5)
    if kind == "impostor":  # eye mask
        mask = [(178, 560), (422, 560), (430, 610), (300, 600), (170, 610)]
        p.shape(mask, (40, 30, 54), 4)
        for cx, cy in eyes:
            p.d.ellipse([(cx - 22) * SS, (cy - 4 - 18) * SS, (cx + 22) * SS, (cy - 4 + 18) * SS], fill=WHITE)
            p.d.ellipse([(cx - 8) * SS, (cy - 4 - 8) * SS, (cx + 8) * SS, (cy - 4 + 8) * SS], fill=INK)
    elif kind == "overthinker":
        for k in range(3):
            p.line(ellipse_pts(300, 360 - k * 12, 70 - k * 18, 30 - k * 6, 0.3, 2 * math.pi - 0.3, 30), 4)
    elif kind == "procrastinator":
        f = ImageFont.truetype(str(HAND_FONT), 60 * SS)
        for k, (x, y) in enumerate(((430, 400), (470, 340), (515, 270))):
            p.d.text((x * SS, y * SS), "z", font=ImageFont.truetype(str(HAND_FONT), (40 + k * 16) * SS), fill=INK)
    elif kind == "perfectionist":
        p.shape([(490, 700), (520, 700), (520, 820), (490, 820)], (250, 230, 150), 3.5)
        for y in range(714, 812, 16):
            p.line([(490, y), (504, y)], 2.5)
    return img


def draw(name: str, expression: str | None = None, height: int = 700, blink: bool = False, arms=None) -> Image.Image:
    """Return a character as a transparent RGBA image `height` pixels tall.
    arms: ((upper, fore), (upper, fore)) angles (see POSES) for posable arms; None keeps the classic arms."""
    global _BLINK
    _BLINK = blink
    try:
        return _draw(name, expression, height, arms)
    finally:
        _BLINK = False


def _draw(name, expression, height, arms=None):
    if name in ("neuro", "host"):  # the channel host
        from . import hosts
        return hosts.draw("neuro", expression or "happy", height)
    if name == "glitch":  # retired host, kept for reference
        img = _glitch(expression or "happy")
    elif name in BUGS:
        img = _bug(name, expression or "neutral")
    else:
        b = CAST[name]
        img = _bean(b, expression or b.default, arms=arms)
    img = img.crop((0, 0, W0 * SS, (860 if name in BUGS else 690) * SS))
    w = int(height * img.width / img.height)
    return img.resize((w, height), Image.LANCZOS)


def back(name: str, height: int = 700) -> Image.Image:
    """A cast member seen from behind (head and shoulders), for over-the-shoulder shots."""
    b = CAST[name]
    hc = b.hair_color or shade(b.color, 0.62)
    img = Image.new("RGBA", (600 * SS, 900 * SS), (0, 0, 0, 0))
    p = Pencil(img, b.seed + 40)
    p.shape(bez((40, 900), (50, 720), (120, 650), (230, 640)) + [(370, 640)] +
            bez((370, 640), (480, 650), (550, 720), (560, 900))[1:], shade(b.color, 0.9), 6)
    p.shape([(240, 560), (360, 560), (370, 660), (230, 660)], b.color, 5)
    for ex in (112, 488):
        p.shape(ellipse_pts(ex, 430, 30, 44), b.color, 5)
    head = ellipse_pts(300, 410, 190, 176, n=70)
    p.shape(head, b.color, 6)
    if b.hair == "long":
        p.shape(ellipse_pts(300, 400, 200, 186, math.pi, 2 * math.pi, 40) +
                bez((500, 400), (520, 560), (500, 660), (470, 700)) + [(130, 700)] +
                bez((130, 700), (100, 660), (80, 560), (100, 400))[1:], hc, 6)
    elif b.hair == "bob":
        p.shape(ellipse_pts(300, 405, 204, 190, math.pi * 0.92, math.pi * 2.08, 50) +
                bez((496, 470), (470, 520), (400, 530), (300, 528)) + bez((300, 528), (200, 530), (130, 520), (104, 470)), hc, 6)
    else:
        p.shape(ellipse_pts(300, 405, 196, 182, math.pi * 1.02, math.pi * 1.98, 50) +
                bez((490, 380), (450, 470), (380, 492), (300, 490)) + bez((300, 490), (220, 492), (150, 470), (110, 380)), hc, 6)
        if b.hair == "bun":
            p.shape(ellipse_pts(300, 300, 80, 70), hc, 6)
    img = img.resize((600, 900), Image.LANCZOS)
    img = img.crop(img.getchannel("A").getbbox())
    return img.resize((int(height * img.width / img.height), height), Image.LANCZOS)


# ---------- scene helpers ----------

def background(color, w=1920, h=1080) -> Image.Image:
    """Flat colour with a soft lighter centre, like a sketchbook page lit from the middle."""
    img = Image.new("RGBA", (w, h), shade(color, 0.82) + (255,))
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse((w * 0.1, h * 0.0, w * 0.9, h * 1.1), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(w // 8))
    img.paste(Image.new("RGBA", (w, h), shade(color, 1.05) + (255,)), (0, 0), glow)
    return img


def label(img: Image.Image, text: str, xy, size=44, color=INK, arrow_to=None, seed=3):
    """Handwritten note, optionally with a hand-drawn arrow pointing at something."""
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(HAND_FONT), size)
    d.text(xy, text, font=f, fill=color, anchor="mm")
    if arrow_to:
        tmp = Image.new("RGBA", (img.width * SS, img.height * SS), (0, 0, 0, 0))
        p = Pencil(tmp, seed)
        x0, y0 = xy[0], xy[1] + size * 0.7
        x1, y1 = arrow_to
        p.line(bez((x0, y0), (x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), (x1, y1)), 3.5, color)
        p.line([(x1 - 10, y1 - 14), (x1, y1), (x1 + 10, y1 - 14)], 3.5, color)
        img.alpha_composite(tmp.resize(img.size, Image.LANCZOS))


def shock_lines(img: Image.Image, cx, cy, color=WHITE, seed=5):
    tmp = Image.new("RGBA", (img.width * SS, img.height * SS), (0, 0, 0, 0))
    p = Pencil(tmp, seed)
    for k in range(3):
        y = cy + k * 40
        p.line([(cx, y), (cx + 40, y - 30), (cx + 70, y + 10), (cx + 110, y - 24), (cx + 140, y)], 4, color)
    img.alpha_composite(tmp.resize(img.size, Image.LANCZOS))


# ---------- profile (2026-11-18): a cast member seen from the side, facing right ----------
# Same head size, colour and pencil line as the front view; one big eye near the front of the face,
# a small nose bump, the ear in the middle of the head and the hair falling at the back.
P_HEAD = (300, 250, 146, 138)
P_EYE = (372, 272)
P_EYE_R = (46, 70)


def _p_arm(p: Pencil, col, upper, fore, sleeve=None):
    """The near arm in profile: angles as in POSES, positive = forward (towards the face)."""
    sh = (300, 452)
    u, f = math.radians(upper), math.radians(fore)
    el = (sh[0] + UPPER * math.sin(u), sh[1] + UPPER * math.cos(u))
    hd = (el[0] + FORE * math.sin(f), el[1] + FORE * math.cos(f))
    el2 = (el[0] + (el[0] - (sh[0] + hd[0]) / 2) * 0.3, el[1] + (el[1] - (sh[1] + hd[1]) / 2) * 0.3)
    p.shape(_hose(sh, el2, hd), sleeve or shade(col, 0.93), 5)
    p.shape(ellipse_pts(hd[0], hd[1], 27, 25, n=28), col, 5)
    return hd


def profile_hand(arm=(16, -4)):
    """Where the near hand is in base units (600 x 690 crop) for a profile arm pose."""
    sh = (300, 452)
    u, f = math.radians(arm[0]), math.radians(arm[1])
    el = (sh[0] + UPPER * math.sin(u), sh[1] + UPPER * math.cos(u))
    return (el[0] + FORE * math.sin(f), el[1] + FORE * math.cos(f))


def front_hand(arm=(16, -4), side=1):
    """Where a hand is in base units (600 x 690 crop) for a front-view arm pose (side 1 = picture right)."""
    return _limb(side, *arm)[2]


def _p_hair(p: Pencil, b: Bean, front: bool):
    hc = b.hair_color or shade(b.color, 0.62)
    cx, cy, rx, ry = P_HEAD
    if not front:
        if b.hair == "long":
            p.shape(bez((330, 150), (150, 150), (130, 330), (150, 500)) + [(290, 500)] +
                    bez((290, 500), (270, 420), (250, 330), (300, 250))[1:], hc, 5)
        if b.hair == "bun":
            p.shape(ellipse_pts(170, 140, 54, 46), hc, 5)
        return
    if b.hair == "none":
        return
    # a cap over the top and the back of the head, ending above the ear; a fringe at the front
    back_to = {"long": 0.62, "bob": 0.55, "sidepart": 0.86, "bun": 0.86, "crop": 0.9}.get(b.hair, 0.9)
    cap = ellipse_pts(cx, cy, rx + 6, ry + 6, math.pi * (2 - 0.2), math.pi * (2 - 0.2) - math.pi * (1 + 0.2 - back_to + 0.6), 40)
    if b.hair == "crop":
        zig = [(cap[-1][0] + 10, cap[-1][1] + 10), (180, 200), (210, 186), (240, 196), (270, 176), (300, 188), (330, 168), (360, 180), (390, 162), (420, 172)]
        p.shape(cap + zig, hc, 5)
    elif b.hair == "bob":
        p.shape(cap + bez(cap[-1], (226, 340), (214, 262), (250, 212)) + bez((250, 212), (320, 186), (380, 176), (430, 182)), hc, 5)
    elif b.hair == "long":
        p.shape(cap + bez(cap[-1], (214, 330), (210, 262), (250, 212)) + bez((250, 212), (320, 186), (380, 176), (430, 182)), hc, 5)
    else:  # sidepart, bun
        p.shape(cap + bez(cap[-1], (200, 270), (230, 240), (250, 210)) + bez((250, 210), (320, 186), (380, 176), (430, 182)), hc, 5)
        if b.hair == "sidepart":
            p.line(bez((420, 176), (380, 150), (320, 140), (260, 150)), 4)


def _p_face(p: Pencil, expr, col, b: Bean):
    ex, ey = P_EYE
    rx, ry = P_EYE_R
    # brow
    by = ey - ry - 14
    if expr in ("worried", "sad"):
        p.line([(ex - 26, by - 10), (ex + 26, by + 6)], 5)
    elif expr == "surprised":
        p.line(ellipse_pts(ex, by + 6, 28, 16, math.pi * 1.15, math.pi * 1.85, 16), 5)
    elif expr == "happy":
        p.line(ellipse_pts(ex, by + 30, 24, 14, math.pi * 1.2, math.pi * 1.8, 16), 5)
    else:
        p.line([(ex - 22, by + 2), (ex + 22, by - 2)], 5)
    # eye
    if _BLINK and expr != "happy":
        p.line(ellipse_pts(ex, ey + 20, 40, 18, math.pi * 0.1, math.pi * 0.9, 20), 6)
    elif expr == "happy":
        p.line(ellipse_pts(ex, ey + 18, 36, 30, math.pi * 1.1, math.pi * 1.9), 7)
    else:
        p.shape(ellipse_pts(ex, ey, rx, ry), WHITE, 5.5)
        pr, dx, dy = (10, 15), 22, 30
        if expr == "surprised":
            pr, dx, dy = (7, 9), 18, 0
        elif expr in ("worried", "sad"):
            pr, dx, dy = (9, 14), 18, 44
        elif expr == "smug":
            pr, dx, dy = (10, 13), 22, 34
        px, py = ex + dx, ey + dy
        p.d.ellipse([(px - pr[0]) * SS, (py - pr[1]) * SS, (px + pr[0]) * SS, (py + pr[1]) * SS], fill=INK)
        p.d.ellipse([(px - 4) * SS, (py - pr[1] + 2) * SS, px * SS, (py - pr[1] + 7) * SS], fill=WHITE)
        if expr == "smug":
            lid = ellipse_pts(ex, ey, rx + 7, ry + 7, math.pi, 2 * math.pi) + [(ex + rx + 7, ey + 6), (ex - rx - 7, ey + 6)]
            p.d.polygon([(x * SS, y * SS) for x, y in lid], fill=col)
            p.line([(ex - rx + 4, ey + 6), (ex + rx - 4, ey + 4)], 6)
    # mouth, at the front of the face
    y, x = 372, 414
    if expr == "happy":
        pts = [(x - 34, y - 8), (x + 22, y - 10)] + bez((x + 22, y - 10), (x + 16, y + 26), (x - 26, y + 26), (x - 34, y - 8))[1:]
        p.shape(pts, (40, 26, 30), 5)
    elif expr == "worried":
        p.line([(x - 22, y + 6), (x - 12, y), (x - 2, y + 6), (x + 8, y)], 4.5)
    elif expr == "surprised":
        p.shape(ellipse_pts(x - 4, y + 4, 10, 15, n=24), (40, 26, 30), 4.5)
    elif expr == "smug":
        p.line(bez((x - 30, y + 2), (x - 14, y + 10), (x + 2, y + 6), (x + 14, y - 8)), 5)
    elif expr == "sad":
        p.line(ellipse_pts(x - 6, y + 18, 16, 12, math.pi * 1.15, math.pi * 1.85, 16), 5)
    else:
        p.line(ellipse_pts(x - 6, y - 8, 14, 10, math.pi * 0.2, math.pi * 0.8, 16), 5)
    hc = b.hair_color or shade(col, 0.62)
    if "mustache" in b.extras:
        p.shape(bez((x + 18, y - 22), (x - 4, y - 34), (x - 40, y - 30), (x - 46, y - 12)) +
                bez((x - 46, y - 12), (x - 20, y - 8), (x + 6, y - 8), (x + 18, y - 22)), hc, 4)
    if "tufts" in b.extras:
        p.shape(ellipse_pts(216, 252, 20, 44, n=30), hc, 4)
    if "glasses" in b.extras:
        p.line(ellipse_pts(ex, ey, rx + 12, ry + 10), 5)
        p.line([(ex - rx - 12, ey - 6), (262, ey - 2)], 5)
    if expr == "worried":
        p.shape(bez((214, 160), (202, 190), (198, 206), (214, 208)) + bez((214, 208), (230, 206), (226, 190), (214, 160))[1:],
                (170, 220, 255), 3.5)


def _bean_profile(b: Bean, expr: str, arms=None) -> Image.Image:
    img = Image.new("RGBA", (W0 * SS, H0 * SS), (0, 0, 0, 0))
    p = Pencil(img, b.seed + 60)
    col = b.color
    _p_hair(p, b, front=False)
    p.shape([(296, 370), (330, 370), (334, 412), (292, 412)], shade(col, 0.85), 4)  # neck
    coat = COAT if "labcoat" in b.extras else None
    torso = [(300 + (x - 300) * 0.78 + 8, y) for x, y in _torso()]
    p.shape(torso, coat or col, 5.5)
    if "tie" in b.extras:  # the tie seen from the side: a sliver down the chest
        p.shape([(388, 414), (404, 418), (400, 520), (386, 540)], (60, 70, 120), 3.5)
    if "badge" in b.extras:
        p.line(bez((330, 404), (370, 460), (392, 500), (396, 540)), 3.5, (60, 90, 200))
        p.shape([(380, 540), (412, 540), (412, 596), (380, 596)], WHITE, 4)
    if "pearls" in b.extras:
        for k in range(5):
            p.shape(ellipse_pts(332 + k * 14, 404 + k * 3, 7, 7, n=14), (250, 248, 240), 2.5)
    cx, cy, rx, ry = P_HEAD
    p.shape(ellipse_pts(cx, cy, rx, ry, n=90), col, 6)
    p.shape(ellipse_pts(cx + rx - 6, 300, 18, 20, -math.pi * 0.55, math.pi * 0.55, 20) + [(cx + rx - 14, 318), (cx + rx - 14, 282)],
            col, 4.5)  # nose bump
    _p_hair(p, b, front=True)
    p.shape(ellipse_pts(258, 282, 20, 28, n=24), col, 4.5)  # ear
    if "earrings" in b.extras:
        p.shape(ellipse_pts(258, 322, 9, 9, n=20), (250, 214, 90), 3)
    _p_face(p, expr, col, b)
    _p_arm(p, col, *(arms[1] if arms else (16, -4)), sleeve=coat)
    return img


def profile(name: str, expression: str | None = None, height: int = 700, blink: bool = False, arms=None,
            facing: int = 1) -> Image.Image:
    """A cast member from the side, `facing` 1 = looking right, -1 = looking left. Only the near arm shows;
    it takes the picture-right entry of an arm pose (positive angles reach forward)."""
    global _BLINK
    _BLINK = blink
    try:
        b = CAST[name]
        img = _bean_profile(b, expression or b.default, arms=arms)
    finally:
        _BLINK = False
    img = img.crop((0, 0, W0 * SS, 690 * SS))
    if facing < 0:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    w = int(height * img.width / img.height)
    return img.resize((w, height), Image.LANCZOS)


# ---------- props (2026-11-18): things the cast holds, drops or puts down ----------

def prop(kind: str, text: str = "", height: int = 200) -> Image.Image:
    """A hand-drawn object, `height` pixels tall: paper (a printed sheet; `text` is its big headline),
    phone, mug."""
    img = Image.new("RGBA", (400 * SS, 520 * SS), (0, 0, 0, 0))
    p = Pencil(img, 77 + len(kind))
    if kind == "paper":
        p.shape([(40, 30), (360, 22), (368, 494), (34, 500)], (252, 251, 246), 6)
        p.d.polygon([(x * SS, y * SS) for x, y in [(300, 22), (360, 22), (360, 82)]], fill=(0, 0, 0, 0))
        p.shape([(300, 24), (360, 82), (304, 80)], (226, 224, 216), 4)  # folded corner
        if text:
            f = ImageFont.truetype(str(HAND_FONT), 10)
            size = 110
            while size > 30:
                f = ImageFont.truetype(str(HAND_FONT), size * SS)
                if p.d.textlength(text, font=f) < 290 * SS:
                    break
                size -= 6
            p.d.text((200 * SS, 140 * SS), text, font=f, fill=(214, 60, 60), anchor="mm")
            p.line([(70, 200), (330, 196)], 5, (214, 60, 60))
        for y in range(250, 470, 34):
            p.line([(70, y), (70 + 220 + (y * 7) % 60, y + 2)], 4, (150, 150, 160), wobble=0.8)
    elif kind == "phone":
        p.shape([(130, 60), (270, 60), (280, 80), (280, 460), (270, 480), (130, 480), (120, 460), (120, 80)], (40, 44, 56), 6)
        p.shape([(140, 100), (260, 100), (260, 430), (140, 430)], (120, 190, 240), 4)
    elif kind == "mug":
        p.line(ellipse_pts(300, 290, 70, 80, -math.pi / 2, math.pi / 2, 30), 14)
        p.shape([(80, 160), (300, 160), (290, 470), (90, 470)], (250, 250, 250), 6)
        p.line([(110, 260), (270, 260)], 6, (58, 99, 216))
    else:
        raise ValueError(f"unknown prop {kind}")
    img = img.crop(img.getbbox())
    w = max(1, int(height * img.width / img.height))
    return img.resize((w, height), Image.LANCZOS)
