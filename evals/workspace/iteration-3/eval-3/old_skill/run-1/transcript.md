# Transcript — Build: childJob (single child) + extract taskStatus via query

## Task restated

Build an Itential Platform workflow where:
1. A `childJob` task runs a **single** child workflow (not a loop).
2. The parent passes its own `ticketId` and `deviceName` job variables to the child.
3. After the child completes, a `query` task extracts the child's `taskStatus` from the childJob's output.

This is a "build" request, so per the `builder-agent` skill's routing (`SKILL.md` frontmatter: "create the workflows", "build everything per the design") this is squarely Builder Agent territory, specifically **Guide 4: Build a childJob (parent calls child workflow), Mode A: Single child**.

## Skill sections consulted

Read `/tmp/eval-old-skill/builder-agent/SKILL.md` in full (2314 lines) before doing anything else, per the harness instructions. Key sections used:

- **Workspace Contract** (lines 45–107) — defines the required pre-existing files (`tasks.json`, `apps.json`, `adapters.json`, `.auth.json`, `.env`, `solution-design.md`, `use-case-memory.md`, etc.) that a real build session must have before the builder touches anything.
- **Guide 1: Build a workflow end-to-end**, especially the "STOP — read real asset projects before writing task JSON" block (lines 163–193) and the Step 4 mapping rules.
- **Guide 4: Build a childJob** (lines 506–660) — Mode A single-child pattern, the `{"task","value"}` variable-passing rules, the "extracting single child output" query example, and the childJob checklist.
- **Utility Tasks → query** (lines 1279–1300) and **→ childJob** (lines 1417–1471) for the exact incoming/outgoing field contracts.
- **Transitions** (lines 1190–1223) and **nodeLocation Spacing Convention** (lines 990–1029) for wiring and canvas layout.
- **$var Resolution Rules** (lines 1237–1271), specifically the `{"task","value"}` vs `{"task","variable"}` distinction and the `incomingRefs` cache warnings.
- **Gotchas** (lines 2142–2209), items 15, 17, 18 (childJob actor/task/variables rules) and item 9 (hex task IDs).
- **Helper Templates** table (lines 2213–2313) — used `helpers/create/create-workflow.json` as the base POST-body scaffold, and the `helpers/assets/` jq commands to pull real, wired examples.

## Real asset verification (per the skill's mandatory "STOP" instruction)

The skill is explicit that task JSON must be extracted from real `helpers/assets/*.json` exports, not written from memory. I ran the skill's own jq commands against the actual repo at `/Users/ankitrbhansali/builderskills/builder-skills/helpers/assets/`.

**Finding — the skill's own example command is stale/wrong.** Guide 4 and the Helper Templates section both tell the builder to pull the childJob example from `vendor-cisco-ios.json`:
```bash
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "childJob")] | first | .value' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/vendor-cisco-ios.json
```
Running this against the real file returns `null` — **`vendor-cisco-ios.json` contains zero `childJob` tasks** in any workflow (verified: `IOS Upgrade`, `Port Turn Up`, `Run Compliance`, `Create & Update Inventory from NetBox`, `Clear & Delete Inventory` — none use childJob). I scanned all asset files for actual childJob usage:

```
itential-platform-configuration-management.json: 2
vendor-arista-eos.json: 14
vendor-netbox.json: 1
vendor-cisco-ios.json: 0   <- skill points here, but it's empty
```

I pulled the real, wired childJob example from `vendor-arista-eos.json` (workflow "Port Turn Up", task `8878`, summary "Post Check") instead:

```json
{
  "name": "childJob",
  "canvasName": "childJob",
  "location": "Application",
  "locationType": null,
  "app": "WorkFlowEngine",
  "type": "operation",
  "displayName": "WorkFlowEngine",
  "variables": {
    "incoming": {
      "task": "",
      "workflow": "@66d0da1721161b4df27174d0: Command Template Runner",
      "variables": {
        "templateName": {"task": "static", "value": "@66d0da1721161b4df27174d0: Port Turn Up - Post Checks"},
        "devices": {"task": "cd3a", "value": "deviceArray"},
        "suppressFailureMessage": {"task": "job", "value": "suppressFailureMessage"}
      },
      "data_array": "",
      "transformation": "",
      "loopType": ""
    },
    "outgoing": {"job_details": null}
  },
  "groups": [],
  "actor": "job",
  "nodeLocation": {"x": 1104, "y": 768}
}
```
This confirms Guide 4 Mode A's documented shape exactly: `actor: "job"`, `task: ""`, `{"task","value"}` variable refs, all-empty-string placeholders for unused `data_array`/`transformation`/`loopType`, `outgoing.job_details: null`. I used this as the structural basis for the deliverable.

I also pulled real `query` tasks that read from a childJob's `job_details` (e.g. task `e4f3` in the same "Port Turn Up" workflow: `"obj": "$var.42d2.job_details"`, `"query": "templateResults"`) to confirm the flat-path query convention documented in Guide 4 ("Query uses flat variable names — `taskStatus`, NOT `variables.job.taskStatus`").

I also diffed `helpers/create/create-workflow.json` against the skill's documented Workflow Structure (lines 1038–1116) to confirm the POST-body scaffold (`{"automation": {...}}`, `canvasVersion: 3`, `encodingVersion: 1`, `font_size: 12`) — they match.

## Workspace Contract gap (flagged, not silently bypassed)

The skill's Workspace Contract requires a `{use-case}/` folder with `tasks.json`, `apps.json`, `adapters.json`, `.auth.json`, `.env`, and (for a real build) an approved `solution-design.md`, before the builder does anything. None of that exists in this session — there is no use-case workspace and no live platform.

I did **not** silently bypass this. Reasoning for why I proceeded anyway: both `childJob` and `query` are generic `WorkFlowEngine` **Application** tasks, not adapter tasks — they don't require `apps.json`/`adapters.json` lookups (those are only needed to resolve adapter `app`/`locationType`/`adapter_id`, per Guide 1 Step 2 and the pre-submit checklist). The skill documents `childJob` and `query`'s full field contracts directly in Guide 4 and the Utility Tasks section, and I verified those contracts against real, production-wired examples in the repo's asset files. So this specific build doesn't actually depend on the missing discovery files. Had this task involved an adapter task (ServiceNow, NetBox, a CLI push, etc.), I would have stopped and surfaced the missing workspace as an upstream failure per the skill's explicit instruction ("If `tasks.json`, `apps.json`, or `adapters.json` is missing, stop and tell the user").

## Design decisions

- **Mode A, not Mode B.** The task says "runs a single child workflow" — that's Guide 4 Mode A (`loopType: ""`, `variables: {...}`), not the loop mode (`data_array` + `loopType: "parallel"/"sequential"`).
- **Variable passing uses `{"task","value"}`, not `$var`.** Per Guide 4 and Gotcha #18, using `$var` strings inside childJob's `variables` block causes an indefinite runtime hang, and using `"variable"` instead of `"value"` causes `undefined.indexOf()` at job start (P6.4.0+). Both `ticketId` and `deviceName` are wired as `{"task": "job", "value": "ticketId"}` / `{"task": "job", "value": "deviceName"}` — pulling from the **parent's** job variables, exactly as the task specifies.
- **`workflow` field is a placeholder.** There is no live platform and no named child workflow in the task prompt, so I could not resolve an actual child workflow name/`@projectId:` prefix. I set `"workflow": "REPLACE_WITH_CHILD_WORKFLOW_NAME"` and call this out explicitly below — per the skill's PUT-vs-POST asymmetry note (line 1130-1134), if this workflow ends up living inside a project, the child's `workflow` field must include the `@{projectId}:` prefix once the child's actual project-scoped name is known.
- **Query task uses the flat path `"taskStatus"`**, not `"variables.job.taskStatus"` or similar — matching Guide 4's explicit warning and the extracted output `$var.job.childTaskStatus` so the value is visible in job output and usable by any downstream logic the engineer adds later.
- **No error transition on the `childJob` task itself.** I checked this against the real "Port Turn Up" and "Post Check" childJob tasks in `vendor-arista-eos.json` — neither wires an `error` transition off the childJob task (only `success`). This matches the skill's stated pattern for childJob error handling: the *child* workflow is expected to internally try/catch (task → success → `newVariable(taskStatus="success")`, task → error → `newVariable(taskStatus="error")` → `workflow_end`) so the child job **always completes**, and the *parent* inspects the resulting `taskStatus` via the query task rather than relying on a childJob-level error transition. The skill's blanket "every adapter/external task needs an error transition" rule is written with adapter tasks in mind (Gotcha #13) and isn't demonstrated on childJob in any real asset. I did not add one, to match verified real-world usage — but flagged this judgment call for the engineer below.
- **No `evaluation` task added.** The task only asked to *extract* `taskStatus`, not branch on it. The skill's "Error Handling: Try-Catch" pattern (parent side) suggests chaining `childJob → query → evaluation` to act on the status, but that's an extension beyond what was asked. I noted it as a natural next step rather than building it in, to avoid speculative scope creep.
- **Canvas layout** follows the skill's own worked example in the nodeLocation Spacing Convention section almost verbatim (single-thread childJob-then-query sequence, no fork): `workflow_start` (600,204) → `childJob` (600,312) → `query` (600,420) → `workflow_end` (600,528), constant-x spine, 108px y-deltas.
- **Task IDs** `a1a1` and `b2b2` are hex-only (`[0-9a-f]{1,4}`), verified with a regex check.

## Deliverable — full workflow JSON

Written to: `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-3/old_skill/run-1/outputs/run-child-workflow-extract-status.json`

```json
{
  "automation": {
    "name": "Run Child Workflow and Extract Status",
    "description": "Parent workflow that runs a single child workflow via childJob, passing the parent's ticketId and deviceName, then extracts the child's taskStatus with a query task.",
    "type": "automation",
    "canvasVersion": 3,
    "encodingVersion": 1,
    "font_size": 12,
    "tasks": {
      "workflow_start": {
        "name": "workflow_start",
        "groups": [],
        "nodeLocation": { "x": 600, "y": 204 }
      },
      "a1a1": {
        "name": "childJob",
        "canvasName": "childJob",
        "summary": "Run Child Workflow",
        "description": "Runs the child workflow a single time, passing the parent's ticketId and deviceName as the child's input variables.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "task": "",
            "workflow": "REPLACE_WITH_CHILD_WORKFLOW_NAME",
            "variables": {
              "ticketId": { "task": "job", "value": "ticketId" },
              "deviceName": { "task": "job", "value": "deviceName" }
            },
            "data_array": "",
            "transformation": "",
            "loopType": ""
          },
          "outgoing": {
            "job_details": null
          }
        },
        "groups": [],
        "actor": "job",
        "scheduled": false,
        "nodeLocation": { "x": 600, "y": 312 }
      },
      "b2b2": {
        "name": "query",
        "canvasName": "query",
        "summary": "Extract Child Task Status",
        "description": "Extracts taskStatus from the completed child job's job_details so the parent can act on the child's outcome.",
        "location": "Application",
        "locationType": null,
        "app": "WorkFlowEngine",
        "type": "operation",
        "displayName": "WorkFlowEngine",
        "variables": {
          "incoming": {
            "pass_on_null": false,
            "query": "taskStatus",
            "obj": "$var.a1a1.job_details"
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
        "ticketId": {
          "title": "ticketId",
          "type": "string",
          "description": "Parent job's ticket identifier, passed through to the child workflow."
        },
        "deviceName": {
          "title": "deviceName",
          "type": "string",
          "description": "Parent job's target device name, passed through to the child workflow."
        }
      },
      "required": ["ticketId", "deviceName"]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "childTaskStatus": {
          "title": "childTaskStatus",
          "type": "string",
          "description": "taskStatus value extracted from the child job's job_details after it completes."
        }
      }
    }
  }
}
```

## Validation performed

- `jq empty` on the file — valid JSON.
- Regex check on task IDs `a1a1`, `b2b2` against `[0-9a-f]{1,4}` — both pass.
- Manually walked the Guide 1 "Pre-submit checklist" (line 351+): hex task IDs ✓; `actor: "job"` on childJob, `"Pronghorn"` on query ✓; childJob variables use `{"task","value"}` not `$var` ✓; `variables` is populated (not `{}`) because this is single mode, not loop mode ✓; `data_array`/`transformation`/`loopType` present as empty strings even though unused ✓; `job_details` outgoing is `null` ✓; `workflow_end` transition is empty `{}` ✓; query uses flat path `"taskStatus"` ✓; no `$var` inside nested objects (the only nested object is childJob's `variables` map, which uses the childJob-specific `{"task","value"}` ref objects, not raw `$var` strings — this is the documented exception) ✓.
- The skill also documents `POST /automation-studio/workflows/validate` as a pre-flight check to run before create/update — noted below as the actual next step since there's no live platform in this session to call it against.

## Final answer / recommendation to the engineer

Here's the workflow: `outputs/run-child-workflow-extract-status.json`, ready to POST to `/automation-studio/automations` (wrapped in `{"automation": {...}}` already) once you're pointed at a real platform. It's a 3-task parent: `workflow_start → childJob (a1a1) → query (b2b2) → workflow_end`, all on a single vertical spine (no forks needed for this shape).

A few things you need to fill in / decide before this is truly ready:

1. **`a1a1.variables.incoming.workflow` is a placeholder** (`"REPLACE_WITH_CHILD_WORKFLOW_NAME"`). I don't have a real platform or a named child workflow to resolve here. Swap in the child's actual name — and if the child lives inside a project, it needs the `@{projectId}: ` prefix (e.g. `"@66d0da17...: My Child Workflow"`), per the skill's project-scoped naming rule.
2. **This assumes `ticketId` and `deviceName` already exist as job variables on the parent** at the point this childJob task runs — they're pulled via `{"task": "job", "value": "ticketId"}` / `{"task": "job", "value": "deviceName"}`. If they're not top-level parent inputs but come from an earlier task's output instead, change `"task": "job"` to that task's ID and `"value"` to its output variable name (same `{"task","value"}` shape works for either).
3. **The child workflow must accept `ticketId` and `deviceName` in its `inputSchema.required`**, and must set a `taskStatus` job variable before it reaches `workflow_end` (success or error path — both should land on a `newVariable` writing `taskStatus`) — otherwise the query in the parent will return `null` and, since `pass_on_null: false`, take the (currently unwired) `failure` transition, which isn't connected to anything and will strand the job. I left this unwired deliberately since the task only asked for extraction, not branching — but flagging it now: if you want this production-safe, you'll want either (a) an `evaluation` task after the query to branch on `childTaskStatus`, or (b) at minimum a `failure` transition off the query routing to a fallback `newVariable`/`workflow_end` so a missing/null status doesn't hang the job silently.
4. **No error transition on the `childJob` task itself** — this matches every real childJob usage I found in the actual asset files (`vendor-arista-eos.json`), which rely on the child's internal try-catch instead. If your child workflow *doesn't* guarantee it always completes (e.g., it can genuinely error out of the platform's control, not just business-logic-fail), you'd want to reconsider that model.
5. **Before you actually create this on a live platform:** run `POST /automation-studio/workflows/validate` against the body first (the skill mandates this pre-flight check) — I couldn't run it here since there's no platform connected in this session.

One thing I noticed while building this that's worth fixing in the skill itself: Guide 4 and the Helper Templates table both tell you to extract the childJob example from `helpers/assets/vendor-cisco-ios.json`, but that file has zero childJob tasks in any of its workflows — the jq command silently returns `null`. The real childJob examples live in `vendor-arista-eos.json` (14 instances) and `itential-platform-configuration-management.json` (2 instances). I used `vendor-arista-eos.json` instead and it worked fine, but the skill's own pointer is stale and would send someone chasing a dead end if they didn't think to check the `null` result.
