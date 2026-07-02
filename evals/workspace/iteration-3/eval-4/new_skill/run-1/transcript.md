# Transcript — Build a `makeData` workflow (deviceName + action → JSON string)

## Task (as given)

> Create a workflow with `makeData` that generates a JSON string containing `deviceName` and `action` fields from job variables.

No live Itential Platform connection was available for this session (no `.auth.json` / `.env` / real `tasks.json` for a specific use-case workspace). Per the `builder-agent` skill's Workspace Contract, the builder should stop and treat missing bootstrap/discovery files as an upstream failure for *platform-specific* task discovery (adapter lookups, schema fetches, etc.). However, `makeData` is a built-in `WorkFlowEngine` utility task (Application-type, not an adapter task) — its schema and wiring pattern are fully documented in the skill itself and demonstrated in the repo's real, production-exported asset projects under `helpers/assets/`. So this task did not require any live API calls or tasks.json/apps.json lookups — it only required consulting the skill's `makeData` section and the real asset examples, exactly as instructed. I built the workflow JSON artifact directly, as instructed by the eval's REPO CONTEXT.

## Skill sections consulted (in order)

1. **`/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md`** — read in full (2442 lines, two passes) before doing anything else, per the eval instructions.
   - `## Workspace Contract` — confirmed `makeData` doesn't require re-pulling discovery data since it's a stock utility task, not an adapter task.
   - `### Guide 1: Build a workflow end-to-end` — the mandatory "STOP, read real asset projects first" block; Step 4 mapping rules (name/canvasName/app/location/type/actor); Step 5 "Handle object inputs" (merge before object-typed incoming); Step 9 pre-submit checklist.
   - `## Workflows` → `### Workflow Structure` — the `{"automation": {...}}` POST body shape, `inputSchema`/`outputSchema` conventions, task/transition structure.
   - `### Task IDs` — hex-only `[0-9a-f]{1,4}` requirement.
   - `### Transitions` — mandatory error transitions are for adapter/external tasks; merge/makeData (internal WorkFlowEngine tasks) don't require them (confirmed against real asset transitions, see below).
   - `## $var Resolution Rules` — `$var` doesn't resolve inside nested objects; must build via `merge` first, then reference `$var.taskId.merged_object`.
   - `### merge` — `data_to_merge` reference format (`{"key":..., "value": {"task":"job","variable":"..."}}`), requires ≥2 items, uses `"variable"` field name (not `"value"`) inside the taskRef.
   - `### makeData` — full incoming/outgoing spec: `input` (string with `<!var!>` placeholders), `outputType` (`string`/`json`/`number`/`boolean`), `variables` (must be a **resolved object**, built via a prior `merge`). Explicit warning: never feed a childJob-sourced merge directly into `makeData.incoming.variables` (not applicable here — no childJob involved).
   - `### nodeLocation Spacing Convention` — vertical layout, spine at constant x, 108px y-delta for sequential single-thread tasks (no fork here, so no ±264 offset needed).
   - Root `AGENTS.md` — Key Rule #8 (`$var` doesn't resolve in nested objects — use merge/makeData/query) and #6 (variable syntax table: `<!var!>` for makeData/command templates vs `$var.job.x` for workflow wiring).

2. **Real production asset files** (per the skill's mandatory "STOP, read these first" instruction in Guide 1) — pulled with `jq`/`python3` from `${CLAUDE_PLUGIN_ROOT}/helpers/assets/`:
   - `helpers/assets/itential-platform-configuration-management.json` — extracted a live `makeData` task (`outputType: "string"`, `input: "[name=<!treeName!>].id"`, `variables: "$var.7c0d.options"`) to confirm the exact field shape and that `variables` is wired as a `$var.<mergeTaskId>.merged_object`-style reference, not inline.
   - `helpers/assets/lcm/lcm-vxlan-fabric-services-project.json` — extracted another live `makeData` task (`"Chat Message"` task, id `7547`) that builds a **string** output with multiple `<!var!>` placeholders (`<!accessVlan!>`, `<!vniSubnet!>`, `<!anycastGWIP!>`) substituted from a merged `variables` object (`$var.c10.templateInputs`) — this is the direct precedent pattern for "JSON string with multiple fields substituted from job variables." Also confirmed downstream tasks reference this makeData's output via `{"task": "7547", "variable": "output"}` (the merge/query taskRef convention), matching the skill's checklist line: "makeData→`output`".
   - `helpers/assets/vendor-servicenow.json` — extracted the "Create Change Request" workflow's `merge` task (id `aab9`) to confirm `data_to_merge` shape (`{"key":..., "value": {"task":"job","variable":...}}`) and confirmed via its `transitions` block that **merge tasks carry only a `success` transition** — no `error` transition — validating that the mandatory error-transition rule in the skill applies to adapter/external tasks, not internal WorkFlowEngine utility tasks like `merge`/`makeData`.

## Design decisions

- **Two tasks, not one**: `makeData.incoming.variables` must be a *resolved object* — the skill is explicit that `$var` references inside nested objects don't resolve, so a `merge` task must run first to assemble `{deviceName, action}` from the two job variables, and `makeData` then references `$var.<mergeId>.merged_object` as its `variables` input.
- **`outputType: "string"`**: the ask is for a JSON *string* (not a native JSON object), so `outputType` is `"string"` and `input` is a literal JSON-looking string with `<!deviceName!>` / `<!action!>` placeholders — mirroring the real "Chat Message" makeData task pattern found in the VXLAN asset project.
- **`deviceName`/`action` as genuine workflow inputs**: wired in `merge.data_to_merge` via `{"task": "job", "variable": "deviceName"}` / `{"task": "job", "variable": "action"}`. Per the skill's warning, `{task:"job"}` refs auto-populate `inputSchema.required` — this is intended here since the task says "from job variables," i.e., these are meant to be supplied to the workflow. `inputSchema` explicitly declares both as required strings to match.
- **makeData output bound to a job variable** (`$var.job.deviceActionJson`) rather than left as `$var.taskId.output`: per the `$var Resolution Rules` guidance, job variables should be used when "values need to be visible in job output" — since this is the terminal result of the workflow, it's exposed in `outputSchema` as `deviceActionJson`.
- **No error transitions on `merge`/`makeData`**: verified against the real ServiceNow asset — its `merge` task's transitions only carry `success`, no `error` key. The skill's mandatory-error-transition rule targets adapter/external tasks specifically (`### Transitions`: "Every adapter/external task needs an error transition"). `merge` and `makeData` are internal WorkFlowEngine tasks with no adapter call, so no error path is required.
- **Task IDs**: `a1a1` (merge), `b2b2` (makeData) — both validated as `[0-9a-f]{1,4}` hex-only per the skill's Task ID rule (verified with a regex check).
- **Canvas layout**: vertical spine at `x=600`, sequential tasks at `y=200, 308, 416, 524` (108px deltas) — no fork in this workflow, so no `±264` offset needed, per the `nodeLocation Spacing Convention` section.

## Workflow JSON produced

Written to: `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-4/new_skill/run-1/outputs/workflow-makeData-device-action.json`

```json
{
  "automation": {
    "name": "Make Device Action Data",
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
      "a1a1": {
        "name": "merge",
        "canvasName": "merge",
        "summary": "Build makeData Variables",
        "description": "Merges deviceName and action job variables into a single object for makeData's variables input.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "data_to_merge": [
              {
                "key": "deviceName",
                "value": { "task": "job", "variable": "deviceName" }
              },
              {
                "key": "action",
                "value": { "task": "job", "variable": "action" }
              }
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
        "nodeLocation": { "x": 600, "y": 308 }
      },
      "b2b2": {
        "name": "makeData",
        "canvasName": "makeData",
        "summary": "Generate Device/Action JSON String",
        "description": "Substitutes deviceName and action into a JSON-formatted string using <!var!> placeholders.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "automatic",
        "displayName": "Tools",
        "variables": {
          "incoming": {
            "input": "{\"deviceName\": \"<!deviceName!>\", \"action\": \"<!action!>\"}",
            "outputType": "string",
            "variables": "$var.a1a1.merged_object"
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
        "nodeLocation": { "x": 600, "y": 416 }
      },
      "workflow_end": {
        "name": "workflow_end",
        "groups": [],
        "nodeLocation": { "x": 600, "y": 524 }
      }
    },
    "transitions": {
      "workflow_start": {
        "a1a1": { "type": "standard", "state": "success" }
      },
      "a1a1": {
        "b2b2": { "type": "standard", "state": "success" }
      },
      "b2b2": {
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

**Flow:** `workflow_start` → `a1a1 (merge: {deviceName, action} → merged_object)` → `b2b2 (makeData: substitutes <!deviceName!>/<!action!> into a JSON string using merged_object as variables)` → `workflow_end`.

**Result at runtime:** given job input `{"deviceName": "IOS-CAT8KV-1", "action": "backup"}`, the workflow produces job output `deviceActionJson = "{\"deviceName\": \"IOS-CAT8KV-1\", \"action\": \"backup\"}"` — a JSON-formatted string (not a parsed object), matching the literal ask ("generates a JSON string").

## Pre-submit checklist verification (Guide 1, Step 9)

- [x] Task IDs hex-only: `a1a1`, `b2b2` — regex-validated
- [x] `app`/`locationType` — N/A adapter check (both tasks are `WorkFlowEngine` Application tasks, no adapter involved)
- [x] `canvasName` matches `name` for both (`merge`, `makeData` — confirmed against real assets, no canvasName divergence for these two)
- [x] No `$var` references inside nested objects — `makeData.incoming.variables` is a single top-level `$var.a1a1.merged_object` reference (not nested), and `merge.data_to_merge` items are top-level array entries per the documented format
- [x] `merge` uses `"variable"` inside its taskRefs (confirmed: `{"task":"job","variable":"deviceName"}`); `makeData` variables field is a resolved object reference, not a childJob-sourced merge (the childJob/makeData warning doesn't apply — no childJob in this workflow)
- [x] No `{task:"job", variable:"x"}` used for internal-only variables — both `deviceName` and `action` are genuine, deliberate workflow inputs, so `{task:"job"}` refs are correct here and intentionally drive `inputSchema.required`
- [x] `workflow_end` transition is empty `{}`
- [x] Canvas layout follows vertical spine convention, no fork, 108px y-deltas
- [x] No error transitions needed on `merge`/`makeData` (not adapter/external tasks — verified against the ServiceNow asset's merge task transitions, which also has no error path)

## Final answer / recommendation to the engineer

Here's the workflow: **`workflow_start → merge → makeData → workflow_end`**.

The reason it's two tasks and not one is a hard platform constraint documented in the skill: `makeData`'s `variables` input has to be a fully resolved object — you can't hand it `$var.job.deviceName` and `$var.job.action` directly inside an inline object, because `$var` references don't resolve when nested inside another value. So the `merge` task runs first, pulls `deviceName` and `action` off the job, and produces `merged_object`. `makeData` then points its `variables` field at `$var.a1a1.merged_object` and does the actual substitution: `input` is the literal string `{"deviceName": "<!deviceName!>", "action": "<!action!>"}` with `outputType: "string"`, so at runtime it emits a real JSON-formatted *string* (not a parsed object) — exactly what was asked for.

I verified this pattern isn't invented — I pulled two real, production-exported `makeData` tasks from the repo's asset library (`helpers/assets/itential-platform-configuration-management.json` and `helpers/assets/lcm/lcm-vxlan-fabric-services-project.json`) that follow the identical shape: `outputType: "string"`, `<!var!>` placeholders in `input`, and `variables` pointed at a prior merge's `merged_object`. I also checked a live ServiceNow asset workflow to confirm that internal utility tasks like `merge`/`makeData` don't need error transitions the way adapter calls do — only `success` transitions are present on those in production exports.

`deviceName` and `action` are wired as genuine job/workflow inputs (`{"task":"job","variable":"..."}` in the merge), so they're declared in `inputSchema.required`. The final JSON string is bound to a job output variable `deviceActionJson`, declared in `outputSchema`, so it's visible in the job's results.

One thing to flag before this goes live: this workflow was built and validated as JSON only — there's no connected Itential Platform in this session, so I couldn't `POST /automation-studio/automations`, run a test job, or confirm the actual runtime string output. Before calling this done, someone should: (1) POST this body to `/automation-studio/automations` on a real platform, (2) start a job with `{"deviceName": "...", "action": "..."}`, and (3) confirm `deviceActionJson` comes back as the expected literal JSON string (per Guide 2's testing/debug flow — `GET /operations-manager/jobs/{jobId}` and inspect `data.tasks.b2b2` outgoing values). If you want this inside a named project instead of a bare workflow, let me know the project (or I can wrap it via `POST /automation-studio/projects/import` with a pre-computed project `_id`), and I'll also need to know who should own/have access to that project before I'd PATCH membership.
