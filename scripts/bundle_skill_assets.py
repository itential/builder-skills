#!/usr/bin/env python3
"""Bundle shared-library files into each skill, so every skill is self-contained.

The shared library is edited in one place: helpers/, spec-files/, environments/ and
AGENTS.md at the repo root. A skill refers to a library file by a path relative to its
own folder -- `assets/helpers/create/create-workflow.json`, `assets/spec-files/...`,
`assets/environments/...`, `assets/AGENTS.md` -- and this script copies exactly those
files into `skills/<name>/assets/`, keeping the library's layout. Every installer
(plugin installs, `gh skill install`, clones) then gets a complete skill folder.

`skills/<name>/assets/` is generated -- never edit it by hand.

What gets bundled for a skill:
  - every `assets/<library path>` mentioned in its SKILL.md (a path ending in `/`,
    or one that is a directory, bundles that whole directory -- except a bare library
    root like `assets/helpers/`, which is too broad to infer from prose);
  - plus any extra library paths listed for it in scripts/bundle-map.json (for skills
    that browse or list a whole directory, e.g. a library root).
Only files tracked by git are bundled.

Fails if a SKILL.md mentions an `assets/...` library path that doesn't exist (placeholder
paths containing <...>, {...}, * or ALL_CAPS names are skipped).

Run by scripts/generate-vendor-wrappers.sh; usage: bundle_skill_assets.py [--list]
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
LIBRARY = {"helpers", "spec-files", "environments"}
REF = re.compile(r"assets/((?:helpers|spec-files|environments)/[A-Za-z0-9_.\-/]*|AGENTS\.md)")
PLACEHOLDER = re.compile(r"[<{*]|(^|/)[A-Z][A-Z0-9_]+(\.|/|$)")


def wanted(skill_dir: Path, extras: list[str]) -> tuple[set[str], list[str]]:
    text = (skill_dir / "SKILL.md").read_text()
    paths, missing = set(extras), []
    for m in REF.finditer(text):
        rel = m.group(1).rstrip(".")  # trailing sentence period
        tail = text[m.end():m.end() + 1]
        wildcard = bool(tail) and tail in "<{*"
        if wildcard:  # e.g. assets/environments/*.env or assets/.../lcm/<model>.json -> that directory
            rel = rel.rsplit("/", 1)[0] + "/"
        if rel != "AGENTS.md" and (PLACEHOLDER.search(rel) or (rel.rstrip("/") in LIBRARY and not wildcard)):
            continue
        if not (ROOT / rel).exists():
            missing.append(rel)
            continue
        paths.add(rel)
    return paths, missing


def main() -> None:
    extras = json.loads((ROOT / "scripts" / "bundle-map.json").read_text())
    unknown = set(extras) - {p.name for p in SKILLS.iterdir()}
    if unknown:
        sys.exit(f"bundle-map.json names skills that don't exist: {sorted(unknown)}")

    tracked = set(subprocess.run(["git", "-C", str(ROOT), "ls-files", *sorted(LIBRARY), "AGENTS.md"],
                                 capture_output=True, text=True, check=True).stdout.split())
    problems, summary = [], []
    for skill_dir in sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()):
        paths, missing = wanted(skill_dir, extras.get(skill_dir.name, []))
        problems += [f"{skill_dir.name}: SKILL.md mentions assets/{m} but {m} doesn't exist" for m in missing]

        out = skill_dir / "assets"
        shutil.rmtree(out, ignore_errors=True)
        count = 0
        for rel in sorted(paths):
            prefix = rel.rstrip("/") + "/"
            files = [t for t in tracked if t == rel or t.startswith(prefix)]
            if not files:
                problems.append(f"{skill_dir.name}: assets/{rel} matches no tracked library file")
            for f in files:
                dst = out / f
                if dst.exists():
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / f, dst); count += 1
        summary.append(f"{skill_dir.name}: {count} file(s)")

        # Every skill-relative file the skill mentions must now exist inside its own folder.
        text = (skill_dir / "SKILL.md").read_text()
        for m in re.finditer(r"(?<![\w/.-])((?:assets|scripts)/[A-Za-z0-9_.\-/]*[A-Za-z0-9_\-])", text):
            rel = m.group(1)
            nxt = text[m.end():m.end() + 1]
            if (nxt and nxt in "<{*") or PLACEHOLDER.search(rel.replace("AGENTS.md", "")):
                continue
            if rel.rstrip("/").split("/")[-1] in LIBRARY or rel in ("assets", "scripts"):
                continue
            if rel.startswith("scripts/") and not rel.endswith((".py", ".sh")):
                continue  # e.g. a customer repo's scripts/requirements.txt, not a file in this skill
            if not (skill_dir / rel).exists():
                problems.append(f"{skill_dir.name}: SKILL.md mentions {rel} but it isn't in the skill folder")

    if "--list" in sys.argv:
        print("\n".join(summary))
    if problems:
        sys.exit("Broken bundled-file references:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    main()
