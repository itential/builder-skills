#!/usr/bin/env python3
"""
Initialize a use-case directory under use-cases/<name>/.
Requires platform data — run scripts/platform_pull.py first.

Usage:
    python scripts/use_case_init.py <use-case-name> <platform-url> <client-id> <client-secret>
"""

import argparse
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


def main():
    parser = argparse.ArgumentParser(description="Initialize a use-case directory")
    parser.add_argument("use_case", help="Use-case name (becomes the directory name)")
    parser.add_argument("platform_url", help="Platform base URL")
    parser.add_argument("client_id", help="OAuth client ID")
    parser.add_argument("client_secret", help="OAuth client secret")
    args = parser.parse_args()

    base = args.platform_url.rstrip("/")
    use_case_dir = USE_CASES_DIR / args.use_case

    # Require platform data
    if not PULLED_AT_FILE.exists():
        print("ERROR: Platform data not found.", file=sys.stderr)
        print("       Run first: python scripts/platform_pull.py <platform-url> <client-id> <client-secret>", file=sys.stderr)
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
    (use_case_dir / ".env").write_text(env_content)

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
    (use_case_dir / ".auth.json").write_text(json.dumps(auth, indent=2) + "\n")
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
