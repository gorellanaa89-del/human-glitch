"""The bug cast: one hand-drawn creature per mental glitch.

Same pencil style as the people in `sketch.py`: a round blob with antennae, huge eyes, one solid
colour, plus one prop that tells you which glitch it is at a glance.
Family 1 = cognitive distortions (Beck/Burns). Family 2 = decision biases (Kahneman/Tversky).
"""
import math

from PIL import Image, ImageDraw, ImageFont

from .sketch import HAND_FONT, INK, SS, WHITE, Pencil, bez, ellipse_pts, shade

W, H = 900, 900
CX, CY = 450, 640          # body centre
BR = (170, 200)            # body radii
EYES = ((CX - 60, 590), (CX + 60, 590))
ER = (44, 56)
DARK = (45, 42, 52)


def _font(size):
    return ImageFont.truetype(str(HAND_FONT), int(size * SS))


# name -> (display name, family, colour, default expression)
BUGS = {
    # family 1: cognitive distortions
    "impostor": ("The Impostor", 1, (150, 110, 220), "worried"),
    "catastrophizer": ("The Catastrophizer", 1, (235, 85, 80), "scream"),
    "mind_reader": ("The Mind Reader", 1, (190, 120, 215), "worried"),
    "fortune_teller": ("The Fortune Teller", 1, (110, 190, 240), "worried"),
    "all_or_nothing": ("The All-or-Nothing", 1, (250, 250, 250), "worried"),
    "filter": ("The Filter", 1, (110, 190, 95), "sad"),
    "should": ("The Should", 1, (165, 165, 175), "worried"),
    "labeler": ("The Labeler", 1, (248, 205, 60), "sad"),
    "generalizer": ("The Generalizer", 1, (245, 145, 55), "sad"),
    "blamer": ("The Blamer", 1, (165, 115, 80), "sad"),
    # family 2: decision biases
    "know_it_all": ("The Know-It-All", 2, (235, 185, 60), "happy"),
    "echo": ("The Echo", 2, (60, 200, 195), "happy"),
    "anchor": ("The Anchor", 2, (60, 80, 140), "neutral"),
    "hoarder": ("The Hoarder", 2, (145, 155, 75), "worried"),
    "sunk_cost": ("The Sunk Cost", 2, (125, 145, 170), "worried"),
    "halo": ("The Halo", 2, (252, 250, 244), "happy"),
    "planner": ("The Planner", 2, (245, 150, 190), "happy"),
    "follower": ("The Follower", 2, (225, 200, 160), "neutral"),
}


# ---------- shared parts ----------

def _canvas():
    return Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))


def _dot(p, x, y, r, color=INK):
    p.d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=color)


def _poly(p, pts, fill):
    p.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill)


def _body_pts():
    return ellipse_pts(CX, CY, *BR, n=90)


HEAD_STYLE = "antennae"  # antennae | none | pixels | signal | sprout


def _antennae(p, col, droop=False, style=None):
    style = style or HEAD_STYLE
    if style == "antennae":
        for side in (-1, 1):
            tip = (CX + side * 110, 300 if not droop else 420)
            p.line(bez((CX + side * 50, 470), (CX + side * 70, 400), (tip[0], tip[1] + 50), tip), 5)
            p.shape(ellipse_pts(*tip, 18, 18, n=20), col, 4.5)
    elif style == "pixels":  # glitch fragments breaking off the top of the head
        for x, y, r in ((CX - 40, 410, 18), (CX + 30, 386, 22), (CX + 90, 420, 14), (CX - 6, 350, 12), (CX + 70, 330, 9)):
            p.shape([(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)], col, 4, wobble=0.6)
    elif style == "signal":  # little wifi arcs: the mind is "transmitting"
        for k in range(3):
            p.line(ellipse_pts(CX, 450, 34 + k * 30, 30 + k * 26, math.pi * 1.25, math.pi * 1.75, 16), 5.5)
        _dot(p, CX, 430, 9)
    elif style == "sprout":  # one curly hair, like a thought that won't lie down
        p.line(bez((CX, 446), (CX - 10, 380), (CX + 60, 360), (CX + 40, 400)) + bez((CX + 40, 400), (CX + 26, 420), (CX + 10, 400), (CX + 24, 388))[1:], 6)


def _feet(p, col):
    for side in (-1, 1):
        p.shape(ellipse_pts(CX + side * 70, 830, 44, 24, n=28), shade(col, 0.8), 4.5)


def _arm(p, col, side, end=None, hand=True):
    end = end or (CX + side * 205, 750)
    sx, sy = CX + side * 166, 660
    p.line(bez((sx, sy), (sx + side * 30, sy + 10), (end[0], end[1] - 40), end), 6)
    if hand:
        p.shape(ellipse_pts(*end, 17, 17, n=20), col, 4.5)


def _eyes(p, expr, col, look=(0, 0), skip=()):
    for i, (cx, cy) in enumerate(EYES):
        if i in skip:
            continue
        side = -1 if i == 0 else 1
        if expr == "happy":
            p.line(ellipse_pts(cx, cy + 14, 30, 22, math.pi * 1.1, math.pi * 1.9, 20), 6)
            continue
        p.shape(ellipse_pts(cx, cy, *ER, n=40), WHITE, 5)
        if expr == "spiral":
            pts = [(cx + (4 + 34 * t) * math.cos(t * 6 * math.pi), cy + (4 + 40 * t) * math.sin(t * 6 * math.pi))
                   for t in [k / 80 for k in range(81)]]
            p.line(pts, 3.5, wobble=0.5)
            continue
        pr = 6 if expr in ("surprised", "scream") else 9
        dx = look[0] + (side * -4 if expr == "angry" else 0)
        dy = 20 + look[1] if expr not in ("worried", "sad") else 26 + look[1]
        _dot(p, cx + dx, cy + dy, pr)
        _dot(p, cx + dx - 3, cy + dy - 4, 2.5, WHITE)
        if expr in ("smug", "angry"):  # heavy lids
            lid = ellipse_pts(cx, cy, ER[0] + 7, ER[1] + 7, math.pi, 2 * math.pi, 30) + [(cx + ER[0] + 7, cy + 4), (cx - ER[0] - 7, cy + 4)]
            _poly(p, lid, col)
            p.line([(cx - ER[0] + 4, cy + 4), (cx + ER[0] - 4, cy + 2)], 5)


def _brows(p, expr, colors=(INK, INK)):
    for i, (cx, cy) in enumerate(EYES):
        side = -1 if i == 0 else 1
        y = cy - ER[1] - 16
        c = colors[i]
        if expr == "angry":
            p.line([(cx + side * 30, y - 10), (cx - side * 24, y + 12)], 6, c)
        elif expr in ("worried", "sad", "scream"):
            p.line([(cx - side * 30, y - 10), (cx + side * 22, y + 8)], 5, c)
        elif expr == "smug" and side == 1:
            p.line(ellipse_pts(cx, y + 2, 30, 14, math.pi * 1.15, math.pi * 1.85, 16), 5, c)
        elif expr == "surprised":
            p.line(ellipse_pts(cx, y + 2, 30, 16, math.pi * 1.15, math.pi * 1.85, 16), 5, c)


def _mouth(p, expr, color=INK):
    my = 690
    if expr == "happy":
        p.shape([(CX - 30, my - 6), (CX + 30, my - 6)] + bez((CX + 30, my - 6), (CX + 28, my + 26), (CX - 28, my + 26), (CX - 30, my - 6))[1:],
                (40, 26, 30), 4.5)
        _dot(p, CX, my + 12, 9, (236, 110, 120))
    elif expr == "worried":
        p.line([(CX - 20, my + 6), (CX - 10, my), (CX, my + 6), (CX + 10, my), (CX + 20, my + 6)], 4.5, color)
    elif expr in ("surprised",):
        p.shape(ellipse_pts(CX, my + 4, 11, 14, n=24), (40, 26, 30), 4.5)
    elif expr == "scream":
        p.shape(ellipse_pts(CX, my + 14, 30, 36, n=30), (40, 26, 30), 5)
        _dot(p, CX, my + 34, 12, (236, 110, 120))
    elif expr == "smug":
        p.line(bez((CX - 24, my + 4), (CX - 6, my + 10), (CX + 12, my + 6), (CX + 26, my - 8)), 5, color)
    elif expr == "angry":
        p.line(bez((CX - 22, my + 8), (CX - 8, my - 2), (CX + 8, my - 2), (CX + 22, my + 8)), 5, color)
    elif expr == "sad":
        p.line(ellipse_pts(CX, my + 16, 18, 12, math.pi * 1.15, math.pi * 1.85, 16), 5, color)
    else:
        p.line(ellipse_pts(CX, my - 8, 14, 10, math.pi * 0.2, math.pi * 0.8, 16), 5, color)


def _core(kind, expr, look=(0, 0), antennae=True, arms=True, belly=True, seed=0):
    """Plain bug body with face; props are drawn on top by `draw`."""
    img = _canvas()
    p = Pencil(img, 60 + list(BUGS).index(kind) + seed)
    col = BUGS[kind][2]
    if antennae:
        _antennae(p, col)
    _feet(p, col)
    p.shape(_body_pts(), col, 6)
    if belly:
        p.shape(ellipse_pts(CX, 720, 90, 90, n=50), shade(col, 1.15 if sum(col) < 600 else 0.94), 3.5, wobble=1.0)
    if arms:
        for side in (-1, 1):
            _arm(p, col, side, hand=False)
    _eyes(p, expr, col, (look[0], look[1] - 30) if kind == "impostor" else look)
    _brows(p, expr)
    _mouth(p, expr)
    return img, p


def _paste_copy(dst, src, x, scale, alpha=1.0):
    """Paste a scaled copy of a full bug canvas so its feet stand on the same ground at centre x."""
    w, h = int(src.width * scale), int(src.height * scale)
    c = src.resize((w, h), Image.LANCZOS)
    if alpha < 1:
        a = c.getchannel("A").point(lambda v: int(v * alpha))
        c.putalpha(a)
    px = int((x - CX * scale) * SS)
    py = int((860 - 860 * scale) * SS)
    layer = Image.new("RGBA", dst.size, (0, 0, 0, 0))
    layer.paste(c, (px, py), c)
    dst.alpha_composite(layer)


def _rot(cx, cy, w, h, ang):
    a = math.radians(ang)
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in pts]


def _rot_text(img, text, cx, cy, ang, size, color=INK):
    f = _font(size)
    tw = int(f.getlength(text)) + 20
    t = Image.new("RGBA", (tw, int(size * SS * 1.6)), (0, 0, 0, 0))
    ImageDraw.Draw(t).text((tw / 2, t.height / 2), text, font=f, fill=color, anchor="mm")
    t = t.rotate(-ang, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(t, (int(cx * SS - t.width / 2), int(cy * SS - t.height / 2)))


def _sparkle(p, x, y, r, color=(255, 210, 60)):
    pts = []
    for k in range(8):
        a = k * math.pi / 4
        rr = r if k % 2 == 0 else r * 0.3
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    p.shape(pts, color, 3)


# ---------- the cast ----------

def draw_full(kind: str, expr: str | None = None) -> Image.Image:
    """Full-resolution (SS) canvas with the bug and its prop."""
    name, fam, col, default = BUGS[kind]
    e = expr or default

    if kind == "impostor":
        img, p = _core(kind, e)
        if e != "happy":  # once patched, the mask comes off
            p.shape([(CX - 122, 560), (CX + 122, 560), (CX + 130, 610), (CX, 600), (CX - 130, 610)], (40, 30, 54), 4)
            for cx, cy in EYES:
                _dot(p, cx, cy - 4, 20, WHITE)
                _dot(p, cx + 4, cy - 2, 8)

    elif kind == "catastrophizer":
        img, p = _core(kind, "spiral" if e == "scream" else e, antennae=False)
        _mouth(p, "scream") if e == "scream" else None
        _brows(p, "worried")
        p.shape([(CX - 46, 452), (CX + 46, 452), (CX + 46, 474), (CX - 46, 474)], (150, 150, 160), 4.5)
        p.shape(ellipse_pts(CX, 452, 36, 46, math.pi, 2 * math.pi, 30) + [(CX + 36, 452)], (255, 120, 70), 4.5)
        _dot(p, CX - 12, 428, 7, (255, 220, 190))
        for a in (-150, -120, -60, -30):
            r = math.radians(a)
            p.line([(CX + 62 * math.cos(r), 440 + 62 * math.sin(r)), (CX + 92 * math.cos(r), 440 + 92 * math.sin(r))], 4.5)
        for side in (-1, 1):  # flailing arms
            _arm(p, col, side, (CX + side * 230, 560))

    elif kind == "mind_reader":
        img, p = _core(kind, e, look=(0, -14), antennae=False, arms=False)
        tur = ellipse_pts(CX, 455, 130, 58, math.pi * 0.95, math.pi * 2.05, 40)
        p.shape(tur + [(CX + 120, 480), (CX - 120, 480)], (250, 240, 225), 5)
        for k in range(3):
            p.line(bez((CX - 110 + k * 30, 470), (CX - 60 + k * 30, 420), (CX + 20 + k * 30, 420), (CX + 80 + k * 20, 470)), 3, wobble=0.8)
        p.shape(ellipse_pts(CX, 440, 16, 20, n=20), (60, 200, 160), 4)
        p.line(bez((CX, 420), (CX + 10, 380), (CX + 40, 360), (CX + 50, 330)), 5)
        p.shape(ellipse_pts(CX, 772, 68, 64, n=40), (200, 225, 255), 5)
        p.line(ellipse_pts(CX - 18, 752, 30, 26, math.pi * 1.1, math.pi * 1.5, 12), 4, WHITE, wobble=0.4)
        p.shape([(CX - 46, 832), (CX + 46, 832), (CX + 36, 852), (CX - 36, 852)], (120, 80, 60), 4)
        for side in (-1, 1):
            _arm(p, col, side, (CX + side * 70, 760))

    elif kind == "fortune_teller":
        img, p = _core(kind, e, look=(10, 0), arms=False)
        _arm(p, col, -1, hand=False)
        hx, hy = CX + 220, 680
        for k, (ang, sym, c) in enumerate(((-30, "?", (210, 60, 70)), (-6, "!", INK), (18, "?", (210, 60, 70)))):
            cx_, cy_ = hx + k * 34 - 30, hy - 62 + abs(k - 1) * 10
            p.shape(_rot(cx_, cy_, 92, 130, ang), WHITE, 4.5)
            _rot_text(img, sym, cx_, cy_, ang, 70, c)
        _arm(p, col, 1, (hx - 10, hy + 10))

    elif kind == "all_or_nothing":
        img = _canvas()
        p = Pencil(img, 60 + list(BUGS).index(kind))
        white, dark = (250, 250, 250), DARK
        if HEAD_STYLE != "antennae":
            _antennae(p, white)
        for side, c in ((-1, white), (1, dark)):
            if HEAD_STYLE == "antennae":
                tip = (CX + side * 110, 300)
                p.line(bez((CX + side * 50, 470), (CX + side * 70, 400), (tip[0], tip[1] + 50), tip), 5)
                p.shape(ellipse_pts(*tip, 18, 18, n=20), c, 4.5)
            p.shape(ellipse_pts(CX + side * 70, 830, 44, 24, n=28), c, 4.5)
        pts = _body_pts()
        _poly(p, pts, white)
        _poly(p, [(max(x, CX), y) for x, y in pts], dark)
        p.line(pts, 6, closed=True)
        for side in (-1, 1):
            _arm(p, white if side < 0 else dark, side, hand=False)
        _eyes(p, e, white, skip=(1,))
        cx, cy = EYES[1]
        p.shape(ellipse_pts(cx, cy, *ER, n=40), WHITE, 5)
        _dot(p, cx - 4, cy + 20, 9)
        if e in ("smug", "angry"):
            lid = ellipse_pts(cx, cy, ER[0] + 7, ER[1] + 7, math.pi, 2 * math.pi, 30) + [(cx + ER[0] + 7, cy + 4), (cx - ER[0] - 7, cy + 4)]
            _poly(p, lid, dark)
            p.line([(cx - ER[0] + 4, cy + 4), (cx + ER[0] - 4, cy + 2)], 5, WHITE)
        _brows(p, e, (INK, WHITE))
        p.line([(CX - 26, 694), (CX, 694)], 5, INK)
        p.line([(CX, 694), (CX + 26, 694)], 5, WHITE)
        _rot_text(img, "0", CX - 80, 760, -6, 64, (200, 200, 205))
        _rot_text(img, "100", CX + 80, 760, 6, 54, (110, 108, 118))

    elif kind == "filter":
        img, p = _core(kind, e)
        (lx, ly), (rx, ry) = EYES
        p.line(ellipse_pts(lx, ly, 58, 64, n=40), 6)
        p.shape(ellipse_pts(rx, ry, 58, 64, n=40), (38, 38, 48), 6)
        p.line(ellipse_pts(rx - 18, ry - 20, 26, 24, math.pi * 1.1, math.pi * 1.5, 12), 4, (120, 120, 140), wobble=0.4)
        p.line([(lx + 56, ly - 10), (rx - 56, ry - 10)], 6)
        p.line([(lx - 56, ly - 8), (CX - 168, ly - 20)], 5)
        p.line([(rx + 56, ry - 8), (CX + 168, ry - 20)], 5)

    elif kind == "should":
        img, p = _core(kind, e, arms=False)
        hx, hy = CX + 210, 470
        _arm(p, col, 1, (hx, hy))
        p.line([(hx, hy - 12), (hx + 2, hy - 62)], 12)
        p.line([(hx, hy - 12), (hx + 2, hy - 60)], 7, col, wobble=0.3)
        paper = [(CX - 300, 600), (CX - 190, 594), (CX - 186, 800), (CX - 296, 806)]
        p.shape(paper, (252, 246, 228), 4.5)
        f = _font(30)
        p.d.text(((CX - 243) * SS, 630 * SS), "RULES", font=f, fill=(200, 50, 60), anchor="mm")
        for k in range(5):
            y = 664 + k * 26
            p.line([(CX - 282, y), (CX - 266, y)], 3, wobble=0.3)
            p.line([(CX - 256, y), (CX - 206, y)], 2.5, (120, 120, 130), wobble=0.4)
        _arm(p, col, -1, (CX - 214, 720))

    elif kind == "labeler":
        img, p = _core(kind, e, arms=False)
        for text, x, y, ang in (("LAZY", CX - 90, 500, -14), ("FAIL", CX + 110, 760, 12), ("USELESS", CX - 30, 790, -4)):
            p.shape(_rot(x, y, 34 + len(text) * 17, 46, ang), WHITE, 3.5, wobble=0.6)
            _rot_text(img, text, x, y, ang, 30, (210, 50, 60))
        _arm(p, col, -1, hand=False)
        hx, hy = CX + 226, 600
        p.shape(_rot(hx + 6, hy - 50, 104, 46, -20), WHITE, 3.5, wobble=0.6)
        _rot_text(img, "LOSER", hx + 6, hy - 50, -20, 30, (210, 50, 60))
        _arm(p, col, 1, (hx, hy))

    elif kind == "generalizer":
        base, _ = _core(kind, e)
        img = _canvas()
        _paste_copy(img, base, CX - 150, 0.82, 0.35)
        _paste_copy(img, base, CX - 80, 0.9, 0.6)
        img.alpha_composite(base)
        p = Pencil(img, 99)
        _rot_text(img, "always", CX + 230, 470, 10, 44)
        _rot_text(img, "never", CX + 240, 530, -6, 44)

    elif kind == "blamer":
        img, p = _core(kind, e, arms=False)
        _arm(p, col, -1, (CX - 190, 760))
        hx, hy = CX + 250, 630
        _arm(p, col, 1, (hx, hy))
        p.line([(hx + 10, hy - 4), (hx + 66, hy - 14)], 12)
        p.line([(hx + 10, hy - 4), (hx + 64, hy - 14)], 7, col, wobble=0.3)
        for k in range(3):
            y = hy - 50 + k * 34
            p.line([(hx + 90, y), (hx + 120, y - 6 + k * 6)], 4)

    elif kind == "know_it_all":
        img, p = _core(kind, e, look=(0, -6), antennae=False)
        crown = [(-80, 0), (-90, -80), (-45, -36), (0, -96), (45, -36), (90, -80), (80, 0)]
        a = math.radians(14)
        pts = [(CX + 40 + x * math.cos(a) - y * math.sin(a), 455 + x * math.sin(a) + y * math.cos(a)) for x, y in crown]
        p.shape(pts, (255, 214, 60), 5)
        for k, (x, y) in enumerate(((-45, -14), (0, -22), (45, -14))):
            _dot(p, CX + 40 + x * math.cos(a) - y * math.sin(a), 455 + x * math.sin(a) + y * math.cos(a), 9,
                 ((220, 60, 70), (70, 140, 230), (220, 60, 70))[k])

    elif kind == "echo":
        img = _canvas()
        p = Pencil(img, 60 + list(BUGS).index(kind))
        for side in (-1, 1):
            ear = ellipse_pts(CX + side * 175, 500, 80, 120, n=50)
            p.shape(ear, col, 6)
            p.shape(ellipse_pts(CX + side * 178, 506, 46, 80, n=40), (250, 170, 180), 4, wobble=1.0)
        base, _ = _core(kind, e, antennae=False)
        img.alpha_composite(base)
        p = Pencil(img, 98)
        for k in range(3):
            p.line(ellipse_pts(CX + 290, 480, 18 + k * 16, 30 + k * 18, -0.8, 0.8, 12), 4)

    elif kind == "anchor":
        img, p = _core(kind, e, arms=False)
        _arm(p, col, 1, hand=False)
        ax, ay = CX - 270, 720
        steel = (165, 170, 182)
        p.shape([(ax - 9, ay), (ax + 9, ay), (ax + 9, ay + 118), (ax - 9, ay + 118)], steel, 4)
        p.shape([(ax - 44, ay + 22), (ax + 44, ay + 22), (ax + 44, ay + 38), (ax - 44, ay + 38)], steel, 4)
        p.line(ellipse_pts(ax, ay - 14, 16, 16, n=20), 7)
        arc = ellipse_pts(ax, ay + 80, 62, 50, math.pi * 0.05, math.pi * 0.95, 30)
        p.line(arc, 14)
        p.line(arc, 7, steel, wobble=0.3)
        for side in (-1, 1):
            tx = ax + side * 62
            p.shape([(tx - 14, ay + 90), (tx + 14, ay + 90), (tx, ay + 66)], steel, 4)
        hx, hy = CX - 214, 700
        for k in range(1, 6):
            t = k / 6
            x, y = hx + (ax - hx) * t, hy + (ay - 30 - hy) * t + math.sin(t * math.pi) * 20
            p.line(ellipse_pts(x, y, 10, 6 if k % 2 else 10, n=16), 4, wobble=0.4)
        _arm(p, col, -1, (hx, hy))

    elif kind == "hoarder":
        img, p = _core(kind, e, look=(-14, 0), arms=False)
        box = [(CX - 130, 660), (CX + 130, 660), (CX + 130, 830), (CX - 130, 830)]
        p.shape(box, (205, 160, 105), 5)
        p.shape([(CX - 130, 660), (CX - 100, 630), (CX + 100, 630), (CX + 130, 660)], (225, 185, 130), 4.5)
        p.shape([(CX - 18, 660), (CX + 18, 660), (CX + 18, 830), (CX - 18, 830)], (235, 220, 170), 3, wobble=0.5)
        for side in (-1, 1):
            _arm(p, col, side, (CX + side * 110, 720))
        for side in (-1, 1):
            p.line([(CX + side * 176, 560), (CX + side * 196, 548)], 4)

    elif kind == "sunk_cost":
        img, p = _core(kind, e, arms=False)
        for side in (-1, 1):
            _arm(p, col, side, (CX + side * 230, 520))
            for k in range(2):
                p.line([(CX + side * (262 + k * 18), 490 - k * 22), (CX + side * (282 + k * 18), 476 - k * 22)], 4)
        top = [(CX - 300 + k * 20, 735 + 9 * math.sin(k * 1.1)) for k in range(31)]
        mud = top + bez((CX + 300, 735), (CX + 360, 780), (CX + 300, 860), (CX + 180, 870))[1:] \
            + bez((CX - 180, 870), (CX - 300, 860), (CX - 360, 780), (CX - 300, 735))
        p.shape(mud, (110, 86, 64), 5)
        for x, w in ((CX - 230, 60), (CX + 210, 70), (CX - 20, 110)):
            p.line(ellipse_pts(x, 790, w, 10, math.pi * 0.1, math.pi * 0.9, 20), 3, (150, 120, 92))
        for x, y in ((CX - 210, 742), (CX + 240, 746)):
            p.shape(ellipse_pts(x, y, 30, 12, n=24), (250, 205, 70), 3.5)
            p.d.text((x * SS, (y - 1) * SS), "$", font=_font(22), fill=(150, 110, 30), anchor="mm")

    elif kind == "halo":
        img, p = _core(kind, e, antennae=False)
        p.line(ellipse_pts(CX, 395, 100, 26, n=50), 18)
        p.line(ellipse_pts(CX, 395, 100, 26, n=50), 11, (255, 210, 60), wobble=0.4)
        for x, y, r in ((CX - 230, 470, 26), (CX + 220, 520, 32), (CX + 250, 760, 20), (CX - 240, 720, 22)):
            _sparkle(p, x, y, r)

    elif kind == "planner":
        img, p = _core(kind, e, arms=False)
        _arm(p, col, -1, hand=False)
        hx, hy = CX + 222, 640
        face = (ellipse_pts(hx, hy - 60, 66, 62, math.pi, 2 * math.pi, 30)
                + bez((hx + 66, hy - 60), (hx + 70, hy + 10), (hx + 40, hy + 30), (hx + 46, hy + 110))[1:]
                + bez((hx + 46, hy + 110), (hx + 30, hy + 120), (hx + 10, hy + 40), (hx - 20, hy + 20))[1:]
                + bez((hx - 20, hy + 20), (hx - 50, hy + 10), (hx - 66, hy - 20), (hx - 66, hy - 60))[1:])
        p.shape(face, (255, 244, 210), 5)
        p.line([(hx, hy - 60), (hx, hy - 104)], 5)
        p.line([(hx, hy - 60), (hx + 34, hy - 46)], 5)
        for a in range(0, 360, 90):
            r = math.radians(a - 90)
            if a == 180:
                continue
            p.line([(hx + 50 * math.cos(r), hy - 60 + 50 * math.sin(r)), (hx + 58 * math.cos(r), hy - 60 + 58 * math.sin(r))], 4)
        _dot(p, hx + 44, hy + 128, 8, (255, 244, 210))
        p.line(ellipse_pts(hx + 44, hy + 128, 8, 8, n=16), 3)
        p.d.text(((hx - 20) * SS, (hy + 150) * SS), "FRI", font=_font(34), fill=INK, anchor="mm")
        _arm(p, col, 1, (hx - 50, hy - 10))

    elif kind == "follower":
        base, _ = _core(kind, e, look=(16, 0))
        img = _canvas()
        _paste_copy(img, base, CX + 340, 0.52)
        _paste_copy(img, base, CX + 215, 0.72)
        img.alpha_composite(base)
        p = Pencil(img, 97)

    else:
        img, p = _core(kind, e)
    return img


def draw(kind: str, expression: str | None = None, height: int = 600) -> Image.Image:
    """Return a bug as a transparent RGBA image `height` pixels tall."""
    img = draw_full(kind, expression).crop((0, 260 * SS, W * SS, 900 * SS))
    w = int(height * img.width / img.height)
    return img.resize((w, height), Image.LANCZOS)
