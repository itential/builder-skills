#!/usr/bin/env python3
"""Bump the plugin version across every manifest that carries one.

Manifests: .claude-plugin/plugin.json and marketplace.json (Claude Code), and the root
plugin.json (Agent Plugins format -- read by Codex, Copilot, Cursor, VS Code). Codex keys
its install cache by this version, so letting the root manifest drift means Codex users
never see a new version.

Used by .github/workflows/version-bump.yml after a PR merges to main. Not meant to be
run against a dirty working tree -- reads the current version from
.claude-plugin/plugin.json, refuses to bump if the manifests already disagree, computes
the next semver value, and writes it to all of them.

  --check   only verify the manifests agree (used in CI); exits 1 if they don't
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
ROOT_PLUGIN_JSON = REPO_ROOT / "plugin.json"


def bump(version: str, kind: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown bump kind: {kind}")


def versions() -> dict:
    plugin = json.loads(PLUGIN_JSON.read_text())
    marketplace = json.loads(MARKETPLACE_JSON.read_text())
    found = {
        ".claude-plugin/plugin.json": plugin["version"],
        ".claude-plugin/marketplace.json metadata": marketplace["metadata"]["version"],
        "plugin.json": json.loads(ROOT_PLUGIN_JSON.read_text())["version"],
    }
    for entry in marketplace.get("plugins", []):
        found[f".claude-plugin/marketplace.json plugins[{entry['name']}]"] = entry["version"]
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bump", choices=["major", "minor", "patch"])
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()

    found = versions()
    if len(set(found.values())) != 1:
        print("Manifest versions disagree:", file=sys.stderr)
        for where, v in found.items():
            print(f"  {v:10} {where}", file=sys.stderr)
        sys.exit(1)
    if args.check:
        print(f"All manifests at {next(iter(found.values()))}")
        return

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

    root_plugin = json.loads(ROOT_PLUGIN_JSON.read_text())
    root_plugin["version"] = new_version
    ROOT_PLUGIN_JSON.write_text(json.dumps(root_plugin, indent=2, ensure_ascii=False) + "\n")

    print(f"{current_version} -> {new_version}", file=sys.stderr)
    print(new_version)


if __name__ == "__main__":
    main()
