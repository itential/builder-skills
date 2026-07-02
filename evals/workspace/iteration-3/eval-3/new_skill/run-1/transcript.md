# Transcript — builder-agent skill test run

## Task restated

Build a workflow where a `childJob` runs a single child workflow and passes the parent's
`ticketId` and `deviceName` to the child. After the child completes, extract the child's
`taskStatus` using a `query` task.

No live Itential Platform is connected in this session. Per the eval instructions, the
deliverable is the actual workflow JSON artifact(s) (tasks, transitions, incoming/outgoing
wiring), built exactly the way the `builder-agent` skill instructs — using real production
asset JSON as the source of truth for task shape, not memory.

## Skill sections consulted (in order)

1. `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md`
   — read in full (both pages, ~2442 lines):
   - **Workspace Contract** / **Build Lifecycle** — noted that a full delivery would normally
     require `use-cases/{name}/tasks.json`, `apps.json`, `adapters.json` before touching a live
     platform. Since this is a standalone build/explore-style request with no use-case workspace
     and no live platform, I stayed within what the skill documents as fully-schema'd,
     platform-agnostic **WorkFlowEngine utility tasks** (`childJob`, `query`, `newVariable`)
     rather than fabricating an adapter task schema I have no `tasks.json`/`apps.json` to verify
     against — this follows the skill's explicit "do not guess task structure from memory" rule.
   - **Guide 1: Build a workflow end-to-end** — task ID hex rule, `$var` resolution rules,
     mandatory error transitions, pre-submit checklist.
   - **Guide 4: Build a childJob (parent calls child workflow)** — this is the core guide for
     the task. Mode A ("Single child — pass variables with `{"task","value"}`") is exactly the
     requested pattern. Read the full mode A example, the childJob checklist, the "Extracting
     single child output" query pattern, the `$var` "returns null" workaround (merge + taskRef),
     and "Building the child workflow" (child must accept `inputSchema`, output a status var,
     and internally try/catch so it always completes).
   - **`### childJob` (Utility Tasks / WorkFlowEngine)** — full incoming/outgoing field list,
     `actor: "job"`, `task: ""`, `"value"` vs `"variable"` distinction vs. `merge`/`evaluation`.
   - **`### query`** — incoming (`pass_on_null`, `query`, `obj`), outgoing (`return_data`),
     transitions (`success`/`failure`), and the warning not to guess adapter response shape
     (not applicable here since we're querying `job_details`, a WorkFlowEngine-internal shape
     the skill documents directly: flat keys like `"taskStatus"`, not `"variables.job.taskStatus"`).
   - **`### newVariable`** — used for the child's `taskStatus` output and the parent's fallback
     handler; confirmed `$var` does not resolve inside `value` (not needed here — literal string
     values only).
   - **`## Workflow Patterns` → Error Handling: Try-Catch** — the exact parent/child taskStatus
     pattern:
     ```
     child: task --success--> newVariable("taskStatus"="success") -> workflow_end
            task --error--> newVariable("taskStatus"="error") -> workflow_end
     parent: childJob -> query (extract taskStatus from job_details) -> evaluation (== "success"?)
     ```
   - **`nodeLocation` Spacing Convention** — vertical layout, spine at constant x, fork branches
     offset ±264px, ~108px y-delta.
   - **Gotchas** pre-flight list — cross-checked every childJob/query/newVariable rule (items
     15–23) against the JSON I produced before finalizing.

2. Real asset JSON in `${CLAUDE_PLUGIN_ROOT}/helpers/assets/` (resolved to
   `/Users/ankitrbhansali/builderskills/builder-skills/helpers/assets/`), per the skill's
   mandatory "STOP — read real assets before writing task JSON" instruction:

   ```bash
   ls helpers/assets/
   jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "childJob")] | first | .value' \
     helpers/assets/vendor-cisco-ios.json
   ```
   **Finding:** the skill's own Guide 4 / Guide 3 examples point to `vendor-cisco-ios.json` for
   a `childJob` example, but that file has no `childJob` task at all (only IOS Upgrade, Port
   Turn Up, Run Compliance, NetBox sync workflows). I verified with:
   ```bash
   grep -rl '"name": "childJob"' helpers/assets/
   # -> vendor-arista-eos.json, vendor-netbox.json,
   #    itential-platform-configuration-management.json, lcm/lcm-vxlan-fabric-services-project.json
   ```
   This is a real gap in the skill's jq examples worth flagging back to the skill maintainer
   (see "Feedback on the skill" below). I pulled the real, wired `childJob` task from
   `itential-platform-configuration-management.json` instead (task `6f5`/`6bf9` inside the
   "Command Template Execution" workflow) and confirmed:
   - `actor: "job"`, `task: ""`, `variables` uses `{"task","value"}` — matches the skill text.
   - Its `variables` used `{"task":"job","value":"templateName"}` style refs for parent-supplied
     inputs — exactly the pattern I used for `ticketId`/`deviceName`.
   - **Critically**, in the real production workflow, the `childJob` tasks (`6f5`, `6bf9`) have
     **no error transition at all** — only a `success` transition (or, for the loop-body
     childJob, an empty `{}` terminator). This confirms the skill's documented rationale: the
     child workflow is expected to catch its own errors internally and always finish, so the
     parent's `childJob` task itself doesn't need an external error transition — the parent
     instead checks `taskStatus` after the fact via `query`. I mirrored this in the parent
     workflow (no error transition off the `childJob` task).

   I also pulled real `query` tasks reading `$var.<childJobTaskId>.job_details` directly (no
   merge/taskRef workaround needed) from three different asset files:
   ```bash
   jq -r '[.components[].document.tasks[]? | select(.name=="query") |
     select(.variables.incoming.obj // "" | test("job_details"))]' \
     helpers/assets/itential-platform-configuration-management.json \
     helpers/assets/vendor-arista-eos.json helpers/assets/vendor-netbox.json
   ```
   Confirmed the direct `"obj": "$var.<childJobId>.job_details"` form is real and used in
   production (e.g., task `e4f3` querying `$var.42d2.job_details` for `"templateResults"`). I
   used the same direct form for `taskStatus`, and kept Guide 4's documented merge+taskRef
   fallback as a call-out for the engineer in case this platform version needs it (per the
   skill's own caveat that this is platform-version-dependent).

   I searched for an existing `"taskStatus"` convention in the asset library and found none —
   confirming this is a documented *pattern* from the skill body rather than something copied
   verbatim from an asset file. I built the child's `taskStatus` handling from the skill's
   explicit try/catch example instead of inventing it.

## Design decisions and how they map to the skill

**Parent workflow — "Run Device Ticket Child And Extract Status"**
- `inputSchema`: `ticketId` (string, required), `deviceName` (string, required) — these are
  genuine workflow inputs supplied by whoever/whatever starts this job, so per the skill's
  `{task:"job"}` rule (Rule 6/merge warning, mirrored for childJob) it's correct to reference
  them as `{"task": "job", "value": "ticketId"}` / `{"task": "job", "value": "deviceName"}` —
  using `{task:"job"}` here is *intentional* since they really are top-level required inputs,
  not internally-produced values.
- `a1b1` (`childJob`, single mode, `actor: "job"`, `task: ""`, all four incoming fields present
  even when unused: `data_array: ""`, `transformation: ""`, `loopType: ""`) — passes both
  variables via `{"task","value"}`, per the childJob-specific syntax (NOT `"variable"`, which
  the skill says causes `undefined.indexOf()` at job start on P6.4.0+).
- `b2c2` (`query`) — `obj: "$var.a1b1.job_details"`, `query: "taskStatus"` (flat key, per the
  skill's explicit warning not to use a nested path like `"variables.job.taskStatus"`),
  `outgoing.return_data: "$var.job.childTaskStatus"` so downstream/job output can read it.
  `pass_on_null: false` so a missing/undefined `taskStatus` routes to the `failure` transition
  instead of silently producing a null job output.
- `c3d3` (`newVariable`) — fallback handler on the query's `failure` transition, sets
  `childTaskStatus = "unknown"` so the job always reaches `workflow_end` cleanly instead of
  dying with "no available transitions" (Gotcha #19/#37-adjacent: every task with a
  non-success terminal state needs somewhere to go).
- No error transition on the `childJob` task itself — matches the real, wired production
  example (`6f5`/`6bf9` in `itential-platform-configuration-management.json`), and matches the
  skill's design intent that the child handles its own errors internally.
- Canvas layout follows the documented vertical convention: spine at `x=600`, ~108px y-delta,
  the one fork branch (`c3d3`, the failure handler) offset to `spine+264=864`, and `workflow_end`
  returns to the spine.
- Task IDs (`a1b1`, `b2c2`, `c3d3`) are hex-only, matching `[0-9a-f]{1,4}`.

**Child workflow — "Process Device Ticket - Child"**
- `inputSchema`: `ticketId`, `deviceName` (both required) — matches exactly what the parent's
  `childJob.variables` passes, per the childJob checklist item "Child workflow's
  `inputSchema.required` matches what you're passing."
- `outputSchema`: `taskStatus` (string) — this is what the parent's `query` task reads back.
- **Explicit placeholder, called out in the JSON's `description` and the task `summary`/
  `description` fields**: the task prompt did not specify what work the child actually performs
  against the ticket/device (no adapter, no `tasks.json`/`apps.json` for a target platform was
  provided — this session has no live platform connection). Rather than invent an adapter task
  schema from memory (explicitly prohibited by the skill: *"Do not guess task structure from
  memory"*), I built the child with a single `newVariable` task that unconditionally sets
  `taskStatus = "success"`, and documented directly in the JSON (and here) exactly how to wire
  in the real try/catch pattern from Guide 4 once a concrete task is chosen:
  ```
  <real task> --success--> newVariable(taskStatus="success") -> workflow_end
  <real task> --error--> newVariable(taskStatus="error") -> workflow_end
  ```
  This keeps the deliverable fully grounded (no fabricated schemas) while still being a
  structurally complete, importable child workflow that demonstrates the required contract
  (accepts `ticketId`/`deviceName`, always completes, outputs `taskStatus`).

## Artifacts produced

1. `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-3/new_skill/run-1/outputs/parent-workflow-childjob-orchestrator.json`
   — full `{"automation": {...}}` body, ready for `POST /automation-studio/automations`
   (per Guide 1 "Workflow Structure").

   ```json
   {
     "automation": {
       "name": "Run Device Ticket Child And Extract Status",
       "description": "Runs a single child workflow for a given ticket/device, passing ticketId and deviceName from the parent job, then extracts the child's taskStatus once the child completes.",
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
           "name": "childJob",
           "canvasName": "childJob",
           "summary": "Run Child Workflow For Ticket",
           "description": "Runs 'Process Device Ticket - Child' as a single (non-loop) child job, passing the parent's ticketId and deviceName job variables.",
           "location": "Application",
           "locationType": null,
           "app": "WorkFlowEngine",
           "type": "operation",
           "displayName": "WorkFlowEngine",
           "variables": {
             "incoming": {
               "task": "",
               "workflow": "Process Device Ticket - Child",
               "variables": {
                 "ticketId": {"task": "job", "value": "ticketId"},
                 "deviceName": {"task": "job", "value": "deviceName"}
               },
               "data_array": "",
               "transformation": "",
               "loopType": ""
             },
             "outgoing": {
               "job_details": null
             },
             "error": "",
             "decorators": []
           },
           "groups": [],
           "actor": "job",
           "scheduled": false,
           "nodeLocation": {"x": 600, "y": 308}
         },
         "b2c2": {
           "name": "query",
           "canvasName": "query",
           "summary": "Extract Child Task Status",
           "description": "Extracts taskStatus from the completed child job's job_details and writes it to the parent's childTaskStatus job variable.",
           "location": "Application",
           "locationType": null,
           "app": "WorkFlowEngine",
           "type": "operation",
           "displayName": "WorkFlowEngine",
           "variables": {
             "incoming": {
               "pass_on_null": false,
               "query": "taskStatus",
               "obj": "$var.a1b1.job_details"
             },
             "outgoing": {
               "return_data": "$var.job.childTaskStatus"
             },
             "error": "",
             "decorators": []
           },
           "groups": [],
           "actor": "Pronghorn",
           "scheduled": false,
           "nodeLocation": {"x": 600, "y": 416}
         },
         "c3d3": {
           "name": "newVariable",
           "canvasName": "newVariable",
           "summary": "Set Fallback Child Status",
           "description": "Fallback handler if taskStatus could not be extracted from job_details (query returned null/undefined) — sets childTaskStatus to 'unknown' instead of leaving the job stuck.",
           "location": "Application",
           "locationType": null,
           "app": "WorkFlowEngine",
           "type": "operation",
           "displayName": "WorkFlowEngine",
           "variables": {
             "incoming": {
               "name": "childTaskStatus",
               "value": "unknown"
             },
             "outgoing": {
               "value": "$var.job.childTaskStatus"
             },
             "error": "",
             "decorators": []
           },
           "groups": [],
           "actor": "Pronghorn",
           "scheduled": false,
           "nodeLocation": {"x": 864, "y": 524}
         },
         "workflow_end": {
           "name": "workflow_end",
           "groups": [],
           "nodeLocation": {"x": 600, "y": 632}
         }
       },
       "transitions": {
         "workflow_start": {
           "a1b1": {"type": "standard", "state": "success"}
         },
         "a1b1": {
           "b2c2": {"type": "standard", "state": "success"}
         },
         "b2c2": {
           "workflow_end": {"type": "standard", "state": "success"},
           "c3d3": {"type": "standard", "state": "failure"}
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
           "ticketId": {"title": "ticketId", "type": "string"},
           "deviceName": {"title": "deviceName", "type": "string"}
         },
         "required": ["ticketId", "deviceName"]
       },
       "outputSchema": {
         "type": "object",
         "properties": {
           "childTaskStatus": {"title": "childTaskStatus", "type": "string"}
         }
       }
     }
   }
   ```

2. `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-3/new_skill/run-1/outputs/child-workflow-process-device-ticket.json`
   — full `{"automation": {...}}` body for the child workflow.

   ```json
   {
     "automation": {
       "name": "Process Device Ticket - Child",
       "description": "Child workflow invoked by 'Run Device Ticket Child And Extract Status'. Accepts ticketId and deviceName from the parent, performs the ticket/device work, and ALWAYS completes with a taskStatus output ('success' or 'error') so the parent can safely query it. PLACEHOLDER: the actual business-logic task (adapter call, config push, etc.) has NOT been specified for this build — see notes below.",
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
         "d1d1": {
           "name": "newVariable",
           "canvasName": "newVariable",
           "summary": "PLACEHOLDER: Mark Ticket Processing Complete",
           "description": "PLACEHOLDER for the child's real work (e.g., a ServiceNow/adapter task keyed on $var.job.ticketId and $var.job.deviceName, looked up via tasks.json for the target platform). Currently just sets taskStatus=success unconditionally so the parent's query has something real to extract. Replace with the try/catch pattern from builder-agent Guide 4: route the real task's success transition to a newVariable(taskStatus=success) and its error transition to a separate newVariable(taskStatus=error), both leading to workflow_end.",
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
           "nodeLocation": {"x": 600, "y": 308}
         },
         "workflow_end": {
           "name": "workflow_end",
           "groups": [],
           "nodeLocation": {"x": 600, "y": 416}
         }
       },
       "transitions": {
         "workflow_start": {
           "d1d1": {"type": "standard", "state": "success"}
         },
         "d1d1": {
           "workflow_end": {"type": "standard", "state": "success"}
         },
         "workflow_end": {}
       },
       "groups": [],
       "inputSchema": {
         "type": "object",
         "properties": {
           "ticketId": {"title": "ticketId", "type": "string"},
           "deviceName": {"title": "deviceName", "type": "string"}
         },
         "required": ["ticketId", "deviceName"]
       },
       "outputSchema": {
         "type": "object",
         "properties": {
           "taskStatus": {"title": "taskStatus", "type": "string"}
         }
       }
     }
   }
   ```

Both files validated with `jq empty <file>` — well-formed JSON.

## Final answer / recommendation to the engineer

Here's the childJob → query pattern you asked for, built exactly per builder-agent Guide 4
Mode A ("single child, pass variables"), cross-checked against a real, wired `childJob` task
pulled from `helpers/assets/itential-platform-configuration-management.json` (the
`vendor-cisco-ios.json` file the skill's own jq examples point to for this doesn't actually
contain a `childJob` task — worth fixing in the skill, see below).

**Parent** (`parent-workflow-childjob-orchestrator.json`) does three things:
1. `a1b1` — a `childJob` task (`actor: "job"`, `task: ""`) that runs "Process Device Ticket -
   Child" once (not a loop — `loopType: ""`, `data_array: ""`), passing your `ticketId` and
   `deviceName` job variables via `{"task": "job", "value": "..."}` refs. This is the childJob-
   specific syntax — don't use `"variable"` here, that's for `merge`/`evaluation` only and will
   cause `undefined.indexOf()` at job start on P6.4.0+.
2. `b2c2` — a `query` task reading `"taskStatus"` straight out of `$var.a1b1.job_details` (flat
   key, not a nested path) and writing it to `$var.job.childTaskStatus`.
3. `c3d3` — a `newVariable` fallback that only fires if the query comes back null/undefined
   (`pass_on_null: false` routes that case to the `failure` transition instead of silently
   losing the value), so the job never gets stuck with "no available transitions."

Note there is intentionally **no error transition on the childJob task itself** — that matches
how it's actually wired in the production `itential-platform-configuration-management.json`
asset. The convention (and Guide 4's documented rationale) is that the child is responsible for
catching its own errors internally and always completing; the parent's job is just to inspect
`taskStatus` afterward, which is exactly what the `query` task does.

**Child** (`child-workflow-process-device-ticket.json`) declares `inputSchema.required =
[ticketId, deviceName]` to match what the parent passes, and always outputs a `taskStatus`
job variable. One important caveat: the task didn't specify what work the child should
actually perform against the ticket/device, and I don't have a live platform or a `tasks.json`/
`apps.json` for any target system in this session — so rather than invent an adapter task shape
from memory (which the skill explicitly forbids — "do not guess task structure from memory"),
I built the child with a single placeholder `newVariable` task that unconditionally sets
`taskStatus = "success"`. Before you use this for real, drop in your actual task(s)
(look them up via `tasks.json`/`apps.json` per Guide 1 Steps 1-3) and wire the try/catch pattern
from Guide 4 around it:
```
<real task> --success--> newVariable(taskStatus="success") -> workflow_end
<real task> --error--> newVariable(taskStatus="error") -> workflow_end
```
That's a straight drop-in replacement for the current `d1d1` placeholder task — same
`inputSchema`/`outputSchema`, same wiring contract with the parent.

Two things to check before you import these for real:
- If these go into a project, the parent's `childJob.variables.incoming.workflow` field needs
  the `@{projectId}: ` prefix once both workflows are inside the same project (per the skill's
  Projects section) — plain `"Process Device Ticket - Child"` only works standalone or across
  projects if that's the exact bare/global name.
- Run `POST /automation-studio/workflows/validate` on both before creating them — that's the
  skill's mandatory pre-flight check and it will catch anything I couldn't verify without a
  live platform connection.

**Feedback on the skill itself** (from actually following it end-to-end): Guide 3 and the
"Task templates — extract from asset projects" table both tell you to run
`jq '... select(.value.name == "childJob") ...' helpers/assets/vendor-cisco-ios.json` to get a
live childJob example, but that file has zero `childJob` tasks — it'll silently return `null`.
The real childJob examples live in `vendor-arista-eos.json`, `vendor-netbox.json`,
`itential-platform-configuration-management.json`, and the LCM project file. Worth updating
those jq examples/asset pointers so the next person doesn't get a silent `null` and assume the
lookup command itself is broken.
