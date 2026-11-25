#!/usr/bin/env python3
"""
Pull platform-wide data into platform/ directory.
Run once per platform instance. Use --refresh to re-pull.

Usage (the client secret comes from ITENTIAL_CLIENT_SECRET, --env-file, or a hidden prompt —
never the command line, where it shows up in shell history and the process list):
    python scripts/platform_pull.py <platform-url> <client-id>
    python scripts/platform_pull.py --refresh --env-file use-cases/<name>/.env
"""

import argparse
import getpass
import os
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


PLATFORM_DIR = Path(__file__).parent.parent / "platform"
PULLED_AT_FILE = PLATFORM_DIR / ".pulled-at"


def fetch(url, token, filename):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    print(f"  ✓ {filename}")
    return filename, data


def authenticate(base, client_id, client_secret):
    print(f"Authenticating to {base}...")
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(
        f"{base}/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read()).get("access_token", "")
    if not token:
        print("ERROR: Authentication failed — no access_token in response", file=sys.stderr)
        sys.exit(1)
    print("Authenticated.")
    return token


def generate_environment_summary(d: Path):
    tasks = json.loads((d / "tasks.json").read_text())
    apps_raw = json.loads((d / "apps.json").read_text())
    adapters_raw = json.loads((d / "adapters.json").read_text())
    applications_raw = json.loads((d / "applications.json").read_text())

    apps = apps_raw if isinstance(apps_raw, list) else apps_raw.get("results", [])
    adapters = adapters_raw if isinstance(adapters_raw, list) else adapters_raw.get("results", [])
    applications = applications_raw if isinstance(applications_raw, list) else applications_raw.get("results", [])

    task_locations = Counter(t.get("location", "") for t in tasks)
    task_apps = Counter(t.get("app", "") for t in tasks)

    lines = [
        "# Environment Overview\n",
        f"**Total tasks in palette:** {len(tasks)}",
        f"  - Application tasks: {task_locations.get('Application', 0)}",
        f"  - Adapter tasks: {task_locations.get('Adapter', 0)}",
        f"  - Broker tasks: {task_locations.get('Broker', 0)}\n",
        "## Applications\n",
        "| Application | State | Description | Task Count |",
        "|-------------|-------|-------------|------------|",
    ]
    for a in sorted(applications, key=lambda x: x.get("id", "")):
        name = a.get("id", "")
        desc = (a.get("description", "") or "")[:60]
        lines.append(f"| {name} | {a.get('state', '')} | {desc} | {task_apps.get(name, 0)} |")

    lines += [
        "",
        "## Adapters\n",
        "| Instance Name | Adapter Type | Package | State | Task Count |",
        "|---------------|-------------|---------|-------|------------|",
    ]
    for a in sorted(adapters, key=lambda x: x.get("id", "")):
        name = a.get("id", "")
        pkg = a.get("package_id", "")
        adapter_type = pkg.split("adapter-")[-1] if "adapter-" in pkg else pkg.split("/")[-1]
        lines.append(f"| {name} | {adapter_type} | {pkg} | {a.get('state', '')} | {task_apps.get(name, 0)} |")

    lines += [
        "",
        "## Top Task Sources\n",
        "| Source | Location | Task Count |",
        "|--------|----------|------------|",
    ]
    for app, cnt in task_apps.most_common(20):
        loc = next((t.get("location", "") for t in tasks if t.get("app") == app), "")
        lines.append(f"| {app} | {loc} | {cnt} |")

    (d / "environment.md").write_text("\n".join(lines) + "\n")



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

def main():
    parser = argparse.ArgumentParser(description="Pull platform-wide data into platform/")
    parser.add_argument("--refresh", action="store_true", help="Re-pull even if data already exists")
    parser.add_argument("platform_url", nargs="?", help="Platform base URL (or PLATFORM_URL in --env-file)")
    parser.add_argument("client_id", nargs="?", help="OAuth client ID (or CLIENT_ID in --env-file)")
    parser.add_argument("client_secret", nargs="?", help=argparse.SUPPRESS)  # deprecated: visible in shell history and ps
    parser.add_argument("--env-file", help="read PLATFORM_URL, CLIENT_ID and CLIENT_SECRET from this .env file")
    args = parser.parse_args()
    resolve_credentials(args)

    base = args.platform_url.rstrip("/")

    # Skip if already pulled
    if PULLED_AT_FILE.exists() and not args.refresh:
        print(f"Platform data already pulled: {PULLED_AT_FILE.read_text().strip()}")
        print("Use --refresh to re-pull.")
        return

    PLATFORM_DIR.mkdir(exist_ok=True)

    token = authenticate(base, args.client_id, args.client_secret)

    encoded_base = urllib.parse.quote(base, safe="")

    files = {
        "openapi.json": f"{base}/help/openapi?url={encoded_base}",
        "tasks.json": f"{base}/workflow_builder/tasks/list",
        "apps.json": f"{base}/automation-studio/apps/list",
        "adapters.json": f"{base}/health/adapters",
        "applications.json": f"{base}/health/applications",
    }

    print(f"Pulling {len(files)} files in parallel...")
    with ThreadPoolExecutor(max_workers=len(files)) as executor:
        futures = {executor.submit(fetch, url, token, filename): filename for filename, url in files.items()}
        for future in as_completed(futures):
            filename, data = future.result()
            (PLATFORM_DIR / filename).write_bytes(data)

    print("  Generating environment.md...")
    generate_environment_summary(PLATFORM_DIR)

    pulled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    PULLED_AT_FILE.write_text(f"{pulled_at}  {base}\n")

    task_count = len(json.loads((PLATFORM_DIR / "tasks.json").read_text()))
    apps_raw = json.loads((PLATFORM_DIR / "apps.json").read_text())
    app_count = len(apps_raw) if isinstance(apps_raw, list) else len(apps_raw.get("results", []))

    print(f"\n=== Platform data pulled at {pulled_at} ===")
    print(f"  {PLATFORM_DIR}/")
    print(f"    openapi.json      — full API reference ({base})")
    print(f"    tasks.json        — {task_count} tasks")
    print(f"    apps.json         — {app_count} apps/adapters")
    print(f"    adapters.json     — adapter instance details")
    print(f"    applications.json — application details")
    print(f"    environment.md    — summary with task counts")


if __name__ == "__main__":
    main()
