# Human Glitch

Free pipeline that turns a reviewed script into a finished YouTube video for the
Human Glitch channel (psychology told as stories, English with a Spanish audio track).

## What it makes for each episode

| File | What it is |
| --- | --- |
| `video.mp4` | 1080p long video: scene cards, stock footage, voice, word-by-word subtitles, watermark |
| `short.mp4` | Vertical Short cut from one scene, under 60 seconds |
| `thumbnail.jpg` | 1280x720 thumbnail in the channel style |
| `audio.es.m4a` | Spanish narration timed to the video, for YouTube's multi-language audio |
| `captions.en.srt`, `captions.es.srt` | Caption files |
| `description.txt` | Description with chapters |

Everything runs on GitHub Actions for free: Microsoft Edge voices (no key), Pixabay
stock footage (free key), ffmpeg, and the YouTube Data API.

## Weekly routine

1. Claude writes the script in `episodes/NNN-topic/` (`script.en.md`, `script.es.md`, `meta.yaml`).
2. You read it and, when happy, change `approved: false` to `approved: true` in `meta.yaml`.
3. GitHub renders the episode. When YouTube is connected, it uploads the video and the Short
   as **private**, with captions and thumbnail. Otherwise download the files from the
   workflow run (Actions tab > the run > Artifacts).
4. In YouTube Studio: check the video, add the Spanish audio file if your channel has
   multi-language audio, and publish or schedule it.

## Script format

```markdown
# Scene: The interview
> keywords: office night laptop woman     (stock footage search)
> card: THEY MADE A MISTAKE               (big text on the scene's opening card)

Narration paragraphs...
```

`script.es.md` must have the same number of scenes; only the narration is used.

## One-time setup (secrets)

Add these in the repository: Settings > Secrets and variables > Actions > New repository secret.

| Secret | Where to get it |
| --- | --- |
| `PIXABAY_API_KEY` | Free at pixabay.com/api/docs (signed in, the key shows under Parameters). Optional: without a stock key scenes use branded animated cards |
| `PEXELS_API_KEY` | Optional second source, if Pexels issues you a key |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | See `tools/youtube-setup.md` |

## Run locally (optional)

```bash
pip install -r requirements.txt   # also needs ffmpeg
python -m hg build episodes/001-impostor-syndrome
python -m hg upload episodes/001-impostor-syndrome
```
