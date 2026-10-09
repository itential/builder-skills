# Changelog

Versions correspond to the plugin manifest version (`plugin.json`) and the GitHub
release tag — what every tool's update installs.

## Unreleased

- Fixed the `iag` Ansible examples: JSON playbook output is set with `stdout_callback` in `ansible.cfg` — `ANSIBLE_STDOUT_CALLBACK` in `runtime.env` is ignored by Gateway5. Added gateway gotchas found on a live Gateway5: importing services through Gateway Manager, waiting for the new service id after a `force` import, getting Ansible onto the gateway via `requirements.txt`, and how `runService` hands Inventory Manager nodes to a service on stdin
- Added broker-action inventories to `itential-inventory`: `createBrokerActions`, the `itential_*` attribute convention, and how Gateway4 inventory variables map to it

- Fixed `scripts/use_case_init.py` writing an `.auth.json` without `platform_url`/`auth_method`, which made solution-arch-agent's `pull-platform-data.py` crash; it now also starts `use-case-memory.md` from the template
- Fixed solution-arch-agent's platform pull recording only the first page of workflows (100) and devices (1,000) — it now fetches all of them, so reuse searches see every workflow
- Fixed skills disagreeing on where a use case lives: `{use-case}` is `use-cases/<use-case-name>/` everywhere
- Fixed `explore` treating the `environments/*.env` templates as real credentials, and `gateway4-to-gateway5` naming the username/password mode `login` instead of `password`

- Removed the repo-wide `customizations/` folder: each skill's own `custom/org`, `custom/team` and `custom/dev` folders are the one place for an organization's rules, and they travel with every install. Move any rules from `customizations/` into the matching skills' `custom/` folders
- Removed `scripts/use-skill`; install the plugin or load a clone with `claude --plugin-dir .` instead

## 2.0.0

- Added native installs for Codex CLI, GitHub Copilot (CLI and VS Code) and Cursor alongside Claude Code, each reading the same `skills/` folder — no per-tool copies in the repo. Working from a clone, load it as a plugin (e.g. `claude --plugin-dir .`); skills are invoked with the plugin prefix (`/itential-builder:spec-agent`)
- Added per-skill `custom/org`, `custom/team` and `custom/dev` folders for an organization's own rules, kept separate from Itential's content so updates never overwrite them
- Changed every skill to be self-contained: the templates, spec library and reference files it uses are bundled into its own `assets/` folder
- Removed the automatic version-bump and mirror-regeneration workflows; versions are bumped by hand when releasing, and the release tag always matches the plugin version

## 1.6.5

- Added the full six-stage delivery lifecycle skills: `spec-agent`, `solution-arch-agent`, `builder-agent`, `qa-agent`, plus `flowagent-to-spec` and `project-to-spec` for productionizing an existing FlowAgent or reverse-engineering an undocumented project (#16, #78, #79)
- Added platform-domain skills: `itential-json-forms`, `gateway4-to-gateway5` migration readiness assessment, and org/team/dev customization layers so a foundational skill can be overridden without editing it directly (#43, #81, #94)
- Added auto-versioning CI: branch-name-based PR labeling, Release Drafter changelog drafting, and a dumb always-patch version-bump workflow that opens its own PR on every merge (#97, #103, #105)
- Added cross-tool Agent Skills compatibility — `.agents/skills` symlinks and a Codex-native plugin manifest so Copilot, Codex CLI, and Cursor can use this repo's skills alongside Claude Code (#109)
- Added dozens of helper JSON templates and real, importable vendor/platform asset exports (ops manager, LCM, config management, data manipulation, vendor integrations), replacing hand-crafted example snippets (#7, #12, #28, #76)
- Fixed numerous `builder-agent` platform gotchas found via live builds: `incomingRefs` caching, `ViewHTML`/manual-task quirks, workflow delete/rename, project membership patching after create/import, childJob variable behavior on P6.4.0, and canvas-layout/task-ID verification (#33, #34, #64, #67, #70, #74, #102, #106)
- Fixed `PATCH /projects` silently ignoring the `accessControl` body — use the `members` array instead (#64)
- Fixed Golden Config guidance to prohibit wiring any Configuration Manager remediation task, since Golden Config only detects and reports drift, never applies fixes to a device (#69)
- Fixed two commits that had been pushed directly to `main`, bypassing branch protection, by reverting them (#77)
- Fixed `version-bump.yml`: moved off a direct push to `main` (rejected by branch protection) to opening its own PR, then simplified to an unconditional patch bump with no label-based categorization (#103, #105)
- Changed the JSON Forms skill name (`app-json_forms` → `itential-json-forms`) and standardized Gateway 4 → Gateway 5 terminology repo-wide (#80, #86)
