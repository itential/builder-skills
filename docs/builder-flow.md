```
SOLUTION DESIGN (locked)
     │
     │  Component Inventory:
     │  ┌────┬───────────────────┬──────────────────┬────────┐
     │  │ #  │ Component         │ Type             │ Action │
     │  ├────┼───────────────────┼──────────────────┼────────┤
     │  │ 1  │ Pre-Check         │ Command Template │ Build  │
     │  │ 2  │ Config Template   │ Jinja2 Template  │ Build  │
     │  │ 3  │ Parse Template    │ TextFSM Template │ Build  │
     │  │ 4  │ Device Backup     │ Child Workflow   │ Reuse  │
     │  │ 5  │ Config Push       │ Child Workflow   │ Build  │
     │  │ 6  │ Orchestrator      │ Parent Workflow  │ Build  │
     │  └────┴───────────────────┴──────────────────┴────────┘
     │
     ▼
BUILD SEQUENCE (build locally, import atomically, test, iterate)
     │
     │  Phase 1: PREPARE
     │    Generate project ID (24-char hex)
     │    All asset names will use @{projectId}: prefix
     │
     │  Phase 2: BUILD LOCALLY (dependency order: leaves → composites)
     │    Command templates (MOP)     ← no deps
     │    Jinja2 / TextFSM templates  ← no deps
     │    Child workflows             ← may use templates
     │    Parent workflow             ← uses children + templates + MOP
     │
     │  Phase 3: IMPORT + SET MEMBERSHIP
     │    POST /automation-studio/projects/import
     │    All assets created inside the project in one call
     │    childJob refs already correct (pre-wired with @projectId:)
     │    PATCH membership immediately — resolve spec owners/groups to platform IDs
     │
     │  Phase 4: TEST
     │    Test leaf assets standalone (MOP, Jinja2 render)
     │    Test each child workflow via jobs/start
     │    Test parent end-to-end via jobs/start
     │
     │  Phase 5: ITERATE
     │    On failure: fix local JSON → PUT to update → re-test
     │    Never recreate — updating preserves IDs
     │
     │  Phase 6: VERIFY + DELIVER
     │    Run acceptance criteria from solution-design.md
     │    Verify membership (set in Phase 3)
     │
     ▼
DELIVERED
```

---

## Design Principle

**Build everything locally first. Import atomically. Test after import.**

The old pattern (create globally → move into project → fix refs) caused:
- Project-locking issues during move
- childJob `workflow` refs breaking because move renames but doesn't update internal references
- Intermediate state where workflows exist outside the project

The import pattern avoids all of this:
- Single `POST /automation-studio/projects/import` creates the project with all assets inside it
- Pre-compute the project ID so childJob `@projectId:` refs can be wired before push
- The import auto-prefixes workflow names — childJob refs just work
- No intermediate state, no fixup pass

**Verified on live platform:** Parent workflow with childJob calling a child — both imported atomically, childJob ref resolved correctly, job completed successfully.

---

## Phase 1: PREPARE

### Generate IDs up front

Before building any JSON, generate the project ID and workflow UUIDs. This lets you pre-wire all `@projectId:` references.

```python
import secrets, uuid

project_id = secrets.token_hex(12)    # 24-char hex for MongoDB ObjectId
child_uuid = str(uuid.uuid4())         # UUID for each workflow
parent_uuid = str(uuid.uuid4())
```

Now every asset knows its project prefix: `@{project_id}: Workflow Name`

---

## Phase 2: BUILD LOCALLY

Build all asset JSON in `{use-case}/` directory. Dependency order: leaves first, composites last.

### 2A. Command Templates (MOP)

Pre-checks, post-checks, validation. Read-only — never push config.

**Build cycle:**
1. Read `helpers/create-command-template.json`
2. Define commands with `<!var!>` syntax and validation rules
3. Save to `{use-case}/cmd-{name}.json`

No platform call yet — just build the JSON.

### 2B. Jinja2 / TextFSM Templates

Config generation (`{{ var }}`) and output parsing.

**Build cycle:**
1. Read `helpers/create-template-jinja2.json` or `helpers/create-template-textfsm.json`
2. Write the template content
3. Set `data` field with sample values (JSON string, not object)
4. Save to `{use-case}/tmpl-{name}.json`

### 2C. Child Workflows

Each child is independently testable. Build each one:

**Step 1: Find tasks.** Search `tasks.json`:
```bash
jq '.[] | select(.name | test("keyword"; "i")) | {name, app, location, canvasName, displayName}' {use-case}/tasks.json
```

**Step 2: Resolve app names.** `app` in tasks.json is WRONG for adapters. Look up from `apps.json`:
```bash
jq '.[] | select(.name | test("keyword"; "i")) | {name, type}' {use-case}/apps.json
```

**Step 3: Fetch schemas.** Check `task-schemas.json` first. Only call API for missing tasks:
```
POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true
{"inputsArray": [{"location": "...", "pckg": "...", "method": "..."}]}
```
Append results to `{use-case}/task-schemas.json`.

**Step 4: Build workflow JSON.**
1. Read `helpers/create-workflow.json` for scaffold
2. Read task helpers for each task type
3. Map schema → task JSON:
   - `name`, `canvasName`, `displayName` from tasks.json
   - `app`, `locationType` from apps.json
   - `adapter_id` from adapters.json (adapter tasks only)
   - `type`: `"automatic"` (adapter) or `"operation"` (utility)
   - `actor`: `"Pronghorn"` (all except childJob → `"job"`)
4. Wire transitions — error transitions on every adapter task
5. Add inputSchema/outputSchema
6. **Error handling pattern:** every child catches errors so parent can check status:
   ```
   task --success--> newVariable("taskStatus" = "success") -> workflow_end
   task --error---> newVariable("taskStatus" = "error")   -> workflow_end
   ```

**Step 5: Pre-submit checklist.**
- [ ] Task IDs are hex-only `[0-9a-f]{1,4}`
- [ ] `app` values from apps.json
- [ ] Every adapter task has `adapter_id` in incoming
- [ ] Every adapter task has error transition
- [ ] No `$var` inside nested objects (use merge)
- [ ] merge uses `"variable"`, childJob uses `"value"`
- [ ] `workflow_end` transition is `{}`

**Step 6: Save** to `{use-case}/wf-{name}.json`.

### 2D. Parent Workflow

Same steps as children, plus:

**childJob wiring:**
- `actor: "job"`, `task: ""`, `job_details: null`
- `workflow` = `"@{project_id}: Child Workflow Name"` (pre-wired with project prefix)
- Variables use `{"task": "job", "value": "varName"}` — NOT `$var`
- For loops: `data_array` + `loopType`, `variables: {}`

**After each childJob — extract and check:**
```
childJob → query (extract taskStatus from job_details) → evaluation (== "success"?)
  ├── success → continue
  └── failure → handle error / rollback
```

Save to `{use-case}/wf-{name}.json`.

---

## Phase 3: IMPORT

### Assemble the import payload

Combine all locally-built assets into a single import document:

```json
{
  "project": {
    "_id": "{project_id}",
    "iid": 1,
    "name": "My Project",
    "description": "...",
    "thumbnail": "",
    "backgroundColor": "#FFFFFF",
    "components": [
      {
        "iid": 1,
        "type": "workflow",
        "reference": "{child_uuid}",
        "folder": "/",
        "document": { ...child workflow JSON (from wf-child.json)... }
      },
      {
        "iid": 2,
        "type": "workflow",
        "reference": "{parent_uuid}",
        "folder": "/",
        "document": { ...parent workflow JSON (from wf-parent.json)... }
      },
      {
        "iid": 3,
        "type": "mopCommandTemplate",
        "reference": "@{project_id}: MOP Template Name",
        "folder": "/",
        "document": { ...MOP JSON (from cmd-precheck.json, without the {mop:} wrapper)... }
      },
      {
        "iid": 4,
        "type": "template",
        "reference": "{template_id}",
        "folder": "/",
        "document": { ...template JSON (from tmpl-config.json, without the {template:} wrapper)... }
      }
    ],
    "created": "2026-03-13T00:00:00.000Z",
    "createdBy": {
      "_id": "000000000000000000000000",
      "provenance": "CloudAAA",
      "username": "admin@itential"
    },
    "lastUpdated": "2026-03-13T00:00:00.000Z",
    "lastUpdatedBy": {
      "_id": "000000000000000000000000",
      "provenance": "CloudAAA",
      "username": "admin@itential"
    }
  }
}
```

### Import format rules

These were discovered through testing. The import format differs from create/export endpoints:

| Field | Import format | Notes |
|-------|--------------|-------|
| `encodingVersion` | **OMIT** from workflow documents | Not valid in import — causes silent component failure |
| `created_by` (workflow) | `{username, provenance, firstname, inactive, sso}` — NO `_id` | Different from project-level `createdBy` |
| `createdBy` (project) | `{_id, username, provenance}` — HAS `_id` | Different from workflow-level `created_by` |
| `_id` (project) | 24-char hex string | Pre-compute so childJob refs can use it |
| Workflow `name` | Clean names — no `@projectId:` prefix | Import adds the prefix automatically |
| childJob `workflow` | Must include `@{projectId}:` prefix | Pre-compute using the same `_id` |
| `reference` (workflow components) | UUID | Becomes the workflow's `uuid` |
| `reference` (MOP components) | `@{projectId}: Template Name` | String reference, not UUID |
| `iid` (components) | Sequential integers starting at 1 | Incrementing ID per component |

### Execute the import

```
POST /automation-studio/projects/import
```

With the assembled payload. Response:
```json
{
  "message": "Successfully imported project",
  "data": {"_id": "...", "name": "...", "components": [...]},
  "metadata": {"failedComponents": []}
}
```

**Check `metadata.failedComponents`** — if any components failed, they'll be listed here with the reason. A successful import has an empty array.

Save the import payload to `{use-case}/project-import.json` for reference.

### Set project membership (immediately after import)

Import sets the OAuth service account as project owner — not the UI user from the spec. PATCH membership immediately to grant the correct owners/editors access.

1. Build a membership lookup table by scanning existing projects (the list endpoint doesn't include usernames — individual GETs are required). See SKILL.md "Resolve membership references from spec" for the full procedure.
2. Match spec members to platform reference IDs using the lookup table.
3. PATCH `/automation-studio/projects/{projectId}` with the resolved members array.

If a member can't be resolved, stop and ask — don't guess or skip.

---

## Phase 4: TEST

Now that everything is on the platform, test each piece.

### 4A. Test leaf assets standalone

**MOP:** `POST /mop/RunCommandTemplate` with test device + variables
```json
{
  "template": "@{projectId}: Pre-Check Template",
  "variables": {"interface": "GigabitEthernet0/1"},
  "devices": ["IOS-CAT8KV-1"]
}
```

**Jinja2:** `POST /template_builder/templates/{name}/renderJinja` with `{context: {...}}`

### 4B. Test child workflows

```
POST /operations-manager/jobs/start
{
  "workflow": "@{projectId}: Child Workflow Name",
  "options": {"type": "automation", "variables": {...test inputs...}}
}
```

Check results:
```
GET /operations-manager/jobs/{jobId}
```
- `data.status` = `"complete"` → check task outputs, verify `taskStatus`
- `data.status` = `"error"` → read `data.error[].message.IAPerror.displayString`

### 4C. Test parent end-to-end

```
POST /operations-manager/jobs/start
{
  "workflow": "@{projectId}: Parent Orchestrator",
  "options": {"type": "automation", "variables": {...full input set...}}
}
```

Verify: all children completed, MOP checks passed, templates rendered, adapters called.

---

## Phase 5: ITERATE

When something fails, fix locally and update on the platform.

**Edit locally → PUT to update → re-test.** Don't recreate — updating preserves IDs and references.

| Asset | Update endpoint |
|-------|----------------|
| Workflow | `PUT /automation-studio/automations/{uuid}` with `{"update": {...}}` |
| Template | `PUT /automation-studio/templates/{id}` with `{"update": {...}}` |
| Command Template | `POST /mop/updateTemplate/{name}` with `{"mop": {...}}` (full replacement) |

### Debug checklist

**Check local files FIRST, not the API:**

| Problem | Check |
|---------|-------|
| Wrong endpoint / payload | `jq '.paths["/the/endpoint"]' openapi.json` |
| Task not found | `grep -i "keyword" tasks.json` |
| Wrong app name | `jq '.[].name' apps.json` |
| Need task schema | `task-schemas.json` before calling API |
| Job error | `data.error[].message.IAPerror.displayString` |
| $var not resolving | Task ID hex-only? Inside nested object? |
| Adapter response wrong shape | Test adapter directly, inspect actual output |

---

## Phase 6: VERIFY + DELIVER

### Run acceptance criteria

For each criterion in `solution-design.md` Section F:
1. Run the test
2. Check pass/fail
3. If fail: fix (Phase 5 cycle), re-test

### Verify membership (set in Phase 3)

Confirm that membership was correctly applied after import:
```
GET /automation-studio/projects/{projectId}
```
Check `data.members` — verify the spec's owner and editors are listed, not just the OAuth service account. If membership is missing or wrong, re-run the Phase 3 membership procedure.

### Deliverables

```
{use-case}/
  customer-spec.md          ← what they asked for (HLD)
  solution-design.md        ← how it was built (LLD)
  customer-context.md       ← business rules
  project-import.json       ← full import payload (reproducible)
  cmd-*.json                ← command templates
  tmpl-*.json               ← Jinja2/TextFSM templates
  wf-*.json                 ← workflows (children + parent)
```

Summary to the engineer:
- What was built and where to find it
- How to run it (input variables, trigger)
- What it expects (devices, adapters, credentials)
- Acceptance test results

---

## The Build Cycle (every asset)

```
1. Search local files     (tasks.json, apps.json, adapters.json)
2. Fetch schema           (multipleTaskDetails → task-schemas.json)
3. Read helper template   (helpers/*.json)
4. Build JSON locally     ({use-case}/wf-*.json, tmpl-*.json, cmd-*.json)
5. ── after all assets built locally ──
6. Assemble import payload (project-import.json)
7. POST import             (single atomic call)
8. Test                    (jobs/start or standalone endpoint)
9. Check results           (job status, task output, stdout)
10. Fix + PUT              (edit local JSON, PUT to update — don't recreate)
```

---

## Dependency Graph

```
                    ┌──────────────────┐
                    │ GENERATE IDs     │  ← Phase 1: project_id, UUIDs
                    └──────┬───────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
     │ MOP (cmd)   │ │ Jinja2   │ │  TextFSM    │  ← Phase 2: build locally
     │ templates   │ │ templates│ │  templates   │     (no deps)
     └──────┬──────┘ └────┬─────┘ └──────┬──────┘
            │              │              │
            │         ┌────▼──────────────▼───┐
            │         │   CHILD WORKFLOWS     │  ← build locally
            │         │   (use templates)     │     (reference templates)
            │         └────────────┬──────────┘
            │                      │
            └──────────┬───────────┘
                       │
               ┌───────▼────────┐
               │ PARENT WORKFLOW │  ← build locally
               │ (childJob refs │     (pre-wire @projectId:)
               │  pre-wired)    │
               └───────┬────────┘
                       │
               ┌───────▼────────┐
               │     IMPORT     │  ← Phase 3: single atomic POST
               │ (all assets    │     creates everything inside project
               │  in one call)  │
               └───────┬────────┘
                       │
               ┌───────▼────────┐
               │   TEST + FIX   │  ← Phase 4-5: test each, PUT to fix
               └───────┬────────┘
                       │
               ┌───────▼────────┐
               │ VERIFY+DELIVER │  ← Phase 6: acceptance criteria
               └────────────────┘
```

---

## Why Import Instead of Create + Move

| Problem | Old pattern (create + move) | Import pattern |
|---------|---------------------------|----------------|
| childJob refs | Break on move — must manually fix | Pre-wired with `@projectId:` — just work |
| Project locking | Race conditions during move | Single atomic call — no intermediate state |
| Intermediate state | Workflows exist outside project temporarily | Never — all created inside project |
| Multiple API calls | Create project + create each asset + move each + fix refs | One POST for everything |
| Reproducibility | Hard to replay the exact sequence | `project-import.json` is the complete artifact |

**Tested and verified:** Parent + child workflow imported atomically, childJob ref resolved, job completed successfully with `childStatus: "success"`.
