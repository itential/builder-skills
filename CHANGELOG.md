# Changelog

Versions correspond to the plugin manifest version in `.claude-plugin/plugin.json`
— what `/plugin update` installs.

## Unreleased

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
