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
    b.add_argument("--max-seconds", type=float, default=None, help="render only the opening, for quick tests")
    b.add_argument("--scene", type=int, default=None, help="render only this scene (1-based) into output/work")
    sh = sub.add_parser("shorts", help="render only the scenes that have Shorts and cut the vertical Shorts")
    sh.add_argument("episode", type=Path)
    sh.add_argument("--tts", default="edge", choices=["edge", "silent"])
    sc = sub.add_parser("scenes", help="print the scene numbers of an episode as JSON (for parallel jobs)")
    sc.add_argument("episode", type=Path)
    u = sub.add_parser("upload", help="upload a rendered episode")
    u.add_argument("episode", type=Path)
    u.add_argument("--no-shorts", action="store_true", help="upload only the long video (Shorts kept for TikTok)")
    u.add_argument("--spanish", action="store_true", help="upload the Spanish version as its own video")
    v = sub.add_parser("visibility", help="check, publish or schedule an uploaded video")
    v.add_argument("video_id")
    v.add_argument("--privacy", default="check", choices=["check", "public", "unlisted", "private"])
    v.add_argument("--at", default=None, help="schedule: UTC time like 2026-11-04T00:00:00Z")
    sub.add_parser("playlists", help="create the English/Spanish playlists and file every uploaded video")
    r = sub.add_parser("run-approved", help="render and upload every approved episode not yet uploaded")
    r.add_argument("--tts", default="edge", choices=["edge", "silent"])
    args = p.parse_args(argv)

    if args.cmd == "build":
        print(json.dumps(render.build(args.episode, args.tts, args.max_seconds, None if args.scene is None else args.scene - 1), indent=2, ensure_ascii=False))
    elif args.cmd == "shorts":
        print(json.dumps(render.build_shorts(args.episode, args.tts), indent=2))
    elif args.cmd == "visibility":
        print(json.dumps(youtube.set_visibility(args.video_id, args.privacy, args.at), indent=2))
    elif args.cmd == "playlists":
        print(json.dumps(youtube.sync_playlists(), indent=2))
    elif args.cmd == "scenes":
        from .script import parse_script
        print(json.dumps(list(range(1, len(parse_script(args.episode / "script.en.md")) + 1))))
    elif args.cmd == "upload":
        if args.spanish:
            print(json.dumps(youtube.upload_es(args.episode), indent=2))
        else:
            print(json.dumps(youtube.upload(args.episode, shorts=not args.no_shorts), indent=2))
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
