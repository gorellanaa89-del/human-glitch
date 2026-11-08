"""Animated scenes: hand-drawn set + characters + bugs, with simple 'limited animation'.

Each scene in the script can carry these lines:
  > set: office                      background from hg/sets.py
  > cast: sarah:happy -> sarah:worried, bug:impostor:worried
                                     who is on screen; "a -> b" switches expression mid-scene
  > switch: 0.3                      when the "->" switches happen (fraction of the scene, snapped to a paragraph)
  > enter: bug:filter@6              actor appears at the start of paragraph 6 (0-based) instead of at once
                                     (people who enter later walk in from the nearest side)
  > gesture: daniel:wave@0, richard:point@3
                                     arm gestures at the start of a paragraph (see sketch.POSES);
                                     people also gesture on their own: when they speak, when their
                                     expression changes, and at some paragraph changes

What moves: gentle breathing/bobbing, blinking, expression changes, bugs popping in with a glitch,
a patched bug shrinking a little, and camera cuts between a wide and a close shot on paragraph changes.

Camera language (2026-11-08): besides wide/group/mid/solo/close, each shot can get
  - over the shoulder: another person's back, big and out of focus, in the foreground
  - dutch angle: the frame tilted a few degrees, for worried moments and for the voices
  - low angle (looking up, for confident people) or high angle (looking down, for worried ones)
  - a whip pan into the shot, a shake and punch-in when a voice pops in
and every shot has a slow handheld float, parallax (the room moves slower than the people) and
more background blur the closer the shot is (depth of field).
Frames are piped straight into ffmpeg, so a scene costs one encode.
"""
import math
import re
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter

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
    def __init__(self, scene, seconds: float, words, size, labeled: set | None = None, seed: int = 0,
                 lang: str = "en"):
        self.w, self.h = size
        self.lang = lang
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
        self._build_gestures(ex)
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
        aliases = {a.name: (bugs.display_name(a.name, self.lang).split()[-1].lower() if a.is_bug else a.name) for a in self.actors}
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

    def _build_gestures(self, ex):
        """When each person moves their arms: (start, end, pose)."""
        self.gest = {a.name: [] for a in self.actors}
        people = [a for a in self.actors if not a.is_bug]
        rng = random.Random(self.rng.random())

        def add(name, t0, t1, pose, force=False):
            g = self.gest.get(name)
            if g is None or pose not in sketch.POSES or t0 < self.enter_t.get(name, 0) + 1.3:
                return
            t1 = min(t1, self.seconds - 0.4)
            if t1 - t0 < 0.6:
                return
            if any(not (t1 + 0.5 < a or t0 > b + 0.5) for a, b, _ in g):
                if not force:
                    return
                g[:] = [x for x in g if t1 + 0.5 < x[0] or t0 > x[1] + 0.5]
            g.append((t0, t1, pose))

        for spec in [x.strip() for x in ex.get("gesture", "").split(",") if x.strip()]:
            who, _, para = spec.partition("@")
            name, _, pose = who.partition(":")
            k = int(para or 0)
            t0 = (self.paras[k] if k < len(self.paras) else 0.0) + 0.2
            add(name, t0, t0 + 2.0, pose, force=True)
        mood = {"surprised": "cheer", "happy": "cheer", "worried": "panic", "sad": "clasp", "smug": "point"}
        for a in people:
            if a.expr1 in mood:
                add(a.name, self.t_switch + 0.1, self.t_switch + 1.7, mood[a.expr1])
        for q0, q1, _, spk in self.quotes:
            if not spk.is_bug:
                add(spk.name, q0 + 0.1, min(q1, q0 + 2.6), rng.choice(("explain", "explain", "shrug", "point")))
        idle = {"worried": ("clasp", "panic", "clasp"), "sad": ("clasp",), "smug": ("point", "explain", "stop"),
                "happy": ("explain", "shrug", "wave"), "surprised": ("shrug", "cheer", "stop")}
        for k, tp in enumerate(self.paras[1:], 1):
            if not people or rng.random() > 0.7:
                continue
            a = people[k % len(people)]
            expr = (a.expr1 if a.expr1 and tp >= self.t_switch else a.expr0) or getattr(sketch.CAST.get(a.name), "default", "neutral")
            add(a.name, tp + 0.25, tp + 1.9, rng.choice(idle.get(expr, ("explain", "shrug", "point"))))

    def _arms_at(self, a, t):
        rest = sketch.POSES["rest"]
        arms = rest
        for g0, g1, pose in self.gest.get(a.name, ()):
            if g0 - 0.25 <= t < g1 + 0.3:
                k = (t - g0 + 0.25) / 0.25 if t < g0 else (1 - (t - g1) / 0.3 if t > g1 else 1.0)
                k = max(0.0, min(1.0, k))
                k = k * k * (3 - 2 * k)
                arms = [[r + (p - r) * k for r, p in zip(ra, pa)] for ra, pa in zip(rest, sketch.POSES[pose])]
                if pose == "wave":
                    arms[1][1] += 20 * k * math.sin(2 * math.pi * t / 0.55)
                elif pose in ("explain", "point", "stop"):
                    arms[1][0] += 7 * k * math.sin(2 * math.pi * t / 0.9)
                elif pose == "shrug":
                    for side in arms:
                        side[1] += 10 * k * math.sin(2 * math.pi * t / 1.1)
                break
        if not self.portrait and a.x > 0.55:  # people on the right gesture towards the middle
            arms = [arms[1], arms[0]]
        return tuple(tuple(int(round(v / 6) * 6) for v in side) for side in arms)

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
            if (sentence_end and gap >= CUT_MIN) or (t[-1:] in ",;:" and gap >= CUT_COMMA) or gap >= CUT_MAX:
                cuts.append(nxt); kinds.append(None)
        # fill free choices, never repeating the previous framing
        options = [("wide", None)] + ([("group", None)] if len(self.actors) > 1 else []) + \
            [(k, a) for a in self.actors for k in ("mid", "solo", "close")]
        prev = None
        self.cams = []
        self.styles = []
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
            drift = (self.w / z) * (DRIFT if k[0] != "wide" else DRIFT * 0.6) * (1 if i % 2 == 0 else -1)
            z, cx0, cy0 = self._clamp(z, cx - drift / 2, cy)
            z, cx1, cy1 = self._clamp(z, cx + drift / 2, cy)
            self.cams.append((c, end, z, cx0, cy0, cx1, cy1))
            st = self._style(i, c, k, kinds[i] is not None)
            if st["ots"] is not None:  # rule of thirds: the face we look at moves away from the shoulder
                sh = st["side"] * (self.w / z) * 0.2
                cam = self.cams[-1]
                _, ax, ay = self._clamp(z, cam[3] + sh, cam[4])
                _, bx, by = self._clamp(z, cam[5] + sh, cam[6])
                self.cams[-1] = (cam[0], cam[1], z, ax, ay, bx, by)
            self.styles.append(st)
            prev = k
        self.cuts = cuts
        self._shot_bgs = {}
        self._bubble_cache = {}
        self._note_cache = {}

    def _expr_at(self, a, t):
        e = a.expr1 if a.expr1 and t >= self.t_switch else a.expr0
        if e:
            return e
        return bugs.BUGS[a.name][3] if a.is_bug else getattr(sketch.CAST.get(a.name), "default", "neutral")

    def _style(self, i, c, k, forced):
        """Extra camera language for one shot (see the module docstring)."""
        st = {"dutch": 0.0, "key": 0.0, "ots": None, "whip": 0, "subject": None, "side": 1}
        if i == 0 or self.portrait:
            return st
        rng = self.rng
        kind, a = k
        if not forced and rng.random() < WHIP:
            st["whip"] = rng.choice((-1, 1))
        if a is None:
            if kind == "wide" and rng.random() < 0.35:
                st["key"] = -HIGH  # a look down on the whole room
            return st
        expr = self._expr_at(a, c)
        r = rng.random()
        if a.is_bug:
            if kind in ("solo", "close") and r < 0.6:
                st["dutch"] = rng.choice((-1, 1)) * DUTCH
            elif r < 0.85:
                st["key"] = LOW
            return st
        if expr in ("worried", "sad", "surprised"):
            if kind in ("solo", "close") and r < 0.45:
                st["dutch"] = rng.choice((-1, 1)) * DUTCH * 0.8
            elif r < 0.8:
                st["key"] = -HIGH
        elif expr == "smug" and r < 0.7:
            st["key"] = LOW
        elif expr == "happy" and r < 0.3:
            st["key"] = LOW * 0.7
        others = [b for b in self.actors if not b.is_bug and b is not a and self.enter_t[b.name] <= c + 0.01]
        if others and kind in ("mid", "solo") and rng.random() < (0.75 if forced else 0.5):
            b = min(others, key=lambda o: abs(o.x - a.x))
            st["ots"], st["subject"] = b, a
            st["side"] = 1 if b.x > a.x else -1  # the listener's back is on their real side of the room
        return st

    def _ots_sprite(self, b, height):
        """A person seen from behind: their shape in their colour, the head in their hair colour, blurred
        because they are much closer to the camera than the focus."""
        key = ("ots", b.name, height)
        if key not in self._sprites:
            spr = sketch.back(b.name, height)
            blur = max(2, int(height / 160))
            pad = blur * 3
            big = Image.new("RGBA", (spr.width + pad * 2, spr.height + pad), (0, 0, 0, 0))
            big.paste(spr, (pad, pad))
            big = big.filter(ImageFilter.GaussianBlur(blur))
            dark = ImageEnhance.Brightness(big).enhance(0.8)
            dark.putalpha(big.getchannel("A"))
            self._sprites[key] = dark
        return self._sprites[key]

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
            blur = max(0.0, z - 1.15) * 2.6 * self.h / 720  # closer shot, softer room
            if blur > 0.4:
                bg = bg.filter(ImageFilter.GaussianBlur(blur))
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
        x_rest = int(self.w * (0.07 if self.portrait else 0.12))  # inside the area a Short keeps
        # in a Short the subtitles sit at the top, so the card goes below them
        y = int(self.h * (0.06 if not self.portrait else 0.27))
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
    def _sprite(self, a: Actor, expr, blink, height, arms=None):
        key = (a.name, expr, blink, height, arms)
        if key not in self._sprites:
            if len(self._sprites) > 700:
                self._sprites.clear()
            if a.is_bug:
                self._sprites[key] = bugs.draw(a.name, expr, height=height, blink=blink)
            else:
                self._sprites[key] = sketch.draw(a.name, expr, height=height, blink=blink, arms=arms)
        return self._sprites[key]

    def _tilt(self, spr, a, expr, blink, height, angle, arms=None):
        """Rotate a sprite a few degrees around its feet (cached in 1-degree steps).
        Returns the rotated sprite and the x shift that keeps the feet in place."""
        deg = round(angle * 2) / 2
        if deg == 0:
            return spr, 0
        key = (a.name, expr, blink, height, deg, arms)
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
            sketch.label(img, bugs.display_name(a.name, self.lang), (int(tx), int(ty)), size=size,
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
        bcx = cx0 + (cx - cx0) * PARALLAX  # the room is further away than the people: it moves less
        off = int(round((bcx - self.w / z / 2 - x0) * z))
        off = min(max(off, 0), bg.width - self.w)
        img = bg.crop((off, 0, off + self.w, self.h))
        cam = (z, cx, cy)
        labels, heads = [], {}
        st = self.styles[i]
        for a in self.actors:
            t0 = self.enter_t[a.name]
            if t < t0:
                continue
            if st["ots"] is not None and not a.is_bug and a is not st["subject"]:
                continue  # over the shoulder: only the face we look at (the listener is the shoulder)
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
                arms = None
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
                arms = self._arms_at(a, t)
                wx, wy = self._world_x(a), self.person_bottom
                if 0 < t0 and 0 <= t - t0 < WALK:  # people who join later walk in from the nearest side
                    k = (t - t0) / WALK
                    k = k if k < 0.8 else 0.8 + (1 - (1 - (k - 0.8) / 0.2) ** 2) * 0.2
                    side = -1 if a.x < 0.5 else 1
                    edge = (self.ox if side < 0 else self.ox + self.w) if self.portrait else (0 if side < 0 else self.world_w)
                    start = edge + side * height * 0.6
                    wx = start + (wx - start) * k
                    step = (t - t0) / 0.32
                    bob = -abs(math.sin(math.pi * step)) * 16 * z
                    angle = 4 * math.sin(math.pi * step) * (1 - k)
                    swing = 26 * math.sin(math.pi * step) * (1 - k * 0.7)
                    arms = tuple(tuple(int(round(v / 6) * 6) for v in pair) for pair in
                                 ((16 + swing, -4 + swing * 0.6), (16 - swing, -4 - swing * 0.6)))
                if t0 == 0:  # rise into frame at the start of the scene
                    k = min(1.0, max(0.0, (t - a.seed * 0.12) / 0.45))
                    bob += (1 - k) ** 2 * height * 0.5
            spr = self._sprite(a, expr, blink, height, arms)
            sx, sy = self._to_screen(cam, wx, wy)
            sx += sway
            spr, dx = self._tilt(spr, a, expr, blink, height, angle, arms)
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
        b = st["ots"]
        if b is not None:
            spr = self._ots_sprite(b, int(self.h * 0.95))
            side = st["side"]
            k = u * 0.03
            px = int((self.w - spr.width * 0.62 - self.w * k) if side > 0 else (-spr.width * 0.38 + self.w * k))
            py = int(self.h * 0.18)
            img.paste(spr, (px, py), spr)
        if fr is not None:
            fc = fr.crop((off, 0, off + self.w, self.h))
            img.paste(fc, (0, 0), fc)
        for lab in labels:
            img.paste(lab, (0, 0), lab)
        img, fwd = self._camera(img, t, i, c, u, st)
        heads = {n: fwd(*p) for n, p in heads.items()}
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

    def _camera(self, img, t, i, c, u, st):
        """Move the finished picture like a camera: slow push in or out, handheld float, dutch tilt,
        low/high angle keystone, whip pan and the shake when a voice pops in. One resample per frame.
        Returns the new picture and a function that maps a point of the old picture onto the new one."""
        w, h = self.w, self.h
        s = 1 + PUSH * (u if i % 2 == 0 else 1 - u)
        ang = 0.0 if self.portrait else HANDHELD * (0.6 * math.sin(2 * math.pi * t / 5.3) + 0.4 * math.sin(2 * math.pi * t / 2.9 + 1))
        tx = w * 0.004 * math.sin(2 * math.pi * t / 4.7)
        ty = h * 0.004 * math.sin(2 * math.pi * t / 3.7 + 2)
        ang += st["dutch"] * (0.85 + 0.15 * u)
        for a in self.actors:  # a voice pops in: punch in and shake
            age = t - self.enter_t[a.name]
            if a.is_bug and 0 <= age < 0.5 and self.enter_t[a.name] > 0:
                d = 1 - age / 0.5
                s *= 1 + 0.07 * d
                tx += w * 0.012 * d * math.sin(age * 90)
                ty += h * 0.012 * d * math.cos(age * 70)
        whip = 0.0
        if st["whip"] and t - c < WHIP_T:
            whip = 1 - (t - c) / WHIP_T
            tx += st["whip"] * w * 0.3 * whip ** 2
        th = math.radians(ang)
        cs, sn = math.cos(th), math.sin(th)
        s *= abs(cs) + abs(sn) * w / h + 2 * max(abs(tx) / w, abs(ty) / h)
        Cx, Cy = w / 2, h * 0.45
        key = st["key"]
        if abs(s - 1) < 1e-3 and abs(ang) < 1e-3 and not key and not whip:
            return img, lambda x, y: (x, y)
        # inverse map (output -> input): in = C + R(-th) (out - C - T) / s
        def inv(x, y):
            dx, dy = x - Cx - tx, y - Cy - ty
            return Cx + (cs * dx + sn * dy) / s, Cy + (-sn * dx + cs * dy) / s
        dst = [(0, 0), (w, 0), (w, h), (0, h)]
        src = [inv(*p) for p in dst]
        if key:  # low angle: the bottom of the picture comes closer; high angle: the top does
            pair = (2, 3) if key > 0 else (0, 1)
            k = abs(key) * (0.7 + 0.3 * u)
            (ax, ay), (bx, by) = src[pair[0]], src[pair[1]]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            src[pair[0]] = (ax + (mx - ax) * k, ay + (my - ay) * k)
            src[pair[1]] = (bx + (mx - bx) * k, by + (my - by) * k)
        rows, rhs = [], []
        for (x, y), (X, Y) in zip(dst, src):
            rows.append([x, y, 1, 0, 0, 0, -X * x, -X * y]); rhs.append(X)
            rows.append([0, 0, 0, x, y, 1, -Y * x, -Y * y]); rhs.append(Y)
        coef = np.linalg.solve(np.array(rows, float), np.array(rhs, float))
        img = img.transform((w, h), Image.PERSPECTIVE, tuple(coef), Image.BILINEAR)
        if whip > 0.05:  # motion blur while the camera swings
            smear = img.resize((max(8, int(w / (2 + 30 * whip))), h), Image.BILINEAR).resize((w, h), Image.BILINEAR)
            img = Image.blend(img, smear, min(1.0, whip * 1.4))

        def fwd(x, y):
            dx, dy = x - Cx, y - Cy
            return Cx + tx + s * (cs * dx - sn * dy), Cy + ty + s * (sn * dx + cs * dy)
        return img, fwd

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

# Pacing: seconds between cuts (at a sentence end / at a comma / at most), sideways drift per shot
# (fraction of the view) and how much each shot slowly zooms.
CUT_MIN, CUT_COMMA, CUT_MAX = 1.8, 3.0, 4.0
DRIFT = 0.09
PUSH = 0.07
PARALLAX = 0.45   # how far the room moves compared with the people when the camera drifts
HANDHELD = 0.35   # degrees of slow handheld float
DUTCH = 5.0       # degrees of a tilted shot
LOW, HIGH = 0.10, 0.08  # keystone of low and high angle shots
WHIP, WHIP_T = 0.22, 0.24  # share of free cuts that whip pan in, and how long the swing lasts
WALK = 1.3  # seconds a person takes to walk into the scene


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


def render_scene(scene, seconds, words, out: Path, size, labeled=None, seed=0, lang="en") -> Path:
    return SceneRenderer(scene, seconds, words, size, labeled, seed, lang).render(out)


def spanish_scene(en_scene, es_scene):
    """The scene as the Spanish picture sees it: the English staging (set, cast, entrances, gestures) with
    the Spanish narration, and the Spanish note cards where the Spanish script has its own `> note@` lines."""
    from dataclasses import replace
    extra = dict(en_scene.extra)
    es_notes = {k: v for k, v in es_scene.extra.items() if k.startswith("note@")}
    if es_notes:
        extra = {k: v for k, v in extra.items() if not k.startswith("note@")}
        extra.update(es_notes)
    return replace(en_scene, narration=es_scene.narration, extra=extra)


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
        spr = sketch.draw(person.name, "worried", height=int(h * 0.92), arms=sketch.POSES["panic"])
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
