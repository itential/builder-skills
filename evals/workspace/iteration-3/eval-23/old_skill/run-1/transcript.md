# Transcript — Debugging `<!var!>` placeholders not resolving in makeData after childJob fan-out

## Task as given

> I have a childJob that fans out over subnets. Afterward I merge each child's job_details together
> with a static template string, then feed that merged object into a makeData task to render a final
> JSON string using `<!var!>` placeholders. The placeholders come through literally unresolved in the
> output instead of being substituted with real values. What's wrong and how do I fix it?

This is a debugging/advice question (Guide 2 in the builder-agent skill: "Debug a failed/misbehaving
job"), not a fresh workflow build, so the deliverable is a diagnosis + a corrected wiring pattern
(with a runnable JSON artifact demonstrating the fix), not a full new use-case build.

## Skill sections consulted

Read `/tmp/eval-old-skill/builder-agent/SKILL.md` in full (2313 lines) before answering, per the
task's instructions to treat it as the sole source of truth. The sections that directly bear on this
bug:

- **`## $var Resolution Rules`** (~line 1237) — `$var` only resolves as a *direct top-level* incoming
  value (`"x": "$var.job.y"`). It does **not** resolve when nested inside another object
  (`"body": {"data": "$var.job.y"}` is stored as a dead literal). Workaround: use `merge`/`makeData`/
  `query` to pre-resolve the object, then reference it with a single-hop `$var.<taskId>.<outVar>`.
- **`### makeData`** (~line 1505) — "Construct data with `<!var!>` variable substitution. **Incoming:**
  `input` (string with `<!var!>` placeholders), `outputType`, `variables` (object)... **The `variables`
  field must be a resolved object.** Use merge first to build it, then pass via
  `$var.taskId.merged_object`."
- **Gotcha #23** (~line 2175): "`makeData` `variables` must be a resolved object — use merge first,
  then pass `$var.taskId.merged_object`."
- **`### merge`** (~line 1302) — `data_to_merge` format, and critically: "**Duplicate keys produce
  arrays** — merging `{"ip": "1.2.3.4"}` and `{"ip": "1.2.3.4"}` yields
  `{"ip": ["1.2.3.4", "1.2.3.4"]}`, not an overwrite."
- **Guide 4: Build a childJob** (~line 506) — Mode B (loop over `data_array`): "**Extracting loop
  output:** Query `"loop"` to get the results array" — the output of a fanned-out childJob is an
  **array**, one element per child/subnet, not a single flat object.
- **`### forEach`** (~line 1473) and Gotcha #40 — `$var.<taskId>.<out>` does not resolve inside nested
  forEach bodies; bind to `$var.job.<varName>` (the loop's `current_item` job-var binding) instead.
- **Variable Syntax Reference table** (~line 2105) — confirms `makeData input` uses `<!var!>` and gives
  the canonical example `{"name": "<!name!>"}`, i.e. the template text is authored inline as a literal
  string on the task, not built dynamically.
- **`incomingRefs` cache** section (~line 1253) and Gotcha #39 — flags a *secondary* risk: if the
  workflow was built via API create/PUT and never saved once through Automation Studio, static
  literals and changed-field taskRefs can resolve to `null` after a PUT to an *existing* task. Worth
  ruling out if the fix below doesn't fully resolve it, but it doesn't match the reported symptom on
  its own (that failure mode produces `null`s, not literal un-substituted `<!var!>` tokens).

Per the skill's explicit "STOP — read real asset JSON before guessing task structure" instruction
(Guide 1, ~line 163), I did not reason from memory about `makeData`/`merge`/`childJob` shapes — I
pulled real, production-imported examples from
`/Users/ankitrbhansali/builderskills/builder-skills/helpers/assets/`:

```bash
# Real makeData task, in production use:
jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "makeData")] | first | .value' \
  helpers/assets/itential-platform-configuration-management.json
```
```json
{
  "name": "makeData",
  "variables": {
    "incoming": {
      "input": "[name=<!treeName!>].id",
      "outputType": "string",
      "variables": "$var.7c0d.options"
    },
    "outgoing": { "output": null }
  }
}
```

This is the exact confirmation of the documented rule: `input` is a **literal string authored inline**
with the `<!var!>` token baked in — it is never itself built from `$var`. `variables` is a **single,
direct, top-level `$var.<taskId>.<outVar>`** reference to an already-resolved object produced by an
upstream task. I traced task `7c0d` in that same workflow ("Golden Configuration Tree") and confirmed
it is a `transformation` task whose `outgoing.options` is exactly the flat object `makeData` consumes —
i.e., in production, the object fed to `makeData.variables` is always pre-flattened by a dedicated
upstream task, never assembled by mixing the template text into the same object.

I also pulled a real `merge` task (`vendor-servicenow.json`) and a real fanned-out `childJob`
(`vendor-netbox.json`, `"Delete Prefix"`, `data_array: "$var.1bd8.ipsInPrefix"`, `loopType: "sequential"`)
to ground the corrected fragment's task IDs/field shapes in real, tested examples rather than invented
ones.

## Diagnosis

Three documented behaviors compound to produce exactly this symptom (literal `<!var!>` text surviving
into the output, rather than `null` or a runtime error):

**1. The template string and the substitution data were merged into the same object — but `makeData`
has two independent incoming fields that must never be combined.**
`input` (the literal template with `<!var!>` tokens) is authored directly in the task JSON. `variables`
is a *separate*, flat, resolved object supplying the values to substitute. If the `merge` task
described ("merge each child's job_details together with a static template string") produced a single
`merged_object` like `{"template": "...<!subnet!>...", "job_details": {...}}` and that whole thing was
wired into `makeData`, then:
- `variables`'s top-level keys are `template` and `job_details` — neither matches any `<!placeholder!>`
  name used in the template, so the substitution engine finds no match for any token and leaves every
  `<!var!>` untouched.
- The actual per-subnet fields the placeholders need (e.g. `subnet`, `vlanId`) are nested *inside*
  `job_details`, not top-level in `variables` — and per the `$var` Resolution Rules, `$var` (and this
  substitution mechanism) does not reach into nested object levels; only direct top-level keys are
  matched.

**2. Even with correct separation, `makeData.variables` must be a single-hop, top-level `$var.<taskId>.<outVar>` reference — not a deeper path into a nested key.**
Wiring something like `"variables": "$var.mergeTaskId.merged_object.job_details"` (reaching a second
level into the merge output) is unsupported; the documented, production-verified pattern is always one
hop from a dedicated upstream task's output (`$var.7c0d.options` in the real example above), where that
output is *already* the flat object you want, not a further-nested value inside it.

**3. The childJob fanned out over N subnets, so `job_details` (or `query("loop")`'s `return_data`) is
an ARRAY of N per-subnet objects — not a single flat object makeData can substitute from.**
Per Guide 4 Mode B, querying `"loop"` returns one array element per child. If those N objects were then
merged together, `merge`'s documented duplicate-key behavior turns any field name shared across
subnets into an **array** (`{"subnet": ["10.0.0.0/24", "10.0.1.0/24", ...]}`), not an overwritten
scalar. A single `<!subnet!>` token in one `makeData` call has no sensible scalar to bind to — there
is no "one subnet" once N children's data has been flattened together. This is a structural mismatch,
independent of (1) and (2): a single flat-substitution render cannot represent a fan-out's worth of
distinct per-child data in one shot.

Any one of these is sufficient to reproduce "placeholders come through literally"; the description
given ("merge each child's job_details together with a static template string, then feed into
makeData") suggests at least (1) and likely (3) are both present.

## The fix

1. **Stop merging the template text into the data.** Keep the `<!var!>`-tokenized template as
   `makeData`'s own literal `input` field, written inline in the task JSON — never sourced via `$var`
   or built by a `merge`.
2. **Build a genuinely flat `variables` object with one key per placeholder**, using a `merge` task
   whose `data_to_merge` entries' `"key"` values are exactly the placeholder names (`subnet`, `vlanId`,
   etc.), sourced with `{"task": ..., "variable": ...}` (merge always uses `"variable"`, never
   `"value"` — that's childJob's convention).
3. **Wire `makeData.variables` with one direct hop**: `"$var.<mergeTaskId>.merged_object"`.
4. **Resolve the fan-out mismatch** — decide which of two shapes you actually want:
   - **One JSON document per subnet** → move the merge→makeData pair *inside* a loop over the
     childJob's `query("loop")` array (`forEach`, since this is post-processing after the fan-out
     already ran) and `push` each rendered string into a job-level array. Remember: the forEach's last
     body task needs an empty `{}` transition (don't loop back to `forEach`), and any reference to a
     task's output inside the nested loop body must go through `$var.job.<varName>` — `$var.<taskId>.<out>`
     does not resolve inside nested forEach bodies.
   - **One aggregate JSON document covering all subnets** → don't use `merge`+`makeData` for the
     data-shaping at all; use a `transformation` (JST) task to reshape the array into whatever flat
     object the report needs, exactly like the real "Golden Configuration Tree" workflow does
     (`transformation` task → `makeData` task, single top-level reference between them).
5. **Sanity checks before re-testing:**
   - `merge` requires at least 2 `data_to_merge` items — 1 item silently returns `null`.
   - `merge`'s `outgoing.merged_object` must be declared as `null` (not `{}`, which makes it
     unreachable).
   - If this workflow was built by PUTing changes onto *existing* tasks (rather than adding new
     tasks) via the API, the `incomingRefs` cache is not regenerated and can cause literals/task-refs
     to resolve to `null` instead of their value. That produces a different symptom (blank/null values,
     not literal placeholder text) but is worth ruling out as a secondary issue by opening the
     workflow once in Automation Studio and saving, if anything still looks wrong after the wiring fix
     above.

## Corrected JSON artifact

Written to:
`/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-23/old_skill/run-1/outputs/childjob-makedata-fix.json`

It contains a full corrected task/transition fragment:
`childJob` (fan-out, loopType `parallel`, `data_array: $var.job.subnets`) → `query("loop")` → `forEach`
over the per-subnet results → per-iteration `query` extractions (`subnet`, `vlanId`) → `merge` (flat,
placeholder-matching keys, including a legitimate static value `reportTitle` merged in alongside the
dynamic ones) → `makeData` (literal `input` with `<!reportTitle!>`, `<!subnet!>`, `<!vlanId!>`
placeholders; `variables` wired as a single top-level `$var.d1d1.merged_object` reference) → `push`
into a job-level results array → `workflow_end`. It also documents the `transformation`-based
alternative for the "one aggregate document" case, with the exact `jq` command to pull the real
"Golden Configuration Tree" reference example from `helpers/assets/itential-platform-configuration-management.json`.

Full JSON (also on disk at the path above):

```json
{
  "_comment": "Corrected fragment for: childJob fan-out over subnets -> per-subnet merge -> makeData render. Pulled/adapted from real patterns in helpers/assets (childJob loop: vendor-netbox.json 'Delete Prefix'; merge: vendor-servicenow.json; makeData literal-input + $var.taskId.output wiring: itential-platform-configuration-management.json 'Golden Configuration Tree', task 7c0d -> 727).",

  "root_cause_summary": [
    "1) The static template text was merged INTO the same object as the child data instead of staying as makeData's own literal `input` field. `input` and `variables` are two separate incoming fields on makeData -- `input` is authored inline with the `<!var!>` tokens baked in as plain JSON text, `variables` is a SEPARATE flat object supplying the substitution values. Merging them together produces a `variables` object whose top-level keys (e.g. 'template') never match any placeholder name, so nothing substitutes.",
    "2) makeData's `variables` must be a single, direct, top-level `$var.<taskId>.<outVar>` reference to an already-resolved flat object (SKILL.md line ~1512, Gotcha #23). Any deeper dotting into a merge/transformation output's nested keys, or any attempt to inline $var refs inside a literal object, will not resolve.",
    "3) Because the childJob fanned out over N subnets (loopType parallel/sequential + data_array), job_details/query('loop') is an ARRAY of N per-subnet objects, not one flat object. merge's duplicate-key behavior turns shared field names across those N objects into ARRAYS, not overwritten scalars (SKILL.md line 1331) -- so even with correct wiring, a single top-level makeData call can't bind one array of N values to one scalar <!placeholder!>. Rendering must happen once per subnet (loop the merge->makeData pair), or be replaced entirely by a `transformation` (JST) task if a single aggregate JSON covering all subnets is actually what's wanted."
  ],

  "tasks": {
    "workflow_start": {
      "name": "workflow_start",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 200}
    },

    "a1a1": {
      "name": "childJob",
      "canvasName": "childJob",
      "summary": "Run Subnet Job Per Subnet",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "task": "",
          "workflow": "Subnet Child Workflow",
          "variables": {},
          "data_array": "$var.job.subnets",
          "transformation": "",
          "loopType": "parallel"
        },
        "outgoing": {"job_details": null}
      },
      "actor": "job",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 312}
    },

    "b1b1": {
      "name": "query",
      "canvasName": "query",
      "summary": "Extract Per-Subnet Results",
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
          "return_data": "$var.job.childResults"
        },
        "error": "",
        "decorators": []
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 420}
    },

    "c1c1": {
      "name": "forEach",
      "canvasName": "forEach",
      "summary": "Render One JSON Doc Per Subnet",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "data_array": "$var.job.childResults"
        },
        "outgoing": {
          "current_item": "$var.job.current_item"
        },
        "error": "",
        "decorators": []
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 528}
    },

    "e1e1": {
      "name": "query",
      "canvasName": "query",
      "summary": "Extract subnet from current_item",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "pass_on_null": false,
          "query": "subnet",
          "obj": "$var.job.current_item"
        },
        "outgoing": {
          "return_data": "$var.job.currentSubnet"
        },
        "error": "",
        "decorators": []
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 336, "y": 636}
    },

    "e2e2": {
      "name": "query",
      "canvasName": "query",
      "summary": "Extract vlanId from current_item",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "pass_on_null": false,
          "query": "vlanId",
          "obj": "$var.job.current_item"
        },
        "outgoing": {
          "return_data": "$var.job.currentVlanId"
        },
        "error": "",
        "decorators": []
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 864, "y": 636}
    },

    "d1d1": {
      "name": "merge",
      "canvasName": "merge",
      "summary": "Build Flat Render Variables (NOT the template text)",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "data_to_merge": [
            {"key": "subnet", "value": {"task": "job", "variable": "currentSubnet"}},
            {"key": "vlanId", "value": {"task": "job", "variable": "currentVlanId"}},
            {"key": "reportTitle", "value": {"task": "static", "variable": "Subnet Provisioning Report"}}
          ]
        },
        "outgoing": {
          "merged_object": null
        },
        "error": "",
        "decorators": []
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 744}
    },

    "f1f1": {
      "name": "makeData",
      "canvasName": "makeData",
      "summary": "Render Final JSON String",
      "description": "input is authored INLINE with <!var!> tokens -- never built via merge/$var. variables is a single top-level $var.<taskId>.merged_object reference to a flat, already-resolved object.",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "automatic",
      "displayName": "Tools",
      "variables": {
        "incoming": {
          "input": "{\"title\": \"<!reportTitle!>\", \"subnet\": \"<!subnet!>\", \"vlanId\": \"<!vlanId!>\"}",
          "outputType": "string",
          "variables": "$var.d1d1.merged_object"
        },
        "outgoing": {
          "output": null
        },
        "error": "",
        "decorators": []
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 852}
    },

    "g1g1": {
      "name": "push",
      "canvasName": "push",
      "summary": "Collect Rendered JSON Docs",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "job_variable": "renderedSubnetDocs",
          "item_to_push": "$var.f1f1.output"
        },
        "outgoing": {},
        "error": "",
        "decorators": []
      },
      "actor": "Pronghorn",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 960}
    },

    "workflow_end": {
      "name": "workflow_end",
      "groups": [],
      "nodeLocation": {"x": 600, "y": 1068}
    }
  },

  "transitions": {
    "workflow_start": {"a1a1": {"type": "standard", "state": "success"}},
    "a1a1": {"b1b1": {"type": "standard", "state": "success"}},
    "b1b1": {"c1c1": {"type": "standard", "state": "success"}},
    "c1c1": {
      "e1e1": {"type": "standard", "state": "loop"},
      "workflow_end": {"type": "standard", "state": "success"}
    },
    "e1e1": {"e2e2": {"type": "standard", "state": "success"}},
    "e2e2": {"d1d1": {"type": "standard", "state": "success"}},
    "d1d1": {"f1f1": {"type": "standard", "state": "success"}},
    "f1f1": {"g1g1": {"type": "standard", "state": "success"}},
    "g1g1": {},
    "workflow_end": {}
  },

  "notes_alternative_pattern": "If the actual intent is ONE aggregate JSON document covering all subnets (not one document per subnet), don't loop makeData at all -- replace the forEach+merge+makeData+push chain with a single `transformation` (JST) task consuming $var.job.childResults directly. This is exactly how the real 'Golden Configuration Tree' workflow in helpers/assets/itential-platform-configuration-management.json does it: a transformation task (id 7c0d) builds a flat object, and only THEN does a makeData task (id 727) consume it via a direct top-level $var.7c0d.options reference. Extract with: jq '[.components[] | select(.type==\"workflow\") | select(.document.name==\"Golden Configuration Tree\")] | first | .document.tasks[\"7c0d\",\"727\"]' helpers/assets/itential-platform-configuration-management.json"
}
```

## Final answer as given to the engineer

Here's what's happening and how to fix it.

**Root cause:** `makeData` has two independent incoming fields — `input` (the literal template text
with `<!var!>` tokens, authored inline in the task JSON) and `variables` (a *separate*, flat, resolved
object supplying the substitution values). Merging the static template string together with the
child's `job_details` in your `merge` task collapses these two things into one object, so:

- The `variables` object you end up passing to `makeData` has top-level keys like `template` and
  `job_details` — not the actual field names your placeholders reference (`subnet`, `vlanId`, etc.).
  makeData's substitution only matches *top-level* keys in `variables` against `<!placeholder!>` names;
  since none match, every token is left exactly as written.
- Even if you hadn't included the template text, your real data is nested one level down inside
  `job_details` — and `$var`/`<!var!>` resolution in this platform never reaches into nested object
  levels. `variables` has to be single-hop-flat, e.g. `{"subnet": "10.0.0.0/24", "vlanId": "100"}`, not
  `{"job_details": {"subnet": ..., "vlanId": ...}}`.
- There's also a structural problem underneath: since the childJob fanned out over multiple subnets,
  `job_details`/`query("loop")` is an **array** of per-subnet results, not one object. If you merge
  those N results together, merge's documented duplicate-key behavior turns shared field names into
  arrays (`"subnet": ["10.0.0.0/24", "10.0.1.0/24", ...]`) rather than picking one — so there's no
  single scalar for a single `<!subnet!>` token to bind to, even with everything else wired correctly.

**Fix:**
1. Keep the `<!var!>`-tokenized template as `makeData`'s own literal `input` — write it directly in
   the task, don't source it through merge/`$var`.
2. Build `variables` with a `merge` task whose `data_to_merge` `"key"` values are exactly your
   placeholder names (`subnet`, `vlanId`, ...), and wire `makeData.variables` as one direct hop:
   `"$var.<mergeTaskId>.merged_object"`.
3. Decide if you want one rendered JSON per subnet or one aggregate JSON for all subnets:
   - **Per subnet:** loop the merge→makeData pair over the childJob's `query("loop")` array (a
     `forEach`), pushing each rendered string into a results array. Inside that loop, reference values
     via `$var.job.<varName>`, not `$var.<taskId>.<out>` — task-output refs don't resolve inside nested
     forEach bodies.
   - **One aggregate doc:** skip `merge`/`makeData` for the data-shaping and use a `transformation`
     (JST) task instead — it's built for exactly this, and it's the pattern the real
     "Golden Configuration Tree" workflow in your asset library uses (transformation → makeData, single
     top-level reference between them).
4. Double-check: `merge` needs at least 2 `data_to_merge` items (1 item silently returns `null`), and
   its `merged_object` outgoing must be declared `null`, not `{}`. If this workflow was created via API
   and then had fields on existing tasks changed via PUT (rather than being fully recreated or saved
   once in Automation Studio), the `incomingRefs` cache issue can also cause values to resolve as
   `null` — worth a one-time Studio save to rule out if anything still looks off after the rewiring.

I put a complete corrected task/transition JSON fragment implementing this (per-subnet variant, plus
notes on the aggregate variant) at
`evals/workspace/iteration-3/eval-23/old_skill/run-1/outputs/childjob-makedata-fix.json`.
