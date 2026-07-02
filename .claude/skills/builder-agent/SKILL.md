---
name: builder-agent
description: Use this skill when someone has an approved solution design and is ready to build. Trigger it for phrases like "solution design is approved", "go ahead and build", "implement the design", "create the workflows", "build everything per the design", "start the build", "the design is locked — implement it", or "write the as-built documentation". Also trigger it when a build is failing mid-way and needs debugging. This skill implements the approved solution-design.md end-to-end — creating all workflows, templates, projects, and configs, testing each component, and producing as-built.md. If the user has a solution-design.md and wants to turn it into working automation, this is the right skill. Invoke after /solution-arch-agent produces an approved solution-design.md.
---

# Builder Agent

**Stages:** Build → As-Built
**Owns:** Implementing the approved design and recording the delivered state.
**Receives from:** `/solution-architecture` (approved `solution-design.md` + complete workspace)
**Produces:** Deployed assets + `as-built.md`

---

## Stage Expectations

### Build

| | |
|--|--|
| **Engineer provides** | Approved `solution-design.md` (all platform data already present in workspace) |
| **Agent does** | Builds all components per design, tests each piece, reports delivery outcomes |
| **Engineer action** | Reviews delivery and resolves open build questions |
| **Deliverable** | Deployed assets (workflows, templates, projects) |
| **Customer receives** | Delivered project — all workflows, templates, and configs tested, packaged, and access granted. Acceptance criteria verified. |

Build implements the approved plan. The builder never re-pulls discovery data — it uses what the Solution Architecture Agent left in the workspace. If any required file is missing, stop and surface as an upstream failure.

### As-Built

| | |
|--|--|
| **Engineer provides** | Deployed assets and build outcomes |
| **Agent does** | Records delivered state, deviations from design, learnings; updates design and spec where needed |
| **Engineer action** | Signs off on as-built record |
| **Deliverable** | `as-built.md` + design/spec updates |
| **Customer receives** | As-built record — delivered state, deviations from design with reasons, and learnings. The baseline for future work on this use case. |

As-Built is closeout documentation. It captures delivery reality — what was built, what changed from the design, and what was learned. Design deviations update `solution-design.md` as an `## As-Built` section. Scope changes amend `customer-spec.md` with a dated `## Amendments` section.

---

This skill covers everything needed to build and test Itential automation assets: projects, workflows, templates, and command templates.

## Workspace Contract

**The builder receives a complete workspace. All discovery data is already present.** Solution-design (or setup for explore mode) has already pulled everything.

**Required files (must exist before build starts):**
```
{use-case}/
  .auth.json              ← auth token
  .env                    ← credentials (for re-auth if token expires)
  openapi.json            ← API reference (pulled by solution-arch-agent or explore)
  tasks.json              ← task catalog (pulled by solution-arch-agent or explore)
  apps.json               ← app/adapter type names (pulled by solution-arch-agent or explore)
  adapters.json           ← adapter instances (pulled by solution-arch-agent or explore)
  applications.json       ← app health (pulled by solution-arch-agent or explore)
```

**May also exist (spec-contingent):**
```
  use-case-memory.md      ← living context: IDs, decisions, gotchas, open items — READ THIS FIRST
  customer-spec.md        ← approved HLD (Requirements)
  feasibility.md          ← approved feasibility assessment
  customer-context.md     ← business rules (if provided)
  solution-design.md      ← approved Solution Design / LLD
  devices.json            ← device inventory
  workflows.json          ← existing workflows
  device-groups.json      ← device groups
  task-schemas.json       ← fetched on demand during build (append-only, never pre-populated)
```

**The builder NEVER re-pulls bootstrap or discovery data.** If `tasks.json`, `apps.json`, or `adapters.json` is missing, stop and tell the user — that's an upstream failure, not something to silently fix.

**Exception — `.auth.json` bootstrap:** If `.auth.json` is missing but `.env` exists with `AUTH_METHOD=oauth`, `CLIENT_ID`, and `CLIENT_SECRET`, the builder MUST authenticate and create `.auth.json` before proceeding — do NOT stop and report an upstream failure. See the **Bootstrap Authentication** section below.

**The only API calls the builder makes are:**
- **Auth bootstrap** — POST /oauth/token when `.auth.json` is missing (see below)
- **Create** — POST workflows, templates, projects
- **Update** — PUT to edit assets
- **Test** — POST jobs/start, GET job status
- **Schema fetch** — task schemas not yet in `task-schemas.json` (append to file after fetching)
- **Re-auth** — if token expires, use `.env` to refresh `.auth.json`

### Bootstrap Authentication

When `.auth.json` is missing but `.env` has `AUTH_METHOD=oauth` with `CLIENT_ID` and `CLIENT_SECRET`, authenticate automatically before proceeding.

**The correct Itential SaaS/Cloud OAuth endpoint is:**
```
POST {PLATFORM_URL}/oauth/token
Content-Type: application/x-www-form-urlencoded
```

**Body (form-encoded, NOT JSON — JSON returns 415):**
```
grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}
```

**Critical:**
- Content-Type MUST be `application/x-www-form-urlencoded` — NOT `application/json`. Sending JSON returns HTTP 415.
- The `/login` endpoint does NOT support OAuth client credentials on SaaS instances — always use `/oauth/token`.
- On success, write `.auth.json` with the token so all subsequent API calls just work.

**Helper script:** `${CLAUDE_PLUGIN_ROOT}/scripts/oauth_bootstrap.py` — reads `.env`, POSTs to `/oauth/token`, writes `.auth.json`. The builder should run this automatically when `.auth.json` is missing and `.env` has `AUTH_METHOD=oauth`.

---

## Build Lifecycle

```
0. Memory file              → create or read use-cases/{name}/use-case-memory.md
1. Decompose                → identify parent/child split before writing any code
2. Create project           → container for all assets
3. Discover tasks           → search tasks.json, fetch schemas
4. Build children first     → each child workflow independently testable
5. Build templates          → Jinja2 (config gen) or TextFSM (output parsing)
6. Build command templates  → MOP pre/post checks with validation rules
7. Build orchestrator last  → parent wires tested children via childJob
8. Add assets to project    → move/copy into the project
9. Set project membership   → resolve spec members, PATCH immediately after import
10. Test                    → jobs/start, check results
11. Debug                   → check job.error, filesystem-first
12. Reconcile               → diff built vs designed, update artifacts
13. Update memory file      → record IDs, decisions, gotchas, test results, open items
14. Update this skill       → if you hit a platform behavior not documented here, add it before closing out
```

**Step 0 — memory file:**

At the start of every session, check for `use-cases/{use-case}/use-case-memory.md`:
- **Exists** → read it before doing anything else. It tells you the platform, project ID, what's already built, decisions made, and open items. Don't re-discover what's already documented.
- **Missing** → create it now from `${CLAUDE_PLUGIN_ROOT}/helpers/use-case-memory.md` template. Fill in Platform URL and Status immediately.

**Step 13 — update memory file after every session:**

Before closing out any build session, update `use-case-memory.md` with:
- Any new asset IDs (project ID, workflow UUIDs, transformation IDs, adapter names)
- Any architectural decisions made and **why**
- Any gotchas hit and how they were fixed
- Test results (date, what was tested, outcome)
- Updated open items list
- Status field if it changed

The memory file is what makes it possible to pick up a use-case after weeks without re-discovering everything from scratch.

**Step 14 — how to update this skill:**
- New platform behavior (error shape, field constraint, task gotcha) → add detail to the relevant body section (`### query`, `### childJob`, `### Projects`, etc.), then add a one-liner to the Gotchas pre-flight list under the right category.
- New pattern or workflow recipe → add to `## Workflow Patterns` and, if the pattern is reusable, export the project from the platform and save it to `${CLAUDE_PLUGIN_ROOT}/helpers/assets/`. Add a row to the Helper Templates table in this file pointing to it.
- Do NOT create a new top-level section for a single finding — put it where a builder would look when working on that topic.

---

## Guides

### Guide 1: Build a workflow end-to-end

Follow these steps in order. Do not skip any step.

---

> **STOP. Before writing a single line of task JSON — run these commands.**
>
> The asset projects in `helpers/assets/` are real, production-tested imports. Read them first.
> Do not guess task structure from memory. Do not copy from `helpers/create/` for task bodies.
> `helpers/create/` is for API wrappers (project/workflow creation endpoints) only — not task JSON.
>
> ```bash
> # 1. Find which asset project matches your use case
> ls ${CLAUDE_PLUGIN_ROOT}/helpers/assets/
>
> # 2. Extract the workflow most similar to what you're building
> jq '[.components[] | select(.type=="workflow")] | .[].document.name' \
>   ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-servicenow.json
>
> # 3. Read its full task map — this is your reference
> jq '[.components[] | select(.type=="workflow") | select(.document.name | test("WORKFLOW_NAME"; "i"))] | first | .document | {tasks, transitions}' \
>   ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-servicenow.json
>
> # 4. Extract the specific task type you need
> jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "TASK_NAME")] | first | .value' \
>   ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-servicenow.json
> ```
>
> Replace `vendor-servicenow.json` with whichever asset file best matches your use case:
> - Adapter tasks (ServiceNow, Infoblox) → `vendor-servicenow.json`, `vendor-infoblox-nios-ddi.json`
> - Network device tasks (CLI, MOP) → `vendor-cisco-ios.json`, `vendor-arista-eos.json`, `vendor-juniper-junos.json`
> - IPAM/inventory → `vendor-netbox.json`
> - Data transformations → `itential-platform-data-manipulation.json`
> - Config management (RunCommandTemplate, itential_cli) → `itential-platform-configuration-management.json`
> - LCM action workflows → `helpers/assets/lcm/lcm-vxlan-fabric-services-project.json`

---

**Step 0: Decompose before you build.**

Before writing any JSON, identify the parent/child split from the solution design. Ask for each phase:

- Can this phase be run and tested on its own? → **Child workflow**
- Does it loop over multiple items (devices, records)? → **Child workflow with `loopType`**
- Is it reusable across other use cases? → **Child workflow**
- Is it a simple sequential step with no independent test value? → **Task in orchestrator**

Build order is always: **children first, orchestrator last.** The orchestrator is just childJob calls to tested children — it should not contain raw adapter tasks unless there is no logical way to split.

**Read a full workflow from asset projects before building any multi-workflow solution:**
```bash
# Parent → childJob → evaluation pattern
jq '[.components[] | select(.type=="workflow") | select(.document.name | test("Upgrade|Runner"))] | first | .document | {name,tasks,transitions}' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json

# childJob loop with data_array
jq '[.components[] | select(.type=="workflow") | select(.document.name | test("Chunk|Loop"))] | first | .document | {name,tasks,transitions}' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/itential-platform-configuration-management.json
```

**Step 1: Find tasks.** Search `tasks.json` for the tasks you need:
```bash
jq '.[] | select(.name | test("keyword"; "i")) | {name, app, type, location, canvasName, displayName}' {use-case}/tasks.json
```

**Step 2: Resolve adapter app names.** For adapter tasks, the `app` in tasks.json is WRONG. Look up the correct name:
```bash
jq '.[] | select(.name | test("keyword"; "i")) | {name, type}' {use-case}/apps.json
```
Also get the adapter instance name:
```bash
jq '.results[] | select(.package_id | test("keyword"; "i")) | {id, state}' {use-case}/adapters.json
```
You now have three values: `app` (from apps.json), `adapter_id` (from adapters.json `.id`), and `displayName` (from tasks.json).

**Step 3: Fetch task schemas.** Get the full input/output schema for every task you'll use:
```
POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true
```
```json
{
  "inputsArray": [
    {"location": "Adapter", "pckg": "Servicenow", "method": "createChangeRequest"},
    {"location": "Application", "pckg": "WorkFlowEngine", "method": "query"}
  ]
}
```
Use the `pckg` value from apps.json (Step 2), NOT tasks.json. Save the response to `{use-case}/task-schemas.json`.

**Step 4: Map schema to workflow task JSON.** For each task, transform the schema into a workflow task:

Schema response:
```json
{
  "name": "createChangeRequest",
  "variables": {
    "incoming": {
      "body": {"type": "object", "description": "Request body"}
    },
    "outgoing": {
      "result": {"type": "object", "description": "Response"}
    }
  }
}
```

Becomes this workflow task (extract a real adapter task from an asset project first — e.g. `jq '[.components[].document.tasks // {} | to_entries[] | select(.value.location == "Adapter")] | first | .value' ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-servicenow.json`):
```json
{
  "a1b2": {
    "name": "createChangeRequest",
    "canvasName": "createChangeRequest",
    "summary": "Create Change Ticket",
    "description": "Creates a ServiceNow change request",
    "location": "Adapter",
    "locationType": "Servicenow",
    "app": "Servicenow",
    "type": "automatic",
    "displayName": "ServiceNow",
    "variables": {
      "incoming": {
        "body": "$var.e1a1.merged_object",
        "adapter_id": "$var.job.adapter_id"
      },
      "outgoing": {
        "result": null
      },
      "error": "",
      "decorators": []
    },
    "groups": [],
    "actor": "Pronghorn",
    "scheduled": false,
    "nodeLocation": {"x": 700, "y": 600}
  }
}
```

**Mapping rules:**
- `name`, `canvasName` → from tasks.json
- `app`, `locationType` → from apps.json (NOT tasks.json)
- `displayName` → from tasks.json
- `location` → `"Adapter"` or `"Application"` (from tasks.json)
- `type` → from tasks.json directly — do not guess. It is per-task, not per-app. Read it alongside name, app, location, and canvasName: `jq '.[] | select(.name == "taskName") | {name, app, type, canvasName, location}' tasks.json`
- `actor` → `"Pronghorn"` for all tasks except childJob (which uses `"job"`)
- `incoming` → each schema key becomes a variable. Wire with `$var` for top-level values
- `outgoing` → set to `null` (capture later with `$var.taskId.outVar`)
- **Add `adapter_id`** to incoming for adapter tasks (not in schema, always required)
- **Add `error` and `decorators`** to variables block

**Step 5: Handle object inputs.** If a task's incoming variable is `type: "object"` (like `body`), you CANNOT put `$var` references inside it — they won't resolve. Use a `merge` task before it:

```json
{
  "e1a1": {
    "name": "merge",
    "canvasName": "merge",
    "summary": "Build Request Body",
    "app": "WorkFlowEngine",
    "type": "operation",
    "variables": {
      "incoming": {
        "data_to_merge": [
          {"key": "short_description", "value": {"task": "job", "variable": "short_description"}},
          {"key": "description", "value": {"task": "job", "variable": "description"}}
        ]
      },
      "outgoing": {"merged_object": null}
    },
    "actor": "Pronghorn"
  }
}
```
Then wire the adapter task's `body` to `"$var.e1a1.merged_object"`.

**Step 6: Handle opaque schemas.** Some task schemas show `body: {type: "object"}` with no inner field details. The adapter validates internally. To discover required fields:
1. Try creating with minimal fields — the error message lists what's missing (e.g., `"must have required property 'summary'"`)
2. Check `openapi.json` for the adapter's endpoint schema
3. Call the adapter directly: `POST /{adapter_id}/{method}` with `{}` body — read the validation error

**Step 7: Wire transitions.** Every adapter task needs BOTH success and error transitions:
```json
"transitions": {
  "a1b2": {
    "b2c3": {"type": "standard", "state": "success"},
    "ef01": {"type": "standard", "state": "error"}
  }
}
```
If both success and error need to reach `workflow_end`, route error to an intermediate `newVariable` task first (JSON can't have duplicate keys).

**Step 8: Add inputSchema/outputSchema.** List all job variables the workflow expects as input and produces as output.

**Step 9: Pre-submit checklist.**
- [ ] Task IDs are hex-only (`[0-9a-f]{1,4}`)
- [ ] `app` and `locationType` values come from apps.json `.name`, NOT tasks.json and NOT the adapter instance name (e.g., `EmailOpensource` not `email`)
- [ ] `adapter_id` is the adapter **instance** name (e.g., `email`), NOT the type name
- [ ] `adapter_id` values come from `adapters.json` `.results[].id` — NEVER from the spec's adapter identity table. The spec is a design document; `adapters.json` is the source of truth for the target environment.
- [ ] `canvasName` values come from tasks.json `canvasName` field
- [ ] Every adapter task has `adapter_id` in incoming
- [ ] Every adapter task has an error transition
- [ ] `evaluation` tasks have both success AND failure transitions
- [ ] `evaluation` operators are from the closed enum (`contains, !contains, <, <=, >, >=, ==, !=`) — no others exist
- [ ] `evaluation` `operand_2` literal values containing regex metacharacters (`.`, `(`, `)`, `[`, `]`, `?`, `+`, `*`, `|`) are properly escaped, OR stored in a `newVariable` constant-holder task to avoid `incomingRefs` cache issues after API PUT
- [ ] No `$var.<taskId>.<out>` references inside nested forEach bodies — use `$var.job.<varName>` instead
- [ ] Incoming variable types match task schema exactly (arrays for `to`/`cc`/`bcc`, numbers for `page`/`pageSize`, etc.)
- [ ] No `$var` references inside nested objects (use merge/makeData)
- [ ] merge uses `"variable"`, childJob uses `"value"`
- [ ] No `{task:"job", variable:"x"}` in merge/childJob for workflow-internal variables — `{task:"job"}` refs add `x` to `inputSchema.required`, prompting operators for values that should be internal. Use the producing task ref instead (query→`return_data`, newVariable→`value`, makeData→`output`, merge→`merged_object`)
- [ ] If a `query` downstream of a `childJob` returns null despite the child succeeding: check whether `"obj": "$var.<childJobId>.job_details"` is resolving — on some platform versions it is treated as a literal string. Fix: insert a `merge` task between childJob and query using `{"task": "<childJobId>", "variable": "job_details"}` in `data_to_merge`, then point `obj` to `$var.<mergeId>.merged_object` (see Guide 4)
- [ ] childJob has `actor: "job"`, all others have `actor: "Pronghorn"`
- [ ] `workflow_end` transition is empty `{}`
- [ ] Canvas layout follows the vertical spacing convention — non-forked sequences on a constant-x spine, fork branches offset to `spine±264` and stay in their own column until convergence
- [ ] No transition lines cross task nodes (the spine column is empty between a fork and its convergence point)
- [ ] Sequential y-delta ~108px (tight grid)
- [ ] **LCM Create actions only:** the instance-write merge task's `data_to_merge` covers every field in the resource model's `schema.required` array — missing even one field causes an instance write failure after provisioning (resources are orphaned from LCM). Read the model's `schema.required` before building the merge task: `jq '.schema.required' helpers/assets/lcm/<model>.json`
- [ ] **ViewData manual tasks:** `view` is a top-level field; `incoming.variables` is present (even if `{}`); `displayName: "Tools"`, no `actor` field
- [ ] **restCall downstream query:** path targets body field directly (e.g., `"access_token"`) — NOT `"response.access_token"` (restCall has no wrapper, unlike adapter tasks)
- [ ] **childJob loop:** if child workflow has `inputSchema.required` fields beyond what each `data_array` element contains, use the forEach enrichment pattern (forEach → merge → arrayPush) to add shared fields into each element before the childJob loop; set `variables: {}` on the childJob
- [ ] **forEach body:** `incoming` contains ONLY `data_array` (no `job_id`); loop body tasks have no external error transitions; last body task has an empty `{}` transition; `$var.job.<varName>` inside loop body instead of `$var.<taskId>.<output>`
- [ ] **makeData with childJob-sourced merge:** if a merge task references a childJob variable, do NOT wire that merge's `merged_object` into `makeData.incoming.variables` — use `query` to extract individual values first

**Complete working example:** Read the ServiceNow "Create Change Request" workflow before building — it demonstrates merge → adapter create → query → adapter update with error transitions:
```bash
jq '[.components[] | select(.type=="workflow") | select(.document.name | test("Create Change"))] | first | .document' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-servicenow.json
```

**How the example works — what each task does and why:**

```
workflow_start → e1a1 (merge) → a1b2 (createChangeRequest) → b2c3 (query) → c3d4 (updateChangeRequest) → workflow_end
                                  ↓ error                                      ↓ error
                                ef01 (newVariable) ────────────────────────────→ workflow_end
```

| Task ID | Task | Why it's there | Key fields |
|---------|------|----------------|------------|
| `e1a1` | `merge` | Builds the `body` object. `$var` can't resolve inside nested objects, so merge assembles the object from individual variables. | `data_to_merge` uses `"variable"` (NOT `"value"`). Needs at least 2 items. |
| `a1b2` | `createChangeRequest` | Adapter call. `body` wired to `$var.e1a1.merged_object` (merge output). | `app`/`locationType` from apps.json (`Servicenow`), NOT tasks.json (`ServiceNow`). `adapter_id` added manually (not in schema). `type: "automatic"`. |
| `b2c3` | `query` | Extracts the change ID from the adapter response. | `query: "response.id"` — adapters transform responses, don't assume native API shape. |
| `c3d4` | `updateChangeRequest` | Second adapter call using the extracted ID. | `changeId` wired from `$var.job.changeId` (set by query's outgoing). |
| `ef01` | `newVariable` | Error handler. Adapter error transitions route here. | Exists because JSON can't have duplicate keys — can't route both success and error to `workflow_end` from the same task. |

**Field mapping — where each value comes from:**

| Workflow task field | Source | Example |
|---------------------|--------|---------|
| `name` | tasks.json `.name` | `createChangeRequest` |
| `canvasName` | tasks.json `.canvasName` | `createChangeRequest` (can differ: `arrayPush`→`push`) |
| `app` | **apps.json** `.name` (adapter **type** name) | `Servicenow`, `EmailOpensource` (NOT `email`, NOT `ServiceNow` from tasks.json) |
| `locationType` | Same as `app` for adapters, `null` for applications | `Servicenow`, `EmailOpensource` |
| `displayName` | tasks.json `.displayName` | `ServiceNow`, `email` |
| `location` | tasks.json `.location` | `Adapter` or `Application` |
| `type` | tasks.json `.type` — read directly, do not guess (per-task, not per-app) | varies |
| `actor` | `"Pronghorn"` always, except childJob which uses `"job"` | `Pronghorn` |
| `adapter_id` | adapters.json `.results[].id` (adapter **instance** name) | `servicenow-prod`, `email` — this goes in `incoming`, NOT in the task-level `app` field |
| incoming vars | From task schema (multipleTaskDetails) | `body`, `changeId` |
| outgoing vars | From task schema, set to `null` | `result` |

### Guide 2: Debug a failed job

**Step 1:** Get the job:
```
GET /operations-manager/jobs/{jobId}
```

**Step 2:** Check `data.status`. If `"error"`, read `data.error[]`:
```
data.error[].task → failing task ID
data.error[].message.IAPerror.displayString → human-readable error
```

**Step 3:** Match the error to a fix:

| Error message | Cause | Fix |
|---------------|-------|-----|
| "Schema validation failed on must have required property 'X'" | Missing field in adapter body | Add the field to merge task |
| "Method not found" | Wrong task name or app | Check tasks.json and apps.json |
| "No available transitions" | Missing error transition | Add `"state": "error"` transition |
| "Cannot find workflow" | childJob ref broken after project move | Update `workflow` field with `@projectId:` prefix |
| "Referenced job variable: undefined" | merge uses `"value"` instead of `"variable"` | Change to `"variable"` in `data_to_merge` |
| Job stuck in `"running"` | No error transition on failed task | Add error transition |

**Step 4:** Fix locally, PUT to update, re-run. Don't recreate — updating preserves the ID.

### Guide 2b: Work with any unfamiliar adapter task

Follow Guide 1 Steps 1-6 for discovery. Quick reference for the lookup commands:

```bash
# Step 1 — find the task
jq '.[] | select(.app | test("meraki";"i")) | {name, app, displayName}' {use-case}/tasks.json

# Step 2 — get the correct app name (tasks.json app field is often wrong for adapters)
jq '.[] | select(.name | test("meraki";"i")) | {name, type}' {use-case}/apps.json

# Step 2 — get the adapter instance name
jq '.results[] | select(.package_id | test("meraki";"i")) | {id, state}' {use-case}/adapters.json

# Step 3 — fetch the task schema
# POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true
# {"inputsArray": [{"location": "Adapter", "pckg": "<app from apps.json>", "method": "<task name>"}]}
```

You now have three values: `app` (from apps.json), `adapter_id` (from adapters.json `.id`), `displayName` (from tasks.json). Two things to pay extra attention to beyond Guide 1:

**Enforce data types from the schema.** When the schema says `"type": "array"`, you MUST pass an array — even for single values:
- `"to": "user@example.com"` → WRONG. Use `"to": ["user@example.com"]`
- `"pageSize": "100"` → WRONG if schema says number. Use `"pageSize": 100`
- `"cc": ""` → OK only if schema allows string; if array, use `"cc": []`

Always check `task-schemas.json` for the exact type of each incoming field before wiring.

**Inspect the actual response before wiring a query path.** Adapter responses are transformed — they do not match the native API's structure. After a successful test run:
1. `GET /operations-manager/jobs/{jobId}` — find the task in `data.tasks` by its task ID
2. Read the task's outgoing variables — that is the real response object
3. Use `jq` to explore: `jq '.data.tasks["a1b2"]' job.json`
4. Wire the `query` path from what you see — not from the upstream API docs

**End-to-end sequence:**
```
1. tasks.json search   → found "getDevice", app "networkAdapter"
2. apps.json lookup    → correct app name is "NetworkAdapter" (capital N)
3. adapters.json       → adapter_id is "network-prod-1"
4. multipleTaskDetails → incoming: {deviceId: string}, outgoing: {result: object}
5. Build + test        → job completes
6. Inspect job         → result is {"response": {"hostname": "...", "model": "..."}}
7. Wire query path     → "response.hostname" (NOT "result.hostname" or "data.hostname")
```

### Guide 3: Add a task to an existing workflow

**Step 1:** Extract the task structure from an asset project that uses the same task type:
```bash
# Adapter task (e.g., ServiceNow)
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.location == "Adapter")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-servicenow.json

# Application task (WorkFlowEngine)
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.app == "WorkFlowEngine" and .value.name != "childJob")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/itential-platform-configuration-management.json

# childJob
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "childJob")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json
```

**Step 2:** Fill in the fields using the mapping rules from Guide 1 Step 4.

**Step 3:** Generate a hex task ID (e.g., `d4e5`) — must be `[0-9a-f]{1,4}`.

**Step 4:** Add the task to `tasks` and add transitions. Remember error transitions on adapter tasks.

**Step 5:** Update via `PUT /automation-studio/automations/{id}` with `{"update": {...}}`.

### Guide 4: Build a childJob (parent calls child workflow)

childJob has two modes. Both are tested and verified on a live platform.

#### Mode A: Single child — pass variables with `{"task","value"}`

The parent passes specific variables to one child workflow run.

**Parent childJob task:**
```json
{
  "a1a1": {
    "name": "childJob",
    "canvasName": "childJob",
    "summary": "Run Single Child",
    "location": "Application",
    "locationType": null,
    "app": "WorkFlowEngine",
    "type": "operation",
    "displayName": "WorkFlowEngine",
    "variables": {
      "incoming": {
        "task": "",
        "workflow": "My Child Workflow",
        "variables": {
          "deviceName": {"task": "job", "value": "targetDevice"},
          "action": {"task": "static", "value": "validate"}
        },
        "data_array": "",
        "transformation": "",
        "loopType": ""
      },
      "outgoing": {"job_details": null}
    },
    "actor": "job"
  }
}
```

**Variable passing rules (uses `"value"`, NOT `"variable"`):**
- `{"task": "job", "value": "targetDevice"}` → passes the parent's `targetDevice` job variable to the child as `deviceName`
- `{"task": "static", "value": "validate"}` → passes the literal string `"validate"`
- `{"task": "b2c3", "value": "return_data"}` → passes a previous task's output (preferred for runtime data)

> **WARNING — `{task:"job"}` refs in childJob variables add fields to `inputSchema.required`** — same behavior as merge (see `### merge` section). Only use `{task:"job", value:"x"}` for genuine workflow inputs. For runtime data produced by earlier tasks, use `{task:"<taskId>", value:"<outVar>"}` to reference the producing task directly.

> **WRONG for task output refs in childJob:**
> `{"task": "b2c3", "variable": "return_data"}` — `"variable"` is for merge/evaluation only.
> In childJob, ALL refs (job, static, AND task output) use `"value"`. Using `"variable"` causes `undefined.indexOf()` at job start time (P6.4.0+) — the workflow fails before any task runs.

**Extracting single child output:**
```json
{
  "b2b2": {
    "name": "query",
    "variables": {
      "incoming": {
        "pass_on_null": false,
        "query": "taskStatus",
        "obj": "$var.a1a1.job_details"
      },
      "outgoing": {"return_data": "$var.job.childStatus"}
    }
  }
}
```
Query uses flat variable names — `"taskStatus"`, NOT `"variables.job.taskStatus"`.

**If the query returns null even though the childJob succeeded** — the `$var` form in `obj` may not resolve on your platform version. Use the merge+taskRef workaround:
```
a1a1 (childJob) → m1m1 (merge: captures job_details via taskRef) → b2b2 (query: reads merged_object)
```
```json
{
  "m1m1": {
    "name": "merge",
    "variables": {
      "incoming": {
        "data_to_merge": [
          {"task": "a1a1", "variable": "job_details"},
          {"task": "static", "value": {}}
        ]
      },
      "outgoing": {"merged_object": null}
    }
  },
  "b2b2": {
    "name": "query",
    "variables": {
      "incoming": {
        "pass_on_null": false,
        "query": "taskStatus",
        "obj": "$var.m1m1.merged_object"
      },
      "outgoing": {"return_data": "$var.job.childStatus"}
    }
  }
}
```
The static `{}` second item is required — merge needs at least 2 items in `data_to_merge`.

#### Mode B: Loop — one child per item in `data_array`

Each element in `data_array` becomes the child's input variables for that iteration. Set `variables: {}` (empty).

**Parent childJob task:**
```json
{
  "a1a1": {
    "name": "childJob",
    "canvasName": "childJob",
    "summary": "Run Child Per Device",
    "variables": {
      "incoming": {
        "task": "",
        "workflow": "My Child Workflow",
        "variables": {},
        "data_array": "$var.job.devices",
        "transformation": "",
        "loopType": "parallel"
      },
      "outgoing": {"job_details": null}
    },
    "actor": "job"
  }
}
```

**Input:** `devices` is an array of objects. Each object becomes one child's variables:
```json
{
  "devices": [
    {"deviceName": "IOS-CAT8KV-1", "action": "backup"},
    {"deviceName": "IOS-CAT8KV-2", "action": "check"},
    {"deviceName": "EOS-AWS-1", "action": "backup"}
  ]
}
```

**Extracting loop output:** Query `"loop"` to get the results array:
```json
{
  "b2b2": {
    "name": "query",
    "variables": {
      "incoming": {
        "pass_on_null": false,
        "query": "loop",
        "obj": "$var.a1a1.job_details"
      },
      "outgoing": {"return_data": "$var.job.childResults"}
    }
  }
}
```
If the query returns null (platform-version-specific `$var` resolution issue), use the same merge+taskRef workaround described above (Mode A) — capture `job_details` via `{"task": "a1a1", "variable": "job_details"}` in merge, then query `$var.m1m1.merged_object`.

**Loop element completeness — required fields must be in each element (not in `variables`).**

The platform validates the child workflow's `inputSchema.required` against **each element's keys only**. Static `variables` set on the childJob task are NOT counted toward satisfying required fields. If your loop elements only contain per-iteration fields (e.g., `subnet_name`, `subnet_cidr`) but the child also requires shared fields (e.g., `subscription_id`, `region`), the validation fails before any iteration runs.

**Fix — forEach enrichment pattern:** enrich each element with the shared fields before the childJob loop, then set `variables: {}` on the childJob:

```
forEach (loop over elements) → merge (add shared fields to current_item) → arrayPush (append enriched element to new array)
                                                                                    ↓ (after forEach success)
childJob (data_array: enrichedArray, variables: {})
```

```json
// forEach outgoing binds current_item to job var
{"outgoing": {"current_item": "$var.job.currentElement"}}

// merge combines current element + shared fields
{"data_to_merge": [
  {"task": "forEachId", "variable": "current_item"},
  {"key": "subscription_id", "value": {"task": "job", "variable": "subscription_id"}},
  {"key": "region", "value": {"task": "job", "variable": "region"}}
]}
// → $var.mergeId.merged_object is the enriched element

// arrayPush appends to accumulator
{"incoming": {"job_variable": "enrichedElements", "item_to_push": "$var.mergeId.merged_object"}}

// childJob uses the enriched array and no static variables
{"data_array": "$var.job.enrichedElements", "variables": {}, "loopType": "parallel"}
```

**Loop output shape** (each element is a flat spread of the child's job variables):
```json
[
  {"status": "complete", "childJobLoopIndex": 0, "deviceName": "IOS-CAT8KV-1", "action": "backup", "taskStatus": "success"},
  {"status": "complete", "childJobLoopIndex": 1, "deviceName": "IOS-CAT8KV-2", "action": "check", "taskStatus": "success"},
  {"status": "complete", "childJobLoopIndex": 2, "deviceName": "EOS-AWS-1", "action": "backup", "taskStatus": "success"}
]
```

Use `"[**].taskStatus"` in a query to extract one field from all iterations.

#### childJob checklist
- [ ] `actor` is `"job"` (NOT `"Pronghorn"`)
- [ ] `task` is `""` (empty string)
- [ ] `job_details` outgoing is `null`
- [ ] All incoming fields present — even unused ones: `"data_array": ""`, `"transformation": ""`, `"loopType": ""`
- [ ] Variables use `{"task","value"}` NOT `$var` (single mode)
- [ ] `variables` is `{}` when using `data_array` (loop mode)
- [ ] Child workflow's `inputSchema.required` matches what you're passing
- [ ] `loopType`: `""` (single), `"parallel"` (simultaneous), `"sequential"` (one at a time)
- [ ] If a downstream `query` of a childJob returns null: the `"obj": "$var.<childJobId>.job_details"` form may not resolve on this platform version — use merge+taskRef workaround (see "Extracting single child output" above)

#### Building the child workflow

The child workflow must:
1. Accept inputs via `inputSchema` that match what the parent passes
2. Set output variables via `newVariable` or task outgoing → `$var.job.x`
3. Handle errors internally (try-catch pattern) so it always completes:
```
task --success--> newVariable("taskStatus" = "success") -> workflow_end
task --error--> newVariable("taskStatus" = "error") -> workflow_end
```
The parent can then check `taskStatus` from `job_details` to decide what to do.

---

## Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/automation-studio/projects/import` | **Import a project (preferred — atomic)** |
| POST | `/automation-studio/projects` | Create an empty project |
| GET | `/automation-studio/projects/{projectId}` | Get a project |
| PATCH | `/automation-studio/projects/{projectId}` | Update a project |
| DELETE | `/automation-studio/projects/{id}` | Delete a project |
| GET | `/automation-studio/projects/{id}/export` | Export project as JSON |
| POST | `/automation-studio/projects/{projectId}/components/add` | Add components (legacy) |
| DELETE | `/automation-studio/projects/{projectId}/components/{componentId}` | Remove component |

### Preferred: Import a project (atomic — all assets in one call)

**Always use import instead of create + add components.** Import creates the project with all workflows, templates, and MOP templates inside it in a single atomic call. No intermediate state, no broken childJob refs, no project-locking issues.

```
POST /automation-studio/projects/import
```

**Build all assets locally first, then import everything at once:**

```json
{
  "project": {
    "_id": "24-char-hex-mongodb-objectid",
    "iid": 1,
    "name": "My Project",
    "description": "...",
    "thumbnail": "",
    "backgroundColor": "#FFFFFF",
    "components": [
      {
        "iid": 1,
        "type": "workflow",
        "reference": "uuid-of-workflow",
        "folder": "/",
        "document": { "...full workflow object..." }
      },
      {
        "iid": 2,
        "type": "mopCommandTemplate",
        "reference": "@projectId: Template Name",
        "folder": "/",
        "document": { "...full MOP object..." }
      }
    ],
    "created": "2026-03-13T00:00:00.000Z",
    "createdBy": {"_id": "000000000000000000000000", "provenance": "CloudAAA", "username": "admin@itential"},
    "lastUpdated": "2026-03-13T00:00:00.000Z",
    "lastUpdatedBy": {"_id": "000000000000000000000000", "provenance": "CloudAAA", "username": "admin@itential"}
  }
}
```

**Import format rules (different from create/export):**

| Field | Import format | Notes |
|-------|--------------|-------|
| `encodingVersion` | **OMIT** from workflow documents | Causes silent component failure if included |
| `created_by` (workflow) | `{username, provenance, firstname, inactive, sso}` — NO `_id` | Different from project-level `createdBy` |
| `createdBy` (project) | `{_id, username, provenance}` — HAS `_id` | Different from workflow-level |
| `_id` (project) | Pre-compute 24-char hex string | So childJob refs can use `@{projectId}:` |
| Workflow `name` | Clean names — no prefix | Import adds `@projectId:` automatically |
| childJob `workflow` | Must include `@{projectId}:` prefix | Pre-wire using the same `_id` |
| `reference` (workflow) | UUID string | Becomes the workflow's `uuid` |
| `reference` (MOP) | `@{projectId}: Template Name` | String reference |
| `iid` (components) | Sequential integers starting at 1 | Incrementing ID |

Response:
```json
{
  "message": "Successfully imported project",
  "data": {"_id": "...", "name": "...", "components": [...]},
  "metadata": {"failedComponents": []}
}
```
**Check `metadata.failedComponents`** — empty array means success.

### Why import instead of create + move

| Problem | Create + move | Import |
|---------|--------------|--------|
| childJob refs | Break on move — manual fix needed | Pre-wired with `@projectId:` — just work |
| Project locking | Race conditions during move | Single atomic call |
| Intermediate state | Workflows exist outside project | Never |
| API calls | Create + create each asset + move + fix refs | One POST |
| Reproducibility | Hard to replay | `project-import.json` is the artifact |

### Legacy: Create + add components (avoid if possible)

Only use this for adding a single asset to an existing project after initial import.

```
POST /automation-studio/projects/{projectId}/components/add
```
```json
{
  "components": [
    {"type": "workflow", "reference": "uuid-...", "folder": "/"}
  ],
  "mode": "move"
}
```

**Warning:** Both `move` and `copy` rename assets with `@projectId:` prefix but do NOT update internal references (childJob `workflow` fields, template names). You must fix these manually.

**Component types:** `workflow`, `template`, `transformation`, `jsonForm`, `mopCommandTemplate`, `mopAnalyticTemplate`

### Update membership (full replacement)

**Before patching, always ask the engineer:** *"Who else should have access to this project? (usernames or group names)"*

Do not auto-discover or assume groups. Wait for the answer, resolve each name to a reference ID by scanning existing projects, then PATCH.

```
PATCH /automation-studio/projects/{projectId}
```

Use the helper: `${CLAUDE_PLUGIN_ROOT}/helpers/update/update-project-members.json`

Include ALL members in every PATCH — this is a full replacement. Omitting an existing member removes them.

**To resolve a username or group name to a reference ID**, scan existing projects:
```bash
for pid in $(curl -s "$BASE/automation-studio/projects?limit=100" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.data[]._id'); do
  curl -s "$BASE/automation-studio/projects/$pid" \
    -H "Authorization: Bearer $TOKEN" \
    | jq -r '.data.members[]? | [.type, .reference, (.username // .name)] | @tsv'
done | sort -u
```
If a name cannot be resolved, ask the engineer for the reference ID — do not guess.

### Resolve membership references from spec

> **_MANDATORY:_** Import sets the OAuth service account as project owner — not the UI user from the spec. The engineer specified in the spec's Project Membership table will be locked out of the project unless you PATCH membership immediately after import. This runs in **Phase 3 (Import)**, not Phase 6 (Deliver).

There is no user/group lookup API on the Itential platform. The only way to resolve a username (e.g., `joksan.flores@itential.com`) or group name (e.g., `solutions-engineers`) to a platform reference ID is by scanning existing projects' members.

**Step 1: Build a membership lookup table.**

The list endpoint (`GET /automation-studio/projects?limit=50`) does NOT include `username`/`name` on member objects — only individual `GET /automation-studio/projects/{id}` calls do. Scan all projects to build the lookup:

```bash
# Get all project IDs
PROJECT_IDS=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "$PLATFORM_URL/automation-studio/projects?limit=100" \
  | jq -r '.data[]._id')

# Build lookup table from individual GETs
> {use-case}/membership-lookup.txt
for pid in $PROJECT_IDS; do
  curl -s -H "Authorization: Bearer $TOKEN" \
    "$PLATFORM_URL/automation-studio/projects/$pid" \
    | jq -r '.data.members[]? | [.type, .reference, (.username // .name), .provenance] | @tsv'
done | sort -u >> {use-case}/membership-lookup.txt
```

Output format (TSV): `type  reference  username/name  provenance`

**Step 2: Match spec members to references.**

For each member in the spec's Project Membership table, find their `reference` ID in `membership-lookup.txt`:
```bash
grep "joksan.flores@itential.com" {use-case}/membership-lookup.txt
# → account  699a67bb...  joksan.flores@itential.com  CloudAAA
```

**Step 3: PATCH membership immediately after import.**

```
PATCH /automation-studio/projects/{projectId}
```
```json
{
  "members": [
    {"type": "account", "role": "owner", "reference": "699a67bb..."},
    {"type": "group", "role": "editor", "reference": "67c859..."}
  ]
}
```

> **If a username or group cannot be resolved from the lookup table, stop and ask the engineer.** Do not guess reference IDs or skip members.

**Baseline members (when no spec membership is defined):** If there is no Project Membership table in the spec, or when doing a freeform build/import outside the spec lifecycle, **ask the engineer:** *"Which user accounts or groups should have access to this project?"* — do not assume or skip. Once you have the names, resolve them via the lookup table above and PATCH immediately. Without this step the engineer will be locked out of the project in the IAP UI. See [#63](https://github.com/itential/builder-skills/issues/63)

### Project Thumbnail

| Operation | Endpoint |
|-----------|----------|
| Set | `PUT /automation-studio/projects/{id}/thumbnail` — body: `{"imageData": "<data-URI>", "backgroundColor": "<hex>"}` |
| Get | `GET /automation-studio/projects/{id}/thumbnail` — returns `{"data": {"image": "<data-URI>", "backgroundColor": "<hex>"}}` |

**`imageData` must be a full data URI — not raw base64.** Passing raw base64 without the `data:image/png;base64,` prefix returns HTTP 200 and stores the value, but the UI renders a black/blank image with no error.

```
data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...
```

Build the data URI in Python:
```python
import base64, io
buf = io.BytesIO()
img.save(buf, format='PNG')
data_uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
```

- **Optimal dimensions: 330 × 100 px** — matches the project card aspect ratio in Automation Studio
- Accepted formats: `jpg`, `jpeg`, `png` — max 1000 KB
- `backgroundColor` (hex, e.g. `"#1B2A4A"`) sets the card background color visible before the image loads

---

## JSON Forms

JSON Forms have their own dedicated skill — `app-json_forms`. See that skill for the form structure (`struct` / `schema` / `uiSchema` / `bindingSchema`), the static-enum vs. REST-bound vs. cascading dropdown (aka field dependency) patterns, the full API reference (including the bulk-only DELETE), and the manual-trigger wiring (`legacyWrapper: false`).

Helper templates for forms still live under `${CLAUDE_PLUGIN_ROOT}/helpers/`:
- `create-json-form.json` — static-enum dropdowns
- `create-json-form-rest-bound.json` — REST-bound or cascading dropdowns

---

## Operations Manager (Automations & Triggers)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/operations-manager/automations` | Create an automation |
| GET | `/operations-manager/automations` | List automations |
| POST | `/operations-manager/triggers` | Create a trigger |
| PATCH | `/operations-manager/triggers/{id}` | Update a trigger |
| GET | `/operations-manager/triggers` | List triggers |

### Create a Manual Trigger with JSON Form

This is a two-step process: create the automation, then create a manual trigger that binds to it.

Use the helper template: `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-ops-manager-automation.json`

**Critical: `legacyWrapper` must be `false`.** When creating a manual trigger with a JSON form, set `legacyWrapper: false`. The default is `true`, which wraps form field values under `formData`, breaking the mapping to workflow job variables. With `legacyWrapper: false`, form field values map directly to workflow input variables by name.

**Required trigger fields:** `name`, `type` (`"manual"`), `enabled`, `actionType` (`"automations"`), `actionId`, `formId`, `legacyWrapper`

---

## Task Discovery

### Pull Task Catalog

**`{use-case}/tasks.json` should already exist** — pulled by `/solution-arch-agent` or `/explore` during feasibility. Do not re-pull if the file exists. If missing, fetch it:

```
GET /workflow_builder/tasks/list → save to {use-case}/tasks.json
GET /automation-studio/apps/list → save to {use-case}/apps.json
```

Search locally:
```bash
grep -i "template" {use-case}/tasks.json
jq '.[] | select(.app == "ConfigurationManager") | .name' {use-case}/tasks.json
```

### Look up task wiring in asset projects first

Before fetching schemas from the API, check if an asset project already has the task wired up. If it does, you get the exact field structure for free — no API call needed.

```bash
# Does any asset project use this task? Find it by task name:
grep -rl '"name": "TASK_NAME"' ${CLAUDE_PLUGIN_ROOT}/helpers/assets/

# Extract the wired task from the matching project:
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "TASK_NAME")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/MATCHING_FILE.json

# See which tasks a specific workflow uses:
jq '[.components[] | select(.type=="workflow") | select(.document.name | test("WORKFLOW"; "i"))] | first | .document.tasks | to_entries[] | {id:.key, name:.value.name, app:.value.app}' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/MATCHING_FILE.json
```

Asset project → best match by task type:
| Task | Best asset to check |
|------|-------------------|
| ServiceNow adapter tasks | `vendor-servicenow.json` |
| Infoblox / DNS / IPAM tasks | `vendor-infoblox-nios-ddi.json` |
| NetBox tasks | `vendor-netbox.json` |
| itential_cli, RunCommandTemplate, MOP tasks | `itential-platform-configuration-management.json`, `vendor-cisco-ios.json` |
| transformation (JST) | `vendor-netbox.json`, `itential-platform-data-manipulation.json` |
| childJob, evaluation, query, newVariable | any vendor project |
| LCM action workflow tasks | `helpers/assets/lcm/lcm-vxlan-fabric-services-project.json` |

### Get Full Task Schemas (only if not found in assets)

**Single task:**
```
GET /automation-studio/locations/{location}/packages/{pckg}/tasks/{method}?dereferenceSchemas=true
```

**Multiple tasks:**
```
POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true
```
```json
{
  "inputsArray": [
    {"location": "Application", "pckg": "WorkFlowEngine", "method": "query"},
    {"location": "Adapter", "pckg": "Servicenow", "method": "createChangeRequest"}
  ]
}
```

**Mapping from tasks.json → schema endpoint:**

| tasks.json field | Maps to |
|------------------|---------|
| `location` (`Application`/`Adapter`) | `{location}` |
| `app` (e.g., `TemplateBuilder`) | `{pckg}` |
| `name` (e.g., `renderJinjaTemplate`) | `{method}` |

**IMPORTANT:** The `pckg` value must come from `apps.json`, NOT `tasks.json`. The names can differ (e.g., tasks.json says `ServiceNow` but apps.json says `Servicenow`).

**Before fetching schemas:**
1. Search asset projects (above) — if found, use the wired example directly
2. Check if `{use-case}/task-schemas.json` exists — search it next
3. Only call `multipleTaskDetails` for tasks not found in either place
4. After fetching, append to `{use-case}/task-schemas.json`

### nodeLocation Spacing Convention

Workflows are laid out **top-to-bottom (vertical)** by default — this is the Itential best practice for readability and consistency, and matches the conventions used in the platform's working examples. Use horizontal only when the engineer explicitly asks for it.

#### Vertical Layout (default)

| Rule | Value |
|------|-------|
| Sequential tasks (y-delta) | +108px |
| Fork branch offset from spine (x-delta) | ±264px |
| Spine x | a constant column (e.g. `x=600`) |

**Clean canvas principles:**
- The **spine is a constant `x`** — non-forked sequences (start, single-thread tasks, end, convergence points) sit on it.
- **Forks split off the spine** — at a fork point, both outgoing branches leave the spine column. Place one at `spine - 264` and the other at `spine + 264`. The spine column stays empty between the fork and the convergence point so transition lines don't cross task nodes. Direction (which branch goes left vs. right) is the engineer's call — pick whatever keeps the picture clean.
- **Branches stay in their own column** until they converge.
- **Convergence tasks** (workflow_end, merges, error sinks) return to the spine `x`.
- **Tight y-spacing** — the canvas grid is dense; ~108px between sequential rows reads well. Don't pad to +250 or +360.
- **Preserve Studio-arranged positions** — if an engineer has arranged a workflow in Automation Studio, treat its `nodeLocation` values as authoritative. Always read from the live export before reimporting. Never recalculate positions from scratch on a workflow that has already been arranged.

Example — fork with a shared error handler (same pattern as ServiceNow "Create Change Request" in `helpers/assets/vendor-servicenow.json`):
```
workflow_start                        (x=600, y=200)
e1a1 merge                            (x=600, y=312)
a1b2 createCR  ── fork point ──       (x=600, y=420)
b2c3 query   [success branch]         (x=336, y=540)
c3d4 updateCR [success branch]        (x=336, y=636)   ef01 newVar [shared error handler]  (x=864, y=636)
workflow_end                          (x=600, y=804)
```

For a childJob phase with query + evaluation (single-thread, no fork → all on spine):
```
y=312  — childJob     (x=600)
y=420  — query        (x=600)   ← extracts taskStatus from job_details
y=528  — evaluation   (x=600)
```

#### Horizontal Layout (only when requested)

If the engineer explicitly asks for horizontal, swap x and y throughout: phases advance on x, fork branches offset on y, spine becomes a constant y row. Same magnitudes, opposite axes.

---

## Workflows

### Workflow Structure

```
POST /automation-studio/automations
```

Body wraps the workflow in `{"automation": {...}}`:

```json
{
  "automation": {
    "name": "My Workflow",
    "description": "Does something useful",
    "type": "automation",
    "canvasVersion": 3,
    "encodingVersion": 1,
    "font_size": 12,
    "tasks": {
      "workflow_start": {
        "name": "workflow_start",
        "groups": [],
        "nodeLocation": {"x": 600, "y": 200}
      },
      "a1b2": {
        "name": "query",
        "canvasName": "query",
        "summary": "Extract Data",
        "description": "Extracts field from response",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "pass_on_null": false,
            "query": "hostname",
            "obj": "$var.job.deviceData"
          },
          "outgoing": {
            "return_data": "$var.job.deviceName"
          },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": {"x": 600, "y": 312}
      },
      "workflow_end": {
        "name": "workflow_end",
        "groups": [],
        "nodeLocation": {"x": 600, "y": 420}
      }
    },
    "transitions": {
      "workflow_start": {
        "a1b2": {"type": "standard", "state": "success"}
      },
      "a1b2": {
        "workflow_end": {"type": "standard", "state": "success"}
      },
      "workflow_end": {}
    },
    "groups": [],
    "inputSchema": {
      "type": "object",
      "properties": {
        "deviceData": {"title": "deviceData", "type": "object"}
      },
      "required": ["deviceData"]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "deviceName": {"title": "deviceName", "type": "string"}
      }
    }
  }
}
```

**Update a workflow:**
```
PUT /automation-studio/automations/{id}
```
```json
{"update": { ...same structure as automation object... }}
```

**Project-scoped name required on PUT.** If the workflow belongs to a project, the `name` field in the `update` body must include the `@<projectId>: ` prefix — even if the workflow was created without it:
```json
{"update": {"name": "@69f10abc: My Workflow", "tasks": {...}, "transitions": {...}}}
```
Sending the bare name (`"name": "My Workflow"`) returns `{"error": {"message": "Name must begin with '@projectId: '"}}`.

Asymmetry: workflow **CREATE** (`POST /automation-studio/automations`) does NOT require the prefix — the platform applies it when the workflow is added to a project. But **PUT-update** always requires it for project-member workflows.

Always read the workflow before updating (`GET /automation-studio/workflows/detailed/{name}` or export the project) to get the current scoped name. See [Rule 24](#) and [issue #55](https://github.com/itential/builder-skills/issues/55).

### Task Fields

| Field | Application Tasks | Adapter Tasks |
|-------|-------------------|---------------|
| `name` | Method name from tasks.json | Method name from tasks.json |
| `canvasName` | From tasks.json `canvasName` field (may differ from `name`: `arrayPush`→`push`) | Same |
| `location` | `"Application"` | `"Adapter"` |
| `locationType` | `null` | Same as `app` |
| `app` | App name (e.g., `WorkFlowEngine`) | From `apps.json` (NOT tasks.json) |
| `type` | `"automatic"` or `"operation"` — read from tasks.json `.type`, do not guess |
| `actor` | `"Pronghorn"` | `"Pronghorn"` |
| `displayName` | App name | May differ from `app` |

**Adapter tasks also require `adapter_id`** in incoming variables — the adapter instance name from `health/adapters`.

### Task Access Control (`groups`)

The `groups` field on a task definition is **task-level GBAC** — group-based access control that restricts which IAP groups can see, claim, and complete a manual task in the Job Inbox.

| Field | Type | Meaning |
|---|---|---|
| `groups` *(plural)* | `string[]` | GBAC. Each entry is a group's MongoDB `_id` (24-char hex). Empty `[]` means no task-level restriction. |
| `group` *(singular, optional)* | `string` | Canvas display category (e.g., `"Tools"`, `"JsonForms"`). Set by the Studio canvas. **NOT access control** — easy to confuse with `groups`. |

```json
{
  "name": "ViewData",
  "type": "manual",
  "app": "WorkFlowEngine",
  "view": "/workflow_engine/task/ViewData",
  ...
  "groups": ["69e65b4189b39131a9b8cce1"]
}
```

**Look up group IDs:**
- `GET /authorization/groups` — list groups (each has `_id` and `name`)
- `GET /authorization/groups/<id>` — resolve a single group

**Two GBAC scopes** — both use the same `string[]` shape (group `_id`s) but apply at different levels:
- **Per-task `groups`** (on the task definition, sibling of `name`/`app`/`type`) — gates access to a single manual task.
- **Top-level workflow `groups`** (sibling of `tasks`/`transitions` at the workflow level) — gates access to the workflow as a whole.

**Tasks of any type can carry `groups`**, but only `type: "manual"` tasks surface in the Job Inbox where GBAC actually gates user access. Leave it as `[]` on automatic tasks unless platform-specific docs say otherwise.

> **Edge cases not yet documented** — verify on your platform before relying on:
> - Semantics with **multiple group IDs** in the array (likely OR — any-of — but unverified)
> - Interaction between **task-level and workflow-level** `groups` (additive vs. override)
> - Whether `groups` accepts a **`$var` job-variable** for dynamic group resolution (almost certainly no — design-time only — but worth confirming)

### Task IDs

Task IDs must be **hex-only**: `[0-9a-f]{1,4}`. Non-hex IDs (e.g., `apush`) cause `$var` references to silently fail.

### Transitions

```json
"transitions": {
  "workflow_start": {
    "a1b2": {"type": "standard", "state": "success"}
  },
  "a1b2": {
    "c3d4": {"type": "standard", "state": "success"},
    "err1": {"type": "standard", "state": "error"}
  },
  "c3d4": {
    "workflow_end": {"type": "standard", "state": "success"}
  },
  "err1": {
    "workflow_end": {"type": "standard", "state": "success"}
  },
  "workflow_end": {}
}
```

**Transition states:**
- `success` — task completed without error (all tasks)
- `error` — task encountered errors (all tasks)
- `failure` — evaluation didn't match or query returned undefined (evaluation/query only)
- `loop` — forEach loop iteration (forEach only)

**Transition types:**
- `standard` — moves forward
- `revert` — moves backward to a previous task (retry loops)

**MANDATORY: Every adapter/external task needs an error transition.** Without one, errors cause "Job has no available transitions" and the job gets stuck forever.

**JSON duplicate key problem:** If both success and error need to go to `workflow_end`, you can't use `workflow_end` as a key twice. Route error to an intermediate task (e.g., `newVariable` to set error status), then route that to `workflow_end`.

### Create Response Shape

Both workflow and template creation return `{created, edit}` — NOT `{message, data, metadata}`:
```json
{
  "created": {"_id": "...", "name": "..."},
  "edit": "/automation-studio/#/edit?..."
}
```

---

## $var Resolution Rules

`$var` only resolves as **direct top-level incoming variable values:**

| Wiring | Works? | Why |
|--------|--------|-----|
| `"deviceName": "$var.job.x"` | Yes | Direct top-level value |
| `"variables": {"key": "$var.job.x"}` | **NO** | Nested inside object |
| `"body": {"data": "$var.job.x"}` | **NO** | Nested — stored as literal string |

**Workaround:** Use `merge`, `makeData`, or `query` to build the nested object, then reference the task's output with `$var.taskId.merged_object`.

**Task ID validation:** `$var.taskId.x` only resolves when `taskId` matches `[0-9a-f]{1,4}`. Non-hex IDs silently fail.

**Prefer task-to-task wiring:** When a task's output feeds directly into the next task's input, wire it as `$var.<taskId>.<outVar>` instead of bouncing through `$var.job.x`. Only use job variables when: (a) values cross non-adjacent tasks, (b) values need to be visible in job output, or (c) multiple downstream tasks need the same value. Direct task-to-task wiring reduces clutter and makes data flow easier to trace.

**`incomingRefs` cache — what PUT does and doesn't fix:**

| Scenario | Result | Fix |
|----------|--------|-----|
| New tasks added via PUT | incomingRefs **generated** — task-to-task `$var` refs resolve immediately | None needed |
| Existing task field values changed via PUT | incomingRefs **NOT regenerated** — literals/changed taskRefs resolve to `null` | Open in Studio → Save |
| `POST /workflow_builder/workflows/save` | Does NOT regenerate incomingRefs either | Open in Studio → Save |
| Evaluation silently returns `false` after PUT | Stale operand cache | Constant-holder workaround below, or Studio save |
| Workflow hangs at `workflow_start` (status: running forever) after PUT | Any task's incomingRefs stale | Recreate via fresh POST — more PUTs won't fix it |

**Constant-holder workaround (API-only, no Studio save needed):** store `operand_2` literal values in a `newVariable` task and reference via `{"task": "k_const", "variable": "value"}` — taskRef resolution bypasses the cache.

**`makeData` static `input` strings do NOT resolve after API create/PUT.** The `input` and `outputType` fields are backed by `job_data` (type `static`). Workaround: use `newVariable` with `value: [...]` (array literal) — `newVariable.value` resolves correctly after API create without a Studio save.

**`task: "static"` values broadly** are backed by `job_data` written at Studio-save time. Any static value (template strings, query paths, model IDs, inline constants in childJob `variables` dicts) resolves as `null` at runtime on a freshly API-imported workflow until saved through Automation Studio.

**Outgoing must write to job var for cross-task `$var` to be readable by downstream tasks.** Pattern: `"outgoing": {"result": "$var.job.raw_result"}` then downstream: `"obj": "$var.job.raw_result"`. If outgoing is `null`, the value is accessible via task iteration (`GET /operations-manager/tasks/{iterationId}`) but NOT via `$var.taskId.result` in downstream tasks at runtime. Use job vars for any result you need to pass forward.

**`POST /automation-studio/workflows/validate`** — runs pre-flight schema validation before create or update. Returns `{errors: [], warnings: []}`. An empty `errors` array means the workflow is schema-valid. Run this on every workflow before POSTing or PUTting.

---

## Utility Tasks (WorkFlowEngine)

These are built-in tasks that require no adapter. They handle data manipulation and control flow.

### query

Extract nested values from objects using dot-path syntax.

**Incoming:** `pass_on_null` (boolean), `query` (string — dot-path), `obj` (object — usually `$var` ref)
**Outgoing:** `return_data` (any)
**Transitions:** `success` (found), `failure` (null/undefined when `pass_on_null: false`)

```json
{
  "incoming": {
    "pass_on_null": false,
    "query": "response.id",
    "obj": "$var.a1b2.result"
  },
  "outgoing": {
    "return_data": "$var.job.changeId"
  }
}
```

**IMPORTANT: Don't guess the query path for adapter responses.** Adapters transform upstream API responses — the field path in the adapter's output is NOT the same as the native API's response structure. The adapter's `result` outgoing is always a `{response, headers, metrics}` object, never a primitive. When the upstream API returns a simple string (like Infoblox's `_ref`), it's at `result.response`, not `result` directly. Always verify the actual response shape from a test job (`GET /operations-manager/jobs/{jobId}` → `data.tasks`) before wiring a path.

### merge

Build an object from multiple resolved values. Primary workaround for `$var` not resolving inside nested objects.

**Incoming:** `data_to_merge` (array, min 2 items)
**Outgoing:** `merged_object` (object)

**IMPORTANT: The field is `"variable"` NOT `"value"`** in the reference objects inside `data_to_merge`.

**Reference format in `data_to_merge`:**
- `{"task": "job", "variable": "varName"}` — pull from a **user-supplied** job variable (input to the workflow)
- `{"task": "static", "variable": "literalValue"}` — literal value
- `{"task": "taskId", "variable": "outVar"}` — pull from a previous task's output

> **WARNING — `{task:"job"}` references add fields to `inputSchema.required`.**
> The platform scans every `data_to_merge` entry in merge tasks (and every `variables` entry in childJob) for `{task:"job"}` references and automatically adds that variable name to `inputSchema.required`. This means using `{task:"job", variable:"changeId"}` for a variable that was produced internally by a query task will prompt operators to supply `changeId` as a workflow input — even though it should never come from the user.
>
> **Rule:** only use `{task:"job"}` for variables that are genuine workflow inputs. For anything produced by an earlier task, use the producing task's ref directly:
>
> | Value source | Correct ref form |
> |---|---|
> | User workflow input | `{"task": "job", "variable": "x"}` |
> | `query` output | `{"task": "queryTaskId", "variable": "return_data"}` |
> | `merge` output | `{"task": "mergeTaskId", "variable": "merged_object"}` |
> | `newVariable` output | `{"task": "newVarTaskId", "variable": "value"}` |
> | `makeData` output | `{"task": "makeDataTaskId", "variable": "output"}` |
> | `parse` output | `{"task": "parseTaskId", "variable": "return_data"}` |
> | adapter task output | `{"task": "adapterTaskId", "variable": "result"}` |

```json
{
  "incoming": {
    "data_to_merge": [
      {"key": "hostname", "value": {"task": "static", "variable": "IOS-CAT8KV-1"}},
      {"key": "details", "value": {"task": "job", "variable": "deviceInfo"}},
      {"key": "config", "value": {"task": "a1b2", "variable": "renderedTemplate"}}
    ]
  },
  "outgoing": {
    "merged_object": "$var.job.requestBody"
  }
}
```

**Gotchas:** Requires at least 2 items (1 item = silently null). Outgoing MUST declare `"merged_object": null` (empty `{}` makes it unreachable). **Duplicate keys produce arrays** — merging `{"ip": "1.2.3.4"}` and `{"ip": "1.2.3.4"}` yields `{"ip": ["1.2.3.4", "1.2.3.4"]}`, not an overwrite. To avoid this, pass a pre-built object as a single workflow input variable instead of merging multiple objects with the same keys.

### parse

Convert a JSON string into a JavaScript object. Essential after extracting `result.stdout` from `runService` (which is always a string, even when the script printed valid JSON).

**Incoming:** `stringToParse` (string — the JSON string to parse)
**Outgoing:** `result` (object — the parsed object)

```json
{
  "name": "parse",
  "canvasName": "parse",
  "summary": "Parse JSON String",
  "location": "Application",
  "locationType": null,
  "app": "WorkFlowEngine",
  "type": "operation",
  "displayName": "WorkFlowEngine",
  "variables": {
    "incoming": {
      "stringToParse": "$var.a1b2.return_data"
    },
    "outgoing": {
      "result": "$var.job.parsedOutput"
    }
  },
  "actor": "Pronghorn"
}
```

**Common pattern — runService → query → parse:**
```
runService → query(result.stdout) → parse(stringToParse) → use parsed fields
```

After `parse`, fields are accessible: `$var.parseTask.result.hostname`, `$var.parseTask.result.status`, etc.

### evaluation

Conditional branching. **MUST have BOTH success AND failure transitions.**

**Incoming:** `all_true_flag` (boolean), `evaluation_groups` (array)
**Outgoing:** `return_value` (boolean)
**Transitions:** `success` (true), `failure` (false)

**Operator enum — closed set. Only these 8 are valid:**
```
contains, !contains, <, <=, >, >=, ==, !=
```
`regex`, `match`, `matches`, `contains_key`, `in`, `startsWith` — **do not exist**. An invalid operator silently returns `false` with empty outgoing and `finish_state: failure`. No error message. Always validate against this list before wiring. Source of truth: `openapi.json` at `components/schemas/workflow_engine_wfEngineCommon_evaluationItem/properties/operator/enum`.

**`contains` is regex-based, not substring.** `operand_2` is interpreted as a regex pattern. A literal like `9.2(4)` is parsed as regex — `.` matches any char, `(4)` becomes a capture group — and may match unintended strings or fail to match the intended one. Escape regex metacharacters in literal patterns: `9\.2\(4\)` not `9.2(4)`.

**`contains` also works for object-key presence** — it is the universal "does X contain Y" operator. On a string operand it does regex matching; on an object operand it tests key presence. There is no separate `contains_key` operator.

**Direct evaluation test (no workflow needed):**
```
POST /workflow_engine/runEvaluationGroups
{"evaluation_groups":[{"operator":"AND","evaluations":[{"operand_1":"<test input>","operator":"contains","operand_2":"<pattern>"}]}]}
```
Returns `true`/`false`. Invalid operators silently return `false`. Use this to validate operators and escape patterns before wiring them into a workflow.

**`incomingRefs` cache — API PUT does not regenerate it for existing task changes.** See the incomingRefs table in [$var Resolution Rules](#var-resolution-rules). Diagnostic sign: `GET /operations-manager/tasks/{iterationUUID}` shows `incomingRefs[n].taskId: null` or `taskPointer: "/variables/outgoing/undefined"`.

**Operand reference format (uses `"variable"`, same as merge):**
- `{"task": "job", "variable": "varName"}`
- `{"task": "static", "variable": "literalValue"}`

```json
{
  "incoming": {
    "all_true_flag": true,
    "evaluation_groups": [{
      "all_true_flag": true,
      "evaluations": [{
        "operand_1": {"variable": "status", "task": "job"},
        "operator": "==",
        "operand_2": {"variable": "success", "task": "static"}
      }]
    }]
  },
  "outgoing": {"return_value": null}
}
```

### childJob

Run another workflow as a sub-job. **Read a live childJob example first:**
```bash
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "childJob")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json
```

**Critical differences from normal tasks:**
- **`actor` MUST be `"job"`** — not `"Pronghorn"`
- **`task` MUST be `""`** (empty string)
- **`outgoing.job_details` MUST be `null`** — do NOT override with `$var.job.X`
- **All incoming fields required** — even unused ones: `"data_array": ""`, `"transformation": ""`, `"loopType": ""`

**Variables use `{"task", "value"}` syntax — NOT `$var`:**
```json
{
  "incoming": {
    "task": "",
    "workflow": "My Child Workflow",
    "variables": {
      "deviceName": {"task": "job", "value": "deviceName"},
      "configData": {"task": "a1b2", "value": "return_data"}
    },
    "data_array": "",
    "transformation": "",
    "loopType": ""
  },
  "outgoing": {"job_details": null}
}
```

**childJob uses `"value"`. merge/evaluation use `"variable"`. Do NOT mix them.**

**Variable passing:**
- `{"task": "static", "value": [...]}` — literal value
- `{"task": "job", "value": "varName"}` — parent job variable (must exist at start)
- `{"task": "taskId", "value": "outVar"}` — previous task's output (preferred for runtime data)

**Loop modes:** `loopType: ""` (single), `"parallel"` (multiple simultaneous), `"sequential"` (one at a time). With loops, use `data_array` (each element becomes a child job's variables) and set `variables: {}`.

**Querying childJob output:**
```json
{
  "name": "query",
  "variables": {
    "incoming": {
      "query": "taskStatus",
      "obj": "$var.f48f.job_details",
      "pass_on_null": false
    }
  }
}
```
Use flat variable names, NOT nested paths. For loop output: `"[**].fieldName"`.

### forEach

Iterate over an array. **Deprecated** — prefer `childJob` with `loopType`. Still common in existing workflows.

**Incoming:** `data_array` (array) — **ONLY `data_array`**. Do NOT include `job_id` in incoming — it triggers errors.
**Outgoing:** `current_item` (any)

**Transition pattern (critical):**
```
forEach --state:loop--> firstBodyTask -> ... -> lastBodyTask --(empty {})
forEach --state:success--> nextTaskAfterLoop
```

#### forEach constraints (all four are required)

1. **`incoming` must only contain `data_array`** — do NOT include `job_id` or any other field. Adding `job_id` causes errors at runtime.

2. **`$var.<taskId>.<output>` does NOT resolve inside the loop body** — string references like `$var.n01.current_item` silently resolve to `null` inside a forEach body. Use `$var.job.<varName>` instead (bind the forEach's outgoing to a job variable and reference that). This applies to ALL reference styles — even taskRef objects `{"task": "outerTask", "variable": "current_item"}` are unreliable inside a nested body.

3. **Loop body tasks cannot transition to tasks outside the loop** — no error transitions from loop body tasks to external error handlers. The `forEach` task itself handles exit via `state: "error"` on the forEach transition. Handle errors within the loop body, then let the forEach's error transition route out.

4. **The last loop body task signals loop-back with an empty `{}` transition** — do NOT add an explicit loop-back target pointing to forEach.

```json
"transitions": {
  "forEachTaskId": {
    "firstBodyTask": {"type": "standard", "state": "loop"},
    "nextTaskAfterLoop": {"type": "standard", "state": "success"},
    "errorHandlerTask": {"type": "standard", "state": "error"}
  },
  "lastBodyTask": {}
}
```

### newVariable

Create or set a job variable at runtime.

**Incoming:** `name` (string), `value` (any)
**Outgoing:** `value` (any)

```json
{
  "incoming": {"name": "taskStatus", "value": "success"},
  "outgoing": {"value": "$var.job.taskStatus"}
}
```

**GOTCHA:** `$var` inside `value` does NOT resolve. The literal string is stored. Use merge + query to build dynamic values.

### makeData

Construct data with `<!var!>` variable substitution.

**Incoming:** `input` (string with `<!var!>` placeholders), `outputType` (`"string"`/`"json"`/`"number"`/`"boolean"`), `variables` (object)
**Outgoing:** `output` (any)

**The `variables` field must be a resolved object.** Use merge first to build it, then pass via `$var.taskId.merged_object`:

```
merge (build variables object) → makeData (use $var.taskId.merged_object as variables)
```

> **WARNING — `makeData.incoming.variables` cannot use `$var` references to a merge that sources childJob output.**
> When a `merge` task's `data_to_merge` contains a childJob reference (e.g., `{"task": "childJobId", "variable": "job_details"}`), the platform cannot compile `$var.<mergeId>.merged_object` as a `taskRef` for `makeData.incoming.variables` — it is stored as a literal static string. Template substitution then operates on the literal string and emits unresolved placeholders.
>
> `query.incoming.obj` does NOT have this limitation — it resolves `$var.<mergeId>.merged_object` correctly even when the merge references childJob output.
>
> **Fix:** extract individual values from the childJob-sourced merge using `query` tasks, then pass those resolved scalars to makeData via a second merge (that contains only non-childJob refs). Do NOT feed a childJob-sourced merge directly into makeData's `variables`.

### delay

Pause execution. **Incoming:** `time` (integer, seconds). **Outgoing:** `time_in_milliseconds`.

### push / pop / shift

Array manipulation on job variables **by name** (plain string, NOT `$var` reference).

```json
{
  "incoming": {
    "job_variable": "collectedResults",
    "item_to_push": "$var.c3d4.return_data"
  }
}
```

**GOTCHA:** Pass `"myArray"`, NOT `"$var.job.myArray"`.

### deepmerge

Same as `merge` but merges nested objects recursively instead of overwriting top-level keys. Use when combining objects that share nested keys.

**Incoming:** `data_to_merge` (array, min 2 items — same format as merge)
**Outgoing:** `merged_object` (object)

### transformation

Perform JSON transformation using JST (JSON Schema Transformation).

**Incoming:** `tr_id` (string — transformation ID), `variableMap` (object — maps transformation inputs to data locations), `options` (object, optional — e.g., `{"extractOutput": true}`)
**Outgoing:** `outgoing` (any)

Used in childJob mode 3 (loop with transformation) to reshape each `data_array` element before passing to the child.

### decision

Multi-way branching based on conditions. Unlike `evaluation` (binary true/false), `decision` branches to different tasks based on multiple conditions.

**Incoming:** `decisionArray` (array of decision objects with conditions and target task IDs)
**Outgoing:** `return_value` (string — the ID of the next task)

### restCall

Make external HTTP calls from within a workflow. Use when calling APIs not exposed through adapters.

**Response shape — no wrapper.** `restCall` returns the **already-parsed JSON body directly** as the outgoing value. There is no `response` or `result` wrapper. Query paths target body fields directly:

```
Correct:   "query": "access_token"
Wrong:     "query": "response.access_token"   ← no response wrapper
Wrong:     "query": "result.access_token"     ← no result wrapper
```

This is the opposite of adapter tasks (e.g., `genericAdapterRequest`), which always wrap the upstream response in `{response, headers, metrics}`. Don't cross-apply the adapter query paths to `restCall` output — you'll get null every time.

### modify

Modify data by querying into an object and replacing with a new value.

**Incoming:** `object_to_update` (any), `query` (string — json-query path), `new_value` (any)
**Outgoing:** `updated_object` (any)

### validateJsonSchema

Validate JSON data against a JSON schema.

**Incoming:** `jsonData` (object), `schema` (object)
**Outgoing:** `result` (object — `{"valid": true}` or `{"valid": false}`)

### Additional Utility Tasks (60+)

Search `tasks.json` for the full catalog:
```bash
jq '.[] | select(.app == "WorkFlowEngine") | {name, summary}' {use-case}/tasks.json
```

| Category | Examples |
|----------|---------|
| String | `stringConcat`, `replace`, `split`, `toLowerCase`, `toUpperCase`, `trim`, `substring` |
| Array | `arrayConcat`, `arrayPush`, `sort`, `join`, `arraySlice`, `map`, `reverse` |
| Object | `assign`, `keys`, `values`, `objectHasOwnProperty`, `setObjectKey` |
| Time | `getTime`, `addDuration`, `convertTimezone`, `calculateTimeDiff` |
| Parse/Transform | `parse`, `transformation`, `stringify` |
| Tools | `restCall`, `csvStringToJson`, `excelToJson`, `asciiToBase64` |

**Reach for purpose-built tasks before chaining primitives.** Two tasks that are commonly underused:

- **`setObjectKey`** (WorkFlowEngine) — writes a value directly into a nested key of an existing object. Use instead of `query` + `merge` when updating a single field on an object already in `$var.job.*`.
- **`renderJinja2ContextWithCast`** (ConfigurationManager) — renders a Jinja2 template with the full job context automatically injected, plus optional type casting on the output. Use instead of `merge` → `renderJinja2` → `query` chains when the template needs access to existing job variables. Outputs `renderedTemplate` accessible via `$var.<taskId>.renderedTemplate`.

Fetch full schemas with `POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true`.

### Task Endpoint Patterns (Standalone Testing)

Some tasks have standalone REST endpoints — **faster than creating test workflows:**
- **WorkFlowEngine:** `POST /workflow_engine/{method}` (e.g., `/workflow_engine/query`) — requires `job_id` (use dummy ObjectId `"4321abcdef694aa79dae47ad"`)
- **MOP:** `POST /mop/RunCommandTemplate` — test command templates directly
- **TemplateBuilder:** `POST /template_builder/templates/{name}/renderJinja` with `{"context": {...}}` (note: `context`, not `variables`)

Most utility tasks (array ops, string ops, forEach, childJob, merge) do NOT have standalone endpoints. Test those by creating a minimal `start → task → end` workflow and running via `jobs/start`.

---

## Templates (Jinja2 / TextFSM)

```
POST /automation-studio/templates
```
```json
{
  "template": {
    "name": "VLAN_Interface_Config",
    "type": "jinja2",
    "group": "Cisco IOS",
    "command": "configure terminal",
    "description": "Generates VLAN interface config",
    "template": "interface Vlan{{ vlan_id }}\n description {{ description }}\n ip address {{ ip_address }} {{ subnet_mask }}\n no shutdown",
    "data": "{\"vlan_id\": 100, \"description\": \"Management\", \"ip_address\": \"10.0.1.1\", \"subnet_mask\": \"255.255.255.0\"}"
  }
}
```

**Required fields:** `name`, `group`, `command`, `description`, `template`, `data`, `type`

**Types:** `jinja2` (config generation) or `textfsm` (output parsing)

**Test rendering directly:**
```
POST /template_builder/templates/{name}/renderJinja
```
```json
{"context": {"vlan_id": 100, "description": "Management"}}
```

**Gotchas:**
- `group` cannot be empty or whitespace-only
- Use underscores in template names (e.g., `IOS_Switchport_Config`)
- `data` field is a JSON string, not an object
- Variable syntax is `{{ var }}` (Jinja2), NOT `$var` or `<!var!>`
- **No `from_json` filter** — Ansible's `from_json` Jinja2 filter does NOT exist in Itential's TemplateBuilder. If you need to parse a JSON string, use a `parse` task before the template render step, not a filter inside the template
- **`renderJinjaTemplate` as a workflow task** — use `TemplateBuilder.renderJinjaTemplate` with incoming `templateName` (string) and `variables` (object). Output is at `result.renderedTemplate` (string). Different from the standalone API endpoint which uses `context` instead of `variables`

---

## Command Templates (MOP)

MOP manages command templates for running CLI commands with validation rules. **MOP is read-only validation only — never use it to push config.**

**To push config to a device, use `itential_cli` via AGManager** — not MOP. The standard pattern for any config push delivery is:

```
Pre-Check (RunCommandTemplate child)
  → Push Configuration to Device (renderJinjaTemplate → dry run approval → itential_cli → commit approval → itential_cli)
  → Post-Check (RunCommandTemplate child)
  → runTemplatesDiff (compare pre vs post)
```

Read the Arista EOS "Push Configuration to Device - IAG" and "Command Template Runner" workflows before building any config push delivery:
```bash
jq '[.components[] | select(.type=="workflow") | select(.document.name | test("Push Config|Command Template"))] | .[].document | {name:.name, tasks:.tasks, transitions:.transitions}' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-arista-eos.json
```

### Create a Command Template

```
POST /mop/createTemplate
```
```json
{
  "mop": {
    "name": "Port_Turn_Up_Pre_Check",
    "description": "Validates interface and VLAN",
    "os": "",
    "passRule": true,
    "ignoreWarnings": false,
    "commands": [
      {
        "command": "show interface <!interface!>",
        "passRule": true,
        "rules": [
          {
            "rule": "line protocol is",
            "eval": "contains",
            "severity": "error"
          }
        ]
      },
      {
        "command": "show vlan brief",
        "passRule": true,
        "rules": [
          {
            "rule": "<!vlan_id!>",
            "eval": "contains",
            "severity": "error"
          }
        ]
      }
    ]
  }
}
```

**Variable syntax:** `<!variable_name!>` in both commands and rules (NOT `{{ }}` or `$var`)

### passRule Logic

- **Template-level `passRule: true`** = ALL commands must pass (AND)
- **Template-level `passRule: false`** = ONE command must pass (OR)
- **Command-level** = same logic for rules within a command

### Rule Evaluation

| Eval | Purpose | Example |
|------|---------|---------|
| `contains` | String exists in output | `"line protocol is"` |
| `!contains` | String does NOT exist | `"ERROR"` |
| `contains1` | String exists exactly once | `"Active"` |
| `RegEx` | Regex matches (capital R, E!) | `"/\\d+\\.\\d+/"` |
| `!RegEx` | Regex does NOT match | `"/ERROR/"` |
| `#comparison` | Extract + compare two values | See below |

**#comparison:** Extract values with regex, compare numerically:
```json
{
  "rule": "/Available: (\\d+)/",
  "ruleB": "/Total: (\\d+)/",
  "eval": "#comparison",
  "evaluator": ">=",
  "severity": "error"
}
```
Evaluators: `=`, `!=`, `<`, `>`, `<=`, `>=`, `%` (percentage)

**Flags:** `case: true` = case-INSENSITIVE (confusing name), `global: true`, `multiline: true` (RegEx only)

### Run a Command Template

**Standalone:**
```
POST /mop/RunCommandTemplate
```
```json
{
  "template": "Port_Turn_Up_Pre_Check",
  "variables": {"interface": "GigabitEthernet0/1", "vlan_id": "100"},
  "devices": ["IOS-CAT8KV-1"]
}
```

**In a workflow (MOP.RunCommandTemplate task):**
```json
{
  "incoming": {
    "template": "$var.job.templateName",
    "variables": "$var.job.templateVariables",
    "devices": "$var.job.devices"
  },
  "outgoing": {
    "mop_template_results": null
  }
}
```

### Response Shape

```json
{
  "all_pass_flag": true,
  "result": true,
  "name": "Port_Turn_Up_Pre_Check",
  "commands_results": [
    {
      "raw": "show interface <!interface!>",
      "evaluated": "show interface GigabitEthernet0/1",
      "all_pass_flag": true,
      "device": "IOS-CAT8KV-1",
      "response": "...command output...",
      "result": true,
      "rules": [{"rule": "line protocol is", "eval": "contains", "result": true}]
    }
  ]
}
```

### Update a Command Template

```
POST /mop/updateTemplate/{mopID}
```
`mopID` is the template name (URL-encoded). Body is `{"mop": {...}}` — **full replacement**, include ALL fields.

### Analytic Templates (Pre/Post Comparison)

```
POST /mop/createAnalyticTemplate
```
```json
{
  "name": "Interface_Change_Validation",
  "os": "cisco-ios",
  "passRule": true,
  "prepostCommands": [
    {
      "preRawCommand": "show interface GigabitEthernet0/1",
      "postRawCommand": "show interface GigabitEthernet0/1",
      "passRule": true,
      "rules": [
        {
          "type": "matches",
          "preRegex": "/line protocol is (\\w+)/",
          "postRegex": "/line protocol is (\\w+)/",
          "evaluator": "="
        }
      ]
    }
  ]
}
```

**In a workflow (MOP.runAnalyticsTemplate task):**
```json
{
  "incoming": {
    "pre": "$var.preCheckTaskId.mop_template_results",
    "post": "$var.postCheckTaskId.mop_template_results",
    "analytic_template_name": "Interface_Change_Validation",
    "variables": {}
  },
  "outgoing": {"analytic_result": null}
}
```

---

## Testing & Debugging

### Start a Job

```
POST /operations-manager/jobs/start
```
```json
{
  "workflow": "My Workflow Name",
  "options": {
    "description": "Test run",
    "type": "automation",
    "variables": {"deviceName": "IOS-CAT8KV-1"}
  }
}
```

Response: `{"message": "...", "data": {"_id": "jobId", "status": "running"}}`

### Check Job Status

```
GET /operations-manager/jobs/{jobId}
```

Response wrapped in `{message, data, metadata}`:
- `data.status` — `"running"`, `"complete"`, `"error"`, `"canceled"`
- `data.variables` — all job variables including outputs
- `data.error` — array of error objects on failure

### Debug Failed Jobs

1. `GET /operations-manager/jobs/{jobId}` — check `data.status`
2. If `"error"`, read `data.error[]` — each has `task` (ID) and `message.IAPerror.displayString`
3. Identify the failing task ID, check its `metrics.finish_state`

**Common failures:**
| Symptom | Cause | Fix |
|---------|-------|-----|
| "Method not found" validation error | Task name doesn't exist | Search `tasks.json` |
| "No available transitions" | Missing error transition | Add `"state": "error"` transition |
| `$var` resolves to literal string | Non-hex task ID or nested object | Check task IDs, use merge |
| "Cannot find workflow" | childJob ref broken after project move | Update `workflow` field with `@projectId:` prefix |
| Schema validation error | Wrong/missing fields | Check `task-schemas.json` |
| Adapter error | Wrong app name or adapter down | Check `apps.json` and `GET /health/adapters` |
| "No config found for Adapter: X" | `app` field uses adapter instance name instead of type name | `app`/`locationType` must be the **type** from `apps.json` (e.g., `EmailOpensource`), not instance name (e.g., `email`). Instance name goes in `adapter_id`. |
| Silent data mismatch | Field type doesn't match schema (string vs array) | Check `task-schemas.json` — pass arrays for array fields, numbers for number fields |

### Standalone Test Endpoints

Some tasks have REST endpoints for quick testing without creating workflows:
- **query:** `POST /workflow_engine/query` (needs dummy `job_id`)
- **Jinja2 render:** `POST /template_builder/templates/{name}/renderJinja` with `{"context": {...}}`
- **MOP:** `POST /mop/RunCommandTemplate` with `{"template": "name", "devices": [...], "variables": {...}}`

### Updating Assets (Edit Locally, PUT to Update)

| Asset | Create | Update | Delete |
|-------|--------|--------|--------|
| Workflow | `POST /automation-studio/automations` | `PUT /automation-studio/automations/{id}` with `{"update": {...}}` | `DELETE /workflow_builder/workflows/delete/{URL-encoded-name}` (by name, not ID) |
| Template | `POST /automation-studio/templates` | `PUT /automation-studio/templates/{id}` with `{"update": {...}}` | `DELETE /automation-studio/templates/{id}` |
| Command Template | `POST /mop/createTemplate` | `POST /mop/updateTemplate/{name}` with `{"mop": {...}}` (full replacement) | — |

**Pre-flight validate before every create or update:**
```
POST /automation-studio/workflows/validate
{"workflow": {...}}
→ {"errors": [], "warnings": []}
```
Empty `errors` = schema valid. Run this before every POST or PUT.

**Workflow rename:**
```
POST /workflow_builder/workflows/rename
{"workflow": {...full doc...}, "newName": "New Workflow Name"}
```
Renames in-place without recreating. Use instead of appending `[Fixed]` suffixes.

---

## Workflow Patterns

### Error Handling: Try-Catch

**In child workflows:** catch errors with `newVariable` to set a status flag:
```
task --success--> newVariable("taskStatus" = "success") -> workflow_end
task --error--> newVariable("taskStatus" = "error") -> workflow_end
```

**In parent workflows:** after childJob, extract and check:
```
childJob -> query (extract taskStatus from job_details) -> evaluation (== "success"?)
  |-- success -> continue
  |-- failure -> handle error
```

### Error Transitions on Adapter Tasks

Every adapter task needs both success and error transitions. Route errors to an intermediate `newVariable` task if both need to reach `workflow_end`:

```json
"transitions": {
  "a1b2": {
    "c3d4": {"type": "standard", "state": "success"},
    "err1": {"type": "standard", "state": "error"}
  },
  "err1": {
    "workflow_end": {"type": "standard", "state": "success"}
  }
}
```

### Manual Tasks (Human-in-the-Loop)

**ViewHTML** — renders an HTML string in a modal for operator review. Requires specific fields or it becomes a draft workflow:
```json
{
  "name": "ViewHTML", "canvasName": "ViewHTML",
  "location": "Application", "locationType": null, "app": "WorkFlowEngine",
  "type": "manual", "displayName": "Tools",
  "view": "/workflow_engine/task/ViewHTML",
  "taskVersion": 2, "hostApp": "@itential/app-operations_manager",
  "variables": {
    "incoming": {
      "header": "Report Title",
      "body": "$var.job.html_output",
      "variables": "",
      "btn_success": "Acknowledge",
      "btn_failure": ""
    },
    "outgoing": {}
  },
  "actor": "Pronghorn"
}
```
`view`, `taskVersion: 2`, and `hostApp` are all **required** — omitting any one causes "Manual Tasks require 'view' key" draft error.

**Read a live ViewData example** from the Cisco IOS upgrade workflow — it shows makeData → ViewData → success/failure branches in production:
```bash
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "ViewData")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json
```

Three rules that cause draft validation errors if missed:
1. `view` is a **top-level** field (sibling of `name`, `type`, `app`) — NOT inside `variables`. Missing it → `"Manual Tasks require 'view' key with path to task view"`.
2. `incoming.variables` **MUST be present** (value can be `{}` if unused). Missing it → `"Input: 'variables' is not defined in task model"`.
3. `displayName` must be `"Tools"` and `actor` must be `null` (no actor field) on manual tasks.

Note: production assets include `"error": ""` and `"decorators": []` in the variables block on ViewData tasks — these are added by Studio on export and are harmless. You do not need to add or remove them.

```json
{
  "name": "ViewData",
  "canvasName": "ViewData",
  "location": "Application",
  "app": "WorkFlowEngine",
  "displayName": "Tools",
  "type": "manual",
  "view": "/workflow_engine/task/ViewData",
  "variables": {
    "incoming": {
      "header": "Approval Required",
      "message": "Review and approve.",
      "body": "$var.job.dataToReview",
      "variables": "$var.job.dataToReview",
      "btn_success": "Approve",
      "btn_failure": "Reject"
    },
    "outgoing": {}
  },
  "groups": []
}
```

### ViewHTML (Manual Task — HTML Display)

Use `ViewHTML` when you need to display formatted HTML to an operator during a workflow — for reports, tables, or styled summaries. Same manual task rules as ViewData apply.

**Read a live ViewHTML example:**
```bash
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "ViewHTML")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json
```

Key differences from ViewData:
1. `view` is `/workflow_engine/task/ViewHTML`
2. `body` is a raw HTML string — use inline CSS (no `<style>` blocks), `<!var!>` syntax for variable substitution
3. `incoming.variables` is a **plain object** `{"varName": "value"}` that populates `<!var!>` placeholders in the HTML — NOT a `$var` reference
4. `displayName: "Tools"`, no `actor` field (same as ViewData)

```json
{
  "name": "ViewHTML",
  "canvasName": "ViewHTML",
  "location": "Application",
  "app": "WorkFlowEngine",
  "displayName": "Tools",
  "type": "manual",
  "view": "/workflow_engine/task/ViewHTML",
  "variables": {
    "incoming": {
      "header": "Report",
      "body": "<h2>Status: <!status!></h2><p>Device: <!device!></p>",
      "variables": {
        "status": "$var.job.deviceStatus",
        "device": "$var.job.deviceName"
      },
      "btn_success": "Continue",
      "btn_failure": "End"
    },
    "outgoing": {}
  },
  "groups": []
}
```

### autoApprove Pattern

Use an `evaluation` task to conditionally skip manual approval:

```
evaluation (autoApprove == true?)
  |-- success -> skip to next task (auto-approved)
  |-- failure -> ViewData (human reviews and approves/rejects)
```

The workflow accepts an `autoApprove` boolean input. When `true`, skips the manual step. Useful for CI/CD pipelines that run unattended vs interactive operator sessions.

### Revert Transitions (Retry Loops)

Use `"type": "revert"` transitions to go backward for retry scenarios:

```
renderTemplate -> viewConfig (approve/reject)
  |-- success -> pushConfig -> evalSuccess
  |                             |-- success -> end
  |                             |-- failure -> viewError (retry/abort)
  |                                             |-- success (retry) --revert--> renderTemplate
  |                                             |-- failure (abort) -> end
  |-- failure (reject) --revert--> renderTemplate
```

The `revert` transition moves execution back to a previous task, allowing the user to fix inputs and retry.

### Modular Workflow Design

- Build each child workflow independently testable via `jobs/start`
- Use `childJob` with `data_array` + `loopType: "parallel"` to fan out
- Check for existing workflows before building new ones
- Keep all asset JSON locally — edit locally, PUT to update

### Network Device Config Pattern

1. **MOP command templates** for validation checks only (show commands + rules)
2. **Jinja2 templates** to generate configuration
3. **Push config** via existing workflow or adapter task — ask the engineer
4. **Test CLI commands** on the actual device BEFORE building workflows

---

## Variable Syntax Reference

| Context | Syntax | Example |
|---------|--------|---------|
| Jinja2 templates | `{{ var }}` | `interface Vlan{{ vlan_id }}` |
| Command templates (MOP) | `<!var!>` | `show interface <!interface!>` |
| `makeData` input | `<!var!>` | `{"name": "<!name!>"}` |
| Workflow variable refs | `$var.job.x` or `$var.taskId.x` | `$var.job.deviceName` |
| childJob variable refs | `{"task":"job","value":"varName"}` | `{"task":"static","value":["a"]}` |
| merge/evaluation refs | `{"task":"job","variable":"varName"}` | `{"task":"static","variable":"success"}` |

**childJob uses `"value"`. merge/evaluation use `"variable"`. Do NOT mix them.**

---

## API Response Shapes

| Endpoint | Shape |
|----------|-------|
| `POST /operations-manager/jobs/start` | `{message, data: {_id, status}}` |
| `GET /operations-manager/jobs/{id}` | `{message, data: {status, variables, error}}` |
| `POST /automation-studio/projects` | `{message, data: {_id, name}}` |
| `POST /automation-studio/automations` | `{created: {_id, name}, edit: "..."}` |
| `POST /automation-studio/templates` | `{created: {_id, name}, edit: "..."}` |
| `GET /automation-studio/workflows` | `{items: [...], skip, limit, total}` |
| `GET /automation-studio/templates` | `{items: [...], skip, limit, total}` |

### Adapter Response Shapes

**Adapters transform upstream API responses.** Don't assume the native API's response structure. For example, ServiceNow's Table API returns `result.sys_id`, but the Itential adapter flattens it to `response.id`. Always verify by calling the adapter directly or checking `openapi.json`.

### Adapter URI Prefix

`genericAdapterRequest` auto-prepends the adapter's `base_path` to `uriPath`. Don't include `/api/v1` in `uriPath`. Use `genericAdapterRequestNoBasePath` to bypass.

---

## Gotchas

> **Pre-flight scan list — read this before every project import and job start.** This list is intentionally redundant with the body sections. The repetition is deliberate: scanning a flat list before submitting catches mistakes that are easy to miss when building task by task.
>
> **To add a new finding:** put the detail in the relevant body section first, then add a one-liner here pointing to it.

### Projects
1. **Use `POST /projects/import` to create projects with all assets atomically** — avoids broken childJob refs, project-locking issues, and intermediate state. Pre-compute `_id` so childJob `@projectId:` refs can be wired before push.
2. **Avoid create + move pattern** — moving assets renames them with `@projectId:` prefix but does NOT update internal references (childJob `workflow` fields, template names).
3. **Import format differs from create** — OMIT `encodingVersion` from workflow documents (causes silent component failure). Workflow `created_by` has NO `_id` but has `firstname`, `inactive`, `sso`. Project `createdBy` HAS `_id`.
4. **Component type is `mopCommandTemplate`** — not `mop`.
5. **Members PATCH is full replacement** — include ALL members or omitted ones are removed.
6. **Import sets the OAuth service account as project owner** — not the UI user. PATCH membership immediately after import (Phase 3, not Phase 6) or the spec engineer is locked out.
7. **`accessControl` in PATCH body is silently ignored** — API returns 200 but the field is a no-op. Always use the `members` array format (`[{type, reference, role}]`).

### Workflows
8. **`canvasName` must come from `tasks.json`** — some differ from method name: `arrayPush`→`push`, `stringConcat`→`concat`. Wrong `canvasName` causes silent `$var` failures.
9. **Task IDs must be hex `[0-9a-f]{1,4}`** — non-hex causes silent `$var` failure.
10. **Validation errors = draft workflow** that cannot be started. Run `POST /automation-studio/workflows/validate` before every create or update.
11. **`$var` inside nested objects doesn't resolve** — use merge/makeData/query to build the object first.
12. **`stringConcat` does not resolve `$var` inside `stringN` arrays** — values stored as literal strings. Use `merge` → `makeData` with `<!var!>` placeholders instead.
13. **Every adapter/external task needs an error transition** — without one, errors cause "Job has no available transitions" and the job gets stuck forever.
14. **JSON can't have duplicate keys** — if success and error both go to `workflow_end`, route error to an intermediate `newVariable` task first.

### Utility Tasks
15. **merge uses `"variable"`, childJob uses `"value"`** — don't mix them. Using `"variable"` in childJob causes `undefined.indexOf()` at job start (P6.4.0+).
16. **merge requires at least 2 items** — 1 item silently returns null.
17. **childJob `actor` MUST be `"job"`**, `task` MUST be `""`, `job_details` outgoing MUST be `null`.
18. **childJob `variables` use `{"task","value"}` NOT `$var`** — `$var` strings inside variables cause an indefinite hang at runtime.
19. **`evaluation` MUST have both success AND failure transitions** — missing one silently drops the job.
20. **`forEach` last body task transition must be empty `{}`** — do NOT connect it back to forEach.
21. **`push`/`pop`/`shift` take variable NAME as a plain string** — `"myArray"` not `"$var.job.myArray"`.
22. **`newVariable` value with `$var` stores the literal string** — use merge + query to build dynamic values.
23. **`makeData` `variables` must be a resolved object** — use merge first, then pass `$var.taskId.merged_object`.
24. **Adapter task `result` is always an object** — never a primitive. When the upstream API returns a simple string (e.g., Infoblox `_ref`), it's at `result.response`. Passing raw `result` in a string context produces `[object Object]`.

### Templates
25. **Template `group` cannot be empty or whitespace-only** — causes a silent rejection.
26. **TextFSM templates may contain control characters** that break jq — use Python with a control-char strip when parsing them.

### MOP
27. **Missing variable = skip = PASS (not fail)** — if a variable isn't passed, the rule is skipped and the command auto-passes. Always verify variables are passed correctly.
28. **`case: true` = case-INsensitive** — the name is backwards. Easy to wire the wrong behavior.
29. **Eval types are case-sensitive** — `"RegEx"` not `"regex"`. Wrong casing silently fails.
30. **Empty rules = auto-pass** — a command with no rules always passes. Add at least one rule to validate output.
31. **MOP update is full replacement** — include ALL fields or omitted ones are lost.
32. **MOP is read-only** — never use it to push config. Use `itential_cli` via AGManager for config push.

### General
33. **Adapter `app` must come from `apps.json`** — NOT `tasks.json`. Names can differ completely (e.g., `ServiceNow` vs `Servicenow`). Wrong `app` causes "No config found for Adapter" at runtime.
34. **`legacyWrapper: false` on Operations Manager manual triggers** — default `true` wraps all form values under `formData`, breaking variable mapping to workflow inputs.
35. **`status: complete` doesn't mean CLI commands succeeded** — always check `stdout` for actual command output and errors.
36. **Endpoint base paths differ** — task catalog at `/workflow_builder/tasks/list`, schemas at `/automation-studio/multipleTaskDetails` (NOT `/workflow_builder/multipleTaskDetails`).
37. **`evaluation` operator is a closed enum** — only `contains, !contains, <, <=, >, >=, ==, !=` exist. Any other string silently returns `false` with empty outgoing and no error message. Validate against this list before wiring.
38. **`contains` uses regex, not substring matching** — `operand_2` is interpreted as a regex pattern. Escape metacharacters (`(`, `)`, `.`, `[`, `]`, `?`, `+`, `*`, `|`) in literal values: `9\.2\(4\)` not `9.2(4)`. Test with `POST /workflow_engine/runEvaluationGroups` before wiring.
39. **API PUT does not regenerate `incomingRefs` for existing task changes** — evaluation operand literals resolve to `null` after PUT. Broader symptom: entire workflow hangs after `workflow_start` (status: running forever). Fix: open in Studio and save. If still failing, recreate via fresh POST — more PUTs won't fix it.
40. **`$var.<taskId>.<out>` does not resolve inside nested forEach bodies** — use `$var.job.<varName>` for any variable referenced inside a nested loop body.
41. **Workflow delete endpoint** — `DELETE /workflow_builder/workflows/delete/{URL-encoded-name}` deletes by name, returns 200 with deleted doc. `DELETE /automation-studio/automations/{id}` does NOT exist (404). Always export the project before deleting anything.
42. **Always use a local venv for Python** — `python3 -m venv .venv && source .venv/bin/activate` before any Python scripts during the build.
43. **Search `tasks.json` before designing any sub-workflow** — a purpose-built platform task may already exist for the intent (filter, inventory, tag, etc.). Server-side is always better than a forEach + evaluation chain.
44. **Prefer server-side filtering over client-side when available** — fetching the full collection and filtering in a forEach adds unnecessary iterations. Check for a filtered-fetch task first.
45. **Propose decomposition when a workflow exceeds ~20 tasks** — extract inner iteration bodies into reusable child workflows.
46. **DRY check on sibling workflows** — if building multiple similarly-named workflows, compare task graphs. Identical graphs → propose one generic workflow, not N clones.
47. **Project component refresh** — `mode: "copy"` creates a new project-scoped UUID that immediately diverges from the standalone. To refresh: DELETE each old component, POST fresh, then update any Operations Manager automation `componentId` via `PATCH /operations-manager/automations/{id}`.
48. **`renderJinja2` inline template with `\n` breaks `parse`** — static values store literal `\n` characters, causing `parse` to fail with "Expected property name or '}' in JSON at position 1". Fix: write single-line templates.
49. **Task outgoing writes directly to job var** — `"outgoing": {"result": "$var.job.myVar"}` works on any task and is more reliable than a separate `newVariable` copy step (written at execution time, bypassing incomingRefs cache).
50. **GatewayManager `"failed to parse start_time"` = device unreachable** — this IAG error (`"failed to parse start_time for command 0: failed to parse timestamp string ''"`) means the device is offline, unreachable, or auth failed. The timestamp complaint is misleading — the session never opened. It is NOT a workflow bug. Guard with an `evaluation` checking whether the response contains a `result` key; if not, route to a skip handler and continue.
51. **NEVER wire a Configuration Manager remediation task** — `runAutoRemediation`, `advancedAutoRemediation`, `convertChangesToConfig`, `patchDeviceConfiguration`, `advancedPatchDeviceConfiguration`, `patchCMDeviceConfiguration` (IAP), `ManualRemediation`, and `ManualRemediationResults` are **prohibited** in every workflow, even when a spec asks for fully automatic remediation. Golden Config detects and reports drift; it never applies fixes to a device. To correct a device, build a normal config-push delivery. (`updateNodeConfig` is allowed — it authors the GC node template, not a device.)

---

## Helper Templates

**Two separate concerns — don't mix them:**
- **API wrappers** (project, workflow, template, form creation) → use `helpers/create/` scaffolds below. These are POST body wrappers — correct structure, required fields.
- **Task JSON inside a workflow** → extract from `helpers/assets/` using jq (see Guide 1 STOP block). Do NOT use `helpers/create/` files for task bodies — they are scaffold stubs, not task examples.

### Scaffolds — start from these

Read these first. They have the correct wrapper, required fields, and structure.

| When you need to... | Read this helper | Then POST to |
|---------------------|------------------|--------------|
| Create a project | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-project.json` | `POST /automation-studio/projects` |
| Create a workflow | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-workflow.json` | `POST /automation-studio/automations` |
| Create a Jinja2 template | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-template-jinja2.json` | `POST /automation-studio/templates` |
| Create a TextFSM template | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-template-textfsm.json` | `POST /automation-studio/templates` |
| Create a MOP command template | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-command-template.json` | `POST /mop/createTemplate` |
| Update a MOP template | `${CLAUDE_PLUGIN_ROOT}/helpers/update/update-command-template.json` | `POST /mop/updateTemplate/{name}` |
| Create a JSON form (static dropdowns) | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-json-form.json` | `POST /json-forms/forms` — see `app-json_forms` skill |
| Create a JSON form (REST-bound or cascading dropdowns) | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-json-form-rest-bound.json` | `POST /json-forms/forms` — see `app-json_forms` skill |
| Create an Ops Manager automation | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-ops-manager-automation.json` | `POST /operations-manager/automations` |
| Create a manual trigger (with form) | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-ops-manager-trigger-manual.json` | `POST /operations-manager/triggers` — `legacyWrapper` MUST be false |
| Create a scheduled trigger | `${CLAUDE_PLUGIN_ROOT}/helpers/create/create-ops-manager-trigger-schedule.json` | `POST /operations-manager/triggers` |
| Import a project (atomic) | `${CLAUDE_PLUGIN_ROOT}/helpers/create/import-project.json` | `POST /automation-studio/projects/import` |
| Add assets to a project | `${CLAUDE_PLUGIN_ROOT}/helpers/operations/add-components-to-project.json` | `POST /projects/{id}/components/add` |
| Update project membership | `${CLAUDE_PLUGIN_ROOT}/helpers/update/update-project-members.json` | `PATCH /projects/{id}` |

### Task templates — extract from asset projects

Do not write task JSON from scratch. For every task type, extract a real example from an asset project and adapt it. Use the jq commands below — they work against the project files in `${CLAUDE_PLUGIN_ROOT}/helpers/assets/`.

```bash
# Adapter task (ServiceNow, Infoblox, etc.)
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.location == "Adapter")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-servicenow.json

# Application task (WorkFlowEngine — getTime, newVariable, query, evaluation, transformation, merge, makeData)
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.app == "WorkFlowEngine" and .value.name == "TASK_NAME")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/itential-platform-configuration-management.json

# childJob
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "childJob")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json

# evaluation / branching
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "evaluation")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json

# transformation (JST)
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "transformation")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-netbox.json

# RunCommandTemplate / viewTemplateResults / reattempt / runTemplatesDiff (MOP tasks)
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "TASK_NAME")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/itential-platform-configuration-management.json

# itential_cli (config push via IAG)
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "itential_cli")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-arista-eos.json

# ViewData / ViewHTML (manual tasks)
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "ViewData")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json
```

Key fields to verify after extracting (see body sections above for full rules per task type):

| Task type | Must-check fields |
|-----------|-------------------|
| Adapter | `app`/`locationType` from apps.json (not tasks.json), `adapter_id`, error transition |
| childJob | `actor: "job"`, `task: ""`, variables use `{"task","value"}` not `$var` |
| evaluation | `evaluation_groups[]`, `all_true_flag`, both success AND failure transitions |
| transformation | `tr_id`, `variableMap` keys match transformation's `incoming` schema |
| ViewData / ViewHTML | `view` is top-level (not inside `variables`), `displayName: "Tools"`, no `actor`, no `error`/`decorators` |
| Manual tasks (any) | `type: "manual"`, `taskVersion: 2`, `hostApp` required |

### Reference workflows — read from asset projects

Real, production-tested workflows. Use the jq commands to extract and study them before building.

| Pattern | Asset file | jq filter |
|---------|-----------|-----------|
| Adapter workflow: merge → create → query → update + error handling | `vendor-servicenow.json` | `select(.document.name \| test("Create Change"))` |
| childJob orchestrator + evaluation branching | `vendor-cisco-ios.json` | `select(.document.name \| test("IOS Upgrade"))` |
| childJob loop with data_array (parallel/sequential) | `vendor-cisco-ios.json` | `select(.document.name \| test("Upgrade\|Runner"))` |
| Config push: renderJinja → dry-run ViewData → itential_cli → commit | `vendor-arista-eos.json` | `select(.document.name \| test("Push Config"))` |
| Pre/post MOP check: RunCommandTemplate → viewTemplateResults → evaluation → reattempt | `itential-platform-configuration-management.json` | `select(.document.name \| test("Command Template Runner"))` |
| IPAM CRUD (adapter + transformation + error) | `vendor-infoblox-nios-ddi.json` | `select(.document.name \| test("Create Network\|Assign Next"))` |
| ITSM ticket + update (ServiceNow) | `vendor-servicenow.json` | `select(.document.name \| test("Create Incident"))` |
| LCM action workflow (must output `instance`) | `lcm/lcm-vxlan-fabric-services-project.json` | `select(.document.name \| test("Create\|Delete"))` — note: this file uses `.data.project.components[]` |
| Email/notification | `itential-platform-email.json` | `select(.document.name \| test("Email"))` |

```bash
# General pattern to read any workflow by name from an asset project:
jq '[.components[] | select(.type=="workflow") | select(.document.name | test("PATTERN"; "i"))] | first | .document | {name:.name, tasks:.tasks, transitions:.transitions}' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/ASSET_FILE.json

# For the LCM project (different wrapper):
jq '[.data.project.components[] | select(.type=="workflow") | select(.document.name | test("PATTERN"; "i"))] | first | .document | {name:.name, tasks:.tasks, transitions:.transitions}' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/lcm/lcm-vxlan-fabric-services-project.json
```
