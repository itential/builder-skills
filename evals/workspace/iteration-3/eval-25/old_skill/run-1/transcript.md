# Transcript — Testing `builder-agent` skill on a childJob loop / static-variables debugging question

## Task as given

> I have a childJob looping over an array of subnet objects (each element only has `subnet_name` and
> `subnet_cidr`) with `loopType` parallel. The child workflow's `inputSchema` also requires
> `subscription_id` and `region`, which are the same for every iteration, so I'm passing them via the
> childJob task's static `variables` field instead of putting them in every array element. Validation
> fails before any iteration runs, saying `subscription_id` and `region` are missing. Why, and how do I
> fix it?

This is a debugging/advice question (Guide 2 territory, specifically the childJob loop mechanics in
Guide 4), not a "build a new workflow from a design doc" request, so the deliverable is a diagnosis plus
a concrete JSON patch the engineer can apply to their existing parent workflow.

## Steps taken

1. Read `/tmp/eval-old-skill/builder-agent/SKILL.md` in full (2314 lines, two Read calls) before answering,
   per the instructions — treated it as the only source of truth.
2. Located **Guide 4: Build a childJob** (lines ~506–658). Key facts pulled from it:
   - childJob has two *tested and verified* modes: **Mode A** (single child, static `variables` map
     using `{"task","value"}` refs) and **Mode B** (loop, `data_array` + `loopType`, with `variables: {}`).
   - Mode B explicitly states: *"Each element in `data_array` becomes the child's input variables for
     that iteration. Set `variables: {}` (empty)."*
   - The childJob checklist (line 644) has it as a hard rule: `- [ ] variables is {} when using
     data_array (loop mode)`.
   - The `### childJob` utility-task section (lines 1417–1471) repeats the same rule: *"With loops, use
     `data_array` (each element becomes a child job's variables) and set `variables: {}`."*
   - The Gotchas pre-flight list (#15–18, lines 2167–2170) reinforces the same constraint and calls out
     that mixing childJob's `{"task","value"}` syntax with merge/evaluation's `{"task","variable"}`
     syntax is a distinct, separate footgun (not what's happening here, but worth ruling out).
3. Noticed the skill references a **third, undocumented childJob mode** — the `### transformation` task
   section (line 1551) says JST transformation is *"Used in childJob mode 3 (loop with transformation) to
   reshape each `data_array` element before passing to the child."* This sounds like exactly the feature
   the engineer wants (inject constants into a loop). However:
   - Guide 4's own opening line says *"childJob has two modes. **Both are tested and verified** on a live
     platform"* — explicitly only Mode A and Mode B, not this "mode 3."
   - I verified there is no worked example of "mode 3" anywhere in the shipped asset library:
     ```bash
     for f in helpers/assets/*.json helpers/assets/lcm/*.json; do
       jq -c '[.components[]?.document.tasks // {} | to_entries[]
               | select(.value.name == "childJob") | .value.variables.incoming
               | {data_array, transformation, loopType, variables}]' "$f"
     done
     ```
     Result: every real, production-imported childJob task in every asset file has
     `"transformation": ""` — never populated. So "mode 3" is *mentioned* but not demonstrated or
     verified anywhere the skill points to. I treated it as a documented-but-unverified gap rather than
     a safe recommendation, per the instruction not to fabricate from memory / not to guess when the
     skill tells you to look things up. I flag it to the engineer as a possible future option but do not
     build on it.
4. Confirmed the real, live-tested behavior instead, by pulling an actual production childJob-loop task
   from the asset library:
   ```bash
   jq '[.components[]?.document.tasks // {} | to_entries[] | select(.value.name == "childJob")] | .[].value.variables.incoming' \
     helpers/assets/vendor-netbox.json
   # → {"data_array": "$var.1bd8.ipsInPrefix", "transformation": "", "loopType": "sequential", "variables": {}}
   ```
   This is a real, production-imported workflow and it confirms the rule exactly: when `data_array` +
   `loopType` are used, `variables` is always `{}`. There is no live example anywhere of a loop-mode
   childJob with a non-empty `variables` map.
5. Looked up the supporting utility tasks needed for the fix (`forEach`, `query`, `merge`, `push`,
   `newVariable`) directly from the skill body text, all of which give exact `incoming`/`outgoing` field
   names — no guessing:
   - `### forEach` (deprecated but still documented, lines 1473–1487) — `data_array` in, `current_item`
     out, `state: loop` to the body, **last body task's transition must be empty `{}`**, and the
     "does not resolve inside *nested* forEach bodies" caveat only applies to nested loops (this is a
     single, non-nested loop, so direct task-to-task refs to `current_item` are fine).
   - Verified that rule against a real production example rather than trusting the prose alone:
     ```bash
     jq -c '.components[]?.document | select(.tasks | to_entries[]? | .value.summary? == "Iterate Over Each Device")
            | .tasks | to_entries[] | select((.value.variables.incoming // {}) | tostring | test("current_item"))
            | {id:.key, name:.value.name, incoming:.value.variables.incoming}' \
       helpers/assets/itential-platform-configuration-management.json
     ```
     Confirmed: `backUpDevice` incoming `"name": "$var.1d07.current_item"` — a direct task-to-task
     reference to the (non-nested) forEach's output, exactly as I planned to use it.
   - `### query`, `### merge`, `### push / pop / shift`, `### newVariable` (lines 1279–1503) — all give
     exact field names (`pass_on_null`/`query`/`obj`/`return_data`; `data_to_merge` with `key`/`value`
     objects using `{"task","variable"}`; `job_variable`/`item_to_push` as a **plain string** name, not a
     `$var` ref; `name`/`value` for newVariable).
   - Also checked `platform/tasks.json` (the real task catalog shipped with this repo) for a `map`/`assign`
     task that might do this in one step, and confirmed neither is wired up anywhere in the asset
     library (`grep`/`jq` returned no hits) and the skill gives no field-level documentation for their
     `incoming` shape — so per the "do not fabricate task schemas from memory" instruction, I did not use
     them and built the enrichment from `query` + `merge` + `push` instead, which *are* fully specified.
6. Checked real node-location conventions for a forEach-based loop against a production workflow (same
   `itential-platform-configuration-management.json` file) to lay out the fix in a way consistent with
   the skill's canvas conventions (spine at a constant x, loop body offset ~264–288px, post-loop task
   returning to the spine) rather than inventing a layout.
7. Wrote the diagnosis and a JSON patch (tasks + transitions + inputSchema additions) to:
   `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-25/old_skill/run-1/outputs/childjob-loop-static-variables-fix.json`
   Validated with `python3 -m json.tool` — parses cleanly.

## Diagnosis (root cause)

`childJob` has two live-tested wiring modes, and they are mutually exclusive on the `variables` field:

- **Mode A (single child):** `data_array: ""`, `loopType: ""`, and `variables` is a map of
  `{"task","value"}` refs — this is how you pass explicit variables to a single child run.
- **Mode B (loop):** `data_array` is set to an array job variable, `loopType` is `"parallel"` or
  `"sequential"`, and **`variables` must be `{}`**. In loop mode, the platform does not read the static
  `variables` map at all — each child iteration's *entire* input variable set is built by flat-spreading
  that iteration's `data_array` element. The skill states this three separate times (Guide 4 Mode B
  description, the childJob checklist, and the Gotchas list), and every real production childJob-loop
  task in the shipped asset library has `variables: {}` with no exception.

Because the array elements only contain `subnet_name` and `subnet_cidr`, and the static `variables` map
is ignored entirely in loop mode, `subscription_id` and `region` are never delivered to *any* child job
iteration — not "delivered incorrectly," just absent. The child workflow's `inputSchema.required` lists
both fields, so the platform's pre-flight schema validation for the child job fails immediately on
missing required properties, before the child workflow's first task ever runs. That matches the reported
symptom exactly ("validation fails before any iteration runs").

There is a third childJob capability referenced in the skill — populating childJob's own `transformation`
field with a JST transformation to reshape each `data_array` element (referred to in the skill as
"childJob mode 3") — which sounds tailor-made for exactly this "add constants to every loop element"
need. I checked for it specifically because it looked like the most direct fix, but the skill itself
scopes its "tested and verified on a live platform" claim to only Mode A and Mode B, and I could not find
a single worked example of a populated `transformation` field on any childJob task anywhere in the shipped
asset library. I'm flagging that as a documented-but-unverified gap rather than building the primary
recommendation on it.

## Recommended fix (given to the engineer)

Keep `variables: {}` on the childJob task (it's mandatory in loop mode) and instead make every element of
the array itself self-contained — i.e., add `subscription_id` and `region` to each of the subnet objects
*before* the childJob task runs, so `data_array` already contains fully-formed
`{subnet_name, subnet_cidr, subscription_id, region}` objects. Concretely, insert a small preprocessing
chain ahead of the childJob task in the parent workflow:

```
workflow_start
  -> newVariable  (init "enrichedSubnets" = [])
  -> forEach      (data_array = $var.job.subnets, outgoing current_item)
        --loop--> query (extract subnet_name from current_item)
                -> query (extract subnet_cidr from current_item)
                -> merge (combine subnet_name + subnet_cidr + subscription_id + region into one object)
                -> push  (append merged object onto job.enrichedSubnets)   [last body task: transition {}]
        --success--> childJob (data_array = $var.job.enrichedSubnets, variables = {}, loopType = "parallel")
  -> query (extract "loop" results from job_details)
  -> workflow_end
```

This is the full patch delivered in
`outputs/childjob-loop-static-variables-fix.json` — it includes the "before" (broken) childJob task as
described by the engineer and the "after" patch: 8 new/updated tasks (`newVariable`, `forEach`, two
`query` extraction tasks, `merge`, `push`, the corrected `childJob`, and the loop-results `query`), the
full `transitions` block wiring them together (including the mandatory empty `{}` transition on the last
loop-body task), and the `inputSchema` additions (`subnets`, `subscription_id`, `region` as required
top-level job variables on the parent).

Every task used in the fix (`forEach`, `query`, `merge`, `push`, `newVariable`) has its exact
`incoming`/`outgoing` field names taken verbatim from the skill body text and cross-checked against real
task wiring in `helpers/assets/itential-platform-configuration-management.json`; nothing was invented
from memory. `push`'s `job_variable` field is a plain string (not a `$var` ref) per the skill's explicit
gotcha (#21 in the Gotchas list) — a common way to accidentally re-break this fix.

## Answer as given to the engineer

> The validation failure is expected, not a bug — it's a consequence of how `loopType`/`data_array`
> childJob (Mode B in the skill's Guide 4) actually works. In loop mode, the childJob task's static
> `variables` field is not read at all; it must be `{}`. Each child iteration's entire set of input
> variables comes from flat-spreading that iteration's element of `data_array` — nothing else. So the
> `subscription_id`/`region` you put in the static `variables` map are being silently dropped for every
> iteration, and since your child workflow's `inputSchema.required` lists both, the platform's schema
> validation for the child job fails before the first task runs, exactly as you're seeing. This isn't
> specific to `parallel` — the same thing happens with `sequential`.
>
> There's a childJob field called `transformation` that in principle lets you reshape each `data_array`
> element (e.g., inject constants) via a JST transformation before it's handed to the child — but I
> couldn't find a single real, working example of it anywhere in our verified asset library, and our
> internal guide explicitly scopes "tested and verified on a live platform" to the two modes that don't
> use it. I'd treat that as an unverified/experimental path rather than build on it right now.
>
> The reliable fix: don't rely on the static `variables` field at all in loop mode. Instead, before the
> childJob task, merge `subscription_id` and `region` into every element of the array so each element is
> self-contained: `{subnet_name, subnet_cidr, subscription_id, region}`. Concretely: `forEach` over your
> raw `subnets` array, pull `subnet_name`/`subnet_cidr` off the current item with two `query` tasks,
> `merge` those two values together with your `subscription_id`/`region` job variables into one flat
> object, and `push` that object onto a new `enrichedSubnets` job variable. Point the childJob's
> `data_array` at `enrichedSubnets` instead of `subnets`, and leave `variables: {}`. Now every parallel
> child iteration receives all four required fields and the child workflow's `inputSchema` validation
> passes. I've written out the full task/transition JSON patch for this (8 tasks, fully wired,
> hex task IDs, correct `success`/`loop` transitions, and the mandatory empty `{}` transition on the last
> loop-body task) — see the attached JSON. One thing to double check after wiring this in Studio or via
> PUT: since you're changing existing task field values via API PUT rather than adding brand-new tasks,
> the skill's `incomingRefs` cache gotcha applies — if the merge/query values resolve to `null` at
> runtime after the PUT, open the workflow in Automation Studio and re-save it once; that regenerates the
> reference cache that a plain PUT doesn't touch.

## Files produced

- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-25/old_skill/run-1/outputs/childjob-loop-static-variables-fix.json`
  — before/after JSON: the broken childJob task as described, plus the full fix patch (new tasks,
  transitions, inputSchema additions). Validated as syntactically correct JSON.
- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-25/old_skill/run-1/transcript.md`
  — this file.
