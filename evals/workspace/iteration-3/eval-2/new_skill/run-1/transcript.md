# Transcript — Build: childJob parallel loop calling "Device Backup"

## Task restated

Create a workflow with a `childJob` that runs a child workflow called **"Device Backup"** for each
device in an array, running them **in parallel**.

No live Itential platform is connected in this session, so no API calls (auth, task discovery,
`jobs/start`, etc.) were made. The deliverable is the actual JSON artifact(s) — a child workflow and
a parent orchestrator workflow — built by following the `builder-agent` skill's documented process
and by extracting real, production-tested task wiring from the skill's asset library
(`helpers/assets/`), exactly as the skill instructs ("Do not guess task structure from memory").

## Skill sections consulted (in order)

1. **Workspace Contract** — noted this is a freeform build (no `use-cases/{name}/` workspace exists
   in this session), so there's no `tasks.json`/`apps.json`/`adapters.json` to search and no live
   platform to fetch schemas from. I treated this as an "explore/freestyle" build and fell back to
   the skill's asset library as the source of truth for real task JSON, per the skill's own guidance
   to never invent task schemas from memory.
2. **Guide 1: Build a workflow end-to-end** — specifically the **STOP block** ("Read production
   asset projects first, don't guess task structure from memory") and Step 0 ("Decompose before you
   build" — parent/child split; loop over multiple items → child workflow with `loopType`).
3. **Guide 4: Build a childJob (parent calls child workflow)** — this is the exact recipe for the
   task: **Mode B: Loop — one child per item in `data_array`**. Read the full mode B spec: task
   shape, `variables: {}`, `data_array`, `loopType: "parallel"`, the loop-output shape, the "Loop
   element completeness" warning (data_array elements must satisfy the child's
   `inputSchema.required` on their own), and the "Building the child workflow" try-catch pattern
   (child must always complete and report a `taskStatus`).
4. **childJob checklist** (Guide 4) and the **childJob body section** (`### childJob` under Utility
   Tasks) — cross-checked field-by-field: `actor: "job"`, `task: ""`, `job_details: null`, all
   incoming fields present even when unused, `variables` uses `{"task","value"}` not `$var`.
5. **nodeLocation Spacing Convention** — vertical layout rules (spine at constant x, fork branches at
   `spine ± 264`, ~108px y-delta, convergence back to spine).
6. **Workflow Structure** section — the `POST /automation-studio/automations` body shape
   (`{"automation": {...}}`), required top-level fields (`canvasVersion`, `encodingVersion`,
   `font_size`, `inputSchema`, `outputSchema`).
7. **Pre-submit checklist** (Guide 1, Step 9) and the **Gotchas** pre-flight list — used as the final
   validation pass on both workflows before calling them done.
8. **Workflow Patterns → Error Handling: Try-Catch** — confirmed the parent/child error-handling
   contract (child catches its own errors and reports `taskStatus`; parent extracts and can branch
   on it).

## Real asset files pulled (per the skill's "look up, don't guess" rule)

Ran the STOP-block jq commands from Guide 1 against `helpers/assets/` (resolved
`${CLAUDE_PLUGIN_ROOT}` = `/Users/ankitrbhansali/builderskills/builder-skills`):

- `jq '[.components[] | select(.type=="workflow")] | .[].document.name' helpers/assets/itential-platform-configuration-management.json`
  → found a real **"Backup Configuration"** workflow. Extracted its `backUpDevice` task
  (`ConfigurationManager.backUpDevice`, `location: "Application"`, incoming `{name, options}`,
  outgoing `{status}`) and its follow-up `query` task (`query: "id"`, `obj: "$var.<taskId>.status"`)
  — used both as the real, wired reference for the child workflow's single-device backup task.
- `grep -l '"name": "childJob"' helpers/assets/*.json` → found real childJob usage in
  `itential-platform-configuration-management.json`, `vendor-arista-eos.json`, `vendor-netbox.json`.
- `grep -o '"loopType": "[^"]*"' helpers/assets/*.json helpers/assets/lcm/*.json` → confirmed the
  asset library has **no** `loopType: "parallel"` example (only `""` and one `"sequential"`), but
  the skill explicitly states Mode B is "tested and verified on a live platform" and documents
  `parallel` as a first-class value alongside `sequential`. I used the one real **`data_array` +
  `loopType: "sequential"`** example that does exist — `vendor-netbox.json`'s "Delete Prefix"
  workflow, task `4b5c` (`childJob`, `workflow: "Delete IP Address - NetBox"`, `variables: {}`,
  `data_array: "$var.1bd8.ipsInPrefix"`, `loopType: "sequential"`, `actor: "job"`,
  `outgoing.job_details: null`) — as the structural template, changing only `loopType` to
  `"parallel"` per the skill's documented enum (`""`/`"parallel"`/`"sequential"`). This confirmed the
  skill's Guide 4 Mode B JSON shape matches a real production export exactly, field for field.
- Also pulled `Delete Prefix`'s downstream `query` task (`82ca`: `query: "loop"`,
  `obj: "$var.4b5c.job_details"`) as the real reference for extracting loop results in the parent.

## Design decisions

- **Decomposition (Guide 1, Step 0):** "Does it loop over multiple items (devices)?" → yes → child
  workflow with `loopType`. Built two separate, independently-testable workflows:
  1. **`Device Backup`** (child) — backs up exactly one device, always completes, reports
     `taskStatus`.
  2. **`Backup All Devices (Parallel)`** (parent/orchestrator) — pure `childJob` fan-out + result
     extraction, no raw adapter tasks, per the rule "the orchestrator is just childJob calls to
     tested children."
- **Child workflow input contract:** `inputSchema.required = ["deviceName"]` only (`backupOptions` is
  optional). This was a deliberate choice to satisfy the Guide 4 "Loop element completeness" rule
  without needing the forEach-enrichment workaround — each `data_array` element only needs to carry
  `deviceName`, which is exactly what the parent's `devices` array elements contain
  (`[{"deviceName": "..."}, ...]`). Had the child required additional shared fields (e.g., a
  credential ID), the forEach → merge → arrayPush enrichment pattern from Guide 4 would be needed
  before the childJob loop — noted as an open item below in case the real child workflow ends up
  needing shared inputs.
- **Try-catch in the child:** `backUpDevice` --success--> `query` (extract `backupId`) -->
  `newVariable(taskStatus=success)` --> `workflow_end`; `backUpDevice` --error-->
  `newVariable(taskStatus=error)` --> `workflow_end`. This matches Guide 4's "Building the child
  workflow" pattern exactly, so the workflow always completes and the parent can safely evaluate
  results.
- **No error transition on the parent's `childJob` task** — checked all three real assets that use
  `childJob`; none of them wire an explicit `error` transition off the `childJob` task itself (only
  `success`, or no transition at all). This is consistent with the skill's model: the child handles
  its own errors internally, and the parent inspects `taskStatus` per iteration inside
  `job_details.loop`, rather than the platform raising a top-level `childJob` error. I followed the
  real pattern rather than blanket-applying the "every external task needs an error transition" rule,
  since childJob is documented and shown in production as terminating only via `success`.
- **`query: "loop"`** on the parent to extract the full per-iteration results array from
  `job_details`, per Guide 4 Mode B ("Extracting loop output"), output bound to
  `$var.job.backupResults`.
- **Canvas layout** follows the vertical spacing convention: constant spine x=600, fork branches at
  ±264 (336/864), ~108px sequential y-delta, convergence tasks back on the spine.
- **Task IDs** are all hex-only (`[0-9a-f]{1,4}`): child uses `a1b1`, `b2c2`, `c3d3`, `e5f5`; parent
  uses `a1a1`, `b2b2`. Verified programmatically with a regex check (see below).

## Artifacts produced

Both are full `POST /automation-studio/automations` request bodies (`{"automation": {...}}`), ready
to POST as-is once a live platform session exists, or to nest inside a `POST
/automation-studio/projects/import` `components[].document` per the skill's atomic-import pattern.

### 1. Child workflow — `Device Backup`

File: `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-2/new_skill/run-1/outputs/device-backup-child-workflow.json`

```json
{
  "automation": {
    "name": "Device Backup",
    "description": "Backs up the running configuration for a single device. Always completes (try-catch pattern) and reports taskStatus (success/error) plus the backup record ID, so a parent childJob loop can evaluate the per-device outcome.",
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
      "a1b1": {
        "name": "backUpDevice",
        "canvasName": "backUpDevice",
        "summary": "Backup Device Configuration",
        "description": "Backs up the running configuration for the target device.",
        "location": "Application",
        "locationType": null,
        "app": "ConfigurationManager",
        "type": "automatic",
        "displayName": "ConfigurationManager",
        "variables": {
          "incoming": {
            "name": "$var.job.deviceName",
            "options": "$var.job.backupOptions"
          },
          "outgoing": {
            "status": null
          },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": {"x": 600, "y": 312}
      },
      "b2c2": {
        "name": "query",
        "canvasName": "query",
        "summary": "Extract Backup ID",
        "description": "Extracts the backup record ID from the backup status response.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "pass_on_null": false,
            "query": "id",
            "obj": "$var.a1b1.status"
          },
          "outgoing": {
            "return_data": "$var.job.backupId"
          },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": {"x": 336, "y": 420}
      },
      "e5f5": {
        "name": "newVariable",
        "canvasName": "newVariable",
        "summary": "Set Task Status - Error",
        "description": "Marks this device's backup as failed so the parent childJob loop can identify it.",
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
        "nodeLocation": {"x": 864, "y": 420}
      },
      "c3d3": {
        "name": "newVariable",
        "canvasName": "newVariable",
        "summary": "Set Task Status - Success",
        "description": "Marks this device's backup as successful so the parent childJob loop can identify it.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "name": "taskStatus",
            "value": "success"
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
        "nodeLocation": {"x": 336, "y": 528}
      },
      "workflow_end": {
        "name": "workflow_end",
        "groups": [],
        "nodeLocation": {"x": 600, "y": 636}
      }
    },
    "transitions": {
      "workflow_start": {
        "a1b1": {"type": "standard", "state": "success"}
      },
      "a1b1": {
        "b2c2": {"type": "standard", "state": "success"},
        "e5f5": {"type": "standard", "state": "error"}
      },
      "b2c2": {
        "c3d3": {"type": "standard", "state": "success"}
      },
      "e5f5": {
        "workflow_end": {"type": "standard", "state": "success"}
      },
      "c3d3": {
        "workflow_end": {"type": "standard", "state": "success"}
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
          "examples": ["IOS-CAT8KV-1"]
        },
        "backupOptions": {
          "title": "backupOptions",
          "type": "object",
          "description": "Optional backup options object (view/notes/etc). Defaults to {} if not supplied by the caller."
        }
      },
      "required": ["deviceName"]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "backupId": {
          "title": "backupId",
          "type": "string"
        },
        "taskStatus": {
          "title": "taskStatus",
          "type": "string",
          "enum": ["success", "error"]
        }
      }
    }
  }
}
```

### 2. Parent workflow — `Backup All Devices (Parallel)`

File: `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-2/new_skill/run-1/outputs/backup-all-devices-parent-workflow.json`

```json
{
  "automation": {
    "name": "Backup All Devices (Parallel)",
    "description": "Orchestrator. Runs the 'Device Backup' child workflow once per device in the input array, in parallel, via a childJob loop (loopType: parallel). Extracts the per-device taskStatus/backupId results after the loop completes.",
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
      "a1a1": {
        "name": "childJob",
        "canvasName": "childJob",
        "summary": "Backup Each Device (Parallel)",
        "description": "Runs the Device Backup child workflow once per element in the devices array, all in parallel.",
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
          "outgoing": {
            "job_details": null
          }
        },
        "groups": [],
        "actor": "job",
        "nodeLocation": {"x": 600, "y": 312}
      },
      "b2b2": {
        "name": "query",
        "canvasName": "query",
        "summary": "Extract Backup Results",
        "description": "Extracts the per-device loop results (taskStatus, backupId, deviceName, etc.) from the childJob output.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "pass_on_null": false,
            "query": "loop",
            "obj": "$var.a1a1.job_details"
          },
          "outgoing": {
            "return_data": "$var.job.backupResults"
          },
          "error": "",
          "decorators": []
        },
        "groups": [],
        "actor": "Pronghorn",
        "scheduled": false,
        "nodeLocation": {"x": 600, "y": 420}
      },
      "workflow_end": {
        "name": "workflow_end",
        "groups": [],
        "nodeLocation": {"x": 600, "y": 528}
      }
    },
    "transitions": {
      "workflow_start": {
        "a1a1": {"type": "standard", "state": "success"}
      },
      "a1a1": {
        "b2b2": {"type": "standard", "state": "success"}
      },
      "b2b2": {
        "workflow_end": {"type": "standard", "state": "success"}
      },
      "workflow_end": {}
    },
    "groups": [],
    "inputSchema": {
      "type": "object",
      "properties": {
        "devices": {
          "title": "devices",
          "type": "array",
          "description": "One object per device. Each object's keys become that iteration's child-workflow input variables (must satisfy Device Backup's inputSchema.required: deviceName).",
          "items": {
            "type": "object",
            "properties": {
              "deviceName": {"type": "string"}
            },
            "required": ["deviceName"]
          },
          "examples": [
            [
              {"deviceName": "IOS-CAT8KV-1"},
              {"deviceName": "IOS-CAT8KV-2"},
              {"deviceName": "EOS-AWS-1"}
            ]
          ]
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
          "description": "One entry per device: {status, childJobLoopIndex, deviceName, taskStatus, backupId, ...}"
        }
      }
    }
  }
}
```

## Verification performed (no live platform, so static checks only)

Ran the skill's pre-submit checklist mechanically against both files:

- `jq empty` on both files → valid JSON.
- Task-ID regex check (`^[0-9a-f]{1,4}$`) on every non-`workflow_start`/`workflow_end` key → all
  pass (`a1b1`, `b2c2`, `c3d3`, `e5f5` / `a1a1`, `b2b2`).
- Parent `childJob` task (`a1a1`): `actor: "job"` ✓, `task: ""` ✓, `job_details: null` ✓,
  `loopType: "parallel"` ✓, `data_array: "$var.job.devices"` ✓, `variables: {}` ✓ (loop mode, per
  Guide 4 Mode B).
- `workflow_end.transitions` empty `{}` on both workflows ✓.
- Every adapter/external task (`backUpDevice`) has both a success and an error transition ✓; no
  duplicate-key routing to `workflow_end` (error routes through a `newVariable` first) ✓.
- No `$var` references embedded inside nested object literals ✓ (`options` is a top-level `$var`
  string, not nested).
- `merge`/`evaluation` weren't needed for this build (no branching, no object construction beyond
  top-level `$var` refs), so the `"variable"` vs `"value"` distinction only applies to the single
  `childJob` task, which correctly uses `{"task","value"}` semantics (empty `variables: {}` here
  since this is loop mode, not single mode).

**Could NOT be verified in this session (no live platform connected):**
- `POST /automation-studio/workflows/validate` was not run (no platform to call). Run this before
  creating/updating either workflow.
- The exact input schema for `ConfigurationManager.backUpDevice`'s `options` field was not fetched
  via `multipleTaskDetails` (no `tasks.json`/`apps.json` in this session) — the `{name, options}`
  shape and `Application`/`ConfigurationManager` app values were taken directly from the real,
  wired `backUpDevice` task in `helpers/assets/itential-platform-configuration-management.json`
  ("Backup Configuration" workflow), so the shape is real, but the exact accepted values/defaults
  for `options` should be confirmed with a schema fetch once a platform session exists.
- No real asset in `helpers/assets/` uses `loopType: "parallel"` specifically — verified against a
  real `loopType: "sequential"` + `data_array` example instead (`vendor-netbox.json`, "Delete
  Prefix" workflow) and changed only the loop-type value per the skill's documented enum. This is
  the one part of the build that relies on the skill's written spec rather than a byte-for-byte
  asset match, though the skill explicitly states Mode B is platform-tested.

## Final answer / recommendation to the engineer

I built this as **two workflows**, per the skill's parent/child decomposition rule (loop over
multiple items → child workflow with `loopType`, orchestrator is childJob-only):

1. **`Device Backup`** — the child. Takes one `deviceName` (+ optional `backupOptions`), calls
   `ConfigurationManager.backUpDevice`, and *always* completes — on success it extracts the backup ID
   and sets `taskStatus: "success"`; on error it sets `taskStatus: "error"`. This mirrors the real
   "Backup Configuration" workflow's `backUpDevice` wiring already running in your platform's
   configuration-management asset project, just narrowed to a single device per invocation (which is
   what's needed for a `childJob` fan-out).

2. **`Backup All Devices (Parallel)`** — the parent. It's just two tasks: a `childJob` in loop mode
   (`workflow: "Device Backup"`, `data_array: "$var.job.devices"`, `loopType: "parallel"`,
   `variables: {}`), and a `query` that pulls the `"loop"` results array back out into
   `$var.job.backupResults`. Call it with:
   ```json
   {"devices": [{"deviceName": "IOS-CAT8KV-1"}, {"deviceName": "IOS-CAT8KV-2"}, {"deviceName": "EOS-AWS-1"}]}
   ```
   and after it finishes, `backupResults` will contain one entry per device with `taskStatus`,
   `backupId`, `deviceName`, and `childJobLoopIndex`, so you can post-process to find any failures.

Before you deploy this: (1) create `Device Backup` first and test it standalone via `jobs/start`
with a single device, per the skill's build order ("children first, orchestrator last"); (2) only
after that passes, create the parent and test it with a small device array; (3) run
`POST /automation-studio/workflows/validate` on both bodies before creating/updating them — I
couldn't do that here since there's no live platform in this session; (4) confirm the exact
`backUpDevice.options` schema against your platform's `task-schemas.json` (fetch via
`multipleTaskDetails` if you haven't already) in case your Configuration Manager version has
additional required fields; (5) if you later need the child to accept additional *shared* fields
(e.g., a credential set that's the same for every device, not per-device), don't try to pass them
via the `childJob`'s static `variables` — those are ignored for loop-mode required-field validation.
Use the forEach → merge → arrayPush enrichment pattern from the skill's Guide 4 to bake those shared
fields into every `data_array` element before the loop.
