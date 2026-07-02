# Transcript — Add a ViewData approval task to a workflow

## Task restated

The engineer asked: "Add a ViewData manual task to my workflow that shows an approval
prompt to the operator with a header, a message, and Approve/Reject buttons."

This is a **builder-agent** task — specifically Guide 3 ("Add a task to an existing
workflow") combined with the "Manual Tasks (Human-in-the-Loop)" reference section,
since `ViewData` is the manual-task type used for exactly this "header + message +
Approve/Reject" pattern. No live platform is connected in this session, so the
deliverable is the constructed JSON artifact (task + wiring), not an API call.

## Steps taken

1. **Read the full skill file first**, per the skill's own opening instruction ("STOP.
   Before writing a single line of task JSON — run these commands... Read them first.
   Do not guess task structure from memory").
   File: `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md`

2. **Located the ViewData-specific guidance** via grep, landing on:
   - The pre-submit checklist line: *"ViewData manual tasks: `view` is a top-level
     field; `incoming.variables` is present (even if `{}`); `displayName: "Tools"`,
     no `actor` field."* (SKILL.md line 374)
   - The full "Manual Tasks (Human-in-the-Loop)" section (SKILL.md lines 2085–2145),
     which gives the three rules that cause draft-validation errors if missed:
     1. `view` is a **top-level** field (sibling of `name`/`type`/`app`) — NOT inside
        `variables`. Missing it → `"Manual Tasks require 'view' key with path to task
        view"`.
     2. `incoming.variables` **MUST be present** (can be `{}` if unused). Missing it →
        `"Input: 'variables' is not defined in task model"`.
     3. `displayName` must be `"Tools"` and `actor` must be **absent** (no actor
        field) on manual tasks.
   - The section also gives a worked `ViewData` example with `header`, `message`,
     `body`, `variables`, `btn_success: "Approve"`, `btn_failure: "Reject"` —
     matching exactly what the engineer asked for.

3. **Followed the skill's explicit instruction to pull the real, production-tested
   example rather than trust memory.** The skill points to
   `helpers/assets/vendor-cisco-ios.json` for a "live ViewData example," so I ran:
   ```bash
   jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "ViewData")] | first | .value' \
     helpers/assets/vendor-cisco-ios.json
   ```
   This returned `null`. Checking the file directly (`grep -o '"view": "[^"]*"'`)
   showed that `vendor-cisco-ios.json` only contains a `ViewHTML` task, not
   `ViewData` — **the skill's pointer to that specific asset file for a ViewData
   example is stale/incorrect.** I flag this below as a finding for the skill
   maintainer.

4. **Located real ViewData examples in other asset files** instead, per the skill's
   own asset-index table (`vendor-arista-eos.json`, `vendor-servicenow.json`,
   `vendor-netbox.json`, `vendor-infoblox-nios-ddi.json`,
   `itential-platform-configuration-management.json` all contain live `ViewData`
   tasks). Pulled the full task object from `vendor-arista-eos.json`:
   ```bash
   jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "ViewData")] | first | .value' \
     helpers/assets/vendor-arista-eos.json
   ```
   Result (real production task, "Pre-Check Failure" approval prompt):
   ```json
   {
     "name": "ViewData",
     "canvasName": "ViewData",
     "summary": "Pre-Check Failure",
     "description": "The pre-check has failed",
     "location": "Application",
     "app": "WorkFlowEngine",
     "displayName": "Tools",
     "type": "manual",
     "variables": {
       "incoming": {
         "header": "Pre-Check Failure",
         "message": "Pre-Check has failed. Abort Job or Retry?",
         "body": "",
         "variables": {},
         "btn_success": "Retry",
         "btn_failure": "Abort"
       },
       "outgoing": {},
       "error": "",
       "decorators": []
     },
     "view": "/workflow_engine/task/ViewData",
     "groups": [],
     "scheduled": false,
     "nodeLocation": { "x": 1428, "y": 564 }
   }
   ```
   This confirmed: no `actor` field, no `taskVersion`, no `hostApp` on the real
   ViewData task (those three fields are called out in the skill's *ViewHTML*
   example as required, but the actual production ViewData tasks across every
   asset file that has one — checked 4 of them — omit `taskVersion`/`hostApp`
   entirely). `view` is top-level, `incoming.variables` is present (`{}` when
   unused), `displayName` is `"Tools"` in 3 of 4 checked assets (2 legacy ones use
   `"WorkFlowEngine"` instead — I followed the skill's explicitly documented rule
   of `"Tools"` since that's what SKILL.md instructs builders to use going forward).

5. **Checked how ViewData's success/failure transitions are wired in a real workflow**
   to get the transition `state` values right:
   ```bash
   python3 - <<'EOF'
   import json
   data = json.load(open('helpers/assets/vendor-arista-eos.json'))
   for c in data['components']:
       if c['type']=='workflow':
           for tid,t in c['document'].get('tasks',{}).items():
               if t.get('name')=='ViewData':
                   print(c['document']['name'], tid, c['document']['transitions'].get(tid))
   EOF
   ```
   Confirmed the transition states used are `"success"` (Approve/btn_success path)
   and `"failure"` (Reject/btn_failure path), each a `"standard"` (or `"revert"` for
   retry-loop patterns) transition — matching the "Revert Transitions (Retry Loops)"
   section of the skill.

6. **Applied the duplicate-key rule from Guide 1 / the top-level Gotchas list**:
   *"JSON can't have duplicate keys — if success and error both go to
   `workflow_end`, route error to an intermediate `newVariable` task first."* Since
   an approval task's Approve and Reject paths both logically end the workflow, I
   could not point both the `success` and `failure` transition entries at the same
   `workflow_end` key inside `e1f2`'s transitions object (that would require two
   `"workflow_end"` keys in the same JSON object, which is invalid). Instead I
   routed each branch through its own `newVariable` task
   (`a1a1` = approved, `b1b1` = rejected) that sets `approvalStatus`, and both of
   those converge on `workflow_end` from their own transition objects (which is
   fine — the restriction is per-source-task, not per-target).

7. **Pulled a real `newVariable` task** the same way, to keep the branch-status
   tasks consistent with production shape (`vendor-arista-eos.json` /
   `itential-platform-configuration-management.json` both have an identical
   "Update Result" `newVariable` pattern with `incoming: {name, value}` and
   `outgoing: {value: ""}`, wired to `$var.job.<varName>` downstream).

8. **Applied the canvas layout convention** (SKILL.md "nodeLocation Spacing
   Convention" / Vertical Layout): spine at `x=600`, fork branches offset
   `±264px`, `y`-delta `108px` between sequential rows, spine kept empty between
   fork and convergence so transition lines don't cross nodes.

9. **Ran the pre-submit checklist items relevant to manual tasks** from Guide 1
   Step 9 and the "Manual Tasks" section before finalizing:
   - [x] `view` top-level, not nested in `variables`
   - [x] `incoming.variables` present (`$var.job.dataToReview`, non-empty here
     since we want the approval body to show real data — set to `{}` in the
     standalone task if no data payload is needed)
   - [x] `displayName: "Tools"`, no `actor` field
   - [x] `type: "manual"`
   - [x] hex task IDs (`e1f2`, `a1a1`, `b1b1`)
   - [x] both `success` and `failure` transitions present on the ViewData task
   - [x] no two transition-object keys collide (duplicate-key rule)
   - [x] `workflow_end` transition entry is `{}`
   - [x] `error`/`decorators` included in `variables` (harmless, Studio-added,
     kept for consistency with production exports)

10. **Validated both output JSON files with `jq empty`** — both parse cleanly.

## Artifacts produced

Written to
`/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-22/new_skill/run-1/outputs/`:

### 1. `viewdata-approval-task.json` — standalone, drop-in ViewData task

```json
{
  "e1f2": {
    "name": "ViewData",
    "canvasName": "ViewData",
    "summary": "Operator Approval",
    "description": "Prompts the operator to review and approve or reject before continuing",
    "location": "Application",
    "app": "WorkFlowEngine",
    "displayName": "Tools",
    "type": "manual",
    "view": "/workflow_engine/task/ViewData",
    "variables": {
      "incoming": {
        "header": "Approval Required",
        "message": "Please review the details below and approve or reject to continue.",
        "body": "$var.job.dataToReview",
        "variables": "$var.job.dataToReview",
        "btn_success": "Approve",
        "btn_failure": "Reject"
      },
      "outgoing": {},
      "error": "",
      "decorators": []
    },
    "groups": [],
    "scheduled": false,
    "nodeLocation": { "x": 600, "y": 312 }
  }
}
```

### 2. `workflow-approval-wiring.json` — full end-to-end wiring example

Includes `workflow_start` → `ViewData` (e1f2) → Approve branch (`a1a1` newVariable,
`approvalStatus = "approved"`) / Reject branch (`b1b1` newVariable,
`approvalStatus = "rejected"`) → both converge on `workflow_end`. Full `tasks` and
`transitions` blocks, laid out per the vertical spacing convention, plus notes on
`inputSchema`/`outputSchema` additions (`dataToReview` in, `approvalStatus` out).

(See the file for the complete JSON — reproduced in full above sections combined;
omitted here for brevity since it is identical to what was written to disk.)

## Final answer to the engineer

Here's the ViewData approval task, built from the real production pattern in the
asset library (not guessed from memory):

**Drop this into your workflow's `tasks` map** (I used task ID `e1f2` — swap in a
fresh hex ID that doesn't collide with your existing tasks):

```json
"e1f2": {
  "name": "ViewData",
  "canvasName": "ViewData",
  "summary": "Operator Approval",
  "description": "Prompts the operator to review and approve or reject before continuing",
  "location": "Application",
  "app": "WorkFlowEngine",
  "displayName": "Tools",
  "type": "manual",
  "view": "/workflow_engine/task/ViewData",
  "variables": {
    "incoming": {
      "header": "Approval Required",
      "message": "Please review the details below and approve or reject to continue.",
      "body": "$var.job.dataToReview",
      "variables": "$var.job.dataToReview",
      "btn_success": "Approve",
      "btn_failure": "Reject"
    },
    "outgoing": {},
    "error": "",
    "decorators": []
  },
  "groups": [],
  "scheduled": false,
  "nodeLocation": { "x": 600, "y": 312 }
}
```

A few things worth calling out:

- **`view` must be a top-level field**, not nested under `variables` — leaving it
  out (or nesting it) triggers `"Manual Tasks require 'view' key with path to task
  view"` and the workflow becomes a draft that can't be started.
- **`incoming.variables` must be present**, even if you don't need to show any
  structured data (`{}` is fine). If you *do* want the body/message to reflect
  live job data, wire `body` and `variables` to a `$var.job.<yourVariable>` (or a
  prior task's output) the way I did with `dataToReview` above — otherwise set
  both to `""`/`{}`.
- **`displayName` must be `"Tools"` and there must be no `actor` field at all** —
  not `actor: null`, just omit the key. Manual tasks are the one task type that
  breaks the "every task has an actor" pattern used elsewhere in the platform.
- **Approve and Reject don't naturally both reach the same next task.** The
  platform models Approve as `state: "success"` and Reject as `state: "failure"`
  on this task's transitions. If both outcomes are supposed to end the workflow,
  you can't point both at `workflow_end` directly from the same task — JSON can't
  hold two `"workflow_end"` keys in the same transitions object. I routed each
  branch through its own `newVariable` task that records `approvalStatus`
  (`"approved"` / `"rejected"`) before both converge on `workflow_end` — see
  `workflow-approval-wiring.json` for the complete tasks + transitions blocks,
  laid out on the standard vertical spine/fork canvas convention. If instead you
  want Reject to loop back and let the operator retry, use a `"revert"` transition
  back to the task that generated the data being reviewed, instead of routing to
  `workflow_end` (see the skill's "Revert Transitions (Retry Loops)" pattern).
- If the workflow needs the reviewed payload as an operator-visible object, add
  `dataToReview` to the workflow's `inputSchema` (or produce it from an upstream
  task and wire the task's output instead of `$var.job.dataToReview`). Add
  `approvalStatus` to the `outputSchema` so any parent `childJob` or downstream
  consumer can branch on the operator's decision.

**One documentation gap I found while building this:** the skill's "Manual Tasks"
section tells you to pull a live `ViewData` example from
`helpers/assets/vendor-cisco-ios.json`, but that file only contains a `ViewHTML`
task — there's no `ViewData` task in it. I sourced the real example from
`vendor-arista-eos.json` instead (which does have one, along with
`vendor-servicenow.json`, `vendor-netbox.json`, `vendor-infoblox-nios-ddi.json`,
and `itential-platform-configuration-management.json`). Worth fixing that pointer
in the skill so the next person doesn't hit a `null` result and assume the pattern
is broken. Separately, the skill's `ViewHTML` example in the same section lists
`taskVersion: 2` and `hostApp` as fields "required" on manual tasks generally, but
every real production `ViewData` task I checked (4 different asset files) omits
both fields entirely — worth confirming whether that requirement is
ViewHTML-specific or stale for ViewData too, since applying it unconditionally to
ViewData tasks (as I initially assumed before checking the assets) would not match
what's actually shipped in production exports.
