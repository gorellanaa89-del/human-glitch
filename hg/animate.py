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
                 lang: str = "en", wipe_in: bool = True, wipe_out: bool = True, wipe_text: str | None = None):
        self.w, self.h = size
        # paper-wipe transitions between scenes (not in a vertical Short)
        self.wipe_in = wipe_in and self.h <= self.w and WIPE_T > 0
        self.wipe_out = wipe_out and self.h <= self.w and WIPE_T > 0
        self.wipe_text = (scene.title if wipe_text is None else wipe_text) or ""
        self.lang = lang
        self.portrait = self.h > self.w
        self.seconds = seconds
        self.rng = random.Random(seed)
        ex = scene.extra
        self.set_name = ex.get("set", "office")
        self.actors = parse_cast(ex.get("cast", ""))
        _layout(self.actors, self.portrait)
        self.scene = scene
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
        self.label_for = {a.name for a in self.actors if (a.is_bug or a.name in NAMED) and a.name not in labeled}
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
        said = dict(quote_speakers(self.scene))
        nth = {}
        for a, b in out:
            t0 = self.words[a][0]
            para = max((k for k, tp in enumerate(self.paras) if tp <= t0 + 0.01), default=0)
            n = nth[para] = nth.get(para, -1) + 1
            speaker = None
            if para in said:  # the script says who speaks: `> say@P: richard`
                who = said[para][min(n, len(said[para]) - 1)]
                speaker = names.get(who)
            else:
                # otherwise the last character named just before the quote, unless they are the one
                # spoken to ("turns to Daniel", "se voltea hacia Daniel")
                toks = [_norm_word(w[2]) for w in self.words[max(0, a - 14):a]]
                best = -1
                for name, alias in aliases.items():
                    for k, tok in enumerate(toks):
                        if tok == alias and k > best and not (k > 0 and toks[k - 1] in _ADDRESSEE):
                            speaker, best = names[name], k
            if b - a + 1 < (2 if speaker else 3):  # very short quotes only when someone is named saying them
                continue
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
            if g0 - 0.3 <= t < g1 + 0.35:
                if t < g0 + 0.1:  # swing up past the pose and settle back (follow-through)
                    k = _ease_back((t - g0 + 0.3) / 0.4, 1.4)
                elif t > g1:
                    k = _ease_io(1 - (t - g1) / 0.35)
                else:
                    k = 1.0
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
        return tuple(tuple(int(round(v / ARM_STEP) * ARM_STEP) for v in side) for side in arms)

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
        # a quote (all its bubbles) is one stretch on the speaker
        talks = []
        for t0, t1, text, spk in self.quotes:
            if talks and talks[-1][2] is spk and t0 - talks[-1][1] < 0.6:
                talks[-1][1] = t1
            else:
                talks.append([t0, t1, spk])
        for t0, t1, spk in talks:
            forced[round(t0, 2)] = ("solo", spk)
        for a in self.actors:
            if self.enter_t[a.name] > 0:
                forced[round(self.enter_t[a.name], 2)] = ("enter", a)
        # the narration names someone on screen: the camera goes to them, so we know who is who
        aliases = {a.name: (bugs.display_name(a.name, self.lang).split()[-1].lower() if a.is_bug else a.name) for a in self.actors}
        last = {}
        for s_, e_, tok in self.words:
            nt = _norm_word(tok)
            for a in self.actors:
                if nt != aliases[a.name] or self.enter_t[a.name] > s_ + 0.01 or s_ < 0.6:
                    continue
                if s_ - last.get(a.name, -99) < MENTION_GAP or round(s_, 2) in forced:
                    continue
                if any(n0 - 0.5 <= s_ < n1 for n0, n1, *_ in self.notes):
                    continue  # a paper card is up: the shot stays open
                if any(q0 - 0.5 <= s_ < q1 for q0, q1, *_ in self.quotes):
                    continue
                forced[round(s_, 2)] = ("mention", a)
                last[a.name] = s_
        cuts = [0.0]
        kinds = [("wide", None)]
        for i, (s, e, t) in enumerate(W):
            nxt = W[i + 1][0] if i + 1 < len(W) else None
            if nxt is None or self.seconds - nxt < 1.5:
                continue
            gap = nxt - cuts[-1]
            key = round(nxt, 2)
            if key in forced and forced[key][0] == "solo" and gap < 1.2 and len(cuts) > 1:
                kinds[-1] = forced[key]; continue  # someone starts talking: the shot just before becomes theirs
            if key in forced and gap >= 1.2:
                cuts.append(nxt); kinds.append(forced[key]); continue
            if any(q0 < nxt < q1 for q0, q1, _ in talks):
                continue  # nobody cuts away while someone is talking
            # end of a quote: go back out to a wider shot
            if any(abs(q1 - 0.35 - e) < 0.01 for _, q1, _ in talks) and gap >= 1.2:
                cuts.append(nxt); kinds.append(None); continue
            sentence_end = t.rstrip("\"”")[-1:] in ".?!"
            if (sentence_end and gap >= CUT_MIN) or (t[-1:] in ",;:" and gap >= CUT_COMMA) or gap >= CUT_MAX:
                cuts.append(nxt); kinds.append(None)
        # fill free choices, never repeating the previous framing
        people = [a for a in self.actors if not a.is_bug]
        options = [("wide", None)] + ([("group", None)] if len(self.actors) > 1 else []) + \
            ([("pan", None), ("pan", None)] if len(self.actors) > 1 and not self.portrait else []) + \
            [(k, a) for a in self.actors for k in ("mid", "solo", "close")]
        prev = None
        self.cams = []
        self.styles = []
        self.subjects = []  # the one person a shot is about (None for wide, group and pan shots)
        for i, (c, k) in enumerate(zip(cuts, kinds)):
            if k is not None and k[0] == "enter":
                k = ("wide", None) if len(self.actors) > 2 else ("group", None)
            if k is not None and k[0] == "mention":
                k = ("mid", k[1]) if prev != ("mid", k[1]) else ("solo", k[1])
            if k is None:
                avail = [o for o in options if _fresh(o, prev) and (o[1] is None or self.enter_t[o[1].name] <= c + 0.01)]
                if any(n0 - CUT_MAX <= c < n1 for n0, n1, *_ in self.notes):
                    # a paper card is (or is about to be) on screen: keep the shot open so it never covers a face
                    avail = [("wide", None)]
                elif any(not x.is_bug and x.name in self.label_for and self._label_start(x) - CUT_MAX <= c < self._label_start(x) + 3.5
                         for x in self.actors):
                    avail = [("wide", None)]  # names are being introduced: everybody in the shot
                k = self.rng.choice(avail) if avail else ("wide", None)
            if len(self.actors) == 0:
                k = ("wide", None)
            end = cuts[i + 1] if i + 1 < len(cuts) else self.seconds
            if k[0] == "pan":
                # the camera travels from one person to another across the shot
                vis = [a for a in self.actors if self.enter_t[a.name] <= c + 0.01]
                if len(vis) < 2:
                    k = ("group", None) if len(vis) > 1 else ("wide", None)
            if k[0] == "pan":
                a0, a1 = min(vis, key=lambda a: a.x), max(vis, key=lambda a: a.x)
                if self.rng.random() < 0.5:
                    a0, a1 = a1, a0
                z0, x0_, y0_ = self._cam_for("mid", a0)
                _, x1_, _ = self._cam_for("mid", a1)
                z = min(z0, 1.45)
                z, cx0, cy0 = self._clamp(z, x0_, y0_)
                z, cx1, cy1 = self._clamp(z, x1_, y0_)
            else:
                z, cx, cy = self._cam_for(k[0], k[1])
                drift = (self.w / z) * (DRIFT if k[0] != "wide" else DRIFT * 0.6) * (1 if i % 2 == 0 else -1)
                z, cx0, cy0 = self._clamp(z, cx - drift / 2, cy)
                z, cx1, cy1 = self._clamp(z, cx + drift / 2, cy)
            self.cams.append((c, end, z, cx0, cy0, cx1, cy1))
            self.subjects.append(k[1] if k[0] in _STEPS else None)
            st = self._style(i, c, k, kinds[i] is not None)
            if st["ots"] is not None:  # rule of thirds: the face we look at moves away from the shoulder
                sh = st["side"] * (self.w / z) * 0.2
                cam = self.cams[-1]
                _, ax, ay = self._clamp(z, cam[3] + sh, cam[4])
                _, bx, by = self._clamp(z, cam[5] + sh, cam[6])
                self.cams[-1] = (cam[0], cam[1], z, ax, ay, bx, by)
            # most cuts become a camera move: the camera glides from the last framing into this one
            st["glide"] = 0.0
            if i > 0 and not self.portrait and st["ots"] is None and self.styles[-1]["ots"] is None \
                    and not st["whip"] and self.rng.random() < GLIDE:
                st["glide"] = min(GLIDE_T, 0.55 * (end - c))
            self.styles.append(st)
            prev = k
        self.cuts = cuts
        self._shot_bgs = {}
        self._bubble_cache = {}
        self._note_cache = {}
        self._note_sides = {}

    def _expr_at(self, a, t):
        e = a.expr1 if a.expr1 and t >= self.t_switch else a.expr0
        if e:
            return e
        return bugs.BUGS[a.name][3] if a.is_bug else getattr(sketch.CAST.get(a.name), "default", "neutral")

    def _style(self, i, c, k, forced):
        """Extra camera language for one shot (see the module docstring)."""
        st = {"dutch": 0.0, "key": 0.0, "ots": None, "whip": 0, "subject": None, "side": 1, "push": PUSH}
        if i == 0 or self.portrait:
            return st
        rng = self.rng
        kind, a = k
        if not forced and rng.random() < WHIP:
            st["whip"] = rng.choice((-1, 1))
        if kind not in ("wide", "pan") and rng.random() < 0.35:
            st["push"] = DOLLY  # a strong, steady push in on the face
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
        if others and kind in ("mid", "solo") and rng.random() < (OTS_FORCED if forced else OTS_FREE):
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

    def _room_at(self, z, bcx, cy):
        """The room (and its foreground) seen by a camera between two shots, blurred like a shot of that size."""
        vw, vh = self.w / z, self.h / z
        bcx = min(max(bcx, vw / 2), self.world_w - vw / 2)
        box = (bcx - vw / 2, cy - vh / 2, bcx + vw / 2, cy + vh / 2)
        bg = self.bg.resize((self.w, self.h), Image.BILINEAR, box=box)
        blur = max(0.0, z - 1.15) * 2.6 * self.h / 720
        if blur > 0.4:
            bg = bg.filter(ImageFilter.GaussianBlur(blur))
        fr = self.front.resize((self.w, self.h), Image.BILINEAR, box=box) if self.front else None
        return bg, fr

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
            self._bubble_cache = {key: (img.crop(bbox), bbox[:2], tip)}
        return self._bubble_cache[key]

    def _note(self, title, sub):
        """A lined paper card with a big handwritten fact. It slides over the scene in the upper part of
        the frame, so it never covers the subtitles at the bottom. Built in layers (paper, title ink,
        underline, small line) so the title can write itself on; see _note_frame."""
        key = (title, sub)
        if key not in self._note_cache:
            from PIL import ImageDraw, ImageFilter, ImageFont
            from .config import BRAND_BLUE, BRAND_GRAY
            cw = int(self.w * (0.86 if self.portrait else 0.38))
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
            title_l = Image.new("RGBA", card.size, (0, 0, 0, 0))
            ImageDraw.Draw(title_l).text((cx, ty), title, font=font, fill=sketch.INK + (255,), anchor="mm")
            tl = d.textlength(title, font=font)
            yl = ty + big * 0.6
            line_l = Image.new("RGBA", card.size, (0, 0, 0, 0))
            ImageDraw.Draw(line_l).line([(cx - tl / 2, yl), (cx - tl / 6, yl + 5), (cx + tl / 6, yl - 3), (cx + tl / 2, yl + 3)],
                                        fill=BRAND_BLUE + (255,), width=6, joint="curve")
            sub_l = None
            if sub:
                sub_l = Image.new("RGBA", card.size, (0, 0, 0, 0))
                ImageDraw.Draw(sub_l).text((cx, yl + big * 0.62), sub, font=sf, fill=BRAND_GRAY + (255,), anchor="mm")
            angle = -2.5 if len(self._note_cache) % 2 == 0 else 2.0
            self._note_cache[key] = (card, title_l, line_l, sub_l, angle, (cx - tl / 2, cx + tl / 2))
        return self._note_cache[key]

    def _note_frame(self, note, t):
        """The card at time t: it lands tilted and settles, the title writes itself left to right,
        then the underline is drawn and the small line fades in."""
        paper, title_l, line_l, sub_l, angle, (xa, xb) = self._note(note[2], note[3])
        age = t - note[0]
        done = ("done", note[2], note[3])
        if age > 1.3 and done in self._note_cache:
            return self._note_cache[done]
        card = paper.copy()
        w_title = _ease_io((age - 0.2) / 0.55)
        w_line = _ease_io((age - 0.7) / 0.3)
        a_sub = _ease_io((age - 0.9) / 0.3)
        if w_title > 0:
            x = int(xa + (xb - xa + 12) * w_title)
            card.alpha_composite(title_l.crop((0, 0, x, title_l.height)))
        if w_line > 0:
            x = int(xa + (xb - xa + 12) * w_line)
            card.alpha_composite(line_l.crop((0, 0, x, line_l.height)))
        if a_sub > 0 and sub_l is not None:
            sm = sub_l
            if a_sub < 1:
                sm = sub_l.copy()
                sm.putalpha(sm.getchannel("A").point(lambda v: int(v * a_sub)))
            card.alpha_composite(sm)
        tilt = angle + angle * 2.5 * (1 - _ease_back(min(1.0, age / 0.5), 1.2))
        out = card.rotate(tilt, resample=Image.BICUBIC, expand=True)
        if age > 1.3:
            self._note_cache[done] = out
        return out

    def _note_pos(self, card, t, t0, t1, side=-1):
        """Slide in from one side with a little overshoot, hold, then slide back out."""
        x_rest = int(self.w * (0.07 if self.portrait else 0.12))  # inside the area a Short keeps
        if side > 0:
            return self._mirror_x(card, self._note_pos(card, t, t0, t1, -1))
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

    def _mirror_x(self, card, pos):
        return self.w - pos[0] - card.width, pos[1]

    def _note_side(self, key, card, heads):
        """Left or right, whichever covers fewer faces (decided once per card, so it doesn't jump)."""
        if key not in self._note_sides:
            x0 = self.w * 0.12
            span = (x0 - 40, x0 + card.width + 40)

            def hits(side):
                lo, hi = span if side < 0 else (self.w - span[1], self.w - span[0])
                return sum(1 for hx, hy in heads.values() if lo < hx < hi and hy < self.h * 0.55)
            self._note_sides[key] = 1 if hits(1) < hits(-1) else -1
        return self._note_sides[key]

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

    def _label_start(self, a):
        """When a name label shows: shortly after the actor appears; a person's name waits until no paper
        card is up (both sit in the top of the frame)."""
        t = self.enter_t[a.name] + 0.6
        if not a.is_bug:
            for n0, n1, *_ in sorted(self.notes):
                if n0 - 4.9 < t < n1:
                    t = n1 + 0.3
        return t

    def _label(self, cam, a: Actor, sx, sy, height):
        view = self._labels
        key = (a.name, round(sx / 3), round(sy / 3), height)
        if len(view) > 40:
            view.clear()
        if key not in view:
            img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            if not a.is_bug:  # a person: first name above the head, a short arrow down to it
                size = int(height * 0.1)
                top = sy - height * 0.80
                ty = max(size * 0.8, top - size * 1.6)
                sketch.label(img, sketch.CAST[a.name].name.split()[0], (int(sx), int(ty)), size=size,
                             arrow_to=(int(sx + size * 0.2), int(top + size * 0.15)))
                box = img.getbbox() or (0, 0, 1, 1)
                view[key] = (img.crop(box), box[:2])
                return view[key]
            size = int(height * 0.16)
            tx = min(self.w - size * 3.2, sx + height * 0.55)
            ty = max(size, sy - height * 0.95)
            sketch.label(img, bugs.display_name(a.name, self.lang), (int(tx), int(ty)), size=size,
                         arrow_to=(int(sx + height * 0.18), int(sy - height * 0.62)))
            box = img.getbbox() or (0, 0, 1, 1)
            view[key] = (img.crop(box), box[:2])
        return view[key]

    def _wipe(self, img, t):
        """Scene change: a navy paper panel with a torn light-blue edge sweeps in from the right at the end
        of a scene, and at the start of the next one it carries the scene's title off to the left."""
        w, h = self.w, self.h
        T_IN = WIPE_T + 0.2
        if self.wipe_out and self.seconds - t < WIPE_T and t >= WIPE_T:
            k = 1 - (self.seconds - t) / WIPE_T
            k = k ** 2.4  # accelerates in
            panel, E, Wsol = _wipe_panel(w, h)
            X = w + (-E - w) * k
            text = None
        elif self.wipe_in and t < T_IN:
            k = _ease_io(t / T_IN) ** 1.15
            panel, E, Wsol = _wipe_panel(w, h)
            X = -E + (-(Wsol + 2 * E) + E) * k
            text = self._wipe_title()
        else:
            return
        X = int(round(X))
        lo, hi = max(0, -X), min(panel.width, w - X)
        if hi <= lo:
            return
        part = panel.crop((lo, 0, hi, h))
        img.paste(part, (X + lo, 0), part)
        if text is not None:
            tx = int(X + E + w / 2 - text.width / 2)
            img.paste(text, (tx, int(h * 0.45 - text.height / 2)), text)

    def _wipe_title(self):
        if not hasattr(self, "_wipe_title_img"):
            from PIL import ImageDraw, ImageFont
            from .config import BRAND_LIGHT
            txt = self.wipe_text.strip()
            if not txt:
                self._wipe_title_img = None
                return None
            size = int(self.h * 0.13)
            font = ImageFont.truetype(str(sketch.HAND_FONT), size)
            d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            while d.textlength(txt, font=font) > self.w * 0.8 and size > 30:
                size -= 4
                font = ImageFont.truetype(str(sketch.HAND_FONT), size)
            tl = d.textlength(txt, font=font)
            im = Image.new("RGBA", (int(tl + 40), int(size * 1.9)), (0, 0, 0, 0))
            dd = ImageDraw.Draw(im)
            dd.text((im.width / 2, size * 0.75), txt, font=font, fill=(255, 255, 255, 255), anchor="mm")
            y = size * 1.45
            dd.line([(20, y), (20 + tl * 0.35, y + 6), (20 + tl * 0.7, y - 3), (20 + tl, y + 4)],
                    fill=BRAND_LIGHT + (255,), width=max(4, size // 14), joint="curve")
            self._wipe_title_img = im
        return self._wipe_title_img

    def _burst(self, img, hx, hy, height, age, a):
        """Hand-drawn emphasis strokes that shoot out around a head and pull back (an expression change,
        a voice popping in). Drawn small at 3x and scaled down so the lines stay soft."""
        from PIL import ImageDraw
        k = age / BURST_T
        r0 = height * (0.36 if not a.is_bug else 0.5)
        grow = _ease_io(min(1.0, k / 0.45))
        tail = _ease_io(max(0.0, (k - 0.35) / 0.65))
        if grow - tail < 0.02:
            return
        L = height * 0.16
        span = int((r0 + L) * 2 + 20)
        S = 3
        lay = Image.new("RGBA", (span * S, span * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        col = BRAND_LIGHT_RGBA if a.is_bug else sketch.INK + (235,)
        n = 7 if a.is_bug else 5
        rnd = random.Random(hash(a.name) & 0xffff)
        for j in range(n):
            # an arc above the head, from upper left to upper right
            ang = math.radians(-160 + 140 * j / (n - 1) + rnd.uniform(-8, 8))
            ln = L * rnd.uniform(0.8, 1.2)
            a0, a1 = r0 + ln * tail, r0 + ln * grow
            c = span / 2
            p0 = ((c + math.cos(ang) * a0) * S, (c + math.sin(ang) * a0) * S)
            p1 = ((c + math.cos(ang) * a1) * S, (c + math.sin(ang) * a1) * S)
            wdt = int(max(2, height / 110) * S)
            d.line([p0, p1], fill=col, width=wdt)
            for q in (p0, p1):
                d.ellipse((q[0] - wdt / 2, q[1] - wdt / 2, q[0] + wdt / 2, q[1] + wdt / 2), fill=col)
        lay = lay.resize((span, span), Image.LANCZOS)
        img.paste(lay, (int(hx - span / 2), int(hy - span / 2)), lay)

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
    def _glide(self, i, t):
        """0..1 while shot i is still gliding in from the previous framing, None once it has arrived."""
        g = self.styles[i].get("glide", 0.0)
        if not g or t - self.cuts[i] >= g:
            return None
        return _ease_io((t - self.cuts[i]) / g)

    def frame(self, t: float) -> Image.Image:
        i = max(k for k, c in enumerate(self.cuts) if c <= t)
        c, end, z, cx0, cy0, cx1, cy1 = self.cams[i]
        u = 0.0 if end - c < 0.01 else (t - c) / (end - c)
        u = u * u * (3 - 2 * u)
        cx, cy = cx0 + (cx1 - cx0) * u, cy0 + (cy1 - cy0) * u
        bcx = cx0 + (cx - cx0) * PARALLAX  # the room is further away than the people: it moves less
        gk = self._glide(i, t)
        if gk is None:
            bg, fr, x0 = self._shot_layers(i)
            off = int(round((bcx - self.w / z / 2 - x0) * z))
            off = min(max(off, 0), bg.width - self.w)
            img = bg.crop((off, 0, off + self.w, self.h))
            fc = fr.crop((off, 0, off + self.w, self.h)) if fr is not None else None
        else:
            # a camera move: zoom and position travel together from where the last shot ended
            _, _, pz, px0, py0, px1, py1 = self.cams[i - 1]
            pb = px0 + (px1 - px0) * PARALLAX
            z = math.exp(math.log(pz) + (math.log(z) - math.log(pz)) * gk)
            z, cx, cy = self._clamp(z, px1 + (cx - px1) * gk, py1 + (cy - py1) * gk)
            bcx = pb + (bcx - pb) * gk
            img, fc = self._room_at(z, bcx, cy)
        cam = (z, cx, cy)
        labels, heads, boxes, bursts = [], {}, [], []
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
                if t - t0 < 0.45 and t0 > 0:
                    scale *= 0.25 + 0.75 * _ease_back((t - t0) / 0.45, 2.2)
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
                    arms = tuple(tuple(int(round(v / ARM_STEP) * ARM_STEP) for v in pair) for pair in
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
            boxes.append((sx - spr.width * 0.2, sx + spr.width * 0.2, a))  # the face, not arms or body
            age = t - t0
            if a.is_bug and age < 0.5:
                g = self._glitch(spr, self.rng, 1.0 - age / 0.5)
                img.paste(g, (x - 40, y - 40), g)
            else:
                img.paste(spr, (x, y), spr)
            l0 = self._label_start(a)
            if a.name in self.label_for and l0 < t < l0 + 4.9 and not any(q[0] <= t < q[1] for q in self.quotes) \
                    and (a.is_bug or z < 1.6):
                lab, pos = self._label((z, cx, cy), a, sx, sy, height)
                fade = min(1.0, (t - l0) / 0.3, (l0 + 4.9 - t) / 0.25)
                if fade < 1:
                    lab = lab.copy()
                    lab.putalpha(lab.getchannel("A").point(lambda v, f=fade: int(v * f)))
                pos = (pos[0], pos[1] + int(14 * (1 - _ease_io(fade))))
                labels.append((lab, pos, lab))
            if a.expr1 and 0 <= t - self.t_switch < BURST_T and not (st["ots"] is not None and a is not st["subject"]):
                bursts.append((sx, sy - spr.height * (0.82 if not a.is_bug else 0.7) + bob, height, t - self.t_switch, a))
            elif a.is_bug and t0 > 0 and 0 <= age < BURST_T:
                bursts.append((sx, sy - spr.height * 0.5 + bob, height, age, a))
        b = st["ots"]
        if b is not None:
            spr = self._ots_sprite(b, int(self.h * 0.95))
            side = st["side"]
            k = u * 0.03
            px = int((self.w - spr.width * 0.62 - self.w * k) if side > 0 else (-spr.width * 0.38 + self.w * k))
            py = int(self.h * 0.18)
            img.paste(spr, (px, py), spr)
        if fc is not None:
            img.paste(fc, (0, 0), fc)
        for b_ in bursts:
            self._burst(img, *b_)
        for lab in labels:
            img.paste(*lab)
        img, fwd = self._camera(img, t, i, c, u, st, gk)
        heads = {n: fwd(*p) for n, p in heads.items()}
        mid = self.h * 0.5
        subject = self.subjects[i]
        faces = [(fwd(x0, mid)[0], fwd(x1, mid)[0]) for x0, x1, a in boxes if subject is None or a is subject]
        edge = self.w * 0.03
        whole = [f for f in faces if f[0] >= edge and f[1] <= self.w - edge]
        if subject is not None and faces:  # a shot about one face: a vertical Short comes in close
            c, half = (faces[0][0] + faces[0][1]) / 2, (faces[0][1] - faces[0][0]) * 0.36
            whole = [(c - half, c + half)]
        # a face cut by the edge of the picture only counts when no face is fully in it
        boxes = whole or [(max(0, a), min(self.w, b)) for a, b in faces if min(self.w, b) - max(0, a) > self.w * 0.03]
        note = next((n for n in self.notes if n[0] <= t < n[1]), None)
        for qi, (q0, q1, text, spk) in enumerate(self.quotes):
            if note is None and q0 <= t < q1 and spk.name in heads:
                hx, hy = heads[spk.name]
                b, pos, tip = self._bubble(qi, text, hx, hy, z)
                # the bubble pops out of the speaker's mouth with a small overshoot, and pops away
                k = min(_ease_back((t - q0) / 0.28, 2.0), 1.0 if q1 - t > 0.14 else max(0.0, (q1 - t) / 0.14))
                if k < 0.999:
                    if k < 0.05:
                        break
                    nw, nh = max(1, int(b.width * k)), max(1, int(b.height * k))
                    pos = (int(tip[0] + (pos[0] - tip[0]) * k), int(tip[1] + (pos[1] - tip[1]) * k))
                    b = b.resize((nw, nh), Image.BILINEAR)
                img.paste(b, pos, b)
                boxes.append((max(0, pos[0]), min(self.w, pos[0] + b.width)))
                break
        if note is not None:
            card = self._note_frame(note, t)
            side = -1 if self.portrait else self._note_side(note[:2], card, heads)
            npos = self._note_pos(card, t, note[0], note[1], side)
            img.paste(card, npos, card)
            if 0 <= npos[0] and npos[0] + card.width <= self.w:  # fully slid in: keep it in a vertical Short
                boxes.append((npos[0], npos[0] + card.width))
        self._wipe(img, t)
        # where things are on screen, so a vertical Short can frame them (see vertical.py)
        self.track.append([i, round(min((b[0] for b in boxes), default=-1)), round(max((b[1] for b in boxes), default=-1)),
                           int(note is not None)])
        return img

    def _lens(self, i, u):
        """Push-in scale, dutch tilt and keystone of shot i at progress u."""
        st = self.styles[i]
        push = st.get("push", PUSH)
        s = 1 + push * (u if (i % 2 == 0 or push > PUSH) else 1 - u)
        return s, st["dutch"] * (0.85 + 0.15 * u), st["key"] * (0.7 + 0.3 * u)

    def _camera(self, img, t, i, c, u, st, gk=None):
        """Move the finished picture like a camera: slow push in or out, handheld float, dutch tilt,
        low/high angle keystone, whip pan and the shake when a voice pops in. One resample per frame.
        Returns the new picture and a function that maps a point of the old picture onto the new one."""
        w, h = self.w, self.h
        s, dutch, key = self._lens(i, u)
        if gk is not None:  # gliding: the lens eases from how the last shot ended
            ps, pd, pk = self._lens(i - 1, 1.0)
            s, dutch, key = ps + (s - ps) * gk, pd + (dutch - pd) * gk, pk + (key - pk) * gk
        ang = 0.0 if self.portrait else HANDHELD * (0.6 * math.sin(2 * math.pi * t / 5.3) + 0.4 * math.sin(2 * math.pi * t / 2.9 + 1))
        tx = w * 0.004 * math.sin(2 * math.pi * t / 4.7)
        ty = h * 0.004 * math.sin(2 * math.pi * t / 3.7 + 2)
        ang += dutch
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
        if abs(s - 1) < 1e-3 and abs(ang) < 1e-3 and abs(key) < 1e-4 and not whip:
            return img, lambda x, y: (x, y)
        # inverse map (output -> input): in = C + R(-th) (out - C - T) / s
        def inv(x, y):
            dx, dy = x - Cx - tx, y - Cy - ty
            return Cx + (cs * dx + sn * dy) / s, Cy + (-sn * dx + cs * dy) / s
        dst = [(0, 0), (w, 0), (w, h), (0, h)]
        src = [inv(*p) for p in dst]
        if abs(key) > 1e-4:  # low angle: the bottom of the picture comes closer; high angle: the top does
            pair = (2, 3) if key > 0 else (0, 1)
            k = abs(key)
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
        self.track = []
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
        _save_track(out, {"w": self.w, "h": self.h, "frames": self.track})
        return out


_STEPS = ("mid", "solo", "close")

# Pacing: seconds between cuts (at a sentence end / at a comma / at most), sideways drift per shot
# (fraction of the view) and how much each shot slowly zooms.
CUT_MIN, CUT_COMMA, CUT_MAX = 2.2, 3.4, 4.6
DRIFT = 0.13
PUSH = 0.07
PARALLAX = 0.45   # how far the room moves compared with the people when the camera drifts
HANDHELD = 0.35   # degrees of slow handheld float
DUTCH = 5.0       # degrees of a tilted shot
LOW, HIGH = 0.10, 0.08  # keystone of low and high angle shots
WHIP, WHIP_T = 0.15, 0.24
DOLLY = 0.2       # push-in of a dolly shot (fraction of the frame by the end of the shot)  # share of free cuts that whip pan in, and how long the swing lasts
WALK = 1.3  # seconds a person takes to walk into the scene
# Smoother motion (2026-11-18): share of cuts that become a camera glide, and how long a glide takes
GLIDE, GLIDE_T = 0.7, 0.8
OTS_FREE, OTS_FORCED = 0.3, 0.5  # over-the-shoulder shots always cut (was 0.5 / 0.75)
BURST_T = 0.6     # seconds an emphasis burst lasts
BRAND_LIGHT_RGBA = (90, 183, 230, 255)
WIPE_T = 0.45     # paper wipe between scenes: seconds to cover / uncover the picture
ARM_STEP = 2      # degrees: arm angles are rounded to this (was 6, which made gestures step)


_WIPE_PANELS = {}


def _wipe_panel(w, h):
    """The navy panel of a scene wipe, with torn light-blue edges on both sides (drawn once per size).
    Returns (image, edge width, solid width)."""
    if (w, h) not in _WIPE_PANELS:
        from PIL import ImageDraw
        from .config import BRAND_LIGHT, BRAND_NAVY
        E, Wsol, S = int(w * 0.09), int(w * 1.2), 2
        W_ = Wsol + 2 * E
        img = Image.new("RGBA", (W_ * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        rnd = random.Random(5)

        def edge(x0, amp, side):
            pts, y = [], -20
            while y < h + 40:
                pts.append(((x0 + side * rnd.uniform(0, amp)) * S, y * S))
                y += rnd.uniform(18, 46)
            return pts
        band = int(w * 0.03)
        left_b, left_n = edge(E * 0.25, E * 0.3, 1), edge(E * 0.25 + band, E * 0.35, 1)
        right_n, right_b = edge(E + Wsol, E * 0.35, -1), edge(E + Wsol + band, E * 0.3, -1)
        d.polygon(left_b + list(reversed(right_b)), fill=BRAND_LIGHT + (255,))
        d.polygon(left_n + list(reversed(right_n)), fill=BRAND_NAVY + (255,))
        _WIPE_PANELS[(w, h)] = (img.resize((W_, h), Image.LANCZOS), E, Wsol)
    return _WIPE_PANELS[(w, h)]


MENTION_GAP = 6.0  # seconds before the same name pulls the camera to that person again
NAMED = ("sarah", "richard", "elena", "daniel", "margaret")  # people who get a name label on first appearance
_ADDRESSEE = {"to", "at", "toward", "towards", "a", "al", "hacia", "con"}


def _norm_word(w: str) -> str:
    import unicodedata
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if c.isalnum() or c == "'")
    for suf in ("'s", "’s"):
        if w.endswith(suf):
            w = w[: -len(suf)]
    return w.strip("'")


def quote_speakers(scene) -> list[tuple[int, list[str]]]:
    """Who says the quotes of each paragraph, from `> say@P: richard, daniel` lines (P counts paragraphs
    from 0; several names = the paragraph's quotes in order). Shared with the voice code."""
    out = []
    for key, val in scene.extra.items():
        if key.startswith("say@"):
            names = [v.strip().lower().removeprefix("bug:") for v in val.split(",") if v.strip()]
            if names:
                out.append((int(key.split("@")[1]), names))
    return sorted(out)


def _ease_io(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def _ease_back(x: float, over: float = 1.7) -> float:
    """Ease out with a small overshoot past 1, then settle (0 -> 1)."""
    x = min(1.0, max(0.0, x)) - 1
    return 1 + (over + 1) * x ** 3 + over * x ** 2


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


def track_path(video: Path) -> Path:
    return video.with_name(video.stem + ".track.json")


def _save_track(video: Path, data: dict):
    import json
    track_path(video).write_text(json.dumps(data, separators=(",", ":")))


def is_animated(scene) -> bool:
    return "set" in scene.extra or "cast" in scene.extra


def render_scene(scene, seconds, words, out: Path, size, labeled=None, seed=0, lang="en", first=False) -> Path:
    """`first`: the episode's opening scene, which starts straight on the picture (no wipe in)."""
    parts = _cutaway_parts(scene, seconds, words)
    if len(parts) == 1:
        return SceneRenderer(scene, seconds, words, size, labeled, seed, lang, wipe_in=not first).render(out)
    from . import media
    files = []
    for k, (sub, t0, t1, sub_words) in enumerate(parts):
        f = out.with_name(f"{out.stem}_part{k}{out.suffix}")
        # a cutaway (lab, experiment) wipes in and out too, without a title
        SceneRenderer(sub, t1 - t0, sub_words, size, labeled, seed + 17 * k, lang,
                      wipe_in=not (first and k == 0), wipe_text=None if k == 0 else "").render(f)
        files.append(f)
    media.concat_files(files, out)
    import json
    tracks = [json.loads(track_path(f).read_text()) for f in files]
    joined, shot = [], 0
    for tr in tracks:  # shot numbers keep counting across the parts
        joined += [[r[0] + shot] + r[1:] for r in tr["frames"]]
        shot += 1 + max((r[0] for r in tr["frames"]), default=0)
    _save_track(out, {"w": tracks[0]["w"], "h": tracks[0]["h"], "frames": joined})
    for f in files:
        f.unlink()
        track_path(f).unlink()
    return out


_AT = re.compile(r"@(\d+)")


def _sub_scene(scene, p0, p1, extra=None):
    """Paragraphs p0..p1-1 of a scene as a scene of their own; every `@paragraph` is renumbered."""
    from dataclasses import replace
    paras = [x for x in scene.narration.split("\n\n") if x.strip()]
    src = dict(scene.extra if extra is None else extra)
    out = {}
    for key, val in src.items():
        if key.startswith("cutaway@"):
            continue
        m = _AT.search(key)
        if m:  # note@3: ...
            k = int(m.group(1))
            if p0 <= k < p1:
                out[_AT.sub(f"@{k - p0}", key)] = val
            continue
        if key in ("enter", "gesture"):
            items = []
            for item in [x.strip() for x in val.split(",") if x.strip()]:
                m = _AT.search(item)
                k = int(m.group(1)) if m else 0
                if p0 <= k < p1:
                    items.append(_AT.sub(f"@{k - p0}", item) if m else item)
                elif k < p0 and key == "enter":
                    items.append(_AT.sub("@0", item))  # already on stage
            if items:
                out[key] = ", ".join(items)
            continue
        out[key] = val
    return replace(scene, narration="\n\n".join(paras[p0:p1]), extra=out)


def _cutaway_parts(scene, seconds, words):
    """Split a scene at its `> cutaway@P: set | cast` lines: paragraph P is shown in another set with
    another cast (a researcher in a lab, the people in an experiment), then the scene comes back.
    Returns [(scene, t0, t1, words shifted to t0)]."""
    cuts = sorted((int(k.split("@")[1]), v) for k, v in scene.extra.items() if k.startswith("cutaway@"))
    paras = [x for x in scene.narration.split("\n\n") if x.strip()]
    cuts = [(p, v) for p, v in cuts if 0 <= p < len(paras)]
    if not cuts:
        return [(scene, 0.0, seconds, words)]
    if not words:
        toks = scene.narration.split()
        step = seconds / max(1, len(toks))
        words = [(i * step, (i + 0.8) * step, t) for i, t in enumerate(toks)]
    starts = paragraph_starts(scene.narration, words, seconds) + [seconds]
    snap = lambda t: round(t * FPS) / FPS
    bounds, specs, p = [], [], 0
    for cp, val in cuts:
        if cp > p:
            bounds.append((p, cp)); specs.append(None)
        bounds.append((cp, cp + 1)); specs.append(val)
        p = cp + 1
    if p < len(paras):
        bounds.append((p, len(paras))); specs.append(None)
    parts = []
    for (p0, p1), spec in zip(bounds, specs):
        t0, t1 = snap(starts[p0] if p0 else 0.0), snap(min(seconds, starts[p1]) if p1 < len(paras) else seconds)
        if t1 - t0 < 0.3:
            continue
        if spec is None:
            sub = _sub_scene(scene, p0, p1)
            cast = sub.extra.get("cast", "")
            if "->" in cast:  # keep the mood change at the same moment of the whole scene
                ts = float(scene.extra.get("switch", 0.5)) * seconds
                if t1 <= ts or t0 >= ts:
                    side = 0 if t1 <= ts else 1
                    items = []
                    for item in [x.strip() for x in cast.split(",") if x.strip()]:
                        ab = [x.strip() for x in item.split("->")]
                        if len(ab) == 2 and side == 1:
                            head = ab[0].rsplit(":", 1)[0] if ab[0].count(":") > (1 if ab[0].startswith("bug:") else 0) else ab[0]
                            items.append(f"{head}:{ab[1].split(':')[-1]}")
                        else:
                            items.append(ab[0])
                    sub.extra["cast"] = ", ".join(items)
                else:
                    sub.extra["switch"] = str((ts - t0) / (t1 - t0))
        else:
            set_name, _, cast = spec.partition("|")
            extra = {k: v for k, v in scene.extra.items() if k.startswith("note@")}
            extra.update({"set": set_name.strip(), "cast": cast.strip()})
            sub = _sub_scene(scene, p0, p1, extra)
        sw = [(a - t0, b - t0, w) for a, b, w in words if t0 - 0.01 <= a < t1 - 0.01]
        parts.append((sub, t0, t1, sw))
    return parts


def spanish_scene(en_scene, es_scene):
    """The scene as the Spanish picture sees it: the English staging (set, cast, entrances, gestures) with
    the Spanish narration, and the Spanish note cards where the Spanish script has its own `> note@` lines."""
    from dataclasses import replace
    extra = dict(en_scene.extra)
    es_notes = {k: v for k, v in es_scene.extra.items() if k.startswith("note@")}
    if es_notes:
        extra = {k: v for k, v in extra.items() if not k.startswith("note@")}
        extra.update(es_notes)
    return replace(en_scene, narration=es_scene.narration, extra=extra, title=es_scene.title)



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
