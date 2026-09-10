#!/usr/bin/env python3
"""Bump the plugin version across .claude-plugin/plugin.json and marketplace.json.

Used by .github/workflows/version-bump.yml after a PR merges to main. Not meant to be
run against a dirty working tree — reads the current version from plugin.json, computes
the next semver value for the given bump type, and writes it back to both manifest files
so they can never drift out of sync with each other.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def bump(version: str, kind: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown bump kind: {kind}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bump", required=True, choices=["major", "minor", "patch"])
    args = parser.parse_args()

    plugin = json.loads(PLUGIN_JSON.read_text())
    current_version = plugin["version"]
    new_version = bump(current_version, args.bump)

    plugin["version"] = new_version
    PLUGIN_JSON.write_text(json.dumps(plugin, indent=2) + "\n")

    marketplace = json.loads(MARKETPLACE_JSON.read_text())
    marketplace["metadata"]["version"] = new_version
    for entry in marketplace.get("plugins", []):
        entry["version"] = new_version
    MARKETPLACE_JSON.write_text(json.dumps(marketplace, indent=2) + "\n")

    print(f"{current_version} -> {new_version}", file=sys.stderr)
    print(new_version)


if __name__ == "__main__":
    main()
