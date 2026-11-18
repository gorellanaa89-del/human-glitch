"""Turn an episode folder into a finished long video, a Short, a thumbnail and captions."""
import os
import json
import math
import re
from pathlib import Path

import yaml

from . import animate, broll, bugs, graphics, media, subtitles, tts
from .config import BROLL_SECONDS, CARD_SECONDS, FPS, H, MAX_ES_TEMPO, SHORT_H, SHORT_W, VOICE_RATE, VOICES, W, CAST
from .script import parse_script

X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]


def _attach_punctuation(words, text):
    """Edge word boundaries drop punctuation; copy it back from the script so captions read naturally."""
    tokens = text.split()
    out, j = [], 0
    for s, e, w in words:
        key = re.sub(r"\W", "", w).lower()
        k = j
        while k < len(tokens) and not re.sub(r"\W", "", tokens[k]).lower().startswith(key):
            k += 1
        if key and k < len(tokens) and k - j <= 3:
            out.append((s, e, tokens[k]))
            j = k + 1
        else:
            out.append((s, e, w))
    return out


def _speakers(sc) -> dict:
    """`> say@P: richard, daniel` lines: who says the quotes of paragraph P, in order."""
    out = {}
    for key, value in sc.extra.items():
        if key.startswith("say@") and key[4:].isdigit():
            names = [n.strip().lower() for n in value.split(",") if n.strip()]
            # an inner voice (e.g. "blamer" or "bug:blamer") speaks with the shared inner-voice voice
            out[int(key[4:])] = ["voice" if n.removeprefix("bug:") in bugs.BUGS else n for n in names]
    return out


def _shift(words, offset, scale=1.0):
    return [(offset + s * scale, offset + e * scale, t) for s, e, t in words]


def _card_clip(png: Path, seconds: float, out: Path):
    media.run(["-loop", "1", "-t", f"{seconds:.3f}", "-i", png,
               "-vf", "noise=alls=4:allf=t,fade=t=in:st=0:d=0.25", *X264, out])


def _broll_clip(src: Path, seconds: float, out: Path):
    start = max(0.0, min(2.0, media.duration(src) - seconds - 0.1))
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          "eq=brightness=-0.06:saturation=0.8,vignette=PI/5")
    media.run(["-ss", f"{start:.2f}", "-stream_loop", "-1", "-i", src, "-t", f"{seconds:.3f}", "-vf", vf, *X264, out])


def _background_clip(png: Path, seconds: float, out: Path):
    frames = max(1, int(seconds * FPS))
    vf = (f"zoompan=z='min(zoom+0.0003,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={W}x{H}:fps={FPS}")
    media.run(["-i", png, "-vf", vf, "-frames:v", frames, *X264, out])


def _scene_video(i, scene, seconds, work: Path, used: set) -> tuple[Path, Path | None]:
    segs = []
    card_png = graphics.scene_card(scene.card or scene.title, f"{i + 1:02d}", work / f"s{i}_card.png", seed=i)
    card = work / f"s{i}_seg0.mp4"
    _card_clip(card_png, min(CARD_SECONDS, seconds), card)
    segs.append(card)
    rest = seconds - CARD_SECONDS
    first_broll = None
    if rest > 0.05:
        need = math.ceil(rest / BROLL_SECONDS)
        clips = broll.fetch(scene.keywords, need, work, used)
        remaining, n = rest, 1
        for clip in clips:
            seg_len = min(BROLL_SECONDS, remaining)
            seg = work / f"s{i}_seg{n}.mp4"
            try:
                _broll_clip(clip, seg_len, seg)
            except RuntimeError as e:
                print(f"  skipping clip {clip.name}: {e}")
                continue
            first_broll = first_broll or seg
            segs.append(seg)
            remaining -= seg_len
            n += 1
            if remaining <= 0.05:
                break
        if remaining > 0.05:
            bg = graphics.background(scene.title, work / f"s{i}_bg.png", card=scene.card)
            seg = work / f"s{i}_seg{n}.mp4"
            _background_clip(bg, remaining, seg)
            segs.append(seg)
    joined = work / f"s{i}_joined.mp4"
    media.concat_files(segs, joined)
    out = work / f"s{i}_video.mp4"
    media.run(["-i", joined, "-t", f"{seconds:.3f}", *X264, out])
    keep = first_broll
    for f in segs + [joined]:
        if f != keep:
            f.unlink(missing_ok=True)
    return out, first_broll


def _fit_spanish(wav: Path, target: float, out: Path) -> tuple[float, bool]:
    d = media.duration(wav)
    tempo = 1.0
    if d > target:
        tempo = min(d / target, MAX_ES_TEMPO)
    af = (f"atempo={tempo:.4f}," if tempo > 1.0 else "") + f"apad,atrim=0:{target:.3f}"
    media.run(["-i", wav, "-af", af, "-ar", "48000", "-ac", "1", out])
    return tempo, d / tempo > target + 0.05


def _chapters(titles, offsets):
    lines = []
    for t, off in zip(titles, offsets):
        s = int(off)
        lines.append(f"{s // 60:02d}:{s % 60:02d} {t}")
    return "\n".join(lines)


def _short_frame(title: str, out: Path) -> Path:
    """The still 1080x1920 frame of a Short: navy background, the title handwritten in white at the top,
    the channel name above it, and a thin light-blue line framing the picture area."""
    from PIL import Image, ImageDraw, ImageFont
    from .config import BRAND_LIGHT, BRAND_NAVY, CHANNEL
    from . import sketch
    img = Image.new("RGB", (SHORT_W, SHORT_H), BRAND_NAVY)
    d = ImageDraw.Draw(img)
    small = ImageFont.truetype(str(sketch.HAND_FONT), 44)
    d.text((SHORT_W / 2, 150), CHANNEL, font=small, fill=BRAND_LIGHT, anchor="mm")
    size = 92
    while True:
        font = ImageFont.truetype(str(sketch.HAND_FONT), size)
        lines, cur = [], ""
        for wd in title.split():
            trial = (cur + " " + wd).strip()
            if d.textlength(trial, font=font) > SHORT_W - 140 and cur:
                lines.append(cur); cur = wd
            else:
                cur = trial
        if cur:
            lines.append(cur)
        if len(lines) <= 3 or size <= 60:
            break
        size -= 8
    y0 = 360 - (len(lines) - 1) * size * 0.55
    for k, line in enumerate(lines):
        d.text((SHORT_W / 2, y0 + k * size * 1.1), line, font=font, fill=(255, 255, 255), anchor="mm")
    d.rectangle((0, 552, SHORT_W, 560), fill=BRAND_LIGHT)
    d.rectangle((0, 1320, SHORT_W, 1328), fill=BRAND_LIGHT)
    img.save(out)
    return out


def _vertical(scene, scene_wav: Path, words, out: Path):
    animate.render_scene(scene, min(59.0, media.duration(scene_wav)), words, out, (SHORT_W, SHORT_H), set(), seed=7)


def _short(scene_video: Path, scene_wav: Path, words, out_dir: Path, work: Path, scene=None,
           name: str = "short.mp4", vertical_cache: dict | None = None, timing_words=None,
           vertical_path: Path | None = None, title: str | None = None) -> Path | None:
    """A vertical Short from one scene: subtitles burned in (karaoke), cut at the last full sentence before 58 s.
    `words` are the subtitle words (any language); `timing_words` (English) time the animation."""
    limit = 58.0
    end = None
    for s, e, t in words:
        if e > limit:
            break
        if t[-1:] in ".?!":
            end = e
    if end is None:
        end = min(limit, words[-1][1]) if words else None
    if not end:
        return None
    end += 0.3
    animated = scene is not None and animate.is_animated(scene)
    stem = Path(name).stem
    out = out_dir / name
    if animated:
        # Full-screen vertical picture: each shot is framed on whoever is on screen and pulls back when
        # several people are (see vertical.py); subtitles sit above TikTok's caption, left of its buttons.
        from . import vertical
        ass = subtitles.write_ass([w for w in words if w[1] <= end], work / f"{stem}.ass", SHORT_W, SHORT_H,
                                  vertical=True, margin=0.235, size=70, margin_lr=(70, 170))
        return vertical.render(scene_video, scene_wav, end, title or "", ass, work, out)
    ass = subtitles.write_ass([w for w in words if w[1] <= end], work / f"{stem}.ass", SHORT_W, SHORT_H,
                              vertical=True)
    fc = (f"[0:v]scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=increase,crop={SHORT_W}:{SHORT_H},"
          f"boxblur=20:2,eq=brightness=-0.15[bg];"
          f"[0:v]scale={SHORT_W}:-2[fg];[bg][fg]overlay=0:(H-h)/2-160,subtitles={ass}[v]")
    media.run(["-i", scene_video, "-i", scene_wav, "-t", f"{end:.3f}", "-filter_complex", fc,
               "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    return out


def build(episode: Path, engine: str = "edge", max_seconds: float | None = None, only_scene: int | None = None) -> dict:
    """Render an episode. With max_seconds, only the opening is rendered (a quick test): narration is cut
    at that point and the Short and thumbnail are skipped. With only_scene (0-based), only that scene's voice,
    picture and vertical Short picture are made and cached in output/work, so scenes can be rendered on several
    machines at once; a later full build reuses every cached scene."""
    import json as _json
    meta = yaml.safe_load((episode / "meta.yaml").read_text(encoding="utf-8"))
    from . import sets
    # per-episode narrator: meta.yaml `voices: {en: ..., es: ...}` and `voice_rate: {en: ..., es: ...}`
    voices = {**VOICES, **(meta.get("voices") or {})}
    rates = {**VOICE_RATE, **(meta.get("voice_rate") or {})}
    styles = meta.get("voice_style") or {}  # only for gemini:<Voice> narrators
    cast = {lang: {**CAST.get(lang, {}), **{k: tuple(v) if isinstance(v, (list, tuple)) else (v, "")
                                            for k, v in ((meta.get("cast") or {}).get(lang) or {}).items()}}
            for lang in ("en", "es")}
    sets.MODE = os.environ.get("HG_BACKGROUNDS") or meta.get("backgrounds", "drawn")  # "photo": real photos where one exists
    scenes = parse_script(episode / "script.en.md")
    es_path = episode / "script.es.md"
    scenes_es = parse_script(es_path) if es_path.exists() else []
    if scenes_es and len(scenes_es) != len(scenes):
        raise ValueError(f"script.es.md has {len(scenes_es)} scenes but script.en.md has {len(scenes)}")

    out_dir = episode / "output"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    warnings, used = [], set()

    en_wavs, es_wavs, videos, videos_es, offsets = [], [], [], [], []
    en_words, es_words, scene_words, scene_es_words = [], [], [], []
    first_frame_src = None
    labeled: set = set()  # bugs whose name label was already shown
    t = 0.0
    for i, sc in enumerate(scenes):
        if max_seconds and t >= max_seconds - 0.5:
            scenes = scenes[:i]
            break
        bug_names = {a.name for a in animate.parse_cast(sc.extra.get("cast", "")) if a.is_bug}
        if only_scene is not None and i != only_scene:
            labeled.update(bug_names)  # keep the "first appearance" labels identical to a full build
            continue
        cache_file = work / f"s{i}.json"
        if not max_seconds and cache_file.exists():
            c = _json.loads(cache_file.read_text())
            print(f"Scene {i + 1}/{len(scenes)}: {sc.title} (already rendered)")
            labeled.update(bug_names)
            wav, video, seconds = work / f"s{i}_en.wav", work / c["video"], c["seconds"]
            words = [tuple(w) for w in c["words"]]
            offsets.append(t); en_wavs.append(wav); videos.append(video)
            scene_words.append(words); en_words += _shift(words, t)
            if scenes_es:
                es_wavs.append(work / f"s{i}_es.wav")
                videos_es.append(work / c["video_es"] if c.get("video_es") else video)
                local_es = [tuple(w) for w in c["es_words"]]
                scene_es_words.append(local_es); es_words += _shift(local_es, t)
                if c.get("es_cut"):
                    warnings.append(f"Scene {i + 1}: Spanish narration is too long and was cut at the end; shorten it.")
            t += seconds
            continue
        print(f"Scene {i + 1}/{len(scenes)}: {sc.title}")
        wav = work / f"s{i}_en.wav"
        words = _attach_punctuation(tts.synthesize(sc.narration, voices["en"], wav, engine, rates["en"], styles.get("en", ""), _speakers(sc), cast["en"]), sc.narration)
        seconds = media.duration(wav)
        full_seconds = seconds
        cut = False
        if max_seconds and t + seconds > max_seconds:
            seconds = max_seconds - t
            cut_wav = work / f"s{i}_en_cut.wav"
            media.run(["-i", wav, "-t", f"{seconds:.3f}", "-af", f"afade=t=out:st={max(0, seconds - 0.6):.3f}:d=0.6", cut_wav])
            wav = cut_wav
            words = [w for w in words if w[0] < seconds]
        labeled_before = set(labeled)
        if animate.is_animated(sc):
            video = work / f"s{i}_video.mp4"
            animate.render_scene(sc, seconds, words, video, (W, H), labeled, seed=i)
            broll_seg = None
        else:
            video, broll_seg = _scene_video(i, sc, seconds, work, used)
        first_frame_src = first_frame_src or broll_seg
        offsets.append(t)
        en_wavs.append(wav)
        videos.append(video)
        scene_words.append(words)
        en_words += _shift(words, t)

        if scenes_es:
            es_raw = work / f"s{i}_es_raw.wav"
            es_sc = scenes_es[i]
            ew = _attach_punctuation(tts.synthesize(es_sc.narration, voices["es"], es_raw, engine, rates["es"], styles.get("es", ""), _speakers(es_sc), cast["es"]), es_sc.narration)
            es_wav = work / f"s{i}_es.wav"
            tempo, cut = _fit_spanish(es_raw, full_seconds, es_wav)
            if seconds < full_seconds:
                es_cut = work / f"s{i}_es_cut.wav"
                media.run(["-i", es_wav, "-t", f"{seconds:.3f}", "-af", f"afade=t=out:st={max(0, seconds - 0.6):.3f}:d=0.6", es_cut])
                es_wav = es_cut
            if cut:
                warnings.append(f"Scene {i + 1}: Spanish narration is too long and was cut at the end; shorten it.")
            es_wavs.append(es_wav)
            local_es = [w for w in _shift(ew, 0.0, 1 / tempo) if w[0] < seconds]
            scene_es_words.append(local_es)
            # The Spanish picture: same staging, but the voices' Spanish names, Spanish bubbles and cards,
            # and cuts that follow the Spanish narration.
            video_es = video
            if animate.is_animated(sc) and os.environ.get("HG_ES_PICTURE", "1") != "0":
                video_es = work / f"s{i}_video_es.mp4"
                animate.render_scene(animate.spanish_scene(sc, es_sc), seconds, local_es, video_es, (W, H),
                                     labeled_before, seed=i, lang="es")
            videos_es.append(video_es)
            es_words += _shift(local_es, t)
        labeled.update(bug_names)
        if not max_seconds:
            cache_file.write_text(_json.dumps({"video": Path(video).name, "seconds": seconds, "words": words,
                                               "es_words": scene_es_words[-1] if scenes_es else [], "es_cut": bool(cut),
                                               "video_es": Path(videos_es[-1]).name if scenes_es else None}))
        if only_scene is not None:
            return {"scene": i + 1, "seconds": round(seconds, 1)}
        t += seconds

    body = work / "body.mp4"
    media.concat_files(videos, body)
    en_wav = work / "en.wav"
    media.concat_files(en_wavs, en_wav, reencode_audio=True)
    mark = graphics.watermark(work / "watermark.png")

    final = out_dir / "video.mp4"
    print("Rendering final video...")
    media.run(["-i", body, "-i", en_wav, "-i", mark,
               "-filter_complex", "[0:v][2:v]overlay=0:0[v]",
               "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "faster", "-crf", "20",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])

    files = {"video": final.name}
    subtitles.write_srt(en_words, out_dir / "captions.en.srt")
    files["captions_en"] = "captions.en.srt"
    if es_wavs:
        es_wav = work / "es.wav"
        media.concat_files(es_wavs, es_wav, reencode_audio=True)
        media.run(["-i", es_wav, "-c:a", "aac", "-b:a", "160k", out_dir / "audio.es.m4a"])
        subtitles.write_srt(es_words, out_dir / "captions.es.srt")
        files.update(audio_es="audio.es.m4a", captions_es="captions.es.srt")
        if any(Path(a) != Path(b) for a, b in zip(videos, videos_es)):
            body_es = work / "body_es.mp4"
            media.concat_files(videos_es, body_es)
            print("Rendering final Spanish video...")
            media.run(["-i", body_es, "-i", out_dir / "audio.es.m4a", "-i", mark,
                       "-filter_complex", "[0:v][2:v]overlay=0:0[v]",
                       "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "faster", "-crf", "20",
                       "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart",
                       out_dir / "video.es.mp4"])
            files["video_es"] = "video.es.mp4"

    idx = int(meta.get("short_scene") or 0) - 1
    if max_seconds:
        idx = -1  # a test of the opening: no Short or thumbnail
    frame = None
    if 0 <= idx < len(scenes) and animate.is_animated(scenes[idx]):
        frame = work / "thumb_frame.png"
        media.run(["-ss", f"{media.duration(videos[idx]) * 0.35:.2f}", "-i", videos[idx], "-frames:v", "1", frame])
    elif first_frame_src:
        frame = work / "thumb_frame.png"
        media.run(["-ss", "1", "-i", first_frame_src, "-frames:v", "1", frame])
    if 0 <= idx < len(scenes) and animate.is_animated(scenes[idx]):
        animate.thumbnail(scenes[idx], meta.get("thumbnail_text") or meta["title"], out_dir / "thumbnail.jpg")
    else:
        graphics.thumbnail(meta.get("thumbnail_text") or meta["title"], out_dir / "thumbnail.jpg", frame)
    files["thumbnail"] = "thumbnail.jpg"

    # Shorts: one per listed scene and language, with the subtitles burned in
    short_specs = meta.get("shorts") or ([{"scene": idx + 1}] if 0 <= idx < len(scenes) else [])
    if max_seconds:
        short_specs = []
    shorts, vcache = [], {}
    for spec in short_specs:
        k = int(spec["scene"]) - 1
        if not 0 <= k < len(scenes):
            continue
        langs = [("en", en_wavs[k], scene_words[k])]
        if scenes_es:
            langs.append(("es", es_wavs[k], scene_es_words[k]))
        for lang, wav, words in langs:
            if lang != "en" and not spec.get(lang):
                continue
            print(f"Short: scene {k + 1} ({lang})")
            f = _short(videos_es[k] if lang == "es" and videos_es else videos[k], wav, words, out_dir, work, scenes[k], name=f"short-{k + 1:02d}-{lang}.mp4",
                       vertical_cache=vcache, timing_words=scene_words[k],
                       vertical_path=work / f"short-{k + 1:02d}_v.mp4", title=spec.get(lang))
            if f:
                shorts.append({"file": f.name, "scene": k + 1, "lang": lang,
                               "title": spec.get(lang) or meta["title"].split("(")[0].strip()})
    if shorts:
        files["shorts"] = shorts

    description = meta.get("description", "").replace("{chapters}", _chapters([s.title for s in scenes], offsets))
    (out_dir / "description.txt").write_text(description, encoding="utf-8")
    report = {
        "title": meta["title"],
        "duration_seconds": round(media.duration(final), 1),
        "scenes": len(scenes),
        "stock_clips": len(used),
        "tts": engine,
        "files": files,
        "warnings": warnings,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def build_shorts(episode: Path, engine: str = "edge") -> list[str]:
    """Only the Shorts: renders just the scenes listed under `shorts:` in meta.yaml (voice and picture,
    cached in output/work like `build --scene`), then cuts the vertical Shorts into output/."""
    import json as _json
    meta = yaml.safe_load((episode / "meta.yaml").read_text(encoding="utf-8"))
    scenes = parse_script(episode / "script.en.md")
    out_dir, work = episode / "output", episode / "output" / "work"
    made = []
    for spec in meta.get("shorts") or []:
        k = int(spec["scene"]) - 1
        if not 0 <= k < len(scenes):
            continue
        cache_file = work / f"s{k}.json"
        if not cache_file.exists():
            build(episode, engine, only_scene=k)
        c = _json.loads(cache_file.read_text())
        langs = [("en", work / f"s{k}_en.wav", c["words"], work / c["video"])]
        if c.get("es_words"):
            langs.append(("es", work / f"s{k}_es.wav", c["es_words"], work / (c.get("video_es") or c["video"])))
        for lang, wav, words, video in langs:
            if lang != "en" and not spec.get(lang):
                continue
            print(f"Short: scene {k + 1} ({lang})")
            f = _short(video, wav, [tuple(w) for w in words], out_dir, work, scenes[k],
                       name=f"short-{k + 1:02d}-{lang}.mp4", title=spec.get(lang))
            if f:
                made.append(f.name)
    return made
