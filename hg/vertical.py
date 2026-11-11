"""Full-screen vertical Shorts (TikTok) cut from a scene's 16:9 animation.

Every shot is framed on its own: with one person (or voice) on screen the picture fills the whole phone
screen; when several people are on screen, or a paper card is up, the camera pulls back until they all fit,
and a blurred copy of the scene fills the space above and below. The framing comes from the scene's
`.track.json` (written by animate.py: shot number and the screen span of people, bubbles and cards).

The title sits at the top under a soft navy fade, the karaoke subtitles a little below the middle, both
clear of TikTok's own menu (top), buttons (right) and caption (bottom)."""
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import BRAND_NAVY, FPS, SHORT_H, SHORT_W

PAD = 0.05          # room kept on each side of the people (fraction of the 16:9 width)
BAND_TOP = 470      # a pulled-back picture starts below the title
TITLE_Y = 330       # centre of the title
FADE_H = 640        # height of the navy fade behind the title


def framings(track: dict, frames: int) -> list[tuple[float, float]]:
    """(view width, view centre x) in 16:9 pixels for every frame: one framing per shot."""
    w, h = track["w"], track["h"]
    full = h * SHORT_W / SHORT_H          # the view width that fills the phone screen
    rows = track["frames"][:frames]
    shots: dict[int, list] = {}
    for shot, x0, x1, note in rows:
        s = shots.setdefault(shot, [None, None, False])  # a paper card on screen adds its own span
        if x0 >= 0 or x1 >= 0:
            s[0] = x0 if s[0] is None else min(s[0], x0)
            s[1] = x1 if s[1] is None else max(s[1], x1)
    out = {}
    for shot, (x0, x1, note) in shots.items():
        if x0 is None:
            vw, cx = full, w / 2
        else:
            x0, x1 = max(0, x0), min(w, x1)
            vw = min(w, max(full, x1 - x0 + 2 * PAD * w))
            cx = (x0 + x1) / 2
        cx = min(max(cx, vw / 2), w - vw / 2)
        out[shot] = (vw, cx)
    res = [out[r[0]] for r in rows]
    while len(res) < frames:  # the track can be a frame short of the video
        res.append(res[-1] if res else (w, w / 2))
    return res


def title_layer(title: str, out: Path) -> Path:
    """Transparent 1080x1920 layer: a navy fade at the top with the title handwritten over it."""
    from . import sketch
    img = Image.new("RGBA", (SHORT_W, SHORT_H), (0, 0, 0, 0))
    fade = Image.new("L", (1, FADE_H))
    for y in range(FADE_H):
        fade.putpixel((0, y), int(215 * (1 - y / FADE_H) ** 1.3))
    navy = Image.new("RGBA", (SHORT_W, FADE_H), BRAND_NAVY + (255,))
    navy.putalpha(fade.resize((SHORT_W, FADE_H)))
    img.alpha_composite(navy)
    if title:
        d = ImageDraw.Draw(img)
        size = 96
        while True:
            font = ImageFont.truetype(str(sketch.HAND_FONT), size)
            lines, cur = [], ""
            for wd in title.split():
                trial = (cur + " " + wd).strip()
                if d.textlength(trial, font=font) > SHORT_W - 200 and cur:
                    lines.append(cur); cur = wd
                else:
                    cur = trial
            if cur:
                lines.append(cur)
            if len(lines) <= 3 or size <= 64:
                break
            size -= 8
        y0 = TITLE_Y - (len(lines) - 1) * size * 0.55
        for k, line in enumerate(lines):
            d.text((SHORT_W / 2 - 10, y0 + k * size * 1.1), line, font=font, fill=(255, 255, 255), anchor="mm",
                   stroke_width=5, stroke_fill=BRAND_NAVY)
    img.save(out)
    return out


def _compose(frame: Image.Image, vw: float, cx: float) -> Image.Image:
    w, h = frame.size
    x0 = int(round(cx - vw / 2))
    view = frame.crop((x0, 0, x0 + int(round(vw)), h))
    s = SHORT_W / view.width
    band_h = int(round(h * s))
    if band_h >= SHORT_H - 2:  # fills the screen
        return view.resize((SHORT_W, SHORT_H), Image.BILINEAR)
    # blurred copy of the scene behind, so the screen is never empty
    k = SHORT_H / h
    bw = int(w * k)
    small = frame.resize((max(1, bw // 12), SHORT_H // 12), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    bg = small.resize((bw, SHORT_H), Image.BILINEAR)
    bx = int(min(max(cx * k - SHORT_W / 2, 0), bw - SHORT_W))
    bg = bg.crop((bx, 0, bx + SHORT_W, SHORT_H))
    bg = Image.blend(bg, Image.new("RGB", bg.size, BRAND_NAVY), 0.45)
    y = int(min(max(BAND_TOP, (SHORT_H - band_h) / 2 - 100), SHORT_H - band_h))  # below the title
    bg.paste(view.resize((SHORT_W, band_h), Image.BILINEAR), (0, y))
    return bg


def render(scene_video: Path, scene_wav: Path, seconds: float, title: str, ass: Path, work: Path, out: Path) -> Path:
    from .animate import track_path
    tp = track_path(scene_video)
    track = json.loads(tp.read_text()) if tp.exists() else None
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "json", str(scene_video)], capture_output=True, text=True, check=True).stdout
    st = json.loads(probe)["streams"][0]
    w, h = st["width"], st["height"]
    frames = int(round(seconds * FPS))
    if track is None or (track["w"], track["h"]) != (w, h):  # no framing info: show the whole width
        plan = [(w, w / 2)] * frames
    else:
        plan = framings(track, frames)
    layer = title_layer(title, work / f"{out.stem}_title.png")
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(scene_video), "-t", f"{seconds:.3f}",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-r", str(FPS), "-"], stdout=subprocess.PIPE)
    sub = str(ass).replace("\\", "/").replace(":", "\\:")
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{SHORT_W}x{SHORT_H}", "-r", str(FPS), "-i", "-",
                            "-loop", "1", "-i", str(layer), "-i", str(scene_wav),
                            "-filter_complex", f"[0:v][1:v]overlay=0:0:shortest=1,subtitles='{sub}'[v]",
                            "-map", "[v]", "-map", "2:a", "-t", f"{seconds:.3f}",
                            "-c:v", "libx264", "-preset", "faster", "-crf", "21", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)],
                           stdin=subprocess.PIPE)
    size = w * h * 3
    try:
        for f in range(frames):
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            frame = Image.frombytes("RGB", (w, h), buf)
            vw, cx = plan[min(f, len(plan) - 1)]
            enc.stdin.write(_compose(frame, vw, cx).tobytes())
    finally:
        enc.stdin.close()
        dec.stdout.close()
        dec.wait()
        if enc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed while making {out}")
    return out
