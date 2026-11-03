"""Turn an episode folder into a finished long video, a Short, a thumbnail and captions."""
import json
import math
import re
from pathlib import Path

import yaml

from . import animate, broll, graphics, media, subtitles, tts
from .config import BROLL_SECONDS, CARD_SECONDS, FPS, H, MAX_ES_TEMPO, SHORT_H, SHORT_W, VOICE_RATE, VOICES, W
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


def _short(scene_video: Path, scene_wav: Path, words, out_dir: Path, work: Path, scene=None) -> Path | None:
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
    ass = subtitles.write_ass([w for w in words if w[1] <= end], work / "short.ass", SHORT_W, SHORT_H,
                              vertical=True, top=animated)
    out = out_dir / "short.mp4"
    if animated:
        vertical = work / "short_v.mp4"
        animate.render_scene(scene, end, words, vertical, (SHORT_W, SHORT_H), set(), seed=7)
        media.run(["-i", vertical, "-i", scene_wav, "-t", f"{end:.3f}", "-vf", f"subtitles={ass}",
                   "-c:v", "libx264", "-preset", "faster", "-crf", "21", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
        return out
    fc = (f"[0:v]scale={SHORT_W}:{SHORT_H}:force_original_aspect_ratio=increase,crop={SHORT_W}:{SHORT_H},"
          f"boxblur=20:2,eq=brightness=-0.15[bg];"
          f"[0:v]scale={SHORT_W}:-2[fg];[bg][fg]overlay=0:(H-h)/2-160,subtitles={ass}[v]")
    media.run(["-i", scene_video, "-i", scene_wav, "-t", f"{end:.3f}", "-filter_complex", fc,
               "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    return out


def build(episode: Path, engine: str = "edge", max_seconds: float | None = None) -> dict:
    """Render an episode. With max_seconds, only the opening is rendered (a quick test): narration is cut
    at that point and the Short and thumbnail are skipped."""
    meta = yaml.safe_load((episode / "meta.yaml").read_text(encoding="utf-8"))
    scenes = parse_script(episode / "script.en.md")
    es_path = episode / "script.es.md"
    scenes_es = parse_script(es_path) if es_path.exists() else []
    if scenes_es and len(scenes_es) != len(scenes):
        raise ValueError(f"script.es.md has {len(scenes_es)} scenes but script.en.md has {len(scenes)}")

    out_dir = episode / "output"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    warnings, used = [], set()

    en_wavs, es_wavs, videos, offsets = [], [], [], []
    en_words, es_words, scene_words = [], [], []
    first_frame_src = None
    labeled: set = set()  # bugs whose name label was already shown
    t = 0.0
    for i, sc in enumerate(scenes):
        if max_seconds and t >= max_seconds - 0.5:
            scenes = scenes[:i]
            break
        print(f"Scene {i + 1}/{len(scenes)}: {sc.title}")
        wav = work / f"s{i}_en.wav"
        words = _attach_punctuation(tts.synthesize(sc.narration, VOICES["en"], wav, engine, VOICE_RATE["en"]), sc.narration)
        seconds = media.duration(wav)
        full_seconds = seconds
        if max_seconds and t + seconds > max_seconds:
            seconds = max_seconds - t
            cut_wav = work / f"s{i}_en_cut.wav"
            media.run(["-i", wav, "-t", f"{seconds:.3f}", "-af", f"afade=t=out:st={max(0, seconds - 0.6):.3f}:d=0.6", cut_wav])
            wav = cut_wav
            words = [w for w in words if w[0] < seconds]
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
            ew = _attach_punctuation(tts.synthesize(es_sc.narration, VOICES["es"], es_raw, engine, VOICE_RATE["es"]), es_sc.narration)
            es_wav = work / f"s{i}_es.wav"
            tempo, cut = _fit_spanish(es_raw, full_seconds, es_wav)
            if seconds < full_seconds:
                es_cut = work / f"s{i}_es_cut.wav"
                media.run(["-i", es_wav, "-t", f"{seconds:.3f}", "-af", f"afade=t=out:st={max(0, seconds - 0.6):.3f}:d=0.6", es_cut])
                es_wav = es_cut
            if cut:
                warnings.append(f"Scene {i + 1}: Spanish narration is too long and was cut at the end; shorten it.")
            es_wavs.append(es_wav)
            es_words += [w for w in _shift(ew, t, 1 / tempo) if w[0] < t + seconds]
        t += seconds

    body = work / "body.mp4"
    media.concat_files(videos, body)
    en_wav = work / "en.wav"
    media.concat_files(en_wavs, en_wav, reencode_audio=True)
    ass = subtitles.write_ass(en_words, work / "en.ass", W, H)
    mark = graphics.watermark(work / "watermark.png")

    final = out_dir / "video.mp4"
    print("Rendering final video...")
    media.run(["-i", body, "-i", en_wav, "-i", mark,
               "-filter_complex", f"[0:v][2:v]overlay=0:0,subtitles={ass}[v]",
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
        # a full Spanish cut (Spanish voice + Spanish subtitles) to review, or to publish on its own
        es_ass = subtitles.write_ass(es_words, work / "es.ass", W, H)
        print("Rendering Spanish video...")
        media.run(["-i", body, "-i", es_wav, "-i", mark,
                   "-filter_complex", f"[0:v][2:v]overlay=0:0,subtitles={es_ass}[v]",
                   "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "faster", "-crf", "20",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_dir / "video.es.mp4"])
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

    if 0 <= idx < len(scenes):
        short = _short(videos[idx], en_wavs[idx], scene_words[idx], out_dir, work, scenes[idx])
        if short:
            files["short"] = short.name

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
