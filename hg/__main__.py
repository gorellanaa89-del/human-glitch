"""Command line: python -m hg build|upload|run-approved"""
import argparse
import json
import sys
from pathlib import Path

import yaml

from . import render, youtube

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"


def _approved_pending() -> list[Path]:
    eps = []
    for meta in sorted(EPISODES.glob("*/meta.yaml")):
        data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
        if data.get("approved") and not (meta.parent / "uploaded.json").exists():
            eps.append(meta.parent)
    return eps


def main(argv=None):
    p = argparse.ArgumentParser(prog="hg")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="render one episode folder")
    b.add_argument("episode", type=Path)
    b.add_argument("--tts", default="edge", choices=["edge", "silent"])
    u = sub.add_parser("upload", help="upload a rendered episode")
    u.add_argument("episode", type=Path)
    r = sub.add_parser("run-approved", help="render and upload every approved episode not yet uploaded")
    r.add_argument("--tts", default="edge", choices=["edge", "silent"])
    args = p.parse_args(argv)

    if args.cmd == "build":
        print(json.dumps(render.build(args.episode, args.tts), indent=2, ensure_ascii=False))
    elif args.cmd == "upload":
        print(json.dumps(youtube.upload(args.episode), indent=2))
    else:
        eps = _approved_pending()
        if not eps:
            print("No approved episodes waiting. Set approved: true in an episode's meta.yaml.")
            return 0
        for ep in eps:
            print(f"== {ep.name} ==")
            print(json.dumps(render.build(ep, args.tts), indent=2, ensure_ascii=False))
            if youtube.configured():
                print(json.dumps(youtube.upload(ep), indent=2))
            else:
                print("YouTube secrets not set: download the files from the workflow run and upload them by hand.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
