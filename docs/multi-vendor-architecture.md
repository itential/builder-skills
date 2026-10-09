# Multi-Vendor Agent Architecture

One folder of skills, read directly by every harness's installer — no per-tool copies, no post-merge bots.

```text
 helpers/  spec-files/  environments/  AGENTS.md      ← shared library (edit once)
        │
        │  scripts/check-generated.sh bundles what each skill references
        ▼
 skills/<name>/SKILL.md          ← the skill (Agent Skills format)
 skills/<name>/assets/           ← bundled library files (generated, committed)
 skills/<name>/scripts/          ← scripts owned by one skill
 skills/<name>/custom/           ← customer rules (empty here)
 skills/<name>/agents/           ← Codex display metadata
        │
        ├── Claude Code   .claude-plugin/plugin.json + marketplace.json   → reads skills/
        ├── Codex         plugin.json + .agents/plugins/marketplace.json  → reads skills/
        ├── Copilot / VS Code   plugin.json (Agent Plugins v1.0.0)        → reads skills/
        ├── Cursor        .cursor-plugin/  or  gh skill install           → reads skills/
        └── any tool      gh skill install / npx skills add               → copies skills/<name>/
```

## What people edit

| Path | Purpose |
|---|---|
| `skills/<name>/SKILL.md` | The skill itself (Agent Skills format) |
| `skills/<name>/scripts/` | Scripts owned by one skill (e.g. solution-arch-agent's `pull-platform-data.py`) |
| `skills/<name>/agents/openai.yaml` | Codex display metadata for the skill (name, short description, starter prompt) |
| `skills/<name>/custom/{org,team,dev}/` | Customer customizations — empty in Itential's repo (see `docs/customization.md`) |
| `helpers/`, `spec-files/`, `environments/`, `AGENTS.md` | **Shared library** — templates, the spec library, `.env` templates, platform rules. Edited once, bundled into every skill that uses them |
| `scripts/bundle-map.json` | Whole-directory bundles a skill needs beyond the files it names (builder-agent → all of `helpers/`, spec-agent → all of `spec-files/`) |
| Manifests | `.claude-plugin/` (Claude Code), root `plugin.json` (Agent Plugins v1.0.0 — Codex, Copilot, VS Code; Codex display fields under `extensions["com.openai"]`), `.cursor-plugin/` (Cursor Team Marketplace), `.agents/plugins/marketplace.json` (Codex marketplace). Every marketplace entry points at `"./"` / `"."`, so installing from an org's own copy installs that copy. |

`skills/<name>/assets/` is generated — never edit it by hand. After changing the library or a skill's references, run `scripts/check-generated.sh` and commit what it changes.

## Why skills are self-contained

Only Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}`; other harnesses would show it to the model as literal text, and `gh skill install` copies only skill folders. So skills never point outside their own folder. Every file a skill needs is referenced by a path relative to the skill folder (the Agent Skills convention) and physically present in it.

`scripts/bundle_skill_assets.py` reads each `SKILL.md`, bundles every `assets/…` library path it mentions (plus `bundle-map.json` entries), copies only git-tracked files, and fails if any skill-relative path in a `SKILL.md` doesn't exist inside that skill's folder afterwards.

## Working from a clone

There are no `.claude/skills`, `.agents/skills` or `.github/skills` copies — load the clone as a plugin instead (`claude --plugin-dir .`, or a local marketplace for Codex and Copilot). The skills then work in any folder, including `use-cases/`. Commands per tool: `docs/vendor-install.md` → "Working from a clone".

## CI

PR checks:

| Check | Required | Fails when |
|---|---|---|
| Skills Valid (`scripts/check-generated.sh`) | Yes | a skill references a file that isn't in its folder, bundled `assets/` are out of date, or a skill's `name` doesn't match its folder / its `description` is missing or over 1024 characters (`scripts/check-skills.py`) |
| Manifest Versions (`scripts/bump_version.py --check`) | Yes | the plugin manifests disagree on version |
| Custom folders empty (`scripts/check-custom-empty.sh`) | Yes | a PR adds real content under `skills/*/custom/` |
| Branch Naming | No — reports only | branch isn't `feature|fix|refactor|docs|chore/<kebab-case>` (the prefix sets the PR label) |

On `main`: **Release Drafter** keeps a draft release named after the version in `plugin.json`, with notes grouped by PR label (only in `itential/builder-skills`). There are no bots that open PRs. Versions are bumped by hand when releasing — see `CONTRIBUTING.md` → Releasing.

## Install & invoke

| Harness | Install | Invoke |
|---|---|---|
| Claude Code | `/plugin install itential-builder@itential-builder` | `/itential-builder:skill-name` |
| Codex CLI | `codex plugin add itential-builder@itential-builder` | `$itential-builder:skill-name`, `/skills`, or auto-route |
| GitHub Copilot CLI | `copilot plugin install itential-builder@itential-builder` | `/skill-name` or auto-route |
| Copilot in VS Code | **Chat: Install Plugin From Source** | `/skill-name` or auto-route |
| Cursor | `gh skill install … --agent cursor --all`, or Team Marketplace | `/skill-name` |

Exact commands, including working from a clone: `docs/vendor-install.md`.

## Customization

Each skill's `custom/{org,team,dev}/` is read by the skill before it acts; in `itential/builder-skills` those folders hold only `.gitkeep` placeholders (`guard-custom.yml`), and `custom/dev/` is gitignored. A customer's committed `custom/org` and `custom/team` files travel with the skill into every install. Precedence is in `AGENTS.md` → Customization Layers. Full guide: **`docs/customization.md`**.
