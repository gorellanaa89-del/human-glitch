"""Render still frames of an episode's stock-footage scenes, without voice, video or upload.

Usage: python tools/preview_scenes.py episodes/001-impostor-syndrome [clips_per_scene]
Writes JPGs to preview/ so the look of the real footage can be checked before producing.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hg import broll, graphics, subtitles  # noqa: E402
from hg.config import H, W  # noqa: E402
from hg.script import parse_script  # noqa: E402

ep = Path(sys.argv[1])
per_scene = int(sys.argv[2]) if len(sys.argv) > 2 else 2
out_dir, work = Path("preview"), Path("preview_work")
out_dir.mkdir(exist_ok=True)
work.mkdir(exist_ok=True)
wm = graphics.watermark(work / "wm.png")
used: set = set()
vf_base = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},eq=brightness=-0.06:saturation=0.8,vignette=PI/5"

for i, scene in enumerate(parse_script(ep / "script.en.md")):
    clips = broll.fetch(scene.keywords, per_scene, work, used)
    print(f"scene {i + 1} ({scene.keywords}): {len(clips)} clips")
    words = scene.narration.split()
    for n, clip in enumerate(clips):
        line = words[n * 6:(n + 1) * 6] or words[:6]
        timed = [(k * 0.4, k * 0.4 + 0.35, w) for k, w in enumerate(line)]
        ass = subtitles.write_ass(timed, work / f"s{i}_{n}.ass", W, H)
        name = out_dir / f"escena-{i + 1}-clip-{n + 1}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2", "-i", str(clip), "-i", str(wm),
                        "-filter_complex", f"[0]{vf_base},setpts=PTS-STARTPTS[v];[v][1]overlay,subtitles={ass}",
                        "-ss", f"{len(line) * 0.2:.2f}", "-frames:v", "1", "-q:v", "3", str(name)], check=True)
