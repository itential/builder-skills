# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries here track the GitHub Release version (see "Pull Request Labels and
Versioning" in `CONTRIBUTING.md`) — not the plugin manifest's dumb per-merge
patch counter in `.claude-plugin/plugin.json`. The two are expected to drift.

## [Unreleased]

No GitHub Release has ever been published for this repo (Release Drafter's
only draft, `v0.1.0`, was never cut) — so everything below is a retroactive,
high-level summary of merged work to date, not a single release's worth of
changes. Going forward, new entries land here per-PR as described in
`CONTRIBUTING.md`; purely internal docs/chore changes (`skip-changelog`) are
intentionally omitted, matching Release Drafter's own exclusion rule.

### Added
- Full six-stage delivery lifecycle skills: `spec-agent`, `solution-arch-agent`,
  `builder-agent`, `qa-agent`, plus `flowagent-to-spec` and `project-to-spec`
  for productionizing an existing FlowAgent or reverse-engineering an
  undocumented project (#16, #78, #79)
- Platform-domain skills: `itential-json-forms`, `gateway4-to-gateway5`
  migration readiness assessment, and org/team/dev customization layers so
  a foundational skill can be overridden without editing it directly (#43,
  #81, #94)
- Auto-versioning CI: branch-name-based PR labeling, Release Drafter changelog
  drafting, and a dumb always-patch version-bump workflow that opens its own
  PR on every merge (#97, #103, #105)
- Cross-tool Agent Skills compatibility — `.agents/skills` symlinks and a
  Codex-native plugin manifest so Copilot, Codex CLI, and Cursor can use this
  repo's skills alongside Claude Code (#109)
- Dozens of helper JSON templates and real, importable vendor/platform asset
  exports (ops manager, LCM, config management, data manipulation, vendor
  integrations) replacing hand-crafted example snippets (#7, #12, #28, #76)

### Fixed
- Numerous `builder-agent` platform gotchas found via live builds: `incomingRefs`
  caching, `ViewHTML`/manual-task quirks, workflow delete/rename, project
  membership patching after create/import, childJob variable behavior on
  P6.4.0, and canvas-layout/task-ID verification (#33, #34, #64, #67, #70,
  #74, #102, #106)
- `PATCH /projects` silently ignoring the `accessControl` body — use the
  `members` array instead (#64)
- Golden Config: prohibit wiring any Configuration Manager remediation task,
  since Golden Config only detects and reports drift, never applies fixes to
  a device (#69)
- Reverted two commits that had been pushed directly to `main`, bypassing
  branch protection (#77)
- `version-bump.yml`: moved off a direct push to `main` (rejected by branch
  protection) to opening its own PR, then simplified to an unconditional
  patch bump with no label-based categorization (#103, #105)

### Changed
- Renamed the JSON Forms skill (`app-json_forms` → `itential-json-forms`) and
  standardized Gateway 4 → Gateway 5 terminology repo-wide (#80, #86)
