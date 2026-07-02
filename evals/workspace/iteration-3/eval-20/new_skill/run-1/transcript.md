# Transcript — childJob loop `taskStatus` null debugging

## Task as given

> My childJob runs a child workflow in a loop over an array of devices (loopType: parallel), and afterward I query `$var.<childJobId>.job_details` with query 'loop' to extract each child's taskStatus. Sometimes downstream logic reports null for taskStatus even though every child completed successfully. What's going on and how do I fix it?

This is a debugging/advice question (Guide 2 territory, but specifically about childJob loop output), not a from-scratch workflow build. Per the run instructions, I still produce a concrete JSON artifact showing the fix, grounded in real task shapes from the repo's asset files rather than invented from memory.

## Steps taken

1. **Read the skill in full** — `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md` (2442 lines, read across two passes: lines 1–1099 then targeted reads of 1490–1640 and 2270–2338, plus a grep pass over `job_details|taskStatus|loop`).

2. **Located the exact documented behavior** in three places in SKILL.md:
   - **Guide 1 pre-submit checklist** (line 367):
     > "If a `query` downstream of a `childJob` returns null despite the child succeeding: check whether `"obj": "$var.<childJobId>.job_details"` is resolving — on some platform versions it is treated as a literal string. Fix: insert a `merge` task between childJob and query using `{"task": "<childJobId>", "variable": "job_details"}` in `data_to_merge`, then point `obj` to `$var.<mergeId>.merged_object` (see Guide 4)"
   - **Guide 4 (Build a childJob), Mode B — Loop section** (lines 653–669): documents exactly the "loop" query pattern the user describes, and the same fallback: "If the query returns null (platform-version-specific `$var` resolution issue), use the same merge+taskRef workaround described above (Mode A) — capture `job_details` via `{"task": "a1a1", "variable": "job_details"}` in merge, then query `$var.m1m1.merged_object`."
   - **childJob checklist** (line 722): restates the same fix as a checklist item.
   - Cross-referenced against the **body reference section on `childJob`** (lines 1508–1562) and the **Gotchas pre-flight list** (`### Utility Tasks`, items 15–18, 22–23) to confirm this is a known, named platform quirk (not a one-off guess) and to make sure I wasn't missing a more specific loop-only variant of the bug.
   - Also checked the **"Building the child workflow" section** (lines 724–735) — this documents a *second*, unrelated failure mode that produces the same symptom (null `taskStatus`): if the child workflow itself never explicitly sets a `taskStatus` job variable on both its success and error exit paths, `job_details.taskStatus` will legitimately be null/missing regardless of how the parent wires its merge/query. I flagged this as a required sanity check before assuming the platform bug is the cause.

3. **Grounded the fix in real, production asset JSON** (per the skill's explicit "STOP — read helper assets first" instruction) rather than inventing task JSON from memory:
   - Pulled a real `merge` task shape from `helpers/assets/vendor-servicenow.json`:
     ```bash
     jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "merge")] | first | .value' helpers/assets/vendor-servicenow.json
     ```
   - Pulled a real `query` task shape from `helpers/assets/itential-platform-configuration-management.json`:
     ```bash
     jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "query")] | first | .value' helpers/assets/itential-platform-configuration-management.json
     ```
   - Checked for a live `childJob` example with `loopType: "parallel"` and a `data_array` populated, across all asset files:
     ```bash
     for f in helpers/assets/*.json; do
       jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "childJob")] | length' "$f"
     done
     ```
     Found `childJob` tasks in `itential-platform-configuration-management.json` (2), `vendor-arista-eos.json` (14), and `vendor-netbox.json` (1) — but every single instance in the repo's current asset library uses `loopType: ""` (single-child mode), none use the parallel loop + `data_array` mode. So the canonical, most-detailed source for the parallel-loop pattern and its null-taskStatus fix is the skill body itself (Guide 4 Mode B), which is written out in full JSON there — not a case where the skill tells me to "look it up in assets and don't guess," since no asset example of that exact mode exists to look up. I used the skill's own documented JSON pattern and combined it with the real merge/query task field shapes pulled from the asset files above, so the field names, `location`/`app`/`displayName` conventions, and structure are grounded in production data even where the specific loop-mode wiring comes from the skill text.

4. **Wrote the JSON artifact** to:
   `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-20/new_skill/run-1/outputs/childjob-loop-taskstatus-fix.json`

   Full contents:

   ```json
   {
     "_comment": "Fix for: query('loop') against $var.<childJobId>.job_details returning null taskStatus values even though every child in the parallel loop completed successfully. Pattern taken from builder-agent SKILL.md Guide 4 (childJob) 'If the query returns null' workaround, grounded against real merge/query task shapes pulled from helpers/assets/vendor-servicenow.json and helpers/assets/itential-platform-configuration-management.json.",

     "tasks": {
       "a1a1": {
         "name": "childJob",
         "canvasName": "childJob",
         "summary": "Run Child Per Device",
         "description": "Fans out one child job per device in the loop, running all children in parallel",
         "location": "Application",
         "locationType": null,
         "app": "WorkFlowEngine",
         "type": "operation",
         "displayName": "WorkFlowEngine",
         "variables": {
           "incoming": {
             "task": "",
             "workflow": "Device Config Child Workflow",
             "variables": {},
             "data_array": "$var.job.devices",
             "transformation": "",
             "loopType": "parallel"
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
         "nodeLocation": {"x": 600, "y": 312}
       },

       "m1m1": {
         "name": "merge",
         "canvasName": "merge",
         "summary": "Capture childJob job_details via taskRef",
         "description": "Workaround for $var.<childJobId>.job_details resolving as a literal string in downstream query.obj on some platform versions. Re-captures job_details through a taskRef in data_to_merge, which resolves reliably.",
         "location": "Application",
         "locationType": null,
         "app": "WorkFlowEngine",
         "type": "operation",
         "displayName": "WorkFlowEngine",
         "variables": {
           "incoming": {
             "data_to_merge": [
               {"task": "a1a1", "variable": "job_details"},
               {"task": "static", "value": {}}
             ]
           },
           "outgoing": {
             "merged_object": null
           },
           "error": "",
           "decorators": []
         },
         "groups": [],
         "scheduled": false,
         "nodeLocation": {"x": 600, "y": 420}
       },

       "b2b2": {
         "name": "query",
         "canvasName": "query",
         "summary": "Extract taskStatus from every loop iteration",
         "description": "Reads the merged_object (not the raw $var.a1a1.job_details) so the loop array actually resolves. Query path uses [**] to pull one field from every element in the loop results.",
         "location": "Application",
         "locationType": null,
         "app": "WorkFlowEngine",
         "type": "operation",
         "displayName": "WorkFlowEngine",
         "variables": {
           "incoming": {
             "pass_on_null": false,
             "query": "loop[**].taskStatus",
             "obj": "$var.m1m1.merged_object"
           },
           "outgoing": {
             "return_data": "$var.job.childTaskStatuses"
           },
           "error": "",
           "decorators": []
         },
         "groups": [],
         "scheduled": false,
         "nodeLocation": {"x": 600, "y": 528}
       }
     },

     "transitions": {
       "a1a1": {
         "m1m1": {"type": "standard", "state": "success"}
       },
       "m1m1": {
         "b2b2": {"type": "standard", "state": "success"}
       }
     },

     "_notes": [
       "Root cause: on some platform versions, query.incoming.obj set directly to \"$var.<childJobId>.job_details\" does not resolve as a live object reference after a parallel childJob loop -- it is treated as a literal string, so every property path read off it (including 'loop' and 'loop[**].taskStatus') comes back null even though job_details is populated and every child completed with taskStatus: success.",
       "Why it looks intermittent / 'sometimes': it is not actually intermittent per se -- it is deterministic per platform version/build. It looks intermittent to the team because the same workflow JSON is reused across environments (dev vs prod) or across platform upgrades where the underlying $var resolution behavior for childJob job_details changed. Confirm by inspecting the query task's raw incoming/outgoing on the completed job (GET job) -- if obj resolved to the literal string '$var.a1a1.job_details' instead of an object, that is the signature of this bug.",
       "Fix: insert a merge task between the childJob and the query task. The merge's data_to_merge uses a taskRef {task: <childJobId>, variable: 'job_details'} (NOT a $var string) to re-capture job_details -- taskRefs in merge resolve reliably even when the $var string form does not. A second static {} entry is required because merge needs at least 2 items in data_to_merge (SKILL.md Gotcha #16: 'merge requires at least 2 items -- 1 item silently returns null').",
       "Then point the query's obj at $var.m1m1.merged_object (the merge output) instead of $var.a1a1.job_details directly.",
       "Query path for loop mode: use 'loop[**].taskStatus' (or 'loop' first, then a nested [**].taskStatus pass) to pull one field across every element of the parallel loop's results array.",
       "Sanity check before assuming this bug: confirm every child really did report taskStatus itself. Per SKILL.md 'Building the child workflow', the child MUST set an explicit taskStatus job variable on both its success and error paths (task --success--> newVariable(taskStatus=success) -> workflow_end, task --error--> newVariable(taskStatus=error) -> workflow_end). If the child does not explicitly set taskStatus, job_details will legitimately have taskStatus: null regardless of the merge/query wiring -- that is a separate, child-workflow-side bug, not the childJob/query wiring bug this fix addresses."
     ]
   }
   ```

## Final answer to the engineer

Here's what's going on.

**Root cause:** The `job_details` output of a `childJob` task is a special object that on some platform builds is not resolved as a live object reference when referenced directly as a `$var` string (`"obj": "$var.<childJobId>.job_details"`) inside a downstream `query` task's `incoming.obj`. Instead, on those versions the platform stores/reads it as a **literal string**. When `query` tries to run its path (`"loop"`, or `"loop[**].taskStatus"`) against a literal string instead of the real object, every lookup returns null — even though the loop genuinely completed and every child really did report `taskStatus: "success"` internally. This is a documented, known platform-version-specific quirk, not something wrong with your loop logic or your children's behavior.

That also explains the "sometimes" — it's not actually random. It's deterministic per platform build/version. It presents as intermittent when the same workflow JSON runs across environments (e.g., a dev instance still on the affected build vs. a prod instance that isn't), or after a platform upgrade changes how `$var` resolves childJob `job_details`. You can confirm this is what's happening by pulling the completed job (`GET /operations-manager/jobs/{jobId}`) and looking at what the query task's `obj` actually resolved to — if it shows the literal string `"$var.<childJobId>.job_details"` instead of an object, that's the signature.

**The fix** — insert a `merge` task between the `childJob` and the `query`:

1. `childJob` (`a1a1`, `loopType: "parallel"`) → outputs `job_details` as usual.
2. `merge` (`m1m1`) — set `data_to_merge` to a **taskRef**, not a `$var` string: `{"task": "a1a1", "variable": "job_details"}`, plus a required second static `{}` entry (merge needs ≥2 items or it silently returns null). TaskRefs in `merge.data_to_merge` resolve reliably even in the cases where the direct `$var` string form doesn't.
3. `query` (`b2b2`) — point `obj` at `$var.m1m1.merged_object` (the merge's output) instead of `$var.a1a1.job_details` directly, and query `"loop[**].taskStatus"` to pull `taskStatus` off every element of the parallel loop's result array in one shot.

This is exactly the workaround documented in the builder-agent skill for this scenario (Guide 4, childJob loop section, and repeated in the Guide 1 pre-submit checklist and the childJob checklist), and it's the same fix used for the single-child-mode equivalent of this bug.

**One thing to rule out first, since it produces the identical symptom:** if your *child* workflow doesn't explicitly set a `taskStatus` job variable on both its success and error exit paths (i.e., it doesn't end with something like `task --success--> newVariable(taskStatus="success") -> workflow_end` and `task --error--> newVariable(taskStatus="error") -> workflow_end`), then `job_details.taskStatus` will legitimately be null/missing for that child no matter how you wire the parent's merge/query — that's a child-workflow gap, not the platform quirk above. Worth a quick check on the child before you conclude it's 100% the merge/query issue, especially if only *some* children (not all) show null.

I built the concrete task JSON for the merge+query fix (childJob → merge → query, field-shape-checked against real `merge`/`query` tasks from the repo's production asset library) so you can drop it straight into your parent workflow between the existing `childJob` task and your current `query` task.

## Files written

- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-20/new_skill/run-1/outputs/childjob-loop-taskstatus-fix.json` — the merge+query fix as full task/transition JSON, with inline `_notes` explaining root cause and fix.
- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-20/new_skill/run-1/transcript.md` — this file.
