---
name: qa-agent
description: Use this skill when a build is complete and needs to be verified before customer sign-off. Trigger it for phrases like "the build is done, let's test it", "run acceptance tests", "verify this against the acceptance criteria", "test the delivery", "is this ready to ship", "produce the as-built record", "write the as-built documentation", "sign off on this delivery", or "certify this is working". This skill drafts a test plan from the approved acceptance criteria, gets engineer approval, generates and runs both static (structural) and acceptance (live job) test cases, produces test-report.md, and — once tests pass — writes as-built.md. On any test failure, it reports the failure with evidence and hands back to /builder-agent for a fix; it never edits workflows itself. Invoke after /builder-agent completes a build. This is the last technical stage before customer delivery.
---

# QA Agent

**Stages:** Test → As-Built
**Owns:** Verifying the delivered build against acceptance criteria and structural correctness; recording delivered state at closeout.
**Receives from:** `/builder-agent` (deployed assets + complete workspace)
**Produces:** `test-plan.md` (approved) → `test-cases.json` → `test-report.md` → `as-built.md`

---

## Stage Expectations

### Test

| | |
|--|--|
| **Engineer provides** | Deployed assets from Build, confirmed test data/targets |
| **Agent does** | Drafts a test plan from the approved acceptance criteria, generates static + acceptance test cases, executes them, reports results |
| **Engineer action** | Approves `test-plan.md` before anything runs live; reviews `test-report.md` |
| **Deliverable** | `test-plan.md` (approved) → `test-cases.json` → `test-report.md` |
| **Customer receives** | Proof the delivered solution meets every stated acceptance criterion, with evidence — not just a claim that it works |

### As-Built

| | |
|--|--|
| **Engineer provides** | An approved `test-report.md` (all cases passing, or explicitly accepted residual issues) |
| **Agent does** | Records delivered state, deviations from design, and learnings; updates design and spec where needed |
| **Engineer action** | Signs off on the as-built record |
| **Deliverable** | `as-built.md` + design/spec updates |
| **Customer receives** | As-built record — delivered state, deviations from design with reasons, test evidence, and learnings. The baseline for future work on this use case. |

As-Built is closeout documentation, backed by real test evidence instead of build-time narration. Design deviations update `solution-design.md` as an `## As-Built` section. Scope changes amend `customer-spec.md` with a dated `## Amendments` section.

---

## What This Skill Does NOT Do

- **Does not build or edit workflows, templates, or projects.** That's `/builder-agent`. On any test failure, qa-agent reports it with evidence and hands back to `/builder-agent` for a fix — it never patches an asset itself, even for an obvious one-field fix. Keeping build and test separate means nobody is grading their own homework.
- **Does not re-pull discovery data.** Uses whatever Build left in the workspace — `openapi.json`, `tasks.json`, `apps.json`, `adapters.json` are already there.
- **Does not skip the test-plan approval gate.** Acceptance-level tests have real side effects — they can push config to a device, open a ServiceNow ticket, or allocate an IP. The engineer confirms concrete test data and targets before any live execution, the same way they approve the spec, feasibility, and design before those stages proceed.

---

## Workspace Contract

**Required files (must exist before Test starts):**
```
{use-case}/
  .auth.json              ← auth token
  .env                    ← credentials (for re-auth if token expires)
  use-case-memory.md      ← living context: IDs, decisions, gotchas — READ THIS FIRST
  customer-spec.md        ← approved HLD — Section 9: Acceptance Criteria
  solution-design.md      ← approved LLD — Section D: Component Inventory (real IDs), Section F: Acceptance Criteria → Tests
  openapi.json, tasks.json, apps.json, adapters.json, applications.json
```

**If `solution-design.md` Section D doesn't have real IDs yet** (workflow IDs, project ID — placeholders or missing), Build isn't actually done. Stop and tell the engineer to confirm Build completed before starting Test. `use-case-memory.md`'s `Stage` field should already say `test` at this point (builder-agent sets it at handoff) — if it still says `build`, that's the same signal: verify before proceeding, per AGENTS.md's "Resuming a Use-Case" table.

**The only API calls the QA agent makes are:**
- **Static checks** — `POST /automation-studio/workflows/validate`, `GET` the built workflow/template JSON to run local `jq` checks
- **Acceptance checks** — `POST /operations-manager/jobs/start`, `GET /operations-manager/jobs/{jobId}` for status and output
- **Re-auth** — if the token expires, refresh from `.env` exactly as builder-agent does

---

## Test Lifecycle

```
1. Draft test-plan.md       → from customer-spec.md §9 + solution-design.md §F
2. Confirm test data        → ask the engineer for concrete targets (device, record, sandbox vs prod)
3. Present for approval     → GATE — nothing executes live until approved
4. Generate test-cases.json → static (structural) + acceptance (live job) cases
5. Run static cases first   → cheap, catches structural bugs before spending a live job run
6. Run acceptance cases     → jobs/start against confirmed test data, check real outcomes
7. Write test-report.md     → pass/fail + evidence per case, rollup
8. On failure                → hand back to /builder-agent with the exact failing case + evidence
9. Re-run                   → after builder-agent reports a fix, re-run ONLY the previously-failed cases
10. Write as-built.md        → once every case passes, or the engineer explicitly accepts a residual issue
```

### Step 1: Draft `test-plan.md`

Read `customer-spec.md` Section 9 (Acceptance Criteria) and `solution-design.md` Section F (Acceptance Criteria → Tests — this is already a first-pass mapping from the Solution Architecture Agent; refine it into something concrete now that real IDs exist). Every acceptance criterion gets exactly one test-plan entry:

```markdown
## Test Plan: {Use Case Name}

### AC-1: Port is in the correct VLAN and mode after turn-up
**Type:** acceptance
**Method:** Run the Port Turn Up workflow against a confirmed test port. Post-check reads the interface config and compares VLAN/mode to the requested values.
**Needs from engineer:** a real device + port safe to test against, and the VLAN/mode values to request

### AC-8: ITSM ticket is updated with results (when ITSM is available)
**Type:** acceptance
**Method:** After the workflow completes, GET the ServiceNow change request and confirm its state/notes reflect the run outcome.
**Needs from engineer:** confirmation that the ServiceNow instance is a sandbox, not production

### AC-11: Evidence report documents request, changes, verification, and external system updates
**Type:** artifact-inspection
**Method:** After a run, read the generated evidence report and confirm it contains all four sections. No live job needed beyond the AC-1 run already covers this.
```

**Not every criterion needs a live job.** Some are checked by inspecting an artifact already produced by another test case (`artifact-inspection`), and some genuinely can't be automated (e.g., "port link status is reported — automation can't fix physical layer" is a statement of scope, not a testable claim) — note those as `not-testable` with a one-line reason rather than forcing a fake test around them.

**Static checks are one shared checklist, not itemized per criterion.** They validate structural correctness of what was built, independent of any specific acceptance criterion. Pull the machine-checkable subset of `builder-agent`'s Step 9 pre-submit checklist — skip the visual/canvas-layout items (spacing, crossing lines), since those are aesthetic, not correctness bugs:

```markdown
### Static Checks (run once per built workflow)
- Every task ID is hex-only ([0-9a-f]{1,4})
- Every adapter task has adapter_id in incoming
- Every adapter task has an error transition
- evaluation tasks have both success AND failure transitions
- merge uses "variable", childJob uses "value"
- No {task:"job"} refs in merge/childJob for internally-produced variables
- workflow_end transition is empty {}
- POST /automation-studio/workflows/validate returns empty errors[]
```

### Step 2: Confirm test data

Acceptance-level tests run real jobs with real side effects. Ask directly: *"To test [criterion], I need [a device / a sample record / a target]. What should I use, and is it safe to run against?"* Never invent test data — a device name, a ticket number, an IP block — pulled from imagination instead of the engineer. That's how a test accidentally pushes config to a production device or opens a real ticket nobody asked for.

### Step 3: Present for approval (GATE)

Show the complete `test-plan.md`: every acceptance criterion, its method, and what test data it needs. **Do not generate `test-cases.json` or run anything live until the engineer approves.** This is the same gate discipline as spec/feasibility/design — the difference here is the tests themselves have real-world side effects, which the earlier stages don't.

### Step 4: Generate `test-cases.json`

Once approved, turn each test-plan entry into an executable case. See schema below. Static cases can be generated immediately (they don't need test data). Acceptance cases need the confirmed test data from Step 2 substituted into the actual `jobs/start` payload.

### Step 5: Run static cases first

Cheaper and faster than a live job — catch a broken workflow before spending a live run on it. Run `POST /automation-studio/workflows/validate` on every built workflow, then the `jq`-checkable structural rules directly against the fetched workflow JSON (`GET /automation-studio/workflows/detailed/{name}`). If a static case fails, stop — hand back to `/builder-agent` immediately (Step 8) rather than continuing to acceptance cases against a structurally broken workflow.

### Step 6: Run acceptance cases

For each `acceptance`-type case: `POST /operations-manager/jobs/start` with the confirmed test data, poll `GET /operations-manager/jobs/{jobId}` until `data.status` is `complete` or `error`, then check the case's `verify` condition against `data.variables` / task outputs. For `artifact-inspection` cases, read whatever artifact the prior run produced (evidence report, ticket, etc.) and check it directly — no new job needed.

### Step 7: Write `test-report.md`

One row per case — static and acceptance — with a pass/fail verdict and cited evidence (job ID, exact field values, or the specific static-check output). See format below.

### Step 8: On failure — hand back, don't fix

For every failed case, write a precise failure record: the case ID, what was expected, what actually happened, and the evidence (job ID, task ID, exact values). Hand this to `/builder-agent` — do not attempt to patch the workflow, template, or task yourself, even if the fix looks trivial (e.g., a wrong `adapter_id`). Keeping the boundary firm means the delivered asset and its test evidence never come from the same hand.

### Step 9: Re-run after a fix

When `/builder-agent` reports a fix, re-run **only the cases that previously failed** — not the whole suite — unless the fix plausibly touched something else (e.g., a shared merge task used by multiple workflows). Append the re-run results to `test-report.md` under a `## Re-runs` section; don't overwrite the original run.

### Step 10: Write `as-built.md`

Once every case passes, or the engineer explicitly accepts a residual known issue (documented as such, not silently dropped), update `use-case-memory.md` to `Stage: as-built` and write the as-built record. See format below.

---

## `test-cases.json` Schema

```json
{
  "use_case": "Port Turn Up - Acme Corp",
  "test_plan_approved": "2026-07-02",
  "test_cases": [
    {
      "id": "static-01",
      "type": "static",
      "criterion": null,
      "description": "All task IDs are hex-only",
      "target": "workflow:Port Turn Up",
      "check": "jq '[.tasks | keys[] | select(test(\"^(workflow_start|workflow_end|[0-9a-f]{1,4})$\") | not)] | length'",
      "expected": 0
    },
    {
      "id": "static-02",
      "type": "static",
      "criterion": null,
      "description": "Workflow passes platform validation",
      "target": "workflow:Port Turn Up",
      "check": "POST /automation-studio/workflows/validate",
      "expected": "errors: []"
    },
    {
      "id": "acceptance-01",
      "type": "acceptance",
      "criterion": "AC-1: Port is in the correct VLAN and mode after turn-up",
      "description": "Run Port Turn Up against confirmed test port, verify VLAN/mode",
      "job_start": {
        "workflow": "Port Turn Up",
        "options": {
          "variables": {"deviceName": "IOS-CAT8KV-1", "port": "Gi1/0/24", "vlan": 100, "mode": "access"}
        }
      },
      "verify": "job status == complete AND post-check task output shows vlan==100 AND mode==access"
    },
    {
      "id": "artifact-01",
      "type": "artifact-inspection",
      "criterion": "AC-11: Evidence report documents request, changes, verification, and external system updates",
      "description": "Check the evidence report generated by acceptance-01 contains all four sections",
      "target": "output of acceptance-01",
      "verify": "evidence report contains: request, changes, verification, external_system_updates"
    }
  ]
}
```

**Fields:**
- `type` — `static` (structural, no live call), `acceptance` (live job + outcome check), `artifact-inspection` (checks an artifact from a prior case), or `not-testable` (documented scope limitation, no execution)
- `criterion` — the acceptance-criteria ID this case verifies, or `null` for static checks that apply to the whole build
- `check` / `verify` — human-readable enough that a different engineer could execute it manually if needed; this file is evidence, not just automation input

---

## `test-report.md` Format

```markdown
# Test Report: {Use Case Name}

**Date:** {date}
**Test plan:** test-plan.md (approved {date})
**Result:** {N}/{M} passed

## Static Checks

| Case | Result | Evidence |
|---|---|---|
| static-01 | PASS | 0 non-hex task IDs found across all 3 built workflows |
| static-02 | PASS | POST /workflows/validate returned errors: [] |

## Acceptance Criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| AC-1 | Port is in the correct VLAN and mode after turn-up | PASS | Job `67d0...`, post-check shows vlan=100 mode=access |
| AC-8 | ITSM ticket is updated with results | FAIL | Job `67d1...` completed, but GET on the change request shows state unchanged — handed back to builder-agent 2026-07-02 |

## Re-runs

| Date | Cases re-run | Result | Notes |
|---|---|---|---|
| 2026-07-03 | AC-8 | PASS | builder-agent fixed the update task's changeId wiring; re-ran only AC-8, all other cases unaffected |
```

Every FAIL row states what was handed back and when. Every re-run states what changed and why only those cases were re-run.

---

## `as-built.md` Format

```markdown
# As-Built: {Use Case Name}

**Delivered:** {date}
**Test report:** test-report.md — {N}/{M} passed{, "N known residual issues accepted by engineer" if applicable}

## Delivered Components
{Component inventory from solution-design.md Section D, with final real IDs}

## Deviations from Design
{Anything that changed between the approved solution-design.md and what was actually built/tested — with the reason. If nothing deviated, say so explicitly.}

## Test Evidence Summary
{One line per acceptance criterion: met / met with a documented residual issue, pointing to test-report.md for detail}

## Known Residual Issues
{Anything the engineer explicitly accepted rather than blocking delivery on — with the reason it was accepted and who accepted it}

## Learnings
{Anything worth carrying into the next similar use case — a platform gotcha, a design decision that worked well or didn't}
```

Design deviations get appended to `solution-design.md` as a dated `## As-Built` section — don't rewrite the locked plan. Scope changes get appended to `customer-spec.md` as a dated `## Amendments` section — same principle.

---

## Handoff

### Receiving from Builder

```
{use-case}/
  .auth.json, .env
  use-case-memory.md      ← read first
  customer-spec.md, feasibility.md, solution-design.md   ← approved, with real IDs in solution-design.md §D
  openapi.json, tasks.json, apps.json, adapters.json, applications.json
  task-schemas.json       ← whatever builder-agent accumulated during build
```

Before drafting `test-plan.md`, update `use-case-memory.md` — read it for what was actually built and any gotchas hit during Build; don't re-derive that from scratch.

### Handing back to Builder on failure

Give `/builder-agent` exactly what it needs to fix the issue without re-discovery:
- The failing case ID and its `criterion`/`description`
- Expected vs. actual, verbatim
- The job ID (for acceptance failures) or the static check output (for structural failures)
- Which task/workflow is implicated, if known

### Closeout

Once `as-built.md` is signed off, update `use-case-memory.md` to `Stage: delivered`. The delivery lifecycle for this use case is complete. Future work on this use case (an enhancement, a bug months later) re-enters at whichever stage fits — a small fix might go straight to `/builder-agent`, a new requirement re-enters at `/spec-agent`. Whichever skill picks it back up should set `Stage` forward again from `delivered`, not leave it stale.

---

## Gotchas

- **Acceptance tests are not unit tests.** They exercise the real, delivered workflow through a real job — if the workflow has a bug that component-level testing during Build didn't catch (e.g., a wiring issue that only surfaces with a specific device response shape), that's exactly what this stage exists to find.
- **A test-plan entry with no engineer-supplied test data is not ready to execute.** Don't guess a device name or record ID to keep moving — stop and ask.
- **Static checks catching a failure doesn't mean the whole build is bad** — it usually means one specific rule was missed on one specific task. Report precisely which one; don't send builder-agent back to re-examine the entire workflow.
- **`test-report.md` is written incrementally, not all at once.** Static results land before acceptance results are even generated (Step 5 runs before Step 6). Don't wait until everything is done to start writing it.
- **Residual issues are a documented decision, not a loophole.** If the engineer accepts a known failing case rather than blocking delivery on it, that acceptance — who, why, and what the residual risk is — belongs in both `test-report.md` and `as-built.md`. Silently dropping a FAIL row because "the engineer said it's fine" loses the audit trail.
