---
name: global-to-spec
description: Document individual Itential platform assets (workflows, forms, transformations, templates, command templates, operations manager automations) that are NOT part of a project. Discovers relationships between standalone assets, groups them into use cases, and produces customer-spec.md + solution-design.md per use case plus a master README. Use when documenting global/standalone assets without existing documentation. NEVER use on project files — use /project-to-spec for those.
argument-hint: "[directory-path or 'platform']"
---

# Global Assets to Spec

**Purpose:** Read individual/global Itential assets → discover relationships → group into use cases → produce documentation
**Feeds into:** Can be handed to `/spec-agent` for refinement or `/solution-arch-agent` for redesign

## ABSOLUTE RULES

1. **NEVER use the Agent tool.** Do ALL work directly in the main conversation using Read, Glob, Grep, and Write tools. No sub-agents — they get stuck on large file sets. This is how `/project-to-spec` works and it never stalls.
2. **Use parallel tool calls for speed.** Instead of agents, issue multiple Read tool calls in a single message (up to 20 at a time). This gives you parallelism without the risk of stuck agents.
3. **Parse in priority order.** Phases 1-2 only need workflows and OM automations for grouping. Do NOT parse templates, transformations, or command templates until Phase 4 when writing the LLD for a specific group — and only parse the ones referenced by that group's workflows.
4. **Write reports as you go.** After the engineer approves groupings (Phase 3), write each use case's customer-spec.md and solution-design.md immediately before moving to the next use case. Do not accumulate all analysis and then write all reports at the end.

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
Individual Assets (workflows, forms, templates, transformations, command templates, OM automations)
      |
      ├── Phase 1: Collect + classify assets (in-memory only)
      ├── Phase 2: Discover relationships + group into use cases (in-memory only)
      ├── Phase 3: Present proposed groupings to engineer for approval
      ├── Phase 4: Write per-use-case reports (customer-spec.md + solution-design.md)
      ├── Phase 5: Write master README.md
      └── Phase 6: Present summary to engineer for review
```

---

## Efficiency Rules

**This skill must operate efficiently.** Follow these rules strictly:

1. **NEVER use the Agent tool.** Use direct Read/Write/Glob/Grep tool calls only — the same way `/project-to-spec` works. Agents get stuck on large file sets.
2. **Parallelize with multiple tool calls, not agents.** Issue up to 20 Read calls in a single message to read files in parallel. This is fast and never stalls.
3. **Read filenames first, parse selectively.** For large directories (100+ files), list the directory first. Parse workflow and OM automation files for relationship discovery. Do NOT parse templates, transformations, or command templates until Phase 4 when writing the LLD for a specific group — and only parse the ones referenced by that group's workflows.
4. **Keep analysis in-memory.** Do NOT write intermediate JSON files. Hold the asset index and relationship graph in your working memory.
5. **Write reports one use case at a time.** Once the engineer approves groupings, pick the first use case, parse its specific assets, write its customer-spec.md and solution-design.md, then move to the next.
6. **Skip deep parsing for test/standalone assets.** For the test/standalone category, a brief catalog table is sufficient — do not produce full HLD/LLD.
7. **For workflow analysis, focus on:** task names, app fields, childJob references, adapter usage, inputSchema, description. Skip deep variable tracing.
8. **Priority order for parsing:** (a) directory listings, (b) workflow JSON for grouping, (c) OM automation JSON for grouping, (d) per-group: templates, transformations, command templates, forms only when writing that group's LLD.

---

## Phase 1: Collect and Classify Assets

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

## Phase 2: Discover Relationships and Group

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

---

## Phase 3: Present Groupings to Engineer

**Stop and present the proposed groupings before writing any reports.** Ask:

1. "Here are the use case groups I identified — does this look right?"
2. "These assets are ungrouped — should any be added to an existing group?"
3. "These appear to be test/dev workflows — should I catalog or skip them?"

Show each group with: name, category (Core/Specialized/Shared/Reference), approximate workflow count, and 1-line description.

**Wait for engineer approval before proceeding to Phase 4.**

---

## Phase 4: Write Per-Use-Case Reports

For each approved use case group, create a directory with two markdown files.

### customer-spec.md Format

Write professional, narrative documentation — not mechanical spec sheets. The HLD should read like a business-facing document with rich prose, detailed tables, and domain-specific context.

````markdown
# {Use Case Name} - High-Level Design (HLD)

**Customer:** {Customer Name}
**Use Case:** {One-Line Description}
**Version:** {Version or build identifier, if discoverable from naming or descriptions}
**Status:** As-Built (inferred from deployed assets)

---

## 1. Executive Summary

{Write 2-3 RICH PARAGRAPHS of narrative prose. This is NOT a bullet list.

Paragraph 1: Describe the overall purpose and business context — what this automation
does, why it exists, what business problem it solves.

Paragraph 2: Describe the major functional areas or modes of operation — what systems
are integrated, what types of automation are covered, how they connect.

Paragraph 3: Describe the operator experience — how users interact with the system,
what entry points exist, what the operational model looks like.

Infer from workflow descriptions, adapter usage, task summaries, OM trigger
configurations, and naming patterns.}

## 2. Business Objectives

1. **{Objective title}** -- {Detailed explanation of the business goal. Use double-dash
   to separate the bold title from the explanation. Each item should be 1-2 sentences.}
2. **{Objective title}** -- {explanation}
3. ...

## 3. Scope

### 3.1 In Scope

| Capability | Description |
|---|---|
| {Capability name} | {Multi-sentence description of what this capability does, how it works, and what systems it touches. Each row should be detailed, not a single phrase.} |
| {Capability name} | {Multi-sentence description} |

### 3.2 Out of Scope

- {Common patterns NOT observed — e.g., rollback, notifications, audit trail}
- {Explicitly excluded capabilities based on adapter and task analysis}

## 4. User Interaction Model

### 4.1 Entry Points

| Entry Point | Trigger | Description |
|---|---|---|
| {Entry point name} | {Manual launch / Scheduled / Endpoint trigger / etc.} | {How this entry point works and what it initiates} |

### 4.2 Operator Workflow (Manual Path)

1. **{Action name}** -- {Detailed description of what happens at this step, what the
   operator sees, what choices are available.}
2. **{Action name}** -- {description}
3. ...

### 4.3 Automated Path

1. {Step description — what triggers, what runs, what the system checks}
2. {Step description}
3. ...

## 5. Integration Points

| System | Direction | Purpose |
|---|---|---|
| **{System name}** | {Bi-directional / Inbound / Outbound} | {What data flows and why, including specific operations} |

## 6-N. {Domain-Specific Sections}

{Include sections specific to the use case domain. Examples:
- For Change Management: "ServiceNow Change Types" table, "State Machine" diagram
- For Compliance: "Compliance Categories" table, "Remediation Patterns"
- For Config Management: "Configuration Platforms" table, "Template Library"
- For Device Build: "Device Types and Build Stages"

These sections go between Integration Points and Acceptance Criteria. Number them
sequentially. Use tables, ASCII diagrams, and numbered lists as appropriate.}

## N-1. Acceptance Criteria

1. {Criterion — specific, measurable, derived from workflow behavior}
2. {Criterion}
3. ...

## N. Identified Gaps and Risks

| ID | Category | Description | Severity |
|---|---|---|---|
| G-1 | {Gap/Risk/Observation} | {Detailed description of what is missing or risky} | Low/Medium/High |
````

**For OM automation / catalog use cases**, adapt Sections 4-6 to focus on trigger inventory and scheduling patterns rather than operator workflows.

**For test/standalone use cases**, use a simplified catalog format — workflow table with Purpose and Adapters columns only. No full HLD needed.

### solution-design.md Format

Write detailed, factual technical documentation. Each component should have multi-sentence descriptions. The LLD should be comprehensive enough that an engineer could understand the full system without reading the source JSON.

````markdown
# {Use Case Name} - Solution Design (LLD)

**Customer:** {Customer Name}
**Use Case:** {One-Line Description}
**Version:** {Version if discoverable}
**Document Type:** As-Built Low-Level Design

---

## 1. Solution Architecture Overview

{Narrative paragraph describing the architecture pattern — hierarchical orchestrator,
master-dispatcher, hub-and-spoke, etc. Describe the layers: operator console,
orchestration, utility. Mention total counts of workflows, transformations, templates,
and OM automations in this use case.}

### 1.1 Workflow Hierarchy

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

## 2. Component Inventory

### 2.1 Workflows ({N} total)

| Workflow | Tasks | Type | Purpose |
|---|---|---|---|
| {workflow name} | {task count} | {Entry Point / Master Orchestrator / Dispatcher / Child / Utility / Interactive / Backup} | {Multi-sentence purpose description. Describe what this workflow does, what systems it touches, and its role in the overall flow.} |

### 2.2 Transformations ({N} total)

| Transformation | Purpose | Key I/O |
|---|---|---|
| {name} | {what it does} | In: {key input fields}. Out: {key output fields} |

### 2.3 Templates ({N} total, if applicable)

| Template | Type | Purpose |
|---|---|---|
| {name} | {jinja2/textfsm/command} | {inferred from content and usage context} |

### 2.4 Command Templates (if applicable)

| Template | OS | Commands | Purpose |
|---|---|---|---|
| {name} | {os} | {count} | {compliance/validation purpose} |

### 2.5 JSON Forms (if applicable)

| Form | Fields | Purpose |
|---|---|---|
| {name} | {count} | {inferred from field names and workflow context} |

### 2.6 Operations Manager Automations (if applicable)

| Automation | Trigger Type | Schedule | Target Workflow |
|---|---|---|---|
| {name} | {schedule/endpoint/manual} | {frequency or "on-demand"} | {componentName} |

## 3. Detailed Flow Descriptions

{For each major workflow (entry points, orchestrators, dispatchers), describe the
flow using numbered narrative steps. Focus on what happens, not task IDs.}

### 3.1 {Workflow Name}

**Entry:** {How this workflow is triggered}

**Flow:**
1. {Step description — what happens, what adapter is called, what data is processed}
2. {Step description}
3. **Dispatch/Branch:** {Describe evaluation branches and routing logic}
4. ...

### 3.2 {Next Major Workflow}
...

## 4. Adapter Mappings

| Adapter Type | Instance ID | Purpose | Key Methods Used |
|---|---|---|---|
| {app name} | {adapter_id} | {what it does} | {list of methods} |

## 5. Data Model

### 5.1 {Key Data Structure}

```json
{
  "field": "<description>"
}
```

## 6. Error Handling Patterns

| Pattern | Implementation | Workflows |
|---|---|---|
| {error pattern} | {how it's handled} | {which workflows use it} |

## 7. External Workflow Dependencies

{List workflows from OTHER use case groups that this group calls or is called by.}

| Workflow | Direction | Purpose |
|---|---|---|
| {external workflow} | {Calls / Called by} | {why} |

## 8. Operational Notes (if OM automations present)

- {Enabled/disabled status, schedule frequencies, webhook configs}
- {Environment-specific configuration notes}

## 9. Identified Technical Observations

1. **{Observation title}**: {Detailed description — dual adapter versions, large workflow
   complexity, migration patterns, naming inconsistencies, etc.}
2. ...
````

---

## Phase 5: Write Master README

Create `README.md` at the root of the reports directory.

```markdown
# {Customer/Platform Name} - Asset Documentation

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

---

## Gotchas

- **NEVER use this on project files.** Redirect to `/project-to-spec`.
- **NEVER produce JSON files as output.** Only markdown reports.
- **Process in batches for large sets.** Read filenames first, then parse selectively.
- **childJob `workflow` is the primary relationship link.** Don't trace `$var` references across workflows.
- **Naming prefix is a heuristic, not a rule.** Prioritize childJob graph over naming when they conflict.
- **OM automations can have multiple triggers.** Document all of them.
- **Not every asset connects.** Don't force them into groups — catalog in Shared Utilities or Reference.
