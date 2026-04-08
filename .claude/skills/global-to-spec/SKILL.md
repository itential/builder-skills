---
name: global-to-spec
description: Document individual Itential platform assets (workflows, forms, transformations, templates, command templates MOP, analytic templates, operations manager automations) that are NOT part of a project. Discovers relationships between standalone assets, groups them into use cases, and produces customer-spec.md + solution-design.md per use case plus a master README. Use when documenting global/standalone assets without existing documentation. NEVER use on project files — use /project-to-spec for those.
argument-hint: "[directory-path or 'platform']"
---

# Global Assets to Spec

**Purpose:** Read individual/global Itential assets → discover relationships → group into use cases → produce documentation
**Output:** `customer-spec.md` (inferred HLD per use case) + `solution-design.md` (as-built LLD per use case) + `README.md` (master readme for the generated reports)
**Feeds into:** Can be handed to `/spec-agent` for refinement or `/solution-arch-agent` for redesign

## CRITICAL: Output Requirements

**The ONLY deliverables are markdown files.** Do NOT produce JSON index files, JSON catalogs, or any intermediate artifacts. All analysis happens in-memory. The output structure is:

```
{reports-directory}/
  README.md                          ← master index of all use cases
  {use-case-slug}/
    customer-spec.md                 ← inferred HLD (business purpose, scope, requirements)
    solution-design.md               ← as-built LLD (components, flows, adapters, data model)
  {use-case-slug}/
    customer-spec.md
    solution-design.md
  ...
```

**Never write JSON files as output.** No `workflow-index.json`, no `asset-index.json`, no `use-case-groups.json`. The user wants documentation, not data dumps.

---

## What This Does

Takes a collection of undocumented, standalone Itential assets — workflows, JSON forms, transformations, templates, command templates, and Operations Manager automations — that are NOT grouped into projects. Discovers how they relate to each other, groups them into logical use cases, and produces documentation for each group plus a master index.

**This is NOT for projects.** If the user has a project file (`.project.json` or project ID), redirect them to `/project-to-spec`.

```
Individual Assets (workflows, forms, templates, transformations, command templates, analytic templates, MOP, OM automations)
      |
      ├── Phase 1: Collect + classify assets (in-memory only)
      ├── Phase 2: Discover relationships + group into use cases (in-memory only)
      ├── Phase 3: Present proposed groupings to engineer for approval
      ├── Phase 4: Write per-use-case reports (customer-spec.md + solution-design.md)
      ├── Phase 5: Write master README.md
      └── Phase 6: Present summary to engineer for review
```

---

## Step 1: Collect and Classify Assets

Ask the engineer for the asset source. Two modes:

### Mode A — Local Directory

The engineer provides a path to a directory containing exported asset JSON files. Scan for:

```
directory/
  workflows/                          *.json
  json_forms/                         *.json
  transformations/                    *.json or *.jst.json
  templates/                          *.json
  command_templates/                  *.json
  operations_manager_automations/     *.json
```

If the directory is flat (all JSON at root), classify by JSON structure.

**Skip project files.** If a `projects/` subfolder exists, ignore it entirely.

### Mode B — Platform API

Authenticate using `.auth.json` (see AGENTS.md auth reuse pattern). Fetch global assets:

```
GET /automation-studio/workflows?exclude-project-members=true&limit=500
GET /automation-studio/templates?limit=500
GET /operations-manager/automations
GET /automation-studio/json-forms?limit=500
GET /mop/templates
```

### Classification Signatures

| Asset Type | Identifying Fields |
|---|---|
| **Workflow** | `tasks` (object), `transitions` |
| **JSON Form** | `schema`, `struct`, `uiSchema` |
| **Transformation** | `incoming`, `outgoing`, `steps` |
| **Template** | `type` (textfsm/jinja2), `template` field |
| **Command Template** | `commands[]` with `rules[]` |
| **OM Automation** | `triggers[]`, `componentName` |

**Build the asset index in-memory only.** For each asset, note: name, file path, type, and key metadata (task count, adapters, childJobs for workflows; componentName for OM automations).

---

## Step 2: Discover Relationships and Group

### Relationship Discovery

Build a relationship graph in-memory connecting all assets:

1. **Workflow → Workflow (childJob links):** For each workflow task where `name === "childJob"` AND `app === "WorkFlowEngine"`, extract child workflow name from `variables.incoming.workflow`. Strip `@projectId:` prefixes.

2. **Workflow → JSON Form:** Tasks where `app === "JsonForms"` or name contains `RenderJsonSchema`/`JsonForm`.

3. **Workflow → Template:** Tasks where `app === "TemplateBuilder"` (renderJinjaTemplate, applyTemplate, applyTextFSMTemplate).

4. **Workflow → Transformation:** Tasks where `name === "transformation"`.

5. **Workflow → Command Template:** Tasks referencing MOP operations (runCommandTemplate).

6. **OM Automation → Workflow:** `componentName` field names the target workflow. Trigger types reveal entry mode: schedule, endpoint (webhook/API), manual (with optional formId).

7. **Adapter patterns:** Collect tasks where `location === "Adapter"` — extract `app` (type name) and operation name.

8. **Naming prefix clustering:** Split on ` - ` (space-dash-space). Assets sharing a prefix are candidates for the same use case.

### Grouping Rules (apply in order)

1. **OM Automations as Entry Points:** Each OM automation's `componentName` → root workflow → traverse childJob graph → collect all reachable workflows + referenced forms/templates/transformations/command templates = one cluster.

2. **Expand by Naming Prefix:** Add ungrouped workflows sharing the same naming prefix as workflows already in a cluster.

3. **Ungrouped Workflow Trees:** Any root workflow (no parent) with children → new cluster.

4. **Shared Utilities:** Workflows appearing in 3+ clusters → "Shared Utilities" group. Also include: generic TextFSM templates, utility transformations (math, array ops), common utilities (MongoDB CRUD, credential retrieval, notifications).

5. **Test / Standalone:** Workflows with developer name prefixes, `[TEST]`/`test-`/`dummy` patterns, Jira ticket patterns, or <5 tasks with no children and no triggers → "Standalone / Test Workflows" (catalog only, no full HLD/LLD).

6. **Remaining Ungrouped:** Group by functional similarity or list as individual entries in master README.

### Analyze the Components

Work through the components to reconstruct intent and structure.

#### Identify the orchestrator

Find the parent workflow — usually the one that:
- Has no `childJob` references pointing to it from other workflows
- References other workflows via `childJob` tasks
- Has the most complex transition graph

#### Map the data flow

For the orchestrator and each child:
1. What are the **inputs**? (inputSchema properties)
2. What adapters are called? (location: "Adapter" tasks)
3. What utility tasks are used? (merge, query, evaluation, childJob, makeData)
4. What are the **outputs**? (outputSchema properties, $var.job.x assignments)
5. What external systems are touched? (adapter names → infer ServiceNow, Route53, etc.)

#### Infer the phases

Each major section of the orchestrator maps to a phase:
- A `childJob` to a child workflow = one phase
- An `evaluation` branch = a decision point
- An adapter call cluster = an integration phase
- A `ViewData` = an approval gate
- Error handling branches = rollback/recovery phases

#### Reconstruct acceptance criteria

From the workflow structure, infer what "done" looks like:
- What does the final outgoing variable represent?
- What adapters were called? → "ServiceNow ticket created and updated"
- What verifications exist? → `evaluation` tasks checking status
- What is the `outputSchema`? → these are the observable outcomes

---

## Step 3: Present Groupings to Engineer

**Stop and present the proposed groupings before writing any reports.** Ask:

1. "Here are the use case groups I identified — does this look right?"
2. "These assets are ungrouped — should any be added to an existing group?" - default no
3. "These appear to be test/dev workflows — should I catalog or skip them?" - default skip

Show each group with: name, category (Core/Specialized/Shared/Reference), approximate workflow count, and 1-line description.

**Wait for engineer approval before proceeding to Phase 4.**

---

## Step 4: Write Per-Use-Case Reports

For each approved use case group, create a directory with two markdown files.

### Produce `customer-spec.md`

Write professional, narrative documentation — not mechanical spec sheets. The HLD should read like a business-facing document with rich prose, detailed tables, and domain-specific context.

````markdown
# {Use Case Name} - High-Level Design (HLD)

**Use Case:** {One-Line Description}
**Version:** {Version or build identifier, if discoverable from naming or descriptions}

> **Note:** This spec was produced by reading global assets `{numberOfAssets} {typeOfAssets}`.
> Review and correct any inferences before using as a delivery baseline.

---

## 1. Problem Statement
{Write 1-2 RICH PARAGRAPHS of narrative prose. This is NOT a bullet list.

Paragraph 1: Describe the overall purpose and business context — what this automation does, why it exists, what business problem it solves.

Paragraph 2: Describe the major functional areas or modes of operation — what systems are integrated, what types of automation are covered, how they connect. Also describe the operator experience — how users interact with the system, what entry points exist, what the operational model looks like.

Infer from workflow descriptions, adapter usage, task summaries, OM trigger configurations, and naming patterns.}

## 2. High-Level Flow
{Inferred from orchestrator transition graph}

## 3. Phases
{One section per major workflow / childJob cluster}

## 4. Key Design Decisions
{Inferred from adapter choices, error handling patterns, approval gates}

## 5. Scope
**In scope (as built):** {list components that exist}
**Not observed:** {common patterns not present — rollback, notifications,audit trail, etc.}

## 6. Risks & Mitigations
{Inferred from error transitions, evaluation branches}

## 7. Requirements

### Capabilities
{Derived from apps and tasks used}

### Integrations
{Derived from adapter names and instance IDs}

## 8. Batch Strategy
{Inferred from childJob loopType usage}

## 9. User Interaction Model

### 9.1 Entry Points

| Entry Point | Trigger | Description |
|---|---|---|
| {Entry point name} | {Manual launch / Scheduled / Endpoint trigger / etc.} | {How this entry point works and what it initiates} |

### 9.2 Operator Workflow (Manual Path)

1. **{Action name}** -- {Detailed description of what happens at this step, what the operator sees, what choices are available.}
2. **{Action name}** -- {description}
3. ...

### 9.3 Automated Path

1. {Step description — what triggers, what runs, what the system checks}
2. {Step description}
3. ...

## 10. Integration Points

| System | Direction | Purpose |
|---|---|---|
| **{System name}** | {Bi-directional / Inbound / Outbound} | {What data flows and why, including specific operations} |

## 11. Acceptance Criteria
{Inferred from outputSchema and evaluation checks}
```

**For test/standalone use cases**, use a simplified catalog format — workflow table with Purpose and Adapters columns only. No full HLD needed.

### Produce `solution-design.md`

Write the as-built LLD — this is factual, not inferred. Each component should have at least a sentence description, so an engineer could understand the full system without reading the source JSON.

````markdown
# {Use Case Name} - Solution Design (LLD)

**Use Case:** {One-Line Description}
**Version:** {Version if discoverable}

> **As-Built** — produced by reading global assets `{numberOfAssets} {typeOfAssets}`.
> Review and correct any inferences before using as a delivery baseline.

---

## A. Environment Summary
{Platform, adapters found, apps used}

## B. Component Inventory
| # | Component | Type | Workflow/Template Name | Purpose | ID | 
|---|-----------|------|----------------------|-----------| -----|
| 1 | {name} | {workflow/template/mop} | {actual name} | {A sentence or two purpose description. Describe what this item does, what systems it touches, and its role in the overall flow.} | {id} |
...

## C. Adapter Mappings
| Adapter | app name | adapter_id | Tasks Used |
|---------|----------|-----------|------------|
| ServiceNow | Servicenow | ServiceNow | createChangeRequest, updateChangeRequest |
...

## D. Workflow Hierarchy

```
{Detailed ASCII tree showing the FULL call chain. Start with OM triggers at top,
then manual entry points, then show the complete parent-child workflow graph.}

Operations Manager Triggers
  |
  |-- {OM Trigger Name} ({schedule type})
  |     |-- {Target Workflow}
  |           |-- {Child Workflow}
  |           |-- {Child Workflow}
  |
Manual Entry Points:
  |
  |-- {Entry Workflow} (master orchestrator)
  |     |-- {Child Workflow} (per-item lifecycle)
  |           |-- {Grandchild Workflow}
```

## E. Workflow Structure
For each workflow: inputs, task sequence, outputs, error handling pattern.

## F. Data Flow
Key variables and how they move between tasks and workflows.

## G. Known Gaps
Patterns not present that are typically expected:
- No rollback logic observed
- No notifications (email/Teams)
- No audit trail
etc.
````

---

## Phase 5: Write Master README

Create `README.md` at the root of the reports directory.

```markdown
# Assets Documentation

> Generated {YYYY-MM-DD} by analyzing {N} workflows, {N} templates,
> {N} transformations, {N} JSON forms, {N} command templates,
> and {N} Operations Manager automations.

## How to Read These Reports

Each use case folder contains two documents:
- **`customer-spec.md`** - Inferred High-Level Design (HLD): business purpose,
  scope, user interaction model, integrations, acceptance criteria
- **`solution-design.md`** - As-Built Low-Level Design (LLD): component inventory,
  workflow hierarchy, adapter mappings, task flows, data model, error handling

## Use Case Index

### Core Network Automation Use Cases

| # | Use Case | Folder | Workflows | Description |
|---|----------|--------|-----------|-------------|
| 1 | [{Name}]({slug}/) | `{slug}` | ~{N} | {1-line description} |

### Specialized Use Cases

| # | Use Case | Folder | Workflows | Description |
|---|----------|--------|-----------|-------------|
| ... |

### Shared Libraries & Infrastructure

| # | Use Case | Folder | Assets | Description |
|---|----------|--------|--------|-------------|
| ... |

### Reference

| # | Use Case | Folder | Assets | Description |
|---|----------|--------|--------|-------------|
| ... | [Standalone/Test Workflows]({slug}/) | `{slug}` | ~{N} | {catalog description} |

## Cross-Use-Case Relationships

```
{ASCII diagram showing how use cases connect.
OM triggers at top, core use cases in middle, shared utilities at bottom.}

                    Operations Manager Triggers
                              |
                              v
                    {Central Orchestrator Use Case}
                              |
          +--------+--------+---------+--------+
          |        |        |         |        |
      {UC1}    {UC2}    {UC3}     {UC4}    {UC5}
          |        |        |         |        |
          +--------+--------+---------+--------+
                              |
                    Shared Utilities
                              |
              +---------+-----+------+---------+
              |         |            |         |
          {Backend1}  {Backend2}  {Backend3}  {Backend4}
```

## Excluded from Documentation

{List any assets excluded and why.}
```

---

## Phase 6: Present to Engineer

Show a summary:

1. **Asset inventory** — total files analyzed per type
2. **Use case groups** — count and names
3. **Reports produced** — list of directories with customer-spec.md + solution-design.md
4. **Excluded assets** — what was skipped
5. **Gaps** — "I don't see rollback logic or notifications."

Ask the engineer to review the reports. Next steps:
- **Accept** — use the reports as-is
- **Refine** — hand specific use case specs to `/spec-agent`
- **Redesign** — hand to `/solution-arch-agent`

---

## What to Watch For

- **Orphaned workflows:** No childJob parent AND no OM trigger. May be standalone utilities, abandoned, or externally invoked. Check adapter usage to infer purpose.
- **`@projectId:` prefixed names:** Strip prefix (everything through colon+space) before matching.
- **Empty componentName:** Fall back to trigger names, `actionId`, or automation name.
- **Duplicate/backup workflows:** Names with "Backup", date suffixes, version numbers → note as backups, don't give own group.
- **Cross-use-case shared workflows:** Document fully in primary group, add cross-references in others.
- **Transformation `.jst.json` naming:** Match on internal `name` field, not filename.
- **Template `data` field:** Often a JSON string, not parsed object.
- **Large TextFSM libraries:** Group under Shared Utilities, not individual use cases.
- **Command template rules:** Each rule encodes a compliance check — valuable for HLD requirements.
- **Workflow descriptions and task summaries are the best source of business intent.**
**Non-hex task IDs:** If you encounter task IDs like `apush` or `myTask`, note them — these are a known bug pattern ($var references silently fail on these).
**Static values as indicators:** Hard-coded strings in merge tasks or newVariable tasks often reveal business rules (e.g., `"value": "production"` → production-only path).
**Missing error transitions:** Note any adapter tasks without error transitions — this is a quality gap in the existing implementation.


---

## Gotchas

- **NEVER use this on project files.** Redirect to `/project-to-spec`.
- **NEVER produce JSON files as output.** Only markdown reports.
- **childJob `workflow` is the primary relationship link.** Don't trace `$var` references across workflows.
- **Naming prefix is a heuristic, not a rule.** Prioritize childJob graph over naming when they conflict.
- **OM automations can have multiple triggers.** Document all of them.
- **Not every asset connects.** Don't force them into groups — catalog in Shared Utilities or Reference.
- Task descriptions and summaries are the best source of intent — use them heavily
