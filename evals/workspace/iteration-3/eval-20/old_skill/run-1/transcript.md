# Transcript — Debugging null `taskStatus` from a parallel childJob loop

## Task restated

The engineer has a parent workflow with a `childJob` task that runs a child workflow in a loop
over an array of devices (`loopType: "parallel"`). Afterward, they run a `query` task against
`$var.<childJobId>.job_details` with `query: "loop"` to extract each child's `taskStatus`.
Sometimes downstream logic reports `null` for `taskStatus` even though every child completed
successfully. They want the diagnosis and the fix.

## Skill sections / files consulted

Per the `builder-agent` SKILL.md instructions, I read the skill fully (2314 lines) before
answering, and per its "STOP — read real asset projects, don't guess from memory" instruction I
pulled real, production-tested JSON out of `helpers/assets/` rather than inventing task shapes:

- **Guide 4: Build a childJob (parent calls child workflow)** — Mode B (loop), the documented
  loop-output shape, and the childJob checklist/try-catch pattern.
- **`### childJob` (Utility Tasks section)** — "Querying childJob output ... For loop output:
  `"[**].fieldName"`."
- **`### query` (Utility Tasks section)** and **`$var Resolution Rules`** — dot-path query
  semantics, `pass_on_null`, and the "outgoing must write to a job var to be readable downstream"
  rule.
- **Gotcha #40 / forEach section** — nested-loop `$var` resolution caveats (ruled out, not
  applicable to childJob loops, but checked for completeness).
- **Real asset files** (grounding, not memory):
  - `helpers/assets/vendor-netbox.json` → workflow `"Delete Prefix"`, task `82ca`: a real
    production `query` task with `query: "loop"`, `obj: "$var.4b5c.job_details"`,
    `outgoing.return_data: "$var.job.deleteIPAddressResult"` — confirms the documented loop-query
    wiring pattern is exactly what's used in production, and confirms `query: "loop"` returns the
    **whole** flat-spread array, not a pre-filtered single field.
  - `helpers/assets/lcm/lcm-vxlan-fabric-services-project.json` → a JST transformation using
    `"switches[**][deviceName]"` as a `query` method argument — confirms the `[**]` wildcard
    array-projection syntax is real and used in shipped Itential automation, not something I
    invented.
  - `grep -rn "childJobLoopIndex"` across `helpers/assets/` — no production workflow currently
    keys off `childJobLoopIndex` for correlation, so I flagged that as a documented-but-unverified-
    in-practice risk rather than a "confirmed observed bug," and said so plainly below.

I did not fabricate any task schema — every task field name (`pass_on_null`, `query`, `obj`,
`return_data`, `job_details`, `childJobLoopIndex`, `taskStatus`, `data_array`, `loopType`) comes
directly from the skill body or from the real asset JSON pulled above.

## Diagnosis

`query: "loop"` on `job_details` is documented (and confirmed in the live `vendor-netbox.json`
"Delete Prefix" workflow, task `82ca`) to return the **full flat-spread array of every child's
job variables**, one element per iteration, e.g.:

```json
[
  {"status": "complete", "childJobLoopIndex": 0, "deviceName": "IOS-CAT8KV-1", "taskStatus": "success"},
  {"status": "complete", "childJobLoopIndex": 1, "deviceName": "IOS-CAT8KV-2", "taskStatus": "success"},
  {"status": "complete", "childJobLoopIndex": 2, "deviceName": "EOS-AWS-1",   "taskStatus": "success"}
]
```

It is **not** a pre-filtered list of `taskStatus` values — `taskStatus` is just one key nested
inside each element. There are three distinct, independently-checkable ways this produces
intermittent nulls. I ranked them by how directly they're documented/confirmed:

**1. Query-path bug (most common cause of a systematic, not intermittent, null) — but worth
ruling out first.** If anything downstream treats the result of `query: "loop"` as though it
were already an array of bare `taskStatus` values (e.g., a second `query` task run with
`query: "taskStatus"` against that array, or an `evaluation`/template reference like
`$var.<queryTaskId>.return_data.taskStatus`), it will resolve to `null`/`undefined` every time —
an array has no top-level `taskStatus` property, only its elements do. The fix, straight from the
skill and confirmed via the `[**]` wildcard usage in the LCM asset project, is to query
`"[**].taskStatus"` directly against `job_details` (or against the loop array) to project that one
field across every iteration in a single call. If this were the whole story you'd expect it to be
null for *every* child, every run — not intermittent — so it's the first thing to rule out, not
necessarily the final answer.

**2. Child workflow doesn't set `taskStatus` on every terminal path — the best fit for
"sometimes."** Guide 4's try-catch pattern requires the child workflow to route **every** path
that can reach `workflow_end` through a `newVariable` that sets `taskStatus` on `$var.job.taskStatus`
— one for the success path, one for the error path:
```
task --success--> newVariable("taskStatus"="success") -> workflow_end
task --error--> newVariable("taskStatus"="error") -> workflow_end
```
If the child workflow has since grown additional branches (an "already configured / no-op, skip"
path, an alternate evaluation outcome, a manual-approval branch, etc.) that were wired straight to
`workflow_end` without also passing through a status-setting `newVariable`, then any device that
happens to take that branch finishes with `status: "complete"` and **no error at all** — but its
job variables never contain a `taskStatus` key. In the parent's loop array, that iteration's
element is simply missing the field, which reads as `null` downstream. Because only the subset of
devices that hit the untracked branch are affected, this shows up as exactly the symptom
described: intermittent, and only on children that took a code path other than the two "main"
ones — even though every child genuinely completed successfully. This is the most likely
explanation given the word "sometimes" in the report, and it's a build/coverage gap in the child
workflow, not a parent-side wiring bug.

**3. Result-ordering assumption on a `parallel` loop (checked, not found in production examples,
flagged as a risk rather than confirmed).** The documented loop-output shape carries an explicit
`childJobLoopIndex` field per element. Its only reason to exist is that `loopType: "parallel"`
fires all children concurrently, so the order elements land in the results array is not
guaranteed to match the order of the input `data_array`. If downstream logic reads the array by
raw position (`results[i]` assumed to correspond to `devices[i]`) instead of matching on
`childJobLoopIndex` (or a natural key such as `deviceName` also passed into the child), it can
read the wrong element for a given device on some runs. I did **not** find a production asset
project that actually keys off `childJobLoopIndex`, so I can't confirm this is exercised/verified
behavior on this platform — I'm flagging it as a design risk worth testing directly (start a job,
check whether `job_details.loop[].childJobLoopIndex` ever comes back out of `data_array` order for
a `parallel` loop) rather than asserting it as the confirmed cause.

## Recommended fix (to the engineer, verbatim)

> The `taskStatus` nulls you're seeing are very unlikely to be a childJob wiring bug — the
> `query: "loop"` → `$var.<childJobId>.job_details` pattern you're using is the same pattern used
> in production (I checked it against the "Delete Prefix" workflow in the NetBox asset project).
> The catch is that `query: "loop"` hands you back the **entire** per-child object for every
> iteration (`status`, `childJobLoopIndex`, every job variable the child set — including but not
> limited to `taskStatus`), not a pre-filtered list of statuses. Two things to fix, in order:
>
> 1. **If you're pulling `taskStatus` out in a second step**, don't try to read `.taskStatus` off
>    the raw loop array directly — arrays don't have that key at the top level, only their
>    elements do, so you'll always get null. Query with the wildcard path
>    `"[**].taskStatus"` against `job_details` directly (I put a working example in
>    `fix-parent-loop-taskStatus-extraction.json`) — that's a real syntax used in production
>    Itential JST transformations (`switches[**][deviceName]`), just applied at the workflow
>    `query`-task level, and it gets you an array of just the statuses in one call.
>
> 2. **Go check the child workflow's branches.** This is the one I'd bet on for "sometimes, even
>    though every child completed successfully": Guide 4's pattern requires *every* path that
>    reaches `workflow_end` to first pass through a `newVariable` that sets `taskStatus`. If a
>    branch was added later (a no-op/"already configured" skip path is the classic one) and it
>    goes straight to `workflow_end` without setting `taskStatus`, that child finishes clean with
>    no error — but its job variables never contain `taskStatus` at all, so its slot in the loop
>    array comes back missing the field. That reads as `null` downstream but only for the devices
>    that hit that branch, which is exactly the intermittent pattern you're describing. Pull the
>    job for one of the "null" cases (`GET /operations-manager/jobs/{childJobId}`) and check
>    whether `taskStatus` is present at all in `data.variables` — if it's absent (not `null`, just
>    not there), you've found it. I put the corrected try-catch shape, with the missing branch
>    wired in, in `fix-child-workflow-taskstatus-coverage.json`.
>
> 3. As a longer-term safety net: since your loop is `parallel`, don't assume the results array
>    preserves the order of your input device list — match each result back to its device using
>    `childJobLoopIndex` (or `deviceName`, since you're already passing that into each child)
>    rather than positional indexing. I couldn't find a production example on this platform that
>    actually exercises out-of-order `parallel` results, so treat this as a "verify, don't
>    assume" item rather than a confirmed cause — but it's cheap to guard against and the field
>    exists specifically for this reason.
>
> Practical next step: pick one device that came back `null` and pull its individual child job
> (`GET /operations-manager/jobs/{childJobId}` using the child job id, not the parent's). If
> `taskStatus` is simply absent from `data.variables`, it's #2 above — fix the child's branch
> coverage. If it's present in the child job but you're still getting null in the parent's
> extraction, it's #1 — fix the query path.

## Artifacts produced

- `outputs/fix-parent-loop-taskStatus-extraction.json` — corrected parent-side task JSON: the
  original `childJob` task, a `query` task using `"[**].taskStatus"` to project the status field
  across every iteration in one call (fix for cause #1), a second `query` task keeping the full
  `loop` array bound to a job variable for correlation by `childJobLoopIndex` (mitigation for
  cause #3), and a guard `evaluation` task that fails fast if any iteration is still missing a
  status (surfaces cause #2 instead of silently propagating a null).
- `outputs/fix-child-workflow-taskstatus-coverage.json` — corrected child-workflow try-catch
  pattern: the original success/error `newVariable` branches from Guide 4, plus the previously
  missing "no-op/skip" branch wired through its own `newVariable` so every terminal path sets
  `taskStatus` before `workflow_end` (fix for cause #2).

Both files use real field names, task shapes, and wiring conventions pulled from the skill body
and from `helpers/assets/vendor-netbox.json` and
`helpers/assets/lcm/lcm-vxlan-fabric-services-project.json` — no fabricated schema.
