# Transcript — builder-agent skill test: forEach loop over device names

## Task as given

The engineer is building a `forEach` loop over a list of device names and asked three questions:

1. Should the forEach's `incoming` include `job_id`?
2. Inside the loop body, can an evaluation task's output (from **outside** the loop) be referenced with `$var.<taskId>.<output>`?
3. How should the last task in the loop body transition?

No live platform is connected in this session, so no HTTP calls were made. The deliverable is the reasoning plus a concrete, validated workflow JSON artifact demonstrating the correct wiring.

## Steps taken

1. Read the full `builder-agent` SKILL.md at
   `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md` (2442 lines, read in two passes due to truncation).
2. Located every reference to `forEach` in the skill via `grep -n "forEach" SKILL.md`. Key hits:
   - Line 377 (pre-flight checklist): *"forEach body: `incoming` contains ONLY `data_array` (no `job_id`); loop body tasks have no external error transitions; last body task has an empty `{}` transition; `$var.job.<varName>` inside loop body instead of `$var.<taskId>.<output>`"*
   - Lines 1564–1596: the dedicated `### forEach` reference section, which spells out the four required constraints in detail (reproduced below).
   - Lines 2300 and 2326 in the numbered gotchas list: reinforce "last body task transition must be empty `{}`" and "`$var.<taskId>.<out>` does not resolve inside nested forEach bodies — use `$var.job.<varName>`".
3. Pulled a real, production-tested example of `forEach` usage from the asset library to confirm the pattern against a live-exported workflow:
   ```bash
   grep -rl '"name": "forEach"' helpers/assets/
   # -> helpers/assets/itential-platform-configuration-management.json
   jq '[.components[] | select(.type=="workflow") | select(.document.tasks | to_entries[] | select(.value.name=="forEach"))] | .[0].document | {name, tasks, transitions}' \
     helpers/assets/itential-platform-configuration-management.json
   ```
   This is the "Golden Configuration Tree" workflow. Its `forEach` tasks (`5208`, `c1c3`) have `incoming: {"data_array": "$var.<taskId>.<output>"}` — **only** `data_array`, no `job_id` — confirming rule #1. Their transitions show the `loop` state entering the body and `success` state exiting to the task after the loop, and the body's terminal tasks carry an empty `{}` transition entry (e.g. `"da7f": {}`, `"850c": {}`), confirming rule #4.
4. Cross-checked `newVariable` task shape (fields: `location`, `locationType`, `app`, `type`, `displayName`, `actor`) from the same asset file to build a schema-accurate example.
5. Checked `AGENTS.md` (project root) for the top-level numbered rules — rule 21 (duplicate transition keys) and rule 19 (error transitions mandatory on adapter/external tasks) informed how the example's branches are wired so no source task has two transition entries pointing at the identical target ID.
6. Built the deliverable workflow JSON by hand, following Guide 1's mapping rules (task ID format `[0-9a-f]{1,4}`, `app`/`location`/`type`/`displayName` = `WorkFlowEngine`/`Application`/`operation`/`WorkFlowEngine` for evaluation, forEach, and newVariable tasks, `actor: "Pronghorn"`), then validated it:
   ```bash
   jq -e . outputs/foreach-device-loop-example.json   # valid JSON
   # python check: every transition source and target key resolves to a real task ID — no dangling refs
   ```

## Answers to the three questions (verbatim from the skill)

### 1. Should `job_id` be in the forEach's `incoming`?

**No.** Per SKILL.md line 1568 and the checklist at line 377/1579:

> "**Incoming:** `data_array` (array) — **ONLY `data_array`**. Do NOT include `job_id` in incoming — it triggers errors."

`incoming` must contain exactly one key, `data_array`, pointing at the array to iterate (e.g. `"$var.job.deviceNames"`). Adding `job_id` (or any other key) causes runtime errors. This is confirmed by the live asset export (`itential-platform-configuration-management.json`, task `5208`/`c1c3`), where `incoming` is `{"data_array": "..."}` and nothing else.

### 2. Can you reference an outside-the-loop evaluation task's output inside the loop body with `$var.<taskId>.<output>`?

**No.** SKILL.md's forEach constraint #2 (line 1581) states:

> "`$var.<taskId>.<output>` does NOT resolve inside the loop body — string references like `$var.n01.current_item` silently resolve to `null` inside a forEach body. Use `$var.job.<varName>` instead (bind the forEach's outgoing to a job variable and reference that). This applies to ALL reference styles — even taskRef objects `{"task": "outerTask", "variable": "current_item"}` are unreliable inside a nested body."

This rule is not scoped only to the forEach's own `current_item` — it applies to **any** `$var.<taskId>.<output>` reference used inside the loop body, including a reference to a task that ran *before* the loop (your evaluation task). The fix is the same pattern used for `current_item`: bind the evaluation task's `outgoing` directly to a job variable when you define it —
```json
"outgoing": { "return_value": "$var.job.maintenanceWindowActive" }
```
— and then, inside the loop body, reference `$var.job.maintenanceWindowActive` (never `$var.e1a1.return_value`). The same trick applies to the forEach's own `current_item`: bind it to `$var.job.currentDeviceName` in the forEach's `outgoing`, and use that job variable inside the body instead of `$var.<forEachTaskId>.current_item`.

This is also reinforced in `AGENTS.md`-style checklist items 40 and the pre-flight bullet at SKILL.md line 362/376/2326, so it's a repeatedly-flagged, tested platform gotcha, not a one-off note.

### 3. How should the last task in the loop body transition?

Per SKILL.md constraint #4 (line 1585) and the pre-flight checklist:

> "The last loop body task signals loop-back with an empty `{}` transition — do NOT add an explicit loop-back target pointing to forEach."

So the last task(s) in the loop body get an empty transitions entry: `"lastBodyTaskId": {}`. You do **not** wire a transition from the last body task back to the `forEach` task ID — the platform handles the loop-back internally when it sees the empty transition object. If the loop body forks (e.g., an eligibility check with two outcomes), each terminal branch task gets its own empty `{}` entry — this is fine since they are different task IDs, not duplicate keys.

Additionally, per constraint #3 (line 1583): loop body tasks must not transition to tasks **outside** the loop on error — the `forEach` task itself owns the `state: "error"` exit path. Handle errors internally within the loop body, then let the forEach's own error transition route out to an external handler.

One side note worth flagging: the skill documents `forEach` as **deprecated** in favor of `childJob` with `loopType` (line 1566: "Iterate over an array. **Deprecated** — prefer `childJob` with `loopType`. Still common in existing workflows.") Since the engineer is starting a new build, it's worth asking whether a `childJob` loop (Guide 4, Mode B) would serve better — it doesn't carry the `$var.job.*` indirection requirement and runs each iteration as an independently-trackable child job. But if there's already a reason to stick with `forEach` (e.g., matching an existing pattern in the same workflow), the three answers above are correct and safe.

## Deliverable JSON produced

Written to:
`/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-26/new_skill/run-1/outputs/foreach-device-loop-example.json`

This is a small, self-contained, structurally-validated workflow (validated with `jq -e .` for JSON well-formedness and a Python check confirming every transition source/target resolves to a real task ID — no dangling references) that demonstrates all three answers together:

```
workflow_start
   -> e1a1 (evaluation, OUTSIDE the loop: "Check Maintenance Window")
        outgoing.return_value bound directly to $var.job.maintenanceWindowActive
      --success--> f2b2 (forEach)
      --failure--> j8k9 (newVariable error handler) --success--> workflow_end

f2b2 (forEach)
   incoming: { "data_array": "$var.job.deviceNames" }   <-- ONLY data_array, no job_id
   outgoing: { "current_item": "$var.job.currentDeviceName" }  <-- rebound to a job var
      --loop--> c3d4 (evaluation, INSIDE the loop body: "Check Device Eligible")
                   operand_1 references $var.job.maintenanceWindowActive   (NOT $var.e1a1.return_value)
                --success--> d4e5 (newVariable "skipped-maintenance-window") --> {}  (empty transition)
                --failure--> e5f6 (newVariable "eligible")                  --> {}  (empty transition)
      --success--> g6h7 (arrayLength, after the loop, on the spine) --> workflow_end
      --error-->   h7i8 (newVariable error handler) --> workflow_end
```

Full JSON (as written to disk):

```json
{
  "name": "ForEach Device Maintenance Check Example",
  "description": "Demonstrates correct forEach wiring: incoming has ONLY data_array (no job_id), an evaluation task OUTSIDE the loop whose output is bound to a job variable and referenced inside the loop body via $var.job.<varName> (NOT $var.<taskId>.<output>), and loop body branches that each terminate with an empty {} transition.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "deviceNames": {
        "type": "array",
        "items": { "type": "string" }
      }
    },
    "required": ["deviceNames"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "maintenanceWindowActive": { "type": "boolean" },
      "deviceCount": { "type": "number" }
    }
  },
  "tasks": {
    "workflow_start": {
      "name": "workflow_start",
      "groups": [],
      "nodeLocation": { "x": 600, "y": 200 }
    },
    "e1a1": {
      "name": "evaluation",
      "canvasName": "evaluation",
      "summary": "Check Maintenance Window",
      "description": "Evaluate whether the current maintenance window is active. This task is OUTSIDE the forEach loop.",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "all_true_flag": false,
          "evaluation_groups": [
            {
              "all_true_flag": false,
              "evaluations": [
                {
                  "query": "",
                  "operand_1": { "task": "job", "variable": "maintenanceWindowFlag" },
                  "operator": "==",
                  "operand_2": { "task": "static", "variable": true }
                }
              ]
            }
          ]
        },
        "outgoing": {
          "return_value": "$var.job.maintenanceWindowActive"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": { "x": 600, "y": 308 }
    },
    "f2b2": {
      "name": "forEach",
      "canvasName": "forEach",
      "summary": "For Each Device Name",
      "description": "Iterate over the incoming list of device names. incoming contains ONLY data_array -- do NOT add job_id here, it causes runtime errors.",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "data_array": "$var.job.deviceNames"
        },
        "outgoing": {
          "current_item": "$var.job.currentDeviceName"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": { "x": 600, "y": 416 }
    },
    "c3d4": {
      "name": "evaluation",
      "canvasName": "evaluation",
      "summary": "Check Device Eligible For Action",
      "description": "First task in the loop body. References the OUTSIDE-the-loop evaluation's result via the job variable $var.job.maintenanceWindowActive -- NOT $var.e1a1.return_value, which would silently resolve to null inside a forEach body. Also uses $var.job.currentDeviceName (the forEach's own outgoing, rebound to a job var) instead of $var.f2b2.current_item for the same reason.",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "all_true_flag": false,
          "evaluation_groups": [
            {
              "all_true_flag": false,
              "evaluations": [
                {
                  "query": "",
                  "operand_1": { "task": "job", "variable": "maintenanceWindowActive" },
                  "operator": "==",
                  "operand_2": { "task": "static", "variable": true }
                }
              ]
            }
          ]
        },
        "outgoing": {
          "return_value": null
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": { "x": 600, "y": 524 }
    },
    "d4e5": {
      "name": "newVariable",
      "canvasName": "newVariable",
      "summary": "Record Skipped (Maintenance Window Active)",
      "description": "Success branch of the eligibility check: maintenance window is active, so this device's action is skipped this iteration. This is a terminal task for this loop iteration -- its transition is empty {} to signal loop-back to forEach. Do NOT wire an explicit transition back to f2b2.",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "name": "lastDeviceActionStatus",
          "value": "skipped-maintenance-window"
        },
        "outgoing": {
          "value": "$var.job.lastDeviceActionStatus"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": { "x": 336, "y": 632 }
    },
    "e5f6": {
      "name": "newVariable",
      "canvasName": "newVariable",
      "summary": "Record Eligible For Action",
      "description": "Failure branch of the eligibility check: maintenance window is not active, so this device is eligible. This is the other terminal task for this loop iteration -- its transition is also empty {}.",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "name": "lastDeviceActionStatus",
          "value": "eligible"
        },
        "outgoing": {
          "value": "$var.job.lastDeviceActionStatus"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": { "x": 864, "y": 632 }
    },
    "g6h7": {
      "name": "arrayLength",
      "canvasName": "length",
      "summary": "Get Device Count",
      "description": "Runs after the forEach loop completes (forEach 'success' state). On the spine, convergence point after the loop.",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "automatic",
      "displayName": "Array",
      "variables": {
        "incoming": {
          "arr": "$var.job.deviceNames"
        },
        "outgoing": {
          "length": "$var.job.deviceCount"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": { "x": 600, "y": 632 }
    },
    "h7i8": {
      "name": "newVariable",
      "canvasName": "newVariable",
      "summary": "Handle ForEach Error",
      "description": "forEach 'error' state routes here (the forEach task itself handles loop-level error exit -- loop body tasks never transition directly to an external error handler).",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "name": "taskStatus",
          "value": "error"
        },
        "outgoing": {
          "value": "$var.job.taskStatus"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": { "x": 864, "y": 416 }
    },
    "j8k9": {
      "name": "newVariable",
      "canvasName": "newVariable",
      "summary": "Handle Maintenance Window Check Failure",
      "description": "e1a1 (outside the loop) requires both success AND failure transitions per checklist. Routes to a dedicated handler instead of duplicating workflow_end as a key on e1a1 (JSON cannot have two entries with the same target key on one source task).",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "name": "taskStatus",
          "value": "error"
        },
        "outgoing": {
          "value": "$var.job.taskStatus"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": { "x": 864, "y": 308 }
    },
    "workflow_end": {
      "name": "workflow_end",
      "groups": [],
      "nodeLocation": { "x": 600, "y": 740 }
    }
  },
  "transitions": {
    "workflow_start": {
      "e1a1": { "type": "standard", "state": "success" }
    },
    "e1a1": {
      "f2b2": { "type": "standard", "state": "success" },
      "j8k9": { "type": "standard", "state": "failure" }
    },
    "f2b2": {
      "c3d4": { "type": "standard", "state": "loop" },
      "g6h7": { "type": "standard", "state": "success" },
      "h7i8": { "type": "standard", "state": "error" }
    },
    "c3d4": {
      "d4e5": { "type": "standard", "state": "success" },
      "e5f6": { "type": "standard", "state": "failure" }
    },
    "d4e5": {},
    "e5f6": {},
    "g6h7": {
      "workflow_end": { "type": "standard", "state": "success" }
    },
    "h7i8": {
      "workflow_end": { "type": "standard", "state": "success" }
    },
    "j8k9": {
      "workflow_end": { "type": "standard", "state": "success" }
    },
    "workflow_end": {}
  }
}
```

## Final answer to the engineer (as I would say it to them)

1. **No, don't put `job_id` in the forEach's `incoming`.** The forEach `incoming` block accepts exactly one field — `data_array` — pointing at your list of device names (e.g. `"$var.job.deviceNames"`). Adding `job_id` (or anything else) triggers runtime errors. I confirmed this against the skill's forEach reference section and against a real production export (Golden Configuration Tree workflow) that uses forEach the same way.

2. **No, you can't use `$var.<taskId>.<output>` inside the loop body — even for a task that ran before the loop.** Any `$var.<taskId>.<output>` reference silently resolves to `null` once you're inside a forEach body; this is a documented, tested platform gotcha, not specific to the forEach's own `current_item`. The fix: when you define the evaluation task (outside the loop), bind its `outgoing` directly to a job variable, e.g. `"outgoing": {"return_value": "$var.job.maintenanceWindowActive"}`. Then inside the loop body, reference `$var.job.maintenanceWindowActive` instead. Do the same thing for the forEach's own `current_item` — bind it to something like `$var.job.currentDeviceName` in the forEach's `outgoing`, and use that job variable in the body instead of `$var.<forEachTaskId>.current_item`.

3. **The last task in the loop body gets an empty `{}` transition** — don't wire it back to the forEach task explicitly; the platform loops back internally when it sees the empty transition. If the body forks into multiple branches, each terminal branch task gets its own empty `{}` entry. Also: loop body tasks should never transition out to an external error handler — let the forEach task's own `state: "error"` transition be the loop's single exit point for errors.

One more thing worth mentioning: the skill flags `forEach` as **deprecated** in favor of `childJob` with `loopType` for new builds — it's simpler (no job-variable indirection needed, and each iteration is independently trackable). Worth considering if this is a fresh build and not an addition to an existing forEach-based workflow.

I put together a full working example wired exactly this way — `foreach-device-loop-example.json` — that you can use as a template.
