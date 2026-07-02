# Transcript — builder-agent skill test

## Task (as given)

Create a workflow with `makeData` that generates a JSON string containing `deviceName` and `action` fields from job variables.

No live Itential Platform is connected in this session. Per instructions, I produced the actual JSON artifact (task/transition/schema wiring) as the deliverable rather than making real HTTP calls, and I resolved `${CLAUDE_PLUGIN_ROOT}` to the real repo at `/Users/ankitrbhansali/builderskills/builder-skills`, pulling real task JSON from the real asset files under `helpers/assets/` rather than working from memory.

## Steps taken

1. **Read the skill in full** — `/tmp/eval-old-skill/builder-agent/SKILL.md` (2313 lines). Read it in two passes (offset 0–1126, 1127+) plus targeted `grep`/`Read` passes on the sections relevant to `makeData`:
   - "Guide 1: Build a workflow end-to-end" (Steps 0–9, pre-submit checklist)
   - "`$var` Resolution Rules" section (nested-object resolution, `incomingRefs` cache behavior, static-value caching)
   - "Utility Tasks (WorkFlowEngine)" → `merge`, `makeData`, `newVariable` subsections
   - "Variable Syntax Reference" table (`<!var!>` placeholder syntax)
   - "Gotchas" flat list, items 11, 12, 22, 23 (all `makeData`/nested-object related)

2. **Did not build from memory.** Per the skill's explicit "STOP" instruction in Guide 1, I pulled real, production-tested task JSON from `helpers/assets/` using the documented `jq` lookup commands, rather than guessing the `makeData`/`merge` task shape:

   ```bash
   # Find a real makeData task
   jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "makeData")] | first | .value' \
     helpers/assets/itential-platform-configuration-management.json

   # Find which workflow uses it, to see the full context
   jq '[.components[] | select(.type=="workflow") | select(.document.tasks // {} | to_entries[] | .value.name == "makeData")] | first | .document | {name, tasks, transitions}' \
     helpers/assets/itential-platform-configuration-management.json

   # Cross-check against a second real example (LCM VXLAN project)
   jq -c '.data.components[] | select(.type=="workflow") | select(.document.tasks != null) | .document.tasks | to_entries[] | select(.value.name=="makeData") | .value' \
     helpers/assets/lcm/lcm-vxlan-fabric-services-project.json

   # Real merge task example (from the ServiceNow "Create Change Request" workflow referenced in Guide 1)
   jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "merge")] | first | .value' \
     helpers/assets/vendor-servicenow.json

   # Real workflow_start / workflow_end node shape
   jq '[.components[] | select(.type=="workflow")] | first | .document.tasks | {workflow_start, workflow_end}' \
     helpers/assets/vendor-servicenow.json
   ```

   Findings from the real data:
   - `makeData`'s `variables` incoming field is always wired to a task-to-task ref (`"$var.<taskId>.<outVar>"`) that points at an already-resolved object — in the config-management asset it's `"$var.7c0d.options"` (output of a `transformation` task); in the LCM asset it's `"$var.c10.templateInputs"` (also a `transformation` output). This matches the skill's explicit instruction: *"The `variables` field must be a resolved object. Use merge first to build it, then pass via `$var.taskId.merged_object`."* Since this task's data source is plain job variables (not a JST transformation), `merge` is the right upstream task per the skill's own guidance, and it's the pattern shown in Guide 1 Step 5.
   - `makeData`'s `input` field uses `<!var!>` placeholders whose names match the **keys** produced by the upstream object (e.g., the LCM example's input string `"...Server VLAN: <!accessVlan!>..."` matches a key `accessVlan` in the `templateInputs` object it references).
   - Real `merge` tasks use `{"key": ..., "value": {"task": "job", "variable": "..."}}` entries in `data_to_merge`, confirming the "`merge` uses `\"variable\"`, not `\"value\"`" rule (Gotcha #15).
   - `location: "Application"`, `locationType: null`, `app: "WorkFlowEngine"` for both `merge` (`displayName: "WorkFlowEngine"`) and `makeData` (`displayName: "Tools"`) — matched exactly in both real examples.

3. **Applied Guide 1's mapping/build rules** to construct the workflow:
   - Step 0 decompose: this is a single, simple, sequential transform — no parent/child split needed (not loop-based, not independently-reusable across other use cases, no adapter calls).
   - Step 4 mapping table: `actor: "Pronghorn"` (non-childJob), `type: "operation"` for `merge`, `type: "automatic"` for `makeData` (confirmed against both pulled examples).
   - Step 5 ("Handle object inputs"): `makeData`'s `variables` field is effectively an object-typed incoming value, so it needs the merge-first pattern — can't just point two separate `$var.job.x` refs at it.
   - Step 7 (transitions): only `success` transitions are needed — `merge`/`makeData` are internal WorkFlowEngine utility tasks, not adapter/external calls, so Gotcha #13's "every adapter/external task needs an error transition" rule doesn't apply (confirmed: neither real `merge` nor real `makeData` example task carried an error transition in its host workflow).
   - Step 8: added `inputSchema` (`deviceName`, `action`, both required strings) and `outputSchema` (`deviceActionJson`, string).
   - Step 9 pre-submit checklist: verified hex task IDs (`e1a1`, `a1b2`), `merge` uses `"variable"` not `"value"`, `merge` has ≥2 items (Gotcha #16), no `$var` inside nested objects, `workflow_end` transition is empty `{}`, canvas layout follows the vertical spine convention (single straight sequence, x=600 constant, y-delta 108px, no fork needed since there's no branching logic).

4. **Chose `outputType: "string"` deliberately.** The task asks for "a JSON string" (a string value containing JSON-formatted text), not a parsed JSON object. `makeData`'s `outputType` enum is `string`/`json`/`number`/`boolean` (per the skill's `makeData` subsection). `outputType: "json"` would have `makeData` attempt to parse the rendered text into an object/array, which is the opposite of what was asked. `outputType: "string"` renders the placeholder-substituted text and returns it as a plain string — exactly "a JSON string containing deviceName and action fields."

5. **Wired the final output to a job variable** (`"output": "$var.job.deviceActionJson"`) rather than leaving it `null`, per the rule: *"Outgoing must write to job var for cross-task `$var` to be readable by downstream tasks... Use job vars for any result you need to pass forward."* Since this is the workflow's deliverable value (declared in `outputSchema`), it must land in a job variable to be visible in the job's output/results.

6. **Surfaced a critical platform gotcha specific to this exact task type** (see "Key caveat" below), pulled directly from the skill's `$var` Resolution Rules section rather than glossed over.

## Workflow JSON produced

Written to: `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-4/old_skill/run-1/outputs/makedata-device-action-workflow.json`

```json
{
  "automation": {
    "name": "Make Device Action JSON",
    "description": "Builds a JSON string containing deviceName and action fields from job variables using makeData.",
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
        "summary": "Build Device Action Data",
        "description": "Combines the deviceName and action job variables into a single resolved object so makeData's variables field can reference it (a raw object literal with $var refs would not resolve).",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "data_to_merge": [
              { "key": "deviceName", "value": { "task": "job", "variable": "deviceName" } },
              { "key": "action", "value": { "task": "job", "variable": "action" } }
            ]
          },
          "outgoing": {
            "merged_object": null
          },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 312 }
      },
      "a1b2": {
        "name": "makeData",
        "canvasName": "makeData",
        "summary": "Build Device Action JSON String",
        "description": "Renders deviceName and action into a JSON-formatted string using <!var!> placeholder substitution against the merged object from e1a1.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "automatic",
        "displayName": "Tools",
        "variables": {
          "incoming": {
            "input": "{\"deviceName\": \"<!deviceName!>\", \"action\": \"<!action!>\"}",
            "outputType": "string",
            "variables": "$var.e1a1.merged_object"
          },
          "outgoing": {
            "output": "$var.job.deviceActionJson"
          },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 420 }
      },
      "workflow_end": {
        "name": "workflow_end",
        "groups": [],
        "nodeLocation": { "x": 600, "y": 528 }
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
        "workflow_end": { "type": "standard", "state": "success" }
      },
      "workflow_end": {}
    },
    "groups": [],
    "inputSchema": {
      "type": "object",
      "properties": {
        "deviceName": { "title": "deviceName", "type": "string" },
        "action": { "title": "action", "type": "string" }
      },
      "required": ["deviceName", "action"]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "deviceActionJson": { "title": "deviceActionJson", "type": "string" }
      }
    }
  }
}
```

Verified with `jq empty` — valid JSON.

## Final answer / recommendation (as I'd say it to the engineer)

Here's the workflow. It's a 4-node, single-thread pipeline — no branching needed since this is a pure data transform with no adapter/external calls:

```
workflow_start → e1a1 (merge) → a1b2 (makeData) → workflow_end
```

- **`e1a1` (merge)** pulls `$var.job.deviceName` and `$var.job.action` and combines them into one resolved object (`merged_object`). This step exists only because of a platform constraint: `$var` references don't resolve when they're nested inside another object's fields — `makeData`'s `variables` field needs a fully-resolved object handed to it, not a literal `{"deviceName": "$var.job.deviceName", ...}`. `merge` is the standard way to build that object first.
- **`a1b2` (makeData)** takes that merged object and renders the template string `{"deviceName": "<!deviceName!>", "action": "<!action!>"}`, substituting the real values in for the placeholders. `outputType` is set to `"string"` (not `"json"`) because you asked for a JSON **string** — `"json"` would make `makeData` try to parse the result back into an object, which isn't what you want here. The result lands in `$var.job.deviceActionJson`.
- `inputSchema` requires `deviceName` and `action` as strings; `outputSchema` declares `deviceActionJson` as the string output.

**One thing you need to know before you test this — it's a real, documented platform quirk, not a hypothetical:**

`makeData`'s `input` template string and `outputType` are "static" fields, and static fields on this platform are backed by `job_data` records that only get generated when a workflow is saved through Automation Studio's UI. If you create or update this workflow purely via the API (`POST /automation-studio/automations` or `PUT .../automations/{id}`) and then run it immediately, there's a documented failure mode where the `input`/`outputType` values resolve as `null` at runtime — meaning the JSON string never gets built correctly — until the workflow has been opened in Automation Studio and saved at least once. The same caching issue affects any other static/literal value on a freshly API-created workflow (constants in `evaluation` operands, childJob static variables, etc.), so it's not unique to this task, but it's directly relevant here since the whole point of this workflow is the `makeData` template substitution.

**My recommendation:** after you `POST` this to create the workflow, run `POST /automation-studio/workflows/validate` first to confirm it's schema-valid (empty `errors` array), then open the created workflow once in Automation Studio and hit **Save** before running your first test job. After that one-time save, the `input`/`outputType` fields will resolve correctly on every subsequent run and API-driven `PUT` update. Then test with `POST /operations-manager/jobs/start` passing `{"deviceName": "...", "action": "..."}` and confirm `data.variables.deviceActionJson` in the job result is the literal JSON-formatted string you expect (e.g. `{"deviceName": "IOS-CAT8KV-1", "action": "backup"}`).

If you'd rather avoid the Studio-save dependency entirely (e.g., for a fully API-driven CI/CD pipeline), the skill's documented workaround is to build the string via `newVariable` instead of `makeData`, but `newVariable`'s `value` field doesn't do `<!var!>` template substitution — you'd need to build the JSON string manually with a `merge`/`query` chain rather than one `makeData` call. Given you specifically asked for `makeData`, I'd start with the Studio-save step above rather than working around the tool entirely.
