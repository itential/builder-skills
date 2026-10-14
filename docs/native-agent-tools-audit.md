# Native agent-tool guidance correction

Before this change, `flowagent` rejected native agent delegation and prescribed
workflow orchestration. `flowagent-to-spec` also dismissed real child-session
evidence. Builders can now discover an active `agent:<child-agent-id>` tool,
attach it to a parent, supply the child's schema directly, and inspect the real
child session and result. Workflow orchestration remains an explicit alternative
when capability is unavailable/unverified or the design calls for it.

## Root cause and affected sources

The old guidance inferred lack of support from the absence of a dedicated
delegation/name field in Agent Project Service. That inference overlooked the
existing `tools[].referenceId` mechanism and the Tools Service's `agent` type.
The same mistaken inference appeared in reverse-engineering guidance. Narrow
tool inventories and workflow-only lifecycle language reinforced it. This is a
shared instruction defect; no Codex-specific runtime defect was established.

The whole-repository audit covered canonical skills, generated assets, helpers,
specs/demo templates, evals, manifests, installers, README and installation docs.
The single-agent Linux diagnostics demo's statement that it needs no subagents
is specific to that design and is not an unsupported-capability claim. Existing
single-agent bundle/decorator examples remain valid. Builder, architect and QA
now route native-agent work to a shared reference instead of applying workflow
rules universally. FlowAgent-to-spec retains deterministic conversion only when
that is the user's requested outcome.

## Distribution trace

| Harness / installation | Source and packaging path | Coverage in this PR |
|---|---|---|
| Claude Code plugin / local clone | `.claude-plugin/{plugin,marketplace}.json` → repo root → `skills/` | Shared source, manifests and packaged files checked |
| Codex plugin / local marketplace | `.agents/plugins/marketplace.json` → root `plugin.json` → `skills/`; `agents/openai.yaml` is display metadata | Shared source, manifests and packaged files checked |
| Copilot CLI / VS Code plugin | Marketplace/root `plugin.json` → `skills/` | Shared source, manifests and packaged files checked |
| Cursor Team Marketplace | `.cursor-plugin/{plugin,marketplace}.json` → `./skills/` | Shared source, manifests and packaged files checked |
| `gh skill` / install script (all supported agent choices) | Copies `skills/<name>/` with bundled assets into the selected skill location | Actual local `gh skill install --from-local` smoke tests for all four agent choices; no runtime inference implied |

There are no harness-specific copies of skill instructions. The generator copies
referenced shared-library files into each skill's `assets/`; builder-agent also
gets all of `helpers/` through `scripts/bundle-map.json`. New native-agent assets
must travel with every referencing skill, including individually copied skills.
Installed 2.1.1 caches/pins remain stale until updated; this PR edits no cache.
Read-only inspection also confirmed both faulty statements in the installed
Codex path `~/.codex/plugins/cache/itential-builder/itential-builder/2.1.1/skills/`.

## Platform evidence and limits

Read the maintained [native-agent reference](../helpers/flowagent/native-agent-tools.md)
for official documentation links, discovery, permissions, schema details and the
minimal [example bodies](../helpers/flowagent/native-agent-example.json).

On 2026-10-14, authorized read-only platform inspection confirmed:

- Fresh OpenAPI create/update schemas accept tool references; parent create uses
  `tools`, update uses `addTools`; session start uses `agentDefinitionId`/`inputs`.
- `GET /tools?type=agent` returns a paginated `{data,total,skip,limit}` object;
  an individual active native tool exposed the saved child's `context: string`
  schema and `parentType: agentProject`.
- An existing parent had three native child-agent bindings. Its existing events
  returned `sessionId`, `sessionStatus`, and textual `lastMessage`. Following the
  returned IDs retrieved actual child metadata/history, not invented receipts.
- One child was `COMPLETE` and the outer event `succeeded`, while the child's
  result reported STOPPED because necessary evidence was missing. Thus neither
  completion flag establishes task success. FAILED/CANCELED scenarios in the
  regression fixtures are synthetic variants, not claims of live failure runs.
- An editable child definition returned HTTP 403 after token refresh; the
  documented operable-agent endpoint returned 200. Access failure on one route
  did not establish capability absence. No access changes were made.

Only allowlisted schema fragments and sanitized structural projections are
committed in `tests/fixtures/flowagent/`. IDs, project/agent names, hostnames,
prompts, customer input/result text, and credentials are excluded. Fixture text
is synthetic; observed field names, types and status values are retained.
The example bodies were validated against these schemas, **not executed**.
No registry refresh, agent/session start, demo, device operation, approval,
notification, release or merge forms part of this change.

Official documentation describes Cloud July 2026 and Platform 6.5 support.
The inspected deployment's exact build was not established; API `info.version`
is not a platform version. Older releases, other installations and external A2A
protocol interoperability are untested. Capability must be checked per target.

## Validation

Run the offline regression suite with:

```sh
python3 -m pip install -r tests/requirements.txt
python3 -m unittest discover -s tests -v
scripts/check-generated.sh
python3 scripts/bump_version.py --check
scripts/check-custom-empty.sh
python3 scripts/check-local-skill-installs.py  # requires gh >= 2.90
```

Schema tests cover native binding/update/input contracts, rejected malformed
variants, and installation consistency. Behavioral eval scenarios cover native
design, unavailable capability, failure/halts, and approvals. See
`evals/COVERAGE-REPORT.md` for which evaluations were actually run. Packaging
checks and assistant evaluations do not constitute execution of this example on
Itential or certification of Claude Code, Codex, Copilot, or Cursor runtimes.
Version metadata remains unchanged per CONTRIBUTING; the user-facing correction
is recorded under Unreleased in CHANGELOG.
