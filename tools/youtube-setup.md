# Connecting YouTube (one time, about 15 minutes)

Do this signed in with the channel's Google account.

## 1. Create a Google Cloud project

1. Go to console.cloud.google.com and create a project called `human-glitch`.
2. APIs & Services > Library: search **YouTube Data API v3** and click **Enable**.

## 2. OAuth consent screen

1. APIs & Services > OAuth consent screen (Google Auth Platform): choose **External**.
2. App name `Human Glitch Uploader`, your email as support and developer contact.
3. Audience: add the channel's Gmail address as a **test user**.
4. **Publish the app** (Audience > Publish app). Apps left in "Testing" get tokens that expire after 7 days.
   You will see an "unverified app" warning when you authorize; that is expected for your own app.

## 3. Create the OAuth client

1. APIs & Services > Credentials > Create credentials > OAuth client ID.
2. Application type: **Web application**.
3. Authorized redirect URI: `https://developers.google.com/oauthplayground`
4. Copy the **Client ID** and **Client secret**.

## 4. Get the refresh token (no installs needed)

1. Open developers.google.com/oauthplayground.
2. Gear icon (top right) > tick **Use your own OAuth credentials** > paste Client ID and secret.
3. In "Input your own scopes" paste:
   `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl`
4. Click **Authorize APIs**, choose the channel account, accept the warnings.
5. Click **Exchange authorization code for tokens** and copy the **Refresh token**.

## 5. Save the three secrets in GitHub

Repository > Settings > Secrets and variables > Actions:

- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

Never paste these values in a chat or commit them to the repository.

## Good to know

- Projects that have not passed Google's API audit can only upload **private** videos.
  The pipeline uploads private; you publish or schedule in YouTube Studio with two clicks.
  You can request the audit later from the YouTube API Services form if you want fully automatic publishing.
- Free quota is 10,000 units a day; one upload uses about 1,600, so roughly 6 uploads a day.
- Custom thumbnails need a phone-verified channel (youtube.com/verify).
