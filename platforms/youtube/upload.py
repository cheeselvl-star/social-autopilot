#!/usr/bin/env python3
"""
YouTube video uploader.

Usage:
    python platforms/youtube/upload.py --video video.mp4 --config upload_config.json
    python platforms/youtube/upload.py --video video.mp4 --title "My Video" --description "Desc"

Reads OAuth token from state/oauth/token.json (relative to project root, or
override with STATE_DIR env var).

Prints final YouTube URL to stdout. Progress and errors go to stderr.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def get_state_dir() -> Path:
    state_dir = os.environ.get("STATE_DIR")
    if state_dir:
        return Path(state_dir)
    # Walk up from this file to find the project root (contains run.py or state/)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "state").exists() or (parent / "run.py").exists():
            return parent / "state"
    # Fallback: relative to cwd
    return Path("state")


def token_path() -> Path:
    return get_state_dir() / "oauth" / "token.json"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def load_credentials() -> Credentials:
    path = token_path()
    if not path.exists():
        print(f"ERROR: token not found at {path}", file=sys.stderr)
        print("Run: python platforms/youtube/oauth_setup.py", file=sys.stderr)
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(str(path), SCOPES)

    if creds.expired and creds.refresh_token:
        print("Token expired — refreshing...", file=sys.stderr)
        creds.refresh(Request())
        # Persist refreshed token
        path.write_text(creds.to_json())
        print("Token refreshed and saved.", file=sys.stderr)

    if not creds.valid:
        print("ERROR: credentials are not valid and could not be refreshed.", file=sys.stderr)
        print("Re-run OAuth setup: python platforms/youtube/oauth_setup.py", file=sys.stderr)
        sys.exit(1)

    return creds


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

RETRIABLE_STATUS_CODES = {500, 502, 503, 504}
MAX_RETRIES = 5


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    privacy_status: str,
) -> str:
    """Upload video and return the YouTube video URL."""
    creds = load_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    video_file = Path(video_path)
    if not video_file.exists():
        print(f"ERROR: video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    file_size = video_file.stat().st_size
    print(f"Uploading: {video_file.name} ({file_size / 1_048_576:.1f} MB)", file=sys.stderr)
    print(f"Title: {title}", file=sys.stderr)
    print(f"Privacy: {privacy_status}", file=sys.stderr)

    media = MediaFileUpload(
        str(video_file),
        mimetype="video/*",
        resumable=True,
        chunksize=256 * 1024,  # 256 KB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    retry = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"Upload progress: {pct}%", file=sys.stderr)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                if retry >= MAX_RETRIES:
                    print(f"ERROR: max retries exceeded. Last error: {e}", file=sys.stderr)
                    sys.exit(1)
                wait = 2 ** retry
                print(f"Retriable error ({e.resp.status}), retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                retry += 1
            else:
                print(f"ERROR: non-retriable HTTP error: {e}", file=sys.stderr)
                sys.exit(1)

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Upload complete. Video ID: {video_id}", file=sys.stderr)
    return url


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Upload a video to YouTube.")
    parser.add_argument("--video", required=True, help="Path to the video file.")
    parser.add_argument(
        "--config",
        help="Path to a JSON config file with title, description, tags, categoryId, privacyStatus.",
    )
    parser.add_argument("--title", default=None)
    parser.add_argument("--description", default="")
    parser.add_argument("--tags", nargs="+", default=[])
    parser.add_argument("--category-id", default="22", help="YouTube category ID (default: 22 = People & Blogs)")
    parser.add_argument(
        "--privacy",
        default="public",
        choices=["public", "private", "unlisted"],
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Start with defaults, overlay config file, overlay CLI args
    config = {
        "title": None,
        "description": "",
        "tags": [],
        "categoryId": "22",
        "privacyStatus": "public",
    }

    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"ERROR: config file not found: {args.config}", file=sys.stderr)
            sys.exit(1)
        with open(config_path) as f:
            file_config = json.load(f)
        config.update(file_config)

    # CLI args override config file
    if args.title:
        config["title"] = args.title
    if args.description:
        config["description"] = args.description
    if args.tags:
        config["tags"] = args.tags
    if args.category_id:
        config["categoryId"] = args.category_id
    if args.privacy:
        config["privacyStatus"] = args.privacy

    if not config.get("title"):
        # Fall back to video filename stem
        config["title"] = Path(args.video).stem
        print(f"No title provided — using filename: {config['title']}", file=sys.stderr)

    url = upload_video(
        video_path=args.video,
        title=config["title"],
        description=config.get("description", ""),
        tags=config.get("tags", []),
        category_id=config.get("categoryId", "22"),
        privacy_status=config.get("privacyStatus", "public"),
    )

    # Final URL goes to stdout so callers can capture it
    print(url)


if __name__ == "__main__":
    main()
