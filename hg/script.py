"""Parse episode scripts written in the simple '# Scene:' markdown format."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Scene:
    title: str
    narration: str
    keywords: str = ""
    card: str = ""
    extra: dict = field(default_factory=dict)


def parse_script(path: Path) -> list[Scene]:
    scenes: list[Scene] = []
    current = None
    paragraphs: list[str] = []

    def close():
        if current is not None:
            current.narration = "\n\n".join(p for p in paragraphs if p)
            scenes.append(current)

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.lower().startswith("# scene:"):
            close()
            current = Scene(title=line.split(":", 1)[1].strip(), narration="")
            paragraphs = [""]
        elif current is None:
            continue
        elif line.startswith(">"):
            key, _, value = line[1:].partition(":")
            key, value = key.strip().lower(), value.strip()
            if key in ("keywords", "card"):
                setattr(current, key, value)
            else:
                current.extra[key] = value
        elif not line:
            paragraphs.append("")
        else:
            paragraphs[-1] = f"{paragraphs[-1]} {line}".strip()
    close()
    if not scenes:
        raise ValueError(f"No '# Scene:' blocks found in {path}")
    return scenes
