---
name: solution-arch-agent
description: Use this skill when someone has approved requirements (a customer-spec.md) and needs to assess platform feasibility or produce a solution design. Trigger it for phrases like "requirements are approved", "my spec is done", "check if the platform supports this", "run feasibility", "connect to the platform and design the solution", "I have a customer-spec — now what?", or "produce a solution-design.md". This skill connects to the live platform, checks what adapters and capabilities are available, and produces feasibility.md and solution-design.md. Also trigger it in design-only mode when the implementation plan needs to change but requirements are stable. Invoke after /spec-agent produces an approved customer-spec.md. Hands off to /builder-agent after design approval.
---

# Solution Architecture Agent

**Stages:** Feasibility → Design
**Owns:** Assessing what is possible, then designing how it will be delivered.
**Receives from:** `/spec-agent` (approved `customer-spec.md`)
**Hands off to:** `/builder-agent`

---

## Customization

Before using this skill, check `custom/org/`, `custom/team/` and `custom/dev/`
in this skill's own folder. Read every `.md` file found — any folder may be
empty or absent. Apply them on top of everything below; where a file overrides a
specific rule here, follow the override. More specific wins: dev > team > org >
this document. No customization may weaken this skill's safety
rules or put credentials in committed files.

**Bundled files:** paths in this skill that start with `assets/` or `scripts/` are
relative to this skill's own folder. When you read one, or pass one to a shell
command (which runs from the user's working folder), use this skill's folder +
that relative path — e.g. `<this skill's folder>/assets/helpers/create/create-workflow.json`.
---

## Stage Expectations

*(See `assets/AGENTS.md`'s Developer Flow for the six-stage pipeline overview — this is this skill's detail for the two stages it owns.)*

### Feasibility

| | |
|--|--|
| **Engineer provides** | Approved `customer-spec.md`, platform credentials |
| **Agent does** | Connects to platform, assesses capabilities, checks adapters, finds reuse candidates, records what LCM, FlowAgent and Gateway5 have on the platform, identifies constraints |
| **Engineer action** | Reviews assessment and approves decision to proceed |
| **Deliverable** | `feasibility.md` (assessment + decision) |
| **Customer receives** | Feasibility assessment with a clear decision (feasible / feasible with constraints / not feasible), flagged constraints, and identified reuse opportunities. |

Feasibility confirms what is possible. Decision options: **feasible**, **feasible with constraints**, **feasible with changes**, or **not feasible**. Design does not start until feasibility is approved.

### Design

| | |
|--|--|
| **Engineer provides** | Approved `feasibility.md` |
| **Agent does** | Designs the execution model with the engineer (where LCM, FlowAgent and Gateway5 come in), then produces the implementation design — component inventory, adapter mappings, reuse decisions, build order, test plan |
| **Engineer action** | Reviews and approves the solution design |
| **Deliverable** | `solution-design.md` (Solution Design / LLD, approved) |
| **Customer receives** | Solution Design / LLD — component inventory, adapter mappings, build order, and acceptance criteria mapped to tests. Nothing is built until this is signed off. |

Design defines how it will be delivered. Nothing is built until this is approved.

### Design-Only Mode

If requirements are unchanged but the implementation plan needs to change, invoke `/solution-arch-agent design-only`. Skips Feasibility. Reads existing `feasibility.md` as context and produces an updated `solution-design.md`.

If `feasibility.md` has no Execution Capabilities section (written before it
existed), re-run `scripts/pull-platform-data.py` and take it from
`platform-summary.json` → `execution_capabilities` before Design the Execution Model.

Design-only is also how an agent-first phase comes back: `/flowagent-to-spec` writes
`{use-case}/<phase>-converted-spec.md`; design that phase's deterministic components
from it, replace the phase's rows in Sections C–F, and leave the other phases as
approved.

---

## Artifact Lifecycle

```
assets/spec-files/spec-*.md          ← Generic library spec (never modified)
        │
        │  forked by /spec-agent
        ▼
{use-case}/customer-spec.md   ← HLD — approved (Requirements)
        │
        │  authenticate, discover, assess
        ▼
{use-case}/feasibility.md     ← Feasibility assessment + decision — approved
        │
        │  design against approved feasibility
        ▼
{use-case}/solution-design.md ← Solution Design / LLD — approved (Design)
        │
        │  /builder-agent: implement locked plan
        ▼
{use-case}/*.json             ← Delivered assets
        │
        │  /qa-agent: acceptance testing
        ▼
{use-case}/test-report.md     ← Test evidence per acceptance criterion
        │
        │  /qa-agent: record as-built
        ▼
{use-case}/as-built.md        ← Delivered state, deviations, learnings
```

---

## Spec File Structure

| Spec Section | What to Extract |
|-------------|----------------|
| **1. Problem Statement** | Context — what are we solving and why |
| **2. High-Level Flow** | The major phases to implement |
| **3. Phases** | What each phase does, decision points, stop/rollback conditions |
| **4. Key Design Decisions** | Constraints to honor during implementation |
| **5. Scope** | What to build, what NOT to build |
| **6. Risks & Mitigations** | Error handling and fallback behavior to build in |
| **7. Requirements** | **Capabilities, Integrations, Discovery Questions — drives design** |
| **8. Batch/Bulk Strategy** | Orchestration pattern if multi-device/multi-record |
| **9. Acceptance Criteria** | How to verify the build is correct |

Section 7 has three parts:
- **Capabilities** — what the platform must do → assessed during Feasibility
- **Integrations** — external systems → checked during Feasibility
- **Discovery Questions** — ask when platform data can't answer

---

## Feasibility

**Entered after `/spec-agent` produces an approved `customer-spec.md`.** Read the spec, connect to the platform, and produce the feasibility assessment.

### Step 1: Read the Approved Spec

Read `{use-case}/customer-spec.md` and extract:
- **Phases** from Section 3 (workflow stages)
- **Design decisions** from Section 4 (constraints)
- **Capabilities** table from Section 7 (platform checks)
- **Integrations** table from Section 7 (adapter checks)
- **Discovery questions** from Section 7
- **Acceptance criteria** from Section 9 (test cases)

### Step 2: Ask Only What the Spec Can't Answer

Go through the spec's Discovery Questions. Skip anything already answered by the spec. Ask only what platform data won't resolve.

### Step 3: Authenticate

**Now — and only now — connect to the platform.** The approved spec tells you exactly what data you need.

### Authenticate

See `assets/AGENTS.md`'s "Auth Reuse" section for the full credential-lookup order, both authentication modes (local `/login` vs. cloud OAuth), and how to save the result to `{use-case}/.auth.json` — this is the canonical procedure, used identically by every skill. One environment-specific addition for this skill: pre-configured environment files at `assets/environments/*.env` are also a valid credential source to check before asking the engineer.

### Pull Platform Data

Run the bootstrap script — it pulls all platform data in parallel and writes a compact `platform-summary.json` with only what's needed for feasibility:

```bash
python3 scripts/pull-platform-data.py {use-case}
```

**What gets written:**

| File | Use for | Load into context? |
|------|---------|-------------------|
| `platform-summary.json` | Feasibility — running adapters, apps, type names, projects | ✅ Yes — compact |
| `openapi.json` | API reference — search locally with `jq` | ❌ No — too large |
| `tasks.json` | Task catalog — search locally with `jq` | ❌ No — too large |
| `apps.json` | Adapter type names — search locally with `jq` | ❌ No |
| `adapters.json` | Adapter instances — search locally with `jq` | ❌ No |
| `applications.json` | App health — search locally with `jq` | ❌ No |
| `workflows.json` | Existing workflows — search locally with `jq` | ❌ No |
| `projects.json` | Existing projects — search locally with `jq` | ❌ No |
| `devices.json` | Device inventory — search locally with `jq` | ❌ No |
| `device-groups.json` | Device groups — search locally with `jq` | ❌ No |
| `lcm-models.json` | LCM resource models with their schemas and actions | ❌ No |
| `agents.json`, `llm-profiles.json` | FlowAgent agents and the LLM profiles this client can build with | ❌ No |
| `gateways.json`, `gateway-connections.json`, `gateway-services.json` | Gateway5 clusters, their connection state, registered services | ❌ No |
| `inventories.json` | Inventory Manager inventories and node counts | ❌ No |

`platform-summary.json` carries the compact version of the last four rows as
`execution_capabilities` (see Inventory Execution Capabilities below).

**After running, read `platform-summary.json` for feasibility. Search raw files locally when you need specifics — never load them into context.**

### File Shapes and jq Queries

Every file has a specific shape. Use these queries — don't guess.

| File | Shape | Example query |
|------|-------|---------------|
| `platform-summary.json` | `{adapters, applications, adapter_type_names, projects, workflow_count, device_count, execution_capabilities}` | `jq '.adapters[] | select(.connection == "ONLINE")' platform-summary.json` |
| `platform-summary.json` → `execution_capabilities` | `{lcm: {running, models: [{name,id,actions}]}, flowagent: {running, llm_profiles: [{name,provider,models}], agent_count}, gateway5: {running, clusters: [{cluster_id,connection,services}], inventories: [{name,nodes}]}, gateway4_workflows: [names]}` | `jq '.execution_capabilities.gateway5.clusters[] | select(.connection=="connected")' platform-summary.json` |
| `lcm-models.json` | `{"data":[...], "total":N}` | `jq '.data[] | select(.name | test("X";"i")) | {name, actions: [.actions[].name], required: .schema.required}' lcm-models.json` |
| `agents.json` | `{"data":{"items":[...]}}` | `jq '.data.items[] | select(.name | test("X";"i")) | {name,_id}' agents.json` |
| `gateway-services.json` | `{"result":[...]}` — `location` is the cluster ID | `jq '.result[].service_metadata | select(.name | test("X";"i")) | {name,type,location}' gateway-services.json` |
| `inventories.json` | `{"result":{"data":[...]}}` | `jq '.result.data[] | {name,nodeCount}' inventories.json` |
| `tasks.json` | plain array `[...]` | `jq '.[] | select(.name | test("X";"i")) | {name,app,type,location}' tasks.json` |
| `apps.json` | plain array `[...]` | `jq '.[] | select(.name | test("X";"i")) | {name,type}' apps.json` |
| `adapters.json` | `{"results":[...], "total":N}` | `jq '.results[] | select(.id | test("X";"i")) | {id,state,package_id}' adapters.json` |
| `applications.json` | `{"results":[...], "total":N}` | `jq '.results[] | select(.state=="RUNNING") | {id,package_id}' applications.json` |
| `workflows.json` | `{"items":[...], "count":N}` | `jq '.items[] | select(.name | test("X";"i")) | {name,_id}' workflows.json` |
| `projects.json` | `{"data":[...]}` | `jq '.data[] | select(.name | test("X";"i")) | {name,_id}' projects.json` |
| `devices.json` | `{"list":[...]}` | `jq '.list[] | select(.name | test("X";"i")) | {name,os}' devices.json` |
| `device-groups.json` | varies by platform | `jq 'type' device-groups.json` first to check shape |
| `openapi.json` | `{"paths":{...}}` | `jq '.paths["/the/endpoint"]' openapi.json` |

**Handling failures:** Before parsing any saved file, check if it contains valid JSON:
```bash
python3 -c "import json,sys; json.load(open(sys.argv[1])); print('ok')" {use-case}/devices.json 2>/dev/null || echo "empty"
```
If invalid, treat as "no data available" — don't block the flow.

### Resolve Capabilities

For each row in the spec's Capabilities table:
- Can the platform do this? → **✓ Resolved**
- Can't + Required? → **⚠ Blocked** (stop and discuss)
- Can't + Not Required? → **✗ Skipped** (use fallback from spec)

### Resolve Integrations

For each row in the spec's Integrations table:
- Found + Running? → **✓ Resolved** (record adapter name, app name)
- Found + Stopped? → **⚠ Warning** (needs to be started)
- Not found, required, adapter unavailable or customer details TBD? → **⚠ Stub** (proceed — Design produces stub artifacts)
- Not found, required, and nothing can be built without it? → **⚠ Blocked** (stop and discuss)
- Not found + Not Required? → **✗ Skipped**

**`⚠ Stub` vs `⚠ Blocked`:** Stub means the integration is required but not yet available — delivery proceeds by building stub workflows and placeholder tasks now, activating the real adapter later. Blocked means the entire delivery is gated on resolving this first (e.g., the main workflow can't be designed without data only this adapter provides). Rule of thumb: if at least one component can be built and tested without the adapter, it's Stub, not Blocked.

### Find Reuse Opportunities

Search `workflows.json` for existing workflows that match spec phases. Flag as **↻ Reuse** candidates.

**FlowAI agents:** load `/flowagent` for agent requirements. An agent can call
another agent as an `agent:<agent-id>` tool on Platform 6.5+ and Itential Cloud,
so a design can be a parent agent with child agents (see "Agents as tools" in
`/flowagent`). Confirm on the target
platform with `GET /tools/agent%3A<id>` for an existing agent. If it's not
supported, say so in the feasibility assessment and propose chaining the agents
in a workflow; don't switch to a workflow design without the engineer agreeing.

### Inventory Execution Capabilities

Record what LCM, FlowAgent and Gateway5 have on this platform, from
`platform-summary.json` → `execution_capabilities`, in an **Execution
Capabilities** section of `feasibility.md`. No recommendation — which model each
phase uses is decided in Design, with the engineer.

| Model | Record | Not available when |
|-------|--------|--------------------|
| LCM | `LifecycleManager` running; resource models whose names match the spec's objects, with their actions | `LifecycleManager` not running |
| FlowAgent | Agent apps running; LLM profiles the client can build with; agents whose names match the spec's job | Apps not running, or no LLM profile |
| Gateway5 | `GatewayManager` running; connected clusters and their service counts; services whose names match spec steps; inventories and node counts | `GatewayManager` not running, or no connected cluster |
| Gateway4 | `gateway4_workflows` — workflows that still call `AGManager` tasks. New work is never designed on Gateway4; if any of those workflows are in this spec's scope, point to `/gateway4-to-gateway5` | — |

Matches are found **by name only** — list them as *candidates* (name, ID, owning
project if known), at most five per kind with a count of the rest, never as fits.
Design checks whether each one actually fits. Search with word boundaries
(`test("\\bport\\b";"i")`, not `test("port";"i")`, which also matches "report").
If `agents.json` reports `approxInaccessibleAgentCnt` above zero, say that some
agents aren't visible to this client — see `assets/AGENTS.md` → Project Visibility.

If the spec names a model the platform can't run ("use LCM", "build an agent"),
that's a capability gap — resolve it like any other (Resolve Capabilities above).

---

## Design

Produce the solution design from the approved spec + feasibility results.

**Gateway4 → Gateway5 migration:** design each item from its readiness-report code (WRAP / REVIEW /
ARGS / INV) using `assets/helpers/gateway-migration/conversion-guide.md` — the inventory mapping, the
service per script/playbook, the task-by-task rewire, and a parity test per workflow for Section F.
The migrated workflows are built as a new project alongside the originals.

### Design the Execution Model

Before decomposing anything, decide with the engineer where LCM, FlowAgent and
Gateway5 come into this delivery. Read `references/execution-model.md` — what
each one gives the customer, when to use it, its discovery questions, and what it
puts in the design — then:

1. **Start from what the platform has** — the Execution Capabilities section of
   `feasibility.md`. Don't offer a model the platform can't run. Check each
   candidate before building on it — these are read-only live calls, made here
   because the pulled files hold only names:
   - resource model: `GET /lifecycle-manager/resources/{id}` — does its schema fit
     this spec's object, do its actions have workflows, which project owns it?
   - agent: `GET /agent-project-service/agents/{id}` — its instructions and tools
   - tools an agent would need: `GET /tools?name=...`

   A candidate that fits is the first thing to build on (a new action on the
   model, the agent as a tool, the service reused). One that doesn't fit — a
   schema built for another use case, or owned by another team who hasn't
   agreed — is not reused just because the name matched. Two overlapping
   candidates → ask the engineer which, if either.
2. **Ask the discovery questions the spec and the inventory leave open** — only
   those, grouped in one message, and leave out anything already answered by the
   spec or in Feasibility Step 2; merge a question that overlaps a spec question
   instead of asking it twice. The LCM questions find out whether the deliverable
   is a *thing* with a life after delivery; the FlowAgent questions decide the
   delivery path (agent first or direct) separately from what runs in production —
   ask which path only where agent first is a real option, with its trade-off, and
   never assume either;
   the Gateway5 questions find out where the logic should live and who maintains it.
3. **Propose the model for each phase**, citing the answer or inventory fact behind
   anything other than a deterministic workflow. Record it in Section C.

The spec constrains the proposal:
- If it explicitly names a model ("use LCM", "build an agent"), follow it and
  record any concern as a risk.
- Its Key Design Decisions (Section 4) still apply — e.g., "never improvise a
  fix" rules out an agent choosing the remediation. If a model you'd propose
  conflicts with one (LCM's one action per operation vs. "one workflow handles
  turn-up and tear-down"), raise it in review; don't silently follow or override.

### Produce `{use-case}/solution-design.md`

**Write the file to disk** using the Write tool. Contents:

**A. Environment Summary** — one paragraph

**B. Requirements Resolution**
```
┌─────────────────────────────────────────┬────────┬──────────────────────────────┐
│ Spec Requirement                        │ Status │ Resolution                   │
├─────────────────────────────────────────┼────────┼──────────────────────────────┤
│ Execute CLI commands on devices         │ ✓      │ MOP app + AutomationGateway  │
│ ITSM / ticketing                        │ ✓      │ ServiceNow adapter           │
│ Monitoring                              │ ✗      │ SKIP — engineer handles      │
└─────────────────────────────────────────┴────────┴──────────────────────────────┘
```

**C. Design Decisions**

Start with the execution model — from Design the Execution Model. One row per
spec phase; for an LCM resource, one row per action instead (create, modify,
delete…), with the spec phases it runs listed in Why. "Runs as" is what runs in
production; "Delivery path" is how it gets built. Illustrative only — the rows
come from this spec's answers, not from this example:
```
┌──────────────────────┬──────────────────────────┬───────────────┬──────────────────────────────────────────┐
│ Phase / action       │ Runs as                  │ Delivery path │ Why                                      │
├──────────────────────┼──────────────────────────┼───────────────┼──────────────────────────────────────────┤
│ Create rule          │ LCM action (Firewall     │ Direct        │ Rules are reviewed and removed later;    │
│                      │ Rule model — new)        │               │ runs phases 1–4                          │
│ Remove rule          │ LCM action               │ Direct        │ Teardown from the instance record        │
│ Diagnose blocked     │ Workflow                 │ Agent first   │ Procedure not written down; read tools   │
│ traffic              │                          │ (engineer's   │ exist; engineer chose to prove it first  │
│                      │                          │ choice)       │                                          │
│ Push to firewalls    │ Gateway5 service (reuse) │ Direct        │ Existing Ansible playbook, netops team   │
│                      │                          │               │ maintains it                             │
└──────────────────────┴──────────────────────────┴───────────────┴──────────────────────────────────────────┘
```
Cross-cutting concerns (throttling, per-device serialization) go in the decisions
table below.

Then the other decisions:
```
┌─────────────────────────────────────┬────────────────────────────────────────┐
│ Decision                            │ In This Environment                    │
├─────────────────────────────────────┼────────────────────────────────────────┤
│ ITSM integration                    │ ServiceNow — create incidents          │
│ Naming convention                   │ VLAN_{id}_{site} (customer standard)   │
└─────────────────────────────────────┴────────────────────────────────────────┘
```

**D. Modular Design — Decompose First**

Before listing components, decide the parent/child split. For a parent agent
with child agents, list each child as its own agent with its own job and inputs,
and cover in Section F how the parent handles a child that fails or stops and
any step that waits for a person. For workflow designs, ask for each phase:

- Can it be run and tested independently? → **Child workflow**
- Does it make sense to reuse it in other use cases? → **Child workflow**
- Does it loop over multiple items? → **Child workflow with `loopType`**
- Is it a one-off step that only makes sense in this flow? → **Task in orchestrator**

**Workflow rule:** Each logical phase becomes a child workflow. The orchestrator sequences them via childJob. This makes every phase independently testable before the orchestrator is built. It doesn't apply to parent and child agents.

**Example decomposition:**
```
Spec phases → Component split
─────────────────────────────────────────────────────────
Pre-flight validation        → Child: Pre-Flight Check
Execute change               → Child: Execute Change
Verify propagation           → Child: Verify Propagation
Rollback on failure          → Child: Rollback
Notifications + ticket close → Tasks in orchestrator
```

The orchestrator is always the last thing built, after all children are tested.

**D. Component Inventory**
```
┌────┬──────────────────────────────┬─────────────────────┬──────────┐
│ #  │ Component                    │ Type                │ Action   │
├────┼──────────────────────────────┼─────────────────────┼──────────┤
│ 1  │ Pre-Check                    │ Command Template    │ Build    │
│ 2  │ Backup workflow              │ Child Workflow      │ Reuse    │
│ 3  │ Orchestrator                 │ Parent Workflow     │ Build    │
└────┴──────────────────────────────┴─────────────────────┴──────────┘
```

Types the execution model adds: `LCM Resource Model`, `LCM Action` (on a new or
existing model), `Agent`, `Agent Tool Decorator`, `Gateway5 Service`,
`Inventory`. An existing resource model, agent or service the design builds on is
listed with Action `Reuse` or `Extend`.

For every `⚠ Stub` integration, add to the inventory:
- `integration-model-{name}.json` — OpenAPI 3.0.3 stub spec (Type: Integration Model, Action: Build)
- `stub-{name}` — stub connectivity workflow (Type: Stub Workflow, Action: Build)
- `integration-questions.md` — customer questionnaire (Type: Questionnaire, Action: Build — one file covers all pending integrations)

**Producing stub artifacts:**

`integration-model-{name}.json` — OpenAPI 3.0.3, minimal and use-case scoped:
- `info.title` — the adapter type name as it will appear in Itential (e.g., `Slack`, `AWX`) — this becomes the `app` and `locationType` field values in workflow tasks
- `info.description` — one line: what this integration does in this use case; append `— STUB: scope TBC with customer` if endpoints aren't yet confirmed
- `servers[].url` — use a `variables` block for unknown hostnames; add `"description": "STUB: confirm with customer"` to any unknown variable
- `components.securitySchemes` — mark `description` as `STUB: confirm auth method with customer` if not yet confirmed
- `paths` — only the operations the stub workflow will call; use accurate schemas where known

`integration-questions.md` — one section per pending integration, three-column table:

| Question | Why needed | Customer answer |
|----------|-----------|-----------------|
| Hostname / base URL | Needed to configure the adapter server | |
| Auth method (bearer / basic / API key) | Determines how credentials are stored | |
| Token source / how to obtain it | Needed to provision the adapter | |
| API version or path prefix differences | Affects endpoint wiring in workflows | |
| Firewall / IP allowlisting requirements | Platform must be able to reach this system | |

Close `integration-questions.md` with a **Next steps** note: once all questions are answered, update each integration model, provision the adapter, and replace placeholder tasks using the as-built activation recipes.

**E. Implementation Plan** — ordered build steps with test method for each

For a phase built agent first, plan two stages: (1) the agent and its test
sessions, with what counts as proven (e.g., N sessions on real requests with the
expected result) and who decides; (2) `/flowagent-to-spec` turns the proven
sessions into `<phase>-converted-spec.md`, which comes back through design-only
mode and Build. Stage 2 is planned now, not left for later; the engineer may still
decide at that point to keep the agent instead.

**F. Acceptance Criteria → Tests** — map each criterion to how to verify it. This is a first-pass mapping — `/qa-agent` refines it into an executable `test-plan.md` once real IDs exist after Build, but the verification *method* per criterion should be decided now, while the design is fresh.

### Present for Review

**Present the full solution design. Do NOT proceed to build until approved.**

Walk through each section:
- Execution model: "[Phase] runs as [model], built [agent first / direct], because [answer or inventory fact]. Agree?"
- Requirements: "I'll use [adapter/app]. Correct?"
- Decisions: "The spec says [X], I'll do [Y]. Sound right?"
- Components: "Reuse this? Build that? Skip this?"
- Plan: "Here's the build order. Agree?"

The engineer may:
- Change reuse → build ("that workflow is outdated")
- Add components ("we also need a cleanup workflow")
- Change the plan order
- Modify how acceptance criteria get tested

Update `{use-case}/solution-design.md` with every change.

---

## Design Approval

**When the engineer approves the solution design: it is locked.**

Both artifacts are now complete before any building begins:
1. `{use-case}/customer-spec.md` — HLD, approved (Requirements)
2. `{use-case}/feasibility.md` — assessment + decision, approved (Feasibility)
3. `{use-case}/solution-design.md` — Solution Design / LLD, approved (Design)

Hand off to `/builder-agent`. The workspace is complete.

---

## Handoff to Builder

**The workspace the `/builder-agent` agent receives:**

```
{use-case}/
  .auth.json              ← auth token
  .env                    ← credentials (for re-auth)
  use-case-memory.md      ← living context: platform refs, built assets, decisions, open items
  customer-spec.md        ← approved HLD
  feasibility.md          ← approved feasibility assessment
  solution-design.md      ← approved Solution Design / LLD
  customer-context.md     ← business rules, naming (if provided)
  openapi.json            ← platform API reference (pulled during feasibility)
  tasks.json              ← task catalog (pulled during feasibility)
  apps.json               ← app/adapter type names (pulled during feasibility)
  adapters.json           ← adapter instances (pulled during feasibility)
  applications.json       ← app health (pulled during feasibility)
  devices.json            ← device inventory (if spec involves devices)
  workflows.json          ← existing workflows (if reuse planned)
  device-groups.json      ← device groups (if spec involves groups)
  task-schemas.json       ← fetched on demand by builder during build (not pre-populated)
```

The builder builds from the locked plan and tests each component individually. Once the build is complete, `/builder-agent` hands off to `/qa-agent`, which runs acceptance testing against Section F's criteria-to-tests mapping and produces the `as-built.md` record.

**Before handing off — update `use-case-memory.md`** (create from `assets/helpers/use-case-memory.md` if `/spec-agent` didn't already):
- Platform URL and project name (if a project already exists)
- `Stage: build`, `Status: active`
- Any adapter instance names and type names resolved during feasibility
- Key decisions made during design (why this adapter, why this split, any constraints)
- The execution model per phase and its delivery path; for agent-first phases, that the `/flowagent-to-spec` conversion is still to come

**Update `Stage` at each internal transition too, not just at final handoff** — set `Stage: feasibility` when starting the feasibility assessment (if `/spec-agent` left it at `requirements`) and `Stage: design` once feasibility is approved and design work begins. Someone resuming mid-Feasibility shouldn't see `Stage: build`.

The builder will read this file first and update it after every build session.

---

## How This Gets Invoked

Entered from `/spec-agent` after the engineer approves `customer-spec.md`. At that point the workspace contains:

```
{use-case}/
  customer-spec.md    ← approved HLD (Requirements complete)
  .env                ← credentials
```

```
/solution-arch-agent flow:
    Feasibility: authenticate → pull platform data → assess capabilities → inventory LCM / FlowAgent / Gateway5 → write feasibility.md → engineer approves
    Design:      design the execution model with the engineer → produce solution-design.md → engineer approves
    Handoff:     pass complete workspace to /builder
```

To revise requirements: update `customer-spec.md` via `/spec-agent` → re-run `/solution-arch-agent` from Feasibility.
To revise design only: invoke `/solution-arch-agent design-only` → reads existing `feasibility.md` → produces updated `solution-design.md`.

---

## Gotchas

- Tokens expire mid-session — on auth errors, re-authenticate silently from `.env` (see `assets/AGENTS.md` Auth Reuse)
- `tasks/list` `app` field has WRONG casing for adapters — use `apps/list`
- OpenAPI spec is ~1.5MB — search it locally with `jq`, never load into context
