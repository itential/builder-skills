# Transcript — Wire up a merge task's `data_to_merge` for a ServiceNow update body

## Task as given

The engineer has a workflow where a `query` task already extracts a `changeId` from a
ServiceNow adapter response (`outgoing: return_data -> $var.job.changeId`). They now need a
`merge` task to build the update-request body, which must contain that `changeId` plus a
static `status` field. Deliverable: the merge task's `data_to_merge` wiring (and enough
surrounding context to make it usable).

## Skill sections consulted

Read `/tmp/eval-old-skill/builder-agent/SKILL.md` in full (2314 lines) before responding, per
instructions. Sections used directly:

1. **Guide 1, Step 5 — "Handle object inputs"** (lines ~308-331): establishes the core reason a
   merge task is needed at all — `$var` references do not resolve inside nested objects (like an
   adapter's `body`), so a `merge` task must assemble the object first, and the adapter task then
   references `$var.<mergeTaskId>.merged_object`.
2. **`### merge` reference section** (lines ~1302-1331): canonical incoming/outgoing schema for
   merge — `data_to_merge` (array, **min 2 items**), reference formats
   (`{"task":"job","variable":"x"}`, `{"task":"static","variable":"x"}`,
   `{"task":"taskId","variable":"outVar"}`), and the gotchas: field name is `"variable"` **not**
   `"value"` (that's for childJob only), outgoing must declare `"merged_object": null` (not `{}`),
   and duplicate keys silently become arrays instead of overwriting.
3. **`$var` Resolution Rules — static-value gotcha** (lines ~1263-1267): this is the one that
   changes the recommended wiring. `task:"static"` reference objects (the kind used directly
   inside `data_to_merge`) are backed by `job_data` written at **Studio-save time** — on a
   workflow created or updated purely via API (no human opening it in Automation Studio and
   hitting Save), any `{"task":"static", ...}` reference resolves to **null at runtime**. The
   skill's documented workaround is the "constant-holder" pattern: park the literal in a
   `newVariable` task (whose own `incoming.value` literal *does* resolve correctly after a pure
   API create/PUT — this is explicitly confirmed in the doc's `makeData` gotcha aside), and have
   the merge task pull the value by task-reference (`{"task":"<newVariableTaskId>","variable":"value"}`)
   instead of by `task:"static"`.
4. **Guide 1, Step 9 — Pre-submit checklist** (lines ~351-370): confirmed `merge uses "variable",
   childJob uses "value"`, hex-only task IDs, every adapter task needs an error transition, and
   the canvas-layout rules (spine x, ±264 fork offset, 108px y-delta) used for `nodeLocation`.
5. **"STOP" banner before Guide 1** (lines ~163-193) and **Task Discovery → "Look up task wiring
   in asset projects first"** (lines ~926-952): both instruct pulling real, production-tested task
   JSON from `helpers/assets/` rather than inventing schema from memory.

## Real asset files consulted (per repo context, `CLAUDE_PLUGIN_ROOT` = this repo)

```bash
ls /Users/ankitrbhansali/builderskills/builder-skills/helpers/assets/
# vendor-servicenow.json is the correct match for ServiceNow adapter tasks per the skill's lookup table
```

Pulled the real "Update Change Request" workflow (the closest production example of a merge +
adapter-update sequence against ServiceNow):

```bash
jq '[.components[] | select(.type=="workflow") | select(.document.name | test("Update Change"))] | first | .document | {tasks, transitions}' \
  helpers/assets/vendor-servicenow.json
```

Key things learned from the real asset that I used verbatim rather than guessing:
- The real `updateChangeRequest` adapter task uses `app: "Servicenow"`, `locationType: "Servicenow"`,
  `displayName: "Servicenow"`, and its `adapter_id` is wired from a job variable named
  `$var.job.adapterId` (camelCase) — I used this naming convention for the fragment rather than
  the illustrative `adapter_id`/`$var.job.adapter_id` shown generically in the guide text.
- **Important divergence to flag to the engineer:** in the real production asset, `changeId` is a
  **separate, top-level incoming field** on `updateChangeRequest` (sibling to `body`), not a field
  *inside* the body object:
  ```json
  "incoming": {
    "changeId": "$var.e4c7.crSysId",
    "body": "$var.e4c7.crUpdatePayload",
    "adapter_id": "$var.job.adapterId"
  }
  ```
  Since `changeId` here is a top-level scalar, `$var.job.changeId` resolves fine on its own —
  no merge needed for it. That real workflow uses a `transformation` (JST) task, not `merge`, to
  build the body (`variableMap` style), which is a different (also valid) approach to the same
  "can't put `$var` inside a nested object" problem.
  The engineer's task explicitly asked for a **merge** task and described **changeId + a static
  status field going into the merge**, which implies their target schema (possibly a different
  adapter, or the same one used differently) wants `changeId` folded into the body object itself,
  not passed as ServiceNow's separate top-level field. I built the artifact to match what was
  literally asked (merge produces `{changeId, status}` as the body), but flagged this schema
  question below — it needs to be confirmed against the actual target task schema
  (`task-schemas.json` / `POST /automation-studio/multipleTaskDetails`) before this ships, per
  Guide 1 Step 6 ("opaque schema" handling).
- Confirmed real `merge` task shape (`ade8`, `aab9` in the asset) has only `incoming`/`outgoing` —
  no `error`/`decorators` block (those are only on adapter tasks in the real examples), matching
  what the skill's `### merge` reference section shows.
- Confirmed real `newVariable` task shape (`helpers/assets/vendor-arista-eos.json`,
  `itential-platform-configuration-management.json`): `incoming: {name, value}`,
  `outgoing: {value: ""}`. This is the exact shape needed for the constant-holder workaround.

## Artifact produced

Written to:
`/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-21/old_skill/run-1/outputs/merge-task-wiring.json`

```json
{
  "tasks": {
    "b2c3": {
      "name": "query",
      "canvasName": "query",
      "summary": "Extract Change ID",
      "description": "Extracts the changeId from the ServiceNow createChangeRequest adapter response",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "pass_on_null": false,
          "query": "response.sys_id",
          "obj": "$var.a1b2.result"
        },
        "outgoing": { "return_data": "$var.job.changeId" },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": {"x": 600, "y": 312}
    },
    "c9a1": {
      "name": "newVariable",
      "canvasName": "newVariable",
      "summary": "Set Update Status Constant",
      "description": "Holds the static status value used when building the change request update payload",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": { "name": "updateStatus", "value": "REPLACE_WITH_ACTUAL_STATUS_LITERAL" },
        "outgoing": { "value": "" }
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 420}
    },
    "e1a1": {
      "name": "merge",
      "canvasName": "merge",
      "summary": "Build Update Request Body",
      "description": "Builds the changeId + status payload for the ServiceNow update call",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "data_to_merge": [
            {"key": "changeId", "value": {"task": "job", "variable": "changeId"}},
            {"key": "status", "value": {"task": "c9a1", "variable": "value"}}
          ]
        },
        "outgoing": { "merged_object": null }
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 528}
    },
    "f4d2": {
      "name": "updateChangeRequest",
      "canvasName": "updateChangeRequest",
      "summary": "Update Change Request",
      "description": "Updates the ServiceNow change request with the new status",
      "location": "Adapter",
      "locationType": "Servicenow",
      "app": "Servicenow",
      "type": "automatic",
      "displayName": "Servicenow",
      "variables": {
        "incoming": {
          "changeId": "$var.job.changeId",
          "body": "$var.e1a1.merged_object",
          "adapter_id": "$var.job.adapterId"
        },
        "outgoing": { "result": "$var.job.updatedCR" },
        "error": "$var.job.serviceNowError",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": {"x": 600, "y": 636}
    },
    "ef01": {
      "name": "newVariable",
      "canvasName": "newVariable",
      "summary": "Handle Update Error",
      "description": "Marks the update as failed for downstream/parent inspection",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": { "name": "taskStatus", "value": "error" },
        "outgoing": { "value": "" }
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 864, "y": 636}
    }
  },
  "transitions": {
    "b2c3": { "c9a1": {"type": "standard", "state": "success"} },
    "c9a1": { "e1a1": {"type": "standard", "state": "success"} },
    "e1a1": { "f4d2": {"type": "standard", "state": "success"} },
    "f4d2": {
      "workflow_end": {"type": "standard", "state": "success"},
      "ef01": {"type": "standard", "state": "error"}
    },
    "ef01": { "workflow_end": {"type": "standard", "state": "success"} }
  }
}
```

(Full file, with inline `_comment` explaining each task's rationale, is in the outputs directory.)

## Pre-submit checklist run against the artifact (Guide 1 Step 9)

- [x] Task IDs hex-only: `b2c3`, `c9a1`, `e1a1`, `f4d2`, `ef01` — all `[0-9a-f]{1,4}`.
- [x] `app`/`locationType` for the adapter task (`Servicenow`) come from the real asset's apps.json-derived value, not the tasks.json display casing (`ServiceNow`).
- [x] `adapter_id` wired from a job variable (`$var.job.adapterId`), not a literal.
- [x] Adapter task (`f4d2`) has both a success and an error transition.
- [x] `merge` uses `"variable"` in its reference objects, not `"value"`.
- [x] `merge.data_to_merge` has 2 items (minimum required).
- [x] `merge` outgoing declares `"merged_object": null` (not `{}`).
- [x] No `$var` references placed inside a nested object — the merge task is exactly the mechanism used to avoid that.
- [x] Shared error handler (`ef01`) used instead of routing both success and error to `workflow_end` from the same task (avoids duplicate JSON keys).
- [x] Canvas layout follows the vertical spine convention: single-thread tasks on `x=600` with 108px y-steps; the error-handler fork offsets to `x=864` (`spine+264`) and converges back to `workflow_end` on the spine.

## Final answer / recommendation to the engineer

Here's the merge task, wired the way you described — `changeId` plus a static status field
feeding the update body:

```json
"e1a1": {
  "name": "merge",
  "variables": {
    "incoming": {
      "data_to_merge": [
        {"key": "changeId", "value": {"task": "job", "variable": "changeId"}},
        {"key": "status",   "value": {"task": "c9a1", "variable": "value"}}
      ]
    },
    "outgoing": { "merged_object": null }
  }
}
```

Two things about this that aren't obvious and will bite you if skipped:

1. **Don't wire the static status field as `{"task": "static", "variable": "..."}` directly in
   `data_to_merge`.** That's the natural way to write a literal into a merge task, and it's what
   the field format supports, but static-task reference values are backed by `job_data` that only
   gets written when a human opens the workflow in Automation Studio and clicks Save. If you
   create or update this workflow purely through the API (which is how you'd deploy it), that
   status value will silently resolve to `null` at runtime — no error, it just won't be there in
   the request body. I routed around this by parking the literal in a small `newVariable` task
   (`c9a1`) and having the merge task pull it by task-reference
   (`{"task": "c9a1", "variable": "value"}`) instead. `newVariable`'s own literal *does* resolve
   correctly right after an API create, so this sidesteps the problem entirely. Replace
   `"REPLACE_WITH_ACTUAL_STATUS_LITERAL"` in `c9a1.variables.incoming.value` with your real status
   value (e.g. whatever your ServiceNow instance expects for the field — often a numeric state
   code like `"2"` rather than a label — verify against the target schema/instance rather than
   guessing).

2. **Confirm `changeId` actually belongs inside the body object for your adapter task, not as a
   sibling field.** I checked the real, production `Update Change Request` workflow shipped in
   this skill's asset library (`helpers/assets/vendor-servicenow.json`), and in that workflow
   ServiceNow's `updateChangeRequest` adapter task takes `changeId` as its own **top-level**
   incoming field, separate from `body`:
   ```json
   "incoming": { "changeId": "$var...", "body": "$var...", "adapter_id": "$var..." }
   ```
   If your target task has the same shape, you don't need `changeId` inside the merge at all —
   wire `"changeId": "$var.job.changeId"` straight onto the adapter task (it's a top-level scalar,
   so it resolves fine without a merge), and let the merge task build just the `status` (plus
   whatever other body fields you have — merge needs at least 2 items total, so if `status` ends
   up being your only body field you'll need to add a second one or fold it into a different
   mechanism, e.g. a `transformation`/JST task as that same asset workflow does). I built the
   artifact to match what you described literally (`changeId` inside the merged body) since that's
   what you asked for, but pull the actual task schema for whichever update task you're calling
   (`task-schemas.json`, or `POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true`)
   before shipping this, so you're not guessing at the body shape.

Downstream wiring, once the merge output is `$var.e1a1.merged_object`:

```json
"f4d2": {
  "name": "updateChangeRequest",
  "variables": {
    "incoming": {
      "changeId": "$var.job.changeId",
      "body": "$var.e1a1.merged_object",
      "adapter_id": "$var.job.adapterId"
    },
    "outgoing": { "result": "$var.job.updatedCR" },
    "error": "$var.job.serviceNowError"
  }
}
```

Don't forget the error transition off this adapter task — I routed it to a small `newVariable`
error handler (`ef01`) that also converges on `workflow_end`, since a JSON object can't have two
keys named `workflow_end` under the same task's transitions.

Full task+transitions JSON (with the existing `query` task shown for context, plus the new
`newVariable` constant-holder, `merge`, adapter-update, and error-handler tasks) is in
`outputs/merge-task-wiring.json`.

## Note on scope / caveats

- No live Itential platform is connected in this session. This was a build/wiring task, so the
  deliverable is the JSON artifact above rather than an API call — no HTTP calls were attempted
  and no platform responses were fabricated.
- I did not have this engineer's actual `tasks.json` / `apps.json` / `adapters.json` /
  `task-schemas.json` for their specific use-case workspace (none was provided), so I sourced the
  adapter task field names and conventions from the real, production-tested asset file
  (`helpers/assets/vendor-servicenow.json`) as the skill instructs, rather than from memory. The
  literal status value and the exact body shape still need to be confirmed against the engineer's
  actual target task schema before this is deployed — flagged above.
