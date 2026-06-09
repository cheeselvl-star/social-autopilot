# social-autopilot

Automate video publishing to YouTube and Facebook Pages from the command line.

Built for content creators who want to schedule or automate video uploads without manual intervention — it runs unattended as a cron job, refreshes OAuth tokens automatically, and prints the published URL to stdout so you can integrate it into any pipeline.

## What it does

- Upload videos to YouTube with full metadata (title, description, tags, category, privacy)
- Publish videos to Facebook Pages via the Graph API
- Auto-refresh OAuth tokens so long-running setups keep working without reauthentication
- Run as a cron job for daily or scheduled publishing pipelines

## Quick Start

### Prerequisites

- Python 3.10+
- A Google Cloud project with the YouTube Data API v3 enabled (for YouTube)
- A Meta Developer App with a page access token (for Facebook)

### Install dependencies

```bash
git clone https://github.com/you/social-autopilot.git
cd social-autopilot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### YouTube — 5 steps

1. Create a project at https://console.cloud.google.com/
2. Enable the YouTube Data API v3
3. Create OAuth 2.0 credentials (type: Desktop app) and download the JSON file
4. Save the JSON file to `state/oauth/client_secret.json`
5. Run the OAuth setup flow (see YouTube Setup below)

### Facebook — 5 steps

1. Create a Meta Developer App at https://developers.facebook.com/
2. Add the Facebook Login and Pages API products
3. Generate a page access token for your Page (via Graph API Explorer or app dashboard)
4. Copy `.env.example` to `.env` and fill in `FB_PAGE_ID`, `FB_ACCESS_TOKEN`, `FB_APP_ID`, `FB_APP_SECRET`
5. Run a test upload to confirm credentials work

---

## YouTube Setup

### 1. Create a Google Cloud project

Go to https://console.cloud.google.com/, create a new project, and enable the **YouTube Data API v3** under APIs & Services.

### 2. Create OAuth credentials

Under APIs & Services > Credentials, create an **OAuth 2.0 Client ID** with application type **Desktop app**. Download the JSON file and save it:

```
state/oauth/client_secret.json
```

### 3. Authorize the app (step 1)

```bash
python run.py youtube oauth-setup
```

This prints an authorization URL. Open it in a browser, sign in with your YouTube account, and authorize the app. Copy the authorization code from the final page.

### 4. Save the token (step 2)

```bash
python run.py youtube oauth-setup --code "4/0AX4..."
```

This saves `state/oauth/token.json`. You are now authorized to upload.

### 5. Test an upload

```bash
python run.py youtube upload --video test.mp4 --config config.example.json
```

---

## Facebook Setup

### 1. Create a Meta Developer App

Go to https://developers.facebook.com/apps/, create a new app, and add the **Pages API** product.

### 2. Get a page access token

Use the [Graph API Explorer](https://developers.facebook.com/tools/explorer/) to generate a page access token with the `pages_manage_posts` permission for your page. You can also generate one via your app's dashboard under Roles > Test Users or Tokens.

### 3. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
FB_PAGE_ID=123456789
FB_ACCESS_TOKEN=EAABsbCS...
FB_APP_ID=your_app_id
FB_APP_SECRET=your_app_secret
```

### 4. Exchange for a long-lived token

Page access tokens from the Explorer expire in ~1 hour. Exchange for a long-lived token (~60 days) immediately:

```bash
python run.py facebook token-refresh
```

This updates `FB_ACCESS_TOKEN` in your `.env` file automatically.

---

## Usage

All commands go through `run.py`:

```bash
# Upload to YouTube using a config file
python run.py youtube upload --video video.mp4 --config upload.json

# Upload to YouTube with inline metadata
python run.py youtube upload --video video.mp4 --title "My Video" --description "Description" --privacy public

# Refresh YouTube OAuth token
python run.py youtube token-refresh

# Re-run YouTube OAuth setup
python run.py youtube oauth-setup

# Upload to Facebook Page
python run.py facebook upload --video video.mp4 --title "My Video" --description "Description"

# Refresh Facebook long-lived token
python run.py facebook token-refresh
```

### YouTube upload config file

Copy `config.example.json` to `upload.json` and fill in your metadata:

```json
{
  "title": "My Video Title",
  "description": "Full description goes here.",
  "tags": ["tag1", "tag2"],
  "categoryId": "22",
  "privacyStatus": "public"
}
```

Category IDs reference: https://developers.google.com/youtube/v3/docs/videoCategories/list

### Privacy options

YouTube: `public`, `private`, `unlisted`

Facebook: all videos are published publicly to the page.

---

## Cron / Automation

Example crontab entries for a daily pipeline. Adjust paths to match your setup.

```cron
# Refresh YouTube token daily at 2 AM
0 2 * * * cd /path/to/social-autopilot && ./venv/bin/python run.py youtube token-refresh >> cron.log 2>&1

# Refresh Facebook token daily at 2:05 AM
5 2 * * * cd /path/to/social-autopilot && ./venv/bin/python run.py facebook token-refresh >> cron.log 2>&1

# Upload a video daily at 9 AM (after token refresh)
0 9 * * * cd /path/to/social-autopilot && ./venv/bin/python run.py youtube upload --video /path/to/video.mp4 --config upload.json >> cron.log 2>&1
```

To edit your crontab:

```bash
crontab -e
```

### Running on a Raspberry Pi

This runs well on a Raspberry Pi 5 with Python 3.11. The only hardware consideration is storage for video files — uploads stream directly from disk so memory usage is low regardless of file size.

---

## Project structure

```
social-autopilot/
  run.py                         # CLI entry point
  config.example.json            # Example YouTube upload metadata
  requirements.txt
  .env.example                   # Template for Facebook credentials
  platforms/
    youtube/
      upload.py                  # YouTube upload script
      token_refresh.py           # YouTube token refresh
      oauth_setup.py             # YouTube OAuth setup flow
    facebook/
      upload.py                  # Facebook Page video upload
      token_refresh.py           # Facebook long-lived token exchange
  state/
    oauth/
      client_secret.json         # (gitignored) Google OAuth client credentials
      token.json                 # (gitignored) YouTube access + refresh token
```

---

## Notes

- This is real production code that runs daily on a Raspberry Pi 5.
- **YouTube quota:** uploading a video consumes approximately 1,600 quota units. The default daily quota is 10,000 units, which allows roughly 6 uploads per day. Monitor your quota at https://console.cloud.google.com/apis/dashboard.
- **Facebook tokens expire.** Long-lived tokens are valid for approximately 60 days. Run `facebook token-refresh` on a schedule, or your uploads will start failing.
- **Never commit `.env` or `state/oauth/`.** Both are gitignored by default. Treat `FB_APP_SECRET` and `client_secret.json` as private credentials.
- The YouTube upload uses a resumable chunked upload, so large files and poor connections are handled gracefully — failed chunks are retried automatically.
