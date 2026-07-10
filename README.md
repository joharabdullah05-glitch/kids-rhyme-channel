# Free, Automated Nursery-Rhyme Channel — Setup Guide

No coding needed. You're just creating free accounts and copy-pasting a few
values. Takes about 30-45 minutes, one time. After that, it uploads a new
video every day on its own.

**What this does:** Every day, a free script picks a public-domain nursery
rhyme, narrates it with free text-to-speech, generates a cartoon background
image for free, stitches them into a video, and uploads it to your YouTube
channel — automatically, with no computer of yours needing to be on.

**What it costs:** $0. Uses only free tiers: GitHub Actions (free automation
runner), Edge TTS (free voice), Pollinations.ai (free AI images), YouTube
Data API (free).

**Read the warning in the chat before doing this** — YouTube penalizes
fully automated "repetitive, mass-produced" content, and kids' content has
extra restrictions. This is a real pipeline, but keep an eye on your
channel's status, especially in the first couple weeks.

---

## Step 1 — Create a GitHub account (free)
1. Go to https://github.com and sign up (free).
2. Click the "+" in the top right → "New repository."
3. Name it anything (e.g. `kids-rhyme-channel`), set it to **Public**, click
   "Create repository."

## Step 2 — Upload these files to your new repo
1. In your new repo, click "Add file" → "Upload files."
2. Upload every file from this project **except** keep the folder structure:
   the file `daily.yml` must end up at the path `.github/workflows/daily.yml`
   exactly (GitHub's upload box lets you drag the whole `.github` folder in —
   if it doesn't preserve the path, create the folders manually using
   "Add file" → "Create new file" and type `.github/workflows/daily.yml` as
   the filename, which auto-creates the folders).
3. Commit the files to the `main` branch.

## Step 3 — Create a Google Cloud project + enable YouTube API (free)
1. Go to https://console.cloud.google.com and sign in with the Google
   account that owns (or will own) your YouTube channel.
2. Create a new project (top left dropdown → "New Project").
3. In the search bar, search "YouTube Data API v3" → click it → click
   "Enable."
4. Go to "APIs & Services" → "OAuth consent screen." Choose "External,"
   fill in an app name (anything) and your email, save through the steps.
   You don't need to submit for verification — it works in testing mode for
   your own account.
5. Go to "APIs & Services" → "Credentials" → "Create Credentials" →
   "OAuth client ID."
   - Application type: **Web application**
   - Under "Authorized redirect URIs," add:
     `https://developers.google.com/oauthplayground`
   - Click Create. You'll get a **Client ID** and **Client Secret** — copy
     both somewhere safe.

## Step 4 — Get a refresh token (one-time, browser only, no code)
1. Go to https://developers.google.com/oauthplayground
2. Click the gear icon (⚙️) top right → check "Use your own OAuth
   credentials" → paste in your Client ID and Client Secret from Step 3.
3. In the left panel's scope list, find and enter this scope manually:
   `https://www.googleapis.com/auth/youtube.upload`
   → click "Authorize APIs."
4. Sign in with the Google account that owns your YouTube channel, approve
   access.
5. Back on the Playground page, click "Exchange authorization code for
   tokens."
6. Copy the **Refresh token** shown — this is what lets the automation
   upload videos without you signing in again.

## Step 5 — Add your secrets to GitHub
1. In your GitHub repo, go to "Settings" → "Secrets and variables" →
   "Actions" → "New repository secret."
2. Add three secrets:
   - `YT_CLIENT_ID` → your Client ID from Step 3
   - `YT_CLIENT_SECRET` → your Client Secret from Step 3
   - `YT_REFRESH_TOKEN` → your refresh token from Step 4

## Step 6 — Turn it on
1. Go to the "Actions" tab in your repo. GitHub may ask you to confirm you
   want to enable workflows — click enable.
2. Click "Daily Nursery Rhyme Upload" in the left list → "Run workflow" to
   test it manually right away.
3. Watch the run — if it finishes green, check your YouTube channel: a new
   video should appear.
4. From here on, it runs automatically every day at 14:00 UTC (edit the
   `cron` line in `.github/workflows/daily.yml` to change the time).

---

## If something fails
Click into the failed run in the "Actions" tab — it shows exactly which
step broke and why. Common issues:
- **Auth error on upload** → refresh token or client secret was copied
  wrong, or the OAuth consent screen wasn't saved — redo Step 3-4.
- **Quota exceeded** → YouTube's free API quota allows about 6 uploads/day;
  daily is well within that.
- **Image/audio generation fails occasionally** → free services sometimes
  rate-limit; a failed run just skips that day, nothing breaks long-term.

## Growing this later
- `rhymes.json` has 15 public-domain rhymes on rotation — add more anytime.
- Once running, add your Ko-fi tip link and an affiliate link to the
  channel bio (from the earlier 30-day plan) — the automation handles
  content, but the monetization link is a one-time manual add.
