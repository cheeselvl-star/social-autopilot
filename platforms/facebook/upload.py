#!/usr/bin/env python3
"""
Facebook Page video uploader.

Reads credentials from environment variables:
    FB_ACCESS_TOKEN  — page access token
    FB_PAGE_ID       — numeric Facebook page ID

Usage:
    python platforms/facebook/upload.py \\
        --video video.mp4 \\
        --title "My Video" \\
        --description "Description here"

Prints the post URL to stdout on success.
Progress and errors go to stderr.

Requires a .env file or env vars set in the shell. Uses python-dotenv to
load .env automatically if present.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be set directly


GRAPH_API_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Facebook uses a chunked resumable upload for videos.
# Chunk size: 10 MB — safe for most connections.
CHUNK_SIZE = 10 * 1024 * 1024


def get_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"ERROR: {key} is not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)
    return val


def start_upload_session(access_token: str, page_id: str, file_size: int, title: str) -> str:
    """Start a resumable upload session. Returns the upload_session_id."""
    url = f"{GRAPH_BASE}/{page_id}/videos"
    resp = requests.post(
        url,
        data={
            "upload_phase": "start",
            "file_size": file_size,
            "title": title,
            "access_token": access_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "upload_session_id" not in data:
        print(f"ERROR: unexpected response from Facebook: {data}", file=sys.stderr)
        sys.exit(1)
    return data["upload_session_id"]


def upload_chunk(
    access_token: str,
    upload_session_id: str,
    chunk_data: bytes,
    start_offset: int,
) -> int:
    """Upload a single chunk. Returns the next expected start_offset."""
    url = f"{GRAPH_BASE}/videos"
    files = {"video_file_chunk": ("chunk", chunk_data, "application/octet-stream")}
    resp = requests.post(
        url,
        data={
            "upload_phase": "transfer",
            "upload_session_id": upload_session_id,
            "start_offset": start_offset,
            "access_token": access_token,
        },
        files=files,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return int(data.get("start_offset", start_offset + len(chunk_data)))


def finish_upload(
    access_token: str,
    page_id: str,
    upload_session_id: str,
    description: str,
) -> str:
    """Finish the upload. Returns the video ID."""
    url = f"{GRAPH_BASE}/{page_id}/videos"
    resp = requests.post(
        url,
        data={
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "description": description,
            "access_token": access_token,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if "video_id" not in data and "id" not in data:
        print(f"ERROR: finish phase did not return a video ID: {data}", file=sys.stderr)
        sys.exit(1)
    return str(data.get("video_id") or data.get("id"))


def upload_video(video_path: str, title: str, description: str) -> str:
    """Upload video to Facebook Page. Returns the post URL."""
    access_token = get_env("FB_ACCESS_TOKEN")
    page_id = get_env("FB_PAGE_ID")

    video_file = Path(video_path)
    if not video_file.exists():
        print(f"ERROR: video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    file_size = video_file.stat().st_size
    print(f"Uploading: {video_file.name} ({file_size / 1_048_576:.1f} MB)", file=sys.stderr)
    print(f"Title: {title}", file=sys.stderr)

    # Start resumable session
    session_id = start_upload_session(access_token, page_id, file_size, title)
    print(f"Upload session started: {session_id}", file=sys.stderr)

    # Transfer chunks
    offset = 0
    with open(video_file, "rb") as f:
        chunk_num = 0
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            chunk_num += 1
            print(f"Uploading chunk {chunk_num}/{total_chunks}...", file=sys.stderr)
            retries = 0
            while retries < 3:
                try:
                    offset = upload_chunk(access_token, session_id, chunk, offset)
                    break
                except requests.RequestException as e:
                    retries += 1
                    if retries >= 3:
                        print(f"ERROR: chunk {chunk_num} failed after 3 retries: {e}", file=sys.stderr)
                        sys.exit(1)
                    wait = 2 ** retries
                    print(f"Chunk error, retrying in {wait}s: {e}", file=sys.stderr)
                    time.sleep(wait)

    print("All chunks uploaded. Finishing...", file=sys.stderr)
    video_id = finish_upload(access_token, page_id, session_id, description)

    post_url = f"https://www.facebook.com/{page_id}/videos/{video_id}"
    print(f"Upload complete. Video ID: {video_id}", file=sys.stderr)
    return post_url


def parse_args():
    parser = argparse.ArgumentParser(description="Upload a video to a Facebook Page.")
    parser.add_argument("--video", required=True, help="Path to the video file.")
    parser.add_argument("--title", required=True, help="Video title.")
    parser.add_argument("--description", default="", help="Video description / caption.")
    return parser.parse_args()


def main():
    args = parse_args()
    url = upload_video(
        video_path=args.video,
        title=args.title,
        description=args.description,
    )
    # URL to stdout so callers can capture it
    print(url)


if __name__ == "__main__":
    main()
