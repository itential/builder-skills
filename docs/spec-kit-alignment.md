# Spec Kit Alignment

This repository borrows useful Spec Kit philosophy without adopting Spec Kit CLI compatibility.

## What Is Implemented

| Spec Kit Concept | Repository Mapping |
|---|---|
| Constitution | `docs/constitution.md` |
| Specification | `{use-case}/customer-spec.md` |
| Plan | `{use-case}/feasibility.md` + `{use-case}/solution-design.md` |
| Tasks | Build plan/test plan in `solution-design.md` or a dedicated task list |
| Implementation | `/builder-agent` / `skills/builder-agent/SKILL.md` |
| Project-local overrides | `customizations/developer/`, `customizations/team/`, `customizations/org/` |
| Generated agent UX | `scripts/generate-vendor-wrappers.sh` |

## Why This Is Not A Plain Spec Kit App

Spec Kit is optimized for software feature delivery through `spec.md`, `plan.md`, `tasks.md`, and implementation commands. This repository delivers Itential automation assets through a domain-specific lifecycle:

```text
Requirements -> Feasibility -> Design -> Build -> As-Built
```

The constitution provides governance and quality gates while preserving the existing Itential artifact names. This repo intentionally does not include `.specify/` templates or require `specify` commands.

## Customization Model

Spec Kit supports customization through templates, presets, extensions, and project-local overrides. This repository uses a simpler domain-specific model:

```text
customizations/developer/  highest priority, local and ignored
customizations/team/       tracked team standards
customizations/org/        tracked organization standards
core                       AGENTS.md, skills/, docs/constitution.md
```

This lets organizations and teams bring their own style, naming, policy, and platform defaults without changing canonical skill behavior.

## Required Checks

Before release:

```bash
scripts/generate-vendor-wrappers.sh
scripts/check-generated.sh
```

Before staging changes, verify ignored secret files remain untracked:

```bash
git status --short
```

Do not stage `.env`, `.auth.json`, private keys, tokens, or pulled customer platform data unless explicitly intended and sanitized.
