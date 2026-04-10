# Itential Platform - AI Agent Guide

This project contains skills for assisting developers on the Itential Platform. Read this first, then use the skills for detailed API references.

## Skill Router

Each skill owns a domain. **Invoke the skill using the Skill tool before working in that domain.** Skills contain the correct API methods, request bodies, response shapes, and patterns. Don't guess — load the skill.

| Skill | Agent | When to Use |
|-------|-------|-------------|
| `/explore` | — | Explore a platform freely — auth, discover, browse, build freestyle. |
| `/spec-agent` | **Spec Agent** | Start a delivery from a spec. Owns Requirements stage. |
| `/project-to-spec` | — | Read an existing project → produce customer-spec.md + solution-design.md. |
| `/documentation` | — | Document any asset (workflows, golden config, LCM, all globals, etc.) → accept specific names/IDs or all globals, discover relationships, group by use case, produce HLD+LLD per use case. Delegates projects to `/project-to-spec`. |
| `/flowagent-to-spec` | — | Read a FlowAgent → produce customer-spec.md as a deterministic workflow spec. |
| `/solution-arch-agent` | **Solution Architecture Agent** | Feasibility assessment + solution design. Runs after Requirements. |
| `/builder-agent` | **Builder Agent** | Build all assets, run tests, produce as-built record. |
| `/iag` | — | Automation Gateway: IAG services (Python, Ansible, OpenTofu). |
| `/flowagent` | — | AI Agents: configure LLM providers, tools, missions. |
| `/itential-mop` | — | Command templates with validation rules. |
| `/itential-devices` | — | Devices, backups, diffs, device groups. |
| `/itential-golden-config` | — | Golden config, compliance, grading, remediation. |
| `/itential-inventory` | — | Device inventories, nodes, actions, tags. |
| `/itential-lcm` | — | Resource models, instances, lifecycle actions. |

### Delivery Lifecycle

Spec-based delivery follows five stages. Each stage has a named agent, a clear input, and a deliverable.

```
Requirements  →  Feasibility  →  Design  →  Build  →  As-Built
      │                │              │          │           │
  Spec Agent   Solution Architecture  Solution   Builder     Builder
                     Agent           Architecture Agent       Agent
                                      Agent
      │                │              │          │           │
  customer-        feasibility.md  solution-    assets/    as-built.md
  spec.md          (assessment     design.md    configs    (delivered state,
  (approved)       + decision)     (approved)  (delivered)  deviations,
                                                            learnings)
                                                           ↳ design updates
                                                           ↳ spec amendments
```

**Deliverables:**

| Deliverable | Artifact | Produced by | Audience |
|-------------|----------|-------------|----------|
| HLD | `customer-spec.md` | Spec Agent | Customer / stakeholder |
| Feasibility Assessment | `feasibility.md` | Solution Architecture Agent | Customer / architect |
| Solution Design / LLD | `solution-design.md` | Solution Architecture Agent | Engineer / delivery team |
| As-Built | `as-built.md` | Builder Agent | Customer / delivery / support / system of record |

**Explore path** (no spec, no delivery lifecycle):
```
/explore → auth → pull platform data → summarize → use skills directly
```

**IMPORTANT: Invoke skills using the Skill tool** — don't just reference them in text. When you need to build workflows/templates, invoke `/builder-agent`. The skills contain the API details you need. Without loading them, you're guessing.

### Auth Reuse — Authenticate Once, Reuse Everywhere

**Auth happens when first needed** — in `/explore` (explore path) or in `/solution-arch-agent` during Feasibility. The token is saved to `{use-case}/.auth.json`. Every subsequent skill should:
1. Read `{use-case}/.auth.json` for `platform_url`, `auth_method`, and `token`
2. Use the token for all API calls (Bearer header for OAuth, query param for local)
3. On auth error (401/403): re-authenticate silently — see procedure below
4. **Never ask the user for credentials if `.env` exists**

This means the user authenticates once and every subsequent skill just works.

**Token expiry — silent re-auth procedure:**

When any API call returns 401 or 403, do not stop and do not ask the user. Re-authenticate silently:

1. Read credentials from `{use-case}/.env` (or `${CLAUDE_PLUGIN_ROOT}/environments/*.env` if no use-case `.env`)
2. Call the appropriate auth endpoint:
   - **OAuth:** `POST {PLATFORM_URL}/oauth/token` with `Content-Type: application/x-www-form-urlencoded` and body `grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}`
   - **Local/password:** `POST {PLATFORM_URL}/login` with `{"username": "...", "password": "..."}`
3. Write the new token back to `{use-case}/.auth.json`
4. Retry the failed request with the new token

If `.env` does not exist and re-auth is needed, then and only then ask the user for credentials.

### Key Rule: Look Up Before You Act — Don't Guess

**Skills** teach patterns, workflows, and know-how (how to build a childJob, how to wire variables, how to test).

**`openapi.json`** has every endpoint, method, request body, and response schema. Pull it locally if not already present, then search — never guess.

**How to get it:**
```bash
# OAuth (cloud)
curl -s "{BASE}/help/openapi?url={ENCODED_BASE}" -H "Authorization: Bearer {TOKEN}" > openapi.json

# Local dev
curl -s "{BASE}/help/openapi?url={ENCODED_BASE}&token={TOKEN}" > openapi.json
```
For explore mode, `/explore` pulls this automatically. For spec mode, `/solution-arch-agent` pulls it during Feasibility. If you're working outside those flows, fetch it yourself.

**Before making any API call:**
1. Check the relevant skill for the pattern
2. Search `openapi.json` locally to confirm the endpoint, method, request body, and response schema — `jq '.paths["/the/endpoint"]'`
3. **Check the body wrapper** — most Itential APIs wrap the body in a top-level key. Find it: `jq '.paths["/the/endpoint"].post.requestBody.content["application/json"].schema.properties | keys'` → returns the wrapper name (e.g., `["role"]` means `{role: {...}}`)
4. Never hardcode API assumptions — the spec is the source of truth

**Before fetching task schemas:**
1. Check if `{use-case}/task-schemas.json` exists — search it first with `jq` or `grep`
2. Only call `multipleTaskDetails` for tasks NOT already in the local file
3. After fetching, always append to the local file so future lookups are instant

**Before parsing any local JSON file:**
1. Check the response shape first — `jq type` and `jq keys` on the file
2. The `/solution-arch-agent` skill has a file-to-shape table — use it
3. Key shapes to remember:
   - `adapters.json` → `{"results": [...]}`
   - `applications.json` → `{"results": [...]}`
   - `devices.json` → `{"list": [...]}`
   - `workflows.json` → `{"items": [...]}`
   - `apps.json` → plain array `[...]`
   - `tasks.json` → plain array `[...]`
4. Use `jq` for parsing, not inline Python scripts with isinstance fallbacks

**When something fails or returns unexpected data — check local files FIRST:**
1. **`openapi.json`** — verify the endpoint exists, check the method (GET vs POST), read the request body schema and response schema. This file has EVERY endpoint, field, and type. Don't guess what a payload looks like — look it up.
2. **`tasks.json`** — verify the task name, app, location. If a task is "not found," search here first.
3. **`task-schemas.json`** — if you already fetched schemas, the full input/output definition is here. Check field names, types, required vs optional.
4. **`adapters.json` / `apps.json`** — verify adapter instance names, app names, casing. Adapter names from `apps.json` (type name) differ from `adapters.json` (instance name).
5. **`job.error` array** — for runtime errors (not just task status)
6. **Actual task output** — `status: complete` doesn't mean the CLI commands worked

**The filesystem is your debugger.** Every API endpoint, every task schema, every adapter name is already saved locally after setup. Never guess a payload structure, field name, or endpoint path — the answer is in these files. Reading a local file costs zero API calls and zero time.

## Understanding User Intent

Figure out which **category of work** the user needs:

- **Building** — create something new (workflow, template, compliance standard). Start with requirements, then build.
- **Operating** — do something now (configure a device, run compliance, backup configs). Identify targets and execute.
- **Exploring** — understand what's available (devices, adapters, workflows). Discover and navigate.
- **Debugging** — something broke (workflow failing, adapter errors). Get job details, check `job.error`.
- **Designing** — planning architecture (modular workflows, compliance hierarchy). Think before building.

## Developer Flow

Five stages. Three agents. Each stage has a named agent, a clear input, and a deliverable. Nothing moves forward without the engineer's sign-off at each stage.

```
Requirements  →  Feasibility  →  Design  →  Build  →  As-Built
      │                │              │          │           │
  /spec-agent    /solution-        /solution-  /builder-  /builder-
                  arch-agent        arch-agent   agent      agent
      │                │              │          │           │
  customer-        feasibility.md  solution-    assets/    as-built.md
  spec.md          (approved)       design.md   configs    (approved)
  (approved)                        (approved)
```

**Stage summaries:**

| Stage | Agent | What happens | Engineer does |
|-------|-------|-------------|---------------|
| Requirements | `/spec-agent` | Refines use case, defines scope, structures HLD | Approves `customer-spec.md` |
| Feasibility | `/solution-arch-agent` | Connects to platform, assesses capabilities, flags constraints | Approves `feasibility.md` |
| Design | `/solution-arch-agent` | Produces component inventory, adapter mappings, build plan | Approves `solution-design.md` |
| Build | `/builder-agent` | Builds all assets, tests each component, delivers | Reviews and accepts delivery |
| As-Built | `/builder-agent` | Records delivered state, deviations, learnings | Signs off on `as-built.md` |

**For explore / freestyle work:**
```
/spec-agent → auth → pull platform data → use skills directly
```

## Key Rules

1. **Never invent task names** — always look them up from `tasks/list`
2. **Always get the schema before building** — `multipleTaskDetails?dereferenceSchemas=true`
3. **Adapter `app` AND `locationType` fields come from `apps/list`**, not `tasks/list` (names can be completely different, not just casing). The `app` field is the adapter **type name** (e.g., `EmailOpensource`), NOT the adapter **instance name** (e.g., `email`). Using the instance name causes `"No config found for Adapter"` errors. Resolve from local `apps.json` and `adapters.json`. When multiple adapter apps exist for the same product, ask the user.
4. **Test each piece individually** before composing into a larger workflow
5. **Check `job.error` for failures**, not just task status
6. **Variable syntax differs by context:**
   - Jinja2 templates: `{{ var }}`
   - Command templates / makeData: `<!var!>`
   - Workflow wiring: `$var.job.x`
   - childJob variable refs: `{"task": "job", "value": "varName"}`
   - merge/evaluation refs: `{"task": "job", "variable": "varName"}` (NOT `"value"` — different field than childJob)
7. **Validation errors = draft workflow** that cannot be started
8. **`$var` references don't resolve inside object values** (e.g., inside `newVariable` value or adapter `body`) — use `merge`, `makeData`, `query`, or other utility tasks to build the object, then pass it as a top-level `$var` reference
9. **Task IDs are hex-only** — `[0-9a-f]{1,4}`. Non-hex IDs (e.g., `apush`) cause `$var` references to silently fail (classified as static, never resolved)
10. **`genericAdapterRequest` prepends the adapter's `base_path`** to `uriPath` — don't include `/api/v1` in `uriPath`. Use `genericAdapterRequestNoBasePath` if you need the full path
11. **Use `POST /projects/import` to create projects atomically** — build all assets locally, pre-compute the project `_id`, pre-wire childJob `@projectId:` refs, then import everything in one call. Avoid the create-then-move pattern (breaks childJob refs, causes project-locking issues).
12. **API response shapes vary** — projects use `{message, data, metadata}`, but workflow and template lists use `{items, skip, limit, total}`, and create endpoints return `{created, edit}`. Always check the response shape before parsing
13. **Project component types** — valid values: `workflow`, `template`, `transformation`, `jsonForm`, `mopCommandTemplate`, `mopAnalyticTemplate`
14. **Use skills, don't reimplement** — `/builder-agent` covers projects, workflows, templates, MOP, and testing. Only load other skills for their specific domains (IAG, FlowAgent, MOP, etc.)
15. **When unsure about ANY endpoint, method, or payload — check `openapi.json` FIRST.** Run `jq '.paths["/the/endpoint"]' {use-case}/openapi.json` to see the method, request body schema, and response schema. Don't guess, don't try variations, don't make up field names — look it up. The spec is always right.
16. **If `openapi.json` is not local, fetch it** — `GET /help/openapi?url={ENCODED_BASE}` and save it. Then search locally.
17. **If the openapi schema is empty for an endpoint** — check the corresponding POST/PUT endpoint's schema for the wrapper pattern. As a last resort, send `{}` and read the `"Missing Params"` error — it lists every required field with name, type, and examples.
18. **Endpoint base paths differ** — task catalog is at `/workflow_builder/tasks/list`, but task schemas are at `/automation-studio/multipleTaskDetails` (NOT `/workflow_builder/multipleTaskDetails`). Don't mix them up.
19. **Error transitions are mandatory on adapter/external tasks** — without an error transition, task errors produce "Job has no available transitions" and the job gets stuck forever. Always add `"state": "error"` transitions on tasks that call adapters or external systems.
20. **Adapter responses are transformed** — adapters reshape the upstream API response. Don't assume the native API's response structure (e.g., ServiceNow `result.sys_id`). Call the adapter endpoint directly or check `openapi.json` to verify the actual response shape before wiring query paths.
21. **Duplicate transition keys to same target** — JSON doesn't allow two keys with the same name. If a task needs both `success` and `error` to reach `workflow_end`, create an error handler task (e.g., `newVariable` to set error status) and route error there, then route that task to `workflow_end`.
22. **Respect task schema data types** — When wiring task inputs, match the type from `task-schemas.json` exactly. If a field is typed as `array`, pass an array (e.g., `["joksan@example.com"]`), not a bare string. If typed as `number`, pass a number, not a string. Common offenders: `to`/`cc`/`bcc` in email tasks (arrays, not strings), `pageSize`/`page` in queries (numbers, not strings). Mismatched types cause silent failures or validation errors.
23. **Adapter `app` ≠ adapter instance name** — The `app` and `locationType` fields on adapter tasks must be the adapter **type name** from `apps.json` (e.g., `EmailOpensource`, `Servicenow`), NOT the adapter **instance name** from `adapters.json` (e.g., `email`, `servicenow-prod`). Using the instance name causes `"No config found for Adapter: <name>"` at runtime. The `adapter_id` field is where the instance name goes. Triple-check: `app` = type, `adapter_id` = instance.
24. **Project-scoped asset names** — once an asset is added to a project, its `name` is prefixed with `@{projectId}: `. When reading or updating a project-owned asset via PUT, you MUST use the scoped name or the API returns 400. Read the asset first to get its current name, or construct it as `@{projectId}: {displayName}`. Strip this prefix when displaying names to the user.

## Helper JSON Templates

**ALWAYS start from a helper template when creating assets.** Read the helper file first, then modify it for your use case. Do NOT build JSON from scratch — the helpers have the correct structure, field names, and wrappers.

Helper templates are in `helpers/`:

| File | Purpose |
|------|---------|
| `create-workflow.json` | Workflow scaffold with start/end tasks |
| `workflow-task-adapter.json` | Adapter task template |
| `workflow-task-application.json` | Application task template |
| `workflow-task-childjob.json` | childJob task template (actor: "job") |
| `workflow-task-query.json` | Query/extract data task (json-query syntax) |
| `workflow-task-newvariable.json` | Create job variable task |
| `workflow-task-transformation.json` | JST transformation task (tr_id + variableMap) |
| `workflow-task-gettime.json` | Get current time task |
| `workflow-task-evalresult.json` | Evaluation/branching task (operand_1/operand_2) |
| `create-command-template.json` | Command template with `<!var!>` syntax |
| `create-template-jinja2.json` | Jinja2 template |
| `create-template-textfsm.json` | TextFSM template |
| `create-json-form.json` | JSON form for user input |
| `update-json-form.json` | Update an existing JSON form (full replacement) |
| `create-ops-manager-automation.json` | Operations Manager automation |
| `create-ops-manager-trigger.json` | API endpoint trigger |
| `create-ops-manager-trigger-manual.json` | Manual/form trigger (legacyWrapper: false) |
| `create-ops-manager-trigger-schedule.json` | Scheduled/cron trigger |
| `create-lcm-resource-model.json` | LCM resource model with lifecycle actions |
| `create-integration.json` | Virtual integration (adapter instance) |
| `create-project.json` | Project creation |
| `add-components-to-project.json` | Add assets to project |
| `import-project.json` | Import a project |
| `update-project-members.json` | Update project membership |
| `create-golden-config-tree.json` | Golden config tree |
| `create-golden-config-node.json` | Child node |
| `update-node-config.json` | Node template with full syntax |
| `add-devices-to-node.json` | Assign devices to a golden config node |
| `create-compliance-plan.json` | Compliance plan |
| `run-compliance-plan.json` | Run compliance plan |
| `run-compliance.json` | Run compliance directly |
| `update-command-template.json` | Update command template (full replacement) |
| `lcm-action-workflow.json` | LCM action workflow (must output `instance` variable) |
