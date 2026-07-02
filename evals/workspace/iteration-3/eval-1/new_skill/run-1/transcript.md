# Transcript — Builder Agent skill test

## Task restated

Build a workflow that uses a **merge** task to assemble a request body from job
variables `deviceName` and `vlanId`, then passes that body to a ServiceNow
`createChangeRequest` adapter task. No live platform is connected in this
session, so the deliverable is the workflow JSON artifact (tasks, transitions,
incoming/outgoing wiring), not an actual API call.

## Steps taken

1. **Read the skill fully first**, per instructions:
   `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md`
   (2442 lines, read in two passes). Key sections consulted:
   - **Workspace Contract** — the builder must not re-pull/guess bootstrap
     discovery data (`tasks.json`, `apps.json`, `adapters.json`); it uses
     what's already in the use-case workspace.
   - **Guide 1: Build a workflow end-to-end**, specifically:
     - The mandatory pre-flight block ("STOP. Before writing a single line of
       task JSON — run these commands") — extract real task JSON from
       `helpers/assets/`, never invent task structure from memory.
     - **Step 5 — Handle object inputs**: `$var` references cannot resolve
       inside nested objects (e.g. inside an adapter's `body`), so a `merge`
       task must build the object first, and the adapter task wires
       `body: "$var.<mergeId>.merged_object"`.
     - **Step 6 — Handle opaque schemas**: adapter `body` schemas often show
       `{type: "object"}` with no field detail; required fields are
       discovered from validation errors or prior test history.
     - **Step 9 — Pre-submit checklist**: hex-only task IDs, `app`/
       `locationType` from `apps.json` (not `tasks.json`), `adapter_id` from
       `adapters.json` instance list, mandatory error transitions on adapter
       tasks, merge uses `"variable"` (not `"value"`), no duplicate
       transition keys to `workflow_end`.
   - **`### merge`** utility-task reference (incoming/outgoing shape,
     `data_to_merge` reference forms, the `{task:"job"}` → `inputSchema.required`
     side effect, the "min 2 items" and "outgoing must not be `{}`" gotchas).
   - **Guide 2: Debug a failed job** — error table, specifically
     `"Schema validation failed on must have required property 'X'"` → missing
     field in adapter body → add to merge task. Used this to flag a real risk
     in my final recommendation.
   - **AGENTS.md** (repo root, auto-loaded) — directory layout, adapter
     `app` vs. adapter-instance naming rule (Rule 23), auth reuse rules.

2. **Pulled the real, production-tested ServiceNow "Create Change Request"
   workflow** from the asset library, per the skill's mandatory instruction
   not to guess task structure:
   ```bash
   jq '[.components[] | select(.type=="workflow") | select(.document.name | test("Create Change"))] | first | .document | {tasks, transitions, inputSchema, outputSchema}' \
     helpers/assets/vendor-servicenow.json
   ```
   This showed the canonical pattern: `merge` (builds payload) →
   `createChangeRequest` (adapter, `body: $var.<mergeId>.merged_object`,
   `adapter_id: $var.job.adapterId`) → `evaluation`/`query` → error handling
   via a sibling task (never two transitions pointing at the same
   `workflow_end` key directly from one task).

3. **Found a real, already-delivered use-case in this repo** —
   `use-cases/cisco-port-turnup/` — whose `use-case-memory.md` documents a
   *live, tested* ServiceNow Create-Ticket workflow built with this exact
   skill, including hard-won production gotchas:
   - `createChangeRequest` (Servicenow adapter) is the correct task —
     **not** `createChange`, which belongs to an adapter
     (`ServiceNow Change Management API:latest`) that wasn't installed on
     that platform.
   - The adapter **`app`/`locationType` value is `Servicenow`** (from
     `apps.json`), while **`adapter_id` is `ServiceNow`** (the running
     adapter instance, from `adapters.json`) — confirmed against the real
     files:
     ```bash
     jq '.[] | select(.name? | test("servicenow";"i"))' platform/apps.json
     jq '.results[]? | select(.package_id? | test("servicenow";"i"))' use-cases/cisco-port-turnup/adapters.json
     ```
     → `apps.json` entry: `{"id": "@itentialopensource/adapter-servicenow", "name": "Servicenow"}`
     → `adapters.json` entry: `{"id": "ServiceNow", "package_id": "@itentialopensource/adapter-servicenow", "state": "RUNNING"}`
   - **`createChangeRequest`'s body requires a `summary` field** — learned
     from the real job run against the live adapter (documented in
     `use-case-memory.md` under "Gotchas Hit"), not from the schema (the
     `body` field is an opaque `{type:"object"}` in `tasks.json`).
   - The real, tested workflow's task JSON (`import-payload.json`) confirmed
     the exact production shape of the `merge` → `createChangeRequest` pair,
     including `displayName`, node spacing, and the error-handling pattern
     (`newVariable` sink routed to `workflow_end` because JSON can't have
     duplicate `workflow_end` keys on two transitions from the same task).

4. **Built the new workflow** by adapting the verified pattern to the
   requested variables (`deviceName`, `vlanId`) instead of the port-turn-up
   use case's original variables. Wrote the full workflow JSON to:
   `evals/workspace/iteration-3/eval-1/new_skill/run-1/outputs/vlan-change-request-workflow.json`

5. **Validated the JSON** (`jq empty ...` — valid) and checked skill
   checklist items directly: task IDs are hex-only (`e1a1`, `a1b2`, `c3d4`),
   the adapter task (`a1b2`) has both success and error transitions, `merge`
   uses `"variable"` (not `"value"`) in `data_to_merge`, `app`/`locationType`
   come from `apps.json` (`Servicenow`) not `tasks.json` (`ServiceNow`), and
   `adapter_id` (`ServiceNow`) comes from `adapters.json`, not the type name.

## Workflow JSON produced

Written to
`evals/workspace/iteration-3/eval-1/new_skill/run-1/outputs/vlan-change-request-workflow.json`.
Full contents:

```json
{
  "automation": {
    "name": "VLAN Change Request: Create ServiceNow CR",
    "description": "Assembles a ServiceNow change_request body from job variables deviceName and vlanId (via a merge task) and creates the change request via the Servicenow adapter's createChangeRequest task.",
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
      "e1a1": {
        "name": "merge",
        "canvasName": "merge",
        "summary": "Build Change Request Body",
        "description": "Assembles the ServiceNow createChangeRequest body from deviceName and vlanId job variables. $var references cannot resolve inside nested objects, so merge builds the object first.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "data_to_merge": [
              {
                "key": "device_name",
                "value": { "task": "job", "variable": "deviceName" }
              },
              {
                "key": "vlan_id",
                "value": { "task": "job", "variable": "vlanId" }
              }
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
      "a1b2": {
        "name": "createChangeRequest",
        "canvasName": "createChangeRequest",
        "summary": "Create ServiceNow Change Request",
        "description": "Creates the change_request in ServiceNow using the body assembled by the merge task and returns the CHG number.",
        "location": "Adapter",
        "locationType": "Servicenow",
        "app": "Servicenow",
        "type": "automatic",
        "displayName": "ServiceNow",
        "variables": {
          "incoming": {
            "body": "$var.e1a1.merged_object",
            "adapter_id": "ServiceNow"
          },
          "outgoing": {
            "result": "$var.job.changeRequestResult"
          },
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
        "summary": "Set Error Message",
        "description": "Records that the ServiceNow createChangeRequest call failed so the job does not get stuck without an available transition.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "name": "errorMessage",
            "value": "ServiceNow createChangeRequest failed"
          },
          "outgoing": {
            "value": "$var.job.errorMessage"
          },
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
      "workflow_start": {
        "e1a1": { "type": "standard", "state": "success" }
      },
      "e1a1": {
        "a1b2": { "type": "standard", "state": "success" }
      },
      "a1b2": {
        "workflow_end": { "type": "standard", "state": "success" },
        "c3d4": { "type": "standard", "state": "error" }
      },
      "c3d4": {
        "workflow_end": { "type": "standard", "state": "success" }
      },
      "workflow_end": {}
    },
    "groups": [],
    "inputSchema": {
      "type": "object",
      "properties": {
        "deviceName": {
          "title": "deviceName",
          "type": "string",
          "description": "Name of the device the VLAN change applies to (e.g. IOS-CAT8KV-1)"
        },
        "vlanId": {
          "title": "vlanId",
          "type": "integer",
          "description": "VLAN ID being requested/changed (1-4094)"
        }
      },
      "required": ["deviceName", "vlanId"]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "changeRequestResult": {
          "title": "changeRequestResult",
          "type": "object",
          "description": "Raw ServiceNow adapter response from createChangeRequest"
        },
        "serviceNowError": {
          "title": "serviceNowError",
          "type": "object",
          "description": "Adapter error payload if createChangeRequest failed"
        },
        "errorMessage": {
          "title": "errorMessage",
          "type": "string",
          "description": "Human-readable error message set when the ServiceNow call fails"
        }
      }
    }
  }
}
```

## Final answer / recommendation to the engineer

Here's the workflow: `workflow_start → e1a1 (merge) → a1b2 (createChangeRequest) → workflow_end`,
with `a1b2`'s error transition routed to `c3d4 (newVariable)` → `workflow_end`
(can't route both success and error to the same `workflow_end` key from one
task, so the error path gets its own sink task that sets `errorMessage`).

What each task does:

- **`e1a1` (merge, "Build Change Request Body")** — pulls `deviceName` and
  `vlanId` from the job's input variables and assembles them into an object
  (`{"device_name": ..., "vlan_id": ...}`), output as `merged_object`. This
  exists because `$var` references don't resolve inside nested object
  literals like an adapter's `body` — you can't write
  `"body": {"device_name": "$var.job.deviceName"}` and expect it to resolve;
  `merge` is the standard workaround. Note it uses `"variable"` (not
  `"value"`) in `data_to_merge` — that field name is easy to get backwards
  with `childJob`, which uses `"value"` instead.
- **`a1b2` (createChangeRequest, ServiceNow adapter)** — `body` is wired to
  `$var.e1a1.merged_object`; `adapter_id` is `"ServiceNow"` (the running
  adapter *instance* name), while `app`/`locationType` are `"Servicenow"`
  (the adapter *type* name from `apps.json` — these two are commonly
  confused and using the wrong one throws `"No config found for Adapter"`).
  Both a success and an error transition are present, as required for any
  adapter task.
- **`c3d4` (newVariable)** — error sink so the job never gets stuck with "no
  available transitions" if ServiceNow rejects the request.

**One real gotcha to flag before you test this** — pulled from this exact
repo's `use-cases/cisco-port-turnup/use-case-memory.md`, where the same
`createChangeRequest` task was built and tested against a live ServiceNow
instance: **the adapter's `body` schema is opaque (`{type: "object"}`) but in
practice ServiceNow rejects the call unless a `summary` field is present** —
the documented production error was
`"must have required property 'summary'"`. Your two source variables,
`deviceName` and `vlanId`, don't map to a ServiceNow `summary`/`description`
field on their own. As built, this workflow will very likely fail its first
test run with that exact validation error (see Guide 2's error table: "Schema
validation failed on must have required property 'X'" → add the field to the
merge task).

Before you run this for real, decide one of:
1. Add a `summary` (and ideally `description`) job variable as a third
   workflow input, and merge it into the body alongside `device_name`/
   `vlan_id`, e.g. `"VLAN <vlanId> change — <deviceName>"`, or
2. If you want the summary auto-generated purely from `deviceName`/`vlanId`
   with no extra input, add a `makeData` task upstream (with `<!deviceName!>`/
   `<!vlanId!>` template substitution, fed by a small merge that resolves
   those two into a flat object) to build the summary string, then include
   that computed value as a third key in `e1a1`'s `data_to_merge`.
3. If your ServiceNow instance has custom fields for network changes (e.g.
   `u_device_name`/`u_vlan_id`), confirm the exact field names against the
   target `change_request` table — I used `device_name`/`vlan_id` as
   placeholders since the schema doesn't expose custom field names, and
   Guide 1 Step 6's discovery method (minimal-body test → read the
   validation error, or check `openapi.json`) is the reliable way to confirm
   them on your instance.

I deliberately built exactly what was asked (merge of `deviceName`/`vlanId`
→ `createChangeRequest`) rather than guessing at a `summary` field's content,
since inventing business content the task didn't ask for isn't something the
skill supports — but I didn't want you to hit that failure blind on first
test.

## Files

- Workflow JSON artifact:
  `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-1/new_skill/run-1/outputs/vlan-change-request-workflow.json`
- Skill consulted:
  `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md`
- Reference asset used:
  `/Users/ankitrbhansali/builderskills/builder-skills/helpers/assets/vendor-servicenow.json`
- Real, tested precedent used for adapter naming/gotchas:
  `/Users/ankitrbhansali/builderskills/builder-skills/use-cases/cisco-port-turnup/use-case-memory.md`
  and `/Users/ankitrbhansali/builderskills/builder-skills/use-cases/cisco-port-turnup/import-payload.json`
