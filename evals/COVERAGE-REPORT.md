# Skill Evaluation Coverage Report

**Date:** 2026-03-25
**Skills:** spec-agent, solution-arch-agent, builder-agent, itential-mop, flowagent, iag

---

## Summary

| Skill | Evals | Assertions | Critical | Structural | Negative |
|-------|-------|------------|----------|------------|----------|
| spec-agent | 5 | 18 | 6 | 11 | 1 |
| solution-arch-agent | 6 | 23 | 8 | 13 | 2 |
| builder-agent | 27 | 82 | 39 | 40 | 3 |
| itential-mop | 6 | 15 | 5 | 9 | 1 |
| flowagent | 1 | 1 | 0 | 0 | 1 |
| iag | 10 | 38 | 16 | 21 | 2 |
| **Total** | **55** | **177** | **74** | **94** | **10** |

**2026-07-02 update:** Removed flowagent evals 1–5 and the "FlowAgent" domain-coverage rows (issues #49–52) — both were built against the deprecated prototype FlowAI API (`//`-format tool identifiers, `{details: {...}}` request wrapper, `/flowai/missions`, `/flowai/adhoc_agent`). The flowagent skill was rewritten against the current Agent Project Service / Model Registry Service / Tools Service / Agent Session Manager APIs; only the skill-trigger negative eval survived (renumbered to id 1). Fresh evals against the current API are a separate follow-up, not yet written.

**2026-06-30 update:** Added 8 builder-agent evals (ids 20-27) covering issues #46-49, #51-54 (childJob query extraction, `{task:"job"}` inputSchema pollution, ViewData schema, makeData+childJob-merge, restCall response shape, childJob loop enrichment, forEach constraints, LCM Create completeness). Ran the official skill-creator executor→grader pipeline (`evals/workspace/iteration-3/`) old-skill-vs-new-skill: **new skill 100% pass rate, old (pre-fix) skill 71.8%, zero regressions** on the 5 pre-existing evals re-run alongside the 8 new ones. See `evals/workspace/iteration-3/benchmark.md` and `review.html` for the full breakdown. One pre-existing assertion (builder-agent eval 4, "makeData outputType is 'json'") was corrected after the grader flagged it as encoding an incorrect platform-semantics assumption — the task asks for a JSON *string*, and `outputType: "string"` is the platform-correct choice, not `"json"`.

---

## Lifecycle Coverage

### Requirements Stage (spec-agent)

| # | Behavior | Eval |
|---|----------|------|
| 1 | Forks spec to customer-spec.md without overwriting existing | spec-agent:1 |
| 2 | Does NOT authenticate before spec is selected | spec-agent:1 |
| 3 | Sets expectations for full lifecycle (Requirements → As-Built) | spec-agent:1 |
| 4 | Saves .env for later auth, hands off to /solution-arch-agent | spec-agent:1 |
| 5 | OAuth uses application/x-www-form-urlencoded (explore path) | spec-agent:2 |
| 6 | Saves .auth.json for downstream skills | spec-agent:2 |
| 7 | Password auth uses query param not Bearer header | spec-agent:3 |
| 8 | Resumes from existing workspace without overwriting | spec-agent:4 |

### Feasibility Stage (solution-arch-agent)

| # | Behavior | Eval |
|---|----------|------|
| 9 | Authenticates AFTER spec approval — not before | solution-arch-agent:1 |
| 10 | Pulls platform data in two stages (core, then spec-contingent) | solution-arch-agent:1 |
| 11 | Produces feasibility.md with decision (feasible/constrained/blocked/not feasible) | solution-arch-agent:1 |
| 12 | Presents feasibility.md for approval before proceeding to design | solution-arch-agent:1 |
| 13 | Marks missing required integration as blocked (not skipped) | solution-arch-agent:3 |
| 14 | Does NOT invent adapters that don't exist | solution-arch-agent:3 |
| 15 | Surfaces blocked capabilities to engineer for a decision | solution-arch-agent:3 |

### Design Stage (solution-arch-agent)

| # | Behavior | Eval |
|---|----------|------|
| 16 | Produces solution-design.md with component inventory, plan, acceptance criteria | solution-arch-agent:2 |
| 17 | Presents solution-design.md for approval before any building | solution-arch-agent:2 |
| 18 | Supports design-only mode (skips feasibility re-run) | solution-arch-agent:4 |
| 19 | Requires approved customer-spec.md before starting feasibility | solution-arch-agent:5 |
| 20 | Adapter names resolved from apps.json not tasks.json | solution-arch-agent:1 |

### Build Stage (builder-agent)

| # | Behavior | Eval |
|---|----------|------|
| 21 | merge uses "variable" not "value" in data_to_merge | builder-agent:1 |
| 22 | Adapter task body wired via $var to merge output | builder-agent:1 |
| 23 | Every adapter task has adapter_id and error transition | builder-agent:1 |
| 24 | childJob actor is "job" | builder-agent:2 |
| 25 | childJob task is empty string | builder-agent:2 |
| 26 | childJob job_details is null | builder-agent:2 |
| 27 | childJob uses {task,value} syntax not $var | builder-agent:3 |
| 28 | makeData variables built via merge first | builder-agent:4 |
| 29 | Duplicate transition key workaround (intermediate task) | builder-agent:5 |
| 30 | evaluation has both success AND failure transitions | builder-agent:6 |
| 31 | $var inside newVariable value stores literal string | builder-agent:7 |
| 32 | push/pop/shift use plain string variable name not $var | builder-agent:8 |
| 33 | IAG stdout is string — parse task needed for JSON | builder-agent:9 |
| 34 | Jinja2 from_json filter doesn't exist | builder-agent:10 |
| 35 | merge duplicate keys produce arrays | builder-agent:11 |
| 36 | Stuck job = missing error transition | builder-agent:12 |
| 37 | Non-hex task IDs cause silent $var failure | builder-agent:13 |
| 38 | $var doesn't resolve inside nested objects | builder-agent:14 |
| 39 | merge requires at least 2 items | builder-agent:15 |
| 40 | forEach last body task must have empty {} transition | builder-agent:16 |

### As-Built Stage (builder-agent)

| # | Behavior | Eval |
|---|----------|------|
| 41 | Produces as-built.md with delivered state, deviations, learnings | builder-agent:17 |
| 42 | Appends ## As-Built to solution-design.md without rewriting locked plan | builder-agent:17 |
| 43 | Only amends customer-spec.md if scope changed during build | builder-agent:17 |

---

## Domain Skill Coverage

### MOP (itential-mop)

| # | Gotcha | Eval |
|---|--------|------|
| 44 | Variable syntax is <!var!> not {{ }} or $var | mop:1 |
| 45 | RegEx eval is case-sensitive (capital R, E) | mop:2 |
| 46 | Missing variable = skip = PASS (silent) | mop:3 |
| 47 | MOP is read-only — never push config | mop:4 |
| 48 | MOP update is full replacement | mop:5 |

### IAG

| # | Gotcha | Eval |
|---|--------|------|
| 53 | Decorator $id must match service name (not "root") | iag:1, iag:4 |
| 54 | Decorator schema needs additionalProperties: false | iag:1, iag:4 |
| 55 | Secrets use type: env with target: ENV_VAR_NAME | iag:1 |
| 56 | Python uses argparse for inputs, os.environ for secrets | iag:1 |
| 57 | network_cli needs look_for_keys=False in ansible.cfg | iag:2, iag:6 |
| 58 | runtime.env needs ANSIBLE_STDOUT_CALLBACK: json | iag:2 |
| 59 | OpenTofu uses "vars" and "var-files" (not plan- prefix) | iag:3, iag:5 |
| 60 | iagctl run opentofu-plan requires action subcommand | iag:7 |
| 61 | One-file-multi-service pattern via runtime.env | iag:8 |

---

## E2E Test Coverage

Live platform tests in `evals/e2e/run-e2e-tests.sh`:

| Test | Pattern | Assertions | Status |
|------|---------|------------|--------|
| Test 1 | merge → makeData → query → evaluation → branch | 5 | Pass |
| Test 2 | childJob loop (data_array, parallel, extract loop) | 3 | Pass |
| Test 3 | merge → adapter create → query → error handling | 3 | Pass |

Last run: 11/11 passed on platform-6-aidev.se.itential.io
