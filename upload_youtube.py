"""
Uploads final_video.mp4 to YouTube using a pre-authorized OAuth refresh token.
All credentials come from environment variables / GitHub Actions secrets:
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

No browser sign-in happens here - the refresh token was generated once,
manually, via Google's OAuth Playground (see README.md).
"""
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).parent
VIDEO_FILE = ROOT / "final_video.mp4"
TITLE_FILE = ROOT / "title.txt"
DESC_FILE = ROOT / "description.txt"


def get_credentials():
    return Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )


def upload():
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    title = TITLE_FILE.read_text().strip()
    description = DESC_FILE.read_text().strip()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["nursery rhymes", "kids songs", "toddler songs"],
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": True,  # required for kids' content (COPPA)
        },
    }

    media = MediaFileUpload(str(VIDEO_FILE), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print("Upload complete. Video ID:", response["id"])
    return response["id"]


if __name__ == "__main__":
    upload()
