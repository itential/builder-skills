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

## Stage Expectations

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

If requirements are unchanged but the implementation plan needs to change, invoke `/solution-architecture design-only`. Skips Feasibility. Reads existing `feasibility.md` as context and produces an updated `solution-design.md`.

---

## Artifact Lifecycle

```
${CLAUDE_PLUGIN_ROOT}/spec-files/spec-*.md          ← Generic library spec (never modified)
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

Check for credentials in this order:
1. `{use-case}/.auth.json` — already authenticated (reuse token)
2. `{use-case}/.env` — credentials saved during setup
3. `${CLAUDE_PLUGIN_ROOT}/environments/*.env` — pre-configured environments at repo root

If none found, ask the engineer for:
1. Platform URL
2. Credentials (username/password or client_id/secret)

**Local Development (username/password):**
```
POST /login
Content-Type: application/json

{"username": "admin", "password": "admin"}
```
Returns a token string. Use as query parameter: `GET /endpoint?token=TOKEN`

**Cloud / OAuth (client_credentials):**
```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

client_id=YOUR_CLIENT_ID
client_secret=YOUR_CLIENT_SECRET
grant_type=client_credentials
```
Returns `{"access_token": "eyJhbG..."}`. Use as Bearer header.

**Save auth for all downstream skills:**
```bash
cat > {use-case}/.auth.json << EOF
{
  "platform_url": "https://platform.example.com",
  "auth_method": "oauth",
  "token": "eyJhbG...",
  "timestamp": "2026-03-13T10:00:00Z"
}
EOF
```

### Pull Platform Data

Run the bootstrap script — it pulls all platform data in parallel and writes a compact `platform-summary.json` with only what's needed for feasibility:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/.claude/skills/solution-arch-agent/pull-platform-data.py {use-case}
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
- Not found + Required? → **⚠ Blocked** (stop and discuss)
- Not found + Not Required? → **✗ Skipped**

### Find Reuse Opportunities

Search `workflows.json` for existing workflows that match spec phases. Flag as **↻ Reuse** candidates.

---

## Design

Produce the solution design from the approved spec + feasibility results.

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
│ ITSM integration                    │ ServiceNow — create incidents          │
│ Naming convention                   │ VLAN_{id}_{site} (customer standard)   │
└─────────────────────────────────────┴────────────────────────────────────────┘
```

**D. Modular Design — Decompose First**

Before listing components, decide the parent/child split. Ask for each phase in the spec:

- Can it be run and tested independently? → **Child workflow**
- Does it make sense to reuse it in other use cases? → **Child workflow**
- Does it loop over multiple items? → **Child workflow with `loopType`**
- Is it a one-off step that only makes sense in this flow? → **Task in orchestrator**

**Rule:** Each logical phase becomes a child workflow. The orchestrator sequences them via childJob. This makes every phase independently testable before the orchestrator is built.

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

**E. Implementation Plan** — ordered build steps with test method for each

**F. Acceptance Criteria → Tests** — map each criterion to how to verify it. This is a first-pass mapping — `/qa-agent` refines it into an executable `test-plan.md` once real IDs exist after Build, but the verification *method* per criterion should be decided now, while the design is fresh.

### Present for Review

**Present the full solution design. Do NOT proceed to build until approved.**

Walk through each section:
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

**Before handing off — update `use-case-memory.md`** (create from `helpers/use-case-memory.md` if `/spec-agent` didn't already):
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
/solution-architecture flow:
    Feasibility: authenticate → pull platform data → assess capabilities → write feasibility.md → engineer approves
    Design:      produce solution-design.md from approved feasibility → engineer approves
    Handoff:     pass complete workspace to /builder
```

To revise requirements: update `customer-spec.md` via `/spec-agent` → re-run `/solution-architecture` from Feasibility.
To revise design only: invoke `/solution-architecture design-only` → reads existing `feasibility.md` → produces updated `solution-design.md`.

---

## Gotchas

- OAuth MUST use `Content-Type: application/x-www-form-urlencoded`, not JSON
- Tokens expire mid-session — on auth errors, re-authenticate silently from `.env`
- `tasks/list` `app` field has WRONG casing for adapters — use `apps/list`
- OpenAPI spec is ~1.5MB — search it locally with `jq`, never load into context
