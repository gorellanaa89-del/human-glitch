"""Read the same text with several edge-tts voices, rates and pitches, so a narrator can be picked by ear.

Usage: python tools/audition/voice_audition.py TEXT_FILE OUT_DIR "voice|rate|pitch" ...
Writes OUT_DIR/<n>-<voice>-<rate>-<pitch>.mp3 and OUT_DIR/voices.txt (every Spanish and multilingual voice).
"""
import asyncio, sys
from pathlib import Path
import edge_tts


async def one(text, voice, rate, pitch, out):
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))
            return
        except Exception as e:  # the free service sometimes drops a request
            print(f"{voice}: {e.__class__.__name__}, retrying")
            await asyncio.sleep(3 * (attempt + 1))
    print(f"{voice}: FAILED")


async def main():
    text = Path(sys.argv[1]).read_text(encoding="utf-8").replace("\n\n", " ")
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    vs = await edge_tts.list_voices()
    (out / "voices.txt").write_text("\n".join(
        f"{v['ShortName']}\t{v['Gender']}\t{','.join(v.get('VoiceTag', {}).get('VoicePersonalities', []))}"
        for v in vs if v["Locale"].startswith("es-") or "Multilingual" in v["ShortName"]))
    for n, spec in enumerate(sys.argv[3:], 1):
        voice, rate, pitch = (spec.split("|") + ["+0%", "+0Hz"])[:3]
        name = f"{n:02d}-{voice}-{rate}-{pitch}".replace("%", "pct").replace("+", "p").replace("-", "_")
        await one(text, voice, rate, pitch, out / f"{name}.mp3")


asyncio.run(main())
