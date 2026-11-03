"""Text to speech with word timings.

engine="edge" uses Microsoft Edge's free online voices (no key needed).
engine="silent" writes silence with estimated timings, for testing the pipeline offline.
"""
import asyncio
from pathlib import Path

from . import media
from .config import SCENE_GAP

Word = tuple[float, float, str]  # start, end, text


async def _edge(text: str, voice: str, mp3: Path, rate: str = "+0%") -> list[Word]:
    import edge_tts

    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words: list[Word] = []
    with open(mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append((start, start + chunk["duration"] / 1e7, chunk["text"]))
    return words


def _estimate(text: str, wps: float = 2.6) -> list[Word]:
    words, t = [], 0.0
    for w in text.split():
        d = max(0.18, len(w) / (wps * 5))
        words.append((t, t + d, w))
        t += d + (0.35 if w[-1] in ".?!" else 0.05)
    return words


def synthesize(text: str, voice: str, wav: Path, engine: str = "edge", rate: str = "+0%") -> list[Word]:
    """Write a 48 kHz mono WAV with SCENE_GAP of trailing silence and return word timings."""
    if engine == "edge":
        mp3 = wav.with_suffix(".mp3")
        words = asyncio.run(_edge(text.replace("\n\n", " "), voice, mp3, rate))
        media.run(["-i", mp3, "-af", f"apad=pad_dur={SCENE_GAP}", "-ar", "48000", "-ac", "1", wav])
        mp3.unlink()
    elif engine == "silent":
        words = _estimate(text)
        media.silence(wav, words[-1][1] + SCENE_GAP)
    else:
        raise ValueError(f"Unknown TTS engine: {engine}")
    return words
