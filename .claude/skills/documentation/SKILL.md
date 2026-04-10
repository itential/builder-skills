---
name: documentation
description: Use this skill to survey and catalog an Itential platform — when someone wants to know what's on their platform, document global assets (workflows, templates, LCM models, golden config, OM automations) that are NOT inside a named project, group them into logical use cases, and produce a master catalog or README. Trigger it for phrases like "document everything on the platform", "what use cases do we have?", "catalog all our global workflows", "I inherited this platform and have no idea what's there", "group our automations by use case", or "produce a platform README". The output is a structured catalog: customer-spec.md + solution-design.md per use case + master README. NOT for documenting a specific named project — use /project-to-spec for that. NOT for building new automation.
---

# Documentation

**Purpose:** Read Itential assets → discover relationships → group into use cases → produce documentation
**Output:** `customer-spec.md` (inferred HLD per use case) + `solution-design.md` (as-built LLD per use case) + `README.md` (master index, only when multiple use cases)
**Feeds into:** Can be handed to `/spec-agent` for refinement or `/solution-arch-agent` for redesign

## CRITICAL: Output Requirements

**The ONLY deliverables are markdown files.** Do NOT produce JSON index files, JSON catalogs, or any intermediate artifacts. All analysis happens in-memory.

```
{reports-directory}/
  README.md                          ← master index of all use cases ONLY when more than one use case
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

Surveys **global** Itential assets — workflows, JSON forms, transformations, templates, command templates, analytic templates, Operations Manager automations, golden configuration trees and compliance plans, and LCM resource models that live outside named projects. Accepts `all`, `platform`, a directory path, or a list of specific global asset names. Discovers how they relate to each other, groups them into logical use cases, and produces documentation for each group plus a master index when there are multiple use cases.

> **For a named project:** Use `/project-to-spec` instead — it reads a single project's components and produces customer-spec.md + solution-design.md tailored to that project.

---

## Flow

```
User invokes /documentation ['all' | 'platform' | directory | specific global asset names]
      |
      ├── Step 0: Determine Scope
      |     ├── Project named? → redirect to /project-to-spec
      |     ├── Specific global assets named? → resolve + discover relationships → ask grouping preference
      |     └── 'all' / platform / directory? → full collection + grouping flow
      |
      ├── Step 1: Collect + classify global assets (in-memory)
      ├── Step 2: Discover relationships + group into use cases (in-memory)
      ├── Step 3: Present proposed groupings to engineer for approval
      ├── Step 4: Write per-use-case reports (customer-spec.md + solution-design.md)
      ├── Step 5: Write master README.md (ONLY when more than one use case)
      └── Step 6: Present summary to engineer for review
```

---

## Step 0: Determine Scope

Before collecting assets, determine what the user wants to document.

### Pattern 1 — Project named

If the user names a specific project, **redirect them to `/project-to-spec`** — that skill is purpose-built for single-project documentation and produces a more thorough analysis.

> "It looks like you want to document a specific project — use `/project-to-spec` for that. It reads the project's components directly and produces a more thorough customer-spec.md and solution-design.md for it."

### Pattern 2 — Specific global asset(s) named

If the user provides one or more asset names or IDs:

1. Resolve each asset via the platform API or local files
2. Traverse the relationship graph starting from each named asset (childJob links, OM→workflow, LCM→workflow, golden config→command template, etc.)
3. Present the discovered asset cluster to the engineer:
   - List all assets found (named + discovered via relationships)
   - Show how they connect

4. Ask the engineer:
   > "I found these assets and their relationships. How should I document them?"
   > - **(Default) Group into use cases** — analyze and cluster into logical groups, then produce HLD+LLD per group
   > - **Document as a single unit** — treat the entire cluster as one use case, produce one HLD+LLD
   > - **Document each asset independently** — produce separate minimal documentation per asset without cross-linking

Proceed based on the engineer's answer.

### Pattern 3 — All globals / platform / directory

If the user says `all`, `platform`, or provides a directory path, run the full collection and grouping flow (Steps 1–6) without asking about grouping preference.

---

## Step 1: Collect and Classify Assets

Ask the engineer for the asset source if not specified. Two modes:

### Mode A — Local Directory

Scan for asset JSON files organized by type:

```
directory/
  workflows/                          *.json
  json_forms/                         *.json
  transformations/                    *.json or *.jst.json
  templates/                          *.json
  command_templates/                  *.json
  operations_manager_automations/     *.json
  golden_config/                      *.json
  lcm/                                *.json
```

If the directory is flat (all JSON at root), classify by JSON structure signatures below.

If a `projects/` subfolder exists, scan it too. Project manifest files (containing `name` + `components[]`) identify which assets belong to a project — use that grouping when building the relationship graph. Strip `@projectId:` prefixes from any workflow names found inside.

### Mode B — Platform API

Authenticate using `.auth.json` (see AGENTS.md auth reuse pattern). Fetch global assets (ensure you fetch pagination if there are a lot of assets):

```
GET /automation-studio/workflows?exclude-project-members=true&limit=500
GET /automation-studio/templates?limit=500
GET /automation-studio/json-forms?limit=500
GET /operations-manager/automations
GET /mop/templates
GET /golden-config/trees
GET /golden-config/plans
GET /lifecycle-manager/model
GET /automation-studio/projects?limit=500
```

### Classification Signatures

| Asset Type | Identifying Fields |
|---|---|
| **Workflow** | `tasks` (object), `transitions` |
| **JSON Form** | `schema`, `struct`, `uiSchema` |
| **Transformation** | `incoming`, `outgoing`, `steps` |
| **Template** | `type` (textfsm/jinja2), `template` field |
| **Command Template** | `commands[]` with `rules[]` |
| **Analytic Template** | `commands[]` with `analytics[]` or `baseline` fields |
| **OM Automation** | `triggers[]`, `componentName` |
| **Golden Config Tree** | `nodes[]`, `rootNode`, `treeType` |
| **Golden Config Compliance Plan** | `planType`, `configSpec`, `devices[]` |
| **LCM Resource Model** | `resourceType`, `actions[]`, `schema` |

**Build the asset index in-memory only.** For each asset, note: name, file path/ID, type, and key metadata.

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

7. **LCM Resource Model → Workflow:** Each LCM action has an `actionWorkflow` field naming an IAP workflow → link.

8. **Golden Config Compliance Plan → Command Template:** Plans reference MOP command templates for configuration checks → link.

9. **Workflow → Golden Config:** Workflows calling golden-config API tasks via adapter → link.

10. **Adapter patterns:** Collect tasks where `location === "Adapter"` — extract `app` (type name) and operation name.

11. **Naming prefix clustering:** Split on ` - ` (space-dash-space). Assets sharing a prefix are candidates for the same use case.

### Grouping Rules (apply in order)

1. **OM Automations as Entry Points:** Each OM automation's `componentName` → root workflow → traverse childJob graph → collect all reachable workflows + referenced forms/templates/transformations/command templates = one cluster.

2. **LCM Resource Models as Entry Points:** Each LCM model → action workflows → traverse childJob graph → collect all reachable assets = one cluster. If a workflow cluster already contains these workflows, merge the LCM model into that cluster.

3. **Golden Config Clusters:** Golden config trees + their compliance plans + referenced command templates → one cluster. If workflows reference these golden config assets, merge into the same cluster.

4. **Expand by Naming Prefix:** Add ungrouped assets sharing the same naming prefix as assets already in a cluster.

5. **Ungrouped Workflow Trees:** Any root workflow (no parent) with children → new cluster.

6. **Shared Utilities:** Workflows appearing in 3+ clusters → "Shared Utilities" group. Also include: generic TextFSM templates, utility transformations (math, array ops), common utilities (MongoDB CRUD, credential retrieval, notifications).

7. **Test / Standalone:** Workflows with developer name prefixes, `[TEST]`/`test-`/`dummy` patterns, Jira ticket patterns, or <5 tasks with no children and no triggers → "Standalone / Test Workflows" (catalog only, no full HLD/LLD).

8. **Remaining Ungrouped:** Group by functional similarity or list as individual entries in master README.

### Analyze the Components

Work through the components to reconstruct intent and structure.

#### Identify the orchestrator

Find the parent workflow — usually the one that:
- Has no `childJob` references pointing to it from other workflows
- References other workflows via `childJob` tasks
- Has the most complex transition graph

For LCM clusters, the resource model itself is the anchor — its action workflows are the orchestrators.
For golden config clusters, the compliance plan anchors the cluster.

#### Map the data flow

For the orchestrator and each child:
1. What are the **inputs**? (inputSchema properties)
2. What adapters are called? (location: "Adapter" tasks)
3. What utility tasks are used? (merge, query, evaluation, childJob, makeData)
4. What are the **outputs**? (outputSchema properties, `$var.job.x` assignments)
5. What external systems are touched? (adapter names → infer ServiceNow, Route53, etc.)

#### Infer the phases

Each major section of the orchestrator maps to a phase:
- A `childJob` to a child workflow = one phase
- An `evaluation` branch = a decision point
- An adapter call cluster = an integration phase
- A `ViewData` = an approval gate
- Error handling branches = rollback/recovery phases
- An LCM action = a lifecycle phase
- A compliance plan check = a validation phase

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
2. "These assets are ungrouped — should any be added to an existing group?" — default no
3. "These appear to be test/dev workflows — should I catalog or skip them?" — default skip

Show each group with: name, category (Core/Specialized/Shared/Reference), approximate asset count, and 1-line description.

**Wait for engineer approval before proceeding to Step 4.**

---

## Step 4: Write Per-Use-Case Reports

For each approved use case group, create a directory (or write directly to reports root if only one use case) with two markdown files.

### Produce `customer-spec.md`

Write professional, narrative documentation — not mechanical spec sheets. The HLD should read like a business-facing document with rich prose, detailed tables, and domain-specific context.

→ See template in `helpers/documentation-output-templates.md` — **"customer-spec.md Template"**

**For test/standalone use cases**, use a simplified catalog format — asset table with Purpose and Adapters columns only. No full HLD needed.

### Produce `solution-design.md`

Write the as-built LLD — this is factual, not inferred. Each component should have at least a sentence description, so an engineer could understand the full system without reading the source JSON.

→ See template in `helpers/documentation-output-templates.md` — **"solution-design.md Template"**

#### Generating Section D: Execution Flow

The guidance and example are in the Section D placeholder in `helpers/documentation-output-templates.md`.

Do not add a sequence diagram to the HLD (`customer-spec.md`). Section 2 of the HLD is a narrative paragraph only.

---

## Step 5: Write Master README

**Only write this step when there are 2 or more use cases.**

Create `README.md` at the root of the reports directory.

→ See template in `helpers/documentation-output-templates.md` — **"README.md Template"**

---

## Step 6: Present to Engineer

Show a summary:

1. **Asset inventory** — total files analyzed per type
2. **Use case groups** — count and names
3. **Reports produced** — list of directories/files with customer-spec.md + solution-design.md
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
- **Template `data` field:** Often a JSON string, not parsed object — parse before analyzing.
- **Large TextFSM libraries:** Group under Shared Utilities, not individual use cases.
- **Command template rules:** Each rule encodes a compliance check — valuable for HLD requirements.
- **LCM `actionWorkflow` may be missing:** If a LCM action has no linked workflow, note the gap — the action is defined but not implemented.
- **Golden config trees without compliance plans:** Document the structure but note there is no automated compliance enforcement.
- **Workflow descriptions and task summaries are the best source of business intent** — use them heavily.
- **Non-hex task IDs:** Task IDs like `apush` or `myTask` are a known bug pattern (`$var` references silently fail on these).
- **Static values as indicators:** Hard-coded strings in merge tasks or newVariable tasks often reveal business rules (e.g., `"value": "production"` → production-only path).
- **Missing error transitions:** Note any adapter tasks without error transitions — this is a quality gap in the existing implementation.

---

## Gotchas

- **NEVER produce JSON files as output.** Only markdown reports.
- **childJob `workflow` is the primary relationship link.** Don't trace `$var` references across workflows.
- **Naming prefix is a heuristic, not a rule.** Prioritize childJob graph over naming when they conflict.
- **OM automations can have multiple triggers.** Document all of them.
- **Not every asset connects.** Don't force them into groups — catalog in Shared Utilities or Reference.
- **When unsure about golden config or LCM relationships**, ask the engineer rather than guessing.
- **Master README is only for multiple use cases.** Single use case → write files directly in reports directory, no subdirectory, no README.
- **Task descriptions and summaries are the best source of intent** — use them heavily.
