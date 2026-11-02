"""Branded still images: scene cards, backgrounds, watermark, thumbnail."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .config import BG, CHANNEL, CYAN, GREEN, MAGENTA, WHITE, font_mono, font_sans


def _grid(w: int, h: int, step: int = 60) -> Image.Image:
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=(19, 27, 35))
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=(19, 27, 35))
    for y in range(0, h, 4):
        d.line([(0, y), (w, y)], fill=(9, 12, 16))
    return img


def _vignette(img: Image.Image, strength: int = 170) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([-w * 0.2, -h * 0.3, w * 1.2, h * 1.3], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) // 5))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    out = Image.composite(img, dark, mask)
    return Image.blend(img, out, strength / 255)


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def _fit(draw, text, font_path, max_w, max_h, start, minimum=40):
    size = start
    while size > minimum:
        font = ImageFont.truetype(font_path, size)
        lines = _wrap(draw, text, font, max_w)
        if len(lines) * size * 1.15 <= max_h and all(draw.textlength(l, font=font) <= max_w for l in lines):
            return font, lines
        size -= 6
    font = ImageFont.truetype(font_path, minimum)
    return font, _wrap(draw, text, font, max_w)


def _glitch_text(img, lines, font, cx, cy, color, offset=7, last_word_color=None):
    d = ImageDraw.Draw(img)
    size = font.size
    total = len(lines) * size * 1.15
    y = cy - total / 2
    for i, line in enumerate(lines):
        x = cx - d.textlength(line, font=font) / 2
        d.text((x - offset, y), line, font=font, fill=MAGENTA)
        d.text((x + offset, y), line, font=font, fill=CYAN)
        if last_word_color and i == len(lines) - 1 and " " in line:
            head, tail = line.rsplit(" ", 1)
            d.text((x, y), head + " ", font=font, fill=color)
            d.text((x + d.textlength(head + " ", font=font), y), tail, font=font, fill=last_word_color)
        else:
            d.text((x, y), line, font=font, fill=color)
        y += size * 1.15


def _slice_shift(img: Image.Image, seed: int, bands: int = 5) -> Image.Image:
    rnd = random.Random(seed)
    w, h = img.size
    out = img.copy()
    for _ in range(bands):
        # Keep slices off the top label/watermark and the bottom subtitle area.
        y = rnd.randint(int(h * 0.15), int(h * 0.78))
        bh = rnd.randint(6, 28)
        dx = rnd.choice([-1, 1]) * rnd.randint(12, 48)
        band = img.crop((0, y, w, y + bh))
        out.paste(band, (dx, y))
    return out


def scene_card(text: str, label: str, out: Path, w: int = 1920, h: int = 1080, seed: int = 0) -> Path:
    img = _grid(w, h)
    d = ImageDraw.Draw(img)
    small = ImageFont.truetype(font_mono(), int(h * 0.026))
    tag = f"SCENE {label}"
    d.text((int(w * 0.96 - d.textlength(tag, font=small)), int(h * 0.05)), tag, font=small, fill=GREEN)
    font, lines = _fit(d, text.upper(), font_mono(), int(w * 0.84), int(h * 0.6), start=int(h * 0.12))
    _glitch_text(img, lines, font, w / 2, h / 2, GREEN)
    img = _slice_shift(_vignette(img), seed)
    img.save(out)
    return out


def background(title: str, out: Path, w: int = 1920, h: int = 1080, card: str = "") -> Path:
    img = _grid(w, h)
    d = ImageDraw.Draw(img)
    if card:
        big, lines = _fit(d, card.upper(), font_mono(), int(w * 0.9), int(h * 0.7), start=int(h * 0.14))
        _glitch_text(img, lines, big, w / 2, h * 0.45, (24, 64, 44), offset=2)
        d = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_mono(), int(h * 0.03))
    # Top-right, away from the subtitles at the bottom and the watermark at top-left.
    tag = f"> {title.lower()}_"
    d.text((int(w * 0.96 - d.textlength(tag, font=font)), int(h * 0.04)), tag, font=font, fill=(34, 70, 52))
    _vignette(img).save(out)
    return out


def watermark(out: Path, w: int = 1920, h: int = 1080) -> Path:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    font = ImageFont.truetype(font_mono(), int(h * 0.026))
    ImageDraw.Draw(img).text((int(w * 0.03), int(h * 0.04)), CHANNEL, font=font, fill=GREEN + (170,))
    img.save(out)
    return out


def thumbnail(text: str, out: Path, frame: Path | None = None) -> Path:
    w, h = 1280, 720
    if frame and frame.exists():
        img = Image.open(frame).convert("RGB").resize((w, h))
        img = ImageEnhance.Color(img).enhance(0.4)
        img = ImageEnhance.Brightness(img).enhance(0.45)
    else:
        img = _grid(w, h, step=48)
    img = _vignette(img, 200)
    d = ImageDraw.Draw(img)
    font, lines = _fit(d, text.upper(), font_sans(), int(w * 0.86), int(h * 0.62), start=170, minimum=70)
    _glitch_text(img, lines, font, w / 2, h * 0.47, WHITE, offset=6, last_word_color=GREEN)
    tag = ImageFont.truetype(font_mono(), 30)
    label = f" {CHANNEL} "
    tw = d.textlength(label, font=tag)
    d.rectangle([40, h - 80, 40 + tw, h - 36], fill=GREEN)
    d.text((40, h - 78), label, font=tag, fill=BG)
    _slice_shift(img, 7, bands=3).save(out, quality=92)
    return out
