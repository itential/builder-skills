# How the platform actually validates workflows

This document is the result of reading the real Itential Platform source
(`app-workflow_builder`, `app-workflow_engine`, `app-automation_studio` —
not this repo) to answer one question: **when an agent builds a workflow
document via raw REST instead of the canvas UI, what actually catches its
mistakes, and what doesn't?**

The short answer: almost nothing does, until the job is running, and
sometimes not even then. This is the reasoning behind `helpers/validate_workflow.py`
existing at all — it isn't a convenience, it's compensating for a real gap.

## The core architectural fact

Both `workflow_builder`'s save path and `workflow_engine`'s job-start path
run the exact same underlying check — `globalUtils.validate()`
(`app-workflow_engine/server/utilities/utils.js`, which calls
`validateTask`/`validateTransition`) — but they treat the result
completely differently:

- **`POST workflow_builder/workflows/save`** calls it through the
  `Workflows.validate()` wrapper (`server/workflows/index.js`), which
  **never throws**. It just attaches whatever it found as `.errors`/
  `.warnings` arrays on the saved document and returns success either
  way. `saveWorkflow` only rejects on a handful of hard-coded guard
  clauses unrelated to workflow correctness: name format/uniqueness,
  project write permission, at least one task present, and `_id`
  referring to a real doc on update.
- **Job start** (`server/jobs/jobStart.js:163`) calls the *same*
  `globalUtils.validate()` directly, bypassing that wrapper, and
  explicitly does `if (validationErrors.length > 0) throw new Error(...)`.
  So a real "error" (not a "warning") from `validateTask`/`validateTransition`
  **does** block a job from starting — it just never blocked the save.

There is also a separate `POST /workflows/validate` endpoint that runs the
same check and returns the report directly — but it lives in
`app-automation_studio`, not `app-workflow_builder`, nothing calls it
automatically, and the canvas UI only calls it voluntarily to paint
red/yellow highlights.

**Consequence:** a workflow can always be *saved* in a shape that's
already broken, no matter how broken. Whether starting a *job* against it
catches the problem depends entirely on whether that specific mistake
happens to be one of the things `validateTask`/`validateTransition`
checks for, and whether it was pushed as an "error" (blocks job start) or
a "warning" (never blocks anything, ever). Several of the mistakes below
aren't checked for at all, at either stage — those fail silently, and the
worst of them (missing transitions) hang the job forever with no error
anywhere.

## Two independent problems

1. **Client-side-only guardrails** (canvas/GoJS, React dropdowns) that
   physically prevent a human from constructing certain states, with no
   server-side equivalent — an API agent can construct these freely.
2. **Runtime failures with no compile-time or save-time check** — the
   platform's own validation logic doesn't look for them at all, so
   there's no error to catch even in principle until a job runs (and in
   the worst cases, not even then).

## 1. Client-side-only guardrails (`app-automation_studio`)

All of this lives in `src/WorkflowCanvas/Diagram.jsx` (GoJS `linkingTool`)
and `src/WorkflowEditor/**`. None of it has a server-side equivalent — a
document built via raw REST can violate every rule below with no error at
any stage.

| Guardrail | Where | What it prevents |
|---|---|---|
| Self-loop / direct `workflow_start`→`workflow_end` links | `Diagram.jsx:739-767` (`linkValidation`) | A task transitioning to itself; skipping the workflow entirely |
| Duplicate transitions, cyclical standard transitions, `failure`/`error` from `workflow_start`, `loop` into `workflow_end` | `Diagram.jsx:836-917` (`insertLink`) | Several of the same structural bugs our gotchas describe, but only as a drag-gesture-time check |
| Loop-containment (a task inside a `forEach` can't transition outside it) | `utils/diagram.js:486-514` (`validateLoopTransitions`) | Exactly the forEach loop-back bug (gotcha #11 below) — the UI can't draw it, so it's never been caught this way in practice |
| Action dropdown limited to `resourceModel.actions` | `ActionSelect.jsx:21-44` | Picking an action incompatible with the selected resource |
| Actor dropdown limited to `Pronghorn`/`job`/upstream manual tasks | `AccessControl.jsx:28-48` | An invalid `actor` value (see gotcha #12 below — this is exactly what's unguarded server-side) |
| `$var.<taskId>.<field>` assembled from cascading dropdowns, never hand-typed | `TaskVariableSelect.jsx:274-306` | Referencing a nonexistent task or field (server does check existence at validate time — see table below — but not type compatibility in all cases) |
| "Enable Query" pointer always addresses one WHOLE field's value | `InputQuery.jsx`, `TaskVariableSelect.jsx:52-158` | There is no UI path to build a decorator pointing at a key nested inside an already-static object value. Confirms our own hard-won empirical finding: task query only resolves when the field's entire value IS the `$var...#/path` reference. |
| Auto-generated task IDs (`makeTaskId()`), auto-filled incoming defaults from JSON-schema, `runCode`'s `language: 'python'` / `safety.timeout: 1` auto-set on drop | `util/workflow.js:32-35, 545-586, 602-647` | Malformed task IDs, missing required fields, and explains why every UI-built `runCode` task has `timeout: 1` — it's an auto-default, not a considered choice |

## 2. Gotcha mechanisms, confirmed against real source

Every workflow/utility-task gotcha in `.claude/skills/builder-agent/SKILL.md`
(the `### Workflows` and `### Utility Tasks` sections, items 8-24) was
checked against the actual compiler/validator/worker code. The `#` column
below is this document's own numbering (not the skill file's item
numbers, since several mechanisms here span or fall between individual
skill items) — see each row's mechanism for the exact source citation.
Status legend:

- **blocks job start** — pushed as an `errors` entry by `validateTask`/
  `validateTransition`, so `jobStart.js`'s direct `globalUtils.validate()`
  call throws. Save still succeeds regardless.
- **advisory only** — pushed as a `warnings` entry (or an `errors` entry
  that some other path suppresses) — never blocks save *or* job start.
- **silent** — not checked by `validateTask`/`validateTransition` at all;
  the first (and sometimes only) sign of trouble is a runtime crash or a
  hung job.
- **hard crash, not part of validate()** — an unrelated code path throws
  a raw, unguarded JS exception outside the validate/errors mechanism
  entirely.

| # | Gotcha | Confirmed mechanism | Status |
|---|---|---|---|
| 1 | `childJob.workflow` can't be project-scoped | `jobStart.js:82-96` resolves by exact `{name}` query with no `@projectId:` stripping; `workflowMap[wfName]` is simply `undefined` so the check is skipped entirely | **silent** until job runs (`Cannot find workflow`) |
| 2 | `merge` entries need a real `value: {task, variable}` wrapper | `utils.js:544-554` (job-start's compile step, called *after* `validate()` passes) unconditionally reads `data.value.task` with no guard — a missing/misnamed wrapper throws `Cannot read properties of undefined (reading 'task')`. `validateTask` itself uses a defensive copy (`lib.js:411-413`, `value = {}`) and does NOT catch this | **hard crash, not part of validate()** — reproduces at save (via `calculateWorkflowSchema`, which also runs this compile step) |
| 3 | `push`: omit `incoming.job_id` | `utils.js:515-533` injects the real job id, then spreads authored `incoming` **over** it — an authored `job_id` silently wins and is wrong | **silent**, wrong data, not an error |
| 3 | `push.outgoing.job_variable_value` shouldn't be `{}` | No code anywhere reads/validates this value, only the key name | **not a platform-enforced rule** — empirical only, keep narrowly scoped |
| 4 | `parse` fields are `text`/`textObject` | `string/index.js:274-281` + `string/ph.json:1555-1585` are the real wiring; `stringToParse`/`result` don't exist. The generic `validateMethod` input/output name-mismatch check pushes this to `errors`, not `warnings` | **blocks job start** (not save) — `Cannot find match for input` |
| 5 | `objectToString.replacer: []` silently empties output | `object/index.js:59-63` passes `replacer` straight into `JSON.stringify` with zero guard | **silent**, no error ever |
| 6 | `$var` doesn't resolve inside array literal elements | `standardTaskIncomings` (`utils.js:469-475`) only classifies whole values via `typeof value === 'string'`; arrays fail that test and are stored as opaque static literals | **silent** |
| 7 | `$var` doesn't resolve inside nested object literal values | Identical mechanism to #6 — same function, same `typeof` check. Exception: `transformation.variableMap`, `runCode.data`, `runAgent.inputs`, and `runService(Static).params` are each handed to `standardTaskIncomings` one level down, so `$var` *does* resolve one level deep inside those four specific fields | **silent** (except the four named one-level-unwrapped fields) |
| 8 | `stringConcat`'s `stringN` array elements don't resolve `$var` | Same root cause as #6; `stringConcat` isn't specially handled in `compileIncomingValues`, falls to the generic (non-recursive) path | **silent** |
| 9 | Missing transition for a reached finish state → job hangs, no error | `finishTask.js:425-478` `addSubsuquentTaskUpdates`: `if (job.tasks[taskId].transitions[finishState])` has **no else branch** — if a task finishes in a state with no transition and wasn't pre-classified as a structural end task, nothing happens: no queue, no bookkeeping, no error. `validateTask`/`validateTransition` never check transition-state completeness, so this can't be caught even at job start. The `updateJob.js:294-301` safety net that prints "Job has no available transitions" only fires when the *whole* tracked graph structurally reaches zero incomplete — it typically doesn't fire for this exact case | **silent runtime hang**, worst case in this whole list |
| 10 | `evaluation` needs both `success` and `failure` transitions | A failed evaluation explicitly returns `undefined` (`evaluations.js:340-350`), mapped to `'failure'` state (`worker/helpers/utils.js:347-358`). No transition for that state → same silent-hang mechanism as #9 | **silent runtime hang** — confirmed live: 8 real instances of this exact gap found across the existing reference assets by the extended validator (see below) |
| 11 | forEach: last loop-body task needs an empty `{}` transition, not a loop-back to the forEach task id | `getEndTasks`/`markIterationTasks` (`jobStart.js:374-395`, `utils.js:6-50`) walk forward over standard transitions with no boundary check for re-entering the forEach task — a loop-back corrupts `endTasks`/`iterationTask` bookkeeping that `sendTask.js`'s `handleNextIteration` depends on to detect "iteration finished, start next" | **silent**, breaks loop iteration silently |
| 12 | `childJob` needs `actor: "job"` (or `"Pronghorn"` / a real task id) | `worker/helpers/utils.js:204-212` `getActor`: only `'Pronghorn'` and `'job'` are recognized by name; anything else is treated as a task id and indexed — throws a generic "Cannot read properties of undefined (reading 'owner')" if it isn't a real task id. No pre-check anywhere | **silent** until job runs |
| 12 | `childJob.variables.incoming.task` value doesn't matter | Both compile-time (`utils.js:511-513`) and every execution (`TaskWorker.js:304-306`) unconditionally overwrite it with the real task id | **not a real constraint** — removed from the gotcha list, it's a no-op field |
| 12 | `childJob` outgoing `job_details` must be `null` | `compileOutgoingValues` (`utils.js:702-721`) never inspects outgoing values, only key names | **not a platform-enforced rule** — empirical only |
| 13 | Adapter output shape `{response, headers, metrics}` lands one level deeper than expected | Not produced by `app-workflow_engine` (adapter/broker framework territory) but the *consequence* is confirmed: `finishTask.js:536-542` `getReturnValue` writes the **entire** return object verbatim into a single declared outgoing variable with no unwrapping | **structural, not a bug** — document as "how output binding works," not a gotcha |
| — | Referenced task must exist (`$var.<taskId>.<field>` → real task id) | `lib.js:1272-1279` pushes this to `errors` | **blocks job start** (not save) — wasn't previously in the gotcha list; added to the validator since it's free to check statically |
| 14 | Every task must have a key in `transitions`, even `{}` — including `workflow_end`, and any task with zero outgoing transitions | `utils.js`'s `validate()` BFS does `Object.keys(workflow.transitions[current])` with **no guard** for a missing key. Confirmed live by building a minimal workflow and bisecting: a task present in `tasks` but absent as a key in `transitions` crashes **save itself** (not job start) with a generic, completely unattributed `"Cannot convert undefined or null to object"` — no task name, no hint. A real canvas-saved document always carries an explicit `"workflow_end": {}` for exactly this reason; this had never been written down anywhere before this investigation | **hard crash on save** — this is NOT one of `validateTask`/`validateTransition`'s checks; it's an unguarded exception inside the same `validate()` call `saveWorkflow` invokes, which is why it manages to block save despite the "validate never blocks save" rule above (see the note on `Workflows.validate()` vs. a raw thrown exception in section on job start) |

**Note on the distinction above**: `Workflows.validate()` swallows anything pushed onto its `errors`/`warnings` *arrays* — that part never blocks save. But it does **not** catch a raw JS exception thrown by the validation code itself (e.g. `Object.keys(undefined)`); that propagates up as the `error` argument to `saveWorkflow`'s callback and does get treated as a hard failure. In other words: things the validator *checks for and reports* are advisory; things that make the validator *itself crash* are blocking. This is exactly why gotcha #14's "workflow_end needs an explicit `{}` entry" fact could survive completely undocumented until now — it's invisible to `/workflows/validate` (which also crashes the same way rather than reporting it as a normal finding).

## 3. What this means for the validator

Since almost every one of the above is silent (no error, ever, or an
error only after a job hangs indefinitely), `helpers/validate_workflow.py`
is not a nice-to-have — for most of these, it is the *only* thing that
will ever catch the mistake. This motivated extending it with checks that
are purely a function of the workflow JSON and don't need any live
platform call:

- Recursive `$var` scan inside array **and** nested-object literal values
  (generalizes the old array-only check to also cover #7/#8, since the
  underlying mechanism is identical — a single `typeof value === 'string'`
  test at the top level of `standardTaskIncomings`).
- `evaluation` tasks must have both a `success` and a `failure` standard
  transition (#10).
- `forEach` loop-body tasks must not transition back to their own
  `forEach` task id (#11).
- `childJob` `actor` must be `"Pronghorn"`, `"job"`, or an existing task
  id (#12).
- `merge` entries must have a real `value` object containing `task`
  (generalizes the old check — the bug is a missing/misnamed wrapper key,
  not specifically "used `variable` instead of `value`").
- Referenced-task existence: any `$var.<taskId>.<field>` must point at a
  task id that exists in `tasks` (this one **is** checked server-side at
  validate time, but only advisorily — worth catching earlier and for
  free since it's cheap to check statically).
- Removed the false constraint that `childJob.variables.incoming.task`
  matters — it's silently overwritten by the platform regardless of what
  is authored, so validating it was pure noise.

One important nuance the generalized `$var`-in-nested-structures scan had
to account for: `transformation.variableMap`, `runCode.data`,
`runAgent.inputs`, and `runService(Static).params` are each unwrapped one
level by `compileIncomingValues` before being handed to
`standardTaskIncomings`, so `$var` genuinely resolves one level deep
inside those four fields specifically. The validator only flags `$var`
found *beyond* that one level, and treats `merge`/`deepmerge`/`evaluation`/
`childJob`/`runAction` as fully custom-compiled (their real failure modes
are covered by the dedicated checks above, not the generic scan).

Not added, and deliberately left as prose-only documentation, because
they aren't statically checkable from JSON alone: `push.outgoing.job_variable_value`
non-`{}` and `childJob` outgoing `job_details: null` — the platform
doesn't enforce either, so flagging them would be inventing a rule with
no source-of-truth backing.

**Confirms the thesis in practice**: running the extended validator
against every existing reference asset in this repo found **8 real,
previously-undetected instances** of gotcha #10 (evaluation tasks missing
a `success` or `failure` transition) in `itential-platform-configuration-management.json`
— a workflow reused as a shared component across several other "known
good" vendor assets, so the same 4 broken tasks show up repeated in
`vendor-arista-eos.json`, `vendor-cisco-ios.json`, and
`vendor-juniper-junos.json` too. These are workflows that would save
successfully, start successfully, and then hang forever the moment
execution reaches the missing state — exactly the failure mode this
whole investigation was trying to eliminate. (`vendor-arista-eos.json`
also still carries the previously-found 14 project-scoped `childJob.workflow`
violations from the prior validator pass — left unfixed pending dedicated
attention, not blindly patched.)

## 4. Other real checks worth knowing about

Found in `app-workflow_engine/server/utilities/lib.js`, all part of the
same `validateTask`/`validateTransition` path (which blocks job start for
`errors`, never blocks save, and never checks anything for `warnings`):
adapter existence, job-variable naming convention, static value type/enum
checking, cross-task type compatibility on `$var` references, dangling
`$var` reference detection, `invalidTaskActors` enforcement, manual task
`groups`/`view` requirements, `transformation` task `tr_id` existence,
unsafe-regex detection, revert/standard transition conflicts, and BFS
reachability of every task from `workflow_start`. Useful signal if you
want it early — call `/workflows/validate` explicitly — but don't assume
`/workflows/save` succeeding means any of this passed, and don't assume a
job starting means the `warnings`-level ones passed either.

## 5. From lint-after to construct-correctly: `helpers/workflow_builder.py`

Everything above is still framed as "check a hand-authored JSON document
after the fact." That's reactive by construction — every new task type
can introduce a new footgun nobody's discovered yet, and an agent has to
recall every rule correctly, every time, when hand-assembling the final
document in one shot.

The canvas UI doesn't have this problem. Not because it validates
better — per section 1, its construction-time guardrails have zero
server-side backing — but because it makes wrong states **unconstructible
in the first place**: task ids are generated, not typed; `$var`
references are assembled from cascading pickers over tasks that already
exist, never typed as a raw string that could land in the wrong place;
GoJS's `linkingTool` physically refuses to let you draw a self-loop, a
duplicate transition, or a loop-boundary violation.

`helpers/workflow_builder.py` ports that same construction-time state
machine (not the UI, just the logic behind it) into a small Python API:
`add_task()` (schema-driven field validation + task-specific defaults,
mirroring `getTasksData`), `connect()` (ports `insertLink`/`checkForPath`/
`validateLoopTransitions` from `Diagram.jsx`/`utils/diagram.js` verbatim),
`ref()`/`job_ref()` (the only way to wire a `$var` reference — structurally
cannot land inside a nested static value, mirroring `TaskVariableSelect`/
`InputQuery`), and `finish()` (checks completeness using the graph it
already built incrementally — reachability, evaluation success+failure,
forEach closure).

**Live-tested end to end against a real platform + Gateway5 cluster**,
not just offline: built a `runCode` task through this API, ran it through
`validate_workflow.py` (0 violations), saved it via
`workflow_builder/workflows/save` (200, no errors), started a job via
`operations-manager/jobs/start`, and confirmed both the job and the task
reached `status: "complete"`. This exercise is what found gotcha #14
above — the builder's first attempt at `to_document()` omitted the
`workflow_end: {}` transitions entry (nobody writes that by hand, because
nobody knew it was required), and the live save crashed with the exact
generic error now explained in this document. Fixed once, in one place,
inside `to_document()` — every workflow built through this API gets it
correct from now on, instead of every future hand-authored document
risking the same crash again.

`validate_workflow.py` remains as the backstop: for legacy/hand-authored
JSON this API doesn't cover yet, and as a second, independent check on
anything `workflow_builder.py` produces.

## 6. Findings from live sub-agent testing (childJob/merge/evaluation, NetBox + Gateway5)

Once `add_merge`/`add_evaluation`/`add_child_job` existed, two independent
agents with no prior context on this work were given only the redesigned
skill and told to build real workflows against a live platform
(`itential-se-poc-dev01`) — cold, the way any future user of this skill
actually would. This surfaced real defects the offline test suite hadn't
caught, plus one more confirmed-wrong documentation claim:

- **`add_evaluation()` didn't set `all_true_flag` on each group entry, only
  the top-level field.** A real evaluation needs `all_true_flag` as a
  sibling of `evaluations` inside every `evaluation_groups[]` entry, not
  just once at the top. Without it, an evaluation task ran, correctly
  resolved `operand_1`/`operand_2`, and still finished in `failure` state
  with empty `outgoing: {}` — silent, no error, and `validate_workflow.py`
  didn't catch it either since nothing here is a JSON-shape violation.
  Fixed by having `add_evaluation()` set the flag in both places from one
  argument.
- **`add_child_job()`'s optional `data_array`/`loopType` fell through to
  catalog-driven type defaulting when a caller had loaded
  `add_task_details()` for childJob** (exactly as this doc's own "Extending
  the catalog with per-field types" guidance recommends) — `data_array`
  defaulted to `[]` (its declared type) and `loopType` to `"parallel"`
  (its first enum value), silently turning an intended single-child call
  into an empty parallel loop. Fixed by having `add_child_job()` always
  pass explicit `data_array=''`/`loop_type=''` unless the caller overrides,
  so these two fields never reach the generic per-type defaulting path.
- **SKILL.md's documented shape for an evaluation operand's inline `query`
  key was wrong**, and had been since before this session's changes:
  it showed `query` nested *inside* `operand_1`. The real shape — confirmed
  against dozens of real evaluation entries across every vendor asset in
  this repo, and independently against a live task run — has `query`
  (applying to `operand_1`) and `rightQuery` (applying to `operand_2`) as
  **siblings** of `operand_1`/`operand_2`/`operator` in the evaluation
  entry itself. The nested-in-operand shape silently compiles the entire
  raw operand object instead of drilling into it. Fixed in SKILL.md.
- **No structural path existed to set `adapter_id`.** It's real, always
  required at runtime, and never declared in any task's schema (tasks.json
  or the dereferenced `getTaskDetails` schema) — so `add_task()` rejected
  it as an unknown field for every adapter task, making it impossible to
  build a correct adapter task in one call. Fixed by special-casing
  `location == 'Adapter'` in `add_task()`: `adapter_id` is added to the
  allowed field set and required.
- **`inputSchema`/`outputSchema` submitted on save are discarded, not
  stored.** `saveWorkflow` always recomputes both from the `$var.job.*`
  references actually found in the task graph (`getWorkflowSchema` →
  `calculateWorkflowSchema`, confirmed in `cog.js`) — a declared-but-
  unreferenced input silently disappears. This wasn't previously
  documented anywhere in this skill. `to_document()` now labels its
  placeholder schemas as such, and a new `expose()` builder method wires a
  task's outgoing field to a job variable (the earlier API only covered
  `incoming` via `ref()`/`job_ref()`, leaving no construction-time way to
  make a value show up as workflow output).
- **No `nodeLocation` was ever assigned**, so every builder-produced
  workflow rendered as a single overlapping stack at `(0, 0)` in Studio.
  `to_document()` now runs a simple BFS-order vertical layout (single
  spine, `+108px` per row, matching this skill's documented layout
  convention) — not the full fork-offsetting algorithm, but enough that a
  linear chain of tasks renders sensibly without manual patching.

Both agents independently confirmed the core design thesis in the same
run: `validate_workflow.py` reported zero violations on every workflow
they built, and every one of the defects above was still real and
job-breaking despite that — because the underlying platform gives no
error either, at save or at job start, for any of them. Static JSON
validation and construction-time correctness are complementary, not
substitutes for each other; this round of testing only found bugs because
real agents ran real jobs against a real platform, not because a script
flagged something.
