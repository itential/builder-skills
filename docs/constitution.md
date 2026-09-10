<!--
Version: 1.0.0
Ratified: 2026-04-25
Last Amended: 2026-04-25
-->

# Itential Builder Skills Constitution

This constitution defines the non-negotiable rules for the repository. It is intentionally repo-native and does not require Spec Kit CLI compatibility.

## Principles

### 1. Single Canonical Source

All reusable agent knowledge must be authored in canonical source files before it appears in vendor-specific surfaces. `AGENTS.md` is the repository entrypoint and `skills/*/SKILL.md` is the canonical domain skill source. Generated copies and wrappers must not become independent sources of truth.

### 2. AAIF-Compatible Agent Entry

The repository must remain usable by agents that understand `AGENTS.md` without requiring vendor-specific installation. Skill references such as `/builder-agent` must be resolvable as pointers to `skills/builder-agent/SKILL.md` for agents without native slash-command support.

### 3. Generated Vendor UX

Vendor-specific files must be generated from canonical sources. This includes Claude skills/commands, Copilot prompts, Cursor rules, and the Codex meta-skill bundle. Generated wrappers must stay thin and point to canonical content or bundled references.

### 4. Spec-Driven Delivery Gates

Delivery work must preserve the staged lifecycle: Requirements, Feasibility, Design, Build, and As-Built. Each stage must produce or update an artifact, and build work must not begin until requirements, feasibility, and design are approved or explicitly waived.

### 5. Verified Platform Truth

Agents must verify Itential endpoints, task names, schemas, adapter names, and response shapes from local platform data before acting. `openapi.json`, `tasks.json`, `task-schemas.json`, `apps.json`, `adapters.json`, and `platform-summary.json` are authoritative when present.

### 6. Security And Secret Handling

Credentials, tokens, private keys, and customer secrets must remain in ignored local files or approved secret stores. Generated docs, specs, prompts, and skills must not contain live secrets. Authentication artifacts such as `.env` and `.auth.json` must remain untracked.

### 7. Layered Customization

Organizations, teams, and developers may add customization guidance in `customizations/`. Customizations are layered by priority: developer local, team, organization, then core. Customizations may narrow defaults, style, naming, and review expectations, but must not override this constitution or create vendor-specific forks of canonical skill behavior.

## Governance

Amendments require:

1. Update `docs/constitution.md`.
2. Update impacted docs or generation scripts.
3. Run `scripts/generate-vendor-wrappers.sh`.
4. Run `scripts/check-generated.sh` before release.

Versioning follows semantic versioning:

| Version Bump | Meaning |
|---|---|
| MAJOR | Removes or redefines a principle in a backward-incompatible way |
| MINOR | Adds a new principle, governance section, or required quality gate |
| PATCH | Clarifies wording without changing required behavior |

## Compliance Review

Every PR that changes `AGENTS.md`, `skills/`, `.claude/`, `.github/prompts`, `.cursor/rules`, `codex/`, `customizations/`, or generation scripts must answer:

1. Did canonical source change first?
2. Were vendor artifacts regenerated?
3. Did `scripts/check-generated.sh` pass?
4. Does the change preserve AAIF repo-local behavior?
5. Does the change preserve Claude/Codex/Cursor/Copilot UX expectations?
6. Do customization files respect the priority model and constitution?
7. Are secrets excluded from tracked files?
