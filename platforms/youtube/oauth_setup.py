#!/usr/bin/env python3
"""
YouTube OAuth setup — two-step flow.

Step 1 (no arguments):
    python platforms/youtube/oauth_setup.py
    Prints an authorization URL. Open it in a browser, authorize the app,
    and copy the code from the redirect URL.

Step 2 (with authorization code):
    python platforms/youtube/oauth_setup.py --code "4/0AX4..."
    Exchanges the code for tokens and saves them to state/oauth/token.json.

Reads client_secret.json from state/oauth/client_secret.json (or STATE_DIR env var).
"""

import argparse
import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


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
    parser = argparse.ArgumentParser(description="Set up YouTube OAuth credentials.")
    parser.add_argument(
        "--code",
        default=None,
        help="Authorization code from Google (step 2). Omit to print the auth URL (step 1).",
    )
    args = parser.parse_args()

    state_dir = get_state_dir()
    oauth_dir = state_dir / "oauth"
    client_secret_path = oauth_dir / "client_secret.json"
    token_path = oauth_dir / "token.json"

    if not client_secret_path.exists():
        print(f"ERROR: client_secret.json not found at {client_secret_path}")
        print()
        print("To get it:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project and enable the YouTube Data API v3")
        print("  3. Create OAuth 2.0 credentials (Desktop app)")
        print("  4. Download the JSON and save it to:", client_secret_path)
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret_path),
        scopes=SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob",
    )

    if args.code is None:
        # Step 1: print auth URL
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        print()
        print("Step 1: Open this URL in your browser and authorize the app:")
        print()
        print(auth_url)
        print()
        print("Step 2: After authorizing, copy the code and run:")
        print(f"  python {Path(__file__).name} --code YOUR_CODE_HERE")
        print()
    else:
        # Step 2: exchange code for token
        try:
            flow.fetch_token(code=args.code)
        except Exception as e:
            print(f"ERROR: could not exchange code for token: {e}")
            sys.exit(1)

        creds = flow.credentials
        oauth_dir.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

        print(f"Token saved to {token_path}")
        print()
        print("You can now run uploads:")
        print("  python run.py youtube upload --video video.mp4 --config upload.json")


if __name__ == "__main__":
    main()
