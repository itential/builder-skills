# Pending Integration Stub Pattern — Design Spec

**Date:** 2026-07-09
**Status:** Approved
**Source:** useCase-lightningAi (EmailOpensource adapter not installed on customer cloud instance)

---

## Problem

A customer's integration list is known but not yet finalized on their side — adapters aren't installed, hostnames aren't confirmed, auth methods are TBD. Under the current skills, this blocks delivery. Engineers either wait for the customer to finalize integrations before building anything, or build informally without guidance on how to structure the stub.

The goal: let delivery proceed in full, demonstrate progress to the customer via runnable stub workflows, and leave a clear activation path for each pending integration.

---

## Scope

**In scope:**
- Guidance for solution-arch-agent (feasibility status + design deliverables)
- Guidance for builder-agent (stub workflow structure + placeholder task pattern)
- Guidance for qa-agent (pending criteria handling)
- Four new AGENTS.md key rules from Lightning AI learnings

**Out of scope:**
- Promoting integration-model files to helpers/ (pattern only — files stay per use-case)
- Changes to spec-agent

---

## Design

### 1. New Feasibility Status: `⚠ Stub`

Add a third integration status to `solution-arch-agent` alongside the existing `⚠ Blocked`:

| Status | Meaning | Action |
|--------|---------|--------|
| `✓ Resolved` | Found, running | Proceed |
| `⚠ Stub` | Required, not yet available | Proceed with stub pattern |
| `⚠ Blocked` | Required, cannot proceed without it | Stop and discuss |
| `✗ Skipped` | Not required | Use fallback |

A `⚠ Stub` integration is required but either not installed on the platform or pending customer confirmation of connection details. Delivery proceeds — the Design stage produces stub artifacts for it.

---

### 2. Design Stage Deliverables (solution-arch-agent)

For each `⚠ Stub` integration, the Design stage produces two new artifacts added to the component inventory:

#### `integration-model-{name}.json` — OpenAPI 3.0.3 stub

Minimal, use-case scoped. Contains only the endpoints the workflows will actually call — not the full vendor API.

| Field | Rule |
|-------|------|
| `info.title` | The adapter type name as it will appear in Itential (e.g., `Slack`, `AWX`, `HashiCorpVault`) — becomes the `app` and `locationType` field values |
| `info.description` | One line describing what this integration does in this use case. Append `— STUB: scope TBC with customer` if the scope is still being confirmed. |
| `servers[].url` | Base URL. Use a `variables` block for unknown hostname; add `"description": "STUB: confirm with customer"` to any unknown variable. |
| `components.securitySchemes` | Auth method. Mark description `STUB: confirm auth method with customer` if not yet confirmed. |
| `paths` | Only the operations the stub workflow will test. Use accurate request/response schemas where known; omit optional fields that aren't needed. |

#### `integration-questions.md` — customer questionnaire

One section per pending integration. Each section has a three-column table:

| Column | Purpose |
|--------|---------|
| **Question** | What needs to be answered |
| **Why needed** | What it unblocks (so the customer understands urgency) |
| **Customer answer** | Blank — for the customer to fill in |

Standard questions per integration:
- What is the hostname / base URL for this system?
- What auth method is used (bearer token / basic auth / API key / mTLS)?
- Where is the token issued / how is it obtained?
- Are there specific API versions or path prefixes that differ from the standard?
- Any firewall rules or IP allowlisting required for the Itential platform to reach this system?

Close the file with a **Next steps** note: once all questions are answered, the engineer updates the integration model, provisions the adapter, and replaces placeholder tasks using the as-built activation recipes.

---

### 3. Stub Workflow per Integration (builder-agent)

Named `stub-{integration-name}` (e.g., `stub-slack`, `stub-awx`). Exercises one core connectivity action. Structure:

```
workflow_start
    → buildPayload    (newVariable — assembles minimum input for the core action)
    → callIntegration (newVariable placeholder — pending_adapter sentinel)
         ↓ error
    → workflow_end
workflow_end
```

**Rules:**
- `buildPayload` — always a `newVariable` task. Assembles the minimum required input for the core action (e.g., for Slack: `{channel, text}`). No adapter dependency — always runnable.
- `callIntegration` — the `newVariable` placeholder. Sets `{integrationName}Status = "pending_adapter"`. This is the task ID that the real adapter task will occupy when activated. Error transition pre-wired to `workflow_end`.
- One input variable: `dryRun` (boolean, default `true`) — signals this is a connectivity test. Stub ignores it; activated workflow can use it to skip side effects during testing.
- Group all stub workflows in the same project as the main delivery workflows.

**Choosing the core action:**
- Use the simplest write/action operation (post a message, launch a job, write a secret)
- Prefer an operation that validates auth end-to-end (not just a GET list)
- If the integration is read-only in the use case, use a lightweight read (get current user, health check)

---

### 4. Placeholder Task Pattern (builder-agent)

When any workflow needs to call an adapter that isn't installed:

1. Place a `newVariable` task in the exact position the real adapter task will occupy
2. Use the same task ID (hex) that will be used for the real task
3. Set the variable: `{integrationName}Status = "pending_adapter"` — machine-readable pending state
4. Wire transitions identically to how the real task will be wired (including error transitions)

**As-built "Activate Integration" section** — one entry per pending integration:

```markdown
## Activate: {Integration Name}

When the {AdapterType} adapter is provisioned:

1. Confirm adapter instance name:
   jq '.results[] | select(.package_id | test("{name}";"i")) | {id,state}' adapters.json

2. Replace task `{taskId}` in workflow `{workflowId}` with:
   {complete replacement task JSON, all fields pre-filled from integration-model-{name}.json}
   Only field to fill in: `adapter_id` — the instance name from step 1.

3. Verify field names from the live schema:
   POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true
   body: {"tasks": [{"name": "{taskName}", "app": "{appType}"}]}
```

**Reusability:** this pattern works identically for standard Itential adapters (EmailOpensource, Slack) and custom OpenAPI virtual integrations. The integration model file is the contract in both cases.

---

### 5. qa-agent: Pending Criteria Handling

For acceptance criteria that depend on a `⚠ Stub` integration:

- Mark status `⏳ Pending adapter` in the test report
- Do not mark as failed — the workflow is structurally correct; the integration is the blocker
- Include the specific activation steps (from the as-built) inline in the test report entry
- All other criteria are evidenced normally

Example test report entry:
```
| Criterion | Status | Evidence |
|-----------|--------|----------|
| Email sent to recipient | ⏳ Pending adapter | EmailOpensource not installed. Workflow reaches sendEmail task; placeholder sets emailStatus=pending_adapter. Activate per as-built §Activate: Email. |
```

---

### 6. AGENTS.md Key Rules (Lightning AI learnings)

Four rules to add, applying to any cloud/SaaS Itential engagement:

**Rule 26 — Cloud/SaaS auth:** The `/login` endpoint may return 500 on cloud instances — it is broken server-side on SaaS, not a credential issue. Always use `POST /oauth/token` with `grant_type=client_credentials` on cloud instances.

**Rule 27 — Workflow variable path:** Job output variables live at `.data.variables.{varName}` (flat), not `.data.variables.job.{varName}`. The `.job` nesting does not exist. Wrong path silently returns null.

**Rule 28 — Template `group` field:** Cannot be an empty string. Passing `group: ""` causes a validation error. Use a real group name or `"Default"`.

**Rule 29 — Service account creation:** On cloud instances, creating a service account for API access requires navigating to **Admin Essentials → Service Accounts** — it is not accessible from the main nav. Standard user management screens do not expose this.

---

## Files Changed

| File | Change |
|------|--------|
| `.claude/skills/solution-arch-agent/SKILL.md` | Add `⚠ Stub` status to Resolve Integrations; add integration model + questionnaire to Design deliverables |
| `.claude/skills/builder-agent/SKILL.md` | Add stub workflow pattern + placeholder task pattern + as-built activation recipe |
| `.claude/skills/qa-agent/SKILL.md` | Add pending criteria handling |
| `AGENTS.md` | Add rules 26–29 |

---

## Connections to Use Case

All patterns in this spec are directly derived from `useCase-lightningAi`:
- Stub status and `integration-model-*.json` files — 10 integration models produced during design
- `LightningAI-Integration-Questions.xlsx` — the questionnaire pattern (format changed to Markdown)
- `newVariable` placeholder for EmailOpensource — the placeholder task pattern
- As-built activation recipe for `d4e5` task — the activation section pattern
- Rules 26–29 — direct from `as-built.md` Learnings section
