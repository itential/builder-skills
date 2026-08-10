# Itential Platform - AI Agent Guide

This project contains skills for assisting developers on the Itential Platform. Read this first, then use the skills for detailed API references.

## Skill Router

Each skill owns a domain. **Invoke the skill using the Skill tool before working in that domain.** Skills contain the correct API methods, request bodies, response shapes, and patterns. Don't guess — load the skill.

| Skill | Agent | When to Use |
|-------|-------|-------------|
| `/explore` | — | Explore a platform freely — auth, discover, browse, build freestyle. |
| `/spec-agent` | **Spec Agent** | Start a delivery from a spec. Owns Requirements stage. |
| `/project-to-spec` | — | Read an existing project → produce customer-spec.md + solution-design.md. |
| `/documentation` | — | Survey global platform assets → discover relationships → group by use case → produce HLD+LLD per use case → optionally create projects and move assets in. For a specific named project, redirect to `/project-to-spec`. |
| `/flowagent-to-spec` | — | Read a FlowAgent → produce customer-spec.md as a deterministic workflow spec. |
| `/solution-arch-agent` | **Solution Architecture Agent** | Feasibility assessment + solution design. Runs after Requirements. |
| `/builder-agent` | **Builder Agent** | Build all assets, test each component individually. Runs after Design. |
| `/qa-agent` | **QA Agent** | Acceptance testing against the approved acceptance criteria + as-built record. Runs after Build — last technical stage before customer sign-off. |
| `/iag` | — | Automation Gateway: IAG services (Python, Ansible, OpenTofu). |
| `/iag4-to-iag5` | — | Assess IAG4→IAG5 migration readiness; identify IAG4 usage and produce a manual-action guideline. Analysis only, no migration. |
| `/flowagent` | — | AI Agents: configure LLM providers, tools, and agent sessions. |
| `/itential-mop` | — | Command templates with validation rules. |
| `/itential-devices` | — | Devices, backups, diffs, device groups. |
| `/itential-golden-config` | — | Golden config, compliance, grading, remediation. |
| `/itential-inventory` | — | Device inventories, nodes, actions, tags. |
| `/itential-lcm` | — | Resource models, instances, lifecycle actions. |
| `/itential-json-forms` | — | JSON Forms: static-enum, REST-bound, and cascading dropdowns for manual triggers and manual tasks. |

### Delivery Lifecycle

Spec-based delivery follows six stages. Each stage has a named agent, a clear input, and a deliverable.

```
Requirements → Feasibility →   Design    →  Build   →    Test    →  As-Built
      │              │             │            │             │            │
  Spec Agent   Solution Arch  Solution Arch  Builder      QA Agent    QA Agent
                   Agent          Agent       Agent
      │              │             │            │             │            │
  customer-      feasibility.md solution-    assets/    test-report.md as-built.md
  spec.md        (assessment    design.md    configs    (evidence per  (delivered
  (approved)     + decision)   (approved)   (delivered) criterion, from   state,
                                                          test-plan.md    deviations,
                                                          approved by     learnings)
                                                          engineer)      ↳ design updates
                                                                         ↳ spec amendments
```

**Deliverables:**

| Deliverable | Artifact | Produced by | Audience |
|-------------|----------|-------------|----------|
| HLD | `customer-spec.md` | Spec Agent | Customer / stakeholder |
| Feasibility Assessment | `feasibility.md` | Solution Architecture Agent | Customer / architect |
| Solution Design / LLD | `solution-design.md` | Solution Architecture Agent | Engineer / delivery team |
| Test Plan | `test-plan.md` | QA Agent | Engineer (approves before any live test execution) |
| Test Report | `test-report.md` | QA Agent | Customer / delivery — evidence per acceptance criterion |
| As-Built | `as-built.md` | QA Agent | Customer / delivery / support / system of record |

**Explore path** (no spec, no delivery lifecycle):
```
/explore → auth → pull platform data → summarize → use skills directly
```

**IMPORTANT: Invoke skills using the Skill tool** — don't just reference them in text. When you need to build workflows/templates, invoke `/builder-agent`. When a build needs acceptance testing or a closeout record, invoke `/qa-agent`. The skills contain the API details you need. Without loading them, you're guessing.

### Directory Layout

Platform data (shared, pulled once) and use-case data (per engagement) live in separate directories. **Never mix them.**

```
builder-skills/
├── platform/               ← shared pre-pull via scripts/platform_pull.py (fallback only)
│   ├── openapi.json        — full API reference
│   ├── tasks.json          — task catalog
│   ├── apps.json           — app and adapter type names
│   ├── adapters.json       — adapter instances and state
│   ├── applications.json   — application details
│   ├── environment.md      — human-readable summary
│   └── .pulled-at          — timestamp of last pull
│
└── use-cases/
    └── <use-case-name>/    ← scaffolded via scripts/use_case_init.py
        ├── .env              — credentials (gitignored)
        ├── .auth.json        — live bearer token (gitignored, auto-refreshed)
        ├── openapi.json      — pulled fresh by /explore or /solution-arch-agent (prefer over platform/)
        ├── tasks.json        — pulled fresh per engagement (prefer over platform/)
        ├── apps.json         — pulled fresh per engagement (prefer over platform/)
        ├── adapters.json     — pulled fresh per engagement (prefer over platform/)
        ├── applications.json — pulled fresh per engagement (prefer over platform/)
        ├── task-schemas.json — fetched on demand during build, never pre-populated
        ├── use-case-memory.md — living context: IDs, decisions, gotchas, test log, open items
        └── (deliverables: customer-spec.md, feasibility.md, solution-design.md, test-plan.md, test-cases.json, test-report.md, as-built.md)
```

**Setup sequence (one-time per platform):**
```bash
./scripts/platform_pull.py <platform-url> <client-id> <client-secret>
```

**Per use-case:**
```bash
./scripts/use_case_init.py <use-case-name> <platform-url> <client-id> <client-secret>
```

**Refresh platform data** (after platform upgrade or new adapters installed):
```bash
./scripts/platform_pull.py --refresh <platform-url> <client-id> <client-secret>
```

**At the start of every session — read the memory file first:**
```bash
cat use-cases/<name>/use-case-memory.md
```
It contains the platform URL, project ID, what's already built, decisions made, and open items. Don't re-discover what's already documented. If the file doesn't exist, create it from `helpers/use-case-memory.md`.

### Resuming a Use-Case

`use-case-memory.md`'s `Stage` field tells you where to pick up — but a field can go stale (an agent forgets to update it, a session gets interrupted mid-write). **Verify `Stage` against which files actually exist before trusting it.** If they disagree, the files are ground truth — investigate the mismatch before proceeding, don't just pick one.

| `Stage` says | Files that should exist | Files that should NOT exist yet |
|---|---|---|
| `requirements` | (nothing yet, or a draft `customer-spec.md`) | `feasibility.md` |
| `feasibility` | `customer-spec.md` (approved) | `feasibility.md` (approved) |
| `design` | `feasibility.md` (approved) | `solution-design.md` (approved) |
| `build` | `solution-design.md` (approved) | Component Inventory (§D) has real IDs |
| `test` | `solution-design.md` §D has real IDs | `test-report.md` (complete) |
| `as-built` | `test-report.md` (all cases passing, or residuals explicitly accepted) | `as-built.md` |
| `delivered` | `as-built.md` (signed off) | — |

`Status: on-hold` can apply at any `Stage` — it means work is paused, not that the stage is wrong. Every skill that hands off to another stage MUST update `Stage` (and `Last updated`) before ending its session — see each skill's handoff section for the exact point to do it.

**Data lookup order:**
- `{use-case}/tasks.json`, `apps.json`, `adapters.json`, `openapi.json` — pulled by `/solution-arch-agent` or `/explore` during feasibility. **Always prefer these — they are per-engagement and fresh.**
- `platform/tasks.json`, `platform/apps.json` etc. — pulled once by `scripts/platform_pull.py`, shared across engagements. Use as fallback only if `{use-case}/` files are missing.
- `{use-case}/task-schemas.json` — fetched on demand during build (never pre-populated). Append after every fetch; never re-fetch what's already cached.
- If neither `{use-case}/tasks.json` nor `platform/tasks.json` exist → tell the user to run `/explore` or `scripts/platform_pull.py` first.

### Auth Reuse — Authenticate Once, Reuse Everywhere

**Auth happens when first needed** — in `/explore` (explore path) or in `/solution-arch-agent` during Feasibility. The token is saved to `use-cases/{use-case}/.auth.json`. Every subsequent skill should:
1. Read `use-cases/{use-case}/.auth.json` for the token
2. Read `use-cases/{use-case}/.env` for `PLATFORM_URL` and credentials
3. Use the token for all API calls (Bearer header for OAuth)
4. On auth error (401/403): re-authenticate silently — see procedure below
5. **Never ask the user for credentials if `.env` exists**

This means the user authenticates once and every subsequent skill just works.

**Token expiry — silent re-auth procedure:**

When any API call returns 401 or 403, do not stop and do not ask the user. Re-authenticate silently:

1. Read credentials from `use-cases/{use-case}/.env`
2. Call: `POST {PLATFORM_URL}/oauth/token` with `Content-Type: application/x-www-form-urlencoded` and body `grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}`
3. Write the new token back to `use-cases/{use-case}/.auth.json`
4. Retry the failed request with the new token

If `.env` does not exist and re-auth is needed, then and only then ask the user for credentials.

### Key Rule: Look Up Before You Act — Don't Guess

**Skills** teach patterns, workflows, and know-how (how to build a childJob, how to wire variables, how to test).

**`platform/openapi.json`** has every endpoint, method, request body, and response schema. Search it locally — never load the full file into context.

**Before making any API call:**
1. Check the relevant skill for the pattern
2. Search `platform/openapi.json` to confirm the endpoint, method, request body, and response schema — `jq '.paths["/the/endpoint"]' platform/openapi.json`
3. **Check the body wrapper** — most Itential APIs wrap the body in a top-level key. Find it: `jq '.paths["/the/endpoint"].post.requestBody.content["application/json"].schema.properties | keys' platform/openapi.json` → returns the wrapper name (e.g., `["role"]` means `{role: {...}}`)
4. Never hardcode API assumptions — the spec is the source of truth

**Before fetching task schemas:**
1. Check if `use-cases/{use-case}/task-schemas.json` exists — search it first with `jq` or `grep`
2. Only call `multipleTaskDetails` for tasks NOT already in the local file
3. After fetching, always append to the local file so future lookups are instant

**Before parsing any local JSON file:**
1. Check the response shape first — `jq type` and `jq keys` on the file
2. The `/solution-arch-agent` skill has a file-to-shape table — use it
3. Key shapes to remember:
   - `adapters.json` → `{"results": [...]}`
   - `applications.json` → `{"results": [...]}`
   - `devices.json` → `{"list": [...]}`
   - `workflows.json` → `{"items": [...]}`
   - `apps.json` → plain array `[...]`
   - `tasks.json` → plain array `[...]`
4. Use `jq` for parsing, not inline Python scripts with isinstance fallbacks

**When something fails or returns unexpected data — check local files FIRST:**
1. **`openapi.json`** — verify the endpoint exists, check the method (GET vs POST), read the request body schema and response schema. This file has EVERY endpoint, field, and type. Don't guess what a payload looks like — look it up.
2. **`tasks.json`** — verify the task name, app, location. If a task is "not found," search here first.
3. **`task-schemas.json`** — if you already fetched schemas, the full input/output definition is here. Check field names, types, required vs optional.
4. **`adapters.json` / `apps.json`** — verify adapter instance names, app names, casing. Adapter names from `apps.json` (type name) differ from `adapters.json` (instance name).
5. **`job.error` array** — for runtime errors (not just task status)
6. **Actual task output** — `status: complete` doesn't mean the CLI commands worked

**The filesystem is your debugger.** Every API endpoint, every task schema, every adapter name is already saved locally after setup. Never guess a payload structure, field name, or endpoint path — the answer is in these files. Reading a local file costs zero API calls and zero time.

## Understanding User Intent

Figure out which **category of work** the user needs:

- **Building** — create something new (workflow, template, compliance standard). Start with requirements, then build.
- **Operating** — do something now (configure a device, run compliance, backup configs). Identify targets and execute.
- **Exploring** — understand what's available (devices, adapters, workflows). Discover and navigate.
- **Debugging** — something broke (workflow failing, adapter errors). Get job details, check `job.error`.
- **Designing** — planning architecture (modular workflows, compliance hierarchy). Think before building.

## Developer Flow

Six stages. Four agents. Each stage has a named agent, a clear input, and a deliverable. Nothing moves forward without the engineer's sign-off at each stage.

```
Requirements → Feasibility →   Design    →  Build   →    Test    →  As-Built
      │              │             │            │             │            │
 /spec-agent   /solution-     /solution-   /builder-     /qa-agent   /qa-agent
                arch-agent     arch-agent    agent
      │              │             │            │             │            │
  customer-      feasibility.md solution-    assets/    test-plan.md  as-built.md
  spec.md        (approved)     design.md   (delivered) (approved),   (approved)
  (approved)                    (approved)              test-report.md
```

**Stage summaries:**

| Stage | Agent | What happens | Engineer does |
|-------|-------|-------------|---------------|
| Requirements | `/spec-agent` | Refines use case, defines scope, structures HLD | Approves `customer-spec.md` |
| Feasibility | `/solution-arch-agent` | Connects to platform, assesses capabilities, flags constraints | Approves `feasibility.md` |
| Design | `/solution-arch-agent` | Produces component inventory, adapter mappings, build plan, acceptance-criteria-to-test mapping | Approves `solution-design.md` |
| Build | `/builder-agent` | Builds all assets, tests each component individually, delivers | Reviews and accepts delivery |
| Test | `/qa-agent` | Drafts `test-plan.md`, runs static + acceptance test cases against confirmed test data, reports evidence | Approves `test-plan.md` before live execution; reviews `test-report.md` |
| As-Built | `/qa-agent` | Records delivered state, deviations, learnings, backed by test evidence | Signs off on `as-built.md` |

**For explore / freestyle work:**
```
/spec-agent → auth → pull platform data → use skills directly
```

## Key Rules

1. **Never invent task names** — always look them up from `tasks/list`
2. **Always get the schema before building** — `multipleTaskDetails?dereferenceSchemas=true`
3. **Adapter `app` AND `locationType` fields come from `apps/list`**, not `tasks/list` (names can be completely different, not just casing). The `app` field is the adapter **type name** (e.g., `EmailOpensource`), NOT the adapter **instance name** (e.g., `email`). Using the instance name causes `"No config found for Adapter"` errors. Resolve from local `apps.json` and `adapters.json`. When multiple adapter apps exist for the same product, ask the user.
4. **Test each piece individually** before composing into a larger workflow
5. **Check `job.error` for failures**, not just task status
6. **Variable syntax differs by context:**
   - Jinja2 templates: `{{ var }}`
   - Command templates / makeData: `<!var!>`
   - Workflow wiring: `$var.job.x`
   - childJob variable refs: `{"task": "job", "value": "varName"}`
   - merge/evaluation refs: `{"task": "job", "variable": "varName"}` (NOT `"value"` — different field than childJob)
7. **Validation errors = draft workflow** that cannot be started
8. **`$var` references don't resolve inside object values** (e.g., inside `newVariable` value or adapter `body`) — use `merge`, `makeData`, `query`, or other utility tasks to build the object, then pass it as a top-level `$var` reference
9. **Task IDs are hex-only** — `[0-9a-f]{1,4}`. Non-hex IDs (e.g., `qt`, `ok`, `success`, `err1`) cause two problems: (a) `$var` references silently fail at runtime (classified as static), and (b) **project import fails** with `"must NOT have additional properties"` — the import schema rejects any task key that is not `workflow_start`, `workflow_end`, or a valid hex ID. Always generate task IDs in hex format from the start. To fix existing workflows with bad IDs: rename tasks in-place via PUT, updating transitions and all `$var.<taskId>.*` references simultaneously.
10. **`genericAdapterRequest` prepends the adapter's `base_path`** to `uriPath` — don't include `/api/v1` in `uriPath`. Use `genericAdapterRequestNoBasePath` if you need the full path
11. **Use `POST /projects/import` to create projects atomically** — build all assets locally, pre-compute the project `_id`, pre-wire childJob `@projectId:` refs, then import everything in one call. Avoid the create-then-move pattern (breaks childJob refs, causes project-locking issues).
11a. **Patch project membership immediately after every create or import** — the platform sets the OAuth service account as the sole owner on creation, locking out human users. Immediately after `POST /automation-studio/projects` or `POST /automation-studio/projects/import`, call `PATCH /automation-studio/projects/{id}` to add the engineer's user account or group as owner. This is mandatory — skip it and the engineer cannot open the project. Resolve reference IDs by scanning existing projects (see "Resolve membership references" below). PATCH is a **full replacement** — always include all members, including the service account, or they will be removed.
11b. **Project thumbnails use a data URI, not raw base64** — `PUT /automation-studio/projects/{id}/thumbnail` expects `{"imageData": "data:image/png;base64,...", "backgroundColor": "#RRGGBB"}`. Passing raw base64 without the `data:image/png;base64,` prefix results in a black/blank thumbnail in the UI. Use `GET /automation-studio/projects/{id}/thumbnail` to retrieve; the response is `{"data": {"image": "data:image/png;base64,...", "backgroundColor": "..."}}`. Accepted formats: jpg, jpeg, png up to 1000 KB. **Optimal dimensions: 330×100 px.**
12. **API response shapes vary** — projects use `{message, data, metadata}`, but workflow and template lists use `{items, skip, limit, total}`, and create endpoints return `{created, edit}`. Always check the response shape before parsing
13. **Project component types** — valid values: `workflow`, `template`, `transformation`, `jsonForm`, `mopCommandTemplate`, `mopAnalyticTemplate`
14. **Use skills, don't reimplement** — `/builder-agent` covers projects, workflows, templates, MOP, and component-level testing. Acceptance testing and as-built records are `/qa-agent`'s job, not builder-agent's. Only load other skills for their specific domains (IAG, FlowAgent, MOP, etc.)
15. **When unsure about ANY endpoint, method, or payload — check `openapi.json` FIRST.** Run `jq '.paths["/the/endpoint"]' platform/openapi.json` to see the method, request body schema, and response schema. Don't guess, don't try variations, don't make up field names — look it up. The spec is always right.
16. **If `openapi.json` is not local, fetch it** — `GET /help/openapi?url={ENCODED_BASE}` and save it. Then search locally.
17. **If the openapi schema is empty for an endpoint** — check the corresponding POST/PUT endpoint's schema for the wrapper pattern. As a last resort, send `{}` and read the `"Missing Params"` error — it lists every required field with name, type, and examples.
18. **Endpoint base paths differ** — task catalog is at `/workflow_builder/tasks/list`, but task schemas are at `/automation-studio/multipleTaskDetails` (NOT `/workflow_builder/multipleTaskDetails`). Don't mix them up.
19. **Error transitions are mandatory on adapter/external tasks** — without an error transition, task errors produce "Job has no available transitions" and the job gets stuck forever. Always add `"state": "error"` transitions on tasks that call adapters or external systems.
20. **Adapter responses are transformed** — adapters reshape the upstream API response. Don't assume the native API's response structure (e.g., ServiceNow `result.sys_id`). Call the adapter endpoint directly or check `openapi.json` to verify the actual response shape before wiring query paths.
21. **Duplicate transition keys to same target** — JSON doesn't allow two keys with the same name. If a task needs both `success` and `error` to reach `workflow_end`, create an error handler task (e.g., `newVariable` to set error status) and route error there, then route that task to `workflow_end`.
22. **Respect task schema data types** — When wiring task inputs, match the type from `task-schemas.json` exactly. If a field is typed as `array`, pass an array (e.g., `["joksan@example.com"]`), not a bare string. If typed as `number`, pass a number, not a string. Common offenders: `to`/`cc`/`bcc` in email tasks (arrays, not strings), `pageSize`/`page` in queries (numbers, not strings). Mismatched types cause silent failures or validation errors.
23. **Adapter `app` ≠ adapter instance name** — The `app` and `locationType` fields on adapter tasks must be the adapter **type name** from `apps.json` (e.g., `EmailOpensource`, `Servicenow`), NOT the adapter **instance name** from `adapters.json` (e.g., `email`, `servicenow-prod`). Using the instance name causes `"No config found for Adapter: <name>"` at runtime. The `adapter_id` field is where the instance name goes. Triple-check: `app` = type, `adapter_id` = instance.
24. **Project-scoped asset names** — once an asset is added to a project, its `name` is prefixed with `@{projectId}: `. When reading or updating a project-owned asset via PUT, you MUST use the scoped name or the API returns 400. Read the asset first to get its current name, or construct it as `@{projectId}: {displayName}`. Strip this prefix when displaying names to the user.
25. **NEVER wire a Configuration Manager remediation task** — `runAutoRemediation`, `advancedAutoRemediation`, `convertChangesToConfig`, `patchDeviceConfiguration`, `advancedPatchDeviceConfiguration`, `patchCMDeviceConfiguration`, `ManualRemediation`, and `ManualRemediationResults` are prohibited in every workflow, even when a spec asks for fully automatic remediation. Golden Config detects and reports drift; it never applies fixes to a device. To correct a device, build a normal config-push delivery using the environment's config-push task (`sendConfig`/`runService` via GatewayManager, `itential_cli`, or netmiko send-config). See the `/itential-golden-config` Remediation section. (`updateNodeConfig` is allowed — it authors the GC node template, not a device.)

## Helper JSON Templates

**For workflow design and task wiring — read from `helpers/assets/` first.** The asset projects are real, tested, production imports. Extract task structures, variable wiring, transition patterns, and transformation usage directly from those files. Do not invent task schemas from memory.

**For API call bodies (create, update, operations) — use the helpers below.** These cover request wrappers and field names for endpoints that the asset projects don't demonstrate.

Helper templates are organized in subdirectories under `helpers/`:

**`helpers/create/`** — POST bodies for creating assets

| File | Purpose |
|------|---------|
| `create-workflow.json` | Workflow scaffold with start/end tasks |
| `create-project.json` | Project creation |
| `import-project.json` | Import a project (atomic — preferred over create + add) |
| `create-command-template.json` | Command template with `<!var!>` syntax |
| `create-template-jinja2.json` | Jinja2 template |
| `create-template-textfsm.json` | TextFSM template |
| `create-json-form.json` | JSON form for user input |
| `create-json-form-rest-bound.json` | JSON form with REST-bound dropdowns |
| `create-ops-manager-automation.json` | Operations Manager automation |
| `create-ops-manager-trigger.json` | API endpoint trigger |
| `create-ops-manager-trigger-manual.json` | Manual/form trigger (legacyWrapper: false) |
| `create-ops-manager-trigger-schedule.json` | Scheduled trigger (repeat object, not cron) |
| `create-lcm-resource-model.json` | LCM resource model with lifecycle actions |
| `create-integration.json` | Virtual integration (adapter instance) |
| `create-golden-config-tree.json` | Golden config tree |
| `create-golden-config-node.json` | Child node |
| `create-compliance-plan.json` | Compliance plan |
| `create-flowagent-project-bundle.json` | FlowAI agent project bundle (project + agent + tools + decorator) — import via `/agent-project-service/project-bundles/import` |
| `create-flowagent-decorator.json` | FlowAI tool decorator body — narrows a tool's `inputSchema` for the LLM |

**`helpers/update/`** — PUT/PATCH bodies for updating assets

| File | Purpose |
|------|---------|
| `update-command-template.json` | Update command template (full replacement) |
| `update-json-form.json` | Update a JSON form — wrapped in `options` key (full replacement) |
| `update-node-config.json` | Node template with full syntax |
| `update-project-members.json` | Update project membership — include all members (PATCH = full replacement) |

**`helpers/operations/`** — Add, run, and other operation bodies

| File | Purpose |
|------|---------|
| `add-components-to-project.json` | Add assets to an existing project |
| `add-devices-to-node.json` | Assign devices to a golden config node |
| `run-compliance-plan.json` | Run a compliance plan |
| `run-compliance.json` | Run compliance directly against a tree/node |

**`helpers/assets/`** — Importable sample projects. Use these as design references and borrow components directly rather than building from scratch.

Import via `POST /automation-studio/projects/import` with body `{"project": <file contents>}`.
After import, PATCH membership immediately (see Rule 11a).

**FlowAI agent samples** — different domain, different import path (not Automation Studio):

| File | What's Inside |
|------|--------------|
| `flowagent-sample-agent-project.json` | Real FlowAI project bundle exported from a live platform: 3 agents, including a multi-tool agent (device command → decorated ServiceNow tool → WorkCenter approval step). Import via `POST /agent-project-service/project-bundles/import` with `{"bundle": <file contents>, "providerResolutions": {...}}` — see the `flowagent` skill. |

**JSON Form samples** — different domain, different import path (`POST /json-forms/forms` directly, not Automation Studio project import):

| File | What's Inside |
|------|--------------|
| `json-form-example-static-enum.json` | Real Cisco IOS "Port Turn Up" form export: 8 fields incl. a static-enum dropdown, number `updown` widgets, `ipv4` format validation. No REST binding. |
| `json-form-example-rest-bound.json` | Real Cisco IOS "Compliance" form export: one REST-bound dropdown pulling tree names live from `GET /configuration_manager/configs`, plus one plain text field. |

Both extracted from real, working `jsonForm`-type components inside `vendor-cisco-ios.json` — see the `itential-json-forms` skill for the full form-structure reference.

**Itential Platform — core utilities**

| File | What's Inside |
|------|--------------|
| `itential-platform-configuration-management.json` | 6 workflows (Command Template Runner, Golden Config, Backup Config, Push Config, Diff), 2 templates, 6 transformations — *requires IAG* |
| `itential-platform-data-manipulation.json` | 21 transformations — Parse Number, Chunk Array, Get Value From JSON Pointer, Group Records, Filter Array, Split String, Remove Duplicates, Allocate Numbers, Convert CSV to JSON, and more |
| `itential-platform-email.json` | 1 workflow (Send Email SMTP), 2 transformations — *requires Email Adapter* |
| `itential-platform-regex-operations.json` | 4 transformations — Test Match, Find Match, Replace, Extract |

**Vendor integrations — design and wiring examples**

*Software upgrade patterns:*

| File | What's Inside |
|------|--------------|
| `vendor-cisco-ios.json` | IOS Upgrade, Port Turn Up, Run Compliance, NetBox Inventory sync — 5 workflows, 6 MOP command templates, 3 JSON forms |
| `vendor-juniper-junos.json` | JUNOS Upgrade, Port Turn Up, Run Compliance, NetBox Inventory sync — 5 workflows, 6 MOP command templates, 1 template, 2 JSON forms |
| `vendor-arista-eos.json` | Software Upgrade, Port Turn Up, Create VLAN, Push Config, File Transfer — 7 workflows, 9 MOP command templates, 6 transformations |

*DNS and IPAM:*

| File | What's Inside |
|------|--------------|
| `vendor-infoblox-nios-ddi.json` | 20 workflows — full CRUD for Networks, Network Containers, DNS A/CNAME/PTR/NS/Fixed Address records, Assign Next IP |
| `vendor-netbox.json` | 6 workflows (Create/Delete Prefix, Reserve/Delete IP, Assign Next IP, Onboard Device), 9 transformations, 1 JSON form |

*ITSM integration:*

| File | What's Inside |
|------|--------------|
| `vendor-servicenow.json` | 9 workflows (Create/Update/Close Incidents, Change Requests, RITMs, Get Catalog Inputs), 6 transformations |

**`helpers/assets/lcm/`** — LCM resource model exports + their backing project (exported from live platform)

The `lcm-*.json` files are resource model exports (import via `POST /lifecycle-manager/resources/import`).
The project file contains the actual LCM action workflows — read it to understand how LCM workflows are structured.

| File | What's Inside |
|------|--------------|
| `lcm-vxlan-fabric-management.json` | Resource model: 5 actions (Create Network, Re-Provision, Delete, Force Delete, Decommission) — 4 wired |
| `lcm-vxlan-fabric-services-project.json` | **Backing project**: 6 LCM action workflows, 13 transformations, 3 JSON forms, 2 templates, 1 MOP template — the real workflow structure to learn from |
| `lcm-fan-device-lifecycle-management.json` | Resource model: 10 actions (Device Onboarding, SW Compliance, CVE Scan, Upgrade, Decommission, etc.) — 9/10 wired |
| `lcm-port-turn-up.json` | Resource model: 6 actions (Create, Delete, Service Verification, Update Service Policy) — 4/6 wired |
| `lcm-ip-blocking-service.json` | Resource model: 4 actions (Create, Update, Delete, Retry) — fully wired |
| `lcm-interface-service-provisioning.json` | Resource model: 3 actions (Create, Modify, Delete) — fully wired |

**Key LCM rule:** every action workflow **must** declare and output an `instance` variable — this is what LCM uses to track resource state between actions. Read the VXLAN project workflows to see the exact pattern.

**`helpers/assets/openapi-specs/`** — OpenAPI spec examples for use with the OpenAPI adapter

| File | Purpose |
|------|---------|
| `whoami-basic-auth.json` | WhoAmI endpoint spec with Basic Auth |
| `whoami-client-creds.json` | WhoAmI endpoint spec with Client Credentials |

### Assets Library — when a vendor or pattern isn't here

The full asset library lives at **https://github.com/itential/assets** (branch: `devel`). Structure: `<Vendor>/<Product>/Projects/<name>.project.json`.

**When to check the repo:**
- The use case involves a vendor not covered by the files above (AWS, Arista, Juniper, F5, Palo Alto, Alkira, Kentik, etc.)
- You need a workflow pattern that isn't in the local helpers
- The customer asks about supported integrations

**How to pull a project from the repo:**
```bash
# List available projects for a vendor
gh api repos/itential/assets/contents/<Vendor>/<Product>/Projects --jq '.[].name'

# Download it into helpers/assets/
curl -sL "https://raw.githubusercontent.com/itential/assets/devel/<Vendor>/<Product>/Projects/<encoded-name>.project.json" \
  -o "helpers/assets/<local-name>.json"
```

**Full vendor index (has Projects/):** Alkira, Apache/Kafka, Arista/EOS, Atlassian/Jira, AWS/EC2, Cisco/ASA, Cisco/IOS, Cisco/Meraki, Cisco/NSO, Cisco/NX-OS, F5/BIG-IP, F5/BIG-IQ, GitHub, GitLab, IP Fabric, Infoblox/NIOS DDI, Juniper/JUNOS, Kentik, Microsoft/Teams, NetBox, Palo Alto/Panorama, ServiceNow, Versa/Director

**`helpers/iag/`** — Automation Gateway service files

| File | Purpose |
|------|---------|
| `example-python-service.yaml` | Python script service |
| `example-ansible-service.yaml` | Ansible playbook service |
| `example-opentofu-service.yaml` | OpenTofu plan service |
| `example-multi-service-chain.yaml` | Multi-service orchestration |
| `service-file-schema.md` | Full YAML schema reference |
