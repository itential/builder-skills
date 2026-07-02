# Transcript — Builder Agent skill test run

## Task restated

Create a workflow with a `childJob` task that runs a child workflow called **"Device Backup"** once for **each device in an array**, with all of the per-device runs executing **in parallel**.

## Skill consulted

`/tmp/eval-old-skill/builder-agent/SKILL.md` (read in full, both halves — 2314 lines). This is the `builder-agent` skill, which implements an approved `solution-design.md` end-to-end. It documents:

- A **Workspace Contract** (Step 0 of the Build Lifecycle) that normally requires `tasks.json`, `apps.json`, `adapters.json`, `.auth.json`, etc. before any build starts.
- **Guide 4: Build a childJob (parent calls child workflow)**, which has exactly two modes:
  - Mode A — single child, `variables: {"var": {"task","value"}}`
  - **Mode B — loop, one child per item in `data_array`**, with `loopType: "parallel" | "sequential"`. This is the mode the task calls for.
- A hard rule at the top of Guide 1 ("STOP. Before writing a single line of task JSON — run these commands") requiring that task JSON be extracted from real, production-tested asset projects under `helpers/assets/` via `jq`, not guessed from memory.
- A `childJob` checklist, a `$var` resolution-rules section, a canvas/nodeLocation layout convention, and a large "Gotchas" pre-flight list (50+ items) to scan before finalizing.

## Key steps taken

**1. Noted the workspace-contract gap up front.** The skill's Build Lifecycle assumes an approved `solution-design.md` and a populated `use-cases/{name}/` workspace (`tasks.json`, `apps.json`, `adapters.json`, `.auth.json`, etc.) already exists, left behind by `/solution-arch-agent`. None of that exists for this ad hoc request — there's no live platform connection and no use-case folder. Per the skill's own instruction ("If any required file is missing, stop and surface as an upstream failure"), a strict reading would have me halt. Since the task explicitly asks me to produce the workflow JSON artifact directly (not to make live API calls), I proceeded with the parts of the skill that don't require a live tasks.json lookup — `childJob`, `query`, `workflow_start`/`workflow_end` are all built-in `WorkFlowEngine` application tasks (not adapter tasks), so they don't require adapter-specific `apps.json`/`adapters.json` resolution. I flagged this gap rather than silently ignoring it (see final answer below).

**2. Followed the Guide 1 "STOP" block and Guide 4 instruction to pull real examples instead of writing from memory.** Ran, against the real repo at `/Users/ankitrbhansali/builderskills/builder-skills`:

```bash
# Which asset files actually contain a childJob task, and with what loopType?
for f in helpers/assets/*.json; do
  jq --arg f "$f" '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "childJob") |
    {file:$f, taskId:.key, loopType:.value.variables.incoming.loopType, workflow:.value.variables.incoming.workflow}]' "$f"
done
```

Result: no asset project contains a `loopType: "parallel"` example, but `helpers/assets/vendor-netbox.json` (workflow **"Delete Prefix"**) has a real, production `loopType: "sequential"` childJob at task id `4b5c`:

```json
{
  "name": "childJob",
  "canvasName": "childJob",
  "summary": "Delete IP Address",
  "description": "Runs a child job inside a workflow.",
  "location": "Application",
  "locationType": null,
  "app": "WorkFlowEngine",
  "type": "operation",
  "displayName": "WorkFlowEngine",
  "variables": {
    "incoming": {
      "task": "",
      "workflow": "Delete IP Address - NetBox",
      "variables": {},
      "data_array": "$var.1bd8.ipsInPrefix",
      "transformation": "",
      "loopType": "sequential"
    },
    "outgoing": { "job_details": null }
  },
  "groups": [],
  "actor": "job",
  "nodeLocation": { "x": -1620, "y": 1932 }
}
```

I also pulled the query task immediately downstream of that childJob in the same workflow (task id `82ca`), which extracts the loop results:

```json
{
  "name": "query",
  "canvasName": "query",
  "summary": "Query Delete IP Addresses Result",
  "location": "Application",
  "locationType": null,
  "app": "WorkFlowEngine",
  "type": "operation",
  "displayName": "WorkFlowEngine",
  "variables": {
    "incoming": { "pass_on_null": false, "query": "loop", "obj": "$var.4b5c.job_details" },
    "outgoing": { "return_data": "$var.job.deleteIPAddressResult" }
  },
  "actor": "Pronghorn",
  "groups": [],
  "nodeLocation": { "x": -1620, "y": 2076 }
}
```

I checked the transitions for both real tasks:
- `4b5c` (childJob) → only a `success` transition to the next task. **No error transition** on the childJob task itself in this production example — confirms the skill's own note that a well-built child workflow "always completes" (handles errors internally via the try-catch pattern) so the parent only needs a `success` path out of childJob.
- `82ca` (query "loop") → only a `success` transition, no `failure` transition, even though `pass_on_null: false`. I followed this same production convention (a `data_array` loop always populates `job_details.loop`, even if the array were empty, so `failure` is not a realistic branch here).

This matches Guide 4 Mode B's documented shape exactly:
```json
{
  "incoming": {
    "task": "",
    "workflow": "My Child Workflow",
    "variables": {},
    "data_array": "$var.job.devices",
    "transformation": "",
    "loopType": "parallel"
  },
  "outgoing": { "job_details": null }
}
```
and the loop-output extraction pattern documented in the `childJob` reference section: `query "loop"` on `$var.<childJobTaskId>.job_details` → job variable; and `"[**].taskStatus"` to pull one field across every iteration.

**3. Built the parent/orchestrator workflow** using the confirmed pattern:

```
workflow_start → a1a1 (childJob, loopType=parallel, data_array=$var.job.devices, workflow="Device Backup")
              → b2b2 (query "loop" → $var.job.backupResults)
              → c3c3 (query "[**].taskStatus" → $var.job.backupStatuses)
              → workflow_end
```

I set `loopType: "parallel"` (not `sequential`, since the task explicitly asked for parallel execution — this is the one field I deliberately changed from the closest real example).

**4. Ran the skill's childJob checklist against the built task:**
- [x] `actor` is `"job"` on the childJob task, `"Pronghorn"` on both query tasks
- [x] `task` is `""`
- [x] `job_details` outgoing is `null` (not overridden)
- [x] All incoming fields present, including unused ones (`transformation: ""`)
- [x] `variables: {}` because loop mode is used (not the single-mode `{"task","value"}` form)
- [x] Task IDs are hex-only: `a1a1`, `b2b2`, `c3c3`
- [x] `workflow_end` transition is empty `{}`
- [x] Canvas layout follows the vertical spine convention (x=600 constant, y-delta 108px, no fork needed since there's no branching)
- [ ] "Child workflow's `inputSchema.required` matches what you're passing" — **cannot verify**, "Device Backup" doesn't exist in any asset project or workspace file available to me. See caveat in my final answer below.

**5. Validated the JSON is well-formed** with `jq empty` against the written file (passed). I could not run the skill's recommended `POST /automation-studio/workflows/validate` pre-flight check because there is no live Itential Platform connected in this session — flagged as a follow-up action for the engineer.

## Artifacts produced

- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-2/old_skill/run-1/outputs/device-backup-parallel-orchestrator.json` — the full workflow document (wrapped in `{"automation": {...}}` per the skill's `POST /automation-studio/automations` body shape), containing:

```json
{
  "automation": {
    "name": "Backup All Devices (Parallel)",
    "description": "Runs the 'Device Backup' child workflow once per device in the input array, in parallel, and collects the per-device results and statuses.",
    "type": "automation",
    "canvasVersion": 3,
    "encodingVersion": 1,
    "font_size": 12,
    "tasks": {
      "workflow_start": { "name": "workflow_start", "groups": [], "nodeLocation": { "x": 600, "y": 200 } },
      "a1a1": {
        "name": "childJob",
        "canvasName": "childJob",
        "summary": "Run Device Backup Per Device (Parallel)",
        "description": "Fans out one 'Device Backup' child job per element in the devices array, all running simultaneously.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "task": "",
            "workflow": "Device Backup",
            "variables": {},
            "data_array": "$var.job.devices",
            "transformation": "",
            "loopType": "parallel"
          },
          "outgoing": { "job_details": null }
        },
        "groups": [],
        "actor": "job",
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 312 }
      },
      "b2b2": {
        "name": "query",
        "canvasName": "query",
        "summary": "Extract Backup Results",
        "description": "Extracts the full array of per-device loop results from the childJob output.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": { "pass_on_null": false, "query": "loop", "obj": "$var.a1a1.job_details" },
          "outgoing": { "return_data": "$var.job.backupResults" },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 420 }
      },
      "c3c3": {
        "name": "query",
        "canvasName": "query",
        "summary": "Extract Per-Device Statuses",
        "description": "Extracts just the taskStatus field from every loop iteration for a quick pass/fail summary.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": { "pass_on_null": false, "query": "[**].taskStatus", "obj": "$var.a1a1.job_details" },
          "outgoing": { "return_data": "$var.job.backupStatuses" },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 528 }
      },
      "workflow_end": { "name": "workflow_end", "groups": [], "nodeLocation": { "x": 600, "y": 636 } }
    },
    "transitions": {
      "workflow_start": { "a1a1": { "type": "standard", "state": "success" } },
      "a1a1": { "b2b2": { "type": "standard", "state": "success" } },
      "b2b2": { "c3c3": { "type": "standard", "state": "success" } },
      "c3c3": { "workflow_end": { "type": "standard", "state": "success" } },
      "workflow_end": {}
    },
    "groups": [],
    "inputSchema": {
      "type": "object",
      "properties": {
        "devices": {
          "title": "devices",
          "type": "array",
          "description": "One entry per device to back up. Each object becomes that iteration's child-job input variables.",
          "items": {
            "type": "object",
            "properties": { "deviceName": { "title": "deviceName", "type": "string" } },
            "required": ["deviceName"]
          }
        }
      },
      "required": ["devices"]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "backupResults": {
          "title": "backupResults",
          "type": "array",
          "description": "Flat spread of every child job's variables, one element per device (includes childJobLoopIndex, deviceName, taskStatus, and any other job variables the child workflow set)."
        },
        "backupStatuses": {
          "title": "backupStatuses",
          "type": "array",
          "description": "taskStatus value only, one entry per device, in the same order as backupResults."
        }
      }
    }
  }
}
```

- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-2/old_skill/run-1/outputs/test-job-start-payload.json` — a sample `POST /operations-manager/jobs/start` body for testing the workflow once it exists on a platform, per the skill's "Testing & Debugging" section:

```json
{
  "workflow": "Backup All Devices (Parallel)",
  "options": {
    "description": "Test run - parallel backup of 3 devices",
    "type": "automation",
    "variables": {
      "devices": [
        { "deviceName": "IOS-CAT8KV-1" },
        { "deviceName": "IOS-CAT8KV-2" },
        { "deviceName": "EOS-AWS-1" }
      ]
    }
  }
}
```

## Final answer / recommendation to the engineer

Here's the orchestrator workflow: **"Backup All Devices (Parallel)"**. It's a single `childJob` task in loop mode — `loopType: "parallel"`, `data_array: $var.job.devices` — that calls **"Device Backup"** once per element of the `devices` array, all running simultaneously, followed by two `query` tasks that pull the combined results (`query: "loop"`) and a flattened status list (`query: "[**].taskStatus"`) out of `job_details` into job-level output variables. I built this straight off the skill's Guide 4 Mode B pattern and cross-checked every field against a real, production-tested `loopType: "sequential"` childJob + `query "loop"` pair from `helpers/assets/vendor-netbox.json`'s "Delete Prefix" workflow (the only production example of this loop pattern in the asset library) — the only field I intentionally changed from that example was `loopType`, from `"sequential"` to `"parallel"`, since that's what you asked for.

Three things you need to close out before this is truly build-complete, per the skill itself:

1. **This assumes a contract with "Device Backup" that I couldn't verify.** No asset project or workspace file in this session actually contains a "Device Backup" workflow, so I don't have its real `inputSchema`. I designed `devices` as an array of `{"deviceName": "..."}` objects because each array element becomes that iteration's full set of child-job input variables — so whatever field name(s) "Device Backup" actually requires as input, the `devices` array elements need to carry exactly that key. If the real child workflow expects something like `{"device": "..."}` or `{"hostname": "...", "credId": "..."}` instead, update the `inputSchema.items.properties` and the `data_array` payload to match. Guide 4 also expects the child to end with a `taskStatus` job variable ("success"/"error") set via the standard try-catch pattern (`task --success--> newVariable(taskStatus=success) --> workflow_end`, `task --error--> newVariable(taskStatus=error) --> workflow_end`) — that's what makes the `c3c3` "[**].taskStatus" query meaningful. If "Device Backup" doesn't already follow that pattern, add it there first — "build children first" is the skill's explicit build order, and I'd normally do that before wiring the parent.

2. **No live platform is connected in this session**, so I could not run the skill's mandatory pre-flight check, `POST /automation-studio/workflows/validate`, or actually `POST /automation-studio/automations` to create it. Do that before importing. If "Device Backup" will live in the same project as this orchestrator, use `POST /automation-studio/projects/import` (atomic, single call) rather than create+move — moving assets after the fact renames them with an `@projectId:` prefix but does **not** update the childJob's `workflow` field, which would silently break this exact task.

3. **No error transition exists on the childJob task itself**, matching the one real production example I found (NetBox "Delete Prefix"). That's correct as long as "Device Backup" is built to always complete (catches its own errors and reports `taskStatus`, per point 1) — if it can genuinely throw an unhandled platform-level error (e.g., the workflow name can't be resolved), this parent would hang with "no available transitions." If you want that extra safety net, add an `error` transition from `a1a1` to an intermediate `newVariable` task that sets a `parentError` flag before `workflow_end`, per the skill's standard duplicate-key workaround.
