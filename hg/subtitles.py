"""Burned-in karaoke subtitles (ASS) and caption files (SRT) from word timings."""
from pathlib import Path

from .config import SUB_FONT

Word = tuple[float, float, str]


def group(words: list[Word], max_words: int, max_seconds: float) -> list[list[Word]]:
    lines, cur = [], []
    for w in words:
        cur.append(w)
        ends_sentence = w[2][-1:] in ".?!:;,"
        if len(cur) >= max_words or (cur[-1][1] - cur[0][0]) >= max_seconds or (ends_sentence and len(cur) >= 3):
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return lines


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_ass(words: list[Word], out: Path, w: int, h: int, vertical: bool = False, top: bool = False) -> Path:
    size = int(h * (0.044 if vertical else 0.06))
    margin_v = int(h * (0.12 if top else 0.27 if vertical else 0.08))
    align = 8 if top else 2
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # Spoken words turn brand light blue #5AB7E6 (BGR &H00E6B75A); upcoming words are white; navy outline.
        f"Style: Default,{SUB_FONT},{size},&H00E6B75A,&H00F8F4F0,&H002C1C05,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(3, size // 14)},0,{align},80,80,{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    lines = group(words, 4 if vertical else 6, 2.6)
    for li, line in enumerate(lines):
        parts = []
        for i, (s, e, txt) in enumerate(line):
            nxt = line[i + 1][0] if i + 1 < len(line) else e
            parts.append(f"{{\\k{max(1, int(round((nxt - s) * 100)))}}}{txt}")
        start, end = line[0][0], line[-1][1] + 0.15
        if li + 1 < len(lines):
            # Never overlap the next line, or libass stacks both on screen.
            end = min(end, lines[li + 1][0][0])
        events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{' '.join(parts)}")
    out.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out


def write_srt(words: list[Word], out: Path) -> Path:
    blocks, prev_end = [], 0.0
    for i, line in enumerate(group(words, 9, 3.5), 1):
        text = " ".join(w[2] for w in line)
        start = max(line[0][0], prev_end)
        prev_end = max(start + 0.3, line[-1][1] + 0.2)
        blocks.append(f"{i}\n{_srt_time(start)} --> {_srt_time(prev_end)}\n{text}\n")
    out.write_text("\n".join(blocks), encoding="utf-8")
    return out
