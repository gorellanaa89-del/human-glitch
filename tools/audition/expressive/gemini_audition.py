"""Read the audition text with Gemini TTS (free tier, needs GEMINI_API_KEY) with a style direction.

Usage: python gemini_audition.py TEXT_FILE OUT_DIR
"""
import base64, json, os, sys, time, urllib.request, wave
from pathlib import Path

key = os.environ.get("GEMINI_API_KEY")
if not key:
    print("no GEMINI_API_KEY, skipping"); sys.exit(0)
text = Path(sys.argv[1]).read_text(encoding="utf-8").replace("\n\n", " ")
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
STYLE = ("Lee en español latino neutro como una narradora joven de datos curiosos en TikTok: "
         "rápida, con mucha energía y curiosidad, sonriendo, subiendo y bajando mucho el tono, "
         "pausas muy cortas, remarcando las palabras clave y con un toque de ironía: ")
for voice in ["Kore", "Aoede", "Leda", "Zephyr", "Callirrhoe", "Despina"]:
    body = {"contents": [{"parts": [{"text": STYLE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    for model in ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        try:
            req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
            data = json.load(urllib.request.urlopen(req, timeout=180))
            pcm = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            with wave.open(str(out / f"gm-{voice.lower()}.wav"), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            print(voice, model, "ok"); break
        except Exception as e:
            print(voice, model, "failed:", str(e)[:200])
    time.sleep(8)  # free tier rate limit
