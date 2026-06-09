#!/usr/bin/env python3
"""
YouTube OAuth token refresh.

Reads token from state/oauth/token.json (or STATE_DIR env var) and refreshes it
if it is expired. Safe to run as a cron job — exits 0 on success, 1 on failure.

Usage:
    python platforms/youtube/token_refresh.py
"""

import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_state_dir() -> Path:
    state_dir = os.environ.get("STATE_DIR")
    if state_dir:
        return Path(state_dir)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "state").exists() or (parent / "run.py").exists():
            return parent / "state"
    return Path("state")


def main():
    token_file = get_state_dir() / "oauth" / "token.json"

    if not token_file.exists():
        print(f"ERROR: token not found at {token_file}")
        print("Run oauth_setup.py first to obtain a token.")
        sys.exit(1)

    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    except Exception as e:
        print(f"ERROR: could not load token: {e}")
        sys.exit(1)

    if creds.valid:
        print("OK (token is still valid, no refresh needed)")
        sys.exit(0)

    if not creds.refresh_token:
        print("ERROR: token is expired and no refresh_token is present. Re-run oauth_setup.py.")
        sys.exit(1)

    try:
        creds.refresh(Request())
    except Exception as e:
        print(f"ERROR: token refresh failed: {e}")
        sys.exit(1)

    try:
        token_file.write_text(creds.to_json())
    except Exception as e:
        print(f"ERROR: could not save refreshed token: {e}")
        sys.exit(1)

    print("OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
