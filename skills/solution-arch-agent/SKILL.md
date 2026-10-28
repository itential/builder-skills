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
| **Agent does** | Connects to platform, assesses capabilities, checks adapters, finds reuse candidates, identifies constraints |
| **Engineer action** | Reviews assessment and approves decision to proceed |
| **Deliverable** | `feasibility.md` (assessment + decision) |
| **Customer receives** | Feasibility assessment with a clear decision (feasible / feasible with constraints / not feasible), flagged constraints, and identified reuse opportunities. |

Feasibility confirms what is possible. Decision options: **feasible**, **feasible with constraints**, **feasible with changes**, or **not feasible**. Design does not start until feasibility is approved.

### Design

| | |
|--|--|
| **Engineer provides** | Approved `feasibility.md` |
| **Agent does** | Produces implementation design — component inventory, adapter mappings, reuse decisions, build order, test plan |
| **Engineer action** | Reviews and approves the solution design |
| **Deliverable** | `solution-design.md` (Solution Design / LLD, approved) |
| **Customer receives** | Solution Design / LLD — component inventory, adapter mappings, build order, and acceptance criteria mapped to tests. Nothing is built until this is signed off. |

Design defines how it will be delivered. Nothing is built until this is approved.

### Design-Only Mode

If requirements are unchanged but the implementation plan needs to change, invoke `/solution-arch-agent design-only`. Skips Feasibility. Reads existing `feasibility.md` as context and produces an updated `solution-design.md`.

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

**After running, read `platform-summary.json` for feasibility. Search raw files locally when you need specifics — never load them into context.**

### File Shapes and jq Queries

Every file has a specific shape. Use these queries — don't guess.

| File | Shape | Example query |
|------|-------|---------------|
| `platform-summary.json` | `{adapters, applications, adapter_type_names, projects, workflow_count, device_count}` | `jq '.adapters[] | select(.connection == "ONLINE")' platform-summary.json` |
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

### Recommend the Execution Model

Before writing `feasibility.md`, decide which execution model each spec phase
uses — see **Choosing the Execution Model** below — and check the platform can
run it. Record the result in a short **Execution Model** section of
`feasibility.md`: one row per phase, the model, why, and the platform check that
backs it. A model the spec needs but the platform can't run is a constraint, the
same as a missing adapter.

---

## Choosing the Execution Model

A delivery is built from four execution models. They are layers, not
alternatives — most designs combine two or three — so choose per phase, not once
for the whole use case.

| Model | What it is | Built with |
|-------|------------|------------|
| **Deterministic workflow** | Fixed steps and branches; same inputs, same path every run | Automation Studio workflows, Operations Manager triggers |
| **LCM resource** | A resource model whose instances keep their state between runs; each lifecycle operation is an action backed by a workflow | `/itential-lcm` — resource model + action workflows |
| **FlowAgent** | An LLM chooses which tools to call, in what order, from the request and what it finds | `/flowagent` — agents, tools, decorators, work items |
| **Gateway5 service** | Python, Ansible or OpenTofu run on an Itential Gateway5 cluster, called from a workflow or an agent | `/iag` — `GatewayManager.runService` |

**The deterministic workflow is the default.** Recommend another model only when
a signal below applies, and say which signal.

### When to recommend each

**LCM resource** — the use case manages a *thing* that outlives one run.

| Recommend when | Don't recommend when |
|----------------|----------------------|
| The spec has more than one lifecycle operation on the same object — create, then modify, delete or decommission later | The job is one-shot: a backup, a compliance run, a set of show commands, a report |
| Someone needs to see what has been provisioned and its current state (VLANs, ports, IP blocks, firewall rules, circuits, tenant services) | The source of truth for that state is an external system the customer won't move (NetBox, ServiceNow CMDB, an IPAM) — read and write it from a workflow instead |
| Day-2 operations need the data captured at create time (modify a service without re-entering it, delete exactly what was built) | Each run is independent and nothing from it is needed afterwards |

Each LCM action is still a deterministic workflow — LCM adds the model, the
instance record and the action history around it. Every action workflow must
output an `instance` variable; carry that rule into the design (see
`/itential-lcm`).

**FlowAgent** — the path depends on judgment that can't be written down as rules.

| Recommend when | Don't recommend when |
|----------------|----------------------|
| The input is free text or unstructured (a ticket description, a user request in plain language, log or `show` output to interpret) | The steps and branches are known — write them as a workflow |
| Troubleshooting or triage, where the next check depends on what the last one found | It runs at high volume, or on a schedule, where cost and run time matter |
| The engineer wants to prove a pattern before committing to fixed steps | The customer needs the same result every run for audit or change control |
| Many read-only tools, and which ones to call varies per request | It changes production configuration with no person approving first |

Keep an agent's writes behind deterministic steps: give it workflows as tools for
anything that changes a device or a record, and put a human approval (work item)
before any change — see `/flowagent`. Once the agent's sessions show a stable
pattern, `/flowagent-to-spec` turns it into a deterministic workflow spec; say so
in the design when you recommend an agent as a first step.

**Gateway5 service** — the logic belongs in code that runs near the devices or
the cloud.

| Recommend when | Don't recommend when |
|----------------|----------------------|
| The customer already has a Python script, Ansible playbook or Terraform/OpenTofu plan to reuse | A native task or adapter already does it — search `tasks.json` first |
| It needs Python packages or vendor SDKs (netmiko, NAPALM, a cloud SDK), or a device protocol no adapter covers | It's a CLI command or config push — use `GatewayManager.sendCommand` / `sendConfig`, or `/itential-mop` for checks |
| Cloud or infrastructure provisioning — use an OpenTofu plan | It only reshapes data already in the workflow — use `GatewayManager.runCode` |
| The same code is reused by several workflows or agents and should be versioned in a repository | It's orchestration, approvals or ITSM — that's the workflow's job |

`runCode` and `runService` both run on Gateway5: `runCode` is short inline Python
over data the workflow passes in; `runService` runs a versioned service from a
repository, with its own packages, decorator and device access. Never design new
work on Gateway4 (`AGManager` tasks); for an existing Gateway4 estate, point to
`/gateway4-to-gateway5`.

### Decide in this order

1. **Is there a resource with more than one lifecycle operation?** → LCM resource
   model; each operation becomes an action workflow. Otherwise, no LCM.
2. **For each phase: can its steps and branches be written down?** → Deterministic
   workflow. If not, and the judgment is essential, a FlowAgent for that phase
   only — called from the workflow with `AgentSessionManager.runAgent`, or the
   agent at the front calling workflows as tools.
3. **For each step that touches a device, system or cloud:** native task or
   adapter → use it; existing script, playbook or plan, or a package/SDK need →
   Gateway5 service; data reshaping only → `runCode`.

Typical combinations:

```
Service with a lifecycle      LCM model → action workflows → adapters / Gateway5 services
Request intake or triage      FlowAgent → workflows as tools (writes) + read-only tools
Fixed change with one         Workflow → runAgent for the judgment step → workflow continues
  judgment step
Reuse customer automation     Workflow → Gateway5 services (existing scripts/playbooks/plans)
```

### Check the platform can run it

| Model | Check | Where |
|-------|-------|-------|
| LCM resource | `LifecycleManager` application `RUNNING`; `runAction` in the task catalog | `applications.json`, `tasks.json` |
| FlowAgent | `AgentProjectService`, `AgentSessionManager` and `AgentExecutionEngine` `RUNNING`; an LLM provider profile the engineer can use | `applications.json`, `GET /model-registry-service/profiles` |
| Gateway5 service | `GatewayManager` `RUNNING`; a connected Gateway5 cluster | `applications.json`, `GET /gateway_manager/v1/gateways` |

If a check fails: say so in `feasibility.md`, give the fallback (e.g., a
deterministic workflow writing to an external source of truth instead of LCM; a
workflow instead of an agent) and let the engineer choose. Don't switch models
without the engineer agreeing.

### Who decides

The recommendation is yours; the choice is the engineer's. If the spec already
names a model ("build an agent", "use LCM"), follow it, and record any concern
from the tables above as a risk instead of overriding it.

---

## Design

Produce the solution design from the approved spec + feasibility results.

**Gateway4 → Gateway5 migration:** design each item from its readiness-report code (WRAP / REVIEW /
ARGS / INV) using `assets/helpers/gateway-migration/conversion-guide.md` — the inventory mapping, the
service per script/playbook, the task-by-task rewire, and a parity test per workflow for Section F.
The migrated workflows are built as a new project alongside the originals.

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
```
┌─────────────────────────────────────┬────────────────────────────────────────┐
│ Decision                            │ In This Environment                    │
├─────────────────────────────────────┼────────────────────────────────────────┤
│ Execution model                     │ LCM model; actions are workflows       │
│ ITSM integration                    │ ServiceNow — create incidents          │
│ Naming convention                   │ VLAN_{id}_{site} (customer standard)   │
└─────────────────────────────────────┴────────────────────────────────────────┘
```

Start Section C with the execution model per phase from feasibility, and the
signal that justifies anything other than a deterministic workflow (see
**Choosing the Execution Model**).

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

Other types to use as the execution model requires: `LCM Resource Model`,
`LCM Action Workflow`, `FlowAgent`, `Agent Tool Decorator`, `Gateway5 Service`.

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

**F. Acceptance Criteria → Tests** — map each criterion to how to verify it. This is a first-pass mapping — `/qa-agent` refines it into an executable `test-plan.md` once real IDs exist after Build, but the verification *method* per criterion should be decided now, while the design is fresh.

### Present for Review

**Present the full solution design. Do NOT proceed to build until approved.**

Walk through each section:
- Execution model: "[Phase] runs as [model] because [signal]. Agree?"
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
    Feasibility: authenticate → pull platform data → assess capabilities → write feasibility.md → engineer approves
    Design:      produce solution-design.md from approved feasibility → engineer approves
    Handoff:     pass complete workspace to /builder
```

To revise requirements: update `customer-spec.md` via `/spec-agent` → re-run `/solution-arch-agent` from Feasibility.
To revise design only: invoke `/solution-arch-agent design-only` → reads existing `feasibility.md` → produces updated `solution-design.md`.

---

## Gotchas

- Tokens expire mid-session — on auth errors, re-authenticate silently from `.env` (see `assets/AGENTS.md` Auth Reuse)
- `tasks/list` `app` field has WRONG casing for adapters — use `apps/list`
- OpenAPI spec is ~1.5MB — search it locally with `jq`, never load into context
