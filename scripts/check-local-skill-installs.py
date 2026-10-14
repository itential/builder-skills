#!/usr/bin/env python3
"""Smoke-test gh skill's four local install targets in disposable repositories.

Requires gh >= 2.90. Copies local files only; does not launch coding harnesses,
change user-level installs, or contact an Itential platform.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ("claude-code", "codex", "github-copilot", "cursor")
CHANGED_SKILLS = ("flowagent", "flowagent-to-spec", "builder-agent", "solution-arch-agent", "qa-agent")


def check():
    expected = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
    with tempfile.TemporaryDirectory(prefix="builder-skill-installs-") as temporary:
        for agent in AGENTS:
            target = Path(temporary) / agent
            target.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=target, check=True)
            result = subprocess.run(
                ["gh", "skill", "install", str(ROOT), "--from-local", "--all",
                 "--agent", agent, "--scope", "project"],
                cwd=target, text=True, capture_output=True, check=True,
            )
            installed = {p.parent.name: p.parent for p in target.rglob("SKILL.md")}
            if set(installed) != expected:
                raise RuntimeError(f"{agent}: installed skill inventory differs: {result.stdout}")
            for name in CHANGED_SKILLS:
                source, destination = ROOT / "skills" / name, installed[name]
                # gh reserializes frontmatter and adds local-path metadata. It
                # also removes the blank line immediately after frontmatter.
                def body(folder):
                    return (folder / "SKILL.md").read_text().split("---", 2)[2].lstrip("\n")
                if body(source) != body(destination):
                    raise RuntimeError(f"{agent}/{name}: skill instructions changed during install")
                for file in (source / "assets").rglob("*"):
                    if file.is_file() and file.read_bytes() != (destination / file.relative_to(source)).read_bytes():
                        raise RuntimeError(f"{agent}/{name}: bundled asset differs: {file}")
            print(f"{agent}: {len(expected)} skills installed; changed instructions and assets match (no harness execution)")


if __name__ == "__main__":
    check()
