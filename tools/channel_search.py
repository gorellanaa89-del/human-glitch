"""List YouTube channels matching a name, with subscribers, videos and last upload (uses the channel's OAuth)."""
import json
import sys

from hg.youtube import _service

def norm(t):
    return "".join(ch for ch in t.lower() if ch.isalnum())


def run(q, yt):
    ids = [i["id"]["channelId"] for i in yt.search().list(part="snippet", q=q, type="channel", maxResults=25).execute()["items"]]
    if not ids:
        print("NAME", json.dumps({"q": q, "exact": 0, "biggest_exact": 0, "matches": []}))
        return
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
    exact = [r for r in rows if norm(q) in norm(r["title"]) or norm(q) in norm(r["handle"])]
    print("NAME", json.dumps({"q": q, "exact": len(exact), "biggest_exact": max((r["subs"] for r in exact), default=0),
                              "matches": sorted(exact, key=lambda r: -r["subs"])[:3]}, ensure_ascii=False))
    for r in sorted(rows, key=lambda r: -r["subs"])[:5]:
        print("ROW", json.dumps(r, ensure_ascii=False))


yt = _service()
for q in (sys.argv[1] if len(sys.argv) > 1 else "Human Glitch").split(";"):
    if q.strip():
        run(q.strip(), yt)
