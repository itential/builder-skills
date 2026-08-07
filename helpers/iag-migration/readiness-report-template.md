<!--
Gateway4 → Gateway5 Readiness Report — FIXED TEMPLATE.
The iag4-to-iag5 skill fills this in. Keep section order and headings identical every run so
the same inputs always produce a byte-identical report (aside from the header metadata line).
Canonical section order (also the Table of Contents at the top): Summary, Workflows, JSON Forms,
Scripts/Playbooks & Roles, Inventory, Recommended Repository Structure, Manual Action Checklist.
The checklist is LAST. The TOC links to each section.
Placeholders are wrapped in {{ }}. Every section is ALWAYS rendered — if a section has no
findings, emit its "No Gateway4 references found." line instead of dropping the section.

DESIGN: the ANALYSIS sections (Workflows, JSON Forms, Inventory) are PURE FACTS — what is on the
platform, nothing inferred, nothing recommended. No per-task "what to do", no remediation codes, no
legend. The only forward-looking / suggested content lives in the two clearly-labelled sections at
the END — Recommended Repository Structure and Manual Action Checklist. Never move recommendation
text into the analysis tables.

WORDING RULE (hard): the rendered report must NOT contain "iag", "IAG4", or "IAG5". Use
"Itential Gateway4"/"Gateway4" and "Itential Gateway5"/"Gateway5". Keep literal API/app names
(GatewayManager.runService, AG Manager) and the ACTUAL adapter names verbatim so the reader can
identify them on the platform. (Scripts/variable names may still use IAG internally — never rendered.)

FIXED recommendation strings — used ONLY in the end checklist / repo section, NEVER the analysis.
They are the VERBATIM REC_* constants in analyze_iag4.py; keep both in sync (determinism contract):
  - self-management task:   move to the Inventory Manager application; drop this task
  - python-script task:     re-implement as a Gateway5 python-script service; call via GatewayManager.runService
  - ansible-playbook task:  register playbook as a Gateway5 ansible-playbook service; call via GatewayManager.runService
  - json form field:        rebind to the Gateway5/replacement endpoint — returns no data once Gateway4 is removed.
  - gateway4-origin device:  device sourced from a Gateway4 adapter; re-home it in Inventory Manager before removing Gateway4
  - python asset (argv):    convert positional args to argparse flags; place in a git repo
  - python asset (argparse):already uses named args; place in a git repo
  - shell asset:            wrap in a Python script (python-script service) or register as an executable service; place in a git repo
  - role asset:             wrap in a playbook or Python script; place in a git repo
  - playbook asset:         place in a git repo; no code change

Sort rules (analyze_iag4.py already applies them — render straight through): workflows by name (asc),
then project id, then workflow id; tasks within a workflow by task id (asc); checklist by
recommendation then name; forms by name; assets by filename; devices by name; unresolved_children as
given (sorted). No per-row timestamps.

Workflow location comes from the workflow's `namespace` field (authoritative project membership):
"Global" when not project-owned, else "«{project_name}» ({project_id})". A stale @id: name prefix
is NOT project membership — those are Global. Never emit "name unavailable". Location is rendered the
SAME way everywhere (index Scope/Connector column AND detail heading) — the project id is kept.
-->

# Itential Gateway4 → Itential Gateway5 Migration Readiness

| | |
|---|---|
| **Generated** | {{YYYY-MM-DD}} |
| **Working directory** | `{{working_dir}}` |
| **Mode** | {{mode}} |
| **Platform source** | {{iap_source}} |
| **Gateway4 assets** | {{gateway4_assets_source}} |
| **Gateway4 matched** | Adapter `{{adapter_type}}` (instances: {{adapter_instances}}) · App `AG Manager` |
| **Scope** | {{scope_description}} |

<!-- DATA-GAP callout — render ONLY if analysis.json.unresolved_children is non-empty. One short line
     pointing to the full list at the BOTTOM (do NOT dump the whole list here — that was the old,
     unreadable behavior). If analysis.json.warnings has entries NOT about unresolved children (e.g.
     local-mode "nothing found"), render those as extra "> **Warning:** …" lines. Omit entirely when
     there is nothing to flag. -->
> **⚠ Data gap — {{n_unresolved}} referenced child workflow(s) could not be analyzed.** Their contents were not followed and must not be assumed. The full list is in [Manual Action Checklist → General](#general). Pull them into scope (live) or add their JSON to `--local-dir`, then re-run this report.

## Contents

1. [Summary](#summary)
2. [Workflows](#workflows)
3. [JSON Forms](#json-forms)
4. [Scripts, Playbooks & Roles](#scripts-playbooks--roles)
5. [Inventory](#inventory)
6. [Recommended Repository Structure](#recommended-repository-structure)
7. [Manual Action Checklist](#manual-action-checklist)

## Summary

| Metric | Count |
|---|---|
| Workflows referencing Gateway4 | {{n_workflows}} |
| Gateway4 tasks | {{n_gw4_tasks}} |
| JSON form fields bound to Gateway4 | {{n_forms}} |
| Config Manager devices sourced from Gateway4 | {{n_gw4_devices}} |
| Gateway4 scripts/playbooks/roles (local) | {{n_assets}} |
| Referenced workflows not analyzed (unresolved) | {{n_unresolved}} |
| Gateway4 inventory | {{inventory_status}} |

## Workflows

<!-- PURE-FACTS analysis section — NO recommendations, NO codes, NO "what to do". Just what is on the
     platform. GROUPED BY LOCATION: iterate analysis.json.workflow_groups (already ordered — projects
     first by name, then a final "Global" group; workflows within a group already name-sorted). Do
     NOT recompute or re-sort.

     For EACH group:
       ### {{group.label}}
         group.label = "«{project_name}» ({project_id})" for a project, or "Global" for the
         not-in-a-project group. The project/Global identity lives HERE, so it is NOT repeated in the
         per-workflow rows below (no "Scope / Connector" column, no location in the detail heading).

       an INDEX TABLE for that group's workflows (project context is the headline, so it's dropped):
         | Workflow | Tasks | Interface(s) | ID |
         | `{{workflow_name}}` | {{n_tasks}} | {{interfaces joined ", "}} | `{{workflow_id}}` |
         - Interface(s) = workflow.interfaces (distinct, task order) joined ", " — FACT from the data:
           "AG Manager" (AGManager application) and/or the ACTUAL adapter name(s); what the reader
           needs for Gateway5 cluster mapping. No recommendation implied.
         - ALWAYS print `workflow_id` (disambiguates the same use case cloned across places — identical
           names, distinct ids; real distinct workflows, not a pull artifact).

       then ONE `####` DETAIL SECTION per workflow in the group:
         #### `{{workflow_name}}` · `{{workflow_id}}`      (no location — the group headline carries it)
         a 3-col table, ONE ROW PER TASK (facts only):
           | Task | Name | Interface |
           | `{{task_id}}` | {{task_name}} | {{interface}} |
         `interface` (req a) = exactly "AG Manager" or the ACTUAL adapter name (verbatim).

         References — collect the relationship lines for this workflow, in this order:
            (1) if called_by (req c) non-empty: "Called by `{{name}}` (`{{id}}`), `{{name}}` (`{{id}}`)"
                (IN-SCOPE parents only — the scan never looks outside the requested scope)
            (2) for each task whose referenced_by (req b) is non-empty:
                "`{{task_id}}` output used by `{{ref_id}}`, `{{ref_id}}`"
           Zero lines → render nothing. Exactly ONE line → inline "**References:** <line>". MORE than
           one → a "**References:**" header then a bullet per line. -->
{{n_workflows}} workflows reference Gateway4 tasks ({{n_gw4_tasks}} tasks total), grouped by project below (Global workflows last). Each project lists its workflows, then per-workflow task detail and cross-references.

{{#each group}}
### {{group.label}}

| Workflow | Tasks | Interface(s) | ID |
|---|---|---|---|
{{#each group.workflow}}| `{{workflow_name}}` | {{n_tasks}} | {{interfaces}} | `{{workflow_id}}` |
{{/each}}

{{#each group.workflow}}
#### `{{workflow_name}}` · `{{workflow_id}}`

| Task | Name | Interface |
|---|---|---|
{{#each task}}| `{{task_id}}` | {{task_name}} | {{interface}} |
{{/each}}
{{references_block}}
{{/each}}
{{/each}}
<!-- if none (workflow_groups empty): --> {{none_workflows}}  <!-- "No Gateway4 references found." -->

## JSON Forms

<!-- Any form field whose BINDING ENDPOINT points at the automation_gateway adapter or the
     agmanager app — REST-bound dropdowns AND non-dropdown fields alike. Matched on endpoint URL
     only, never the request body (a /configuration_manager/... field filtering by adapterType is
     Configuration Manager, NOT Gateway4). Only forms belonging to IN-SCOPE projects are scanned. -->
{{#each form}}- **{{form_name}}** — {{field_key}} (`{{bound_endpoint}}`): rebind to the Gateway5/replacement endpoint — returns no data once Gateway4 is removed.
{{/each}}
<!-- if none: --> {{none_forms}}  <!-- "No Gateway4-bound form fields." -->

## Scripts, Playbooks & Roles

{{#each asset}}- `{{filename}}` ({{asset_type}}) — {{short_recommendation}}
{{/each}}
<!-- if none: --> {{none_assets}}  <!-- "No Gateway4 references found." -->

## Inventory

<!-- Two parts:
     1. Config Manager devices — from analysis.json.devices:
        - present:true, n_iag4>0 → a lead line "**{n_iag4} of {n_devices}** Config Manager devices are
          sourced from a Gateway4 adapter (origin `{origins}`) and need to be re-homed in Inventory
          Manager before Gateway4 is removed:" then ONE dot-separated line of `device_name` values
          (NOT one bullet per device — that lives in the checklist). If origins vary, state per-device
          origin inline instead.
        - present:true, n_iag4==0 → "No Config Manager devices are sourced from a Gateway4 adapter."
        - present:false → "Config Manager devices not pulled — cannot check device origins."
          (scoped/local runs where the device check is out of scope → "Skipped — outside scan scope.")
     2. Gateway4 built-in inventory (from the Gateway4 source the user gave; never Gateway5): if not
        accessed/none provided → "No Gateway4 built-in inventory was found in the local directory
        provided." (or the generic not-accessed line); if present → note to move it to Inventory Manager. -->
{{inventory_finding}}

## Recommended Repository Structure

<!-- FIXED guidance section, always rendered. **Option A is ALWAYS the recommendation** — never
     make it conditional on service count, and do NOT print any service counts here. Tailor the
     Option A tree and the Naming-Conventions "Examples" column to THIS environment's migrated
     services (from checklist.workflows + the Step 4 assets): one leaf per service, foldered by
     domain, annotated `← was <original> (<iag4_type>)`. python-script leaves get main.py +
     requirements.txt; ansible-playbook leaves get playbook.yml. Options B and C are shown for
     scale but keep them brief. Use placeholder team names `team1`, `team2`, … (one team per
     domain in B/C) — never assume real team names. Keep the three option headings and the Naming
     Conventions table headings verbatim so runs stay comparable. Do NOT add a "See /iag …" line
     here — that pointer lives in the SKILL, not the report. -->
Gateway5 runs services **only from a git repository**. Three layouts are shown below; **Option A
(mono-repo) is recommended** for most environments — Options B and C are for larger teams or
stricter ownership / separation-of-concerns requirements. Team names below are placeholders
(`team1`, `team2`, …) — substitute your own.

### Option A — Mono-repo (recommended)

{{option_a_tree}}

### Option B — Multi-repo (per-domain ownership)

{{option_b_tree}}

### Option C — Service-file repo + code repos (separation of concerns)

{{option_c_tree}}

### Naming Conventions

| Item | Pattern | Examples (this environment) |
|---|---|---|
| Services | `{team}-{domain}-{action}` | {{service_name_examples}} |
| Decorators | `{service-name}-decorator` | {{decorator_examples}} |
| Repositories | `{team}-{purpose}` | {{repo_examples}} |
| Secrets | `{team}-{system}-{purpose}` | {{secret_examples}} |

## Manual Action Checklist

<!-- Grouped by item type. Emit a `### <group>` subheading then its items. Render ONLY groups that
     have actions; drop an empty group entirely. Group order: Workflows, JSON Forms,
     Scripts/Playbooks/Roles, Inventory, General. -->
### Workflows

<!-- Self-contained items — each carries its full recommendation text, so no separate legend is
     needed. checklist.workflows is already sorted by recommendation then name (so identical
     recommendations sit together). Item: "- [ ] `{{key}}` ({{app_display}}, {{count}} task|tasks) —
     {{recommendation}}". app_display is "AG Manager" or the adapter type (resolved in analysis.json).
     Pluralize: "task" if count==1 else "tasks". No codes, no divergence note. -->
{{#each checklist.workflows}}- [ ] `{{key}}` ({{app_display}}, {{count}} task(s)) — {{recommendation}}
{{/each}}

### JSON Forms

{{#each checklist.forms}}- [ ] **{{form_name}}** — {{field_key}} (`{{bound_endpoint}}`): {{recommendation}}
{{/each}}

### Scripts, Playbooks & Roles

{{#each asset}}- [ ] `{{filename}}` — {{short_recommendation}}
{{/each}}

### Inventory

{{#each device}}- [ ] `{{device_name}}` (origin {{origins}}) — {{recommendation}}
{{/each}}{{inventory_action}}

### General

<!-- Cross-cutting items. MUST include a repo-setup item pointing at the Recommended Repository
     Structure section and a git-secret item. THEN, if analysis.json.unresolved_children is non-empty,
     render the moved data-gap list here as its own labelled block (this is where the top callout
     points). Do NOT emit any service counts. -->
- [ ] Set up the Gateway5 service git repository — see [Recommended Repository Structure](#recommended-repository-structure) (Option A recommended)
- [ ] Store Gateway5 service credentials as git-backed secrets, not embedded in scripts

**Unresolved child workflows — pull into scope (live) or add JSON to `--local-dir`, then re-run:**

{{#each unresolved_children}}- [ ] `{{name}}`
{{/each}}
