#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="${ROOT_DIR}/skills"
CLAUDE_SKILLS_DIR="${ROOT_DIR}/.claude/skills"
GENERATED_NOTICE="Generated from canonical sources. Do not edit directly. Run scripts/generate-vendor-wrappers.sh."

if [[ ! -d "${SKILLS_DIR}" ]]; then
  echo "ERROR: skills directory not found: ${SKILLS_DIR}" >&2
  exit 1
fi

# .claude/skills is a mirror of skills/, one symlink per skill directory -- not a copy.
# skills/ is the single canonical source (per the Agent Plugins spec's fixed `skills/`
# discovery location); a copy here would be a second source of truth that can drift,
# and previously coexisted with .claude/commands/*.md registering the same skill name
# a second time under Claude Code's separate custom-commands mechanism, which Claude
# Code surfaced as duplicate entries for the same skill. Symlinks make that impossible:
# there is exactly one real SKILL.md per skill, referenced from wherever a client needs it.
rm -rf "${CLAUDE_SKILLS_DIR}"
mkdir -p "${CLAUDE_SKILLS_DIR}"
for skill_dir in "${SKILLS_DIR}"/*; do
  [[ -d "${skill_dir}" ]] || continue
  [[ -f "${skill_dir}/SKILL.md" ]] || continue
  skill_name="$(basename "${skill_dir}")"
  ln -s "../../skills/${skill_name}" "${CLAUDE_SKILLS_DIR}/${skill_name}"
done

mkdir -p "${ROOT_DIR}/.github/prompts"
mkdir -p "${ROOT_DIR}/.cursor/rules"
mkdir -p "${ROOT_DIR}/codex/itential-builder-skills/references"

rm -f "${ROOT_DIR}/.github/prompts/"*.prompt.md
rm -f "${ROOT_DIR}/.cursor/rules/itential-skills.mdc"
rm -f "${ROOT_DIR}/codex/itential-builder-skills/references/"*.md

for skill_dir in "${SKILLS_DIR}"/*; do
  [[ -d "${skill_dir}" ]] || continue
  [[ -f "${skill_dir}/SKILL.md" ]] || continue

  skill_name="$(basename "${skill_dir}")"
  title="$(printf '%s' "${skill_name}" | tr '-' ' ')"

  cat > "${ROOT_DIR}/.github/prompts/${skill_name}.prompt.md" <<EOF
<!-- ${GENERATED_NOTICE} -->

---
mode: agent
description: Use the Itential ${title} skill
---

Read \`AGENTS.md\`, then load \`skills/${skill_name}/SKILL.md\`.
Follow that skill for the current user request.
EOF

  # Thin pointer, not a content copy -- same non-duplication rule as the Cursor/Copilot
  # generators below. A prior version of this script `cp`'d the full SKILL.md here,
  # creating a third full copy of the same content (after skills/ and .claude/skills/)
  # that could silently drift from the canonical source.
  cat > "${ROOT_DIR}/codex/itential-builder-skills/references/${skill_name}.md" <<EOF
<!-- ${GENERATED_NOTICE} -->

# ${title}

Use the \`/${skill_name}\` skill.

Read \`AGENTS.md\`, then load \`skills/${skill_name}/SKILL.md\`.
Follow that skill for the current user request.
EOF
done

cat > "${ROOT_DIR}/.github/copilot-instructions.md" <<'EOF'
<!-- Generated from canonical sources. Do not edit directly. Run scripts/generate-vendor-wrappers.sh. -->

# Copilot Instructions

Read `AGENTS.md` first. It is the canonical cross-vendor agent guide for this repository.

When `AGENTS.md` routes work to a skill such as `/builder-agent`, read the matching `skills/builder-agent/SKILL.md` file before acting in that domain.
EOF

cat > "${ROOT_DIR}/.cursor/rules/itential-skills.mdc" <<'EOF'
<!-- Generated from canonical sources. Do not edit directly. Run scripts/generate-vendor-wrappers.sh. -->

---
description: Route Itential skill requests to canonical skill guides
alwaysApply: true
---

Read `AGENTS.md` first. It is the canonical cross-vendor agent guide for this repository.

Skill references use the form `/skill-name`. If a user invokes or mentions a skill such as `/builder-agent`, read `skills/builder-agent/SKILL.md` before acting in that domain.

Do not duplicate or reinterpret skill instructions in Cursor rules. The canonical skill content is always under `skills/{skill-name}/SKILL.md`.
EOF

cat > "${ROOT_DIR}/codex/itential-builder-skills/SKILL.md" <<'EOF'
---
name: itential-builder-skills
description: Use for Itential Platform automation delivery, discovery, design, build, IAG services, FlowAI agents, MOP command templates, devices, golden config, inventory, and LCM.
metadata:
  short-description: Itential Platform automation lifecycle and domain skills
---

# Itential Builder Skills

Generated from canonical sources. Do not edit directly. Run `scripts/generate-vendor-wrappers.sh`.

Use this skill for Itential Platform work: requirements, feasibility, solution design, build, as-built documentation, platform exploration, and domain-specific automation.

This is a Codex distributable meta-skill. It bundles the same domain skill content used by the repository-local `AGENTS.md` router.

## Routing

Load the referenced file before acting in that domain:

| Intent | Reference |
|---|---|
| Explore a platform, authenticate, discover assets, or work freestyle | `references/explore.md` |
| Start a new delivery from requirements or create a customer spec | `references/spec-agent.md` |
| Assess feasibility or produce a solution design | `references/solution-arch-agent.md` |
| Build approved assets, test components, or produce as-built docs | `references/builder-agent.md` |
| Document existing global platform assets by use case | `references/documentation.md` |
| Convert an existing project into spec/design docs | `references/project-to-spec.md` |
| Convert a FlowAI agent into a deterministic workflow spec | `references/flowagent-to-spec.md` |
| Build or manage IAG services | `references/iag.md` |
| Build or manage FlowAI agents, providers, tools, and missions | `references/flowagent.md` |
| Build MOP command or analytic templates | `references/itential-mop.md` |
| Work with devices, backups, diffs, or device groups | `references/itential-devices.md` |
| Build golden config trees, compliance, grading, or remediation | `references/itential-golden-config.md` |
| Work with device inventory nodes, actions, and tags | `references/itential-inventory.md` |
| Build LCM resource models, instances, or lifecycle actions | `references/itential-lcm.md` |
| Build JSON forms (static-enum, REST-bound, cascading dropdowns) | `references/itential-json-forms.md` |
| Run acceptance testing and produce the as-built record after a build | `references/qa-agent.md` |

## Operating Rules

1. Read the matching reference file before acting.
2. If working inside this repository, also read `AGENTS.md`.
3. If customization files exist, apply them in priority order: `customizations/developer/`, `customizations/team/`, `customizations/org/`, then core.
4. Customizations may narrow style, naming, defaults, and review expectations, but must not violate `docs/constitution.md`.
5. Never guess Itential API endpoints, request bodies, task names, or response shapes.
6. Use local platform files first when present: `openapi.json`, `tasks.json`, `task-schemas.json`, `apps.json`, `adapters.json`, and `platform-summary.json`.
7. Use helper JSON templates from `helpers/` when creating assets in the repository.
8. Keep delivery stage gates intact: Requirements, Feasibility, Design, Build, As-Built.
EOF

echo "Generated vendor wrappers for skills in ${SKILLS_DIR}"
