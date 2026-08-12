---
name: iag4-to-iag5
description: Assess how ready an environment is to move from Itential Automation Gateway 4 (IAG4) to IAG5. Use for phrases like "am I ready to move to IAG5", "assess my IAG4 to IAG5 migration", "what do I need to change to switch off gateway 4", "scan my workflows for automation gateway usage", "which workflows use IAG4", "IAG4 readiness report", or "evaluate my gateway migration". This skill does NOT perform the migration — it analyzes IAP assets (workflows in and out of projects, JSON forms) and IAG4 assets (scripts, playbooks, roles, inventory), then writes a deterministic markdown guideline of the manual actions the user must take. It is strictly READ-ONLY against IAP and IAG — it never creates, updates, or deletes anything on the platform; its only write is the report in the working directory. It can also run in a LOCAL-FILES-ONLY mode with no API access. The rendered report uses the terms "Itential Gateway4"/"Gateway4" and "Itential Gateway5"/"Gateway5" (never "IAG"). For actually building IAG5 services, use /iag.
argument-hint: "[working-directory]"
---

# IAG4 → IAG5 Readiness Assessment (iag4-to-iag5)

**Path:** Standalone analysis — not part of the delivery lifecycle. Sibling to `/iag`.
**Owns:** Identifying IAG4 usage across IAP + IAG4 assets and reporting the manual migration steps.
**Produces:** `<working-dir>/iag4-to-iag5-readiness.md` — one deterministic markdown report. All
pulled JSON, the auth cache, and scratch files go under `<working-dir>/tmp/` — never the
working-dir root. Only the report lives in the root.

## NON-NEGOTIABLE RULES (never break these)

These four rules override everything else. If following any other instruction would violate one of
them, STOP and ask the user instead.

1. **Strictly read-only on IAP and Gateway4.** No create/update/delete/import/patch — no
   state-mutating `POST/PUT/PATCH/DELETE`, no writing workflows/forms/projects/inventory/gateway
   assets. The ONLY write is the report (and read-cache JSON) in the working directory. Anything that
   would mutate a platform is recorded in the report as a manual action, never executed.
   **Gateway4 assets (scripts, playbooks, roles, inventory) come from ONE of two sources:** (a) a
   **local directory** in the working dir, or (b) **Gateway4's own HTTP API** when the user provides
   Gateway4 credentials (username/password) — read-only GETs only. Use whichever the user has; if
   neither, ask. **Never contact Gateway5, and never use `iagctl`** — `iagctl` is a Gateway5 CLI (it
   does not exist on Gateway4). Gateway5 is entirely out of scope and must never be contacted or
   mentioned to the user.
2. **Never make up information, and never contact Gateway5 directly.** Do NOT guess identifiers,
   task classifications, workflow/task references, adapter names, or the contents of anything you
   could not read. If something is unknown, ambiguous, or unreadable, **go back to the user to
   clarify** — do not invent, infer, or fill in a plausible value. The analyzer's
   `unresolved_children`/`warnings` exist precisely so unknowns are surfaced, not fabricated.
   Gateway5 is out of scope — never call it, `iagctl`, or any Gateway5 endpoint, and never mention it.
3. **Respect the scan scope absolutely.** When the user points you at a project or specific
   workflow(s) (anything other than an explicit `--all`), analyze ONLY that item **plus** any other
   workflow/project it (or its children) references via childJob — the transitive downward closure.
   Do NOT look at, pull, or report on anything else on the platform. Referenced children may live in
   the global space or in other projects; those are in scope only because they are referenced.
4. **Scoped pulls only, and support local-only.** Never bulk-pull the whole platform for a scoped
   run. Pull exactly the requested item, then follow references. If the user gives no API access (or
   asks to analyze only local files), run in **local-files-only mode** against the working directory
   — no API calls at all. When something referenced cannot be resolved (not pullable, not on disk),
   emit a **last-resort warning** in the report; never substitute a guess.

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

This skill is **read-only against IAP and Gateway4**. Its ONLY write target is the **working
directory** (the report, plus any pulled read-cache JSON).
- **Allowed:** IAP auth (`/oauth/token`, `/login`), IAP read/discovery **GET**s (workflows,
  json-forms, projects export, apps, adapters), the POST-based **devices read** if needed; Gateway4
  assets (scripts/playbooks/roles/inventory) from **either** a **local directory** the user supplies
  **or** read-only GETs against **Gateway4's HTTP API** when the user provides Gateway4
  username/password.
- **Forbidden:** any create/update/delete/import/patch on IAP or Gateway4 — no state-mutating
  `POST/PUT/PATCH/DELETE`, no editing/creating workflows, forms, projects, inventory, or gateway
  assets. **Never contact Gateway5 and never use `iagctl`** — `iagctl` is a Gateway5 CLI and does
  not exist on Gateway4; Gateway5 is out of scope (do not call it and do not mention it to the user).
  If a step *would* mutate a platform, **do not do it** — record it in the report as a manual
  action for the user.

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

**Ask these up front if the user did not already supply them** (use AskUserQuestion):

1. **Working directory** — where the report is written. If the user passed one as an argument,
   use it; else ask.
2. **Scan scope** — the workflow analysis (Step 2) is driven by one of three deterministic scopes.
   A scoped run is the DEFAULT; carry the choice into the script flag. The scope is the **seed** —
   the analyzer then follows childJob references DOWN into the transitive closure (rule 3), so a
   scoped run still covers every workflow the seed reaches, and **only** those:
   - **project(s)** → `--projects <id,id>` (recommended — one or more project ids)
   - **explicit workflow list** → `--workflows "Name A;Name B"`
   - **all workflows** → `--all` — **not recommended**: bulk-scans every workflow on the platform
     (e.g. 1504) and can overflow a small model's context window. Only use if the user explicitly
     asks. `--all` is the ONLY mode that pulls the whole platform; every other scope pulls just the
     seed + referenced children.
3. **Data source per platform.** There are TWO platforms this skill can read — **IAP** and
   **Gateway4** — and EACH can be sourced either **live (read-only HTTP API)** or **local files**.
   Ask the user (never assume); any combination is valid (IAP-only, Gateway4-only, or both; live,
   local, or mixed):
   - **IAP** — **live** (scoped read-only API pulls) or **local IAP JSON** (workflow/project/form
     exports already on disk), or none.
   - **Gateway4** — **live** (read-only GETs against Gateway4's HTTP API using the username/password
     the user provides) or a **local directory** of scripts/playbooks/roles/inventory, or none.
   - **Never** offer, ask about, or use `iagctl` or any Gateway5 endpoint — Gateway5 is out of scope
     (`iagctl` is a Gateway5 CLI and does not exist on Gateway4).
   - When a source is fully local, pass `--local` (and `--local-dir <dir>`) to the analyzer; it makes
     no API calls for that source. Anything referenced but not readable becomes a last-resort
     warning — never a guess.

Then establish the data sources:

4. **Never assume the source of assets.** Look for a `.env` in the working dir (the auth cache
   lives at `tmp/.auth.json`). A `.env` may carry **IAP** creds and/or **Gateway4** creds — check
   which it has; if its purpose is unclear, ask the user.
   - Confirm, for IAP and for Gateway4 independently, whether the user has **live** access
     (credentials for read-only API calls) or **local files**, or neither.
5. Establish each source (IAP, Gateway4) as `live` or `local`. **Local files take precedence** over
   live pulls when both exist. Record all of this for the report header (`Mode:` = live/local per
   source).

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

**Devices — for the Inventory check (read-only, POST is a query not a mutation). SCOPE-GATED.**
The device-origin check is **platform-wide**, so it runs ONLY under `--all` (or when the user
explicitly opts in). In a scoped `--projects`/`--workflows` run, and in local-only mode, **do not
pull devices** — it is outside the requested scope (rule 3); the report's Inventory device line then
renders "Skipped — outside scan scope." When it does apply: so the analyzer can tell whether
Configuration Manager devices are sourced from an IAG4 gateway adapter, pull the device list into
`tmp/devices.json`. `POST /configuration_manager/devices` is the "Find Devices"
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

**Workflows — pull ONLY what the scope needs (rule 4).** Never bulk-pull the whole platform for a
scoped run. How you pull depends on the Step-0 scope and data source:

- **Local-files-only mode** (no API): do NOT pull anything. The workflow/project-export/form JSON
  already in the working dir is the input. Skip straight to Step 2 with `--local --local-dir <dir>`
  (point `--local-dir` at wherever those files live, default `<working-dir>/tmp`).

- **`--projects <id,id>` (live):** export just those projects — read-only —
  `GET /automation-studio/projects/{id}/export`; take `components[]` where `type == "workflow"` and
  write each `document` as one ndjson line to `tmp/wf_all.ndjson` (also grab `type == "jsonForm"`
  components for the in-scope form scan). Stamp each doc's `namespace` with the project `{_id,name}`
  so location resolves correctly.

- **`--workflows "Name A;Name B"` (live):** fetch just those workflows by name (read-only), e.g.
  `GET /automation-studio/workflows?equals[name]=<name>` (or the list filtered to the names), and
  append each returned workflow doc as an ndjson line to `tmp/wf_all.ndjson`.

- **`--all` (live, NOT recommended — the only bulk mode):** paginate the full list (caps at 100/page;
  `?limit=500` silently returns only 100). Read `total`, loop `skip`, append each page's `items[]`:
  ```bash
  total=$(curl -s -H "$AUTH" "{BASE}/automation-studio/workflows?limit=1" | jq .total)
  # FAIL FAST: non-numeric total = auth failed (error body, not a workflows page). Do NOT proceed —
  # an empty pull yields a misleading all-zeros report. #1 cause: OAuth token sent as ?token= not header.
  case "$total" in ''|*[!0-9]*) echo "AUTH/PULL FAILED — workflows 'total' is not numeric ('$total'). Fix auth (OAuth token → Authorization: Bearer HEADER, not ?token=) and re-run." >&2; exit 1;; esac
  skip=0; : > tmp/wf_all.ndjson
  while [ "$skip" -lt "$total" ]; do
    curl -s -H "$AUTH" "{BASE}/automation-studio/workflows?limit=100&skip=${skip}" | jq -c '.items[]' >> tmp/wf_all.ndjson
    skip=$((skip+100))
  done
  lines=$(wc -l < tmp/wf_all.ndjson)
  [ "$lines" -eq "$total" ] || echo "WARNING: pulled $lines of $total — incomplete (likely mid-run token expiry); re-auth and re-run." >&2
  ```

**Closure loop (rule 3, live scoped runs only).** After the first analyzer run (Step 2), read
`analysis.json → unresolved_children`. For each referenced child workflow name not yet in the pool,
fetch it (by name; if it belongs to a project, export that project) and append to `tmp/wf_all.ndjson`,
then re-run the analyzer. Repeat until `unresolved_children` is empty **or** no source can resolve
what remains — anything still unresolved stays in `unresolved_children` and becomes a last-resort
report warning. This is how a scoped run legitimately reaches into other projects / the global space:
only via references, never by scanning the whole platform. In **local mode** there is no pull loop —
resolve children only from the local files; whatever is missing stays a warning.

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
# live scoped run:
python3 -B ${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/analyze_iag4.py \
  --tmp <working-dir>/tmp \
  { --projects <id,id>  |  --workflows "Name A;Name B"  |  --all }
# local-files-only run (no API): add --local (and --local-dir if the JSON isn't in tmp/):
python3 -B ${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/analyze_iag4.py \
  --tmp <working-dir>/tmp --local --local-dir <dir-of-workflow-json> \
  { --projects <id,id>  |  --workflows "Name A;Name B"  |  --all }
# writes <working-dir>/tmp/analysis.json
```

The script is **read-only** (its only write is `tmp/analysis.json`), needs no network/auth, and
consumes `tmp/{wf_all.ndjson,adapters.json,apps.json,json-forms.json}` (plus, in `--local` mode, any
`*.json` workflow/project-export files under `--local-dir`). A missing scope flag exits non-zero.

**Exit codes / failure handling:**
- In **live** mode, a `wf_all.ndjson` that is missing, empty, **or non-workflow** (rows that parse as
  JSON but carry no `tasks` object — the signature of a mid-pull auth failure that wrote error bodies
  like `{"message":"Unauthorized"}` into the ndjson) exits 2. This means the pull failed auth, NOT
  that there is no IAG4 usage; a genuinely IAG4-free platform still has real workflows WITH tasks.
  **If it exits non-zero, STOP — do not write a report and never report "0 workflows / 0 tasks" off a
  failed pull.** Fix auth (OAuth token → `Authorization: Bearer` header, not `?token=`), re-pull, re-run.
- In **`--local`** mode the script never hard-fails on missing data (that is the whole point — analyze
  what's on disk). If there are no workflow docs to read, it emits an empty report and a `warnings[]`
  entry; surface that warning to the user rather than pretending zero usage was confirmed.

Then **read `tmp/analysis.json`** — it contains `identifiers` (now incl. `adapter_display_names`),
`mode`, `counts`, sorted `workflows[]` (each with `interface`+`referenced_by` per task and a
`called_by` list), sorted `forms[]`, `devices`, an aggregated `checklist`, `unresolved_children`, and
`warnings`. Do not re-walk the workflows yourself; the JSON is authoritative for the report.

**New fields (render these — do NOT recompute):**
- **`interface`** (per Gateway4 task, req a) — `"AG Manager"` (AGManager application) or the ACTUAL
  adapter name (verbatim). This tells the user which Gateway5 cluster the task must map to.
- **`referenced_by`** (per Gateway4 task, req b) — other tasks in the SAME workflow that consume this
  task's output (`$var.<taskId>.…` or a `{"task":"<taskId>"}` job ref). Render as "used by: …".
- **`called_by`** (per workflow, req c) — the IN-SCOPE parent workflows that call this workflow via
  childJob. Only in-scope parents ever appear (rule 3).
- **`unresolved_children`** / **`warnings`** — referenced workflows that could not be read. Surface,
  never fabricate their contents (rule 2).
- **`workflow_groups[].n_workflows`** / **`n_tasks`** — per-group aggregate counts (workflow count
  and total Gateway4 task count in that project/Global group). Drives the new Workflows Summary
  table at the top of the Workflows section — render, do not recompute.

**What the script does (documented here so the report strings stay reviewable — the script is the
source of truth; do NOT hand-classify):**

*Workflows.* A task is an **IAG4 task** if its `app`/`location` matches the automation_gateway
adapter (type `AutomationGateway`, or a resolved instance id) or the `AGManager` app. It **never**
flags `GatewayManager` (IAG5). Each IAG4 task is classified from its name/summary/description into
exactly one row, with the verbatim recommendation the report prints:

| Detected IAG4 task | `iag4_type` label | Code | Short recommendation (verbatim) |
|---|---|---|---|
| **Device/group self-management** (add/remove/create/delete device(s) or group) — checked first | `self-management` | `INV` | move to the Inventory Manager application; use a device send-command / set-config task instead of the Gateway4 device operation |
| Playbook op — name/summary/description contains "playbook" | `ansible-playbook` | `REVIEW` | likely no code change — review how inventory is handled (Gateway5 has no built-in inventory) |
| Ansible collection-module task or role — name/summary/description contains "role"/"collection", or the task name is an FQCN (e.g. `cisco.ios_ios_command`); this is where `itential_cli`/`itential_set_config` land (their description is "Ansible Role") | `collection-or-role` | `WRAP` | wrap in a Python script or an Ansible playbook and run as a Gateway5 service, or replace with an Inventory Manager send_command/set_config task if that covers the same logic |
| **Everything else** — any other IAG4 op (`isAlive`, `runCommand`, `getDeviceConfig`, …) | `python-script` | `ARGS` | change positional args to named args (--flag / argparse); run as a Gateway5 python-script service |

*Interface, references, closure (the script also computes these — render, don't recompute):*
- **Interface (req a):** each Gateway4 task is tagged `interface` = `"AG Manager"` when it uses the
  AGManager application, else the actual `automation_gateway` adapter name it carries — so the user
  can map each task to the right Gateway5 cluster.
- **Task output references (req b):** `referenced_by` lists other tasks in the same workflow that
  consume the Gateway4 task's output (via `$var.<taskId>.` or a `{"task":"<taskId>"}` job ref).
- **Workflow references (req c):** `called_by` lists the in-scope parent workflows that call the
  workflow via childJob (`app == "WorkFlowEngine"`, `variables.incoming.workflow`).
- **Scope closure (rule 3):** the scope flag is a SEED; the script follows childJob edges DOWN to the
  transitive closure and analyzes only that set. Children it can't find in the pool land in
  `unresolved_children` — the skill's Step-1 closure loop pulls them (live) or they become a warning.

`python-script` is the default. The only questions this skill ever asks are the Step 0 pair
(working dir + scope), an unclear `.env` purpose (Step 0), or **unresolved IAG4 identifiers**
(empty/ambiguous `identifiers` block — Step 1b). Never ask how to classify a task.

**Project name — from the workflow's `namespace`, not the name prefix.** Project membership is
resolved from each workflow's authoritative `namespace` field (`{type:"project", _id, name}`), NOT
by parsing the `@<id>:` name prefix. A workflow is **in a project** (and the report shows the
project name) iff `namespace` marks it project-owned; otherwise it is **Global** — including
workflows whose name still carries a stale `@<id>:` prefix pointing at a deleted project (a bulk-
import leftover, not live membership). Each entry carries `location_type` (`global`/`project`),
`project_id`, `project_name`. Render location as plain `name (id)` for a project, else `Global`
(no special quoting/brackets around the name).
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

## Step 4 — Scan Gateway4 assets (local directory or Gateway4 HTTP API)

Only if Gateway4 is in scope. Read the assets from whichever source the user has (Step 0):
- **local directory** → read the files from disk; or
- **Gateway4 HTTP API** → read-only GETs against Gateway4 using the username/password the user
  provided (never a mutating call).

Never use `iagctl` or any Gateway5 endpoint (out of scope). If the user has neither a local dir nor
Gateway4 credentials, ask which they can provide; do not fabricate the asset list. Classify each
file/asset and attach the verbatim recommendation:

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

**(b) Gateway4 built-in inventory.** Base this ONLY on the Gateway4 source the user gave (local dir
or Gateway4 HTTP API GETs) — never on Gateway5. If Gateway4 was not in scope / no source provided,
say so and note the action generically ("if the Gateway4 gateway holds a built-in inventory, move it
to Inventory Manager"); if an inventory is present, same action; if there clearly is none, state
that. Whenever inventory could exist, add the checklist item: move it into the
**Inventory Manager** application in IAP; inventory variables can still be passed into Gateway5
scripts/playbooks at run time via IAP workflows. (Lightweight this version — deeper Inventory
Manager mapping guidance comes later.)

## Step 6 — Write the report

Fill `${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/readiness-report-template.md` and write
`<working-dir>/iag4-to-iag5-readiness.md` (the report is the **only** file in the working-dir
root — all pulled JSON and scratch stay in `tmp/`).

**Recommendations via short CODES + one static legend.** Each Gateway4 task carries a short
remediation code — **WRAP / REVIEW / ARGS / INV** — computed by the analyzer (`code` per task,
`codes` per workflow). Explain them ONCE in a static **Recommended Actions** legend section; the
Workflows tables show only the code (never the full sentence). The full recommendation text lives in
the legend and the end Manual Action Checklist. Codes are a best-effort classification from each
task's name/description — the legend says "review each", so this is honest guidance, not asserted
fact. Do NOT write the full recommendation sentence into the Workflows tables.

**Section order (fixed) + Table of Contents.** Render sections in this order: **Summary, Recommended
Actions, Workflows, JSON Forms, Scripts/Playbooks & Roles, Inventory, Recommended Repository
Structure, Manual Action Checklist** — the checklist is **last**, after the repo section. Immediately
under the header table, emit a `## Contents` table-of-contents with one linked entry per section
(GitHub-style anchors, e.g. `[Scripts, Playbooks & Roles](#scripts-playbooks--roles)`) so the reader
can jump around. **Nest the Workflows entry** with one sub-link per `workflow_groups[]` entry
(project/Global groups, same order as rendered), e.g.:
```
3. [Workflows](#workflows)
   - [Arista EOS (66d0da1721161b4df27174d0)](#arista-eos-66d0da1721161b4df27174d0)
   - [Global](#global)
```
Anchor = a plain GitHub slug of `group.label`: lowercase, drop any character that isn't a
letter/digit/space/hyphen (drops the parentheses), then spaces → hyphens. Do **not** nest down to
individual workflows — that would make the TOC unreadably long; the group's own index table already
lists each workflow with its ID.

**WORDING — the rendered report must NOT contain "iag"/"IAG4"/"IAG5" (req d).** Use "Itential
Gateway4"/"Gateway4" and "Itential Gateway5"/"Gateway5". Keep literal API/app names
(`GatewayManager.runService`, `AG Manager`) and the ACTUAL adapter names verbatim so the reader can
identify them on the platform. When you fill the template: (1) substitute every `{{placeholder}}`,
(2) **strip all `<!-- … -->` guidance comments** (they are for you, not the report), and (3) as a
final self-check, confirm the written report contains no case-insensitive "iag" —
`grep -i iag <working-dir>/iag4-to-iag5-readiness.md` must return nothing (the filename itself is not
part of the file's content). If it matches, fix the wording before telling the user it's done.

**Render the deterministic sections straight from `tmp/analysis.json`** — do not recompute:
- **Header** = a two-column key/value table (Generated, Working directory, Mode ← `mode`, Platform
  source, Gateway4 assets, Gateway4 matched ← `identifiers` (adapter type + instances; app label is
  always `AG Manager`), Scope ← `scope`).
- **Data-gap callout** — render a single `> **⚠ Data gap — N referenced child workflow(s) could not
  be analyzed.**` line (N ← `unresolved_children` length) **only if** that list is non-empty; it
  points the reader to the full list at the BOTTOM (Manual Action Checklist → General). Do NOT dump
  the list up here. Any `warnings[]` entries not about unresolved children render as extra
  `> **Warning:** …` lines. Never invent what a warned-about workflow contains (rule 2).
- **Summary** counts ← `counts` (`n_workflows`, `n_gw4_tasks` ← `counts.n_iag4_tasks`, `n_forms`,
  `n_gw4_devices` ← `counts.n_iag4_devices`), plus `n_unresolved` ← `unresolved_children` length.
- **Recommended Actions** — the static legend table (WRAP / REVIEW / ARGS / INV). Render the
  "Recommended action" cells VERBATIM from the template (they mirror the analyzer's `REC_BY_CODE`);
  do not reword. Include the "codes are a best-effort classification — review each" line.
- **Workflows** section ← `workflow_groups[]` (already ordered). **Grouped by location**: iterate
  `workflow_groups` (projects first by name, then a final `Global` group; workflows within each
  already name-sorted). Do NOT re-sort.
  - **Workflows Summary table** — render FIRST, right after the intro line and before the per-group
    breakdown: one row per group, `Project / Location | Workflows | Tasks to fix` =
    `` {group.label} | {group.n_workflows} | {group.n_tasks} ``, plus a final `**Total**` row from
    `counts.n_workflows` / `counts.n_iag4_tasks`. Straight from the analyzer's per-group aggregates —
    do not recompute.
  - **Group headline** — `### {group.label}` where `label` is plain `project_name (project_id)` for a
    project or `Global` (no special quoting/brackets around the name). The project/Global identity
    lives HERE, so it is **not** repeated below (no "Scope / Connector" column, no location in the
    detail heading — kills the repeated text).
  - **Per-group index table** — one row per workflow: `Workflow | Tasks | Interface(s) | Rec | ID` =
    `` `workflow_name` | n_tasks | interfaces | codes | `workflow_id` ``. `interfaces` ← distinct
    `interfaces` (task order) — factual `AG Manager` and/or adapter name(s), for cluster mapping.
    `codes` ← the workflow's distinct `codes` (CODE_ORDER) joined `, ` (e.g. `WRAP, ARGS`) — the
    short recommendation codes from the legend. **Always print `workflow_id`** — disambiguates clones.
  - **Detail section** (one per workflow) — `#### \`workflow_name\` · \`workflow_id\`` (no location)
    then a **4-col** table, one row per task: `Task | Name | Interface | Rec` = `` `task_id` |
    task_name | interface | code ``. `interface` (req a) is `AG Manager` or the actual adapter name
    (verbatim); `code` is the task's short remediation code (full text in the legend, NOT here).
  - **References** — collect the relationship lines in order: (1) if `called_by` (req c) non-empty,
    `` Called by `name` (`id`), … `` (in-scope parents only); (2) for each task whose `referenced_by`
    (req b) is non-empty, `` `task_id` output used by `id`, `id` ``. Zero lines → render nothing.
    Exactly one line → inline `**References:** <line>`. More than one → `**References:**` then a
    bullet per line. (This avoids the noise of a heading for a single fact.)
  - `label` is built by the analyzer; **never write "name unavailable"** — a stale `@id:` prefix is
    the `Global` group, not a project.
- **JSON Forms** section ← `forms[]` (already sorted): `**form_name** — field_key
  (`bound_endpoint`): rebind…`. Forms are matched on the **binding endpoint only**; a
  `/configuration_manager/...` field that filters by `adapterType` is NOT flagged (see Step 2).
- **Recommended Repository Structure** section (comes BEFORE the checklist) — tailor the
  template's fixed Options A/B/C + Naming Conventions to THIS environment's migrated services (the
  distinct `checklist.workflows` keys **plus** the Step 4 assets). **Option A (mono-repo) is ALWAYS
  the recommendation** — do not make it conditional on service count, and do not print any service
  counts anywhere in this section (no "small team / < 20 services" qualifiers on the option
  headings either). In the Option A tree, emit one leaf per service foldered by domain, each
  annotated `← was <original> (<iag4_type>)`. File layout by code/type: **ARGS** (python-script) and
  **WRAP** (collection-or-role) leaves become python services → `main.py` + `requirements.txt`;
  **REVIEW** (ansible-playbook) leaves → `playbook.yml`. **INV** (self-management) tasks are NOT
  services — they move to Inventory Manager, so **exclude them from the repo tree**. Fill the Naming
  Conventions
  "Examples" column with the actual service names mapped to `{team}-{domain}-{action}`. **Use
  placeholder team names `team1`, `team2`, … (one team per domain in B/C) — never assume real team
  names.** Domains are still derived from the services. Keep the option headings verbatim: `Option
  A — Mono-repo (recommended)`, `Option B — Multi-repo (per-domain ownership)`, `Option C —
  Service-file repo + code repos (separation of concerns)`. **Do NOT render a "See `/iag` …" line
  into the report** — that pointer stays here in the skill: for how to write `services.yaml`, the
  `--property_name` named-arg contract, `repositories:` config, and `GatewayManager.runService`
  wiring, defer to `/iag`.
- **Manual Action Checklist** — the **last** section — **grouped by item type**, each group under its
  own `###` subheading, in fixed order: **Workflows, JSON Forms, Scripts/Playbooks & Roles, Inventory,
  General**. **Render only groups that have items — drop an empty group entirely.**
  - **Workflows** ← `checklist.workflows` (already `{code, workflow_name, workflow_id, count}` sorted
    by code (WRAP, REVIEW, ARGS, INV) then workflow name/id). Grouped **by code**: render one `####`
    heading per code that has items — `#### {code} — {REC_BY_CODE[code]}` (the recommendation text
    appears ONCE per code heading, not per item) — then one line per workflow underneath: `` - [ ]
    `workflow_name` (`workflow_id`) — N task(s) ``. Skip a code heading entirely if it has no items.
    This tells the reader WHICH workflow needs the work, not just an environment-wide task-name total.
  - **JSON Forms** ← `checklist.forms`. **Scripts, Playbooks & Roles** ← the Step 4 assets.
  - **Inventory** ← flagged devices from `analysis.json → devices` — one `- [ ] \`device_name\` —
    origin \`origins\`` per device (name + origin only; the re-homing recommendation is stated once,
    already, in the Inventory report section above — do not repeat it here) plus the gateway
    built-in-inventory action (Step 5b); scoped/local run where devices weren't pulled →
    "Skipped — outside scan scope."
  - **General** ← cross-cutting items: a repo-setup item linking to the Recommended Repository
    Structure section (`Set up the Gateway5 service git repository — see [Recommended Repository
    Structure](#recommended-repository-structure) (Option A recommended)`) and a git-secret item.
    **THEN, if `unresolved_children` is non-empty, render the moved data-gap list here** under a bold
    label `**Unresolved child workflows — pull into scope (live) or add JSON to \`--local-dir\`, then
    re-run:**` with one `- [ ]` per name. This is the single place the full list lives (the top
    callout points here). Do NOT emit service counts.

The **Inventory** report section (not the checklist) renders the device-origin finding as a lead line
+ a single dot-separated list of device names (not one bullet each — that's the checklist's job);
sections with no findings get `No Gateway4 references found.`

Finally, tell the user the report path and give a one-paragraph headline of the counts. Note
that `tmp/` is read-cache/scratch and safe to delete.

**The skill's job ends here.** Once the report is written and its path/headline is given to the
user, STOP. Do not follow up with next-step suggestions, offers to convert/migrate/build anything,
or any other proactive recommendation — not even "would you like me to start building the
repository structure" or "I can convert script X now." If the user wants to act on the report,
they will say so and start a new, separate request (e.g. `/iag`); this skill never volunteers it.

---

## Gotchas

- **Read-only, always (rule 1).** Never mutate IAP or IAG. If a step would create/update/delete/
  import, don't — write it into the report as a manual action instead.
- **Never fabricate (rule 2).** If an identifier, classification, reference, adapter name, or
  workflow's contents can't be read, STOP and ask the user. Unknowns surface as
  `unresolved_children`/`warnings` — never a plausible guess.
- **Respect scope (rule 3).** A scoped run analyzes ONLY the seed + its transitive childJob
  closure. Never pull or report anything outside that set. `--all` is the ONLY whole-platform mode.
- **Scoped pulls + local-only (rule 4).** Don't bulk-pull for a scoped run — pull the seed, then
  follow references (closure loop). With no API, run `--local` against the working dir; unresolved
  references become a last-resort warning.
- **Report wording (req d).** The rendered report must contain no "iag"/"IAG4"/"IAG5" — use
  "Gateway4"/"Gateway5". Keep `GatewayManager.runService`, `AG Manager`, and actual adapter names
  verbatim. Strip template comments and `grep -i iag` the final report as a self-check.
- **`AGManager` (Gateway4) ≠ `GatewayManager` (Gateway5).** Two different applications. Flag
  `AGManager` (rendered as "AG Manager"); never flag `GatewayManager` — it is the Gateway5 target.
- **Interface tag drives cluster mapping (req a).** Each Gateway4 task's `interface` is "AG Manager"
  or the actual adapter name — this is what tells the user which Gateway5 cluster to map it to.
- **Adapter type vs instance.** A task's `app` is the adapter *type*; the instance name lives
  elsewhere. Resolve via `apps.json`/`adapters.json`; recognize both so you don't miss tasks.
- **OAuth token goes in the `Authorization: Bearer` header, NOT `?token=`.** `?token=` only
  works for local `/login` tokens. Sending an OAuth token as a query param returns "malformed
  token" — the #1 auth failure here.
- **`--all` paginates; scoped pulls don't.** The `workflows` list caps at 100/page — only the
  `--all` bulk pull loops on `total`. Scoped runs pull via project export / by-name instead.
- **Static dropdowns are not a concern.** Only `binding: true` REST-bound dropdowns can point at Gateway4.
- **The script owns workflow + form classification — never hand-classify.** `analyze_iag4.py`
  emits `python-script` as the default and computes interface/refs/closure. Only *unresolved
  identifiers* (empty `identifiers` block — Step 1b), an *unclear `.env` purpose*, or the *Step 0
  working-dir/scope/source questions* warrant a question — never the per-task approach or the source.
- **Keep the recommendation strings in sync.** They live once as constants in
  `helpers/iag-migration/analyze_iag4.py` and must match `readiness-report-template.md`
  verbatim. Change them in both places or determinism breaks.
- **Ask working dir + scope + data source first.** If not supplied, ask up front (Step 0). Warn that
  `--all` can overflow a small model's context on large platforms.
- **Identification only.** Do not create Gateway5 services, edit workflows, or rewrite scripts here.
  Route actual builds to `/iag`.
- **Done means done.** The skill's only deliverable is the report. Once it's written, stop — no
  follow-up suggestions, no offering to convert scripts, build the repo, or do anything else
  automatically, even if it seems helpful. Let the user initiate any next step explicitly.

## See also
- `/iag` — building IAG5 service(s) (Python/Ansible/OpenTofu), service YAML, `runService` wiring.
- `/itential-inventory` — Inventory Manager, the IAG5 replacement for gateway inventory.
- `/itential-json-forms` — REST-bound dropdown structure and `bindingSchema`.
- `/explore` — auth + IAP pull mechanics reused in Step 1.
- Analysis script: `${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/analyze_iag4.py` (Step 2, deterministic).
- Template: `${CLAUDE_PLUGIN_ROOT}/../../../helpers/iag-migration/readiness-report-template.md`.
