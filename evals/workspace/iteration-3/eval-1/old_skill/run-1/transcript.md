# Transcript — builder-agent skill test

## Task restated

Build a workflow that:
1. Uses a `merge` task to assemble a request body from job variables `deviceName` and `vlanId`.
2. Passes that assembled body to a ServiceNow `createChangeRequest` adapter task.

No live Itential Platform is connected in this session. Deliverable is the workflow JSON artifact (tasks, transitions, incoming/outgoing wiring), not a live API call.

## Skill sections/files consulted

1. **`/tmp/eval-old-skill/builder-agent/SKILL.md`** — read in full (2314 lines). Key sections used:
   - **Guide 1: Build a workflow end-to-end** — the "STOP" block mandating that task JSON be extracted from `helpers/assets/` (real production imports) rather than written from memory or guessed.
   - **Guide 1, Steps 1–4** — task discovery (`tasks.json`), adapter app-name resolution (`apps.json`), adapter instance resolution (`adapters.json`), and the schema→task-JSON mapping rules.
   - **Guide 1, Step 5 "Handle object inputs"** — the exact justification for why a `merge` task is required in front of an adapter task whose incoming `body` is `type: object` (because `$var` refs don't resolve inside nested objects).
   - **Guide 1, Step 7** — transition wiring rules (every adapter task needs success + error; can't route both to `workflow_end` directly due to duplicate-key constraint on the transitions map, so error routes through an intermediate task).
   - **Guide 1, Step 9 "Pre-submit checklist"** — used as the acceptance checklist for the final JSON.
   - **Guide 1 "Complete working example"** — the ServiceNow "Create Change Request" workflow, which is the closest real, production-tested analog to this exact task (merge → createChangeRequest with error transition).
   - **`### merge`** (Utility Tasks section) — confirms `data_to_merge` uses the key `"variable"` (NOT `"value"`), requires ≥2 items, and that `merged_object` outgoing must be declared non-empty.
   - **`### $var Resolution Rules`** — confirms direct top-level `$var` refs work, nested ones don't; and the "outgoing must write to job var" gotcha, used to decide `outgoing.result` → `$var.job.createdCR`.
   - **`## Gotchas`** (items 8, 9, 11, 13, 14, 15, 16, 33) — cross-checked the final JSON against these before finishing.
   - **`### Workflow Structure`** — used for the top-level workflow document shape (`automation` wrapper, `canvasVersion`, `encodingVersion`, `tasks`/`transitions`/`inputSchema`/`outputSchema`).
   - **`### nodeLocation Spacing Convention`** — used for canvas layout (constant-x spine, ±264 fork offset, ~108px y-delta).

2. **Real repo asset files** (resolved `${CLAUDE_PLUGIN_ROOT}` = `/Users/ankitrbhansali/builderskills/builder-skills`), pulled per the skill's exact `jq` commands:
   - `helpers/assets/vendor-servicenow.json` — confirmed a "Create Change Request" workflow exists; extracted its full `tasks`/`transitions` map. This is the "real, production-tested import" the skill's STOP block requires reading before writing any task JSON.
   - `platform/tasks.json` — looked up `createChangeRequest` and `merge` task entries (`name`, `app`, `type`, `location`, `canvasName`, `displayName`).
   - `platform/apps.json` — looked up the correct adapter type name for ServiceNow, per the skill's mandatory rule that `app`/`locationType` must come from `apps.json`, not `tasks.json`.
   - `platform/adapters.json` — looked up the ServiceNow adapter **instance** id (`.results[] | select(.package_id | test("servicenow"))`).

   I did not fabricate any of these values — every field in the final JSON traces back to one of these three files or the asset workflow example.

## Key findings during discovery (real data, not fabricated)

**From `helpers/assets/vendor-servicenow.json`** ("Create Change Request" workflow, task `aab9`/`cc49`):
```json
"aab9": {
  "name": "merge",
  "variables": {
    "incoming": {
      "data_to_merge": [
        {"key": "title", "value": {"task": "job", "variable": "title", "editable": true}}
      ]
    },
    "outgoing": {"merged_object": null}
  }
},
"cc49": {
  "name": "createChangeRequest",
  "location": "Adapter",
  "locationType": "Servicenow",
  "app": "Servicenow",
  "type": "automatic",
  "displayName": "Servicenow",
  "variables": {
    "incoming": {
      "body": "$var.aab9.merged_object",
      "adapter_id": "$var.job.adapterId"
    },
    "outgoing": {"result": "$var.job.createdCR"},
    "error": "$var.job.serviceNowError"
  }
}
```
This confirmed the merge→adapter wiring pattern (`body: "$var.<mergeTaskId>.merged_object"`) and the `"variable"` key (not `"value"`) inside `data_to_merge`.

**From `platform/tasks.json`:**
```json
{"name": "createChangeRequest", "app": "ServiceNow", "type": "automatic", "location": "Adapter", "canvasName": "createChangeRequest", "displayName": "ServiceNow"}
{"name": "merge", "app": "WorkFlowEngine", "type": "operation", "location": "Application", "canvasName": "merge", "displayName": "WorkFlowEngine"}
```
Note: `tasks.json` reports `app: "ServiceNow"` (capital N) for the adapter task — per the skill this is explicitly **wrong** and must not be used for the task's `app`/`locationType` fields.

**From `platform/apps.json`:**
```json
{"id": "@itentialopensource/adapter-servicenow", "type": "Adapter", "name": "Servicenow"}
```
Confirms the correct `app`/`locationType` value is `"Servicenow"` (matches the real asset workflow exactly, and differs from `tasks.json`'s `"ServiceNow"` — exactly the trap the skill warns about).

**From `platform/adapters.json`:**
```json
{"id": "ServiceNow", "package_id": "@itentialopensource/adapter-servicenow", "state": "RUNNING"}
```
Confirms the adapter **instance** id (`adapter_id`) is `"ServiceNow"`.

I could not fetch a live task schema (no platform connection; `POST /automation-studio/multipleTaskDetails` requires a live API). Per Guide 1 Step 6, I fell back to the real, wired example in `vendor-servicenow.json`, which already shows the exact `body`/`adapter_id` incoming shape for `createChangeRequest` — this satisfies the skill's instruction to prefer an asset-project example over fetching schemas fresh.

## Workflow built

Structure: `workflow_start → merge (a1a1) → createChangeRequest (b2b2) → workflow_end`, with `b2b2`'s error transition routed to an intermediate `newVariable` task (`c3d4`) before reaching `workflow_end` — required because JSON transition maps can't have the `workflow_end` key twice under the same source task.

Full workflow JSON (also saved to `outputs/create-change-request-workflow.json`):

```json
{
  "automation": {
    "name": "Create Change Request From Device VLAN Data",
    "description": "Builds a ServiceNow change request body from job variables deviceName and vlanId via a merge task, then creates the change request via the ServiceNow adapter.",
    "type": "automation",
    "canvasVersion": 3,
    "encodingVersion": 1,
    "font_size": 12,
    "tasks": {
      "workflow_start": {
        "name": "workflow_start",
        "groups": [],
        "nodeLocation": { "x": 600, "y": 200 }
      },
      "a1a1": {
        "name": "merge",
        "canvasName": "merge",
        "summary": "Build Change Request Payload",
        "description": "Assembles the ServiceNow change request body from job variables deviceName and vlanId. A merge task is required because $var references cannot resolve inside a nested object (the adapter's body field).",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "data_to_merge": [
              { "key": "deviceName", "value": { "task": "job", "variable": "deviceName" } },
              { "key": "vlanId", "value": { "task": "job", "variable": "vlanId" } }
            ]
          },
          "outgoing": { "merged_object": null },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 308 }
      },
      "b2b2": {
        "name": "createChangeRequest",
        "canvasName": "createChangeRequest",
        "summary": "Create Change Request",
        "description": "Creates the ServiceNow change request using the body built by the merge task.",
        "location": "Adapter",
        "locationType": "Servicenow",
        "app": "Servicenow",
        "type": "automatic",
        "displayName": "ServiceNow",
        "variables": {
          "incoming": {
            "body": "$var.a1a1.merged_object",
            "adapter_id": "ServiceNow"
          },
          "outgoing": { "result": "$var.job.createdCR" },
          "error": "$var.job.serviceNowError",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 416 }
      },
      "c3d4": {
        "name": "newVariable",
        "canvasName": "newVariable",
        "summary": "Set Error Status",
        "description": "Records that the ServiceNow change request creation failed, so the workflow still completes cleanly instead of hanging.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": { "name": "taskStatus", "value": "error" },
          "outgoing": { "value": "$var.job.taskStatus" },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": { "x": 864, "y": 524 }
      },
      "workflow_end": {
        "name": "workflow_end",
        "groups": [],
        "nodeLocation": { "x": 600, "y": 632 }
      }
    },
    "transitions": {
      "workflow_start": { "a1a1": { "type": "standard", "state": "success" } },
      "a1a1": { "b2b2": { "type": "standard", "state": "success" } },
      "b2b2": {
        "workflow_end": { "type": "standard", "state": "success" },
        "c3d4": { "type": "standard", "state": "error" }
      },
      "c3d4": { "workflow_end": { "type": "standard", "state": "success" } },
      "workflow_end": {}
    },
    "groups": [],
    "inputSchema": {
      "type": "object",
      "properties": {
        "deviceName": { "title": "deviceName", "type": "string", "description": "Name of the device the change request relates to." },
        "vlanId": { "title": "vlanId", "type": "integer", "description": "VLAN ID the change request relates to." }
      },
      "required": ["deviceName", "vlanId"]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "createdCR": { "title": "createdCR", "type": "object", "description": "The ServiceNow adapter response for the created change request." },
        "serviceNowError": { "title": "serviceNowError", "type": "object", "description": "Populated only if the ServiceNow adapter call errors." },
        "taskStatus": { "title": "taskStatus", "type": "string", "description": "Set to 'error' if change request creation failed." }
      }
    }
  }
}
```

## Pre-submit checklist (Guide 1, Step 9) — verified

- [x] Task IDs are hex-only: `a1a1`, `b2b2`, `c3d4` (plus fixed `workflow_start`/`workflow_end`)
- [x] `app`/`locationType` = `"Servicenow"`, from `platform/apps.json`, NOT `platform/tasks.json`'s `"ServiceNow"`
- [x] `adapter_id` = `"ServiceNow"`, the adapter **instance** id from `platform/adapters.json` `.results[].id`, not a type name
- [x] `canvasName` = `"createChangeRequest"`, from `platform/tasks.json`
- [x] Adapter task has `adapter_id` in incoming
- [x] Adapter task has an error transition (`b2b2` → `c3d4` on `state: error`)
- [x] No `$var` references inside nested objects — `body` is a single top-level `$var.a1a1.merged_object` reference, not a literal object with embedded `$var`s
- [x] `merge` uses `"variable"` (confirmed in `data_to_merge`, not `"value"`)
- [x] `merge` has 2 items in `data_to_merge` (`deviceName`, `vlanId`) — satisfies the ≥2 minimum (1 item silently returns null per the merge gotcha)
- [x] `workflow_end` transition is empty `{}`
- [x] No duplicate `workflow_end` key under a single source task — error routed through intermediate `c3d4` first
- [x] Canvas layout follows the vertical spine convention: spine at `x=600`, fork branch (`c3d4`) offset to `x=864` (spine+264), ~108px sequential y-delta, spine column empty at the branch row so lines don't cross nodes

I ran `jq` validation locally to confirm the file is syntactically valid JSON and that the wiring (`data_to_merge` uses `"variable"`, `body` references `$var.a1a1.merged_object`, `b2b2` has an error transition) is present as intended. I could not run the platform's own `POST /automation-studio/workflows/validate` or an actual `jobs/start` test because no live Itential Platform is connected in this session — that step is a hard requirement from the skill (`Testing & Debugging` section) before this workflow is actually created/updated on a real instance.

## Final answer / recommendation to the engineer

Here's the workflow: `create-change-request-workflow.json` (saved next to this transcript). It does exactly what you asked — a `merge` task (`a1a1`) pulls `deviceName` and `vlanId` off the job and assembles them into a single object, and that object is wired straight into the ServiceNow `createChangeRequest` adapter task's `body` field via `$var.a1a1.merged_object`.

A few things worth flagging before you push this to a real environment:

1. **Why the merge task is mandatory, not optional**: `createChangeRequest`'s `body` field is a nested object, and `$var` references don't resolve when they're embedded inside a nested object — only as a direct top-level value. Wiring `deviceName`/`vlanId` straight into a literal `body: {...}` would silently store the literal strings `"$var.job.deviceName"` etc. instead of resolving them. The merge task builds the object first so the adapter task can reference it with one clean top-level `$var`.

2. **`app`/`locationType` traps**: I pulled the ServiceNow adapter type name from this repo's `platform/apps.json` (`"Servicenow"`), not `platform/tasks.json` (which reports `"ServiceNow"` — capital N). Using the `tasks.json` value here would produce a `"No config found for Adapter: ServiceNow"` runtime error. Same for `adapter_id` — I used the adapter **instance** id from `platform/adapters.json` (`"ServiceNow"`), not a type or spec identity value. **Before you deploy this for real, re-run these three lookups against your target environment's live `tasks.json`/`apps.json`/`adapters.json`** — the values I used come from this repo's reference `platform/` snapshot, not a live-connected instance, since no platform was reachable in this session.

3. **Error handling**: `createChangeRequest` has an error transition to a small `newVariable` task that sets `taskStatus = "error"` before reaching `workflow_end` — this avoids the "Job has no available transitions" hang the skill warns about, and avoids the JSON duplicate-key problem you'd hit trying to route both success and error directly to `workflow_end`.

4. **`body` schema is opaque**: I don't have a live `multipleTaskDetails` schema fetch for `createChangeRequest` (no platform connection), so I based the wiring pattern on the real, already-wired "Create Change Request" workflow in this repo's `helpers/assets/vendor-servicenow.json`. That example uses fields like `title`/`summary`/`description`/`assignment_group`, not `deviceName`/`vlanId` — ServiceNow's change request table doesn't have native `deviceName`/`vlanId` columns, so if your ServiceNow instance expects specific field names (e.g., `short_description`, `cmdb_ci`), you'll want to confirm the required body shape against your instance's schema or a test run's validation error (`"must have required property 'X'"`) before relying on this as final. I built exactly what was asked — a merge of `deviceName`/`vlanId` into the body — but flag this as an open item for you to confirm against the actual ServiceNow change-request field mapping.

5. Not run: `POST /automation-studio/workflows/validate` and an actual `jobs/start` test — both require a live platform connection that isn't available in this session. Please run both before considering this workflow production-ready.
