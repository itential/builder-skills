---
name: builder-agent
description: Builder Agent — owns Build and As-Built. Implements the approved solution design, tests each component, delivers the solution, and records the as-built state. Invoke after /solution-architecture produces an approved solution-design.md.
argument-hint: "[action or asset-type]"
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
  openapi.json            ← API reference
  tasks.json              ← task catalog
  apps.json               ← app names
  adapters.json           ← adapter instances
  applications.json       ← app health
```

**May also exist (spec-contingent):**
```
  customer-spec.md        ← approved HLD (Requirements)
  feasibility.md          ← approved feasibility assessment
  customer-context.md     ← business rules (if provided)
  solution-design.md      ← approved Solution Design / LLD
  devices.json            ← device inventory
  workflows.json          ← existing workflows
  device-groups.json      ← device groups
  task-schemas.json       ← cached task schemas
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

**Helper script:** `${CLAUDE_PLUGIN_ROOT}/helpers/oauth-bootstrap.sh` — reads `.env`, POSTs to `/oauth/token`, writes `.auth.json`. The builder should run this automatically when `.auth.json` is missing and `.env` has `AUTH_METHOD=oauth`.

---

## Build Lifecycle

```
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
```

---

## Guides

### Guide 1: Build a workflow end-to-end

Follow these steps in order. Do not skip any step.

**Step 0: Decompose before you build.**

Before writing any JSON, identify the parent/child split from the solution design. Ask for each phase:

- Can this phase be run and tested on its own? → **Child workflow**
- Does it loop over multiple items (devices, records)? → **Child workflow with `loopType`**
- Is it reusable across other use cases? → **Child workflow**
- Is it a simple sequential step with no independent test value? → **Task in orchestrator**

Build order is always: **children first, orchestrator last.** The orchestrator is just childJob calls to tested children — it should not contain raw adapter tasks unless there is no logical way to split.

**Reference helpers for parent/child patterns:**
- `${CLAUDE_PLUGIN_ROOT}/helpers/reference-child-workflow.json` — child with try-catch (always sets `taskStatus`, always completes)
- `${CLAUDE_PLUGIN_ROOT}/helpers/reference-parent-workflow.json` — parent with childJob → query → evaluation branching
- `${CLAUDE_PLUGIN_ROOT}/helpers/reference-childjob-loop.json` — parent + child with `data_array` loop (parallel or sequential)

Read these before building any multi-workflow solution.

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

Becomes this workflow task (use the adapter helper template as starting point):
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
- [ ] Incoming variable types match task schema exactly (arrays for `to`/`cc`/`bcc`, numbers for `page`/`pageSize`, etc.)
- [ ] No `$var` references inside nested objects (use merge/makeData)
- [ ] merge uses `"variable"`, childJob uses `"value"`
- [ ] childJob has `actor: "job"`, all others have `actor: "Pronghorn"`
- [ ] `workflow_end` transition is empty `{}`
- [ ] Canvas layout follows the spacing convention — success path on y=0 spine, error handlers drop to y=+132
- [ ] No tasks overlap (minimum +264px x-delta between columns)

**Complete working example:** Read `${CLAUDE_PLUGIN_ROOT}/helpers/reference-adapter-workflow.json` before building. It's a tested workflow (merge → adapter create → query → adapter update) with `_comment` fields explaining every decision.

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

### Guide 2b: Work with any adapter task (discover → schema → test → wire)

This is the general pattern for using any adapter task you haven't used before. Don't guess fields or response shapes — discover them.

**Step 1: Find the task.**
Search `tasks.json` for the adapter's tasks:
```bash
jq '.[] | select(.app | test("meraki";"i")) | {name, app, displayName}' {use-case}/tasks.json
```
This gives you the task `name` and `app` (but remember — `app` here may have wrong casing).

**Step 2: Get the correct app name.**
The `app` in tasks.json is often wrong for adapters. Look it up in `apps.json`:
```bash
jq '.[] | select(.name | test("meraki";"i")) | {name, type}' {use-case}/apps.json
```
Also get the adapter instance name from `adapters.json`:
```bash
jq '.results[] | select(.package_id | test("meraki";"i")) | {id, state}' {use-case}/adapters.json
```
Now you have three values: `app` (from apps.json), `adapter_id` (from adapters.json), `displayName` (from tasks.json).

**Step 3: Get the task schema.**
```
POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true
{"inputsArray": [{"location": "Adapter", "pckg": "Meraki", "method": "getOrganizations"}]}
```
Use the `pckg` value from apps.json. The response tells you every incoming and outgoing variable with types. Save to `task-schemas.json`.

**Step 4: Respect data types from the schema.**
When the schema says a field is `"type": "array"`, you MUST pass an array — even for single values. Common mistakes:
- `"to": "user@example.com"` → WRONG. Schema says array. Use `"to": ["user@example.com"]`
- `"cc": ""` → OK only if schema allows string. If array, use `"cc": []`
- `"pageSize": "100"` → WRONG if schema says number. Use `"pageSize": 100`

Always check `task-schemas.json` for the exact type of each field before wiring.

**Step 5: Understand opaque schemas.**
Many adapter schemas show `body: {type: "object"}` with no inner detail — the adapter validates internally. To discover required fields:
1. Build a minimal test workflow: `workflow_start → adapter_task → workflow_end` (with error transition)
2. Pass `body: {}` (empty object) via a merge task
3. Run the job — the error message lists every required field: `"must have required property 'X'"`
4. Add fields one at a time until the call succeeds

**Step 5: Inspect the actual response.**
Adapter task outgoing `result` is always an object (containing `response`, `headers`, `metrics`, etc.) — never a primitive. When the API returns a simple string (like Infoblox's `_ref`), it's at `result.response`, not `result` directly. Always add a `query` task to extract the specific field before passing to downstream tasks. Passing raw `result` to a string context produces `[object Object]`.

Adapter responses are transformed — they **do not match** the native API's structure. Never assume the response shape. After a successful call:
1. Get the job: `GET /operations-manager/jobs/{jobId}`
2. Find the adapter task in `data.tasks` by its task ID
3. Look at the task's outgoing variables — this is the actual response object
4. Use `jq` to explore the structure: what keys exist, where the ID or status lives

**Step 6: Wire the query path.**
Now that you've seen the real response, wire a `query` task with the correct dot-path:
```json
{
  "query": "response.result.sys_id",
  "obj": "$var.b2b2.result"
}
```
The path comes from what you saw in Step 5 — not from the native API docs, not from guessing.

**Example — full sequence for a hypothetical adapter:**
```
1. tasks.json search → found "getDevice", app "networkAdapter"
2. apps.json lookup → correct app is "NetworkAdapter" (capital N)
3. adapters.json → adapter_id is "network-prod-1"
4. multipleTaskDetails → incoming: {deviceId: string}, outgoing: {result: object}
5. Test with known deviceId → job completes
6. Inspect job → result is {"response": {"hostname": "...", "model": "...", "status": "active"}}
7. Query path → "response.hostname" (not "result.hostname", not "data.hostname")
```

### Guide 3: Add a task to an existing workflow

**Step 1:** Read the helper template for the task type:
- Adapter task → `${CLAUDE_PLUGIN_ROOT}/helpers/workflow-task-adapter.json`
- Application task → `${CLAUDE_PLUGIN_ROOT}/helpers/workflow-task-application.json`
- childJob → `${CLAUDE_PLUGIN_ROOT}/helpers/workflow-task-childjob.json`

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
Include ALL members (existing + new) — this is a full replacement.

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

---

## JSON Forms

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/json-forms/forms` | List all JSON forms |
| POST | `/json-forms/forms` | Create a JSON form |
| PUT | `/json-forms/forms/{id}` | Update a JSON form (full replacement) |

### Create a JSON Form

```
POST /json-forms/forms
```

Use the helper template: `${CLAUDE_PLUGIN_ROOT}/helpers/create-json-form.json`

**Update format:** `PUT /json-forms/forms/{id}` — body MUST be wrapped in `{"options": {...}}` and include ALL fields (`created`, `createdBy`, `lastUpdated`, `lastUpdatedBy`, `name`, `description`, `struct`, `schema`, `uiSchema`, `validationSchema`, `bindingSchema`, `version`). This is a full replacement — omitting any field will clear it.

**Dropdown fields** use `enum`/`enumNames` arrays in both `struct.items` and `schema.properties` — these must stay in sync.

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

Use the helper template: `${CLAUDE_PLUGIN_ROOT}/helpers/create-ops-manager-automation.json`

**Critical: `legacyWrapper` must be `false`.** When creating a manual trigger with a JSON form, set `legacyWrapper: false`. The default is `true`, which wraps form field values under `formData`, breaking the mapping to workflow job variables. With `legacyWrapper: false`, form field values map directly to workflow input variables by name.

**Required trigger fields:** `name`, `type` (`"manual"`), `enabled`, `actionType` (`"automations"`), `actionId`, `formId`, `legacyWrapper`

---

## Task Discovery

### Pull Task Catalog

```
GET /workflow_builder/tasks/list → save to {use-case}/tasks.json
GET /automation-studio/apps/list → save to {use-case}/apps.json
```

Search locally:
```bash
grep -i "template" {use-case}/tasks.json
jq '.[] | select(.app == "ConfigurationManager") | .name' {use-case}/tasks.json
```

### Get Full Task Schemas

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
1. Check if `{use-case}/task-schemas.json` exists — search it first
2. Only call `multipleTaskDetails` for tasks NOT already in the local file
3. After fetching, append to the local file

### nodeLocation Spacing Convention

**Ask the engineer before starting:** "Do you prefer a horizontal layout (left to right) or vertical (top to bottom)?"

- **Horizontal** is the Automation Studio default — tasks advance left-to-right, branches drop down. Use this unless the engineer says otherwise.
- **Vertical** works better for deep workflows with many sequential phases where horizontal becomes too wide to read.

The rules below assume **horizontal**. For vertical, swap x and y roles (phases advance on y, branches offset on x).

#### Horizontal Layout (default)

| Rule | Value |
|------|-------|
| workflow_start → first task (x-delta) | +264px |
| Sequential task columns (x-delta) | +360px |
| Stacked tasks in same column (y-delta) | +132px |
| Last task → workflow_end (x-delta) | +276px |

**Clean canvas principles:**
- The **success path is the spine** — keep it on `y=0`, advancing left to right
- **Error handlers drop down** — same x as the failing task, `y=+132` or `y=+264`
- **Branch convergence** — tasks that merge back to the success path return to `y=0`
- **Group related tasks** at the same x: merge + the adapter it feeds, childJob + its query extractor
- **Never overlap** — maintain at least +264px x-delta between task columns

Example for a 3-phase workflow:
```
workflow_start (x=0,   y=0)
  Phase 1:   x=264  — task1     (y=0),   task1_err (y=132)
  Phase 2:   x=624  — task2     (y=0),   task2_err (y=132)
  Phase 3:   x=984  — task3     (y=0),   task3_err (y=132)
workflow_end (x=1260, y=0)
```

For a childJob phase with query + evaluation:
```
  x=264  — childJob     (y=0)
  x=624  — query        (y=0)   ← extracts taskStatus from job_details
  x=984  — evaluation   (y=0),  eval_fail (y=132)
```

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
        "nodeLocation": {"x": 360, "y": 1308}
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
        "nodeLocation": {"x": 600, "y": 1308}
      },
      "workflow_end": {
        "name": "workflow_end",
        "groups": [],
        "nodeLocation": {"x": 1152, "y": 1308}
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

**IMPORTANT: Don't guess the query path for adapter responses.** Adapters transform upstream API responses — the field path in the adapter's output is NOT the same as the native API's response structure. Always inspect the actual task output from a test job before wiring the query path. See Guide 2b Step 5-6 for the discovery process.

### merge

Build an object from multiple resolved values. Primary workaround for `$var` not resolving inside nested objects.

**Incoming:** `data_to_merge` (array, min 2 items)
**Outgoing:** `merged_object` (object)

**IMPORTANT: The field is `"variable"` NOT `"value"`** in the reference objects inside `data_to_merge`.

**Reference format in `data_to_merge`:**
- `{"task": "job", "variable": "varName"}` — pull from a job variable
- `{"task": "static", "variable": "literalValue"}` — literal value
- `{"task": "taskId", "variable": "outVar"}` — pull from a previous task's output

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

Run another workflow as a sub-job. **Use helper template** `${CLAUDE_PLUGIN_ROOT}/helpers/workflow-task-childjob.json`.

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

**Incoming:** `data_array` (array)
**Outgoing:** `current_item` (any)

**Transition pattern (critical):**
```
forEach --state:loop--> firstBodyTask -> ... -> lastBodyTask --(empty {})
forEach --state:success--> nextTaskAfterLoop
```
The last task in the loop body has an **empty transition `{}`**. Do NOT connect it back to forEach.

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

| Asset | Create | Update |
|-------|--------|--------|
| Workflow | `POST /automation-studio/automations` | `PUT /automation-studio/automations/{id}` with `{"update": {...}}` |
| Template | `POST /automation-studio/templates` | `PUT /automation-studio/templates/{id}` with `{"update": {...}}` |
| Command Template | `POST /mop/createTemplate` | `POST /mop/updateTemplate/{name}` with `{"mop": {...}}` (full replacement) |

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

```json
{
  "name": "ViewData",
  "type": "manual",
  "view": "/workflow_engine/task/ViewData",
  "variables": {
    "incoming": {
      "header": "Approval Required",
      "message": "Review and approve.",
      "body": "$var.job.dataToReview",
      "btn_success": "Approve",
      "btn_failure": "Reject"
    }
  }
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

### Projects
1. **Use `POST /projects/import` to create projects with all assets atomically** — avoids broken childJob refs, project-locking issues, and intermediate state. Pre-compute the project `_id` so childJob `@projectId:` refs can be wired before push.
2. **Avoid create + move pattern** — moving assets renames them with `@projectId:` prefix but does NOT update internal references (childJob `workflow` fields, template names).
3. **Import format differs from create** — OMIT `encodingVersion` from workflow documents (causes silent failure). Workflow `created_by` has NO `_id` but has `firstname`, `inactive`, `sso`. Project `createdBy` HAS `_id`.
4. **Component type is `mopCommandTemplate`** not `mop`.
5. **Members PATCH is full replacement** — include ALL members.
6. **Import sets the OAuth service account as project owner** — not the UI user. PATCH membership immediately after import (Phase 3, not Phase 6).

### Workflows
5. **`canvasName` must come from `tasks.json`** — some differ from method name: `arrayPush`→`push`, `stringConcat`→`concat`.
6. **Task IDs must be hex `[0-9a-f]{1,4}`** — non-hex causes silent `$var` failure.
7. **Validation errors = draft workflow** that cannot be started.
8. **`$var` inside nested objects doesn't resolve** — use merge/makeData/query to build the object.
8b. **`stringConcat` does not resolve `$var` inside `stringN` arrays** — the values are stored as literal strings. The schema shows `stringN` as type "array" of strings, which looks like it should accept `$var` references — but it doesn't resolve them. Use `merge` → `makeData` with `<!var!>` placeholders instead when concatenating multiple resolved variables into a string.
9. **Every adapter/external task needs an error transition** — without one, jobs get stuck.
10. **JSON can't have duplicate keys** — if success and error both go to `workflow_end`, use an intermediate task.

### Utility Tasks
11. **merge uses `"variable"`, childJob uses `"value"`** — don't mix them.
12. **merge requires at least 2 items** — 1 item = silently null.
13. **childJob `actor` MUST be `"job"`**, `task` MUST be `""`, `job_details` MUST be `null`.
14. **childJob `variables` use `{"task","value"}` NOT `$var`** — `$var` inside causes indefinite hang.
15. **`evaluation` MUST have both success AND failure transitions.**
16. **`forEach` last body task transition must be empty `{}`.**
17. **`push`/`pop`/`shift` take variable NAME as string** — `"myArray"` not `"$var.job.myArray"`.
18. **`newVariable` value with `$var` stores the literal string** — use merge + query.
19. **`makeData` `variables` must be a resolved object** — use merge first.

### Templates
20. **Template `group` cannot be empty or whitespace-only.**
21. **TextFSM templates may have control chars** that break jq — use Python with control-char strip.

### MOP
22. **Missing variable = skip = PASS (not fail)** — verify variables are passed correctly.
23. **`case: true` = case-INsensitive** — confusing name.
24. **Eval types are case-sensitive** — `"RegEx"` not `"regex"`.
25. **Empty rules = auto-pass** — add at least one rule for validation.
26. **MOP update is full replacement** — include ALL fields.
27. **MOP is read-only** — never use it to push config.

### General
28. **Adapter `app` must come from `apps.json`** — NOT `tasks.json` (names can differ completely).
29. **`status: complete` doesn't mean CLI commands succeeded** — check `stdout`.
30. **Endpoint base paths differ** — tasks at `/workflow_builder/tasks/list`, schemas at `/automation-studio/multipleTaskDetails` (NOT `/workflow_builder/multipleTaskDetails`).
31. **Adapter task `result` is always an object** — never a primitive. When the upstream API returns a simple string (e.g., Infoblox `_ref`), it's at `result.response`, not `result` directly. Always use a `query` task to extract the specific field. Passing raw `result` in a string context produces `[object Object]`.
32. **`stringConcat` doesn't resolve `$var` in `stringN` arrays** — use merge → makeData with `<!var!>` placeholders instead.
33. **`legacyWrapper: false` on Operations Manager manual triggers** — default `true` wraps form values under `formData`, breaking variable mapping.
34. **Always use a local venv for Python** — run `python3 -m venv .venv && source .venv/bin/activate` instead of using global Python when running any Python scripts during the build process.

---

## Helper Templates

**Read the matching helper before building anything.** Helpers have the correct JSON structure. Modify them for your use case — do NOT build JSON from scratch.

### Scaffolds — start from these

Read these first. They have the correct wrapper, required fields, and structure.

| When you need to... | Read this helper | Then POST to |
|---------------------|------------------|--------------|
| Create a project | `${CLAUDE_PLUGIN_ROOT}/helpers/create-project.json` | `POST /automation-studio/projects` |
| Create a workflow | `${CLAUDE_PLUGIN_ROOT}/helpers/create-workflow.json` | `POST /automation-studio/automations` |
| Create a Jinja2 template | `${CLAUDE_PLUGIN_ROOT}/helpers/create-template-jinja2.json` | `POST /automation-studio/templates` |
| Create a TextFSM template | `${CLAUDE_PLUGIN_ROOT}/helpers/create-template-textfsm.json` | `POST /automation-studio/templates` |
| Create a MOP command template | `${CLAUDE_PLUGIN_ROOT}/helpers/create-command-template.json` | `POST /mop/createTemplate` |
| Update a MOP template | `${CLAUDE_PLUGIN_ROOT}/helpers/update-command-template.json` | `POST /mop/updateTemplate/{name}` |
| Create a JSON form | `${CLAUDE_PLUGIN_ROOT}/helpers/create-json-form.json` | `POST /json-forms/forms` |
| Create an Ops Manager automation + trigger | `${CLAUDE_PLUGIN_ROOT}/helpers/create-ops-manager-automation.json` | `POST /operations-manager/automations` + `POST /operations-manager/triggers` |
| Add assets to a project | `${CLAUDE_PLUGIN_ROOT}/helpers/add-components-to-project.json` | `POST /projects/{id}/components/add` |
| Update project membership | `${CLAUDE_PLUGIN_ROOT}/helpers/update-project-members.json` | `PATCH /projects/{id}` |

### Task templates — embed these in your workflow

When adding a task to a workflow, read the matching template and fill in the fields using the mapping rules from Guide 1 Step 4.

| Task type | Read this helper | Key fields to set |
|-----------|------------------|-------------------|
| Application task (WorkFlowEngine, TemplateBuilder, etc.) | `${CLAUDE_PLUGIN_ROOT}/helpers/workflow-task-application.json` | `app`, `name`, `canvasName`, incoming/outgoing from schema |
| Adapter task (ServiceNow, etc.) | `${CLAUDE_PLUGIN_ROOT}/helpers/workflow-task-adapter.json` | `app`/`locationType` from apps.json, add `adapter_id`, add error transition |
| childJob task | `${CLAUDE_PLUGIN_ROOT}/helpers/workflow-task-childjob.json` | `actor: "job"`, `task: ""`, variables use `{"task","value"}` syntax |

### Reference workflows — study these patterns

These are complete, tested workflows. Read them to understand how tasks connect, how data flows, and how error handling works. Each task has a `_comment` field explaining why it's there.

| Pattern | Read this helper | What it teaches |
|---------|------------------|-----------------|
| Adapter workflow with merge + query + error handling | `${CLAUDE_PLUGIN_ROOT}/helpers/reference-adapter-workflow.json` | merge builds objects, adapter tasks need error transitions, query extracts from adapter response, newVariable as error handler |
| childJob loop (parent + child) | `${CLAUDE_PLUGIN_ROOT}/helpers/reference-childjob-loop.json` | Has both parent and child workflows. data_array input, parallel/sequential, extracting loop results, try-catch in child |
| childJob with evaluation (parent orchestrator) | `${CLAUDE_PLUGIN_ROOT}/helpers/reference-parent-workflow.json` | childJob → query → evaluation pattern for checking child success/failure |
| merge → makeData pattern | `${CLAUDE_PLUGIN_ROOT}/helpers/reference-merge-makedata.json` | Building template variables with merge, then string substitution with makeData |
| Child with makeData/query/merge | `${CLAUDE_PLUGIN_ROOT}/helpers/reference-child-workflow.json` | Data transformation patterns inside a child workflow |
