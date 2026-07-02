# Transcript — Debugging unresolved `<!var!>` placeholders after childJob → merge → makeData

## Task as given

> I have a childJob that fans out over subnets. Afterward I merge each child's job_details together
> with a static template string, then feed that merged object into a makeData task to render a final
> JSON string using `<!var!>` placeholders. The placeholders come through literally unresolved in the
> output instead of being substituted with real values. What's wrong and how do I fix it?

This is framed as a debugging/advice question (no live platform in this session), so the deliverable is
a full diagnosis + recommended fix, plus a concrete corrected JSON artifact showing both the broken
pattern and the fix.

## Steps taken

1. Read the full `builder-agent` SKILL.md at
   `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md`
   (2442 lines, read in full via paginated `Read` calls) before answering, per the test instructions.
2. Also had `CLAUDE.md`/`AGENTS.md` context auto-injected — cross-checked Rule 8 ("`$var` references
   don't resolve inside object values... use merge, makeData, query...") and Rule 22/6 for variable
   syntax by context. This corroborated but did not contradict the SKILL.md findings.
3. Located the exact documented gotcha by grepping the skill for `makeData`:
   ```bash
   grep -n "makeData" .claude/skills/builder-agent/SKILL.md
   ```
   Found:
   - Guide 1 pre-submit checklist, line 378: *"makeData with childJob-sourced merge: if a merge task
     references a childJob variable, do NOT wire that merge's `merged_object` into
     `makeData.incoming.variables` — use `query` to extract individual values first."*
   - `### makeData` body section (lines 1614–1632) — the authoritative, detailed explanation:
     > **WARNING — `makeData.incoming.variables` cannot use `$var` references to a merge that sources
     > childJob output.** When a `merge` task's `data_to_merge` contains a childJob reference (e.g.,
     > `{"task": "childJobId", "variable": "job_details"}`), the platform cannot compile
     > `$var.<mergeId>.merged_object` as a `taskRef` for `makeData.incoming.variables` — it is stored
     > as a literal static string. Template substitution then operates on the literal string and emits
     > unresolved placeholders.
     >
     > `query.incoming.obj` does NOT have this limitation — it resolves `$var.<mergeId>.merged_object`
     > correctly even when the merge references childJob output.
     >
     > **Fix:** extract individual values from the childJob-sourced merge using `query` tasks, then
     > pass those resolved scalars to makeData via a second merge (that contains only non-childJob
     > refs). Do NOT feed a childJob-sourced merge directly into makeData's `variables`.
   - Gotchas pre-flight list, item 23 (line 2303): *"`makeData` `variables` must be a resolved object —
     use merge first, then pass `$var.taskId.merged_object`."*
   - Variable Syntax Reference (line 2239): confirms `makeData input` uses `<!var!>` syntax, same family
     as MOP command templates — distinct from `$var.job.x` workflow wiring and Jinja2 `{{ var }}`.
4. Cross-checked the general `$var` Resolution Rules section (lines 1313–1345) — this is the umbrella
   rule the makeData gotcha is a special case of: `$var` only resolves as a **direct top-level incoming
   value**; nested/object contexts require merge/makeData/query as an intermediate resolver. The
   makeData-specific twist is that even the *intermediate resolver itself* (a merge) can produce an
   unresolvable taskRef if it was built from a childJob reference.
5. Pulled real production examples to ground the fix in actual asset JSON rather than invented syntax:
   ```bash
   jq '[.components[].document.tasks // {} | to_entries[] | select(.value.name == "makeData")] | first | .value' \
     helpers/assets/itential-platform-configuration-management.json
   ```
   Confirmed the real shape of a working `makeData` task (`input` with `<!var!>` placeholders,
   `outputType`, `variables` wired to `$var.<taskId>.<resolvedOutput>`, `outgoing.output`).
   Also reviewed the "Extracting single child output" merge+taskRef workaround example in Guide 4
   (lines 582–613) and the ServiceNow `createChangeRequest` merge example (lines 310–330) to get the
   exact `data_to_merge` reference-object shapes (`{"task","variable"}` for task-produced values,
   `{"task":"static","value":...}` for literals, and the `{"key":"name","value":{...}}` wrapper form
   for naming fields in the resulting merged object).
6. Assembled a corrected task/transition JSON fragment (both the broken pattern and the fixed pattern)
   using only documented, real field shapes — no invented schema. Validated with `jq empty`.

## Diagnosis

Root cause: **`makeData.incoming.variables` cannot resolve a `$var` reference to a merge task whose
`data_to_merge` includes a childJob-sourced reference** (e.g. `{"task": "<childJobId>",
"variable": "job_details"}`). This is a documented, platform-specific limitation that is narrower than
the general "`$var` doesn't resolve inside nested objects" rule — it applies specifically to the
`makeData.incoming.variables` field when the upstream merge is childJob-sourced. Concretely:

- Your merge task (`data_to_merge: [{childJob job_details ref}, {static template string}]`) builds an
  object fine in isolation.
- But when you wire `makeData.incoming.variables` to `$var.<mergeTaskId>.merged_object`, the engine
  cannot compile that reference into a resolvable `taskRef` *because the merge's source data includes a
  childJob reference*. Instead of resolving the object, the engine stores the string
  `"$var.<mergeTaskId>.merged_object"` itself as a literal.
- `makeData`'s `<!var!>` substitution then runs against that literal string (which has no matching
  keys), so every `<!placeholder!>` in `input` is left untouched and passes straight through to
  `output`.
- Notably, `query.incoming.obj` does **not** have this limitation — the exact same
  `$var.<mergeTaskId>.merged_object` reference resolves correctly when read by a `query` task. This is
  the key fact that makes the fix possible: use `query` as the resolver for anything sourced from a
  childJob-tainted merge, and only feed **already-resolved scalars** into `makeData`.

## Recommended fix (given to the engineer)

Don't feed a childJob-sourced merge directly into `makeData.incoming.variables`. Instead:

1. Keep (or add) a `merge` task that captures the childJob's `job_details` via a taskRef —
   `data_to_merge: [{"task": "<childJobId>", "variable": "job_details"}, {"task": "static", "value": {}}]`
   — this is also the standard workaround for `$var.<childJobId>.job_details` not resolving on some
   platform versions.
2. Use one or more `query` tasks against that merge's `merged_object` (`obj:
   "$var.<mergeTaskId>.merged_object"`) to pull out the **individual scalar values** the template
   actually needs (counts, statuses, specific fields) — `query.incoming.obj` resolves this fine even
   though `makeData.incoming.variables` won't.
3. Build a **second, clean `merge`** whose `data_to_merge` contains **only** those already-resolved
   query outputs plus static/literal values — no childJob references anywhere in this second merge.
4. Wire `makeData.incoming.variables` to `$var.<secondMergeTaskId>.merged_object`. Because this merge
   has no childJob-sourced entries, the reference compiles as a real taskRef, the object resolves at
   runtime, and every `<!var!>` placeholder in `makeData.incoming.input` now substitutes correctly.

In short: **treat the childJob-sourced merge as a "resolve-only" object you read with `query`, never as
something you hand directly to `makeData`.** Anything that needs to reach `makeData` must first pass
through a query (or another resolver) that strips out the childJob lineage, landing in a merge built
from clean, already-scalar values.

## Artifact produced

`/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-23/new_skill/run-1/outputs/childjob-makedata-fix.json`

Contains two labeled sections (validated with `jq empty`):

- `broken_pattern` — the exact anti-pattern described in the question: `childJob (a1a1)` →
  `merge (e1e1)` (mixes the childJob's `job_details` ref with a static template string in the same
  `data_to_merge`) → `makeData (f1f1)` reading `$var.e1e1.merged_object` — reproduces the unresolved
  `<!var!>` placeholder bug, with an inline `why_it_fails` explanation.
- `fixed_pattern` — the corrected task graph and transitions:
  `childJob (a1a1)` → `merge (b2b2)` (capture `job_details` via taskRef) →
  `query (c3c3)` (full loop array, for record-keeping) →
  `query (d4d4)` (scalar: subnet count) →
  `query (d5d5)` (scalar: representative status) →
  `merge (e5e5)` (clean merge: static title + the two resolved scalars, **no childJob refs**) →
  `makeData (f1f1)` (variables wired to `$var.e5e5.merged_object`, `<!title!>`, `<!totalSubnets!>`,
  `<!status!>` now resolve) → `workflow_end`, with a shared `newVariable` error handler (`errh1`) wired
  from every failure/error transition to avoid the JSON duplicate-key problem on `workflow_end`.

Both sections use real, documented field shapes only (task IDs are hex per the platform's `[0-9a-f]{1,4}`
requirement; `merge` uses `"variable"`/`"value"` per the documented reference-object conventions;
`childJob` uses `actor: "job"`, empty `task`, `job_details` outgoing `null`).
