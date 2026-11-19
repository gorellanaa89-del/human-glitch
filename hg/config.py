"""Brand and render settings for Human Glitch."""
from pathlib import Path

W, H = 1920, 1080
FPS = 30
SHORT_W, SHORT_H = 1080, 1920

# Brand palette, matched to Potencia People (potenciapeople.com), sampled from the site on 2026-11-03.
BRAND_BLUE = (58, 99, 216)     # #3A63D8 primary (buttons, numbers)
BRAND_MID = (75, 116, 232)     # #4B74E8 gradient start
BRAND_LIGHT = (90, 183, 230)   # #5AB7E6 light blue, gradient end
BRAND_NAVY = (5, 28, 44)       # #051C2C headings / dark background
BRAND_GRAY = (77, 87, 97)      # #4D5761 body text
BRAND_PAPER = (240, 240, 240)  # #F0F0F0 light background

BG = BRAND_NAVY
GREEN = BRAND_LIGHT  # legacy name: the main accent used across cards and thumbnails
MAGENTA = (255, 46, 136)  # only for the glitch colour split
CYAN = BRAND_MID
WHITE = (240, 244, 248)

CHANNEL = "INSIDE VOICE PSYCHOLOGY"

# Speaking rate per language (edge-tts format). Normal speed keeps the stories moving
# (the earlier -10% felt slow); Spanish a little faster, as it needs more words for the same content.
VOICE_RATE = {"en": "+0%", "es": "+5%"}

VOICES = {
    "en": "en-US-AndrewNeural",
    "es": "es-MX-JorgeNeural",
}

# Seconds of silence after each scene's narration.
SCENE_GAP = 0.35
# Length of the title card that opens each scene.
CARD_SECONDS = 3.0
# Length of each stock clip used as b-roll.
BROLL_SECONDS = 7.0
# Fastest speed-up allowed when fitting the Spanish track to the English timing.
MAX_ES_TEMPO = 1.25

# Brand fonts ship with the repository (assets/fonts, SIL Open Font License), so runners need no font packages.
_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_MONO = [
    str(_FONTS / "JetBrainsMono-ExtraBold.ttf"),
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-ExtraBold.ttf",
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]
_SANS = [
    str(_FONTS / "Inter-Black.otf"),
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

# Voices for the characters' quoted lines (Giancarlo 2026-11-18: characters must sound different from the narrator).
# The script marks who speaks with `> say@P: name` (P = paragraph, from 0). "voice" = any of the inner voices.
# Spanish: Gemini voices with a direction in words; English: Edge voices. meta.yaml `cast:` can override.
CAST = {
    "es": {
        "richard": ("gemini:Algenib", "Di esto como un director de empresa arrogante y molesto, con voz grave, firme y cortante"),
        "daniel": ("gemini:Puck", "Di esto como un joven nervioso e inseguro que no quiere molestar a nadie"),
        "elena": ("gemini:Sulafat", "Di esto como una mentora calmada y cálida, con voz serena y pausada"),
        "sarah": ("gemini:Achernar", "Di esto como una analista ansiosa que habla rápido y duda de sí misma"),
        "margaret": ("gemini:Gacrux", "Di esto como una gerente veterana, seca y sarcástica"),
        "mom": ("gemini:Laomedeia", "Di esto como una mamá de sesenta y tantos, cariñosa pero muy terca y desconfiada"),
        "grandpa": ("gemini:Charon", "Di esto como un abuelo de ochenta años, orgulloso, de voz grave y algo gruñón"),
        "voice": ("gemini:Enceladus", "Di esto como una voz interior intensa y susurrada, muy convencida"),
    },
    "en": {
        "richard": ("en-US-ChristopherNeural", ""),
        "daniel": ("en-US-EricNeural", ""),
        "elena": ("en-US-JennyNeural", ""),
        "sarah": ("en-US-AriaNeural", ""),
        "margaret": ("en-GB-SoniaNeural", ""),
        "mom": ("en-US-MichelleNeural", ""),
        "grandpa": ("en-US-DavisNeural", ""),
        "voice": ("en-US-RogerNeural", ""),
    },
}
