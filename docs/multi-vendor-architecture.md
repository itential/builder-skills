# Multi-Vendor Agent Architecture

One set of skills, written once, installed complete in every harness.

```text
 skills/<name>/SKILL.md          shared library (edit once)
 skills/<name>/custom/           helpers/  spec-files/  environments/  AGENTS.md
 skills/<name>/agents/                 │
 skills/<name>/scripts/                │  CI bundles what each skill references
        │                              ▼
        └──────────────► skills/<name>/assets/        (generated)
                                │
                                │  CI copies each complete skill folder
                                ▼
          .claude/skills/     .agents/skills/        .github/skills/   (generated)
           Claude Code       Codex, Cursor,          GitHub Copilot
                             gh skill installs
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
| `customizations/{org,team,developer}/` | Repo-wide layer for an Itential-internal team's own clone |
| Manifests | `.claude-plugin/` (Claude Code), root `plugin.json` (Agent Plugins v1.0.0 — Codex, Copilot, VS Code; Codex display fields under `extensions["com.openai"]`), `.cursor-plugin/` (Cursor Team Marketplace), `.agents/plugins/marketplace.json` (Codex marketplace) |

## What is generated — never edit by hand

| Path | Built from |
|---|---|
| `skills/<name>/assets/` | The library files that skill references, keeping library paths (`assets/helpers/create/…`, `assets/spec-files/…`, `assets/environments/…`, `assets/AGENTS.md`) |
| `.claude/skills/`, `.agents/skills/`, `.github/skills/` | Real copies (not symlinks) of each complete `skills/<name>/` folder |

## Why skills are self-contained

Only Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}`; other harnesses would show it to the model as literal text, and `gh skill install` copies only skill folders. So skills never point outside their own folder. Every file a skill needs is referenced by a path relative to the skill folder (the Agent Skills convention) and physically present in it. Verified live: Codex and Copilot, run from an unrelated folder, open a skill's bundled file from inside its installed plugin.

`scripts/bundle_skill_assets.py` reads each `SKILL.md`, bundles every `assets/…` library path it mentions (plus `bundle-map.json` entries), copies only git-tracked files, and fails if any skill-relative path in a `SKILL.md` doesn't exist inside that skill's folder afterwards.

## Workflow

Edit `skills/` or the shared library and push. `.github/workflows/generate-mirrors.yml` bundles `skills/*/assets` and regenerates the three copies on every push to `main` that touches them — pushing directly, or opening a `chore: regenerate vendor mirrors` PR where `main` is branch-protected (as it is on `itential/builder-skills`). Its own commit only touches generated paths, which the trigger excludes, so it can't loop. Nobody runs the conversion by hand; to preview locally: `scripts/check-generated.sh`.

PR checks:
- **Generated Copies Untouched** (`scripts/check-mirror-edits.sh`) — fails a PR that edits generated files (the three copies or `skills/*/assets`) by hand.
- **Manifest Versions** (`scripts/bump_version.py --check`) — fails if any plugin manifest disagrees on version. The version bump updates all of them.
- **Custom folders empty** (`scripts/check-custom-empty.sh`) — Itential's repo never ships customer content.

## Install & invoke

| Harness | Install | Invoke |
|---|---|---|
| Claude Code | `/plugin install itential-builder@itential-builder` | `/itential-builder:skill-name` |
| Codex CLI | `codex plugin add itential-builder@itential-builder` | `$itential-builder:skill-name`, `/skills`, or auto-route |
| GitHub Copilot CLI | `copilot plugin install itential-builder@itential-builder` | `/skill-name` or auto-route |
| Copilot in VS Code | **Chat: Install Plugin From Source** | `/skill-name` or auto-route |
| Cursor | `gh skill install … --agent cursor --all`, or Team Marketplace | `/skill-name` |

Every marketplace entry points at `"./"` or `"."` — the repo the marketplace was added from — so installing from an org's own copy installs that copy, not Itential's. Exact commands: `docs/vendor-install.md`.

## Customization

Each skill's `custom/{org,team,dev}/` is read by the skill before it acts; in `itential/builder-skills` those folders hold only `.gitkeep` placeholders (`guard-custom.yml`), and `custom/dev/` is gitignored. A customer's committed `custom/org` and `custom/team` files travel with the skill into every copy and every install. The repo-wide `customizations/` layer and the combined precedence are in `AGENTS.md` → Customization Layers. Full guide: **`docs/customization.md`**.
