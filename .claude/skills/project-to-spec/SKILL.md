---
name: project-to-spec
description: Use this skill when a user names a specific existing Itential project and wants it documented — reverse-engineered into a requirements spec and solution design. Trigger it for phrases like "document the DNS_Management project", "create a spec from the Firewall_Rule_Lifecycle project", "reverse-engineer project X into a spec", "I have a project with no docs — produce a customer-spec and solution design for it", or "use this project as a baseline for a rebuild". Reads the project's workflows, templates, and MOP components, infers business purpose and design decisions, and produces customer-spec.md + solution-design.md. For documenting global/unprojectized assets across the whole platform, use /documentation instead.
argument-hint: "[project-name or project-id]"
---

# Project to Spec

**Purpose:** Read an existing project → produce documentation
**Output:** `customer-spec.md` (inferred HLD) + `solution-design.md` (as-built LLD)
**Feeds into:** Can be handed directly to `/solution-arch-agent` (design-only mode) or `/spec-agent` for refinement

---

## What This Does

Takes an undocumented or partially-documented project and produces the spec and design documents that *should* have existed before it was built. The engineer reviews and corrects the inferred documents — then they can feed into the standard delivery lifecycle for updates, rebuilds, or knowledge transfer.

```
Existing Project
      │
      ├── Pull all components (workflows, templates, MOP)
      ├── Read each workflow: tasks, adapters, transitions, data flows
      ├── Infer: business purpose, phases, inputs, outputs, integrations
      │
      ├── customer-spec.md   ← inferred HLD (engineer reviews + corrects)
      └── solution-design.md ← as-built LLD (actual component inventory)
```

---

## Step 1: Identify the Project

Ask the engineer for a project name or ID. Then pull the project:

```
GET /automation-studio/projects/{projectId}
```

Or search by name:
```
GET /automation-studio/projects?contains=name:{projectName}
```

Response: `{message, data: {_id, name, components: [...], members: [...]}}`

Save the project ID and component list.

---

## Step 2: Pull All Components

For each component in the project, fetch the full document.

**Workflows:**
```
GET /automation-studio/workflows/detailed/{urlEncodedName}
```

**Templates:**
```
GET /automation-studio/templates/{id}
```

**MOP Command Templates:**
```
GET /mop/listATemplate/{name}
```

For each workflow, extract and save locally:
- `tasks` — every task with name, app, adapter, incoming/outgoing variables
- `transitions` — the flow between tasks
- `inputSchema` / `outputSchema` — what the workflow accepts and returns
- Task summaries and descriptions (these often contain intent)

Save to `{use-case}/project-components.json`.

---

## Step 3: Analyze the Components

Work through the components to reconstruct intent and structure.

### Identify the orchestrator

Find the parent workflow — usually the one that:
- Has no `childJob` references pointing to it from other workflows
- References other workflows via `childJob` tasks
- Has the most complex transition graph

### Map the data flow

For the orchestrator and each child:
1. What are the **inputs**? (inputSchema properties)
2. What adapters are called? (location: "Adapter" tasks)
3. What utility tasks are used? (merge, query, evaluation, childJob, makeData)
4. What are the **outputs**? (outputSchema properties, $var.job.x assignments)
5. What external systems are touched? (adapter names → infer ServiceNow, Route53, etc.)

### Infer the phases

Each major section of the orchestrator maps to a phase:
- A `childJob` to a child workflow = one phase
- An `evaluation` branch = a decision point
- An adapter call cluster = an integration phase
- A `ViewData` = an approval gate
- Error handling branches = rollback/recovery phases

### Reconstruct acceptance criteria

From the workflow structure, infer what "done" looks like:
- What does the final outgoing variable represent?
- What adapters were called? → "ServiceNow ticket created and updated"
- What verifications exist? → `evaluation` tasks checking status
- What is the `outputSchema`? → these are the observable outcomes

---

## Step 4: Produce `customer-spec.md`

Write the inferred HLD. Use the standard spec structure but mark inferred sections clearly.

```markdown
# Use Case: {Inferred Name}

> **Note:** This spec was produced by reading project `{projectName}` ({projectId}).
> Review and correct any inferences before using as a delivery baseline.

## 1. Problem Statement
{Inferred from workflow descriptions, adapter usage, and task summaries}

## 2. High-Level Flow
{Inferred from orchestrator transition graph}

## 3. Phases
{One section per major workflow / childJob cluster}

## 4. Key Design Decisions
{Inferred from adapter choices, error handling patterns, approval gates}

## 5. Scope
**In scope (as built):** {list components that exist}
**Not observed:** {common patterns not present — rollback, notifications, etc.}

## 6. Risks & Mitigations
{Inferred from error transitions, evaluation branches}

## 7. Requirements

### Capabilities
{Derived from apps and tasks used}

### Integrations
{Derived from adapter names and instance IDs}

## 8. Batch Strategy
{Inferred from childJob loopType usage}

## 9. Acceptance Criteria
{Inferred from outputSchema and evaluation checks}
```

---

## Step 5: Produce `solution-design.md`

Write the as-built LLD — this is factual, not inferred.

```markdown
# Solution Design: {Project Name}

> **As-Built** — produced by reading project `{projectId}`.

## A. Environment Summary
{Platform, adapters found, apps used}

## B. Component Inventory
| # | Component | Type | Workflow/Template Name | ID |
|---|-----------|------|----------------------|-----|
| 1 | {name} | {workflow/template/mop} | {actual name} | {id} |
...

## C. Adapter Mappings
| Adapter | app name | adapter_id | Tasks Used |
|---------|----------|-----------|------------|
| ServiceNow | Servicenow | ServiceNow | createChangeRequest, updateChangeRequest |
...

## D. Workflow Structure
For each workflow: inputs, task sequence, outputs, error handling pattern.

## E. Data Flow
Key variables and how they move between tasks and workflows.

## F. Known Gaps
Patterns not present that are typically expected:
- No rollback logic observed
- No notifications (email/Teams)
- No audit trail
etc.
```

---

## Step 6: Present to Engineer

Show both documents and walk through:

1. **Inferences to verify** — "I inferred the purpose is X based on the adapter usage and task names. Is that correct?"
2. **Gaps** — "I don't see rollback logic or notifications. Were these intentional omissions or should they be added?"
3. **Next steps** — offer three options:
   - **Use as-is** — accept the documents as the baseline for this project
   - **Refine the spec** — hand to `/spec-agent` to refine the requirements with the engineer
   - **Redesign** — hand to `/solution-arch-agent` in design-only mode to produce an updated implementation plan

---

## What to Watch For

**Orphaned tasks:** Tasks with no useful summary — check their adapter/app and incoming variables to infer purpose.

**Non-hex task IDs:** If you encounter task IDs like `apush` or `myTask`, note them — these are a known bug pattern ($var references silently fail on these).

**Deep nesting:** childJob → childJob → childJob patterns indicate a modular design — document each layer separately.

**Static values as indicators:** Hard-coded strings in merge tasks or newVariable tasks often reveal business rules (e.g., `"value": "production"` → production-only path).

**Missing error transitions:** Note any adapter tasks without error transitions — this is a quality gap in the existing implementation.

---

## Gotchas

- Workflow names include `@projectId:` prefix — strip it when displaying to the engineer
- `GET /automation-studio/workflows?exclude-project-members=false` is needed to list project-owned workflows
- Template `data` field is a JSON string, not an object — parse it before analyzing
- childJob `workflow` field shows the child workflow name (with prefix) — this is the dependency graph
- Task descriptions and summaries are the best source of intent — use them heavily
