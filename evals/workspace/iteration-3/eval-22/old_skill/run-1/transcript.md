# Transcript — Add a ViewData Approval Manual Task

## Task as given

> Add a ViewData manual task to my workflow that shows an approval prompt to the operator
> with a header, a message, and Approve/Reject buttons.

No live Itential Platform is connected in this session, and no specific workflow JSON was
supplied by the engineer. Per skill convention (Guide 3: "Add a task to an existing
workflow"), I produced (a) a standalone, drop-in `ViewData` task definition the engineer can
merge into their real workflow's `tasks` map, and (b) a complete, minimal, valid workflow
JSON that shows the task fully wired end-to-end (transitions, fork, convergence), so the
wiring pattern can be lifted directly regardless of what the engineer's existing workflow
looks like.

## Skill sections consulted

Read `/tmp/eval-old-skill/builder-agent/SKILL.md` in full (2314 lines) before doing anything else, per
the harness instructions. Relevant sections used:

1. **"STOP. Before writing a single line of task JSON — run these commands."** (Guide 1
   preamble) — mandates reading real, production-tested asset projects under
   `helpers/assets/` before guessing task structure from memory.
2. **`### Task Access Control (groups)`** — documents `groups` (plural, GBAC array of group
   `_id`s) vs. `group` (singular, canvas display category) and shows a `ViewData` skeleton.
3. **`### Manual Tasks (Human-in-the-Loop)`** — gives the documented `ViewData` and
   `ViewHTML` JSON shapes and three "rules" that (per the skill text) cause `"Manual Tasks
   require 'view' key"` draft errors if violated:
   1. `view` is top-level (sibling of `name`/`type`/`app`), not inside `variables`.
   2. `variables` has **only** `incoming`/`outgoing` — "no `error` or `decorators` (those are
      for automatic tasks only)".
   3. `displayName` must be `"Tools"`, and there is **no `actor` field** on manual tasks.
   Also documents the `ViewHTML` "required fields" claim: `view`, `taskVersion: 2`, and
   `hostApp` are "all required."
4. **`### autoApprove Pattern`** and **`### Revert Transitions (Retry Loops)`** — patterns
   for conditionally skipping approval and for retry loops off a `ViewData` reject branch
   (not used here since the ask was a plain approval prompt, but read for completeness).
5. **`### Transitions`** — the "JSON duplicate key" rule: if two branches off the same task
   both need to land on `workflow_end`, you cannot write `workflow_end` twice as a sibling
   key, so an intermediate task (e.g. `newVariable`) is required for one of the branches.
6. **`### nodeLocation Spacing Convention`** — vertical layout by default: spine at a
   constant `x`, sequential tasks `y += 108`, fork branches offset `±264` from the spine,
   convergence tasks return to the spine `x`.
7. **`## Task Discovery` → "Look up task wiring in asset projects first"** — before calling
   any schema API, grep `helpers/assets/` for the task name and extract the wired example.
8. **Pre-submit checklist (Guide 1, Step 9)** — hex-only task IDs, error transitions on
   adapter tasks (not applicable to manual tasks), canvas layout rules.

## Verifying against the real asset files (as instructed — did not build from memory)

The skill explicitly points at `vendor-cisco-ios.json` for a "live ViewData example." I
pulled it directly from the real repo:

```bash
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "ViewData")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json
# -> null
```

**Finding:** `vendor-cisco-ios.json` contains no `ViewData` task at all — the skill's
pointer is stale/wrong for that specific claim. I then searched all real asset files for
actual `ViewData` usage:

```bash
grep -rl '"ViewData"' ${CLAUDE_PLUGIN_ROOT}/helpers/assets/
# vendor-netbox.json, vendor-arista-eos.json,
# itential-platform-configuration-management.json, vendor-servicenow.json,
# vendor-infoblox-nios-ddi.json
```

I extracted several real, production `ViewData` tasks (Arista "Port Turn Up", "Push
Configuration to Device - IAG", ServiceNow error dialog) to see the actual shape used in
production imports, e.g. (from `vendor-arista-eos.json`, task `cba5` in the "Push
Configuration to Device - IAG" workflow — exactly the "config push with dry-run approval"
pattern the skill's own Guide 1 preamble references):

```json
{
  "name": "ViewData",
  "canvasName": "ViewData",
  "summary": "View Configuration",
  "description": "Show the proposed configuration and decision options",
  "location": "Application",
  "app": "WorkFlowEngine",
  "displayName": "Tools",
  "type": "manual",
  "variables": {
    "incoming": {
      "header": "View Configuration",
      "message": "$var.582e.deviceConfigurationPushMessage",
      "body": "$var.582e.renderedTemplate",
      "variables": {},
      "btn_success": "Provision",
      "btn_failure": "End Job"
    },
    "outgoing": {},
    "error": "",
    "decorators": []
  },
  "view": "/workflow_engine/task/ViewData",
  "groups": [],
  "scheduled": false,
  "nodeLocation": { "x": 312, "y": 900 }
}
```

**Discrepancy vs. the skill's prose I'm flagging to the engineer:** every real, production
`ViewData` task I found (Arista, ServiceNow, Infoblox, config-management asset files) *does*
include `"error": ""` and `"decorators": []` inside `variables`, and *none* of them include
`taskVersion` or `hostApp`. This directly contradicts the skill's stated rule #2 ("no `error`
or `decorators`") and its "required fields" claim for `taskVersion`/`hostApp` (that claim
appears only next to the `ViewHTML` example, and even the repo's own real `ViewHTML` task in
`vendor-cisco-ios.json` omits both fields too). Since the skill's own top instruction says to
trust the real asset files over invented/remembered structure ("do not guess task structure
from memory... these are real, production-tested imports"), I built the deliverable to match
the verified real-world shape (`error`/`decorators` included, no `taskVersion`/`hostApp`),
not the contradicting inline prose. I did keep the three genuinely-load-bearing rules that
*are* consistent across every real example: `view` is top-level, `displayName: "Tools"`, and
no `actor` field.

I also confirmed the transition states used on `ViewData` branches by inspecting the real
`transitions` blocks around those tasks (e.g. Arista's `cba5` → `ca47`/`08e4` uses
`state: "success"` for the "Provision" button and `state: "failure"` for the "End Job"
button) — confirming `ViewData`'s Approve/Reject buttons map to transition `state: "success"`
/ `state: "failure"` respectively, not `error`.

I pulled the real `newVariable` schema from `vendor-arista-eos.json` the same way, to build
a schema-accurate error-avoidance sink for the two branches (since routing both `success` and
`failure` directly to `workflow_end` from the same task is illegal — duplicate JSON key —
per the skill's documented "JSON duplicate key problem").

## Task ID and layout choices

- Task ID for the `ViewData` task: `b1a2` (hex-only, `[0-9a-f]{1,4}`, per skill rule). This is
  a placeholder — the engineer must pick an ID that doesn't collide with their real
  workflow's existing task IDs.
- Canvas layout in the full example follows the documented vertical convention: spine
  `x = 600`, `y += 108` between sequential tasks, fork branches at `spine ± 264` (`336` /
  `864`), convergence (`workflow_end`) back on the spine.

## Artifacts produced

**1. `outputs/viewdata-approval-task.json`** — the standalone, drop-in `ViewData` task
object (key `b1a2`) with header, message, and Approve/Reject buttons, ready to be merged
into the engineer's actual `tasks` map:

```json
{
  "b1a2": {
    "name": "ViewData",
    "canvasName": "ViewData",
    "summary": "Operator Approval",
    "description": "Prompts the operator to review and approve or reject before the workflow continues.",
    "location": "Application",
    "app": "WorkFlowEngine",
    "displayName": "Tools",
    "type": "manual",
    "view": "/workflow_engine/task/ViewData",
    "variables": {
      "incoming": {
        "header": "Approval Required",
        "message": "Please review the request below and approve or reject.",
        "body": "",
        "variables": {},
        "btn_success": "Approve",
        "btn_failure": "Reject"
      },
      "outgoing": {},
      "error": "",
      "decorators": []
    },
    "groups": [],
    "scheduled": false,
    "nodeLocation": { "x": 600, "y": 528 }
  }
}
```

**2. `outputs/workflow-example-with-approval.json`** — a complete, valid, minimal workflow
(`workflow_start → ViewData → fork(success/failure) → newVariable sinks → workflow_end`)
that demonstrates the exact transition wiring, including the duplicate-key workaround:

```json
{
  "automation": {
    "name": "Operator Approval Example",
    "description": "Demonstrates a ViewData manual task presenting an approval prompt with header, message, and Approve/Reject buttons.",
    "type": "automation",
    "canvasVersion": 3,
    "encodingVersion": 1,
    "font_size": 12,
    "tasks": {
      "workflow_start": { "name": "workflow_start", "groups": [], "nodeLocation": { "x": 600, "y": 200 } },
      "b1a2": {
        "name": "ViewData",
        "canvasName": "ViewData",
        "summary": "Operator Approval",
        "description": "Prompts the operator to review and approve or reject before the workflow continues.",
        "location": "Application",
        "app": "WorkFlowEngine",
        "displayName": "Tools",
        "type": "manual",
        "view": "/workflow_engine/task/ViewData",
        "variables": {
          "incoming": {
            "header": "Approval Required",
            "message": "Please review the request below and approve or reject.",
            "body": "",
            "variables": {},
            "btn_success": "Approve",
            "btn_failure": "Reject"
          },
          "outgoing": {},
          "error": "",
          "decorators": []
        },
        "groups": [],
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 308 }
      },
      "c1a3": {
        "name": "newVariable",
        "canvasName": "newVariable",
        "summary": "Mark Approved",
        "description": "Records that the operator approved the request.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": { "name": "approvalStatus", "value": "approved" },
          "outgoing": { "value": "$var.job.approvalStatus" },
          "error": "",
          "decorators": []
        },
        "actor": "Pronghorn",
        "groups": [],
        "scheduled": false,
        "nodeLocation": { "x": 336, "y": 416 }
      },
      "d1a4": {
        "name": "newVariable",
        "canvasName": "newVariable",
        "summary": "Mark Rejected",
        "description": "Records that the operator rejected the request.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": { "name": "approvalStatus", "value": "rejected" },
          "outgoing": { "value": "$var.job.approvalStatus" },
          "error": "",
          "decorators": []
        },
        "actor": "Pronghorn",
        "groups": [],
        "scheduled": false,
        "nodeLocation": { "x": 864, "y": 416 }
      },
      "workflow_end": { "name": "workflow_end", "groups": [], "nodeLocation": { "x": 600, "y": 524 } }
    },
    "transitions": {
      "workflow_start": { "b1a2": { "type": "standard", "state": "success" } },
      "b1a2": {
        "c1a3": { "type": "standard", "state": "success" },
        "d1a4": { "type": "standard", "state": "failure" }
      },
      "c1a3": { "workflow_end": { "type": "standard", "state": "success" } },
      "d1a4": { "workflow_end": { "type": "standard", "state": "success" } },
      "workflow_end": {}
    },
    "groups": [],
    "inputSchema": { "type": "object", "properties": {}, "required": [] },
    "outputSchema": {
      "type": "object",
      "properties": { "approvalStatus": { "title": "approvalStatus", "type": "string" } }
    }
  }
}
```

## Final answer to the engineer

Here's the `ViewData` approval task, verified against real production imports (not
guessed from memory):

```json
{
  "b1a2": {
    "name": "ViewData",
    "canvasName": "ViewData",
    "summary": "Operator Approval",
    "description": "Prompts the operator to review and approve or reject before the workflow continues.",
    "location": "Application",
    "app": "WorkFlowEngine",
    "displayName": "Tools",
    "type": "manual",
    "view": "/workflow_engine/task/ViewData",
    "variables": {
      "incoming": {
        "header": "Approval Required",
        "message": "Please review the request below and approve or reject.",
        "body": "",
        "variables": {},
        "btn_success": "Approve",
        "btn_failure": "Reject"
      },
      "outgoing": {},
      "error": "",
      "decorators": []
    },
    "groups": [],
    "scheduled": false,
    "nodeLocation": { "x": 600, "y": 528 }
  }
}
```

To use it:

1. Rename the key `b1a2` to any unused hex ID (`[0-9a-f]{1,4}`) in your workflow's `tasks`
   map, and merge this object in.
2. Point whatever task currently precedes this step at it with a `success` transition.
3. `ViewData`'s two buttons map to transition states, not `error`: the **Approve** button
   fires `state: "success"`, **Reject** fires `state: "failure"`. Wire both out of this task
   ID accordingly.
4. If both branches need to reach `workflow_end`, you can't write `workflow_end` as a
   sibling key twice under the same task — route at least one branch through an
   intermediate task first (e.g. a `newVariable` that records `approvalStatus`), then have
   that land on `workflow_end`. I included a full worked example of this in
   `workflow-example-with-approval.json`.
5. If you want the operator to see the actual data/config under review (not just the header
   and message), wire `body` to the job variable holding that payload, e.g.
   `"body": "$var.job.dataToReview"` — I left it empty (`""`) since you only asked for
   header + message + buttons.
6. If this task should be restricted to specific IAP groups in the Job Inbox, populate the
   `groups` array with group `_id`s from `GET /authorization/groups` — left as `[]`
   (unrestricted) by default.

One thing worth knowing, in case you hit a validation surprise: the skill I used to build
this says a `ViewData`/`ViewHTML` task's `variables` block should contain *only*
`incoming`/`outgoing` (no `error`/`decorators`), and that `ViewHTML` requires `taskVersion`
and `hostApp`. When I checked that against the real, already-imported production workflows
in this repo's asset library (Arista, ServiceNow, Infoblox, NetBox, Cisco IOS), every real
`ViewData` task actually *does* carry `error`/`decorators`, and none of the real `ViewData`
or `ViewHTML` tasks carry `taskVersion` or `hostApp`. I built your task and example to match
what's actually been imported and works on a live platform (verified pattern from real
files), not the inline prose — but flagging it so you're not surprised if you'd read that
section of the skill yourself. Worth a doc fix in the skill.

## Files written

- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-22/old_skill/run-1/outputs/viewdata-approval-task.json`
- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-22/old_skill/run-1/outputs/workflow-example-with-approval.json`
- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-22/old_skill/run-1/transcript.md` (this file)
