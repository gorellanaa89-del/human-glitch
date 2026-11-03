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
import re
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
    # a scene cut short for a test keeps only its first words: map paragraphs one word to one word
    scale = len(words) / total if words and len(words) >= 0.9 * total else 1.0
    for c in counts:
        if not words:
            starts.append(seconds * cum / total)
        elif round(cum * scale) >= len(words):
            starts.append(seconds + 1.0)  # paragraph falls after the cut: never reached
        else:
            starts.append(0.0 if cum == 0 else words[round(cum * scale)][0])
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
    span = (0.42 if portrait else 0.36) if n == 2 else min(0.64, 0.2 * (n - 1))
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
        self._tilts = {}
        self._labels = {}
        self._build_world()
        self.words = self._ensure_words(scene.narration, words)
        self.quotes = self._quotes()
        self.notes = self._notes(ex)
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
        self.person_h = int((0.66 if not self.portrait else 0.50) * self.world_h)
        self.bug_h = int((0.38 if not self.portrait else 0.30) * self.world_h)
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

    # ---- timing helpers ----
    def _ensure_words(self, narration, words):
        if words:
            return list(words)
        toks = narration.split()  # silent test renders: spread the words evenly
        step = self.seconds / max(1, len(toks))
        return [(i * step, (i + 0.8) * step, t) for i, t in enumerate(toks)]

    def _quotes(self):
        """Spans of quoted speech in the narration: (start, end, text, speaker)."""
        out, cur = [], None
        for i, (s, e, t) in enumerate(self.words):
            if cur is None and t[:1] in "\"“":
                cur = [i]
            if cur is not None:
                core = t.rstrip(".,!?;:")
                closes = core[-1:] in "\"”" and (i > cur[0] or sum(core.count(q) for q in "\"“”") >= 2)
                if closes or i - cur[0] > 60:
                    cur.append(i)
                    a, b = cur
                    out.append((a, b))
                    cur = None
        spans = []
        names = {a.name: a for a in self.actors}
        aliases = {a.name: (bugs.BUGS[a.name][0].split()[-1].lower() if a.is_bug else a.name) for a in self.actors}
        for a, b in out:
            before = " ".join(w[2] for w in self.words[max(0, a - 14):a]).lower()
            speaker, best = None, -1
            for name, alias in aliases.items():
                k = before.rfind(alias)
                if k > best:
                    speaker, best = names[name], k
            if b - a + 1 < (2 if speaker else 3):  # very short quotes only when someone is named saying them
                continue
            t0 = self.words[a][0]
            if speaker is None or self.enter_t.get(speaker.name, 0) > t0:
                vis = [x for x in self.actors if self.enter_t[x.name] <= t0]
                bug_vis = [x for x in vis if x.is_bug]
                speaker = bug_vis[0] if bug_vis else (vis[0] if vis else None)
            if speaker is None:
                continue
            idx = list(range(a, b + 1))
            step = -(-len(idx) // -(-len(idx) // 11))  # even chunks of at most 11 words
            for k in range(0, len(idx), step):  # long quotes become a sequence of bubbles
                chunk = idx[k:k + step]
                text = re.sub(r'^[\"“]+|[\"”]+[.,;:]*$', "", " ".join(self.words[j][2] for j in chunk))
                spans.append((self.words[chunk[0]][0], self.words[chunk[-1]][1] + 0.35, text, speaker))
        return spans

    def _notes(self, ex):
        notes = []
        for key, val in ex.items():
            if key.startswith("note@"):
                para = int(key.split("@")[1])
                if para < len(self.paras):
                    t0 = self.paras[para]
                    t1 = self.paras[para + 1] if para + 1 < len(self.paras) else self.seconds
                    title, _, sub = val.partition("|")
                    notes.append((t0 + 0.2, min(t1, t0 + 4.2), title.strip(), sub.strip()))
        return notes

    # ---- shots ----
    def _cam_for(self, kind, actor=None):
        portrait = self.portrait
        if kind == "wide":
            return (1.0, self.ox + self.w / 2, self.world_h - self.h / 2)
        if kind == "group":
            xs = [self._world_x(b) for b in self.actors]
            group_w = max(xs) - min(xs) + self.person_h * 0.9
            z = max(1.0, min(1.3, self.w / max(1, group_w)))
            fx, fy, _ = self._focus()
            return self._clamp(z, fx, fy + (self.h / z) * 0.18)
        if actor.is_bug:
            z = {"mid": 1.5, "solo": 1.95, "close": 2.5}[kind] * (0.7 if portrait else 1.0)
            return self._clamp(z, self._world_x(actor), self.bug_feet - self.bug_h * (0.42 if kind != "close" else 0.55))
        z = {"mid": 1.35, "solo": 1.7, "close": 2.3}[kind] * (0.77 if portrait else 1.0)
        head = {"mid": 0.5, "solo": 0.52, "close": 0.6}[kind]
        return self._clamp(z, self._world_x(actor), self.person_bottom - self.person_h * head)

    def _clamp(self, z, cx, cy):
        vw, vh = self.w / z, self.h / z
        return (z, min(max(cx, vw / 2), self.world_w - vw / 2), min(max(cy, vh / 2), self.world_h - vh / 2))

    def _build_shots(self):
        """Cut every few seconds on sentence ends, mixing wide, group and single close-ups that drift slowly.
        Quotes cut to the speaker; entrances cut to a shot that shows the newcomer."""
        W = self.words
        forced = {}
        for t0, t1, text, spk in self.quotes:
            forced[round(t0, 2)] = ("solo", spk)
        for a in self.actors:
            if self.enter_t[a.name] > 0:
                forced[round(self.enter_t[a.name], 2)] = ("enter", a)
        cuts = [0.0]
        kinds = [("wide", None)]
        for i, (s, e, t) in enumerate(W):
            nxt = W[i + 1][0] if i + 1 < len(W) else None
            if nxt is None or self.seconds - nxt < 1.5:
                continue
            gap = nxt - cuts[-1]
            key = round(nxt, 2)
            if key in forced and gap >= 1.2:
                cuts.append(nxt); kinds.append(forced[key]); continue
            # end of a quote: go back out to a wider shot
            if any(abs(q[1] - 0.35 - e) < 0.01 for q in self.quotes) and gap >= 1.2:
                cuts.append(nxt); kinds.append(None); continue
            sentence_end = t.rstrip("\"”")[-1:] in ".?!"
            if (sentence_end and gap >= 2.4) or (t[-1:] in ",;:" and gap >= 3.8) or gap >= 5.0:
                cuts.append(nxt); kinds.append(None)
        # fill free choices, never repeating the previous framing
        options = [("wide", None)] + ([("group", None)] if len(self.actors) > 1 else []) + \
            [(k, a) for a in self.actors for k in ("mid", "solo", "close")]
        prev = None
        self.cams = []
        for i, (c, k) in enumerate(zip(cuts, kinds)):
            if k is not None and k[0] == "enter":
                k = ("wide", None) if len(self.actors) > 2 else ("group", None)
            if k is None:
                avail = [o for o in options if _fresh(o, prev) and (o[1] is None or self.enter_t[o[1].name] <= c + 0.01)]
                k = self.rng.choice(avail) if avail else ("wide", None)
            if len(self.actors) == 0:
                k = ("wide", None)
            z, cx, cy = self._cam_for(k[0], k[1])
            end = cuts[i + 1] if i + 1 < len(cuts) else self.seconds
            drift = (self.w / z) * (0.035 if k[0] != "wide" else 0.02) * (1 if i % 2 == 0 else -1)
            z, cx0, cy0 = self._clamp(z, cx - drift / 2, cy)
            z, cx1, cy1 = self._clamp(z, cx + drift / 2, cy)
            self.cams.append((c, end, z, cx0, cy0, cx1, cy1))
            prev = k
        self.cuts = cuts
        self._shot_bgs = {}
        self._bubble_cache = {}
        self._note_cache = {}

    def _shot_layers(self, i):
        if i not in self._shot_bgs:
            c, end, z, cx0, cy0, cx1, cy1 = self.cams[i]
            vw, vh = self.w / z, self.h / z
            x0 = min(cx0, cx1) - vw / 2
            x1 = max(cx0, cx1) + vw / 2
            y0 = cy0 - vh / 2
            size = (int(round((x1 - x0) * z)), self.h)
            box = (x0, y0, x1, y0 + vh)
            bg = self.bg.resize(size, Image.LANCZOS, box=box)
            fr = self.front.resize(size, Image.LANCZOS, box=box) if self.front else None
            self._shot_bgs = {i: (bg, fr, x0)}  # keep only the current shot in memory
        return self._shot_bgs[i]

    def _bubble(self, qi, text, hx, hy, z):
        key = (qi, round(hx), round(hy))
        if key not in self._bubble_cache:
            from PIL import ImageDraw, ImageFont
            fsize = int(self.h * (0.034 if self.portrait else 0.05))
            font = ImageFont.truetype(str(sketch.HAND_FONT), fsize)
            d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            maxw = self.w * (0.7 if self.portrait else 0.36)
            lines, cur = [], ""
            for wd in text.split():
                trial = (cur + " " + wd).strip()
                if d.textlength(trial, font=font) > maxw and cur:
                    lines.append(cur); cur = wd
                else:
                    cur = trial
            lines.append(cur)
            tw = max(d.textlength(l, font=font) for l in lines)
            th = len(lines) * fsize * 1.15
            bw, bh = tw + fsize * 1.6, th + fsize * 1.2
            side = 1 if hx < self.w * 0.55 else -1
            bx = hx + side * (bw / 2 + self.w * 0.05)
            bx = min(max(bx, bw / 2 + 20), self.w - bw / 2 - 20)
            by = max(bh / 2 + 24, min(hy - bh * 0.35, self.h * 0.45))
            img = Image.new("RGBA", (self.w * sketch.SS, self.h * sketch.SS), (0, 0, 0, 0))
            p = sketch.Pencil(img, 31 + qi)
            pts = sketch.ellipse_pts(bx, by, bw / 2 * 1.08, bh / 2 * 1.12, n=60)
            tip = (hx + side * self.w * 0.03, hy - self.h * 0.02)
            base_a = (bx - side * bw * 0.18, by + bh * 0.3)
            base_b = (bx - side * bw * 0.02, by + bh * 0.42)
            p.shape([base_a, tip, base_b], (255, 255, 255), 3.5, wobble=0.8)
            p.shape(pts, (255, 255, 255), 4.0, wobble=1.0)
            img = img.resize((self.w, self.h), Image.LANCZOS)
            dd = ImageDraw.Draw(img)
            for li, line in enumerate(lines):
                dd.text((bx, by - th / 2 + (li + 0.5) * fsize * 1.15), line, font=font, fill=sketch.INK, anchor="mm")
            bbox = img.getbbox()
            self._bubble_cache = {key: (img.crop(bbox), bbox[:2])}
        return self._bubble_cache[key]

    def _note(self, title, sub):
        """A lined paper card with a big handwritten fact. It slides over the scene in the upper part of
        the frame, so it never covers the subtitles at the bottom."""
        key = (title, sub)
        if key not in self._note_cache:
            from PIL import ImageDraw, ImageFilter, ImageFont
            from .config import BRAND_BLUE, BRAND_GRAY
            cw = int(self.w * (0.86 if self.portrait else 0.44))
            big = int(self.h * (0.07 if self.portrait else 0.12))
            font = ImageFont.truetype(str(sketch.HAND_FONT), big)
            d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            while d0.textlength(title, font=font) > cw * 0.84 and big > 30:
                big -= 4
                font = ImageFont.truetype(str(sketch.HAND_FONT), big)
            sf = ImageFont.truetype(str(sketch.HAND_FONT), int(big * 0.42))
            ch = int(big * (2.3 if sub else 1.7))
            pad = 40
            card = Image.new("RGBA", (cw + pad * 2, ch + pad * 2), (0, 0, 0, 0))
            shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle((pad + 10, pad + 14, pad + cw + 10, pad + ch + 14), 10, fill=(5, 28, 44, 90))
            card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
            d = ImageDraw.Draw(card)
            d.rounded_rectangle((pad, pad, pad + cw, pad + ch), 10, fill=(250, 247, 238, 255), outline=sketch.INK + (255,), width=3)
            for y in range(pad + int(ch * 0.2), pad + ch - 6, int(big * 0.42)):
                d.line([(pad + 4, y), (pad + cw - 4, y)], fill=(222, 229, 240, 255), width=2)
            d.line([(pad + int(cw * 0.08), pad + 3), (pad + int(cw * 0.08), pad + ch - 3)], fill=(240, 190, 190, 255), width=3)
            cx = pad + cw / 2
            ty = pad + big * 0.85
            d.text((cx, ty), title, font=font, fill=sketch.INK + (255,), anchor="mm")
            tl = d.textlength(title, font=font)
            yl = ty + big * 0.6
            d.line([(cx - tl / 2, yl), (cx - tl / 6, yl + 5), (cx + tl / 6, yl - 3), (cx + tl / 2, yl + 3)], fill=BRAND_BLUE + (255,), width=6, joint="curve")
            if sub:
                d.text((cx, yl + big * 0.62), sub, font=sf, fill=BRAND_GRAY + (255,), anchor="mm")
            card = card.rotate(-2.5 if len(self._note_cache) % 2 == 0 else 2.0, resample=Image.BICUBIC, expand=True)
            self._note_cache[key] = card
        return self._note_cache[key]

    def _note_pos(self, card, t, t0, t1):
        """Slide in from the left with a little overshoot, hold, then slide back out."""
        x_rest = int(self.w * (0.07 if self.portrait else 0.04))
        y = int(self.h * (0.06 if not self.portrait else 0.08))
        x_off = -card.width - 20
        if t - t0 < 0.4:
            u = (t - t0) / 0.4
            k = 1 - (1 - u) ** 3 + 0.08 * math.sin(math.pi * u)
            return int(x_off + (x_rest - x_off) * k), y
        if t1 - t < 0.3:
            u = 1 - (t1 - t) / 0.3
            return int(x_rest + (x_off - x_rest) * u * u), y
        return x_rest, y + int(4 * math.sin(2 * math.pi * (t - t0) / 2.4))

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

    def _tilt(self, spr, a, expr, blink, height, angle):
        """Rotate a sprite a few degrees around its feet (cached in 1-degree steps).
        Returns the rotated sprite and the x shift that keeps the feet in place."""
        deg = round(angle * 2) / 2
        if deg == 0:
            return spr, 0
        key = (a.name, expr, blink, height, deg)
        if key not in self._tilts:
            if len(self._tilts) > 400:
                self._tilts.clear()
            self._tilts[key] = spr.rotate(deg, resample=Image.BICUBIC, expand=True)
        r = self._tilts[key]
        # rotating about the centre moves the feet sideways; shift back so they stay put,
        # and drop the extra height that expand adds below the feet
        dx = -spr.height / 2 * math.sin(math.radians(deg))
        pad_y = (r.height - spr.height) / 2
        return r.crop((0, 0, r.width, int(r.height - pad_y))), dx

    def _label(self, cam, a: Actor, sx, sy, height):
        view = self._labels
        key = (a.name, round(sx / 3), round(sy / 3), height)
        if len(view) > 40:
            view.clear()
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
        i = max(k for k, c in enumerate(self.cuts) if c <= t)
        c, end, z, cx0, cy0, cx1, cy1 = self.cams[i]
        u = 0.0 if end - c < 0.01 else (t - c) / (end - c)
        u = u * u * (3 - 2 * u)
        cx, cy = cx0 + (cx1 - cx0) * u, cy0 + (cy1 - cy0) * u
        bg, fr, x0 = self._shot_layers(i)
        off = int(round((cx - self.w / z / 2 - x0) * z))
        off = min(max(off, 0), bg.width - self.w)
        img = bg.crop((off, 0, off + self.w, self.h))
        cam = (z, cx, cy)
        labels, heads = [], {}
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
                bob = -abs(math.sin(2 * math.pi * (t + a.seed) / 1.6)) * 16 * z
                angle = 6 * math.sin(2 * math.pi * (t + a.seed) / 2.2)
                sway = 14 * z * math.sin(2 * math.pi * (t + a.seed * 0.5) / 3.1)
                wx, wy = self._world_x(a), self.bug_feet
            else:
                height = int(self.person_h * z)
                height -= height % 2
                # idle: breathe, lean from side to side and shift weight, each person at their own pace
                ph = t + a.seed * 0.9
                bob = math.sin(2 * math.pi * ph / 2.6) * 7 * z
                angle = 2.2 * math.sin(2 * math.pi * ph / 3.4) + 1.2 * math.sin(2 * math.pi * ph / 1.7)
                sway = 10 * z * math.sin(2 * math.pi * ph / 4.1)
                talking = any(q0 <= t < q1 and spk is a for q0, q1, _, spk in self.quotes)
                if talking:  # the speaker bounces and nods while the bubble is up
                    bob -= abs(math.sin(2 * math.pi * t / 0.42)) * 12 * z
                    angle += 3 * math.sin(2 * math.pi * t / 0.84)
                if a.expr1 and abs(t - self.t_switch) < 0.35:  # a hop on the expression change
                    bob -= math.sin(math.pi * (t - self.t_switch + 0.35) / 0.7) * 30 * z
                if 0 < t0 and 0 <= t - t0 < 0.45:  # people who join later pop up into place
                    k = (t - t0) / 0.45
                    bob += (1 - k) ** 2 * height * 0.35
                if t0 == 0:  # rise into frame at the start of the scene
                    k = min(1.0, max(0.0, (t - a.seed * 0.12) / 0.45))
                    bob += (1 - k) ** 2 * height * 0.5
                wx, wy = self._world_x(a), self.person_bottom
            spr = self._sprite(a, expr, blink, height)
            sx, sy = self._to_screen(cam, wx, wy)
            sx += sway
            spr, dx = self._tilt(spr, a, expr, blink, height, angle)
            x, y = int(sx - spr.width / 2 + dx), int(sy - spr.height + bob)
            if x > self.w or x + spr.width < 0:
                continue
            heads[a.name] = (sx, sy - spr.height * (0.82 if not a.is_bug else 0.7) + bob)
            age = t - t0
            if a.is_bug and age < 0.5:
                g = self._glitch(spr, self.rng, 1.0 - age / 0.5)
                img.paste(g, (x - 40, y - 40), g)
            else:
                img.paste(spr, (x, y), spr)
            if a.name in self.label_for and 0.6 < age < 5.5 and not any(q[0] <= t < q[1] for q in self.quotes):
                labels.append(self._label((z, cx, cy), a, sx, sy, height))
        if fr is not None:
            fc = fr.crop((off, 0, off + self.w, self.h))
            img.paste(fc, (0, 0), fc)
        for lab in labels:
            img.paste(lab, (0, 0), lab)
        note = next((n for n in self.notes if n[0] <= t < n[1]), None)
        for qi, (q0, q1, text, spk) in enumerate(self.quotes):
            if note is None and q0 <= t < q1 and spk.name in heads:
                hx, hy = heads[spk.name]
                b, pos = self._bubble(qi, text, hx, hy, z)
                img.paste(b, pos, b)
                break
        if note is not None:
            card = self._note(note[2], note[3])
            img.paste(card, self._note_pos(card, t, note[0], note[1]), card)
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


_STEPS = ("mid", "solo", "close")


def _fresh(option, prev) -> bool:
    """A new shot must look clearly different from the last one: another framing, and on the same
    person a jump of at least two sizes (mid to close), so cuts never feel like a small jitter."""
    if prev is None:
        return True
    if option[0] == prev[0] and option[1] is prev[1]:
        return False
    if option[1] is not None and option[1] is prev[1] and option[0] in _STEPS and prev[0] in _STEPS:
        return abs(_STEPS.index(option[0]) - _STEPS.index(prev[0])) > 1
    return option[0] != prev[0] or option[1] is not prev[1]


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
