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

**Draw.io Architecture Diagram**

Generate one file in the same directory as `solution-design.md`:
- `solution-design.drawio` — editable mxGraph XML diagram

**What to show:**
- Entry points (operators, OM triggers, LCM actions) at the top
- The orchestrator workflow below entry points
- Each child workflow in execution order, top to bottom
- External systems (adapters/integrations) called by each workflow, to the RIGHT of the calling workflow on the same horizontal band
- Arrow labels describing the operation (e.g., "childJob", "Create ticket", "Get device")

**What to exclude:**
- Workflows or connections marked as "not wired", inactive, or not yet implemented
- Alternative / optional execution paths — describe those in prose in Section E instead
- Return arrows from child workflows back to the parent

**Grouping rule — eliminates horizontal sprawl:**
When 3 or more parallel child workflows follow the same pattern (e.g., multiple tool-removal workflows), represent them as ONE box with bullet lines listing the members. Use `&#xa;` for line breaks in the `value=` attribute. Label the arrow `childJob (×N)`. List the external systems those child workflows collectively reach once each, to the right of the group box.

**Layout rules — follow exactly:**
1. Workflow chain runs in a single vertical column on the LEFT (x=40 to x=380)
2. External systems sit in a column on the RIGHT (x=470 to x=680), at the same y-band as the workflow that calls them
3. Workflow → next workflow: vertical arrow going straight down
4. Workflow → external system: horizontal arrow going straight right
5. No diagonal arrows. No long arrows crossing the canvas.
6. Canvas width: ≤ 700px. Canvas height: grow as needed (100px per row).

**Shape guide:**
- Entry points: `style="ellipse;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=12;"` — Size: 180×50
- Workflows (orchestrator, child, grouped): `style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=12;"` — Size: 280×55 (taller for grouped bullet lists)
- forEach / loop: `style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;fontSize=12;"` — Size: 280×55
- External systems: `style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fff3cd;strokeColor=#d0893c;fontStyle=1;fontSize=11;"` — Size: 180×45
- JSON Forms (user input): `style="rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;"` — Size: 160×60
- All arrows: `style="edgeStyle=orthogonalEdgeStyle;html=1;fontSize=10;"`

**`solution-design.drawio` scaffold** — generic pattern to follow; replace all `{...}` placeholders with real names from the use case:

\`\`\`xml
<mxfile>
  <diagram name="{Use Case Name} - Solution Design">
    <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="700" pageHeight="900" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>

        <!-- Entry points (y=30) — one ellipse per entry point, spaced at x=40, x=240, x=440... -->
        <mxCell id="ep1" value="{Entry Point, e.g. Operator}" style="ellipse;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=12;" vertex="1" parent="1">
          <mxGeometry x="40" y="30" width="180" height="50" as="geometry"/>
        </mxCell>
        <!-- Repeat for each additional entry point -->

        <!-- Orchestrator workflow (y=130) -->
        <mxCell id="mw" value="{Orchestrator Workflow Name}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=12;" vertex="1" parent="1">
          <mxGeometry x="40" y="130" width="280" height="55" as="geometry"/>
        </mxCell>
        <mxCell id="e_ep1_mw" value="{trigger, e.g. launch}" style="edgeStyle=orthogonalEdgeStyle;html=1;fontSize=10;" edge="1" source="ep1" target="mw" parent="1">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>

        <!-- Child workflow (y=240) — with external systems to the right -->
        <mxCell id="cw1" value="{Child Workflow Name}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=12;" vertex="1" parent="1">
          <mxGeometry x="40" y="240" width="280" height="55" as="geometry"/>
        </mxCell>
        <mxCell id="e_mw_cw1" value="childJob" style="edgeStyle=orthogonalEdgeStyle;html=1;fontSize=10;" edge="1" source="mw" target="cw1" parent="1">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>
        <!-- External system at the same y-band, to the right -->
        <mxCell id="ext1" value="{External System Name}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fff3cd;strokeColor=#d0893c;fontStyle=1;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="380" y="248" width="180" height="45" as="geometry"/>
        </mxCell>
        <mxCell id="e_cw1_ext1" value="{operation}" style="edgeStyle=orthogonalEdgeStyle;html=1;fontSize=10;" edge="1" source="cw1" target="ext1" parent="1">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>
        <!-- Add more external systems at y+55 each for additional systems called by the same workflow -->

        <!-- Grouped child workflows — use when 3+ parallel children follow the same pattern (y=350) -->
        <mxCell id="grp1" value="{Group Label, e.g. Tool Removal Workflows (×N)}&#xa;• {Child Workflow 1}&#xa;• {Child Workflow 2}&#xa;• {Child Workflow 3}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=11;align=left;spacingLeft=10;" vertex="1" parent="1">
          <mxGeometry x="40" y="350" width="280" height="90" as="geometry"/>
        </mxCell>
        <mxCell id="e_cw1_grp1" value="childJob (×N)" style="edgeStyle=orthogonalEdgeStyle;html=1;fontSize=10;" edge="1" source="cw1" target="grp1" parent="1">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>
        <!-- External systems the group collectively reaches — one box per distinct system, stacked at y=350, y=405, y=460... -->
        <mxCell id="ext2" value="{External System A}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fff3cd;strokeColor=#d0893c;fontStyle=1;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="380" y="350" width="180" height="45" as="geometry"/>
        </mxCell>
        <mxCell id="e_grp1_ext2" value="{operation}" style="edgeStyle=orthogonalEdgeStyle;html=1;fontSize=10;" edge="1" source="grp1" target="ext2" parent="1">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>
        <!-- Continue for each additional external system at y+55 -->

        <!-- Continue adding child workflows/loops below (y += 100+ per row) -->

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
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
