# Transcript — Builder Agent skill test: childJob parallel loop validation failure

## Task as given

> I have a childJob looping over an array of subnet objects (each element only has
> `subnet_name` and `subnet_cidr`) with `loopType: parallel`. The child workflow's
> `inputSchema` also requires `subscription_id` and `region`, which are the same for
> every iteration, so I'm passing them via the childJob task's static `variables` field
> instead of putting them in every array element. Validation fails before any iteration
> runs, saying `subscription_id` and `region` are missing. Why, and how do I fix it?

This is a debugging/advice question (not a from-scratch build request), so per the eval
instructions I produced a full diagnosis plus the corrected JSON pattern as the concrete
artifact, rather than a whole new project/workflow.

## Steps taken

1. Read `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md`
   in full (2442 lines, read in two pages) before answering, per the harness instruction
   to treat it as the only source of truth.
2. Also read `AGENTS.md` (the router doc pulled in via `CLAUDE.md`) since it's loaded
   alongside the skill and contains the same-topic global "Key Rules" (rule #6 on variable
   syntax by context, rule #24 on scoped naming, etc.) that a builder would have in context.
3. Found the exact match for this scenario already documented in the skill: **Guide 4,
   Mode B ("Loop — one child per item in `data_array`")**, subsection **"Loop element
   completeness — required fields must be in each element (not in `variables`)"**
   (`SKILL.md` lines ~671–711). This section states verbatim:

   > The platform validates the child workflow's `inputSchema.required` against **each
   > element's keys only**. Static `variables` set on the childJob task are NOT counted
   > toward satisfying required fields. If your loop elements only contain per-iteration
   > fields (e.g., `subnet_name`, `subnet_cidr`) but the child also requires shared fields
   > (e.g., `subscription_id`, `region`), the validation fails before any iteration runs.

   This is the engineer's exact scenario, down to the same field names used as the
   illustrative example in the skill (`subnet_name`/`subnet_cidr` shared vs.
   `subscription_id`/`region`) — strong signal this is a documented, previously-hit
   platform gotcha, not a guess.

4. The skill also has this codified as a pre-flight checklist item under Guide 1 Step 9:

   > **childJob loop:** if child workflow has `inputSchema.required` fields beyond what
   > each `data_array` element contains, use the forEach enrichment pattern
   > (forEach → merge → arrayPush) to add shared fields into each element before the
   > childJob loop; set `variables: {}` on the childJob

5. To ground the fix in real, production task JSON rather than inventing shapes from
   memory (per the "look it up, don't guess" rule in `AGENTS.md`), I pulled real task
   structures from the local asset library at
   `${CLAUDE_PLUGIN_ROOT}/helpers/assets/`:

   - **`forEach`** — extracted from `itential-platform-configuration-management.json`,
     workflow "Backup Configuration" (task `1d07`, "Iterate Over Each Device"). This
     confirmed the real transition mechanics: `forEach` has two outgoing transitions —
     `"state": "loop"` → first body task, and `"state": "success"` → what runs after
     the loop completes. The last body task in that real example (`6af7`, a `ViewData`)
     has an **empty `{}` transition**, which matches the skill's checklist rule ("last
     body task has an empty `{}` transition") — the platform's forEach engine uses that
     empty transition to know the iteration's body finished and to pull the next item.
     ```bash
     jq '[.components[] | select(.type=="workflow") | select(.document.name == "Backup Configuration")] | first | .document | {tasks, transitions}' \
       helpers/assets/itential-platform-configuration-management.json
     ```
   - **`merge`** — extracted from `vendor-servicenow.json` ("Build sysparmQuery" task),
     confirming the `data_to_merge` shape (list of `{"key","value":{"task","variable"}}`
     entries, or a bare `{"task","variable"}` entry to pull in a whole prior task's
     output) and that merge tasks use `"variable"` (not `"value"`) for task-output refs.
   - **`childJob` loop mode with `data_array`** — extracted a real wired example from
     `vendor-netbox.json` ("Delete IP Address" child, task `4b5c`): confirmed
     `variables: {}`, `data_array: "$var.<taskId>.<output>"`, `loopType` set (in that
     asset, `"sequential"`; the engineer's case uses `"parallel"`, which the skill
     documents as an equally valid enum value), and `actor: "job"`.
   - **`arrayPush`** is not present as a wired example in any local asset file
     (`grep -rl '"name": "arrayPush"' helpers/assets/` returned nothing), so I built its
     task JSON directly from the skill's own documented Guide 4 snippet (`incoming:
     {"job_variable", "item_to_push"}`), which the skill itself supplies as the
     canonical shape for this exact pattern — this is the skill teaching a pattern, not
     me guessing a schema. I also used `AGENTS.md`'s explicit `canvasName` note
     (`arrayPush` → canvasName `"push"`) for the `canvasName` field.

6. Verified both produced JSON files are syntactically valid (`jq empty ...`) and that
   the task/transition key sets match 1:1.

## Diagnosis (why validation fails)

The childJob task has two separate places where you can supply data to the child
workflow:

- `variables` — a static, single-shot map of `{childVarName: {task, value}}` refs. This
  is meant for values that are the *same for the whole childJob call*.
- `data_array` — used only when `loopType` is set (`"parallel"` or `"sequential"`). Each
  element of this array becomes the **entire set of input variables** for one child
  iteration.

When `loopType` is non-empty, the Itential Platform's pre-flight validator checks the
child workflow's `inputSchema.required` against **each element of `data_array` in
isolation**. It does **not** union `variables` into that check, and it does not know
that `variables` is "supposed to" supplement each element. This happens as a **draft
workflow validation failure** — it's checked before the job starts, exactly like other
validation failures in Rule #7 of `AGENTS.md` ("Validation errors = draft workflow that
cannot be started").

So with:
```json
"variables": {
  "subscription_id": {"task": "job", "value": "subscription_id"},
  "region": {"task": "job", "value": "region"}
},
"data_array": "$var.job.subnets",   // each element: {subnet_name, subnet_cidr}
"loopType": "parallel"
```
every element in `subnets` is missing `subscription_id` and `region` from the
validator's point of view, because the validator never looks at `variables` in loop
mode. Hence the failure "subscription_id and region are missing" — fired once, before
any of the (parallel) child jobs are even attempted.

## The fix — forEach enrichment pattern

Per Guide 4 / Mode B and the Guide 1 Step 9 checklist: enrich every element with the
shared fields *before* the childJob loop, so each element is self-sufficient, then set
`variables: {}` on the childJob (since nothing needs to be passed the old way anymore).

Pattern:
```
forEach (iterate raw subnets)
  → merge (current_item + subscription_id + region from $var.job.*)
    → arrayPush (append merged object onto an accumulator array)
                                                    ↓ (after forEach's loop finishes)
childJob (data_array: <accumulator>, variables: {}, loopType: "parallel")
```

Concretely, for this scenario:
1. Add a `newVariable` task before the `forEach` to initialize the accumulator, e.g.
   `enrichedSubnets = []`.
2. `forEach` loops over `$var.job.subnets` (the original, unenriched array).
3. Inside the loop body, a `merge` task combines the current element
   (`{"task": "<forEachId>", "variable": "current_item"}`) with the two shared job-level
   fields (`{"key": "subscription_id", "value": {"task": "job", "variable":
   "subscription_id"}}` and the same for `region`).
4. An `arrayPush` task appends the merge's `merged_object` onto `enrichedSubnets`
   (`{"job_variable": "enrichedSubnets", "item_to_push": "$var.<mergeId>.merged_object"}`)
   and has the loop body's terminal **empty `{}` transition**.
5. `forEach`'s `"success"` transition (loop complete) leads to the `childJob` task, now
   wired as:
   ```json
   {
     "data_array": "$var.job.enrichedSubnets",
     "variables": {},
     "loopType": "parallel"
   }
   ```
   Each element of `enrichedSubnets` now carries all four fields
   (`subnet_name`, `subnet_cidr`, `subscription_id`, `region`), matching the child's
   `inputSchema.required` exactly, so per-element validation passes and the parallel
   loop starts.

Full, syntactically-valid task/transition JSON for both the broken version and the
fixed version is in the outputs directory (see below) — every task in the fixed version
is either lifted from a real asset export (`forEach`, `merge`, `childJob` loop shape) or
built directly from the skill's own documented `arrayPush` snippet, with hex task IDs,
mandatory error transition on the childJob, and canvas layout following the
skill's vertical spine convention (`x=600` spine, `y+108` per row, error branch offset
to `spine+264`).

## Artifacts written

- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-25/new_skill/run-1/outputs/broken-childjob-loop.json`
  — the engineer's current (failing) childJob task JSON, plus a worked explanation of
  why the validator rejects it.
- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-25/new_skill/run-1/outputs/fixed-childjob-loop.json`
  — the full corrected workflow fragment: `newVariable` (init accumulator) → `forEach` →
  `merge` → `arrayPush` → `childJob` (loop, `variables: {}`) → `query` (extract loop
  results) → `workflow_end`, with a dedicated error path off the childJob per the
  mandatory-error-transition rule.

## Final answer to the engineer (verbatim)

Your childJob's static `variables` field and its `data_array` loop field are validated
completely independently. When `loopType` is set (`"parallel"` or `"sequential"`), the
platform checks the child workflow's `inputSchema.required` against **each element of
`data_array` by itself** — it does not merge in whatever you put in `variables`.
`variables` in loop mode is basically inert for satisfying required fields; it's really
only meaningful in single-child mode (`loopType: ""`). So because your `subnets`
elements only carry `subnet_name` and `subnet_cidr`, every single element is missing
`subscription_id` and `region` as far as the validator is concerned, and the whole
workflow fails pre-flight validation before any of your parallel children even start.

The fix is to stop trying to inject the shared fields through `variables` and instead
bake them into every element before the loop runs — the "forEach enrichment" pattern:

1. Initialize an empty accumulator array (`enrichedSubnets`) with a `newVariable` task.
2. Run a `forEach` over your original `subnets` array.
3. Inside the loop, use a `merge` task to combine the current element
   (`current_item`) with `subscription_id` and `region` pulled from `$var.job.*`
   (these are still your normal workflow-level inputs — nothing changes about how the
   operator supplies them).
4. Use an `arrayPush` task to append that merged object onto `enrichedSubnets`. Make
   sure `arrayPush` is the last task in the loop body with an empty `{}` transition —
   that's what tells the forEach engine the iteration is done and to pull the next item.
5. Point your childJob at the enriched array instead of the raw one:
   `data_array: "$var.job.enrichedSubnets"`, and set `variables: {}` — you don't need it
   anymore since every element is now self-sufficient.

Now every element the platform validates has all four required fields
(`subnet_name`, `subnet_cidr`, `subscription_id`, `region`), so per-element validation
passes and your parallel loop actually starts. I've written out the full corrected
task/transition JSON (plus the broken version for side-by-side comparison) so you can
drop it straight into your workflow — see `fixed-childjob-loop.json` in the outputs
folder. One more thing while you're in there: add an error transition off the childJob
task (I routed mine to a small `newVariable` error-flag task before `workflow_end`) —
childJob tasks can still fail at the platform level even after this fix, and without an
error transition the job will get stuck in "running" forever instead of failing
cleanly.
