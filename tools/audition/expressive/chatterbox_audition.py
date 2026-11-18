"""Read the audition text with Chatterbox Multilingual (open source, runs on CPU) at several expressiveness levels.

Usage: python chatterbox_audition.py TEXT_FILE OUT_DIR [PROMPT_WAV]
Each line of settings.txt is: name|exaggeration|cfg_weight|temperature|prompt(yes/no)
The optional prompt is a synthetic narrator clip (never a real person's voice) that sets the timbre.
"""
import re, sys, time
from pathlib import Path
import torch, torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

text = Path(sys.argv[1]).read_text(encoding="utf-8")
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
prompt = sys.argv[3] if len(sys.argv) > 3 else None
# Chatterbox drifts on long inputs, so read sentence groups of about 200 characters.
sents = re.split(r"(?<=[.?!:])\s+", text.replace("\n", " ").strip())
chunks, cur = [], ""
for s in sents:
    if len(cur) + len(s) > 200 and cur:
        chunks.append(cur); cur = s
    else:
        cur = (cur + " " + s).strip()
chunks.append(cur)

model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
settings = [l.split("|") for l in Path(__file__).with_name("settings.txt").read_text().split("\n") if l and not l.startswith("#")]
for name, ex, cfg, temp, use_prompt in settings:
    t0 = time.time(); torch.manual_seed(7)
    parts = []
    for c in chunks:
        kw = dict(language_id="es", exaggeration=float(ex), cfg_weight=float(cfg), temperature=float(temp))
        if use_prompt == "yes" and prompt:
            kw["audio_prompt_path"] = prompt
        w = model.generate(c, **kw)
        parts += [w, torch.zeros(1, int(model.sr * 0.12))]
    torchaudio.save(str(out / f"{name}.wav"), torch.cat(parts, dim=1), model.sr)
    print(f"{name}: {time.time() - t0:.0f}s")
