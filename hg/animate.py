"""Animated scenes: hand-drawn set + characters + bugs, with simple 'limited animation'.

Each scene in the script can carry these lines:
  > set: office                      background from hg/sets.py
  > cast: sarah:happy -> sarah:worried, bug:impostor:worried
                                     who is on screen; "a -> b" switches expression mid-scene
  > switch: 0.3                      when the "->" switches happen (fraction of the scene, snapped to a paragraph)
  > enter: bug:filter@6              actor appears at the start of paragraph 6 (0-based) instead of at once

What moves: gentle breathing/bobbing, blinking, expression changes, bugs popping in with a glitch,
a patched bug shrinking a little, and camera cuts between a wide and a close shot on paragraph changes.
Frames are piped straight into ffmpeg, so a scene costs one encode.
"""
import math
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops

from . import bugs, sets, sketch
from .config import FPS

PERSON_W_RATIO = sketch.W0 / 690      # width/height of a cropped person sprite
BUG_W_RATIO = bugs.W / 640            # width/height of a cropped bug sprite


@dataclass
class Actor:
    name: str          # "sarah" or "impostor"
    is_bug: bool
    expr0: str | None
    expr1: str | None = None
    enter_para: int = 0
    x: float = 0.5     # world position (fraction of width)
    seed: int = 0


def parse_cast(text: str) -> list[Actor]:
    actors: dict[str, Actor] = {}
    for item in [c.strip() for c in text.split(",") if c.strip()]:
        parts = [p.strip() for p in item.split("->")]
        first = parts[0].split(":")
        is_bug = first[0] == "bug"
        if is_bug:
            name, e0 = first[1], (first[2] if len(first) > 2 else None)
        else:
            name, e0 = first[0], (first[1] if len(first) > 1 else None)
        e1 = parts[1].split(":")[-1] if len(parts) > 1 else None
        actors[name] = Actor(name, is_bug, e0, e1, seed=len(actors))
    return list(actors.values())


def paragraph_starts(narration: str, words, seconds: float) -> list[float]:
    paras = [p for p in narration.split("\n\n") if p.strip()]
    counts = [len(p.split()) for p in paras]
    total = sum(counts) or 1
    starts, cum = [], 0
    for c in counts:
        if not words:
            starts.append(seconds * cum / total)
        else:
            idx = min(len(words) - 1, round(cum * len(words) / total))
            starts.append(0.0 if cum == 0 else words[idx][0])
        cum += c
    return starts


def _layout(actors: list[Actor], portrait: bool):
    people = [a for a in actors if not a.is_bug]
    bugs_ = [a for a in actors if a.is_bug]
    order = people + bugs_
    n = len(order)
    if n == 1:
        order[0].x = 0.5 if not order[0].is_bug else 0.45
        return
    span = (0.5 if portrait else 0.36) if n == 2 else min(0.64, 0.2 * (n - 1))
    for i, a in enumerate(order):
        a.x = 0.5 - span / 2 + span * i / (n - 1)


class SceneRenderer:
    def __init__(self, scene, seconds: float, words, size, labeled: set | None = None, seed: int = 0):
        self.w, self.h = size
        self.portrait = self.h > self.w
        self.seconds = seconds
        self.rng = random.Random(seed)
        ex = scene.extra
        self.set_name = ex.get("set", "office")
        self.actors = parse_cast(ex.get("cast", ""))
        _layout(self.actors, self.portrait)
        self.paras = paragraph_starts(scene.narration, words, seconds)
        for spec in [s.strip() for s in ex.get("enter", "").split(",") if s.strip()]:
            who, _, para = spec.partition("@")
            name = who.split(":")[-1]
            for a in self.actors:
                if a.name == name:
                    a.enter_para = int(para or 0)
        frac = float(ex.get("switch", 0.5))
        self.t_switch = min(self.paras, key=lambda t: abs(t - frac * seconds)) if self.paras else frac * seconds
        if self.t_switch <= 0.01 and len(self.paras) > 1:
            self.t_switch = self.paras[1]
        self.enter_t = {a.name: (self.paras[a.enter_para] if a.enter_para < len(self.paras) else 0.0) for a in self.actors}
        labeled = labeled if labeled is not None else set()
        self.label_for = {a.name for a in self.actors if a.is_bug and a.name not in labeled}
        labeled.update(self.label_for)
        self._sprites = {}
        self._build_world()
        self._build_shots()

    # ---- world and camera ----
    def _build_world(self):
        bg = sets.draw(self.set_name)
        front = sets.front(self.set_name)
        # cover-fit the 16:9 set into the frame
        s = max(self.w / bg.width, self.h / bg.height)
        self.world_w, self.world_h = int(bg.width * s), int(bg.height * s)
        self.bg = bg.resize((self.world_w, self.world_h), Image.LANCZOS).convert("RGB")
        self.front = front.resize((self.world_w, self.world_h), Image.LANCZOS) if front else None
        self.ox = (self.world_w - self.w) / 2  # world x of the frame's left edge in the wide shot
        unit = self.world_h / 1080
        self.person_h = int((0.66 if not self.portrait else 0.44) * self.world_h)
        self.bug_h = int((0.38 if not self.portrait else 0.27) * self.world_h)
        if self.set_name == "meeting":
            self.person_h = int(self.person_h * 1.0)
        self.person_bottom = self.world_h + int(30 * unit)
        self.bug_feet = int(self.world_h * (0.975 if self.set_name != "savanna" else 0.93))
        if self.set_name == "meeting":
            self.bug_feet = int(self.world_h * 0.86)

    def _world_x(self, a: Actor):
        if self.portrait:
            return self.ox + a.x * self.w
        return a.x * self.world_w

    def _focus(self):
        bugs_ = [a for a in self.actors if a.is_bug]
        a = bugs_[0] if bugs_ else (self.actors[0] if self.actors else None)
        if a is None:
            return self.world_w / 2, self.world_h / 2, None
        top = (self.bug_feet - self.bug_h * 0.75) if a.is_bug else (self.person_bottom - self.person_h * 0.75)
        xs = [self._world_x(b) for b in self.actors]
        return (min(xs) + max(xs)) / 2, top, a  # frame the whole group, so nobody is cut at the edge

    def _build_shots(self):
        """Paragraph-driven cuts between a wide shot and a close shot."""
        cuts = [0.0]
        for t in self.paras[1:]:
            if t - cuts[-1] >= 4.0 and self.seconds - t >= 3.0:
                cuts.append(t)
        self.cuts = cuts
        fx, fy, self.focus_actor = self._focus()
        wide = (1.0, self.ox + self.w / 2, self.world_h - self.h / 2)
        xs = [self._world_x(b) for b in self.actors] or [fx]
        group_w = max(xs) - min(xs) + self.person_h * 0.9
        z = max(1.0, min(1.3, self.w / max(1, group_w)))
        vw, vh = self.w / z, self.h / z
        cx = min(max(fx, vw / 2), self.world_w - vw / 2)
        cy = min(max(fy + vh * 0.18, vh / 2), self.world_h - vh / 2)
        close = (z, cx, cy)
        self.shots = []
        for i, _ in enumerate(cuts):
            cam = wide if (i % 2 == 0 or self.focus_actor is None) else close
            self.shots.append(cam)
        self._views = {}

    def _view(self, cam):
        if cam not in self._views:
            z, cx, cy = cam
            vw, vh = self.w / z, self.h / z
            box = (cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2)
            bg = self.bg.resize((self.w, self.h), Image.LANCZOS, box=box)
            fr = self.front.resize((self.w, self.h), Image.LANCZOS, box=box) if self.front else None
            self._views[cam] = (bg, fr, {})
        return self._views[cam]

    def _to_screen(self, cam, x, y):
        z, cx, cy = cam
        return (x - cx) * z + self.w / 2, (y - cy) * z + self.h / 2

    # ---- sprites ----
    def _sprite(self, a: Actor, expr, blink, height):
        key = (a.name, expr, blink, height)
        if key not in self._sprites:
            if a.is_bug:
                self._sprites[key] = bugs.draw(a.name, expr, height=height, blink=blink)
            else:
                self._sprites[key] = sketch.draw(a.name, expr, height=height, blink=blink)
        return self._sprites[key]

    def _label(self, cam, a: Actor, sx, sy, height):
        view = self._view(cam)[2]
        key = (a.name, round(sx), round(sy), height)
        if key not in view:
            img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            size = int(height * 0.16)
            tx = min(self.w - size * 3.2, sx + height * 0.55)
            ty = max(size, sy - height * 0.95)
            sketch.label(img, bugs.BUGS[a.name][0], (int(tx), int(ty)), size=size,
                         arrow_to=(int(sx + height * 0.18), int(sy - height * 0.62)))
            view[key] = img
        return view[key]

    @staticmethod
    def _glitch(sprite: Image.Image, rng: random.Random, strength: float) -> Image.Image:
        pad = 40
        out = Image.new("RGBA", (sprite.width + pad * 2, sprite.height + pad * 2), (0, 0, 0, 0))
        alpha = sprite.getchannel("A").point(lambda v: int(v * 0.55))
        for color, dx in (((255, 46, 136), -1), ((90, 183, 230), 1)):
            ghost = Image.new("RGBA", sprite.size, color + (0,))
            ghost.putalpha(alpha)
            out.alpha_composite(ghost, (pad + int(dx * rng.randint(6, 18) * strength), pad + rng.randint(-4, 4)))
        y = 0
        while y < sprite.height:
            hgt = rng.randint(sprite.height // 12, sprite.height // 5)
            dx = int(rng.randint(-22, 22) * strength) if rng.random() < 0.6 else 0
            strip = sprite.crop((0, y, sprite.width, min(sprite.height, y + hgt)))
            out.alpha_composite(strip, (pad + dx, pad + y))
            y += hgt
        return out

    # ---- frames ----
    def frame(self, t: float) -> Image.Image:
        shot = max(i for i, c in enumerate(self.cuts) if c <= t)
        cam = self.shots[shot]
        z = cam[0]
        bg, fr, _ = self._view(cam)
        img = bg.copy()
        labels = []
        for a in self.actors:
            t0 = self.enter_t[a.name]
            if t < t0:
                continue
            switched = a.expr1 and t >= self.t_switch
            expr = a.expr1 if switched else a.expr0
            period = 3.6 + (a.seed * 0.7) % 1.8
            blink = ((t + a.seed * 1.3) % period) < 0.13
            if a.is_bug:
                scale = 1.0
                if switched and a.expr1 == "happy":
                    k = min(1.0, (t - self.t_switch) / 0.6)
                    scale = 1.0 - 0.18 * k
                height = int(self.bug_h * z * scale)
                height -= height % 4
                bob = -abs(math.sin(2 * math.pi * (t + a.seed) / 1.6)) * 10 * z
                wx, wy = self._world_x(a), self.bug_feet
            else:
                height = int(self.person_h * z)
                bob = math.sin(2 * math.pi * (t + a.seed * 0.9) / 3.2) * 4 * z
                if a.expr1 and abs(t - self.t_switch) < 0.25:  # small hop on the expression change
                    bob -= math.sin(math.pi * (t - self.t_switch + 0.25) / 0.5) * 14 * z
                wx, wy = self._world_x(a), self.person_bottom
            spr = self._sprite(a, expr, blink, height)
            sx, sy = self._to_screen(cam, wx, wy)
            x, y = int(sx - spr.width / 2), int(sy - spr.height + bob)
            age = t - t0
            if a.is_bug and age < 0.5:
                g = self._glitch(spr, self.rng, 1.0 - age / 0.5)
                img.paste(g, (x - 40, y - 40), g)
            else:
                img.paste(spr, (x, y), spr)
            if a.name in self.label_for and 0.6 < age < 5.5:
                labels.append(self._label(cam, a, sx, sy, height))
        if fr is not None:
            img.paste(fr, (0, 0), fr)
        for lab in labels:
            img.paste(lab, (0, 0), lab)
        return img

    def render(self, out: Path, crf: int = 21):
        frames = max(1, int(round(self.seconds * FPS)))
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{self.w}x{self.h}", "-r", str(FPS), "-i", "-",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p", "-an", str(out)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for f in range(frames):
                proc.stdin.write(self.frame(f / FPS).tobytes())
        finally:
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg failed while rendering {out}")
        return out


def is_animated(scene) -> bool:
    return "set" in scene.extra or "cast" in scene.extra


def render_scene(scene, seconds, words, out: Path, size, labeled=None, seed=0) -> Path:
    return SceneRenderer(scene, seconds, words, size, labeled, seed).render(out)


def thumbnail(scene, text: str, out: Path) -> Path:
    """YouTube thumbnail in the cartoon style: the scene's set, its first person big on the right,
    its first bug beside them, and the hook text in big white letters with a navy outline on the left."""
    from PIL import ImageDraw, ImageFilter, ImageFont
    from .config import BRAND_LIGHT, BRAND_NAVY, CHANNEL, font_sans

    w, h = 1280, 720
    img = sets.draw(scene.extra.get("set", "office")).resize((w, h), Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(3)).convert("RGBA")
    actors = parse_cast(scene.extra.get("cast", ""))
    person = next((a for a in actors if not a.is_bug), None)
    bug = next((a for a in actors if a.is_bug), None)
    if person:
        spr = sketch.draw(person.name, "worried", height=int(h * 0.92))
        img.alpha_composite(spr, (int(w * 0.70 - spr.width / 2), h - spr.height + 20))
    if bug:
        spr = bugs.draw(bug.name, bug.expr0, height=int(h * 0.5))
        img.alpha_composite(spr, (int(w * 0.93 - spr.width / 2), h - spr.height - 10))
    d = ImageDraw.Draw(img)
    words = text.upper().split()
    lines, cur = [], []
    for wd in words:
        cur.append(wd)
        if len(" ".join(cur)) >= 4:
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    size = 170 if len(lines) <= 2 else 140
    font = ImageFont.truetype(font_sans(), size)
    while max(d.textlength(l, font=font) for l in lines) > w * 0.56 and size > 60:
        size -= 6
        font = ImageFont.truetype(font_sans(), size)
    y = h / 2 - len(lines) * size * 1.05 / 2
    for i, line in enumerate(lines):
        color = BRAND_LIGHT if i == len(lines) - 1 else (255, 255, 255)
        d.text((48, y + i * size * 1.05), line, font=font, fill=color, stroke_width=max(6, size // 12), stroke_fill=BRAND_NAVY)
    tag = ImageFont.truetype(font_sans(), 28)
    label = f" {CHANNEL} "
    tw = d.textlength(label, font=tag)
    d.rectangle([40, h - 76, 40 + tw, h - 34], fill=BRAND_NAVY)
    d.text((40, h - 74), label, font=tag, fill=BRAND_LIGHT)
    img.convert("RGB").save(out, quality=92)
    return out
