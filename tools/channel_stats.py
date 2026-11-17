"""Print the channel's numbers: subscribers, every upload's views/likes/comments, and (when the
token allows it) YouTube Analytics: watch time, average view duration, retention %, traffic sources,
countries, impressions and CTR. Read-only."""
import datetime as dt
import json
import os

from hg.youtube import _service

yt = _service()
ch = yt.channels().list(part="snippet,statistics,contentDetails,status", mine=True).execute()["items"][0]
print("CHANNEL", json.dumps({"title": ch["snippet"]["title"], "id": ch["id"], **ch["statistics"],
                             "status": ch.get("status", {})}))
uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
ids, tok = [], None
while True:
    r = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=tok).execute()
    ids += [i["contentDetails"]["videoId"] for i in r["items"]]
    tok = r.get("nextPageToken")
    if not tok:
        break
for k in range(0, len(ids), 50):
    for v in yt.videos().list(part="snippet,statistics,status,contentDetails", id=",".join(ids[k:k + 50])).execute()["items"]:
        print("VIDEO", json.dumps({"id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"],
                                   "privacy": v["status"]["privacyStatus"], "duration": v["contentDetails"]["duration"],
                                   **v["statistics"]}))

# YouTube Analytics (needs a token with yt-analytics.readonly or youtube scope; failures are printed, not fatal)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
end = dt.date.today().isoformat()
start = "2026-10-25"


def q(name, **kw):
    try:
        r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, **kw).execute()
        print("ANALYTICS", name, json.dumps({"cols": [c["name"] for c in r.get("columnHeaders", [])], "rows": r.get("rows", [])}))
    except Exception as e:  # noqa: BLE001
        print("ANALYTICS_ERR", name, str(e)[:400])


q("per_video", metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,subscribersGained",
  dimensions="video", sort="-views", maxResults=50)
q("per_day", metrics="views,estimatedMinutesWatched,subscribersGained", dimensions="day", sort="day")
q("traffic", metrics="views,estimatedMinutesWatched", dimensions="insightTrafficSourceType", sort="-views")
q("country", metrics="views,estimatedMinutesWatched", dimensions="country", sort="-views", maxResults=15)
q("impressions", metrics="videoThumbnailImpressions,videoThumbnailImpressionsClickRate,views", dimensions="video",
  sort="-views", maxResults=50)
q("traffic_detail_search", metrics="views", dimensions="insightTrafficSourceDetail",
  filters="insightTrafficSourceType==YT_SEARCH", sort="-views", maxResults=25)
q("traffic_detail_suggested", metrics="views", dimensions="insightTrafficSourceDetail",
  filters="insightTrafficSourceType==RELATED_VIDEO", sort="-views", maxResults=25)
q("traffic_detail_external", metrics="views", dimensions="insightTrafficSourceDetail",
  filters="insightTrafficSourceType==EXT_URL", sort="-views", maxResults=25)
q("demographics", metrics="viewerPercentage", dimensions="ageGroup,gender")
q("device", metrics="views", dimensions="deviceType", sort="-views")
q("subscribed", metrics="views,averageViewDuration", dimensions="subscribedStatus")
q("creator_content", metrics="views,estimatedMinutesWatched", dimensions="creatorContentType")
for vid in ids:
    q(f"traffic_{vid}", metrics="views,averageViewDuration", dimensions="insightTrafficSourceType",
      filters=f"video=={vid}", sort="-views")
    q(f"country_{vid}", metrics="views", dimensions="country", filters=f"video=={vid}", sort="-views", maxResults=5)
for vid in ids:
    q(f"retention_{vid}", metrics="audienceWatchRatio,relativeRetentionPerformance", dimensions="elapsedVideoTimeRatio",
      filters=f"video=={vid}")
