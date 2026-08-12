<!--
Gateway4 → Gateway5 Readiness Report — FIXED TEMPLATE.
The iag4-to-iag5 skill fills this in. Keep section order and headings identical every run so
the same inputs always produce a byte-identical report (aside from the header metadata line).
Canonical section order (also the Table of Contents at the top): Summary, Workflows, JSON Forms,
Scripts/Playbooks & Roles, Inventory, Recommended Repository Structure, Manual Action Checklist.
The checklist is LAST. The TOC links to each section.
Placeholders are wrapped in {{ }}. Every section is ALWAYS rendered — if a section has no
findings, emit its "No Gateway4 references found." line instead of dropping the section.

DESIGN: the analysis stays factual, but each Gateway4 task carries ONE short remediation CODE
(WRAP / REVIEW / ARGS / INV). The codes are explained ONCE in the static "Recommended Actions"
legend section; task tables show only the code, never the full sentence. The full recommendation
text lives in the legend and the end Manual Action Checklist. Codes are a best-effort classification
from each task's name/summary/description — the legend says "review each". Never write the full
recommendation sentence into the Workflows tables (just the code).

WORDING RULE (hard): the rendered report must NOT contain "iag", "IAG4", or "IAG5". Use
"Itential Gateway4"/"Gateway4" and "Itential Gateway5"/"Gateway5". Keep literal API/app names
(GatewayManager.runService, AG Manager) and the ACTUAL adapter names verbatim so the reader can
identify them on the platform. (Scripts/variable names may still use IAG internally — never rendered.)

FIXED remediation CODES — the "Recommended action" cell for each is the VERBATIM REC_* constant in
analyze_iag4.py (CODE_BY_TYPE / REC_BY_CODE); keep both in sync (determinism contract):
  - WRAP   (collection-or-role task, e.g. itential_cli / itential_set_config): wrap in a Python script or an Ansible playbook and run as a Gateway5 service, or replace with an Inventory Manager send_command/set_config task if that covers the same logic
  - REVIEW (ansible playbook):        likely no code change — review how inventory is handled (Gateway5 has no built-in inventory)
  - ARGS   (python script):           change positional args to named args (--flag / argparse); run as a Gateway5 python-script service
  - INV    (device/group op on the Gateway4 adapter): move to the Inventory Manager application; use a device send-command / set-config task instead of the Gateway4 device operation
Other fixed strings (keep in sync too):
  - json form field:        rebind to the Gateway5/replacement endpoint — returns no data once Gateway4 is removed.
  - gateway4-origin device:  device sourced from a Gateway4 adapter; re-home it in Inventory Manager before removing Gateway4
  - python asset (argv):    convert positional args to argparse flags; place in a git repo
  - python asset (argparse):already uses named args; place in a git repo
  - shell asset:            wrap in a Python script (python-script service) or register as an executable service; place in a git repo
  - role asset:             wrap in a playbook or Python script; place in a git repo
  - playbook asset:         place in a git repo; no code change

Sort rules (analyze_iag4.py already applies them — render straight through): workflows by name (asc),
then project id, then workflow id; tasks within a workflow by task id (asc); checklist by code
(WRAP, REVIEW, ARGS, INV) then name; forms by name; assets by filename; devices by name;
unresolved_children as
given (sorted). No per-row timestamps.

Workflow location comes from the workflow's `namespace` field (authoritative project membership):
"Global" when not project-owned, else "{project_name} ({project_id})" (plain text — no special
brackets/quoting around the name). A stale @id: name prefix is NOT project membership — those are
Global. Never emit "name unavailable". Location is rendered the SAME way everywhere (index
Scope/Connector column AND detail heading) — the project id is kept.

TOC anchors for the nested Workflows sub-links (see Contents below) are plain GitHub slugs of
`group.label`: lowercase, drop any character that isn't a letter/digit/space/hyphen (this drops the
parentheses around the id), then replace spaces with hyphens. E.g. "Arista EOS (66d0da17...)" ->
"arista-eos-66d0da17...". "Global" -> "global". Since labels are plain text (no «» quoting), this
is a direct, deterministic slug — compute it the same way every run.
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

<!-- The Workflows entry (3) nests one sub-link per analysis.json workflow_groups[] entry (project/
     Global groups, in the same order rendered in the Workflows section) so the reader can jump
     straight to a project. Anchor = the slug rule above. Do NOT nest down to individual workflows
     (keeps the TOC compact) — each group's index table below already lists its workflows with IDs. -->
1. [Summary](#summary)
2. [Recommended Actions](#recommended-actions)
3. [Workflows](#workflows)
   {{#each group}}- [{{group.label}}](#{{slug(group.label)}})
   {{/each}}
4. [JSON Forms](#json-forms)
5. [Scripts, Playbooks & Roles](#scripts-playbooks--roles)
6. [Inventory](#inventory)
7. [Recommended Repository Structure](#recommended-repository-structure)
8. [Manual Action Checklist](#manual-action-checklist)

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

## Recommended Actions

<!-- STATIC legend, always rendered verbatim. The "Recommended action" cells are the VERBATIM
     REC_WRAP / REC_REVIEW / REC_ARGS / REC_INV constants from analyze_iag4.py — do not reword
     (determinism sync). Each Gateway4 task in Workflows is tagged with one of these codes. -->
Each Gateway4 task in the Workflows section is tagged with one short code. Codes are a best-effort
classification from the task's name and description — **review each** before acting.

| Code | Applies to (Gateway4 task type) | Recommended action |
|---|---|---|
| **WRAP** | Ansible collection-module task or role (e.g. `itential_cli`, `itential_set_config`) | wrap in a Python script or an Ansible playbook and run as a Gateway5 service, or replace with an Inventory Manager send_command/set_config task if that covers the same logic |
| **REVIEW** | Ansible playbook | likely no code change — review how inventory is handled (Gateway5 has no built-in inventory) |
| **ARGS** | Python script | change positional args to named args (--flag / argparse); run as a Gateway5 python-script service |
| **INV** | Device/group operation on the Gateway4 adapter | move to the Inventory Manager application; use a device send-command / set-config task instead of the Gateway4 device operation |

## Workflows

<!-- Facts + a short remediation CODE per task (Rec column; full text is in the Recommended Actions
     legend). GROUPED BY LOCATION: iterate analysis.json.workflow_groups (already ordered — projects
     first by name, then a final "Global" group; workflows within a group already name-sorted). Do
     NOT recompute or re-sort.

     For EACH group:
       ### {{group.label}}
         group.label = "{project_name} ({project_id})" (plain text) for a project, or "Global" for the
         not-in-a-project group. The project/Global identity lives HERE, so it is NOT repeated in the
         per-workflow rows below (no "Scope / Connector" column, no location in the detail heading).

       an INDEX TABLE for that group's workflows (project context is the headline, so it's dropped):
         | Workflow | Tasks | Interface(s) | Rec | ID |
         | `{{workflow_name}}` | {{n_tasks}} | {{interfaces joined ", "}} | {{codes joined ", "}} | `{{workflow_id}}` |
         - Interface(s) = workflow.interfaces (distinct, task order) joined ", " — FACT from the data:
           "AG Manager" (AGManager application) and/or the ACTUAL adapter name(s); what the reader
           needs for Gateway5 cluster mapping.
         - Rec = workflow.codes (distinct codes, CODE_ORDER) joined ", " (e.g. "WRAP, ARGS"). Codes
           are explained in the Recommended Actions legend above.
         - ALWAYS print `workflow_id` (disambiguates the same use case cloned across places — identical
           names, distinct ids; real distinct workflows, not a pull artifact).

       then ONE `####` DETAIL SECTION per workflow in the group:
         #### `{{workflow_name}}` · `{{workflow_id}}`      (no location — the group headline carries it)
         a 4-col table, ONE ROW PER TASK:
           | Task | Name | Interface | Rec |
           | `{{task_id}}` | {{task_name}} | {{interface}} | {{code}} |
         `interface` (req a) = exactly "AG Manager" or the ACTUAL adapter name (verbatim). `code` =
         the task's short remediation code (WRAP / REVIEW / ARGS / INV) — full text in the legend.

         References — collect the relationship lines for this workflow, in this order:
            (1) if called_by (req c) non-empty: "Called by `{{name}}` (`{{id}}`), `{{name}}` (`{{id}}`)"
                (IN-SCOPE parents only — the scan never looks outside the requested scope)
            (2) for each task whose referenced_by (req b) is non-empty:
                "`{{task_id}}` output used by `{{ref_id}}`, `{{ref_id}}`"
           Zero lines → render nothing. Exactly ONE line → inline "**References:** <line>". MORE than
           one → a "**References:**" header then a bullet per line. -->
{{n_workflows}} workflows reference Gateway4 tasks ({{n_gw4_tasks}} tasks total), grouped by project below (Global workflows last). Each project lists its workflows, then per-workflow task detail and cross-references. The **Rec** column codes are explained in [Recommended Actions](#recommended-actions).

<!-- Workflows Summary — one row per workflow_groups[] entry, straight from group.n_workflows /
     group.n_tasks (already aggregated by the analyzer — do not recompute). A quick per-project view
     of how much work is outstanding before diving into the per-group detail below. -->
| Project / Location | Workflows | Tasks to fix |
|---|---|---|
{{#each group}}| {{group.label}} | {{group.n_workflows}} | {{group.n_tasks}} |
{{/each}}| **Total** | {{n_workflows}} | {{n_gw4_tasks}} |

{{#each group}}
### {{group.label}}

| Workflow | Tasks | Interface(s) | Rec | ID |
|---|---|---|---|---|
{{#each group.workflow}}| `{{workflow_name}}` | {{n_tasks}} | {{interfaces}} | {{codes}} | `{{workflow_id}}` |
{{/each}}

{{#each group.workflow}}
#### `{{workflow_name}}` · `{{workflow_id}}`

| Task | Name | Interface | Rec |
|---|---|---|---|
{{#each task}}| `{{task_id}}` | {{task_name}} | {{interface}} | {{code}} |
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

<!-- Grouped by CODE (WRAP/REVIEW/ARGS/INV, CODE_ORDER — matches the Recommended Actions legend).
     checklist.workflows is already {code, workflow_name, workflow_id, count} sorted by code then
     workflow name/id. Render ONE #### heading per code that has items (carries the recommendation
     text ONCE via REC_BY_CODE — do not repeat it per item), then one line per workflow: "- [ ]
     `{{workflow_name}}` (`{{workflow_id}}`) — {{count}} task(s)". Skip a code heading entirely if
     it has no items. -->
{{#each code in CODE_ORDER}}
#### {{code}} — {{REC_BY_CODE[code]}}

{{#each checklist.workflows where code==code}}- [ ] `{{workflow_name}}` (`{{workflow_id}}`) — {{count}} task(s)
{{/each}}
{{/each}}

### JSON Forms

{{#each checklist.forms}}- [ ] **{{form_name}}** — {{field_key}} (`{{bound_endpoint}}`): {{recommendation}}
{{/each}}

### Scripts, Playbooks & Roles

{{#each asset}}- [ ] `{{filename}}` — {{short_recommendation}}
{{/each}}

### Inventory

<!-- Simple identification list — device name + origin only, no repeated recommendation text (the
     single re-homing action is already stated once in the Inventory report section above). -->
{{#each device}}- [ ] `{{device_name}}` — origin `{{origins}}`
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
