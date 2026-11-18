"""Text to speech with word timings.

engine="edge" uses Microsoft Edge's free online voices (no key needed).
A voice named "gemini:<Voice>" (e.g. gemini:Callirrhoe) uses Google's Gemini TTS instead (secret GEMINI_API_KEY),
which takes a style direction in words; its word timings come from aligning a Whisper transcript to the script.
engine="silent" writes silence with estimated timings, for testing the pipeline offline.
"""
import asyncio
import re
import time
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


GEMINI_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
DEFAULT_STYLE = ("Lee en español latino neutro como una narradora joven de datos curiosos en TikTok: "
                 "rápida, con mucha energía y curiosidad, sonriendo, subiendo y bajando mucho el tono, "
                 "pausas muy cortas, remarcando las palabras clave y con un toque de ironía")


def _gemini(text: str, voice: str, wav24: Path, style: str) -> None:
    import base64, json, os, urllib.error, urllib.request, wave
    key = os.environ["GEMINI_API_KEY"]
    body = {"contents": [{"parts": [{"text": f"{style}:\n\n{text}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    last = None
    for attempt in range(8):  # free tier: a few requests per minute, so wait and retry on 429/5xx
        model = GEMINI_MODELS[0] if attempt < 6 else GEMINI_MODELS[1]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        try:
            req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
            data = json.load(urllib.request.urlopen(req, timeout=300))
            pcm = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            with wave.open(str(wav24), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            return
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, TimeoutError) as e:
            last = e
            print(f"  gemini voice failed ({getattr(e, 'code', e.__class__.__name__)}), retrying...")
            time.sleep(min(90, 15 * (attempt + 1)))
    raise RuntimeError(f"Gemini TTS failed: {last}")


def _norm(w: str) -> str:
    import unicodedata
    w = unicodedata.normalize("NFD", w.lower())
    return "".join(c for c in w if c.isalnum())


def _align(text: str, audio: Path, lang: str) -> list[Word]:
    """Word timings for `text` as spoken in `audio`: Whisper words matched to the script words."""
    import difflib
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    import subprocess, numpy as np
    # decode with ffmpeg ourselves (faster-whisper's PyAV decoder breaks with some av versions)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    samples = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    segs, _ = model.transcribe(samples, language=lang, word_timestamps=True, vad_filter=False)
    heard = [(w.start, w.end, w.word.strip()) for s in segs for w in s.words]
    script = text.split()
    sm = difflib.SequenceMatcher(a=[_norm(w) for w in script], b=[_norm(h[2]) for h in heard], autojunk=False)
    times: list = [None] * len(script)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            times[a + k] = heard[b + k][:2]
    end = heard[-1][1] if heard else 1.0
    # words Whisper heard differently: spread them evenly between the matched neighbours
    k = 0
    while k < len(script):
        if times[k] is None:
            j = k
            while j < len(script) and times[j] is None:
                j += 1
            t0 = times[k - 1][1] if k > 0 else 0.0
            t1 = times[j][0] if j < len(script) else end
            step = max(0.05, (t1 - t0) / (j - k))
            for m in range(k, j):
                times[m] = (t0 + step * (m - k), t0 + step * (m - k + 1))
            k = j
        else:
            k += 1
    return [(s, e, w) for (s, e), w in zip(times, script)]


def _one(text: str, voice: str, wav: Path, engine: str, rate: str, style: str):
    """One stretch of speech, no trailing gap: returns edge word timings, or None for Gemini (aligned later)."""
    if voice.startswith("gemini:"):
        raw = wav.with_suffix(".g24.wav")
        _gemini(text, voice.split(":", 1)[1], raw, style or DEFAULT_STYLE)
        # trim the model's leading/trailing silence, apply the rate (e.g. "+10%") as a tempo change
        pct = float(rate.rstrip("%") or 0)
        tempo = f",atempo={1 + pct / 100:.3f}" if pct else ""
        media.run(["-i", raw, "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                   "silenceremove=start_periods=1:start_threshold=-45dB,areverse" + tempo,
                   "-ar", "48000", "-ac", "1", wav])
        raw.unlink()
        return None
    mp3 = wav.with_suffix(".mp3")
    words = None
    for attempt in range(4):  # the free voice service sometimes drops a request
        try:
            words = asyncio.run(_edge(text, voice, mp3, rate))
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            print(f"  voice request failed ({e.__class__.__name__}), retrying...")
            time.sleep(5 * (attempt + 1))
    media.run(["-i", mp3, "-ar", "48000", "-ac", "1", wav])
    mp3.unlink()
    return words


QUOTE = re.compile(r'["“][^"”]+["”][.,;:!?]*')


def segments(text: str, speakers: dict | None) -> list[tuple[str, str | None]]:
    """Split narration into (text, speaker) stretches: quotes in paragraph P go to speakers[P] in order
    (the last name repeats); everything else, and quotes with no speaker, is the narrator (None)."""
    out: list = []
    for p, para in enumerate(text.split("\n\n")):
        names = (speakers or {}).get(p) or []
        pos, q = 0, 0
        for m in QUOTE.finditer(para):
            if not names:
                break
            out.append((para[pos:m.start()], None))
            out.append((m.group(0), names[min(q, len(names) - 1)]))
            pos, q = m.end(), q + 1
        out.append((para[pos:], None))
    merged: list = []
    for t, who in out:
        t = t.strip()
        if not t:
            continue
        if merged and merged[-1][1] == who:
            merged[-1] = (merged[-1][0] + " " + t, who)
        else:
            merged.append((t, who))
    return merged


def synthesize(text: str, voice: str, wav: Path, engine: str = "edge", rate: str = "+0%", style: str = "",
               speakers: dict | None = None, cast: dict | None = None) -> list[Word]:
    """Write a 48 kHz mono WAV with SCENE_GAP of trailing silence and return word timings.
    speakers ({paragraph: [name, ...]}, from `> say@P:` lines) and cast ({name: (voice, style)}) give the
    characters' quoted lines their own voices."""
    if engine == "silent":
        words = _estimate(text)
        media.silence(wav, words[-1][1] + SCENE_GAP)
        return words
    flat = text.replace("\n\n", " ")
    segs = segments(text, speakers) if speakers and cast else [(flat, None)]
    parts, words, t, needs_align = [], [], 0.0, False
    for k, (seg, who) in enumerate(segs):
        v, st = (cast or {}).get(who, (voice, style)) if who else (voice, style)
        part = wav.with_name(f"{wav.stem}_p{k}.wav")
        w = _one(seg, v, part, engine, rate, st)
        if w is None:
            needs_align = True
        else:
            words += [(a + t, b + t, x) for a, b, x in w]
        parts.append(part)
        t += media.duration(part) + 0.15
    gap = 0.15
    inputs = []
    for part in parts:
        inputs += ["-i", part]
    n = len(parts)
    chain = "".join(f"[{i}:a]apad=pad_dur={gap}[p{i}];" for i in range(n - 1))
    labels = "".join(f"[p{i}]" for i in range(n - 1)) + f"[{n - 1}:a]"
    media.run([*inputs, "-filter_complex", f"{chain}{labels}concat=n={n}:v=0:a=1,apad=pad_dur={SCENE_GAP}[o]",
               "-map", "[o]", "-ar", "48000", "-ac", "1", wav])
    for part in parts:
        part.unlink()
    if needs_align:
        lang = "es" if any(c in text for c in "ñáéíóú¿¡") else "en"
        return _align(flat, wav, lang)
    return words
