# Transcript — builder-agent skill test

## Task restated

Engineer report: "In my forEach loop, the last task connects back to the forEach task but the job errors out."

This is a debugging question against a workflow already built on the Itential Platform. No live platform is connected in this session, so the deliverable is a full diagnosis plus corrected JSON artifacts (no real HTTP calls made).

## Steps taken

1. Read `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md` in full (2442 lines, read in two passes) per the instruction to treat it as the only source of truth.
2. Located the `### forEach` section (lines 1564–1596), which documents four mandatory constraints for forEach loops, most relevant here being constraint #4:
   > "The last loop body task signals loop-back with an empty `{}` transition — do NOT add an explicit loop-back target pointing to forEach."
3. Cross-checked this against the Guide 1 Step 9 pre-submit checklist (line 377):
   > "**forEach body:** `incoming` contains ONLY `data_array` (no `job_id`); loop body tasks have no external error transitions; last body task has an empty `{}` transition; `$var.job.<varName>` inside loop body instead of `$var.<taskId>.<output>`"
4. Cross-checked against the numbered General Gotchas list (line 2300):
   > "20. **`forEach` last body task transition must be empty `{}`** — do NOT connect it back to forEach."
5. Verified this rule against a **real, production-tested asset export** (per the skill's mandate to never guess task structure from memory) — `helpers/assets/itential-platform-configuration-management.json`, workflow "Golden Configuration Tree":
   - `jq` extraction of the full `transitions` map showed the real forEach task (id `5208`) transitions on `state: "loop"` into `f77d`, and the actual last body task in that chain (`da7f`) has transition value `{}` (empty) — confirming the documented pattern is exactly what's used in shipped production workflows, with no edge anywhere pointing back to `5208`.
   - Also pulled the full task JSON for `5208` (forEach), `f77d` (evaluation), and `da7f` (ViewData/manual, the terminal body task) to ground the example in real field shapes (`incoming.data_array`, `outgoing.current_item`, etc.)
6. Also reviewed Guide 2 ("Debug a failed job") for the job-error-lookup procedure (`GET /operations-manager/jobs/{jobId}`, check `data.status`, read `data.error[].task` and `data.error[].message.IAPerror.displayString`) to give the engineer the concrete next step for confirming the diagnosis on their real job, since no live platform is available in this session.
7. Wrote the corrected JSON artifact to `outputs/forEach-loopback-fix.json`, containing:
   - The diagnosis and the exact rule violated, with the skill section cited
   - A minimal "BROKEN" transitions snippet showing the mistake (explicit edge from last body task back to the forEach task ID)
   - A minimal "FIXED" transitions snippet (empty `{}` on the last body task)
   - A complete, importable-shape minimal forEach workflow illustrating all four forEach constraints together
   - The verified real production reference (Golden Configuration Tree, task `5208`/`f77d`/`da7f`) as an appendix

## JSON produced (full, inline)

```json
{
  "diagnosis": "The last task in a forEach loop body must NOT have an explicit transition back to the forEach task ID. The forEach task manages iteration internally; the last body task signals 'this iteration is done' by having an EMPTY transition object {}. Wiring an explicit transition from the last body task back to the forEach task ID creates a real graph edge into forEach from outside its recognized entry point (workflow_start -> forEach, or forEach's own internal loop re-entry). The engine does not support forEach being re-entered via an external transition while it is already managing an active loop state for that job, so the job errors out instead of continuing to the next iteration.",
  "source": "builder-agent SKILL.md - '### forEach' section and General Gotcha #20 / checklist item 'forEach body' (Guide 1 Step 9 pre-submit checklist)",
  "rule_violated": "forEach constraint #4: 'The last loop body task signals loop-back with an empty {} transition — do NOT add an explicit loop-back target pointing to forEach.'",

  "example_BROKEN": {
    "description": "This is the pattern the engineer currently has — DO NOT USE. The last body task (c3d4) has an explicit transition wired back to the forEach task ID (a1a1). This is what causes the job to error out.",
    "transitions": {
      "a1a1": {
        "b2b2": { "type": "standard", "state": "loop" },
        "workflow_end": { "type": "standard", "state": "success" },
        "errHandler": { "type": "standard", "state": "error" }
      },
      "b2b2": {
        "c3d4": { "type": "standard", "state": "success" }
      },
      "c3d4": {
        "a1a1": { "type": "standard", "state": "success" }
      }
    }
  },

  "example_FIXED": {
    "description": "Correct pattern. forEach (a1a1) loops into the body via state:loop. The body runs b2b2 -> c3d4. The LAST body task (c3d4) has an EMPTY transition object {} — this is the documented signal that tells the engine the iteration is complete and control returns to forEach internally. No explicit edge to the forEach task ID exists anywhere in the transitions map.",
    "transitions": {
      "a1a1": {
        "b2b2": { "type": "standard", "state": "loop" },
        "workflow_end": { "type": "standard", "state": "success" },
        "errHandler": { "type": "standard", "state": "error" }
      },
      "b2b2": {
        "c3d4": { "type": "standard", "state": "success" }
      },
      "c3d4": {}
    }
  },

  "full_minimal_forEach_workflow_FIXED": {
    "note": "A complete, importable-shape minimal forEach loop workflow illustrating all four documented forEach constraints together. Task IDs are hex-only per platform requirement.",
    "tasks": {
      "workflow_start": { "name": "workflow_start" },
      "a1a1": {
        "name": "forEach",
        "canvasName": "forEach",
        "summary": "Loop Over Items",
        "description": "Iterate over the incoming data array",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "data_array": "$var.job.items"
          },
          "outgoing": {
            "current_item": "$var.job.currentItem"
          },
          "error": ""
        },
        "actor": "Pronghorn",
        "groups": [],
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 312 }
      },
      "b2b2": {
        "name": "evaluation",
        "canvasName": "evaluation",
        "summary": "Check Current Item",
        "description": "Evaluate the current loop item using the job-scoped variable, not $var.a1a1.current_item",
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
                    "operand_1": { "task": "job", "variable": "currentItem" },
                    "operand_2": { "task": "static", "variable": "" },
                    "operator": "!=",
                    "query": "",
                    "rightQuery": ""
                  }
                ]
              }
            ]
          },
          "outgoing": { "return_value": "" }
        },
        "actor": "Pronghorn",
        "groups": [],
        "nodeLocation": { "x": 600, "y": 420 }
      },
      "c3d4": {
        "name": "newVariable",
        "canvasName": "newVariable",
        "summary": "Record Processed Item (last task in loop body)",
        "description": "Last task in the loop body. Its transition MUST be empty {} — this signals iteration complete, do not wire this back to a1a1.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": { "name": "lastProcessed", "value": "processed" },
          "outgoing": { "value": "$var.job.lastProcessed" }
        },
        "actor": "Pronghorn",
        "groups": [],
        "nodeLocation": { "x": 600, "y": 528 }
      },
      "workflow_end": { "name": "workflow_end" }
    },
    "transitions": {
      "workflow_start": {
        "a1a1": { "type": "standard", "state": "success" }
      },
      "a1a1": {
        "b2b2": { "type": "standard", "state": "loop" },
        "workflow_end": { "type": "standard", "state": "success" }
      },
      "b2b2": {
        "c3d4": { "type": "standard", "state": "success" },
        "c3d4_2": { "type": "standard", "state": "failure" }
      },
      "c3d4": {},
      "workflow_end": {}
    },
    "constraints_illustrated": [
      "1. a1a1.variables.incoming contains ONLY data_array (no job_id)",
      "2. b2b2 references $var.job.currentItem (job-scoped), NOT $var.a1a1.current_item (taskId-scoped) — the latter silently resolves to null inside a forEach body",
      "3. Loop body tasks (b2b2, c3d4) have no transitions to any task outside the loop except back into the loop chain itself; errors are handled inside the loop body (b2b2's failure branch would route to another in-loop task, not an external error handler)",
      "4. c3d4 (the last body task) has an empty {} transition — no explicit edge back to a1a1"
    ]
  },

  "real_production_reference": {
    "note": "Verified against a real, production-tested export: 'Golden Configuration Tree' workflow in helpers/assets/itential-platform-configuration-management.json",
    "forEach_task_id": "5208",
    "chain": "5208 (forEach) --state:loop--> f77d (evaluation) --state:failure--> da7f (ViewData) --> {} (empty, terminal)",
    "forEach_task_incoming": { "data_array": "$var.6882.return_data" },
    "last_body_task_transition": { "da7f": {} }
  }
}
```

## Final answer to the engineer

That's exactly the bug. In a `forEach` loop on Itential Platform, the last task in the loop body must **not** have an explicit transition pointing back to the `forEach` task ID. It must have an **empty transition object `{}`** — that's the signal the workflow engine uses internally to know the current iteration is done and to advance to the next item. The engine already manages the loop internally via `state: "loop"` from the forEach task; it doesn't expect (and can't cleanly handle) a real graph edge coming back into it from a body task. When you wire that explicit edge, the forEach task effectively gets a second, unrecognized entry point while it's mid-loop for that job, and the job errors out instead of continuing.

**Fix:** find the last task in your loop body and change its transition entry from something like:
```json
"c3d4": {
  "a1a1": { "type": "standard", "state": "success" }
}
```
to:
```json
"c3d4": {}
```
Don't route it anywhere — not to the forEach task, and not to `workflow_end` either (the exit path after the whole loop finishes is wired on the `forEach` task itself via its own `state: "success"` transition, separate from `state: "loop"`).

While you're in there, double check the other three related forEach requirements, since they cause similarly hard-to-spot failures:
1. The forEach task's `incoming` should contain **only** `data_array` — no `job_id`. Adding `job_id` causes runtime errors.
2. Inside the loop body, don't reference the current item as `$var.<forEachTaskId>.current_item` — that silently resolves to `null` inside a forEach body on this platform. Bind forEach's `current_item` outgoing to a job variable and use `$var.job.<varName>` instead, everywhere inside the loop.
3. Loop body tasks should not have transitions to error handlers *outside* the loop. Handle errors within the loop body itself; let the `forEach` task's own `state: "error"` transition be the only exit route for loop-level failures.

I verified this against a real, shipped production workflow ("Golden Configuration Tree" in the platform's Configuration Management asset project) — its forEach task loops into an `evaluation` task, which on failure routes to a `ViewData` task, and that `ViewData` task (the last task in the body) has a transition of exactly `{}`. No edge anywhere points back to the forEach task ID. That's the pattern to copy.

If you want to confirm this is the actual root cause on your job before editing, pull the job and look at the error detail:
```
GET /operations-manager/jobs/{jobId}
```
Check `data.status == "error"` and read `data.error[].task` (should point at your forEach task or the mis-wired last body task) and `data.error[].message.IAPerror.displayString` for the platform's error text. Then fix the transition locally and `PUT` the workflow update (don't recreate — that preserves the workflow ID) and re-run.

## Files consulted / produced

- Consulted: `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md` (forEach section, checklist, general gotchas, Guide 2 debug procedure)
- Consulted (real production data, not memory): `/Users/ankitrbhansali/builderskills/builder-skills/helpers/assets/itential-platform-configuration-management.json` — "Golden Configuration Tree" workflow, tasks `5208`/`f77d`/`da7f`
- Produced: `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-16/new_skill/run-1/outputs/forEach-loopback-fix.json`
- Produced: this transcript at `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-16/new_skill/run-1/transcript.md`
