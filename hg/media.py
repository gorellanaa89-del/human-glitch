"""Small ffmpeg/ffprobe helpers."""
import json
import subprocess
from pathlib import Path


def run(args: list, quiet: bool = True):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + [str(a) for a in args]
    result = subprocess.run(cmd, capture_output=quiet, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr}")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def silence(path: Path, seconds: float):
    run(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", path])


def concat_files(paths: list[Path], out: Path, reencode_audio: bool = False):
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in paths), encoding="utf-8")
    codec = ["-c:a", "pcm_s16le"] if reencode_audio else ["-c", "copy"]
    run(["-f", "concat", "-safe", "0", "-i", listing, *codec, out])
    listing.unlink()
