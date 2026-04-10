# Documentation Output Templates

Templates for the three markdown files produced by the `/documentation` skill.

---

## customer-spec.md Template

```markdown
# {Use Case Name} - High-Level Design (HLD)

**Use Case:** {One-Line Description}
**Version:** {Version or build identifier, if discoverable from naming or descriptions}

> **Note:** This spec was produced by reading {numberOfAssets} {typeOfAssets}.
> Review and correct any inferences before using as a delivery baseline.

---

## 1. Problem Statement
{Write 1-2 RICH PARAGRAPHS of narrative prose. This is NOT a bullet list.

Paragraph 1: Describe the overall purpose and business context — what this automation does,
why it exists, what business problem it solves.

Paragraph 2: Describe the major functional areas or modes of operation — what systems are
integrated, what types of automation are covered, how they connect. Also describe the operator
experience — how users interact with the system, what entry points exist, what the operational
model looks like.

Infer from workflow descriptions, adapter usage, task summaries, OM trigger configurations,
LCM action names, golden config structure, and naming patterns.}

## 2. High-Level Flow

{Write 1-3 sentences describing the end-to-end execution from trigger to completion, using
business language. Cover: the entry point (who or what starts this), the major phases in
order, which external systems are touched and why, and what the final outcome is.
Do not use workflow names or technical task names — describe what happens, not what it's called.}

## 3. Phases
{One section per major workflow / childJob cluster / LCM action / golden config check stage}

## 4. Key Design Decisions
{Inferred from adapter choices, error handling patterns, approval gates, LCM action structure}

## 5. Scope
**In scope (as built):** {list components that exist}
**Not observed:** {common patterns not present — rollback, notifications, audit trail, etc.}

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
| {Entry point name} | {Manual launch / Scheduled / Endpoint trigger / LCM action / etc.} | {How this entry point works and what it initiates} |

### 9.2 Operator Workflow (Manual Path)

1. **{Action name}** — {Detailed description of what happens at this step, what the operator sees, what choices are available.}
2. **{Action name}** — {description}

### 9.3 Automated Path

1. {Step description — what triggers, what runs, what the system checks}
2. {Step description}

## 10. Integration Points

| System | Direction | Purpose |
|---|---|---|
| **{System name}** | {Bi-directional / Inbound / Outbound} | {What data flows and why, including specific operations} |

## 11. Acceptance Criteria
{Inferred from outputSchema and evaluation checks}
```

**For test/standalone use cases**, use a simplified catalog format — asset table with Purpose and Adapters columns only. No full HLD needed.

---

## solution-design.md Template

```markdown
# {Use Case Name} - Solution Design (LLD)

**Use Case:** {One-Line Description}
**Version:** {Version if discoverable}

> **As-Built** — produced by reading {numberOfAssets} {typeOfAssets}.
> Review and correct any inferences before using as a delivery baseline.

---

## A. Environment Summary
{Platform, adapters found, apps used}

## B. Component Inventory
| # | Component | Type | Name | Purpose | ID |
|---|-----------|------|------|---------|-----|
| 1 | {name} | {workflow/template/mop/golden-config/lcm} | {actual name} | {A sentence to describe what this item does, what systems it touches, and its role in the overall flow.} | {id} |

## C. Adapter Mappings
| Adapter | app name | adapter_id | Tasks Used |
|---------|----------|-----------|------------|
| ServiceNow | Servicenow | ServiceNow | createChangeRequest, updateChangeRequest |

## D. Execution Flow

{Trace the full use case execution across ALL assets in this group. This is not a single-workflow diagram — it spans entry points, orchestrators, child workflows, forms, templates, adapters, and external systems. Actors are real participants: human operators, OM triggers, LCM actions, each distinct workflow, and each external system (one actor per system, not per adapter call). Use `->>` for calls and `-->>` for responses. Add `alt error path` blocks only where the transition graph shows a meaningful branch to an error handler — not on every adapter call. Cap actors at 8; collapse minor utility workflows into one if needed.

For single standalone assets: `actor User ->> Asset ->> External System -->> Asset -->> User`.}

\`\`\`mermaid
sequenceDiagram
  actor {Entry Point — e.g. Operator, Scheduled Trigger, LCM Action}
  {Entry Point}->>{Orchestrator Workflow}: {trigger or launch description}
  {Orchestrator Workflow}->>{External System}: {operation, e.g. Create ticket}
  {External System}-->>{Orchestrator Workflow}: {result, e.g. ticket_id}
  {Orchestrator Workflow}->>{Child Workflow}: childJob
  {Child Workflow}->>{External System}: {operation, e.g. Push config}
  alt error path
    {External System}-->>{Child Workflow}: failure
    {Child Workflow}-->>{Orchestrator Workflow}: error status
  end
  {Orchestrator Workflow}->>{Entry Point}: complete
\`\`\`

## E. Workflow Structure

For each workflow, write a subsection using the following structure. Only include a task-type sub-table if that type actually exists in the workflow — suppress empty tables entirely.

### {Workflow Name}

**Description:** {One sentence describing the workflow's role.}

**Adapters and Integrations**

| Name | Operation |
|------|-----------|
| {Adapter instance name} | {Operation(s) called} |

_(Omit this table if the workflow uses no adapters.)_

**Inputs**

| Input | Type | Description |
|-------|------|-------------|
| {varName} | {string/object/array/number/boolean} | {What this input represents} |

**Outputs**

| Output | Type | Description |
|--------|------|-------------|
| {varName} | {string/object/array/number/boolean} | {What this output represents} |

**Child Jobs**

| Workflow Name | Task Summary | Task Description |
|---------------|--------------|-----------------|
| {child workflow name} | {task summary} | {what this task does} |

_(Omit if no child job tasks.)_

**Transformations**

| Transformation Name | Task Summary | Task Description |
|--------------------|--------------|-----------------|
| {transformation name} | {task summary} | {what this task does} |

_(Omit if no transformation tasks.)_

**Template Tasks**

| Template Name | Template Type | Task Summary | Task Description |
|---------------|--------------|--------------|-----------------|
| {template name} | {jinja2/textfsm} | {task summary} | {what this task does} |

_(Omit if no template tasks.)_

**Command Template Tasks**

| Template Name | Task Summary | Task Description |
|---------------|--------------|-----------------|
| {command template name} | {task summary} | {what this task does} |

_(Omit if no command template tasks.)_

**Analytic Template Tasks**

| Template Name | Task Summary | Task Description |
|---------------|--------------|-----------------|
| {analytic template name} | {task summary} | {what this task does} |

_(Omit if no analytic template tasks.)_

**JSON Form Tasks**

| Form Name | Task Summary | Task Description |
|-----------|--------------|-----------------|
| {form name} | {task summary} | {what this task does} |

_(Omit if no JSON form tasks.)_

## F. Command Templates

For each command template referenced in this use case, document its commands and validation rules. Omit this section entirely if no command templates exist.

### {Command Template Name}

| Command | Rules |
|---------|-------|
| `{cli command}` | {Rule: `{pattern}` — Eval: `{contains/regex/etc}`, Flags: `{flags if any}`, Severity: `{error/warn/info}`} |

_(Multiple rules for one command go in the same cell as a list. Multiple commands each get their own row.)_

## H. Known Gaps
Patterns not present that are typically expected:
- No rollback logic observed
- No notifications (email/Teams)
- No audit trail
```

---

## README.md Template

```markdown
# Assets Documentation

> Generated {YYYY-MM-DD} by analyzing {N} workflows, {N} templates,
> {N} transformations, {N} JSON forms, {N} command templates,
> {N} OM automations, {N} golden config assets, and {N} LCM resource models.

## How to Read These Reports

Each use case folder contains two documents:
- **`customer-spec.md`** — Inferred High-Level Design (HLD): business purpose,
  scope, user interaction model, integrations, acceptance criteria
- **`solution-design.md`** — As-Built Low-Level Design (LLD): component inventory,
  workflow hierarchy, adapter mappings, task flows, data model, error handling

## Use Case Index

### Core Network Automation Use Cases

| # | Use Case | Folder | Assets | Description |
|---|----------|--------|--------|-------------|
| 1 | [{Name}]({slug}/) | `{slug}` | ~{N} | {1-line description} |

### Specialized Use Cases

| # | Use Case | Folder | Assets | Description |
|---|----------|--------|--------|-------------|

### Shared Libraries & Infrastructure

| # | Use Case | Folder | Assets | Description |
|---|----------|--------|--------|-------------|

### Reference

| # | Use Case | Folder | Assets | Description |
|---|----------|--------|--------|-------------|
| | [Standalone/Test Workflows]({slug}/) | `{slug}` | ~{N} | {catalog description} |

## Cross-Use-Case Relationships

\`\`\`
{ASCII diagram showing how use cases connect.
OM triggers and LCM entry points at top, core use cases in middle,
shared utilities at bottom.}

                    Operations Manager / LCM Triggers
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
\`\`\`

## Excluded from Documentation

{List any assets excluded and why.}
```
