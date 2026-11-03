"""Upload a rendered episode with the YouTube Data API v3.

Needs YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN (see tools/README.md).
Projects that have not passed Google's API audit can only upload private videos,
so everything goes up as private; publish_at schedules it when the account allows.
"""
import json
import os
from pathlib import Path

import yaml

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]


def configured() -> bool:
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _insert(yt, path: Path, snippet: dict, status: dict) -> str:
    from googleapiclient.http import MediaFileUpload

    req = yt.videos().insert(
        part="snippet,status",
        body={"snippet": snippet, "status": status},
        media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True),
    )
    resp = None
    while resp is None:
        progress, resp = req.next_chunk()
        if progress:
            print(f"  uploaded {int(progress.progress() * 100)}%")
    return resp["id"]


def _caption(yt, video_id: str, srt: Path, lang: str, name: str):
    from googleapiclient.http import MediaFileUpload

    yt.captions().insert(
        part="snippet",
        body={"snippet": {"videoId": video_id, "language": lang, "name": name, "isDraft": False}},
        media_body=MediaFileUpload(str(srt), mimetype="application/octet-stream"),
    ).execute()


def upload(episode: Path, shorts: bool = True) -> dict:
    """Upload the long video (private) with captions and thumbnail; Shorts too unless shorts=False
    (for example when they are kept for TikTok)."""
    meta = yaml.safe_load((episode / "meta.yaml").read_text(encoding="utf-8"))
    out = episode / "output"
    log_path = episode / "uploaded.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    yt = _service()

    status = {
        "privacyStatus": "private",
        "selfDeclaredMadeForKids": False,
        "containsSyntheticMedia": bool(meta.get("synthetic_media")),
    }
    if meta.get("publish_at"):
        status["publishAt"] = meta["publish_at"]

    if "video_id" not in log:
        snippet = {
            "title": meta["title"][:100],
            "description": (out / "description.txt").read_text(encoding="utf-8")[:5000],
            "tags": meta.get("tags", []),
            "categoryId": "27",  # Education
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        }
        print("Uploading long video...")
        log["video_id"] = _insert(yt, out / "video.mp4", snippet, status)
        log_path.write_text(json.dumps(log, indent=2))
        vid = log["video_id"]
        try:
            from googleapiclient.http import MediaFileUpload

            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(out / "thumbnail.jpg"))).execute()
        except Exception as e:  # custom thumbnails need a phone-verified channel
            print(f"  thumbnail not set (verify the channel at youtube.com/verify): {e}")
        for lang, name, f in (("en", "English", "captions.en.srt"), ("es", "Español", "captions.es.srt")):
            if (out / f).exists():
                try:
                    _caption(yt, vid, out / f, lang, name)
                except Exception as e:
                    print(f"  {lang} captions not uploaded: {e}")

    shorts_wanted = shorts
    report = json.loads((out / "report.json").read_text()) if (out / "report.json").exists() else {}
    shorts = report.get("files", {}).get("shorts") or (
        [{"file": "short.mp4", "lang": "en", "title": meta["title"].split("(")[0].strip()}] if (out / "short.mp4").exists() else [])
    done = log.setdefault("shorts", {})
    for sh in shorts if shorts_wanted else []:
        if sh["file"] in done or not (out / sh["file"]).exists():
            continue
        es = sh["lang"] == "es"
        snippet = {
            "title": f"{sh['title']} #Shorts"[:100],
            "description": ("Historia completa en el canal. #psicologia #shorts" if es
                            else "Full story on the channel. #psychology #shorts"),
            "tags": meta.get("tags", []),
            "categoryId": "27",
            "defaultLanguage": sh["lang"],
            "defaultAudioLanguage": sh["lang"],
        }
        print(f"Uploading Short {sh['file']}...")
        done[sh["file"]] = _insert(yt, out / sh["file"], snippet, dict(status))
        log_path.write_text(json.dumps(log, indent=2))
    return log
