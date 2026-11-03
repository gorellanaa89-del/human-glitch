"""List YouTube channels matching a name, with subscribers, videos and last upload (uses the channel's OAuth)."""
import json
import sys

from hg.youtube import _service

q = sys.argv[1] if len(sys.argv) > 1 else "Human Glitch"
yt = _service()
ids = [i["id"]["channelId"] for i in yt.search().list(part="snippet", q=q, type="channel", maxResults=25).execute()["items"]]
chans = yt.channels().list(part="snippet,statistics,contentDetails", id=",".join(ids)).execute()["items"]
rows = []
for c in chans:
    st = c["statistics"]
    up = c["contentDetails"]["relatedPlaylists"]["uploads"]
    last = ""
    try:
        it = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=1).execute()["items"]
        last = it[0]["contentDetails"].get("videoPublishedAt", "") if it else ""
    except Exception:
        pass
    rows.append({"title": c["snippet"]["title"], "handle": c["snippet"].get("customUrl", ""),
                 "subs": int(st.get("subscriberCount", 0)), "videos": int(st.get("videoCount", 0)),
                 "created": c["snippet"]["publishedAt"][:10], "last_upload": last[:10],
                 "about": c["snippet"]["description"][:120].replace("\n", " ")})
for r in sorted(rows, key=lambda r: -r["subs"]):
    print("ROW", json.dumps(r, ensure_ascii=False))
