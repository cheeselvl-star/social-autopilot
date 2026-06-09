#!/usr/bin/env python3
"""
social-autopilot -- automate video publishing to YouTube and Facebook

Usage:
  python run.py youtube upload --video path/to/video.mp4 --config upload.json
  python run.py youtube upload --video path/to/video.mp4 --title "Title"
  python run.py youtube token-refresh
  python run.py youtube oauth-setup
  python run.py youtube oauth-setup --code AUTH_CODE

  python run.py facebook upload --video path/to/video.mp4 --title "Title" --description "Desc"
  python run.py facebook token-refresh
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLATFORMS = ROOT / "platforms"


def usage():
    print(__doc__.strip())
    sys.exit(1)


def run_script(script_path: Path, args: list[str]):
    """Run a platform script, forwarding remaining CLI args."""
    if not script_path.exists():
        print(f"ERROR: script not found: {script_path}", file=sys.stderr)
        sys.exit(1)
    result = subprocess.run([sys.executable, str(script_path)] + args)
    sys.exit(result.returncode)


def main():
    if len(sys.argv) < 3:
        usage()

    platform = sys.argv[1].lower()
    command = sys.argv[2].lower()
    remaining = sys.argv[3:]

    routes = {
        ("youtube", "upload"):        PLATFORMS / "youtube" / "upload.py",
        ("youtube", "token-refresh"): PLATFORMS / "youtube" / "token_refresh.py",
        ("youtube", "oauth-setup"):   PLATFORMS / "youtube" / "oauth_setup.py",
        ("facebook", "upload"):       PLATFORMS / "facebook" / "upload.py",
        ("facebook", "token-refresh"): PLATFORMS / "facebook" / "token_refresh.py",
    }

    key = (platform, command)
    if key not in routes:
        print(f"ERROR: unknown command: {platform} {command}", file=sys.stderr)
        print(file=sys.stderr)
        usage()

    run_script(routes[key], remaining)


if __name__ == "__main__":
    main()
