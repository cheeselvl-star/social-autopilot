#!/usr/bin/env python3
"""
Facebook long-lived token refresh.

Exchanges a short-lived page access token for a long-lived one (valid ~60 days).
Reads credentials from environment variables:
    FB_ACCESS_TOKEN  — current page access token
    FB_APP_ID        — your Meta app ID
    FB_APP_SECRET    — your Meta app secret

Writes the new token back to .env if a .env file exists in the project root,
otherwise prints it to stdout.

Exits 0 on success, 1 on failure.

Usage:
    python platforms/facebook/token_refresh.py
"""

import os
import re
import sys
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


GRAPH_API_VERSION = "v19.0"


def get_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"ERROR: {key} is not set. Add it to .env or export it.")
        sys.exit(1)
    return val


def exchange_for_long_lived_token(app_id: str, app_secret: str, short_token: str) -> str:
    """Exchange a user/page token for a long-lived token."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"
    resp = requests.get(
        url,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )

    try:
        resp.raise_for_status()
    except requests.HTTPError:
        try:
            err = resp.json()
            print(f"ERROR: Facebook API returned an error: {err.get('error', {}).get('message', resp.text)}")
        except Exception:
            print(f"ERROR: HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    token = data.get("access_token")
    if not token:
        print(f"ERROR: no access_token in response: {data}")
        sys.exit(1)

    expires_in = data.get("expires_in")
    if expires_in:
        days = int(expires_in) // 86400
        print(f"New token expires in approximately {days} days.")

    return token


def find_env_file() -> Path | None:
    """Walk up from CWD to find a .env file."""
    here = Path.cwd()
    for parent in [here] + list(here.parents):
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
        # Stop at home dir
        if parent == Path.home():
            break
    return None


def update_env_file(env_path: Path, key: str, new_value: str) -> bool:
    """Update a key=value line in the .env file. Returns True if key was found and updated."""
    content = env_path.read_text()
    pattern = re.compile(rf"^({re.escape(key)}\s*=\s*)(.*)$", re.MULTILINE)
    if pattern.search(content):
        new_content = pattern.sub(rf"\g<1>{new_value}", content)
        env_path.write_text(new_content)
        return True
    return False


def main():
    access_token = get_env("FB_ACCESS_TOKEN")
    app_id = get_env("FB_APP_ID")
    app_secret = get_env("FB_APP_SECRET")

    print("Exchanging token for long-lived version...")
    new_token = exchange_for_long_lived_token(app_id, app_secret, access_token)

    env_file = find_env_file()
    if env_file:
        updated = update_env_file(env_file, "FB_ACCESS_TOKEN", new_token)
        if updated:
            print(f"Token updated in {env_file}")
        else:
            print(f"FB_ACCESS_TOKEN not found in {env_file} — printing new token instead.")
            print(f"New token: {new_token}")
    else:
        print("No .env file found. New token:")
        print(new_token)

    print("OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
