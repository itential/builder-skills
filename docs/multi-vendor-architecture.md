# Multi-Vendor Agent Architecture

This repository uses a source/generated model:

```text
AGENTS.md + skills/ + helpers/ + spec-files/
        |
        v
generated vendor UX
```

## Canonical Sources

Edit these files directly:

| Path | Purpose |
|---|---|
| `AGENTS.md` | AAIF-compatible repo entrypoint and skill router |
| `skills/*/SKILL.md` | Canonical domain skill content |
| `docs/constitution.md` | Repo-native governance and quality gates |
| `helpers/` | JSON scaffolds and reusable build templates |
| `spec-files/` | Reusable customer spec templates |
| `docs/` | Human-facing documentation |
| `customizations/org/` | Organization-wide standards |
| `customizations/team/` | Team-specific standards |
| `customizations/developer/` | Local developer preferences, ignored except examples |

## Customization Priority

Customization guidance is optional and layered:

| Priority | Layer | Path |
|---:|---|---|
| 1 | Developer local | `customizations/developer/` |
| 2 | Team | `customizations/team/` |
| 3 | Organization | `customizations/org/` |
| 4 | Core | `AGENTS.md`, `skills/`, `docs/constitution.md` |

Higher-priority layers can narrow style, naming, defaults, and review expectations. They cannot violate `docs/constitution.md` or fork vendor behavior.

## Generated Vendor Artifacts

Do not edit these directly:

| Path | Vendor / Purpose |
|---|---|
| `.claude/skills/` | Claude native skill mirror |
| `.claude/commands/` | Claude slash-command wrappers |
| `.github/copilot-instructions.md` | GitHub Copilot repo instruction adapter |
| `.github/prompts/` | GitHub Copilot reusable prompt wrappers |
| `.cursor/rules/` | Cursor routing rules |
| `codex/itential-builder-skills/` | Single installable Codex meta-skill bundle |

Generated wrappers stay thin. They point back to canonical skill content instead of copying routing logic by hand.

## Workflow

After editing a canonical skill or adding a new skill:

```bash
scripts/generate-vendor-wrappers.sh
scripts/check-generated.sh
```

`scripts/generate-vendor-wrappers.sh` updates all vendor UX surfaces from `skills/`.

`scripts/check-generated.sh` reruns generation and fails if generated artifacts are stale or untracked. Use it in CI before release.

## Design Principle

Vendors get different UX surfaces, but the operational knowledge does not fork:

| Vendor | UX Surface |
|---|---|
| Claude | Native skills and slash commands |
| Codex | `AGENTS.md` repo-local routing or global `itential-builder-skills` install |
| Cursor | Rules that route skill references to `skills/` |
| GitHub Copilot | Repo instructions and reusable prompt files |

The canonical source of truth remains `AGENTS.md` plus `skills/`.
