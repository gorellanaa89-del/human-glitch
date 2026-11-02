"""Brand and render settings for Human Glitch."""
from pathlib import Path

W, H = 1920, 1080
FPS = 30
SHORT_W, SHORT_H = 1080, 1920

BG = (11, 15, 20)
GREEN = (57, 255, 136)
MAGENTA = (255, 46, 136)
CYAN = (0, 229, 255)
WHITE = (240, 244, 248)

CHANNEL = "HUMAN GLITCH"

VOICES = {
    "en": "en-US-AndrewNeural",
    "es": "es-MX-JorgeNeural",
}

# Seconds of silence after each scene's narration.
SCENE_GAP = 0.6
# Length of the title card that opens each scene.
CARD_SECONDS = 3.0
# Length of each stock clip used as b-roll.
BROLL_SECONDS = 7.0
# Fastest speed-up allowed when fitting the Spanish track to the English timing.
MAX_ES_TEMPO = 1.25

_MONO = [
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-ExtraBold.ttf",
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]
_SANS = [
    "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _first(paths):
    for p in paths:
        if Path(p).exists():
            return p
    raise FileNotFoundError(f"None of these fonts exist: {paths}")


def font_mono():
    return _first(_MONO)


def font_sans():
    return _first(_SANS)


# Font family name used by the burned-in subtitles (libass looks it up by name).
SUB_FONT = "Inter"
