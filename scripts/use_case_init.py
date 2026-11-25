#!/usr/bin/env python3
"""
Initialize a use-case directory under use-cases/<name>/.
Requires platform data — run scripts/platform_pull.py first.

Usage (the client secret comes from ITENTIAL_CLIENT_SECRET, --env-file, or a hidden prompt —
never the command line, where it shows up in shell history and the process list):
    python scripts/use_case_init.py <use-case-name> <platform-url> <client-id>
"""

import argparse
import getpass
import os
import json
import shutil
from datetime import datetime, timezone
import sys
import urllib.parse
import urllib.request
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent
PLATFORM_DIR = SCRIPTS_DIR.parent / "platform"
USE_CASES_DIR = SCRIPTS_DIR.parent / "use-cases"
PULLED_AT_FILE = PLATFORM_DIR / ".pulled-at"


def get_token(platform_url, client_id, client_secret):
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(
        f"{platform_url}/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read()).get("access_token", "")
    if not token:
        print("ERROR: Authentication failed — no access_token in response", file=sys.stderr)
        sys.exit(1)
    return token



def read_env_file(path):
    """KEY=VALUE pairs from a .env file (comments and blank lines skipped, surrounding quotes removed)."""
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def resolve_credentials(args):
    """Fill platform_url, client_id and client_secret without the secret ever being typed on the command line.

    Secret, in order: the deprecated positional argument (with a warning), ITENTIAL_CLIENT_SECRET,
    --env-file, then a hidden prompt when run in a terminal. URL and client ID fall back to --env-file.
    """
    env = read_env_file(args.env_file) if args.env_file else {}
    args.platform_url = args.platform_url or env.get("PLATFORM_URL")
    args.client_id = args.client_id or env.get("CLIENT_ID")
    if not args.platform_url or not args.client_id:
        sys.exit("ERROR: give the platform URL and client ID as arguments, or point --env-file at a .env that has them.")
    if args.client_secret:
        print("WARNING: a client secret on the command line shows up in your shell history and the process list. "
              "Set ITENTIAL_CLIENT_SECRET, use --env-file, or leave it out to be prompted. "
              "This argument will be removed in a future release.", file=sys.stderr)
        return
    args.client_secret = os.environ.get("ITENTIAL_CLIENT_SECRET") or env.get("CLIENT_SECRET")
    if not args.client_secret and sys.stdin.isatty():
        args.client_secret = getpass.getpass("Client secret (input hidden): ")
    if not args.client_secret:
        sys.exit("ERROR: no client secret. Set ITENTIAL_CLIENT_SECRET, use --env-file, or run in a terminal to be prompted.")


def write_private(path, text):
    """Write a file only its owner can read (credentials and tokens)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(path, 0o600)

def main():
    parser = argparse.ArgumentParser(description="Initialize a use-case directory")
    parser.add_argument("use_case", help="Use-case name (becomes the directory name)")
    parser.add_argument("platform_url", nargs="?", help="Platform base URL (or PLATFORM_URL in --env-file)")
    parser.add_argument("client_id", nargs="?", help="OAuth client ID (or CLIENT_ID in --env-file)")
    parser.add_argument("client_secret", nargs="?", help=argparse.SUPPRESS)  # deprecated: visible in shell history and ps
    parser.add_argument("--env-file", help="read PLATFORM_URL, CLIENT_ID and CLIENT_SECRET from this .env file")
    args = parser.parse_args()
    resolve_credentials(args)

    base = args.platform_url.rstrip("/")
    use_case_dir = USE_CASES_DIR / args.use_case

    # Require platform data
    if not PULLED_AT_FILE.exists():
        print("ERROR: Platform data not found.", file=sys.stderr)
        print("       Run first: python scripts/platform_pull.py <platform-url> <client-id>", file=sys.stderr)
        sys.exit(1)

    print(f"Platform data: {PULLED_AT_FILE.read_text().strip()}")

    # Skip if already initialized
    if use_case_dir.exists():
        print(f"Use-case '{args.use_case}' already exists at {use_case_dir} — skipping.")
        return

    use_case_dir.mkdir(parents=True)

    # Write .env
    env_content = "\n".join([
        f"PLATFORM_URL={base}",
        f"CLIENT_ID={args.client_id}",
        f"CLIENT_SECRET={args.client_secret}",
        "AUTH_METHOD=oauth",
        "",
    ])
    write_private(use_case_dir / ".env", env_content)

    # Get initial token and write .auth.json
    print(f"Authenticating to {base}...")
    token = get_token(base, args.client_id, args.client_secret)
    # Same shape the skills write and read (see AGENTS.md -> Auth Reuse)
    auth = {
        "platform_url": base,
        "auth_method": "oauth",
        "token": token,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    write_private(use_case_dir / ".auth.json", json.dumps(auth, indent=2) + "\n")
    print("Authenticated.")

    # Create empty task schema cache
    (use_case_dir / "task-schemas.json").write_text("[]\n")

    # Start the use-case memory file from the template (AGENTS.md -> Directory Layout)
    template = SCRIPTS_DIR.parent / "helpers" / "use-case-memory.md"
    if template.exists():
        shutil.copy(template, use_case_dir / "use-case-memory.md")

    print(f"\n=== Use-case initialized: {args.use_case} ===")
    print(f"  {use_case_dir}/")
    print(f"    .env              — credentials (gitignored)")
    print(f"    .auth.json        — bearer token (gitignored, auto-refreshed)")
    print(f"    task-schemas.json — task schema cache (populated on demand)")
    print(f"    use-case-memory.md — living context: IDs, decisions, open items")
    print(f"\nPlatform data (shared): {PLATFORM_DIR}/")
    print(f"  openapi.json, tasks.json, apps.json, adapters.json, environment.md")


if __name__ == "__main__":
    main()
