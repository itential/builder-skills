---
name: iag4-to-iag5
description: Assess how ready an environment is to move from Itential Automation Gateway 4 (IAG4) to IAG5. Use for phrases like "am I ready to move to IAG5", "assess my IAG4 to IAG5 migration", "what do I need to change to switch off gateway 4", "scan my workflows for automation gateway usage", "which workflows use IAG4", "IAG4 readiness report", or "evaluate my gateway migration". This skill does NOT perform the migration — it analyzes IAP assets (workflows in and out of projects, JSON forms) and IAG4 assets (scripts, playbooks, roles, inventory), then writes a deterministic markdown guideline of the manual actions the user must take. It is strictly READ-ONLY against IAP and IAG — it never creates, updates, or deletes anything on the platform; its only write is the report in the working directory. For actually building IAG5 services, use /iag.
argument-hint: "[working-directory]"
---

# IAG4 → IAG5 Readiness Assessment (iag4-to-iag5)

**Path:** Standalone analysis — not part of the delivery lifecycle. Sibling to `/iag`.
**Owns:** Identifying IAG4 usage across IAP + IAG4 assets and reporting the manual migration steps.
**Produces:** `<working-dir>/iag4-to-iag5-readiness.md` — one deterministic markdown report. All
pulled JSON, the auth cache, and scratch files go under `<working-dir>/tmp/` — never the
working-dir root. Only the report lives in the root.

## What this does (and does NOT do)

IAG4 and IAG5 are architecturally different:

| | IAG4 | IAG5 |
|---|---|---|
| IAP interface | `automation_gateway` adapter + **`AGManager`** application (`agmanager`) | **`GatewayManager`** application (`runService`) |
| Runnable things | playbooks, scripts (any lang), roles, ansible modules | Python scripts, Ansible playbooks, OpenTofu plans, + `executable` type |
| Source of services | uploaded to the gateway | **git repository only** |
| Script inputs | positional args (`sys.argv[n]`, `./x a b`) | **named CLI flags** (`--from a --to b`) |
| Inventory | built-in gateway inventory | **none** — use Inventory Manager in IAP |

> **`AGManager` (IAG4) and `GatewayManager` (IAG5) are two different applications.** Flag
> `AGManager`; never flag `GatewayManager` — it is the migration target.

**This skill only IDENTIFIES and RECOMMENDS.** It does not rewrite scripts, generate IAG5
service YAML, or rewire workflows — that is future work. Its single output is the readiness
report. Keep every recommendation to a **manual action the user performs themselves**.

### Read-only guarantee (hard rule)

This skill is **read-only against IAP and IAG**. Its ONLY write target is the **working
directory** (the report, plus any pulled read-cache JSON).
- **Allowed:** auth (`/oauth/token`, `/login`), read/discovery **GET**s (workflows, json-forms,
  projects export, apps, adapters), the POST-based **devices read** if needed; on IAG, only
  read-only `iagctl get/describe/db export` or local files.
- **Forbidden:** any create/update/delete/import/patch on IAP or IAG — no state-mutating
  `POST/PUT/PATCH/DELETE`, no `iagctl db import`, no writing services, no editing/creating
  workflows, forms, projects, inventory, or gateway config. If a step *would* mutate the
  platform, **do not do it** — record it in the report as a manual action for the user.

These two rules are agent guidance — they shape the recommendations but are **not** printed in
the report (the report is a terse checklist, not a narrative):
1. IAG5 runs **Python scripts, Ansible playbooks, OpenTofu plans** natively, plus an
   **`executable`** type (`filename` + `arg-format`) for other binaries/scripts. Anything not
   directly runnable needs a wrapper (usually a Python wrapper).
2. IAG5 services run **only from a git repository** — migrated assets must live in a git repo the
   gateway can reach (this is `/iag`'s `repositories:` block). The report includes a **Recommended
   Repository Structure** section (Options A/B/C + naming conventions) that you tailor to the
   environment's actual services — see Step 6. Defer to `/iag` for the mechanics of `services.yaml`,
   named-arg contracts, and `runService` wiring.

**Defer to `/iag` for all "how".** This skill identifies *what* must change; `/iag` is the
authoritative reference for building the IAG5 service, the `--property_name` named-arg contract,
`repositories:`, and `GatewayManager.runService` wiring (incl. `clusterId` via
`GET /gateway_manager/v1/gateways/`). Do not duplicate that here — point the reader to `/iag`.

## Determinism contract

Same inputs ⇒ identical report. Enforce:
- Fixed section set/order — from `${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/readiness-report-template.md`. Never drop a section; empty sections render `No IAG4 references found.`
- **The workflow + JSON-form findings are produced by `analyze_iag4.py`** (Step 2), not by the
  model — that script owns their determinism (detection, classification, sorting, aggregation).
  Its recommendation strings MUST stay byte-identical to the template. Render those sections
  verbatim from `tmp/analysis.json`; only the scripts + inventory sections are model-authored.
- Stable sort (the script already applies this): workflows by name (asc); tasks within a workflow
  by task id (asc); forms by name (asc); IAG4 assets by filename (asc); checklist by section then name.
- The **only** volatile line is the header `Generated:` date and the source lines. No per-row
  timestamps, no random ordering, no rephrasing of the fixed recommendation strings below.
- The report is a **terse checklist** — header, summary table, bullet/sub-bullet workflow list,
  short form/asset/inventory sections, checklist. Do NOT print the read-only guarantee, the two
  IAG5 rules, or any adapter/instance explainer in the report — those are agent guidance only.

---

## Step 0 — Working directory, scope & data sources

**Ask these two up front if the user did not already supply them** (use AskUserQuestion):

1. **Working directory** — where the report is written. If the user passed one as an argument,
   use it; else ask.
2. **Scan scope** — the workflow analysis (Step 2) is driven by one of three deterministic
   scopes; ask which the user wants and carry it into the script flag:
   - **project(s)** → `--projects <id,id>` (recommended — one or more project ids)
   - **explicit workflow list** → `--workflows "Name A;Name B"`
   - **all workflows** → `--all` — **not recommended**: on a large platform this scans every
     workflow (here 1504) and can overflow a small model's context window. Only use if the user
     explicitly asks.

Then establish the data sources:

3. **Never assume the source of assets.** Look for a `.env` in the working dir (the auth cache
   lives at `tmp/.auth.json`).
   - If a `.env` exists, determine whether it targets **IAP only, IAG only, or both**. If the
     file's purpose is unclear, **ask the user** — do not guess.
   - Ask (or confirm) what the user has: local IAP asset JSON, live IAP access, local IAG4
     assets, live IAG4 access — any combination, including IAP-only or IAG4-only.
4. Establish each source as `live`, `local`, or `none`. **Local files take precedence** over
   live pulls when both exist. Record all of this for the report header.

## Step 1 — IAP data (only if IAP is in scope)

Prefer local files in the working dir. Otherwise pull live, reusing the `/explore` mechanics.
**All pulled JSON and the auth cache go under `<working-dir>/tmp/`** — create it first
(`mkdir -p <working-dir>/tmp`). Never write these to the working-dir root.

**Auth.** Read `PLATFORM_URL`, `AUTH_METHOD`, and credentials from `<working-dir>/.env`. Reuse
`tmp/.auth.json` if present; silent re-auth from `.env` on 401/403 (AGENTS.md auth-reuse
procedure). Never ask for credentials if `.env` exists. **The token transport depends on the
auth method — do not mix them up (this is the #1 cause of "malformed token" failures):**

- **OAuth / cloud (`AUTH_METHOD=oauth`):** `POST /oauth/token`
  (`Content-Type: application/x-www-form-urlencoded`, body
  `grant_type=client_credentials&client_id=...&client_secret=...`) → `access_token`. Send it on
  **every** call as an `Authorization: Bearer <token>` **header**. `?token=` does NOT work for
  OAuth tokens.
- **Local (`AUTH_METHOD=login` / username+password):** `POST /login` (`application/json`,
  `{"username":...,"password":...}`) → token string. Send it as a `?token=<token>` **query
  param**.

**Pull** — read-only GETs only, saved into `tmp/` (validate each with `jq type`). OAuth example
(reuse the `$AUTH` header var for every call — this is the pattern that actually works):
```bash
mkdir -p <working-dir>/tmp
TOKEN=$(jq -r .access_token <working-dir>/tmp/.auth.json)
AUTH="Authorization: Bearer ${TOKEN}"
curl -s -H "$AUTH" "{BASE}/automation-studio/apps/list"   -o tmp/apps.json
curl -s -H "$AUTH" "{BASE}/health/adapters"               -o tmp/adapters.json
curl -s -H "$AUTH" "{BASE}/json-forms/forms"              -o tmp/json-forms.json
```

**Projects — optional, defensive fallback only.** Project names now come from each workflow's own
`namespace` field (returned inline on the workflows list), so `projects.json` is **no longer the
primary source** for the `project_id → name` map. The script uses it only as a fallback for the
rare workflow that lacks a namespace but whose name prefix still resolves to a live project. Pull
it if convenient (paginate the same 100/page cap; merge every page's `data[]` into one
`{"data":[...]}`), but a missing/partial `projects.json` no longer causes `name unavailable`:
```bash
total=$(curl -s -H "$AUTH" "{BASE}/automation-studio/projects?limit=1" | jq '.metadata.total')
skip=0; echo '{"data":[]}' > tmp/projects.json
while [ "$skip" -lt "${total:-0}" ]; do
  curl -s -H "$AUTH" "{BASE}/automation-studio/projects?limit=100&skip=${skip}" \
    | jq '{data:.data}' > tmp/projects.page.json
  jq -s '{data: (.[0].data + .[1].data)}' tmp/projects.json tmp/projects.page.json > tmp/projects.merged.json \
    && mv tmp/projects.merged.json tmp/projects.json
  skip=$((skip+100))
done
rm -f tmp/projects.page.json
```
A workflow is treated as project-owned **only** when its `namespace` says so; a workflow whose name
carries a stale `@{id}:` prefix for a deleted project is reported as **Global**, not `name
unavailable`.

**Devices — for the Inventory check (read-only, POST is a query not a mutation).** So the analyzer
can tell whether Configuration Manager devices are sourced from an IAG4 gateway adapter, pull the
device list into `tmp/devices.json`. `POST /configuration_manager/devices` is the "Find Devices"
read query; body `{"options":{"start":0,"limit":100}}`, response shape `{total, list:[...]}` where
each device carries `origins[]` (the source adapter instances). Paginate on `total`:
```bash
total=$(curl -s -H "$AUTH" -H "Content-Type: application/json" \
  "{BASE}/configuration_manager/devices" -d '{"options":{"start":0,"limit":1}}' | jq .total)
start=0; echo '{"list":[]}' > tmp/devices.json
while [ "$start" -lt "${total:-0}" ]; do
  curl -s -H "$AUTH" -H "Content-Type: application/json" \
    "{BASE}/configuration_manager/devices" -d "{\"options\":{\"start\":${start},\"limit\":100}}" \
    | jq '{list:.list}' > tmp/devices.page.json
  jq -s '{list: (.[0].list + .[1].list)}' tmp/devices.json tmp/devices.page.json > tmp/devices.merged.json \
    && mv tmp/devices.merged.json tmp/devices.json
  start=$((start+100))
done
rm -f tmp/devices.page.json
```
Skip this only if IAP is out of scope or Configuration Manager is not installed. If `devices.json`
is absent the analyzer degrades gracefully (reports "device origins not checked").

**Workflows — MUST paginate (the list caps at 100 per page).** A single `?limit=500` silently
returns only 100 rows while `total` may be far higher (e.g. 1504) — you WILL miss workflows.
Read `total` from the first page, then loop `skip` in steps of the returned page size, appending
each page's `items[]`:
```bash
total=$(curl -s -H "$AUTH" "{BASE}/automation-studio/workflows?limit=1" | jq .total)
# FAIL FAST: if `total` is not a number, auth failed (the first call returned an error body, not a
# workflows page). Do NOT proceed — an empty pull produces a misleading all-zeros report. The #1
# cause is sending an OAuth token as ?token= instead of the Authorization: Bearer header.
case "$total" in ''|*[!0-9]*) echo "AUTH/PULL FAILED — workflows 'total' is not numeric ('$total'). Fix auth (OAuth token goes in the Authorization: Bearer HEADER, not ?token=) and re-run." >&2; exit 1;; esac
skip=0; : > tmp/wf_all.ndjson
while [ "$skip" -lt "$total" ]; do
  curl -s -H "$AUTH" "{BASE}/automation-studio/workflows?limit=100&skip=${skip}" \
    | jq -c '.items[]' >> tmp/wf_all.ndjson
  skip=$((skip+100))
done
# VALIDATE the pull before running the analyzer: the ndjson line count must match `total`. A count of
# 0 (or well below `total`) means pages 401'd silently — re-auth and re-pull; never analyze a short pull.
lines=$(wc -l < tmp/wf_all.ndjson)
[ "$lines" -eq "$total" ] || echo "WARNING: pulled $lines of $total workflows — pull is incomplete (likely mid-run token expiry); re-auth and re-run before analyzing." >&2
```
`tmp/wf_all.ndjson` (one workflow doc per line) is the full set — global **and** `@{projectId}:`
scoped workflows both come back from this list, so scanning it covers both. (If any project's
workflows are ACL-hidden from the list, export that project via
`GET /automation-studio/projects/{id}/export` and read `components[]` where
`type == "workflow"` → `document.tasks`.)

## Step 1b — Resolve the IAG4 identifiers

IAG4 is matched two ways (confirmed):
1. **`automation_gateway` adapter** — resolve the adapter **type** name (e.g. `AutomationGateway*`)
   from `apps.json` / `adapters.json`, NOT the instance name. A task's `app` field carries the
   adapter *type* (AGENTS.md rules 3 & 23). Note both the type and any instance names so you can
   recognize either.
2. **`AGManager` application** (the `agmanager` app) — workflow tasks with `task.app == "AGManager"`
   (e.g. `itential_cli`, `itential_set_config`, and IAG4 device/group management operations).

**`AGManager` (IAG4) ≠ `GatewayManager` (IAG5) — they are two different applications.** Flag
`AGManager`. **Do NOT match `GatewayManager`** — that is the IAG5 target.

**The analysis script (Step 2) resolves these identifiers itself** from `tmp/adapters.json`
(instances whose `package_id` contains `automation_gateway`) and the fixed `AGManager` app name,
and echoes them in `analysis.json → identifiers`. You only need to intervene if that block comes
back empty/ambiguous (no apps.json, multiple gateway-like adapters) — then **stop and ask the
user to confirm the exact identifiers** before continuing.

---

## Step 2 — Scan IAP workflows + JSON forms (deterministic script)

The workflow and JSON-form analysis is done by a **deterministic script**, not by hand — this is
what guarantees the same inputs always produce the same findings, and it keeps 1000s of workflow
docs out of your context. Run it against the `tmp/` you populated in Step 1, passing the scope
chosen in Step 0:

```bash
python3 -B ${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/analyze_iag4.py \
  --tmp <working-dir>/tmp \
  { --projects <id,id>  |  --workflows "Name A;Name B"  |  --all }
# writes <working-dir>/tmp/analysis.json
```

The script is **read-only** (its only write is `tmp/analysis.json`), needs no network/auth, and
consumes `tmp/{wf_all.ndjson,adapters.json,apps.json,json-forms.json}`. A missing scope flag exits
non-zero; a `wf_all.ndjson` that is missing, empty, **or non-workflow** (rows that parse as JSON but
carry no `tasks` object — the signature of a mid-pull auth failure that wrote error bodies like
`{"message":"Unauthorized"}` into the ndjson) exits 2 (go back to Step 1 — this means the pull failed
auth, NOT that there is no IAG4 usage; a genuinely IAG4-free platform still has real workflows WITH
tasks). **If the script exits non-zero, STOP — do not write a report and never report "0 workflows /
0 IAG4 tasks" off a failed pull.** Fix auth (OAuth
token → `Authorization: Bearer` header, not `?token=`), re-pull, and re-run. Then **read
`tmp/analysis.json`** — it contains `identifiers`, `counts`, sorted `workflows[]`, sorted `forms[]`,
and an aggregated `checklist`. Do not re-walk the workflows yourself; the JSON is authoritative for
Steps 2–3 of the report.

**What the script does (documented here so the report strings stay reviewable — the script is the
source of truth; do NOT hand-classify):**

*Workflows.* A task is an **IAG4 task** if its `app`/`location` matches the automation_gateway
adapter (type `AutomationGateway`, or a resolved instance id) or the `AGManager` app. It **never**
flags `GatewayManager` (IAG5). Each IAG4 task is classified from its name/summary/description into
exactly one row, with the verbatim recommendation the report prints:

| Detected IAG4 task | `iag4_type` label | Short recommendation (verbatim) |
|---|---|---|
| **Device/group self-management** (add/remove/create/delete device(s) or group) — checked first | `self-management` | move to the Inventory Manager application; drop this task |
| Playbook/role op — name/summary/description contains "playbook" or "role" (e.g. `install_remove_inactive`, `transfer_image`) | `ansible-playbook` | register playbook as an IAG5 ansible-playbook service; call via GatewayManager.runService |
| **Everything else** — any other IAG4 op (`itential_cli`, `isAlive`, `runCommand`, `getDeviceConfig`, …) | `python-script` | re-implement as an IAG5 python-script service; call via GatewayManager.runService |

`python-script` is the default. The only questions this skill ever asks are the Step 0 pair
(working dir + scope), an unclear `.env` purpose (Step 0), or **unresolved IAG4 identifiers**
(empty/ambiguous `identifiers` block — Step 1b). Never ask how to classify a task.

**Project name — from the workflow's `namespace`, not the name prefix.** Project membership is
resolved from each workflow's authoritative `namespace` field (`{type:"project", _id, name}`), NOT
by parsing the `@<id>:` name prefix. A workflow is **in a project** (and the report shows the
project name) iff `namespace` marks it project-owned; otherwise it is **Global** — including
workflows whose name still carries a stale `@<id>:` prefix pointing at a deleted project (a bulk-
import leftover, not live membership). Each entry carries `location_type` (`global`/`project`),
`project_id`, `project_name`. Render location as `«name» (id)` for a project, else `Global`.
**Never emit "name unavailable"** — the old projects.json-prefix lookup produced that; `namespace`
does not. (`projects.json` is now only a defensive fallback for the rare workflow missing a
namespace whose prefix still resolves to a live project.) Also note `workflow_id` — it
disambiguates copies that share a name.

**Task ids repeat across workflow copies — that is correct, not a bug.** The same use case is
often cloned into many projects, so each copy legitimately shares the same internal task id (e.g.
`49eb`). The id is the real key from the workflow's `tasks` map; distinct copies are distinct
`workflow_id`s. Do not "fix" or dedupe them.

*JSON forms.* A form field is IAG4-bound only when its **binding endpoint URL** points at the IAG4
automation_gateway adapter route prefix (`automationgateway` / `automation_gateway`) or the
`agmanager` app — dropdowns and any other REST-bound field alike. The script matches on the
**endpoint path only**: `base`+`href`, `originalHref`, `links[].href`, and the `binding:hyperSchema`
mirror in `bindingSchema.properties`. **It deliberately does NOT scan the request body.** A field
bound to `/configuration_manager/...` that merely *filters* by
`options.adapterType: ["AutomationGateway"]` is a **Configuration Manager** field, **not** an
IAG4-bound field — flagging it is a false positive (Config Manager is not IAG4; the device-origin
check in Step 5 is what covers IAG4-sourced devices). Each real hit lands in `forms[]` as
`{form_name, field_key, bound_endpoint, matched_on}`; the report prints the fixed line "rebind to
the IAG5/replacement endpoint — returns no data once IAG4 is removed." (Reference shape:
`${CLAUDE_PLUGIN_ROOT}/../../../helpers/assets/json-form-example-rest-bound.json` and `itential-json-forms`.)

## Step 3 — (folded into Step 2)

JSON-form scanning is performed by the same script run in Step 2; its results are in
`analysis.json → forms[]`. No separate action.

## Step 4 — Scan IAG4 assets (local dir / IAG4 pull)

Only if IAG4 assets are in scope. Classify each file and attach the verbatim recommendation:

| Asset | Detection | `asset_type` | Short recommendation (verbatim) |
|---|---|---|---|
| Python script with positional args | `.py` reading `sys.argv[n]` / no argparse named flags | `python` | convert positional args to argparse flags; place in a git repo |
| Python script already using named flags | `.py` with argparse named flags | `python` | already uses named args; place in a git repo |
| Bash/shell/other script | `.sh`/`.bash`/other executable script | `shell` | wrap in a Python script (python-script service) or register as an executable service; place in a git repo |
| Ansible role | role dir layout (`tasks/main.yml`, etc.) | `role` | wrap in a playbook or Python script; place in a git repo |
| Ansible playbook | `.yml`/`.yaml` playbook (plays/tasks, not a role) | `playbook` | place in a git repo; no code change |

## Step 5 — IAG4 inventory

IAG4's built-in inventory does not exist in IAG5. This section has **two parts**:

**(a) Configuration Manager device origins — from the script.** The analyzer reads
`tmp/devices.json` (pulled in Step 1) and flags any device whose `origins[]` (the source
adapter/broker) is one of the resolved IAG4 gateway adapter instances — those devices lose their
source when IAG4 is removed. Read `analysis.json → devices`:
- `present: false` → devices weren't pulled: "Config Manager devices not pulled — cannot check device origins."
- `present: true, n_iag4 == 0` → "No Config Manager devices are sourced from an IAG4 gateway."
- `present: true, n_iag4 > 0` → state the count of `n_iag4`/`n_devices` and list each flagged
  device: `` `{device_name}` (origin {origins}) — device sourced from an IAG4 gateway adapter;
  re-home it in Inventory Manager before removing IAG4 ``.

**(b) Gateway built-in inventory.** If IAG4 was not accessed, say so and note the action; if a
built-in inventory is present, same action; if none, state that. Whenever inventory could exist,
add the checklist item: move it into the **Inventory Manager** application in IAP; inventory
variables can still be passed into IAG5 scripts/playbooks at run time via IAP workflows.
(Lightweight this version — deeper Inventory Manager mapping guidance comes later.)

## Step 6 — Write the report

Fill `${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/readiness-report-template.md` and write
`<working-dir>/iag4-to-iag5-readiness.md` (the report is the **only** file in the working-dir
root — all pulled JSON and scratch stay in `tmp/`).

**Section order (fixed) + Table of Contents.** Render sections in this order: **Summary,
Workflows, JSON Forms, Scripts/Playbooks & Roles, Inventory, Recommended Repository Structure,
Manual Action Checklist** — the checklist is **last**, after the repo section. Immediately under
the header metadata, emit a `## Contents` table-of-contents with one linked entry per section
(GitHub-style anchors, e.g. `[Scripts, Playbooks & Roles](#scripts-playbooks--roles)`) so the
reader can jump around.

**Render the deterministic sections straight from `tmp/analysis.json`** — do not recompute:
- Header identifiers ← `identifiers` (adapter type + instances + app); **Scope** line ← `scope`.
  Summary counts ← `counts` (`n_workflows`, `n_iag4_tasks`, `n_forms`, `n_iag4_devices`).
- **Workflows** section ← `workflows[]` (already sorted) as a **table, ONE ROW PER WORKFLOW**:
  columns `Workflow | Workflow ID | Location | IAG4 Tasks & Recommendations`. Put ALL of a
  workflow's IAG4 tasks in the last cell, one per line joined by literal `<br>`, each formatted
  `` `task_id` **task_name** — short_recommendation ``. Do NOT emit one row per task — a single row
  per workflow lets the reader see at a glance which workflows have more than one IAG4 task even
  when names repeat. **Always print the `workflow_id`** — it disambiguates workflows that share a
  name (the same use case cloned appears as several rows with identical names but distinct ids;
  real distinct workflows, not a duplication artifact). Location cell is exactly `Global` when
  `location_type == "global"`, else `«project_name» (project_id)`. **Never write "name
  unavailable"** — a stale `@id:` prefix is Global, not a project.
- **JSON Forms** section ← `forms[]` (already sorted): `**form_name** — field_key
  (`bound_endpoint`): rebind…`. Forms are matched on the **binding endpoint only**; a
  `/configuration_manager/...` field that filters by `adapterType` is NOT flagged (see Step 2).
- **Recommended Repository Structure** section (comes BEFORE the checklist) — tailor the
  template's fixed Options A/B/C + Naming Conventions to THIS environment's migrated services (the
  distinct `checklist.workflows` keys **plus** the Step 4 assets). **Option A (mono-repo) is ALWAYS
  the recommendation** — do not make it conditional on service count, and do not print any service
  counts anywhere in this section (no "small team / < 20 services" qualifiers on the option
  headings either). In the Option A tree, emit one leaf per service foldered by domain, each
  annotated `← was <original> (<iag4_type>)`; python-script leaves get `main.py` +
  `requirements.txt`, ansible-playbook leaves get `playbook.yml`. Fill the Naming Conventions
  "Examples" column with the actual service names mapped to `{team}-{domain}-{action}`. **Use
  placeholder team names `team1`, `team2`, … (one team per domain in B/C) — never assume real team
  names.** Domains are still derived from the services. Keep the option headings verbatim: `Option
  A — Mono-repo (recommended)`, `Option B — Multi-repo (per-domain ownership)`, `Option C —
  Service-file repo + code repos (separation of concerns)`. **Do NOT render a "See `/iag` …" line
  into the report** — that pointer stays here in the skill: for how to write `services.yaml`, the
  `--property_name` named-arg contract, `repositories:` config, and `GatewayManager.runService`
  wiring, defer to `/iag`.
- **Manual Action Checklist** — the **last** section — **grouped by item type**, each group under
  its own `###` subheading, in fixed order: **Workflows** (← `checklist.workflows`, e.g.
  `` `<key>` (<app>, <count> tasks) — <recommendation> ``), **JSON Forms** (← `checklist.forms`),
  **Scripts, Playbooks & Roles** (← the Step 4 assets you classified), **Inventory** (← the
  flagged devices from `analysis.json → devices` plus the gateway built-in-inventory action from
  Step 5b), and **General** (cross-cutting items — MUST include a repo-setup item pointing at the
  Recommended Repository Structure section ABOVE, e.g. `Set up the IAG5 service git repository —
  see Recommended Repository Structure above (Option A recommended)`, plus a git-secret item).
  **Render only groups that have items — drop an empty group entirely** (no empty heading).
  `checklist.workflows`/`checklist.forms` are already aggregated by recommendation with counts.

Then add the sections you produced yourself: **Scripts/Playbooks/Roles** (Step 4) and the
gateway-inventory half of **Inventory** (Step 5b). The **device-origin** half of Inventory (5a)
comes from `analysis.json → devices` — render each flagged device and add a `- [ ]` checklist item
per flagged device (or one consolidated item if many). All sections go in the fixed template
order; sections with no findings get `No IAG4 references found.`

Finally, tell the user the report path and give a one-paragraph headline of the counts. Note
that `tmp/` is read-cache/scratch and safe to delete.

---

## Gotchas

- **Read-only, always.** Never mutate IAP or IAG. If a step would create/update/delete/import,
  don't — write it into the report as a manual action instead.
- **`AGManager` (IAG4) ≠ `GatewayManager` (IAG5).** Two different applications. Flag `AGManager`;
  never flag `GatewayManager` — it is the IAG5 target interface.
- **Adapter type vs instance.** A task's `app` is the adapter *type*; the instance name lives
  elsewhere. Resolve via `apps.json`/`adapters.json`; recognize both so you don't miss tasks.
- **OAuth token goes in the `Authorization: Bearer` header, NOT `?token=`.** `?token=` only
  works for local `/login` tokens. Sending an OAuth token as a query param returns "malformed
  token" — the #1 auth failure here.
- **Paginate the workflows list.** It caps at 100 rows per page regardless of `limit`. Loop on
  `total` (see Step 1) or you silently scan only the first 100 of possibly thousands.
- **Both global and project workflows.** The `workflows` list returns global **and**
  `@{projectId}:`-scoped workflows, so paginating it covers both. Only fall back to project
  export for projects whose workflows are ACL-hidden from the list.
- **Static dropdowns are not a concern.** Only `binding: true` REST-bound dropdowns can point at IAG4.
- **The script owns workflow + form classification — never hand-classify.** `analyze_iag4.py`
  emits `python-script` as the default. Only *unresolved IAG4 identifiers* (empty `identifiers`
  block — Step 1b), an *unclear `.env` purpose*, or the *Step 0 working-dir/scope pair* warrant a
  question — never the per-task approach or the source.
- **Keep the recommendation strings in sync.** They live once as constants in
  `helpers/iag-migration/analyze_iag4.py` and must match `readiness-report-template.md`
  verbatim. Change them in both places or determinism breaks.
- **Ask working dir + scope first.** If not supplied, ask both up front (Step 0). Warn that
  `--all` can overflow a small model's context on large platforms.
- **Identification only.** Do not create IAG5 services, edit workflows, or rewrite scripts here.
  Route actual builds to `/iag`.

## See also
- `/iag` — building IAG5 services (Python/Ansible/OpenTofu), service YAML, `runService` wiring.
- `/itential-inventory` — Inventory Manager, the IAG5 replacement for gateway inventory.
- `/itential-json-forms` — REST-bound dropdown structure and `bindingSchema`.
- `/explore` — auth + IAP pull mechanics reused in Step 1.
- Analysis script: `${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/analyze_iag4.py` (Step 2, deterministic).
- Template: `${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/readiness-report-template.md`.
