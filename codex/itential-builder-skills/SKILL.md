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

## Operating Rules

1. Read the matching reference file before acting.
2. If working inside this repository, also read `AGENTS.md`.
3. If customization files exist, apply them in priority order: `customizations/developer/`, `customizations/team/`, `customizations/org/`, then core.
4. Customizations may narrow style, naming, defaults, and review expectations, but must not violate `docs/constitution.md`.
5. Never guess Itential API endpoints, request bodies, task names, or response shapes.
6. Use local platform files first when present: `openapi.json`, `tasks.json`, `task-schemas.json`, `apps.json`, `adapters.json`, and `platform-summary.json`.
7. Use helper JSON templates from `helpers/` when creating assets in the repository.
8. Keep delivery stage gates intact: Requirements, Feasibility, Design, Build, As-Built.
