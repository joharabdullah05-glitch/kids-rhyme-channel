"""
Uploads final_video.mp4 to YouTube using a pre-authorized OAuth refresh token.
All credentials come from environment variables / GitHub Actions secrets:
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

No browser sign-in happens here - the refresh token was generated once,
manually, via Google's OAuth Playground (see README.md).
"""
import os
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

ROOT = Path(__file__).parent
VIDEO_FILE = ROOT / "final_video.mp4"
TITLE_FILE = ROOT / "title.txt"
DESC_FILE = ROOT / "description.txt"
THUMBNAIL_FILE = ROOT / "captioned_0.jpg"  # first captioned frame from generate_video.py

BASE_TAGS = ["nursery rhymes", "kids songs", "toddler songs", "songs for children", "shorts"]


def get_credentials():
    return Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )


def build_tags(title: str):
    # Pull the rhyme name (before the " | ") into its own tags for better search matching
    rhyme_name = title.split("|")[0].strip()
    extra = [rhyme_name, rhyme_name.lower()] if rhyme_name else []
    # de-dupe while preserving order, stay under YouTube's ~500 char tag budget
    seen = set()
    tags = []
    for t in extra + BASE_TAGS:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            tags.append(t)
    return tags


def upload_with_retry(request, max_retries=5):
    response = None
    retry = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retry < max_retries:
                wait = 2 ** retry
                print(f"Transient error ({e.resp.status}), retrying in {wait}s...")
                time.sleep(wait)
                retry += 1
                continue
            raise
    return response


def set_thumbnail(youtube, video_id: str):
    if not THUMBNAIL_FILE.exists():
        return
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(THUMBNAIL_FILE), mimetype="image/jpeg"),
        ).execute()
        print("Custom thumbnail set.")
    except HttpError as e:
        # Custom thumbnails require a phone-verified channel; fail quietly if not eligible
        print(f"Could not set thumbnail (channel may need phone verification): {e}")


def upload():
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    title = TITLE_FILE.read_text().strip()
    description = DESC_FILE.read_text().strip()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": build_tags(title),
            "categoryId": "27",  # Education
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": True,  # required for kids' content (COPPA) - do not change
        },
    }

    media = MediaFileUpload(str(VIDEO_FILE), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = upload_with_retry(request)
    video_id = response["id"]
    print("Upload complete. Video ID:", video_id)

    set_thumbnail(youtube, video_id)
    return video_id


if __name__ == "__main__":
    upload()
