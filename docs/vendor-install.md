# Vendor Install And Command Guide

This repository is AAIF-aligned around `AGENTS.md` and canonical skill content in `skills/`.

Different AI coding tools expose different command systems. The repository provides thin vendor wrappers where useful, but `AGENTS.md` and `skills/` remain the source of truth.

## Claude Code

Claude gets the richest command experience.

Install through the Claude plugin flow:

```text
/plugin marketplace add itential/builder-skills
/plugin install itential-builder@itential-builder
```

Use slash commands:

```text
/itential-builder:spec-agent
/itential-builder:builder-agent
```

For local development, generated command wrappers live in `.claude/commands/` and canonical skill content is mirrored into `.claude/skills/`.

## Codex

Codex supports two usage modes.

### Repo-Local Use

Codex uses `AGENTS.md` directly. No separate Codex skill install is required when working inside this repository.

Open the repository in Codex and ask for the skill by name:

```text
Use builder-agent to implement the approved solution design.
```

Codex should resolve that through `AGENTS.md` to:

```text
skills/builder-agent/SKILL.md
```

For a command-like terminal helper:

```bash
scripts/use-skill builder-agent
```

### Global Codex Skill Install

For use outside this repository, install the bundled Codex meta-skill with Skill Installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo itential/builder-skills \
  --path codex/itential-builder-skills
```

After installing, restart Codex. The skill appears as:

```text
itential-builder-skills
```

The Codex meta-skill bundles the domain references under `codex/itential-builder-skills/references/` so users do not need to install every domain skill separately.

## Cursor

Cursor reads `.cursor/rules/*.mdc` and `AGENTS.md`.

Use natural language or slash-style text:

```text
Use /solution-arch-agent to run feasibility.
```

Cursor rules point back to `AGENTS.md` and `skills/{skill-name}/SKILL.md`.

## GitHub Copilot

Copilot reads `.github/copilot-instructions.md`. Reusable prompt wrappers are generated in `.github/prompts/*.prompt.md`.

Use the matching prompt file from Copilot Chat, or ask in natural language:

```text
Use the builder-agent prompt to build this approved design.
```

## Regenerating Wrappers

After adding or renaming a skill:

```bash
scripts/generate-vendor-wrappers.sh
scripts/check-generated.sh
```

Wrappers must stay thin. Do not copy full skill content into vendor command or prompt files.

For the source/generated architecture, see `docs/multi-vendor-architecture.md`.
