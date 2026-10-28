# Changelog

Versions correspond to the plugin manifest version (`plugin.json`) and the GitHub
release tag — what every tool's update installs.

## Unreleased

- solution-arch-agent now recommends an execution model per phase — deterministic workflow, LCM resource, FlowAgent or Gateway5 service — with when to use and when not to use each, the order to decide in, common combinations and the platform check behind each. Feasibility records the choice and its check in `feasibility.md`; the design records it in Section C and lists LCM, agent and Gateway5 components in the inventory
- Removed `evals/` from the repository; evals are run and maintained locally, not in the repo
- builder-agent, solution-arch-agent and qa-agent now cover agents that call other agents: design them as a parent with child agents instead of forcing a workflow, let builder create agents and run test sessions, let QA run sessions in the approved test plan, and judge a child by its answer rather than its status
- Reworded `flowagent`'s description, README row and Codex metadata around designing, building and testing agents; running delivered agents belongs to the Operator pack
- builder-agent's manual-task section now says when to use ViewData, InteractiveHTML or QuickForm, with each task's output
- Fixed `itential-inventory` guidance, which never mentioned that an Inventory Manager adapter instance must exist and be running before inventory nodes appear in Configuration Manager or command templates. Added a Device Broker Adapter section (check, create, start, verify) and a pointer in the gotchas and the create-inventory scenario, plus notes that broker actions are a separate requirement for operating on those devices and that the Gateway host's Python must be 3.10 to 3.14 for the built-in broker services
- Fixed `flowagent` and `flowagent-to-spec`, which said an agent can't call another agent. An agent can call any saved agent as an `agent:<id>` tool; a new "Agents as tools" section, tested on a live platform, covers building a parent and child, checking whether the child's task actually worked, unreliable message paging, and export/import (`providerResolutions` is required). Human approval now says when to use ViewData (approve/reject), InteractiveHTML (custom form) or QuickForm (an action per row). Reorganised `flowagent` by task with each rule stated once, cutting it from 922 to about 610 lines

## 2.1.1

- Fixed invalid task IDs in builder-agent and itential-lcm examples and in the `runcode-taskquery-reference` asset (all now 1-4 hex characters), and added guidance for naming a new or inserted task, so generated workflows are less likely to fail project import with `must NOT have additional properties`
- Fixed builder-agent guidance for the object-typed fields that take `$var` references, which treated them all the same. `runCode` `data` is now authored one `$var` per key (a whole-object string ref runs, but Studio shows it as one row per character and can't add keys, and editing a row then saving writes the character keys into `data`, so the script gets them instead of the object and the job still completes). `runAgent` `inputs` is also one `$var` per key: Studio hides a whole-object string ref and a save turns it into one key per character. `runService` `params` follows the service: one `$var` per key when the service declares a parameter schema (Studio shows bound rows), a ref to a `merge` output when it doesn't (Studio shows per-key strings there as literal JSON). `transformation` `variableMap` must be per key, since a string ref makes `jobs/start` fail. Added a pre-flight check for each
- Fixed the flowagent skill's "Using Agents in Workflows" example, which wired `runAgent` `inputs` as one whole-object `$var`; it is now an object with one `$var` per key of the agent's input schema, with a note on why
- Added builder-agent evals 36–40 for the per-field `$var` shapes above

## 2.1.0

- Added a Gateway4 → Gateway5 migration delivery: a new spec (`spec-gateway4-to-gateway5-migration`) that takes the `gateway4-to-gateway5` readiness report as input, and a conversion guide covering the inventory move to Inventory Manager with broker actions, services imported through Gateway Manager, the task-by-task rewire, and parity tests — proven on a live Gateway4 and Gateway5 against a real device
- Added `convert_gateway4.py` (bundled with builder-agent and iag): reads Gateway4 read-only, or its exported JSON, and generates the Gateway5 `services.yaml` (decorators built from each script's Gateway4 schema or its own `argparse` flags), the service repository layout with playbooks reading their devices from the Inventory Manager nodes passed to `runService`, Inventory Manager nodes with broker attributes (including enable mode from `ansible_become`, which config pushes need) and secret references, and a report of what still needs review
- Added broker-action inventories to `itential-inventory`: `createBrokerActions`, the `itential_*` attribute convention, and how Gateway4 inventory variables map to it
- Added builder-agent guidance for Enable Query edge cases: array indexes (`#/items/0` shown as `.items[0]`), keys containing `/`, `~` or `.` (dotted keys need `.["a.b"]`), and what a path that doesn't exist does (error transition; on `evaluation`, the failure transition)
- Added `helpers/enable_query.py` to generate and check Enable Query decorators (`check` / `fix` / `apply_decorators`); it also flags `$var` references placed inside a static object, which are sent as literal text

- Changed the config-push examples in the asset library from `AGManager.itential_cli` (Gateway4) to `GatewayManager.sendConfig`: "Push Configuration" (`itential-platform-configuration-management.json`), "Push Configuration to Device - IAG" (`vendor-arista-eos.json`) and the three VXLAN Fabric Services LCM action workflows. Each takes `inventoryName` and `clusterId` and checks success per device. In the push workflows a `runCode` task replaces the "Process Push Configuration Data" transformation and returns the config, inventory target and messages in one result (`pushData`, replacing the `configurationToPush` output). Both push workflows were run against a live Arista EOS device, when the push lands and when it can't
- Changed builder-agent and iag to recommend `sendConfig` for config push, and `runCode` instead of JST transformations for reshaping data; `itential_cli` is called out as Gateway4, for existing workflows only, with two ways to move the tasks that read its output

- Fixed `scripts/use_case_init.py` writing an `.auth.json` without `platform_url`/`auth_method`, which made solution-arch-agent's `pull-platform-data.py` crash; it now also starts `use-case-memory.md` from the template
- Fixed solution-arch-agent's platform pull recording only the first page of workflows (100) and devices (1,000) — it now fetches all of them, so reuse searches see every workflow
- Fixed skills disagreeing on where a use case lives: `{use-case}` is `use-cases/<use-case-name>/` everywhere
- Fixed `explore` treating the `environments/*.env` templates as real credentials, and `gateway4-to-gateway5` naming the username/password mode `login` instead of `password`
- Fixed the `iag` Ansible examples: JSON playbook output is set with `stdout_callback` in `ansible.cfg` — `ANSIBLE_STDOUT_CALLBACK` in `runtime.env` is ignored by Gateway5. Added gateway gotchas found on a live Gateway5: importing services through Gateway Manager, waiting for the new service id after a `force` import, getting Ansible onto the gateway via `requirements.txt`, and how `runService` hands Inventory Manager nodes to a service on stdin
- Fixed transformation tasks in `itential-platform-configuration-management.json` and `vendor-arista-eos.json` that pointed at transformations outside their project, so 8 workflows imported as drafts that couldn't start; all 8 now start. Command Template Runner_v2's missing "Command Template Response Processor" and its four "Standard Output" transformations are now `runCode` tasks writing one `standardOutput` result (`success`, `reason`, `errorMessage`), replacing the separate `success`/`reason` outputs; it needs a `clusterId` input. Also fixed the LCM workflows' success check, which only looked at Gateway4's `icode` — that reports success even when the device rejects the configuration
- Fixed builder-agent's Enable Query guidance: it only showed the plain-field decorator, so workflows with a `#/path` but a missing or wrong decorator ran correctly yet showed no query in Studio, and opening then saving them silently dropped the query. It now gives the verified `pointer` for every field shape — top-level fields, whole object fields, `runCode` `data` and `transformation` `variableMap` keys, `merge` items, `childJob` variables and `childJob` loop `data_array`
- Fixed builder-agent telling builders to put `query` inside an `evaluation` operand, which never applied; the query goes on each evaluation item (`query` / `rightQuery`)
- Fixed builder-agent saying a `merge` item reading a `childJob` output must use `value`; on 6.5.2 `value` resolves to null with no error and `variable` is correct
- Fixed the push-config workflows' error-view decorator: its `displayPath` used `.results.0.output` where Studio writes `.results[0].output`, so Studio showed the query wrong and could strip it on save. `enable_query.py check` now passes on every file in the asset library

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
