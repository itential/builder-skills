<!--
IAG4 → IAG5 Readiness Report — FIXED TEMPLATE.
The iag4-to-iag5 skill fills this in. Keep section order and headings identical every run so
the same inputs always produce a byte-identical report (aside from the header metadata line).
Canonical section order (also the Table of Contents at the top): Summary, Workflows, JSON Forms,
Scripts/Playbooks & Roles, Inventory, Recommended Repository Structure, Manual Action Checklist.
The checklist is LAST (after Recommended Repository Structure). The TOC links to each section.
Placeholders are wrapped in {{ }}. Every section is ALWAYS rendered — if a section has no
findings, emit its "No IAG4 references found." line instead of dropping the section.
Sort rules: workflows by name (asc), then project id, then workflow id; tasks within a workflow by task id (asc),
forms by name (asc), IAG4 assets by filename (asc), devices by name (asc), checklist by section
then name. No per-row timestamps. The script (analyze_iag4.py) already applies every sort — render
straight from analysis.json.
Keep it terse — this is a working checklist, not a narrative. No read-only banners, no "two
rules" preamble, no per-workflow tables. Those belong in the skill, not the report.
Short recommendation strings are FIXED (verbatim) for determinism — they are the module-level
constants in analyze_iag4.py; keep both in sync:
  - ansible-playbook task:  register playbook as an IAG5 ansible-playbook service; call via GatewayManager.runService
  - python-script task:     re-implement as an IAG5 python-script service; call via GatewayManager.runService
  - self-management task:   move to the Inventory Manager application; drop this task
  - json form field:        rebind to the IAG5/replacement endpoint — returns no data once IAG4 is removed.
  - iag4-origin device:     device sourced from an IAG4 gateway adapter; re-home it in Inventory Manager before removing IAG4
  - python asset (argv):    convert positional args to argparse flags; place in a git repo
  - python asset (argparse):already uses named args; place in a git repo
  - shell asset:            wrap in a Python script (python-script service) or register as an executable service; place in a git repo
  - role asset:             wrap in a playbook or Python script; place in a git repo
  - playbook asset:         place in a git repo; no code change
Workflow location comes from the workflow's `namespace` field (authoritative project membership):
"Global" when not project-owned, else "«{project_name}» ({project_id})". A stale @id: name prefix
is NOT project membership — those are Global. Never emit "name unavailable".
-->

# IAG4 → IAG5 Migration Readiness

**Generated:** {{YYYY-MM-DD}} · **Working dir:** {{working_dir}}
**IAP source:** {{iap_source}} · **IAG4 assets:** {{iag4_source}}
**IAG4 matched:** adapter `{{adapter_type}}` (instances: {{adapter_instances}}), app `{{agmanager_app}}`
**Scope:** {{scope_description}}

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
| Workflows referencing IAG4 | {{n_workflows}} |
| IAG4 tasks | {{n_iag4_tasks}} |
| JSON form fields bound to IAG4 | {{n_forms}} |
| Config Manager devices sourced from IAG4 | {{n_iag4_devices}} |
| IAG4 scripts/playbooks/roles (local) | {{n_assets}} |
| IAG4 inventory | {{inventory_status}} |

## Workflows

<!-- One TABLE, ONE ROW PER WORKFLOW (not per task). All of a workflow's IAG4 tasks go in the last
     cell, one per line, joined by literal <br>. This keeps each workflow on a single row so a
     reader can instantly see which workflows have >1 IAG4 task, even when several workflows share
     the same NAME (the same use case cloned across places) — `workflow_id` is what distinguishes
     them; they are distinct workflows, not a pull artifact. Location is the project NAME when the
     workflow's `namespace` marks it as project-owned (project id in parens for disambiguation);
     when `location_type` is "global" (no live project — includes workflows whose name carries a
     stale @id: prefix for a deleted project) Location is exactly "Global". Never emit "name
     unavailable". Rows sorted by workflow name, then project id, then workflow id; tasks within the
     cell by task id (the script already applies this — render straight through). -->
| Workflow | Workflow ID | Location | IAG4 Tasks & Recommendations |
|---|---|---|---|
{{#each workflow}}| {{workflow_name}} | `{{workflow_id}}` | {{location}} | {{#join task with <br>}}`{{task_id}}` **{{task_name}}** — {{short_recommendation}}{{/join}} |
{{/each}}
<!-- location cell: "Global", or "«{project_name}» ({project_id})" when location_type == "project".
     tasks cell: for each task `{{task_id}}` **{{task_name}}** — {{short_recommendation}}, joined by <br>. -->
<!-- if none: --> {{none_workflows}}  <!-- "No IAG4 references found." -->

## JSON Forms

<!-- Any form field whose endpoint/body/validation points at the automation_gateway adapter or the
     agmanager app — REST-bound dropdowns AND non-dropdown fields alike. -->
{{#each form}}- **{{form_name}}** — {{field_key}} (`{{bound_endpoint}}`): rebind to the IAG5/replacement endpoint — returns no data once IAG4 is removed.
{{/each}}
<!-- if none: --> {{none_forms}}  <!-- "No IAG4-bound form fields." -->

## Scripts, Playbooks & Roles

{{#each asset}}- `{{filename}}` ({{asset_type}}) — {{short_recommendation}}
{{/each}}
<!-- if none: --> {{none_assets}}  <!-- "No IAG4 references found." -->

## Inventory

{{inventory_finding}}
<!-- Two parts, both one line each:
     1. Config Manager devices: if analysis.json devices.present is true, state how many of
        n_devices have an IAG4 gateway origin and list each flagged device as:
          - `{{device_name}}` (origin {{origins}}) — device sourced from an IAG4 gateway adapter; re-home it in Inventory Manager before removing IAG4
        If devices.present is false: "Config Manager devices not pulled — cannot check device origins."
        If present but n_iag4 == 0: "No Config Manager devices are sourced from an IAG4 gateway."
     2. Gateway built-in inventory: if IAG4 was not accessed: "IAG4 not accessed — if the gateway
        holds a built-in inventory, move it to Inventory Manager in IAP." If present: same action.
        If none: "No IAG4 built-in inventory found." -->

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
IAG5 runs services **only from a git repository**. Three layouts are shown below; **Option A
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

<!-- Grouped by item type. Emit a `### <group>` subheading then its `- [ ]` items. Render ONLY the
     groups that have actions; drop an empty group entirely (do not print an empty heading). Group
     order is fixed: Workflows, JSON Forms, Scripts/Playbooks/Roles, Inventory, General.
     - Workflows      ← checklist.workflows: `- [ ] `{{key}}` ({{app}}, {{count}} tasks) — {{recommendation}}`
     - JSON Forms     ← checklist.forms: `- [ ] **{{form_name}}** — {{field_key}} (`{{bound_endpoint}}`): {{recommendation}}`
     - Scripts/Playbooks/Roles ← Step 4 assets: `- [ ] `{{filename}}` — {{short_recommendation}}`
     - Inventory      ← flagged devices (Step 5a) + gateway built-in inventory (Step 5b)
     - General        ← cross-cutting items -->
### Workflows

{{#each checklist.workflows}}- [ ] `{{key}}` ({{app}}, {{count}} tasks) — {{recommendation}}
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

{{#each general_action}}- [ ] {{action_text}}
{{/each}}
<!-- General MUST include a repo-setup item pointing at the Recommended Repository Structure
     section ABOVE, e.g. "- [ ] Set up the IAG5 service git repository — see Recommended Repository
     Structure above (Option A recommended)" plus a git-secret item. Do NOT emit the old
     "TBD: git repo layout" line, and do NOT print any service counts. -->

