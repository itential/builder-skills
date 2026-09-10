# Itential Platform - AI Agent Guide

This project contains skills for assisting developers on the Itential Platform. Read this first, then use the skills for detailed API references.

## Skill Router

Each skill owns a domain. **Invoke the skill using the Skill tool before working in that domain — this is a hard gate, not a suggestion.** If you are about to hand-author a workflow, template, project, or any other platform-asset JSON payload and you have not invoked a domain skill (e.g., `/builder-agent`) this session, stop and invoke it first. Do not construct the payload from general knowledge or from a prior job's error trace alone.

Three things commonly go wrong even after this gate is respected — watch for all three, they compound:

1. **Loading the skill is not the same as consulting it.** Open the specific `helpers/create/*.json` or `helpers/assets/*.json` file the skill's own tables point you to for the task at hand — don't rely on having the skill's text in context somewhere. "Did you load the skill?" and "which helper file did you open for the error you're stuck on?" are different questions; only the second one has evidence behind it.
2. **A rule read once doesn't stay active for a later, different decision.** Re-check the specific governing rule immediately before any destructive or hard-to-reverse call (importing over an existing project ID, `DELETE`, a full-replacement `PATCH`) — don't rely on general awareness from having read it earlier.
3. **If your own reasoning already flags a specific risk a rule warns about, that's stronger evidence than a hunch that it'll work anyway.** Don't spend a live test confirming what you already predicted — apply the rule's fix before attempting the risky version, not after it fails. Treat a self-identified risk as equivalent to an observed failure for Repeat-Failure Circuit Breaker purposes (see below).
4. **A direct, explicit instruction from the user in the current session always takes precedence over a general-purpose rule in this document.** If you find yourself reasoning that a specific instruction ("start from scratch," "ignore X") doesn't apply to some action because a general rule (e.g., "reuse verified patterns") seems to justify it anyway — stop. That reasoning pattern is a red flag, not a resolution. When a general rule and a specific instruction appear to conflict, the instruction wins; if you're not sure whether an action falls inside or outside its scope, ask rather than resolve the ambiguity in whichever direction is more convenient.

| Skill | Agent | When to Use |
|-------|-------|-------------|
| `/explore` | — | Explore a platform freely — auth, discover, browse, build freestyle. |
| `/spec-agent` | **Spec Agent** | Start a delivery from a spec. Owns Requirements stage. |
| `/project-to-spec` | — | Read an existing project → produce customer-spec.md + solution-design.md. |
| `/documentation` | — | Survey global platform assets → discover relationships → group by use case → produce HLD+LLD per use case → optionally create projects and move assets in. For a specific named project, redirect to `/project-to-spec`. |
| `/flowagent-to-spec` | — | Read a FlowAgent → produce customer-spec.md as a deterministic workflow spec. |
| `/solution-arch-agent` | **Solution Architecture Agent** | Feasibility assessment + solution design. Runs after Requirements. |
| `/builder-agent` | **Builder Agent** | Build all assets, test each component individually. Runs after Design. |
| `/qa-agent` | **QA Agent** | Acceptance testing against the approved acceptance criteria + as-built record. Runs after Build — last technical stage before customer sign-off. |
| `/iag` | — | Automation Gateway: IAG services (Python, Ansible, OpenTofu). |
| `/gateway4-to-gateway5` | — | Assess Gateway4→Gateway5 migration readiness; identify Gateway4/IAG4 usage and produce a manual-action guideline. Analysis only, no migration. |
| `/flowagent` | — | AI Agents: configure LLM providers, tools, and agent sessions. |
| `/itential-mop` | — | Command templates with validation rules. |
| `/itential-devices` | — | Devices, backups, diffs, device groups. |
| `/itential-golden-config` | — | Golden config, compliance, grading, remediation. |
| `/itential-inventory` | — | Device inventories, nodes, actions, tags. |
| `/itential-lcm` | — | Resource models, instances, lifecycle actions. |
| `/itential-json-forms` | — | JSON Forms: static-enum, REST-bound, and cascading dropdowns for manual triggers and manual tasks. |

### Delivery Lifecycle

Spec-based delivery follows six stages. Each stage has a named agent, a clear input, and a deliverable.

```
Requirements → Feasibility →   Design    →  Build   →    Test    →  As-Built
      │              │             │            │             │            │
  Spec Agent   Solution Arch  Solution Arch  Builder      QA Agent    QA Agent
                   Agent          Agent       Agent
      │              │             │            │             │            │
  customer-      feasibility.md solution-    assets/    test-report.md as-built.md
  spec.md        (assessment    design.md    configs    (evidence per  (delivered
  (approved)     + decision)   (approved)   (delivered) criterion, from   state,
                                                          test-plan.md    deviations,
                                                          approved by     learnings)
                                                          engineer)      ↳ design updates
                                                                         ↳ spec amendments
```

**Deliverables:**

| Deliverable | Artifact | Produced by | Audience |
|-------------|----------|-------------|----------|
| HLD | `customer-spec.md` | Spec Agent | Customer / stakeholder |
| Feasibility Assessment | `feasibility.md` | Solution Architecture Agent | Customer / architect |
| Solution Design / LLD | `solution-design.md` | Solution Architecture Agent | Engineer / delivery team |
| Test Plan | `test-plan.md` | QA Agent | Engineer (approves before any live test execution) |
| Test Report | `test-report.md` | QA Agent | Customer / delivery — evidence per acceptance criterion |
| As-Built | `as-built.md` | QA Agent | Customer / delivery / support / system of record |

**Explore path** (no spec, no delivery lifecycle):
```
/explore → auth → pull platform data → summarize → use skills directly
```

Build workflows/templates → invoke `/builder-agent`. Need acceptance testing or a closeout record → invoke `/qa-agent`. (Same hard gate as the Skill Router section above — invoke via the Skill tool, don't just reference a skill by name in text.)

### Directory Layout

Platform data (shared, pulled once) and use-case data (per engagement) live in separate directories. **Never mix them.**

```
builder-skills/
├── platform/               ← shared pre-pull via scripts/platform_pull.py (fallback only)
│   ├── openapi.json        — full API reference
│   ├── tasks.json          — task catalog
│   ├── apps.json           — app and adapter type names
│   ├── adapters.json       — adapter instances and state
│   ├── applications.json   — application details
│   ├── environment.md      — human-readable summary
│   └── .pulled-at          — timestamp of last pull
│
└── use-cases/
    └── <use-case-name>/    ← scaffolded via scripts/use_case_init.py
        ├── .env              — credentials (gitignored)
        ├── .auth.json        — live bearer token (gitignored, auto-refreshed)
        ├── openapi.json      — pulled fresh by /explore or /solution-arch-agent (prefer over platform/)
        ├── tasks.json        — pulled fresh per engagement (prefer over platform/)
        ├── apps.json         — pulled fresh per engagement (prefer over platform/)
        ├── adapters.json     — pulled fresh per engagement (prefer over platform/)
        ├── applications.json — pulled fresh per engagement (prefer over platform/)
        ├── task-schemas.json — fetched on demand during build, never pre-populated
        ├── use-case-memory.md — living context: IDs, decisions, gotchas, test log, open items
        └── (deliverables: customer-spec.md, feasibility.md, solution-design.md, test-plan.md, test-cases.json, test-report.md, as-built.md)
```

**Setup sequence (one-time per platform):**
```bash
./scripts/platform_pull.py <platform-url> <client-id> <client-secret>
```

**Per use-case:**
```bash
./scripts/use_case_init.py <use-case-name> <platform-url> <client-id> <client-secret>
```

**Refresh platform data** (after platform upgrade or new adapters installed):
```bash
./scripts/platform_pull.py --refresh <platform-url> <client-id> <client-secret>
```

**At the start of every session — read the memory file first:**
```bash
cat use-cases/<name>/use-case-memory.md
```
It contains the platform URL, project ID, what's already built, decisions made, and open items. Don't re-discover what's already documented. If the file doesn't exist, create it from `helpers/use-case-memory.md`.

**This applies even in freestyle/explore-mode work with no formal spec.** If a session creates a workflow, project, or other durable platform asset — or discovers a non-obvious platform quirk (e.g., "workflow_builder and automation-studio are separate stores," "runCode requires reading stdin, not a pre-injected `data` variable") — create or update `use-cases/<name>/use-case-memory.md` with at least the IDs created and the lesson learned, even if no spec/design doc exists for this engagement. Don't work entirely out of `/tmp` scratch files and let a session's hard-won discoveries evaporate when it ends — the cost of writing a few lines to a durable file is far lower than the cost of a future session re-discovering the same platform quirk from scratch.

**If you cause and then recover from a mistake with real consequences (data loss, a destroyed asset, a broken integration), record it in `use-case-memory.md` even more diligently than a routine successful step.** These are exactly the lessons a future session — yours or another model's — most needs to avoid repeating. Write down what you did, what broke, why, and the exact fix, not just the final recovered state.

### Resuming a Use-Case

`use-case-memory.md`'s `Stage` field tells you where to pick up — but a field can go stale (an agent forgets to update it, a session gets interrupted mid-write). **Verify `Stage` against which files actually exist before trusting it.** If they disagree, the files are ground truth — investigate the mismatch before proceeding, don't just pick one.

| `Stage` says | Files that should exist | Files that should NOT exist yet |
|---|---|---|
| `requirements` | (nothing yet, or a draft `customer-spec.md`) | `feasibility.md` |
| `feasibility` | `customer-spec.md` (approved) | `feasibility.md` (approved) |
| `design` | `feasibility.md` (approved) | `solution-design.md` (approved) |
| `build` | `solution-design.md` (approved) | Component Inventory (§D) has real IDs |
| `test` | `solution-design.md` §D has real IDs | `test-report.md` (complete) |
| `as-built` | `test-report.md` (all cases passing, or residuals explicitly accepted) | `as-built.md` |
| `delivered` | `as-built.md` (signed off) | — |

`Status: on-hold` can apply at any `Stage` — it means work is paused, not that the stage is wrong. Every skill that hands off to another stage MUST update `Stage` (and `Last updated`) before ending its session — see each skill's handoff section for the exact point to do it.

**Data lookup order:**
- `{use-case}/tasks.json`, `apps.json`, `adapters.json`, `openapi.json` — pulled by `/solution-arch-agent` or `/explore` during feasibility. **Always prefer these — they are per-engagement and fresh.**
- `platform/tasks.json`, `platform/apps.json` etc. — pulled once by `scripts/platform_pull.py`, shared across engagements. Use as fallback only if `{use-case}/` files are missing.
- `{use-case}/task-schemas.json` — fetched on demand during build (never pre-populated). Append after every fetch; never re-fetch what's already cached.
- If neither `{use-case}/tasks.json` nor `platform/tasks.json` exist → tell the user to run `/explore` or `scripts/platform_pull.py` first.

### Auth Reuse — Authenticate Once, Reuse Everywhere

**Auth happens when first needed** — in `/explore` (explore path) or in `/solution-arch-agent` during Feasibility. The token is saved to `use-cases/{use-case}/.auth.json`. Every subsequent skill should:
1. Read `use-cases/{use-case}/.auth.json` for the token
2. Read `use-cases/{use-case}/.env` for `PLATFORM_URL` and credentials
3. Use the token for all API calls (Bearer header for OAuth)
4. On auth error (401/403): re-authenticate silently — see procedure below
5. **Never ask the user for credentials if `.env` exists**

This means the user authenticates once and every subsequent skill just works.

**Token expiry — silent re-auth procedure:**

When any API call returns 401 or 403, do not stop and do not ask the user. Re-authenticate silently:

1. Read credentials from `use-cases/{use-case}/.env`
2. Call: `POST {PLATFORM_URL}/oauth/token` with `Content-Type: application/x-www-form-urlencoded` and body `grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}`
3. Write the new token back to `use-cases/{use-case}/.auth.json`
4. Retry the failed request with the new token

If `.env` does not exist and re-auth is needed, then and only then ask the user for credentials.

**"Ask the user" is not limited to missing credentials.** It also applies whenever the Repeat-Failure Circuit Breaker above triggers (the same class of error twice in a row) — surfacing the specific error and asking how to proceed is always preferable to a third silent guess.

**Running fully autonomously with no user turns available? "Ask the user" becomes "stop and document."** Don't continue iterating past 3-4 attempts on the same error class just because no one is available to answer. Instead: stop, write a clear summary of the specific blocker to `use-case-memory.md` and your final response — the exact error, what you've tried, and what you believe the next diagnostic step should be. A clearly-documented stopping point is far more useful to whoever picks this up next than an unbounded attempt log that eventually runs out with no summary at all.

### Key Rule: Look Up Before You Act — Don't Guess

**Skills** teach patterns, workflows, and know-how (how to build a childJob, how to wire variables, how to test).

**`platform/openapi.json`** has every endpoint, method, request body, and response schema. Search it locally — never load the full file into context.

**Before making any API call:**
1. Check the relevant skill for the pattern
2. Search `platform/openapi.json` to confirm the endpoint, method, request body, and response schema — `jq '.paths["/the/endpoint"]' platform/openapi.json`
3. **Check the body wrapper** — most Itential APIs wrap the body in a top-level key. Find it: `jq '.paths["/the/endpoint"].post.requestBody.content["application/json"].schema.properties | keys' platform/openapi.json` → returns the wrapper name (e.g., `["role"]` means `{role: {...}}`)
4. Never hardcode API assumptions — the spec is the source of truth

**Before fetching task schemas:**
1. Check if `use-cases/{use-case}/task-schemas.json` exists — search it first with `jq` or `grep`
2. Only call `multipleTaskDetails` for tasks NOT already in the local file
3. After fetching, always append to the local file so future lookups are instant

**Before parsing any local JSON file:**
1. Check the response shape first — `jq type` and `jq keys` on the file
2. The `/solution-arch-agent` skill has a file-to-shape table — use it
3. Key shapes to remember:
   - `adapters.json` → `{"results": [...]}`
   - `applications.json` → `{"results": [...]}`
   - `devices.json` → `{"list": [...]}`
   - `workflows.json` → `{"items": [...]}`
   - `apps.json` → plain array `[...]`
   - `tasks.json` → plain array `[...]`
4. Use `jq` for parsing, not inline Python scripts with isinstance fallbacks

**When something fails or returns unexpected data — check local files FIRST:**
1. **`openapi.json`** — verify the endpoint exists, check the method (GET vs POST), read the request body schema and response schema. This file has EVERY endpoint, field, and type. Don't guess what a payload looks like — look it up.
2. **`tasks.json`** — verify the task name, app, location. If a task is "not found," search here first.
3. **`task-schemas.json`** — if you already fetched schemas, the full input/output definition is here. Check field names, types, required vs optional.
4. **`adapters.json` / `apps.json`** — verify adapter instance names, app names, casing. Adapter names from `apps.json` (type name) differ from `adapters.json` (instance name).
5. **`job.error` array** — for runtime errors (not just task status)
6. **Actual task output** — `status: complete` doesn't mean the CLI commands worked

**The filesystem is your debugger.** Every API endpoint, every task schema, every adapter name is already saved locally after setup. Never guess a payload structure, field name, or endpoint path — the answer is in these files. Reading a local file costs zero API calls and zero time.

### Pre-Flight Checklist — run this before writing ANY task or calling ANY create/save endpoint

Don't just weigh this against the urge to try something — literally check off each line before proceeding. This is deliberately mechanical: skipping straight to a live API call and iterating on the error is the single largest source of wasted turns and broken deliveries seen in this workflow.

```
[ ] Checked helpers/assets/*.json (or the vendor asset library) for a worked example of this exact task/pattern
[ ] Checked tasks.json / tasks/list for the exact task name and app — did NOT invent a task name
[ ] Checked task-schemas.json (or fetched via multipleTaskDetails) for exact field names, types, and enum values
[ ] If this integrates with an external system, searched tasks.json for a native app task (e.g., GatewayManager,
    InventoryManager, or the specific adapter) BEFORE reaching for restCall/genericAdapterRequest — a native
    task exists for almost every case; restCall against the platform's OWN internal API is almost always wrong
[ ] Did NOT invent an endpoint path, field name, or enum value anywhere in this payload
```

**If you catch yourself about to guess a field name, enum value, or task name because looking it up feels slower — stop.** The lookup is one `jq` or `grep` call and costs less time than a single failed API round-trip, let alone a retry loop.

### Repeat-Failure Circuit Breaker

**If the same class of validation or schema error recurs twice in a row on the same asset, stop iterating blindly.** Do not attempt a third variation from memory. Instead:
1. Go read the exact field's definition in `task-schemas.json` or `openapi.json` — don't infer the fix from the error message's wording alone.
2. If the fix isn't obvious from the schema, surface the specific recurring error to the user and ask how to proceed, rather than trying a fourth or fifth variation.

A recurring error message is a signal that your mental model of the schema is wrong, not that the next guess will happen to be right. Common repeat offenders and their real fix:

| If you see this exact warning, again... | Stop guessing — the fix is... |
|---|---|
| `"... should be of type string but is of type object"` (or `array`) | You passed a raw object/array into a field the schema requires as a string. Build it through `merge`/`makeData` first per the `$var` Resolution rule below, or JSON-stringify it — don't just try a different task type. |
| `"inventory should be of type array but is of type string"` | A `{{ $.var }}` Jinja reference resolves to a **string** at runtime, not the array it points to. Pass the `$var` reference directly (unwrapped by `{{ }}`) to a field expecting an array, or build the array with a dedicated task first. |
| `"outputType is of type enum but got non-enumerated value ..."` | Don't infer the enum from the JS type of your value (`"array"`, `"object"`) — go read the task's actual allowed enum values in `task-schemas.json`. |
| `"Workflow already exists"` on repeated saves | Use `PUT`/update on the existing asset, not another `DELETE`+`POST` cycle. |
| Two errors **alternate** in response to opposite fixes for the same field (e.g., removing a field → `"must have required property 'X'"`; adding it back → `"must NOT have additional properties"`) | This is NOT a sign the fix is close — alternating errors on the same field mean it belongs in a different location, has the wrong type, or belongs under a different parent object entirely. **Stop toggling the field.** This is the circuit breaker's trigger condition just as much as an identical repeated error is — don't let "the error text changed" fool you into thinking you're making progress. Go read the full schema for the field's actual parent object immediately (see the `jq` command below) instead of toggling it again. |
| A "transition not found" / "path" error recurs after a fix that didn't visibly change the transitions logic | Check for a **duplicate key** in the `transitions` object silently overwriting your real fix — JSON keeps only the last occurrence of a duplicate key with no error, so a workflow with both a success and an error branch keyed by the same task ID will silently drop one of them. This is invisible to normal validation (the file is syntactically valid). Before saving, verify `len(keys) == len(set(keys))` on every object level programmatically, rather than re-examining path logic that was never the actual problem. |

**When the fix isn't obvious from the error text (including the oscillation case above), don't keep editing from memory — pull the actual schema and diff against it field by field:**
```bash
jq '.paths["/the/endpoint"].post.requestBody.content["application/json"].schema' openapi.json
```
Read the full returned schema, not just a `.paths | keys` listing of endpoint names — a shallow query that only lists paths will not surface the field-level contradiction causing the error. If the schema is empty or unhelpful for this endpoint, use the matching `helpers/create/*.json` template for this exact operation instead of continuing to guess (see the Helper JSON Templates section) — a working example beats an empty schema every time.

**If an API call returns empty/404/no-results for an asset a human confirms exists and is visible to them, do not invent an explanation about permissions, auth method, or account type and repeat it.** Verify instead, in this order: (1) check the actual HTTP status code, not just an empty response body; (2) verify query parameter encoding against a known-working example if the user has provided one (e.g., a browser's own network request); (3) try the alternate documented endpoint for the same resource (e.g., `workflows/detailed/{name}` vs `automations/{name}`) before concluding it's a visibility/permissions issue. A permissions theory should be your last hypothesis, not your first — and if a human directly tells you your theory is wrong, don't repeat it again later in the same session.

## Understanding User Intent

Figure out which **category of work** the user needs:

- **Building** — create something new (workflow, template, compliance standard). Start with requirements, then build.
- **Operating** — do something now (configure a device, run compliance, backup configs). Identify targets and execute.
- **Exploring** — understand what's available (devices, adapters, workflows). Discover and navigate.
- **Debugging** — something broke (workflow failing, adapter errors). Get job details, check `job.error`.
- **Designing** — planning architecture (modular workflows, compliance hierarchy). Think before building.

## Developer Flow

Six stages. Four agents. Each stage has a named agent, a clear input, and a deliverable. Nothing moves forward without the engineer's sign-off at each stage.

```
Requirements → Feasibility →   Design    →  Build   →    Test    →  As-Built
      │              │             │            │             │            │
 /spec-agent   /solution-     /solution-   /builder-     /qa-agent   /qa-agent
                arch-agent     arch-agent    agent
      │              │             │            │             │            │
  customer-      feasibility.md solution-    assets/    test-plan.md  as-built.md
  spec.md        (approved)     design.md   (delivered) (approved),   (approved)
  (approved)                    (approved)              test-report.md
```

**Stage summaries:**

| Stage | Agent | What happens | Engineer does |
|-------|-------|-------------|---------------|
| Requirements | `/spec-agent` | Refines use case, defines scope, structures HLD | Approves `customer-spec.md` |
| Feasibility | `/solution-arch-agent` | Connects to platform, assesses capabilities, flags constraints | Approves `feasibility.md` |
| Design | `/solution-arch-agent` | Produces component inventory, adapter mappings, build plan, acceptance-criteria-to-test mapping | Approves `solution-design.md` |
| Build | `/builder-agent` | Builds all assets, tests each component individually, delivers | Reviews and accepts delivery |
| Test | `/qa-agent` | Drafts `test-plan.md`, runs static + acceptance test cases against confirmed test data, reports evidence | Approves `test-plan.md` before live execution; reviews `test-report.md` |
| As-Built | `/qa-agent` | Records delivered state, deviations, learnings, backed by test evidence | Signs off on `as-built.md` |

**For explore / freestyle work:**
```
/spec-agent → auth → pull platform data → use skills directly
```

## Key Rules

1. **Never invent task names** — always look them up from `tasks/list`
2. **Always get the schema before building** — `multipleTaskDetails?dereferenceSchemas=true`
3. **Adapter `app` AND `locationType` fields come from `apps/list`**, not `tasks/list` (names can be completely different, not just casing). The `app` field is the adapter **type name** (e.g., `EmailOpensource`), NOT the adapter **instance name** (e.g., `email`). Using the instance name causes `"No config found for Adapter"` errors. Resolve from local `apps.json` and `adapters.json`. When multiple adapter apps exist for the same product, ask the user.
4. **Test each piece individually** before composing into a larger workflow
5. **Check `job.error` for failures**, not just task status
6. **Variable syntax differs by context:**
   - Jinja2 templates: `{{ var }}`
   - Command templates / makeData: `<!var!>`
   - Workflow wiring: `$var.job.x`
   - childJob variable refs: `{"task": "job", "value": "varName"}`
   - merge/evaluation refs: `{"task": "job", "variable": "varName"}` (NOT `"value"` — different field than childJob)
7. **Validation errors = draft workflow** that cannot be started. Run `POST /workflow_engine/workflows/validate` with `{"asset": {...workflow document...}}` → `{"isValid", "errors", "warnings"}` before every save — it is more thorough than the older `POST /automation-studio/workflows/validate` and should replace it. `isValid` is `errors.length === 0` only — **warnings never affect it**, so check both. The endpoint can return HTTP 500 instead of a normal body (a manual-view task with the wrong `type` triggers this). It does not catch missing error/failure transitions, invalid `evaluation.operator` values, or `merge`/`childJob` `"value"`/`"variable"` key mixups — see `builder-agent`'s pre-flight validation section for the full breakdown of what it does and doesn't catch.
8. **`$var` references don't resolve inside object values** (e.g., inside `newVariable` value or adapter `body`) — use `merge`, `makeData`, `query`, or other utility tasks to build the object, then pass it as a top-level `$var` reference. **This is the single most commonly re-violated rule** — if the platform returns `"should be of type string but is of type object/array"` on a `makeData`/`newVariable`/adapter task, this rule is almost always the cause, even if you already tried a fix for it once. Re-read this rule before trying a third payload variation; don't just swap which task type you're using. Exceptions — these resolve one level deep into one specific nested key: `GatewayManager.runService`/`runServiceStatic` (`params`), `GatewayManager.runCode` (`data`), `AgentSessionManager.runAgent` (`inputs`).
9. **Task IDs are hex-only** — `[0-9a-f]{1,4}`, no exceptions, even for a task nothing references via `$var` yet (a workflow gets extended over time, and a non-hex ID that "happens to work" today will silently break the first `$var` reference added to it later). Non-hex IDs (e.g., `qt`, `ok`, `success`, `err1`, `mail1`) cause `$var` references to silently fail at runtime and **project import fails** with `"must NOT have additional properties"` — the import schema rejects any task key that isn't `workflow_start`, `workflow_end`, or a valid hex ID. Check every task key against the hex pattern as a final validation step before finalizing any workflow JSON. To fix existing workflows with bad IDs: rename tasks in-place via PUT, updating transitions and all `$var.<taskId>.*` references simultaneously.
10. **`genericAdapterRequest` prepends the adapter's `base_path`** to `uriPath` — don't include `/api/v1` in `uriPath`. Use `genericAdapterRequestNoBasePath` if you need the full path
11. **Use `POST /projects/import` to create projects atomically** — build all assets locally, pre-compute the project `_id`, pre-wire childJob `@projectId:` refs, then import everything in one call. Avoid the create-then-move pattern (breaks childJob refs, causes project-locking issues). A workflow built standalone via `workflow_builder/workflows/save` and never imported into a project is **NOT a delivered asset** — it's a disconnected draft with no project membership or `@projectId:` scoping, and may not even be listed by `/automation-studio/workflows`.
11a. **Your very next tool call after `POST /automation-studio/projects` or `POST /automation-studio/projects/import` succeeds must be `PATCH /automation-studio/projects/{id}` to add the engineer as owner** — not "verify the import," not "build the next component," the PATCH itself. The platform sets the OAuth service account as the sole owner on creation, locking out human users; skip this and the engineer cannot open the project. Resolve reference IDs by scanning existing projects (see "Resolve membership references" below). PATCH is a **full replacement** — always include all members, including the service account, or they will be removed.
11b. **Project thumbnails use a data URI, not raw base64** — `PUT /automation-studio/projects/{id}/thumbnail` expects `{"imageData": "data:image/png;base64,...", "backgroundColor": "#RRGGBB"}`. Passing raw base64 without the `data:image/png;base64,` prefix results in a black/blank thumbnail in the UI. Use `GET /automation-studio/projects/{id}/thumbnail` to retrieve; the response is `{"data": {"image": "data:image/png;base64,...", "backgroundColor": "..."}}`. Accepted formats: jpg, jpeg, png up to 1000 KB. **Optimal dimensions: 330×100 px.**
11c. **⚠️ `POST /automation-studio/projects/import` against an EXISTING project `_id` is a destructive full-replace, not a merge.** Any existing component not listed in your import payload is silently deleted — this has caused real data loss (a previously-built, working workflow destroyed by an unrelated import). Before importing into an existing project `_id`: `GET /automation-studio/projects/{id}` first and include every existing component in your payload alongside whatever you're adding. Corollary: if a project reference you were relying on turns out missing/stale (`"Project not found"`), do not create a new project and retrofit a standalone workflow into it via `components/add` — that's the create-then-move pattern from Rule 11 by another route. Rebuild the intended end state atomically via `projects/import` instead.
12. **API response shapes vary** — projects use `{message, data, metadata}`, but workflow and template lists use `{items, skip, limit, total}`, and create endpoints return `{created, edit}`. Always check the response shape before parsing
13. **Project component types** — valid values: `workflow`, `template`, `transformation`, `jsonForm`, `mopCommandTemplate`, `mopAnalyticTemplate`
14. **Use skills, don't reimplement** — `/builder-agent` covers projects, workflows, templates, MOP, and component-level testing. Acceptance testing and as-built records are `/qa-agent`'s job, not builder-agent's. Only load other skills for their specific domains (IAG, FlowAgent, MOP, etc.)
15. **When unsure about ANY endpoint, method, or payload — check `openapi.json` FIRST.** See "Key Rule: Look Up Before You Act" above for the full lookup sequence.
16. **If `openapi.json` is not local, fetch it** — `GET /help/openapi?url={ENCODED_BASE}` and save it. Then search locally.
17. **If the openapi schema is empty for an endpoint** — check the corresponding POST/PUT endpoint's schema for the wrapper pattern. As a last resort, send `{}` and read the `"Missing Params"` error — it lists every required field with name, type, and examples.
18. **Endpoint base paths differ** — task catalog is at `/workflow_builder/tasks/list`, but task schemas are at `/automation-studio/multipleTaskDetails` (NOT `/workflow_builder/multipleTaskDetails`). Don't mix them up.
19. **Error transitions are mandatory on adapter/external tasks** — without an error transition, task errors produce "Job has no available transitions" and the job gets stuck forever. Always add `"state": "error"` transitions on tasks that call adapters or external systems.
20. **Adapter responses are transformed** — adapters reshape the upstream API response. Don't assume the native API's response structure (e.g., ServiceNow `result.sys_id`). Call the adapter endpoint directly or check `openapi.json` to verify the actual response shape before wiring query paths.
21. **Duplicate transition keys to same target** — JSON doesn't allow two keys with the same name. If a task needs both `success` and `error` to reach `workflow_end`, create an error handler task (e.g., `newVariable` to set error status) and route error there, then route that task to `workflow_end`.
22. **Respect task schema data types** — When wiring task inputs, match the type from `task-schemas.json` exactly. If a field is typed as `array`, pass an array (e.g., `["joksan@example.com"]`), not a bare string. If typed as `number`, pass a number, not a string. Common offenders: `to`/`cc`/`bcc` in email tasks (arrays, not strings), `pageSize`/`page` in queries (numbers, not strings). Mismatched types cause silent failures or validation errors.
23. **Adapter `app` ≠ adapter instance name** — The `app` and `locationType` fields on adapter tasks must be the adapter **type name** from `apps.json` (e.g., `EmailOpensource`, `Servicenow`), NOT the adapter **instance name** from `adapters.json` (e.g., `email`, `servicenow-prod`). Using the instance name causes `"No config found for Adapter: <name>"` at runtime. The `adapter_id` field is where the instance name goes. Triple-check: `app` = type, `adapter_id` = instance.
24. **Project-scoped asset names** — once an asset is added to a project, its `name` is prefixed with `@{projectId}: `. When reading or updating a project-owned asset via PUT, you MUST use the scoped name or the API returns 400. Read the asset first to get its current name, or construct it as `@{projectId}: {displayName}`. Strip this prefix when displaying names to the user.
25. **NEVER wire a Configuration Manager remediation task** — `runAutoRemediation`, `advancedAutoRemediation`, `convertChangesToConfig`, `patchDeviceConfiguration`, `advancedPatchDeviceConfiguration`, `patchCMDeviceConfiguration`, `ManualRemediation`, and `ManualRemediationResults` are prohibited in every workflow, even when a spec asks for fully automatic remediation. Golden Config detects and reports drift; it never applies fixes to a device. To correct a device, build a normal config-push delivery using the environment's config-push task (`sendConfig`/`runService` via GatewayManager, `itential_cli`, or netmiko send-config). See the `/itential-golden-config` Remediation section. (`updateNodeConfig` is allowed — it authors the GC node template, not a device.)
26. **Search for a native app task before reaching for `restCall`/`genericAdapterRequest`.** Before wiring any interaction with an external system OR with the Itential platform's own internal services (Gateway Manager, Inventory Manager, etc.), search `tasks.json` for a task whose `app` matches that system first — `jq '.[] | select(.app=="GatewayManager")' tasks.json` (or `InventoryManager`, or the adapter's type name). A native task exists for nearly every case (e.g., `GatewayManager.sendCommand`/`runService`, `InventoryManager.buildInventoryFilter`). Using `restCall` to hit the platform's own internal REST API instead of the native task is almost always wrong — it bypasses the transforms, validation, and auth the native task handles for you, and it is *not* a substitute for "I couldn't find the right task," it's a sign you didn't search `tasks.json` filtered by the right `app` yet.
27. **Never construct a large JSON payload as an inline shell string (bash heredoc, `-d '{...}'`).** Write it to a scratch file with a proper file-write tool, or if only `bash` is available, generate it with `python3 -c "..."` using `json.dump()` to a file (single-quoted script argument, not an interactive heredoc) — never hand-embed multi-line templated strings, backticks, or unicode inside a shell here-doc. Hand-authoring large JSON as escaped shell text is fragile and is the most common source of multi-turn "fix the JSON syntax error" loops. If a JSON payload fails to parse, don't try to patch it byte-by-byte with `sed`/string-replace — regenerate it cleanly from a script or template instead.
28. **Don't declare a build/stage "delivered" or "complete" without objective evidence — job/task status is not that evidence by itself.** Three checks, all required: (a) a non-empty `warnings` array on save/validate blocks delivery the same as `errors` would; (b) "tested" means an actual job ran against the *delivered* asset and `job.error` was checked, not a component tested in isolation; (c) `workflow_end: complete` only means the orchestration finished — check every task's own result payload (`runCode`'s `result.status`/`stderr`, an adapter's response body, a `query`'s extracted value) for an embedded error, traceback, or **null/empty value where real data was expected** — a task can show `finish_state: success` while its own result is `"error"`, or while it evaluated successfully but produced nothing. State explicitly which task outputs you checked and their actual values before calling a run "successful."
29. **Reuse a script/task pattern you already verified earlier in the same session — don't re-derive it from assumptions the second time.** If you've established a correct code contract once (e.g., a `runCode` script's `import sys, json; data = json.load(sys.stdin)` stdin-reading boilerplate, copied from a working example), copy that exact boilerplate verbatim into every subsequent task of the same type in the same session — don't rewrite the input-handling logic from scratch based on assumption each time you author a new instance of that task. A model that gets a pattern right once and then regresses away from it on the next occurrence has effectively not learned it at all.
30. **If a project reference you were relying on turns out to be missing or stale (e.g., a `"Project not found"` error), do not paper over this by creating a new project and moving pre-existing standalone assets into it via `components/add`.** That is the create-then-move pattern (Rule 11) regardless of why you ended up there — falling into it while recovering from an unrelated error is still the discouraged pattern. Instead, rebuild the intended end state (project + all its components, including any workflow you'd already created standalone) atomically via `POST /automation-studio/projects/import`, even if that means recreating a workflow that technically already exists elsewhere.

## Helper JSON Templates

**For workflow design and task wiring — read from `helpers/assets/` first.** The asset projects are real, tested, production imports. Extract task structures, variable wiring, transition patterns, and transformation usage directly from those files. Do not invent task schemas from memory.

**`helpers/assets/*.json` (the curated, generic reference library) is always fair game to consult, regardless of any "start from scratch" instruction** — that instruction is about not reusing a prior *delivery* of this specific use case, not about avoiding the platform's general reference material. A prior `use-cases/<name>/` folder representing an earlier attempt at the *same* task, on the other hand, is exactly what "start from scratch" means to exclude — don't read its build artifacts to "reuse a verified pattern" and reason your way around the instruction. If genuinely unsure which category a file falls into, treat it as excluded and ask.

**For API call bodies (create, update, operations) — use the helpers below.** These cover request wrappers and field names for endpoints that the asset projects don't demonstrate.

Helper templates are organized in subdirectories under `helpers/`:

**`helpers/create/`** — POST bodies for creating assets

| File | Purpose |
|------|---------|
| `create-workflow.json` | Workflow scaffold with start/end tasks |
| `create-project.json` | Project creation |
| `import-project.json` | Import a project (atomic — preferred over create + add) |
| `create-command-template.json` | Command template with `<!var!>` syntax |
| `create-template-jinja2.json` | Jinja2 template |
| `create-template-textfsm.json` | TextFSM template |
| `create-json-form.json` | JSON form for user input |
| `create-json-form-rest-bound.json` | JSON form with REST-bound dropdowns |
| `create-ops-manager-automation.json` | Operations Manager automation |
| `create-ops-manager-trigger.json` | API endpoint trigger |
| `create-ops-manager-trigger-manual.json` | Manual/form trigger (legacyWrapper: false) |
| `create-ops-manager-trigger-schedule.json` | Scheduled trigger (repeat object, not cron) |
| `create-lcm-resource-model.json` | LCM resource model with lifecycle actions |
| `create-integration.json` | Virtual integration (adapter instance) |
| `create-golden-config-tree.json` | Golden config tree |
| `create-golden-config-node.json` | Child node |
| `create-compliance-plan.json` | Compliance plan |
| `create-flowagent-project-bundle.json` | FlowAI agent project bundle (project + agent + tools + decorator) — import via `/agent-project-service/project-bundles/import` |
| `create-flowagent-decorator.json` | FlowAI tool decorator body — narrows a tool's `inputSchema` for the LLM |

**`helpers/update/`** — PUT/PATCH bodies for updating assets

| File | Purpose |
|------|---------|
| `update-command-template.json` | Update command template (full replacement) |
| `update-json-form.json` | Update a JSON form — wrapped in `options` key (full replacement) |
| `update-node-config.json` | Node template with full syntax |
| `update-project-members.json` | Update project membership — include all members (PATCH = full replacement) |

**`helpers/operations/`** — Add, run, and other operation bodies

| File | Purpose |
|------|---------|
| `add-components-to-project.json` | Add assets to an existing project |
| `add-devices-to-node.json` | Assign devices to a golden config node |
| `run-compliance-plan.json` | Run a compliance plan |
| `run-compliance.json` | Run compliance directly against a tree/node |

**`helpers/assets/`** — Importable sample projects. Use these as design references and borrow components directly rather than building from scratch.

Import via `POST /automation-studio/projects/import` with body `{"project": <file contents>}`.
After import, PATCH membership immediately (see Rule 11a).

**FlowAI agent samples** — different domain, different import path (not Automation Studio):

| File | What's Inside |
|------|--------------|
| `flowagent-sample-agent-project.json` | Real FlowAI project bundle exported from a live platform: 3 agents, including a multi-tool agent (device command → decorated ServiceNow tool → WorkCenter approval step). Import via `POST /agent-project-service/project-bundles/import` with `{"bundle": <file contents>, "providerResolutions": {...}}` — see the `flowagent` skill. |

**JSON Form samples** — different domain, different import path (`POST /json-forms/forms` directly, not Automation Studio project import):

| File | What's Inside |
|------|--------------|
| `json-form-example-static-enum.json` | Real Cisco IOS "Port Turn Up" form export: 8 fields incl. a static-enum dropdown, number `updown` widgets, `ipv4` format validation. No REST binding. |
| `json-form-example-rest-bound.json` | Real Cisco IOS "Compliance" form export: one REST-bound dropdown pulling tree names live from `GET /configuration_manager/configs`, plus one plain text field. |

Both extracted from real, working `jsonForm`-type components inside `vendor-cisco-ios.json` — see the `itential-json-forms` skill for the full form-structure reference.

**Itential Platform — core utilities**

| File | What's Inside |
|------|--------------|
| `itential-platform-configuration-management.json` | 6 workflows (Command Template Runner, Golden Config, Backup Config, Push Config, Diff), 2 templates, 6 transformations — *requires IAG* |
| `itential-platform-data-manipulation.json` | 21 transformations — Parse Number, Chunk Array, Get Value From JSON Pointer, Group Records, Filter Array, Split String, Remove Duplicates, Allocate Numbers, Convert CSV to JSON, and more |
| `itential-platform-email.json` | 1 workflow (Send Email SMTP), 2 transformations — *requires Email Adapter* |
| `itential-platform-regex-operations.json` | 4 transformations — Test Match, Find Match, Replace, Extract |
| `netbox-inventory-sync-runcode-enablequery.json` | 2 real, verified workflows demonstrating `runCode` (Python-on-gateway) + "Enable Query" (inline field decorator) replacing a per-item transform loop that would otherwise need `forEach`+`query`×N+`evaluation`+`merge`+`push`. One reuses an external script, one uses only native app tasks — both collapsed their device-mapping loop to 1-2 tasks. See `builder-agent` skill's `### "Enable Query"` and `Step 0a` for the decision rule on when to reach for this pattern. |
| `runcode-taskquery-reference.json` | Minimal, focused reference for the mechanics of wiring `runCode` + task query together (not the "why" — see the netbox asset above for the collapse story): bringing multiple upstream tasks' data into `data`, unwrapping a nested field via `#/path` + a matching decorator before the script runs, and reading the result back out. Combines two NetBox list calls into one summary. See `builder-agent` skill's `### Worked example: wiring runCode + task query together`. |

**Vendor integrations — design and wiring examples**

*Software upgrade patterns:*

| File | What's Inside |
|------|--------------|
| `vendor-cisco-ios.json` | IOS Upgrade, Port Turn Up, Run Compliance, NetBox Inventory sync — 5 workflows, 6 MOP command templates, 3 JSON forms |
| `vendor-juniper-junos.json` | JUNOS Upgrade, Port Turn Up, Run Compliance, NetBox Inventory sync — 5 workflows, 6 MOP command templates, 1 template, 2 JSON forms |
| `vendor-arista-eos.json` | Software Upgrade, Port Turn Up, Create VLAN, Push Config, File Transfer — 7 workflows, 9 MOP command templates, 6 transformations |

*DNS and IPAM:*

| File | What's Inside |
|------|--------------|
| `vendor-infoblox-nios-ddi.json` | 20 workflows — full CRUD for Networks, Network Containers, DNS A/CNAME/PTR/NS/Fixed Address records, Assign Next IP |
| `vendor-netbox.json` | 6 workflows (Create/Delete Prefix, Reserve/Delete IP, Assign Next IP, Onboard Device), 9 transformations, 1 JSON form |

*ITSM integration:*

| File | What's Inside |
|------|--------------|
| `vendor-servicenow.json` | 9 workflows (Create/Update/Close Incidents, Change Requests, RITMs, Get Catalog Inputs), 6 transformations |

**`helpers/assets/lcm/`** — LCM resource model exports + their backing project (exported from live platform)

The `lcm-*.json` files are resource model exports (import via `POST /lifecycle-manager/resources/import`).
The project file contains the actual LCM action workflows — read it to understand how LCM workflows are structured.

| File | What's Inside |
|------|--------------|
| `lcm-vxlan-fabric-management.json` | Resource model: 5 actions (Create Network, Re-Provision, Delete, Force Delete, Decommission) — 4 wired |
| `lcm-vxlan-fabric-services-project.json` | **Backing project**: 6 LCM action workflows, 13 transformations, 3 JSON forms, 2 templates, 1 MOP template — the real workflow structure to learn from |
| `lcm-fan-device-lifecycle-management.json` | Resource model: 10 actions (Device Onboarding, SW Compliance, CVE Scan, Upgrade, Decommission, etc.) — 9/10 wired |
| `lcm-port-turn-up.json` | Resource model: 6 actions (Create, Delete, Service Verification, Update Service Policy) — 4/6 wired |
| `lcm-ip-blocking-service.json` | Resource model: 4 actions (Create, Update, Delete, Retry) — fully wired |
| `lcm-interface-service-provisioning.json` | Resource model: 3 actions (Create, Modify, Delete) — fully wired |

**Key LCM rule:** every action workflow **must** declare and output an `instance` variable — this is what LCM uses to track resource state between actions. Read the VXLAN project workflows to see the exact pattern.

**`helpers/assets/openapi-specs/`** — OpenAPI spec examples for use with the OpenAPI adapter

| File | Purpose |
|------|---------|
| `whoami-basic-auth.json` | WhoAmI endpoint spec with Basic Auth |
| `whoami-client-creds.json` | WhoAmI endpoint spec with Client Credentials |

### Assets Library — when a vendor or pattern isn't here

The full asset library lives at **https://github.com/itential/assets** (branch: `devel`). Structure: `<Vendor>/<Product>/Projects/<name>.project.json`.

**When to check the repo:**
- The use case involves a vendor not covered by the files above (AWS, Arista, Juniper, F5, Palo Alto, Alkira, Kentik, etc.)
- You need a workflow pattern that isn't in the local helpers
- The customer asks about supported integrations

**How to pull a project from the repo:**
```bash
# List available projects for a vendor
gh api repos/itential/assets/contents/<Vendor>/<Product>/Projects --jq '.[].name'

# Download it into helpers/assets/
curl -sL "https://raw.githubusercontent.com/itential/assets/devel/<Vendor>/<Product>/Projects/<encoded-name>.project.json" \
  -o "helpers/assets/<local-name>.json"
```

**Full vendor index (has Projects/):** Alkira, Apache/Kafka, Arista/EOS, Atlassian/Jira, AWS/EC2, Cisco/ASA, Cisco/IOS, Cisco/Meraki, Cisco/NSO, Cisco/NX-OS, F5/BIG-IP, F5/BIG-IQ, GitHub, GitLab, IP Fabric, Infoblox/NIOS DDI, Juniper/JUNOS, Kentik, Microsoft/Teams, NetBox, Palo Alto/Panorama, ServiceNow, Versa/Director

**`helpers/iag/`** — Automation Gateway service files

| File | Purpose |
|------|---------|
| `example-python-service.yaml` | Python script service |
| `example-ansible-service.yaml` | Ansible playbook service |
| `example-opentofu-service.yaml` | OpenTofu plan service |
| `example-multi-service-chain.yaml` | Multi-service orchestration |
| `service-file-schema.md` | Full YAML schema reference |
