"""Compare YouTube niches with real data: for each niche, the most-viewed videos of the last 6 months
for a few searches, and the channels behind them (size and age). Prints one JSON line per niche."""
import datetime as dt
import json
import statistics
import sys

from hg.youtube import _service

NICHES = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
now = dt.datetime.now(dt.timezone.utc)
since = (now - dt.timedelta(days=182)).strftime("%Y-%m-%dT%H:%M:%SZ")
yt = _service()

for niche, queries in NICHES.items():
    vids = {}
    for q in queries:
        res = yt.search().list(part="snippet", q=q, type="video", order="viewCount", publishedAfter=since,
                               relevanceLanguage="en", videoDuration="medium", maxResults=50).execute()
        for it in res["items"]:
            vids[it["id"]["videoId"]] = it["snippet"]["channelId"]
    ids = list(vids)
    stats = {}
    for k in range(0, len(ids), 50):
        for v in yt.videos().list(part="statistics,snippet", id=",".join(ids[k:k + 50])).execute()["items"]:
            stats[v["id"]] = (int(v["statistics"].get("viewCount", 0)), v["snippet"]["title"], v["snippet"]["channelTitle"])
    chans = list(set(vids.values()))
    cinfo = {}
    for k in range(0, len(chans), 50):
        for c in yt.channels().list(part="statistics,snippet", id=",".join(chans[k:k + 50])).execute()["items"]:
            cinfo[c["id"]] = (int(c["statistics"].get("subscriberCount", 0)), c["snippet"]["publishedAt"][:10])
    views = sorted((stats[v][0] for v in stats), reverse=True)
    young_cut = (now - dt.timedelta(days=548)).strftime("%Y-%m-%d")
    young_hits = {vids[v] for v in stats if stats[v][0] >= 100_000 and cinfo.get(vids[v], (0, "1900"))[1] >= young_cut}
    small_hits = {vids[v] for v in stats if stats[v][0] >= 100_000 and cinfo.get(vids[v], (10**9, ""))[0] < 50_000}
    top = sorted(stats.items(), key=lambda kv: -kv[1][0])[:3]
    print("NICHE", json.dumps({
        "niche": niche, "videos": len(views), "channels": len(chans),
        "median_views": int(statistics.median(views)) if views else 0,
        "p25_views": views[len(views) * 3 // 4] if views else 0,
        "videos_over_100k": sum(1 for x in views if x >= 100_000),
        "new_channels_with_100k_video": len(young_hits),
        "small_channels_with_100k_video": len(small_hits),
        "top": [{"views": s[0], "title": s[1][:70], "channel": s[2]} for _, s in top],
    }, ensure_ascii=False))
