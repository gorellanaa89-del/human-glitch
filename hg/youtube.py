"""Upload a rendered episode with the YouTube Data API v3.

Needs YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN (see tools/README.md).
Projects that have not passed Google's API audit can only upload private videos,
so everything goes up as private; publish_at schedules it when the account allows.
"""
import json
import os
import time
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


def set_visibility(video_id: str, privacy: str = "public", publish_at: str | None = None) -> dict:
    """Make an uploaded video public now, or schedule it (privacy stays private until publish_at, UTC ISO).
    Returns the video's status as YouTube reports it afterwards."""
    yt = _service()
    cur = yt.videos().list(part="status", id=video_id).execute()["items"][0]["status"]
    print("before:", json.dumps(cur))
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": cur.get("selfDeclaredMadeForKids", False),
              "embeddable": cur.get("embeddable", True), "license": cur.get("license", "youtube"),
              "publicStatsViewable": cur.get("publicStatsViewable", True)}
    if publish_at:
        status.update(privacyStatus="private", publishAt=publish_at)
    elif privacy == "private":
        status["publishAt"] = None  # cancel any scheduled publication
    if privacy == "check":
        return cur
    res = yt.videos().update(part="status", body={"id": video_id, "status": status}).execute()["status"]
    print("after:", json.dumps(res))
    return res


def upload_es(episode: Path) -> dict:
    """Upload the Spanish version as its own private video: the same picture with the Spanish voice track
    (audio.es.m4a), Spanish title/description from meta.yaml `es:`, Spanish chapters, captions and a
    Spanish thumbnail. Used while the channel cannot add a second audio track to the English video."""
    import re
    import subprocess

    from googleapiclient.http import MediaFileUpload

    from . import animate
    from .script import parse_script

    meta = yaml.safe_load((episode / "meta.yaml").read_text(encoding="utf-8"))
    es = meta.get("es") or {}
    out = episode / "output"
    log_path = episode / "uploaded.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    if log.get("es_video_id"):
        print(f"Spanish video already uploaded: {log['es_video_id']}")
        return log

    video = out / "video.es.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(out / "video.mp4"), "-i", str(out / "audio.es.m4a"),
                    "-map", "0:v", "-map", "1:a", "-c", "copy", "-shortest", "-movflags", "+faststart", str(video)],
                   check=True)

    # Spanish chapters: the English timestamps with the Spanish scene titles.
    stamps = re.findall(r"^(\d\d:\d\d) ", (out / "description.txt").read_text(encoding="utf-8"), re.M)
    titles = [s.title for s in parse_script(episode / "script.es.md")]
    chapters = "\n".join(f"{t} {n}" for t, n in zip(stamps, titles))
    description = es.get("description", "").replace("{chapters}", chapters)

    thumb = out / "thumbnail.es.jpg"
    try:
        idx = int(meta.get("short_scene") or 1) - 1
        from . import sets
        sets.MODE = meta.get("backgrounds", "drawn")
        animate.thumbnail(parse_script(episode / "script.en.md")[idx], es.get("thumbnail_text") or es["title"], thumb)
    except Exception as e:
        print(f"  Spanish thumbnail not drawn: {e}")

    yt = _service()
    snippet = {
        "title": es["title"][:100],
        "description": description[:5000],
        "tags": es.get("tags") or meta.get("tags", []),
        "categoryId": "27",
        "defaultLanguage": "es",
        "defaultAudioLanguage": "es",
    }
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": bool(meta.get("synthetic_media"))}
    print("Uploading Spanish video...")
    log["es_video_id"] = _insert(yt, video, snippet, status)
    log_path.write_text(json.dumps(log, indent=2))
    vid = log["es_video_id"]
    if thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
        except Exception as e:
            print(f"  thumbnail not set (verify the channel at youtube.com/verify): {e}")
    if (out / "captions.es.srt").exists():
        try:
            _caption(yt, vid, out / "captions.es.srt", "es", "Español")
        except Exception as e:
            print(f"  es captions not uploaded: {e}")
    try:
        sync_playlists(episode.parent)
    except Exception as e:
        print(f"  playlists not updated: {e}")
    return log


PLAYLISTS = {
    "en": ("English episodes", "Every Inside Voice Psychology story in English."),
    "es": ("Episodios en español", "Todas las historias de Inside Voice Psychology en español."),
}


def sync_playlists(episodes_dir: Path | None = None) -> dict:
    """Make sure the channel has one public playlist per language and that every uploaded long video
    (uploaded.json: video_id = English, es_video_id = Spanish) is in the right one. Safe to run again."""
    episodes_dir = episodes_dir or Path(__file__).resolve().parent.parent / "episodes"
    yt = _service()
    existing = {}
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req:
        res = req.execute()
        existing.update({p["snippet"]["title"]: p["id"] for p in res.get("items", [])})
        req = yt.playlists().list_next(req, res)
    ids = {}
    for lang, (title, desc) in PLAYLISTS.items():
        if title not in existing:
            body = {"snippet": {"title": title, "description": desc, "defaultLanguage": lang},
                    "status": {"privacyStatus": "public"}}
            existing[title] = yt.playlists().insert(part="snippet,status", body=body).execute()["id"]
            print(f"created playlist {title}: {existing[title]}")
        ids[lang] = existing[title]
    report = {}
    for log_path in sorted(episodes_dir.glob("*/uploaded.json")):
        log = json.loads(log_path.read_text())
        for lang, key in (("en", "video_id"), ("es", "es_video_id")):
            vid = log.get(key)
            if not vid:
                continue
            try:
                found = yt.playlistItems().list(part="snippet", playlistId=ids[lang], videoId=vid).execute().get("items")
            except Exception:  # a playlist created seconds ago can still answer "not found"
                found = []
            if not found:
                for attempt in range(6):
                    try:
                        yt.playlistItems().insert(part="snippet", body={"snippet": {
                            "playlistId": ids[lang], "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
                        break
                    except Exception:
                        if attempt == 5:
                            raise
                        time.sleep(10)
                print(f"added {vid} to {PLAYLISTS[lang][0]}")
            report.setdefault(PLAYLISTS[lang][0], []).append(vid)
    report["playlist_ids"] = ids
    return report
