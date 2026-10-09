#!/usr/bin/env python3
"""Check every skill against the Agent Skills format, so it installs cleanly in every harness.

For each skills/<name>/SKILL.md:
  - it starts with YAML frontmatter that has `name` and `description`;
  - `name` equals the folder name and is kebab-case (max 64 characters);
  - `description` is non-empty and at most 1024 characters;
  - every skill-relative file it mentions (assets/..., scripts/....py|.sh, references/...)
    exists inside the skill's own folder -- installers copy only that folder. Patterns
    such as assets/<name>.json or assets/.../ALL_CAPS_NAME.json are skipped, and so are
    scripts/ paths that aren't .py or .sh (those point into the user's own project).
Also checks that agents/openai.yaml, if present, has an `interface:` block.

Run by the Skills Valid PR check; usage: python3 scripts/check-skills.py
"""
import re
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REF = re.compile(r"(?<![\w/.-])((?:assets|scripts|references)/[A-Za-z0-9_.\-/]*[A-Za-z0-9_\-])")
PLACEHOLDER = re.compile(r"[<{*]|(^|/)[A-Z][A-Z0-9_]+(\.|/|$)")


def frontmatter(text: str) -> dict[str, str] | None:
    """Top-level keys of the frontmatter; folded/indented continuation lines are joined."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            return {k: v.strip().strip("\"'") for k, v in fields.items()}
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            value = m.group(2)
            fields[key] = "" if value in (">", "|", ">-", "|-") else value
        elif key and line.startswith((" ", "\t")):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return None  # no closing ---


def check(skill: Path) -> list[str]:
    problems = []
    text = (skill / "SKILL.md").read_text()
    fm = frontmatter(text)
    if fm is None:
        return ["SKILL.md has no frontmatter block (--- ... ---) at the top"]

    name, desc = fm.get("name", ""), fm.get("description", "")
    if name != skill.name:
        problems.append(f"name '{name}' doesn't match the folder name '{skill.name}'")
    if not NAME.match(skill.name) or len(skill.name) > 64:
        problems.append("folder name must be kebab-case (a-z, 0-9, hyphens), max 64 characters")
    if not desc:
        problems.append("description is missing")
    elif len(desc) > 1024:
        problems.append(f"description is {len(desc)} characters (max 1024)")

    for m in REF.finditer(text):
        rel = m.group(1)
        nxt = text[m.end():m.end() + 1]
        if (nxt and nxt in "<{*") or PLACEHOLDER.search(rel.replace("AGENTS.md", "")):
            continue  # a pattern like assets/<name>.json, not a real file
        if rel.startswith("scripts/") and not rel.endswith((".py", ".sh")):
            continue  # e.g. the user's own scripts/requirements.txt, not a file in this skill
        if not (skill / rel).exists():
            problems.append(f"mentions {rel}, which isn't in the skill folder")

    openai = skill / "agents" / "openai.yaml"
    if openai.exists() and not re.search(r"^interface:", openai.read_text(), re.M):
        problems.append("agents/openai.yaml has no top-level `interface:` block")
    return problems


def main() -> None:
    skills = sorted(p for p in SKILLS.iterdir() if p.is_dir())
    failed = False
    for skill in skills:
        if not (skill / "SKILL.md").is_file():
            print(f"{skill.name}: no SKILL.md"); failed = True
            continue
        for p in check(skill):
            print(f"{skill.name}: {p}"); failed = True
    if failed:
        sys.exit(1)
    print(f"Skills valid: {len(skills)} skill(s) checked.")


if __name__ == "__main__":
    main()
