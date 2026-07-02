---
name: flowagent
description: Create and run AI agents on the Itential Platform (Agent Project Service, Model Registry Service, Tools Service, Agent Session Manager). Agents use LLMs to autonomously call platform tools (adapters, workflows, IAG services) to complete objectives. Use when setting up agents, configuring LLM provider profiles, managing tools and decorators, or running/tracking agent sessions.
argument-hint: "[action or agent-name]"
---

# FlowAI - Agent Skills Guide

FlowAI lets you create AI agents that use LLMs (Anthropic, OpenAI, Google, Ollama, AWS Bedrock, Databricks, or platform-managed models) to autonomously operate the Itential Platform. Agents can call adapters, run workflows, and invoke IAG services — all driven by natural language instructions and a typed input contract.

**This skill documents six services**: **Agent Project Service** (projects + agents), **Model Registry Service** (LLM provider profiles + models), **Tools Service** (tools + decorators), **Agent Session Manager** (running and tracking agents), **Agent Execution Engine** (internal execution kernel — not called directly), and **Tool RPC** (tool-call execution tracking). Human-in-the-loop approval is handled by a separate WorkCenter Service — see Work Items in the API Reference below.

**Response schema caveat:** several endpoints (notably most of Agent Project Service and the Tools Service) declare their success response as a bare `{"type": "object"}` in the OpenAPI spec — the exact response field names are not formally typed. Where this skill states a response shape, it's inferred from request-body schemas, the project-bundle export format (which IS fully typed), or cross-referenced fields — not guessed. Treat every shape and JSON example below as a known-good working structure, not a guarantee that matches your platform version exactly.

## Verifying This Skill Against Your Platform

This skill is a map, not a substitute for checking the live API. Don't hardcode a field name or endpoint from memory when you can look it up in seconds:

- **Pull the real spec and search it locally.** `GET /help/openapi?url={ENCODED_BASE}` (or reuse an already-pulled `openapi.json`), then `jq '.paths["/agent-project-service/agents/{agentId}"]' openapi.json`. The services in this skill live under `/agent-project-service`, `/model-registry-service`, `/tools`, `/agent-session-manager`, `/tool-rpc`, and `/work-center-service` — filter on those base paths.
- **Get a tool's live schema instead of assuming it.** `GET /tools/{referenceId}` always returns that tool's current `inputSchema` exactly as the LLM sees it — adapters and app methods change independently of this skill, so this call is the one source that's always current.
- **When the OpenAPI spec itself is untyped, call the endpoint and read the real response** rather than trusting a shape in this skill as final — every response shape documented below was built that way, and your platform version may have moved on.
- **Prefer real exported structures over hand-authored JSON.** `GET /agent-project-service/project-bundles/{projId}/export` on any existing project returns a complete, valid Agent + Project payload straight from the platform — exporting something that already works and reading it is faster and more reliable than composing a bundle from memory. Two ready-made local references follow the same idea:
  - `helpers/create/create-flowagent-project-bundle.json` — a structurally-correct starting template with `REPLACE_*` placeholders. Edit and import it rather than typing a bundle out from scratch.
  - `helpers/assets/flowagent-sample-agent-project.json` — a real project bundle, exported after building and running it against a live platform: one project with three agents, including a multi-tool agent that calls a device command, opens a ServiceNow incident through a decorated tool, and presents a WorkCenter approval step. It's exact platform data, not a hand-written example — but it's still one specific environment's snapshot: its `referenceId`s, `decoratorId`, and `provider` names won't exist on your platform verbatim. Read it to see the real shape (in particular, how `{{ deviceName }}` in `instructions` lines up with `inputSchema`, and how `tools[].decoratorId` attaches), then re-resolve every ID against your own `GET /tools` and `GET /model-registry-service/profiles` before reusing it.

## Concepts

- **Project** — the top-level container that owns agents. GBAC-controlled (`owner`/`editor`/`viewer` roles via `members`). Agents cannot exist outside a project. Supports portable bundle import/export.
- **Agent** — a named AI entity: `instructions` (system prompt), a typed `inputSchema` (what parameters it accepts), a `provider` reference (which LLM profile + model it uses), a `tools` list, and an `operators` access list.
- **Profile** — a configured, credentialed instance of an LLM provider (e.g., "Production Anthropic"). Owned by Model Registry Service. Holds masked credentials and a curated list of enabled models, each with its own UUID.
- **Model** — one specific model enabled on a profile (e.g., a Claude or GPT model), addressed by a UUID assigned when it's added to the profile. An agent's `provider` field is `{profile: <uuid>, model: <uuid>}` — both required together.
- **Tool** — a callable platform capability (adapter method, IAG service, app method), addressed by a structured `referenceId` (`<type>:<source>:<method>`, e.g. `application:ConfigurationManager:runCompliancePlan`). Discovered via `POST /tools/discover`, never created by hand.
- **Decorator** — a standalone, ID-addressed override of a tool's description and input schema for a specific use case. Cloneable and portable (bulk export/import). An agent attaches a decorator to a specific tool reference, not globally.
- **Session** — a single run of an agent. Has an 8-state lifecycle (`PENDING` → `RUNNING` → `COMPLETE`/`FAILED`/`CANCELED`, plus `PAUSING`/`PAUSED`/`CANCELING`) and a typed activity log (`messages`).
- **Operators** — an agent-level access-control list (account/group IDs) granting specific callers the right to run that agent, independent of their project role. Only project owners can edit it.
- **Builder Groups** — a profile-level access-control list controlling which groups can build agents against a given LLM profile.
- **Work Item** — a human-in-the-loop task, created when an agent calls a `view`-type tool (e.g. `view:WorkCenter:QuickForm`). Lives in a separate WorkCenter Service (`/work-center-service/*`), not the Tools Service. The agent's tool call sits at `status: "pending"` until a person completes the work item.

## Gotchas

- **`inputSchema` only allows `string`/`number` property types**, requires `additionalProperties: false`, and validates session `inputs` at start time — a session start with inputs that don't match returns a validation error, not a soft failure inside the agent run.
- **Every declared `inputSchema` property MUST be used in `instructions`.** `instructions` isn't just a static system prompt — it's a template, and `inputSchema` properties are substituted into it as `{{ propertyName }}` at session-start time. Declaring a property and never referencing it fails agent create/update with `"'<name>' is defined in schema but not used in template"`.
- **Agent create vs. update field asymmetry:** `instructions`/`inputSchema` are top-level on create, but nested under `prompt` on `PATCH`. Tool changes are a full array on create (`tools`) but deltas on update (`addTools`/`removeTools`/`decorateTools`/`authorizeTools`).
- **`provider.profile` and `provider.model` are two separate UUIDs, both required together** (`additionalProperties: false` — no inline API key, temperature, or other override at the agent level; all of that lives on the Profile).
- **Profile credentials are always masked on read** (`credential.masked: true`) — there's no way to retrieve a saved secret via the API, by design.
- **Provider type is immutable on a profile once created.** To switch providers, create a new profile and repoint agents at it — `GET /model-registry-service/profiles/{id}/agent-impact` first to see what breaks.
- **Deleting a profile is irreversible (hard delete)** — always check `agent-impact` first.
- **Deleting a project cascades to every agent inside it** — no soft-delete/recovery.
- **Updating an agent's `operators` requires the owner GBAC role**, even though other agent fields only need editor — a common source of unexpected 403s.
- **`operators` grants operate-access only — it does not configure what identity the agent's tool calls run as.** That's a separate concern, not set on the agent definition itself.
- **Decorators replace the ENTIRE tool input schema**, not just the fields you specify. Omitting a required field means the agent will never send it, and the underlying adapter call fails with a schema validation error. Always test the tool directly first to enumerate every required field.
- **`agentSnapshot` on a session is frozen at session-start time.** Editing the agent afterward does not change what an already-running or already-completed session executed.
- **Tool execution is asynchronous and externalized internally**, but a fast tool call still completes and shows up fully resolved in `messages` within seconds in practice — the async/receipt pattern is an internal implementation detail, not something that makes results harder to read via the session API. If a session does seem stuck mid-tool-call, check `GET /tool-rpc/executions?status=running`.
- **Generic WorkFlowEngine utility tasks (merge, query, getTime, etc.) are not discoverable as tools.** `POST /tools/discover` only registers adapter methods, app methods, workflows, and IAG gateway services — a task existing in `tasks.json` doesn't mean it's addressable as a tool `referenceId`. If you need simple platform-level info, look for it via an app method (e.g., `application:ConfigurationManager:*`) instead.
- **No bulk session delete.** You must delete sessions one at a time.
- **No documented ad-hoc/ephemeral agent capability.** Every session-start path requires a saved `agentDefinitionId` — there is no "run this agent definition once without saving it" endpoint.
- **`run-agent`'s HTTP response is not the final answer** — it returns `{sessionId, status}` immediately just like plain `sessions` start. The "wait for the result" behavior only happens through the `terminationCallbackSignature` mechanism at the workflow-engine layer, not by blocking the HTTP call.
- **Most Agent Project Service and Tools Service responses are untyped in the OpenAPI spec** (`{"type":"object"}`). Verify exact field names against a live call before hardcoding a `$var` path in a workflow task.
- **A session stuck in `RUNNING` may just be waiting on a human.** The session's own `status` never enters a distinct "awaiting input" state — check `GET /work-center-service/work-items?rootExecutionId=<sessionId>` before assuming it's stuck. See Work Items below.

### Quick fixes for common problems

| Problem | Cause | Fix |
|---------|-------|-----|
| Tool execution fails | Wrong parameters | Test the tool directly (see Tools below), check openapi for correct inputs, update `instructions` or add a decorator |
| Agent calls wrong tool | Unclear objective | Be more specific in `instructions` about what to do and when |
| Agent loops (`iterationCount` high) | Too many tools or vague instructions | Reduce the `tools` array, add step-by-step guidance in `instructions` |
| Session input validation error | Inputs don't match `inputSchema` | Check `required`/`properties`/`additionalProperties` — only `string`/`number` types allowed |
| Agent create/update rejected: "defined in schema but not used in template" | An `inputSchema` property isn't referenced in `instructions` | Add `{{ propertyName }}` somewhere in `instructions`, or remove the unused property |
| Agent doesn't use a tool | Tool not in `tools` array or instructions don't mention it | Add the tool's `referenceId`, mention it by purpose in `instructions` |
| Session stuck in `PENDING`/`RUNNING` | Long-running tool call, a stuck external tool executor, or a pending human-in-the-loop task | Check `GET /work-center-service/work-items?rootExecutionId=<sessionId>` before assuming it's stuck; if genuinely stuck, `POST /agent-session-manager/sessions/{sessionId}` with `{"action":"CANCEL"}` |
| High token usage | Agent is exploring too many options | Constrain with "use ONLY these tools, in this order" in `instructions` |

---

## API Reference

### Projects (Agent Project Service)

**Base path:** `/agent-project-service`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agent-project-service/projects` | List projects (`limit`, `skip`, `sort`: name\|created\|lastUpdated, `order`: 1\|-1, `search`) |
| POST | `/agent-project-service/projects` | Create a project |
| GET | `/agent-project-service/projects/{projId}` | Get a project (`projId` = UUID `_id` or integer `iid`) |
| PATCH | `/agent-project-service/projects/{projId}` | Update name/description/members |
| DELETE | `/agent-project-service/projects/{projId}` | Delete a project **and all agents within it** — requires owner role |
| GET | `/agent-project-service/admin/projects` | Admin: list all projects, bypassing GBAC |
| PATCH / DELETE | `/agent-project-service/admin/projects/{projId}` | Admin: update/delete any project, bypassing GBAC |

**Create:**
```json
{ "name": "Network Operations", "description": "..." }
```
`name`: 1–100 chars, no leading/trailing whitespace. `description`: max 500 chars. Creator defaults to sole `owner`.

**Update membership:**
```json
{
  "members": [
    { "type": "account", "reference": "<24-char-hex-account-id>", "role": "owner" },
    { "type": "group", "reference": "<24-char-hex-group-id>", "role": "editor" }
  ]
}
```
Roles: `owner` | `editor` | `viewer`. **Only owners can update `members`.** This is a full field replacement per the PATCH body shape (only send what you're changing — `name`, `description`, `members` are each independently optional, but if you send `members` at all, send the complete list).

### Project Bundles (Import/Export) — the preferred way to create a project + agents together

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agent-project-service/project-bundles/{projId}/export` | Export a project and all its agents as a portable bundle |
| POST | `/agent-project-service/project-bundles/import` | Import a bundle to create (or merge into) a project |

**Prefer this over individual `POST /projects` + `POST /projects/{projId}/agents` calls** when creating a project with one or more agents — same rationale as Automation Studio's project import: build the whole thing locally, import atomically, avoid multi-call intermediate state.

**Bundle shape** (`agentProjectBundleVersion: 1`):
```json
{
  "_id": "<project-uuid>",
  "name": "NERC Compliance",
  "description": "Runs NERC-CIP compliance plan, collects device violations, ...",
  "agentProjectBundleVersion": 1,
  "created": "2026-07-01T13:59:16.070Z",
  "createdBy": { "provenance": "CloudAAA", "username": "joksan.flores@itential.com" },
  "agents": [
    {
      "_id": "<agent-uuid>",
      "name": "NERC CIP Compliance",
      "description": "",
      "instructions": "You are a NERC-CIP compliance automation engineer...",
      "inputSchema": {
        "type": "object",
        "additionalProperties": false,
        "required": ["device"],
        "properties": { "device": { "type": "string" } }
      },
      "created": "2026-07-01T14:09:15.000Z",
      "createdBy": { "username": "joksan.flores@itential.com", "provenance": "CloudAAA" },
      "provider": { "profileName": "anthropic-selab-gw", "modelName": "claude-sonnet-4-6" },
      "tools": [
        { "referenceId": "application:ConfigurationManager:runCompliancePlan", "lastKnownName": "runCompliancePlan", "decoratorId": "6a453e7b025a4623ad3df433" },
        { "referenceId": "application:ConfigurationManager:searchCompliancePlanInstances", "lastKnownName": "searchCompliancePlanInstances" },
        { "referenceId": "adapter:Servicenow:ServiceNow:createChangeRequest", "lastKnownName": "createChangeRequest", "decoratorId": "6a4522569c7614ba882f176c" },
        { "referenceId": "gatewayService:selab-iag5-standalone:04a19e29-f2dc-41f7-b9c7-102e6b19df08", "lastKnownName": "sleep-and-echo" }
      ]
    }
  ]
}
```

`provider` is de-identified on export to `{profileName, modelName}` strings (not the live UUIDs) — portable across environments where those UUIDs would differ. `agents[]` supports multiple agents per project. `tools[].decoratorId` is present only on entries that have one attached.

**Import:**
```
POST /agent-project-service/project-bundles/import
```
```json
{
  "bundle": { "...same shape as export, agentProjectBundleVersion: 1..." },
  "conflictMode": "keep-both",
  "name": "Network Operations",
  "description": "optional override of the bundle's project name/description",
  "providerResolutions": {
    "<agent identifier from the bundle>": { "profileName": "Production Anthropic", "modelName": "claude-sonnet-4-6" }
  }
}
```
`conflictMode`: `keep-both` (duplicate) | `replace` (overwrite an existing project/agent with matching identity). `providerResolutions` remaps each agent's `profileName`/`modelName` to a profile/model that actually exists in the **target** environment — required because profiles are environment-specific (different credentials per environment) even though the bundle references them by portable name. **The named profile/model must already exist in the target environment before import** — bundle import does not create profiles.

### Agents (Agent Project Service)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agent-project-service/projects/{projId}/agents` | Create an agent inside a project |
| DELETE | `/agent-project-service/projects/{projId}/agents/{agentId}` | Delete an agent |
| GET | `/agent-project-service/agents/{agentId}` | Get an agent (flat path — not project-nested) |
| PATCH | `/agent-project-service/agents/{agentId}` | Update an agent |
| GET | `/agent-project-service/operable-agents` | Paginated list of agents the caller can run (project role OR `operators` membership) |
| GET | `/agent-project-service/operable-agents/{agentId}` | Single operable agent |
| GET | `/agent-project-service/agent-names/accessible` | Minimal names of agents visible under read/write/manage GBAC; filterable by `modelId`, `toolReferenceId`, `projUUID`, `access` |
| GET | `/agent-project-service/agent-names/operable` | Minimal `{name, _id, project}` for every agent the caller can operate (unpaginated) |

**There is no endpoint to list all agents within one project** — use `agent-names/accessible?projUUID=<uuid>` instead.

**Create (full body):**
```json
{
  "name": "network-ops-agent",
  "description": "...",
  "instructions": "...",
  "inputSchema": {
    "type": "object", "additionalProperties": false,
    "required": ["deviceName"],
    "properties": { "deviceName": { "type": "string" } }
  },
  "provider": { "profile": "<uuid>", "model": "<uuid>" },
  "tools": [
    { "referenceId": "string", "decoratorId": "<24-hex, optional>", "lastKnownName": "string, optional" }
  ],
  "operators": ["<24-hex-account-or-group-id>"]
}
```
`tools[].referenceId` is the only required field per tool entry. `provider` requires both `profile` and `model` together if present — `additionalProperties: false` (no inline API keys or temperature here; those live on the Profile).

**Writing `instructions` and `inputSchema`:**

`instructions` is a single string (not a chat array) — tell the agent WHO it is and HOW to work: its role, what tools are available and when to use each, expected output format, and constraints (read-only, require approval, etc.).

`inputSchema` is a strict, flat contract for what a caller must supply when starting a session — only `string`/`number` property types are allowed, `additionalProperties` must be `false`, and `required` lists which of the declared properties are mandatory:
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["deviceName"],
  "properties": {
    "deviceName": { "type": "string" },
    "priority": { "type": "string" }
  }
}
```
This is a real function-signature-style contract now, not a free-form context bag — the platform validates session inputs against it.

**CRITICAL — every declared `inputSchema` property MUST appear as a `{{ propertyName }}` template variable somewhere in `instructions`.** `instructions` isn't just a static system prompt — it's a template, and `inputSchema` properties are substituted into it at session-start time. Declaring a property that isn't referenced fails agent create/update with: *"'&lt;name&gt;' is defined in schema but not used in template"*. A session's `agentSnapshot.instructions` shows the **post-substitution** text — e.g. a schema property `count` referenced as `{{ count }}` in the instructions becomes the literal value (`3`) in the snapshot once a session starts with `inputs: {count: 3}`. Declare a property only if you actually reference it with `{{ }}` somewhere in `instructions`.

**Update — note the shape differs from create:**
```json
{
  "name": "string, optional",
  "description": "string, optional",
  "prompt": { "instructions": "string", "inputSchema": { "...same strict schema..." } },
  "provider": { "profile": "<uuid>", "model": "<uuid>" },
  "addTools": [{ "referenceId": "string", "decoratorId": "<24-hex, optional>" }],
  "decorateTools": [{ "referenceId": "string", "decoratorId": "<24-hex-or-null>" }],
  "authorizeTools": [{ "referenceId": "string" }],
  "removeTools": [{ "referenceId": "string" }],
  "operators": ["<24-hex-id>"]
}
```
- `instructions`/`inputSchema` are top-level on **create** but nested under `prompt` on **update** — an intentional API asymmetry, not a typo.
- Tool changes on update are **deltas**, not a full-array replace: `addTools`, `removeTools`, `decorateTools` (attach/detach/change a decorator on an existing reference — `decoratorId: null` clears it), and `authorizeTools` (marks a tool reference as explicitly authorized — exact semantics not documented beyond the field name; verify against your platform before relying on it for anything security-sensitive).
- **Updating `operators` requires the owner GBAC role** on the parent project, even though other agent edits only need editor.

**`operators` — what it actually is:** a direct, agent-level access grant (array of 24-hex account/group IDs) letting those specific callers *operate* (run) this one agent, independent of their project role. It's additive to project GBAC, not a replacement — a project editor/owner can already operate every agent in the project; `operators` extends operate-access to accounts that otherwise wouldn't have it. This does not control what identity the agent's own tool calls run as — that's a separate concern not configured on the agent definition itself.

### Providers and Profiles (Model Registry Service)

**Base path:** `/model-registry-service`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/model-registry-service/providers` | List supported provider types (read-only catalog — cannot create/edit/delete) |
| GET | `/model-registry-service/providers/{providerId}` | Get one provider type's credential field requirements |
| POST | `/model-registry-service/providers/{providerId}/fetch-models` | Validate a credential and preview its available models |
| GET | `/model-registry-service/profiles` | List profiles (`search`, `provider`, `sortBy`: name\|provider\|agentCount\|createdAt, `sortDir`, `page`, `pageSize`) |
| POST | `/model-registry-service/profiles` | Create a profile |
| GET | `/model-registry-service/profiles/{id}` | Get a profile (credentials always masked) |
| PATCH | `/model-registry-service/profiles/{id}` | Update a profile (provider type is immutable) |
| DELETE | `/model-registry-service/profiles/{id}` | Hard-delete a profile |
| GET | `/model-registry-service/profiles/{id}/agent-impact` | List agents that will break if this profile is deleted |
| GET | `/model-registry-service/gateways` | List GatewayManager clusters available for `category: "gateway"` profiles |

**Provider type IDs observed in the credential union:** `openai`, `anthropic`, `google`, `ollama`, `bedrock`, `bedrock-proxy`, `databricks`, `gateway-manager`, plus `managed` (platform-hosted, no credential). **There is no distinct `azure-openai` provider ID** — reach Azure OpenAI via `provider: "openai"` with `credential.baseURL` pointed at your Azure endpoint, or via gateway/proxy routing. Always confirm against `GET /providers` on your actual deployment before assuming an ID exists.

**Create a profile — three categories, discriminated by `category`:**

`"direct"` (you supply the credential straight to the provider):
```json
{
  "profile": {
    "category": "direct",
    "name": "Production Anthropic",
    "provider": "anthropic",
    "credential": { "type": "anthropic", "apiKey": "sk-ant-..." },
    "models": [{ "name": "claude-opus-4-6-20260201" }],
    "builderGroups": []
  }
}
```

`"gateway"` (routed through a GatewayManager cluster — adds a required `gatewayCluster`):
```json
{
  "profile": {
    "category": "gateway",
    "name": "Gateway-Routed Bedrock",
    "provider": "bedrock",
    "gatewayCluster": "<cluster-id-from-GET-gateways>",
    "credential": { "type": "bedrock", "config": { "region": "us-east-1", "accessKeyId": "...", "secretAccessKey": "..." } },
    "models": [{ "name": "anthropic.claude-3-5-sonnet-20241022-v2:0" }],
    "builderGroups": []
  }
}
```

`"managed"` (platform-hosted, no credential at all):
```json
{
  "profile": {
    "category": "managed",
    "name": "Platform-Managed Model",
    "provider": "<provider-id-with-managedModels>",
    "models": [{ "name": "<must-match-one-of-provider.managedModels[].name>" }],
    "builderGroups": []
  }
}
```

**Credential shapes by type:**

| `type` | Required | Optional |
|---|---|---|
| `openai` | `apiKey` | `baseURL` |
| `anthropic` | `apiKey` | `baseURL` |
| `google` | `apiKey` | — |
| `ollama` | *(none)* | `baseURL` |
| `bedrock` | `config.region`, `config.accessKeyId`, `config.secretAccessKey` | `config.iamRole` |
| `bedrock-proxy` | `config.serviceUrl`, `config.tokenUrl`, `config.clientId`, `config.clientSecret` | — |
| `databricks` | `config.type` (const `"oauth-m2m"`), `config.host`, `config.clientId`, `config.clientSecret` | — |
| `gateway-manager` | `config.clusterId`, `config.backendProvider`, `config.credential` | `config.properties` |

**Response (create/get):**
```json
{
  "id": "<profile-uuid>",
  "name": "Production Anthropic",
  "provider": "anthropic",
  "credential": { "type": "api-key", "masked": true, "baseUrl": "..." },
  "models": [
    { "id": "<model-uuid>", "name": "claude-opus-4-6-20260201", "enabled": true, "status": "active" }
  ],
  "builderGroups": [],
  "agentCount": 0,
  "createdAt": "...", "updatedAt": "...", "createdBy": "...", "updatedBy": "..."
}
```
`credential.masked` is always `true` on read — the actual secret is never echoed back. **`models[].id` is the UUID you use as an agent's `provider.model`; `id` (top level) is `provider.profile`.**

**Update:** wrapped in `{"update": {...}}`, all fields optional. Provider type cannot change. `models[]` items on update require both `name` and `enabled` (unlike create, which only requires `name`).

**Before deleting a profile**, always check impact first:
```
GET /model-registry-service/profiles/{id}/agent-impact
→ { "affectedAgents": [{ "id", "name", "modelId", "modelName" }] }
```

**Discover models for a credential before saving it:**
```
POST /model-registry-service/providers/{providerId}/fetch-models
```
```json
{ "credential": { "type": "anthropic", "apiKey": "sk-ant-..." } }
```
or, to refresh using an already-saved profile's credential:
```json
{ "profileId": "<existing-profile-uuid>" }
```
Response: `{ "success": true, "models": [{ "id", "name", "enabled", "status" }], "retrievedAt": "..." }`. **These `models[].id` values are provider-native, not registry UUIDs** — use `models[].name` to populate a profile's `models` array; the registry assigns a new UUID once the model is actually saved into a profile.

**Related read-through view for agent authoring** (`/agent-project-service/profiles`, `/agent-project-service/profiles/{profileId}`) — GBAC-scoped proxy onto the same profiles, used when wiring an agent so the UI only shows profiles the current user is allowed to use. Same profile `id`/UUID either way.

### Tools

**Base path:** `/tools`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools` | Search tools (see query params below) |
| GET | `/tools/{referenceId}` | Get a single tool |
| POST | `/tools/bulk` | Batch lookup by `referenceIds` |
| POST | `/tools/discover` | Scan the platform and register/refresh tools |

**`GET /tools` query parameters:** `skip`, `limit`, `type`, `name`, `referenceIds` (comma-separated), `description` (keyword), `active` (boolean), `parentIds`/`parentTypes`/`parentTitles` (comma-separated — tools can be hierarchical, e.g. children of an adapter instance), `excludeToolChildren` (top-level only), `sort` (`name`\|`type`\|`description`\|`source`\|`referenceId`), `order` (`asc`\|`desc`).

**Test a tool directly before wiring it to an agent.** Don't give an agent a tool you haven't tested yourself — every tool wraps a real platform API call, and if the direct call fails, the agent's call will too:
```bash
# Look up the tool's registry entry (schema/description the LLM will see)
GET /tools/{referenceId}

# Test the underlying endpoint directly — same as testing any platform call, independent of FlowAI:
# Adapter:     POST /ServiceNow/createChangeRequest   {"body": {...}}
# App:         POST /configuration_manager/getDevice  {"name": "IOS-CAT8KV-1"}
# IAG service: POST /gateway_manager/v1/gateways/{clusterId}/services/{serviceName}/run  {"params": {...}}
# Workflow:    POST /operations-manager/jobs/start     {"workflow": "...", "options": {...}}
```
Look up the exact route and request body from `openapi.json` (`jq '.paths | keys[] | select(contains("<adapter-or-app-name>"))' openapi.json`) the same way you would for any platform call — this doesn't depend on FlowAI at all. **If the tool's native schema is too broad or the LLM keeps sending wrong/incomplete inputs**, create a decorator (see Decorators below) — but only after confirming the native tool actually works when called correctly.

**Discover:**
```
POST /tools/discover
```
No body. Scans adapters, IAG services, and app methods, persisting each as a registry entry addressed by `referenceId`. Safe to re-run — refreshes the registry rather than duplicating entries.

**Tool identity — `referenceId` format:** a colon-separated `<type>:<source>:<method>` string. Observed `type` values: `application`, `adapter`, `gatewayService`, `workflow`, `integration`, `template`, `jsonForm`, `method` (a method belonging to a parent `application`/`adapter` entry — see `parentType`/`parentId`/`parentTitle` on the tool object):

| Type | Example `referenceId` | Structure |
|---|---|---|
| `application` | `application:ConfigurationManager:runCompliancePlan` | `application:<app-name>:<method>` |
| `adapter` | `adapter:Servicenow:ServiceNow:createChangeRequest` | `adapter:<adapter-instance-id>:<app-type-name>:<method>` |
| `gatewayService` | `gatewayService:selab-iag5-standalone:04a19e29-f2dc-41f7-b9c7-102e6b19df08` | `gatewayService:<cluster-id>:<service-uuid>` |
| `workflow` | `workflow:7473bb49-f317-4280-9d7a-9e4bd4969365` | `workflow:<workflow-uuid>` |
| `integration` | `integration:BECentral%3A2.3:BECentral23:getDevicesByTagId` | `integration:<instance-id-may-be-url-encoded>:<app-name>:<method>` |

**Tool object shape** (`GET /tools/{referenceId}`):
```json
{
  "_id": "<mongo-id>",
  "type": "method",
  "referenceId": "application:ConfigurationManager:getDevicesFiltered",
  "active": true,
  "checksum": "...",
  "description": "Gets a specific subset of devices for based on given options",
  "inputSchema": { "...full JSON Schema draft 2020-12, with real property definitions, enums, and examples..." },
  "lastUpdated": "...",
  "name": "getDevicesFiltered",
  "parentId": "ConfigurationManager",
  "parentInstance": null,
  "parentTitle": "ConfigurationManager",
  "parentType": "application"
}
```
`inputSchema` on a tool is a full, real JSON Schema (types, enums, patterns, examples) — this is what an LLM actually sees for that tool's parameters, and it's what a decorator's `toolInputSchema` replaces if one is attached.

There is **no create/update/delete for individual tools** — the registry is populated only by discovery.

### Decorators

**Base path:** `/tools/decorators`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tools/decorators` | Create a decorator for a tool |
| GET | `/tools/decorators/{decoratorId}` | Get a decorator |
| DELETE | `/tools/decorators/{decoratorId}` | Delete a decorator |
| POST | `/tools/decorators/{decoratorId}/clone` | Clone a decorator (start from an existing one, adapt for a new team/agent) |
| GET | `/tools/decorators/bulk/export` | Export all decorators (paginated) |
| POST | `/tools/decorators/bulk/import` | Bulk-import decorators |
| GET | `/tools/{referenceId}/decorators` | List all decorators for one tool — a tool can have many |

`helpers/create/create-flowagent-decorator.json` is a ready-to-edit starting template for the body below.

**Create — required shape:**
```json
{
  "toolDecorator": {
    "referenceId": "<tool's referenceId>",
    "name": "<decorator name>",
    "description": "<what this decorator customizes and why>",
    "toolDescription": "<replacement description the LLM sees>",
    "toolInputSchema": { "...replacement JSON Schema..." }
  }
}
```
`referenceId`, `name`, `description`, `toolDescription`, `toolInputSchema` are all required. Response contains the generated `decoratorId` (24-char hex Mongo ObjectId), plus the full decorator record (`toolDescription`, `toolInputSchema` with `$schema` auto-added, `created`/`createdBy`/`lastUpdated`/`lastUpdatedBy`) — this response shape isn't in the OpenAPI spec, so treat the fields above as the reference.

**Example — narrowing a vague native schema:** `adapter:Servicenow:ServiceNow:createIncident`'s native `inputSchema` only declares `{body: {type: object}}`, with no field-level detail. An LLM working from that schema alone has no way to know `summary` and `short_description` are required, and the adapter rejects a call missing them: `"Schema validation failed on must have required property 'summary'"`. A decorator fixes this by declaring the fields explicitly:

```
POST /tools/decorators
```
```json
{
  "toolDecorator": {
    "referenceId": "adapter:Servicenow:ServiceNow:createIncident",
    "name": "create-incident-required-fields",
    "description": "Ensures summary and short_description are always included -- the native schema doesn't declare them.",
    "toolDescription": "Creates a ServiceNow incident. The body MUST include both 'summary' and 'short_description' -- omitting summary causes a schema validation error from the adapter. Include 'description' for full diagnostic detail.",
    "toolInputSchema": {
      "type": "object",
      "properties": {
        "body": {
          "type": "object",
          "properties": {
            "summary": { "type": "string", "description": "Required. Short one-line summary of the incident." },
            "short_description": { "type": "string", "description": "Required. Brief description shown in incident lists -- usually the same text as summary." },
            "description": { "type": "string", "description": "Full diagnostic detail." }
          },
          "required": ["summary", "short_description"]
        }
      },
      "required": ["body"]
    }
  }
}
```
**Response shape:**
```json
{
  "_id": "6a465ed52d79d885c63eb250",
  "toolDescription": "...",
  "toolInputSchema": { "note": "same shape as sent, with $schema auto-added" },
  "referenceId": "adapter:Servicenow:ServiceNow:createIncident",
  "name": "create-incident-required-fields",
  "description": "...",
  "created": "...",
  "createdBy": { "_id": "...", "username": "...", "provenance": "..." },
  "lastUpdated": "...",
  "lastUpdatedBy": { "_id": "...", "username": "...", "provenance": "..." }
}
```
`_id` is the `decoratorId`. Note the decorator only narrows `body`'s known properties (`summary`, `short_description`, `description`) — it doesn't set `additionalProperties: false`, so other real adapter fields the LLM already knows about (from training or context) can still pass through; only omit `additionalProperties: false` if you deliberately want to lock the schema down to exactly those fields.

**Two ways to attach it to an agent:**

1. **At agent creation** — include `decoratorId` directly in the `tools[]` entry:
```json
{ "tools": [{ "referenceId": "adapter:Servicenow:ServiceNow:createIncident", "decoratorId": "6a465ed52d79d885c63eb250" }] }
```

2. **On an existing agent** — `PATCH` with `decorateTools`:
```
PATCH /agent-project-service/agents/{agentId}
```
```json
{ "decorateTools": [{ "referenceId": "adapter:Servicenow:ServiceNow:createIncident", "decoratorId": "6a465ed52d79d885c63eb250" }] }
```
Decorators are looked up by ID when an agent runs, not embedded inline — the same decorator can be referenced by multiple agents, and `clone` lets you start from an existing decorator rather than hand-authoring overrides from scratch for a new team/use case.

**Effect:** with the decorator attached, `createIncident` produces a single `tool-execution` message with `status: "succeeded"` — the LLM has the exact required fields up front and doesn't need a failed first attempt to discover them.

**CRITICAL:** a decorator's `toolInputSchema` **replaces the entire schema the LLM sees** — any field you omit will never be sent by the agent, even if the underlying adapter requires it. Test the tool directly (see Tools above) to find every required field before writing the decorator.

**When to create a decorator (and when NOT to):** create one only when the tool's native schema is too broad and the LLM sends wrong/incomplete inputs despite good `instructions`, or when different teams need different required fields on the same tool. Skip it for read-only tools and skip it if fixing the `instructions` text alone solves the problem.

### Sessions (Agent Session Manager)

**Base path:** `/agent-session-manager`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agent-session-manager/sessions` | List/search sessions |
| POST | `/agent-session-manager/sessions` | Start a session (async — fire and forget) |
| GET | `/agent-session-manager/sessions/{sessionId}` | Get one session's metadata |
| POST | `/agent-session-manager/sessions/{sessionId}` | Cancel / Pause / Resume a session |
| DELETE | `/agent-session-manager/sessions/{sessionId}` | Delete a session (per-session only — no bulk clear) |
| POST | `/agent-session-manager/sessions/run-agent` | Run an agent from inside an Itential workflow |
| GET | `/agent-session-manager/sessions/sources` | Distinct `trigger.source` values (UI filter helper) |
| GET | `/agent-session-manager/sessions/{sessionId}/messages` | Session activity log (paginated) |
| GET | `/agent-session-manager/sessions/{sessionId}/messages/{eventId}` | One event, untruncated |

**List — query parameters:** `filters` (array of field/operator/value), `offset`, `limit` (max 100), `sortBy` (`createdAt`\|`updatedAt`\|`startedAt`\|`status`\|`createdBy`\|`agentDefinitionId`), `sortOrder`.

**Session object** (`agentSnapshot.instructions` shows `{{ }}` template variables already substituted with the actual session `inputs`):
```json
{
  "sessionId": "string",
  "agentDefinitionId": "string",
  "agentSnapshot": { "_id": "...", "name": "...", "instructions": "... (template vars substituted) ...", "namespace": { "_id": "...", "name": "..." } },
  "status": "PENDING | RUNNING | PAUSING | PAUSED | COMPLETE | FAILED | CANCELING | CANCELED",
  "startedAt": "...", "endTime": "...", "durationMs": 0,
  "createdAt": "...", "createdBy": "<account-id>",
  "provider": "anthropic",
  "modelVersion": "claude-sonnet-4-6",
  "sessionType": "root | child",
  "trigger": { "type": "eventSystem|endpoint|schedule|manual|job|session", "name": "...", "source": "..." },
  "errorMessage": "...", "errorCategory": "...",
  "iterationCount": 0, "toolGroupCount": 0, "totalToolCallCount": 0,
  "totalInputTokens": 0, "totalOutputTokens": 0,
  "inputs": {}
}
```
`provider`/`modelVersion` are plain strings (provider id and model name) at the session level — not the `{profile, model}` UUID pair used on the agent itself. `agentSnapshot` is a copy of the agent's config **at session-start time** — updating the agent afterward does not retroactively change what a past session ran. `sessionType: child` implies sessions can spawn child sessions; the mechanism for that isn't exposed in this API slice — treat as informational unless you see it triggered from elsewhere.

**Start a session (async):**
```
POST /agent-session-manager/sessions
```
```json
{ "agentDefinitionId": "<agent-uuid>", "inputs": { "deviceName": "IOS-CAT8KV-1" } }
```
`inputs` must satisfy the agent's `inputSchema`. Response: `{ "sessionId": "...", "status": "..." }` — returns immediately, does not wait for completion. **`status` in the response was observed going straight to `RUNNING` in testing** — don't assume you'll always see `PENDING` first; poll and branch on the terminal states (`COMPLETE`/`FAILED`/`CANCELED`), not on catching a specific intermediate value.

**Cancel / Pause / Resume:**
```
POST /agent-session-manager/sessions/{sessionId}
```
```json
{ "action": "CANCEL", "canceledBy": "<username>", "correlationId": "<for tracing>" }
```
`action` is one of `CANCEL` | `PAUSE` | `RESUME`. Response: the full updated Session object.

**Delete:**
```
DELETE /agent-session-manager/sessions/{sessionId}
```
Per-session only — **there is no bulk "clear all sessions" endpoint**. To purge history, page through `GET /sessions` and delete individually.

**Run from a workflow:**
```
POST /agent-session-manager/sessions/run-agent
```
```json
{
  "agent": "<agent-uuid>",
  "inputs": { "deviceName": "IOS-CAT8KV-1" },
  "terminationCallbackSignature": {
    "location": "string", "serviceName": "string", "methodName": "string", "identifier": "string"
  }
}
```
Note the field is `agent`, not `agentDefinitionId`. `terminationCallbackSignature` is an IAP cog hook invoked when the session reaches a terminal state — **the calling workflow task stays "running" until then**, which is what makes this feel synchronous from the workflow's perspective, even though the HTTP response itself returns immediately with `{sessionId, status}`. The "wait" happens at the workflow-engine layer, not the HTTP layer — see "Using Agents in Workflows" below.

**Activity log:**
```
GET /agent-session-manager/sessions/{sessionId}/messages?sortBy=timestamp&sortOrder=asc
```
Each message: `{ sessionId, eventId, timestamp, type, category, sequenceNumber?, text?, data }`.
- `type`: `inference-pending` | `inference-succeeded` | `inference-failed` | `tool-execution` | `agent-session-paused` | `agent-session-resumed` | `agent-session-completed` | `agent-session-failed` | `agent-session-canceled`
- `category`: `AGENT_REASONING` | `TOOL_CALLED` | `AGENT_STATUS`
- `sequenceNumber` is `null` on `tool-execution` and `AGENT_STATUS` messages — only `AGENT_REASONING` messages are sequenced.

**Real `data` shapes:** session messages return the actual resolved tool input/output inline, not just a store/receipt pointer — the receipt pattern described under Agent Execution Engine below is internal plumbing between the execution engine and its tool executor; it doesn't change what this endpoint returns.

`inference-succeeded`:
```json
{
  "durationMs": 2125,
  "stopReason": "tool_use | end_turn",
  "tokenUsage": { "inputTokens": 1055, "outputTokens": 73, "cacheReadTokens": 0, "cacheCreationTokens": 0 }
}
```
Sibling `text` field on the same message has the LLM's actual reasoning/response text.

`tool-execution`:
```json
{
  "toolGroupId": "<uuid>",
  "toolCallId": "toolu_...",
  "toolName": "getDevicesFiltered",
  "toolType": "method",
  "input": { "options": { "limit": 3 } },
  "isInputTruncated": false,
  "output": { "...the tool's actual return value..." },
  "isOutputTruncated": false,
  "durationMs": 764,
  "errorMessage": null, "errorCategory": null, "canceledBy": null,
  "outcomeEventId": "<eventId of the AGENT_REASONING message that follows>",
  "status": "succeeded"
}
```
`output` is the real, resolved tool result — inspect it directly rather than assuming you need `GET .../messages/{eventId}` to see it. `isInputTruncated`/`isOutputTruncated` flag when a large payload WAS truncated in this listing; fetch the single-event endpoint only in that case. A `view`-type tool call (see Work Items below) instead sits at `"status": "pending"` with `"output": null` until a person completes the corresponding work item.

### Work Items (WorkCenter Service)

**Base path:** `/work-center-service`

An agent can pause and wait for a real person to act, using a `view`-type tool. This is a different mechanism from a normal tool call:

**The tool:** `view:WorkCenter:QuickForm` (discovered and wired into an agent's `tools[]` exactly like any other tool). Its `inputSchema` fields:

| Field | Type | Required | Purpose |
|---|---|---|---|
| `quickFormData` | array | ✅ | The rows to render in the table |
| `columnDisplay` | `all` \| `allowlist` \| `denylist` | ✅ | Which columns appear |
| `columns` | array | | Column names to include/exclude (used with `allowlist`/`denylist`) |
| `actionColumnHeader` | string | ✅ | Display header for the action column |
| `actionColumnKey` | string | ✅ | Key used to annotate each row with the operator's input in the outgoing rows |
| `actionColumnType` | `dropdown` \| `text` \| `selection` | ✅ | Input control rendered per row |
| `actionColumnRequired` | boolean | ✅ | When `true`, Complete is disabled until every row is actioned |
| `actionColumnLabels` | array | | Dropdown options (required when `actionColumnType` is `dropdown`) |
| `actionColumnAllowMultiple` | boolean | | Allow multiple dropdown selections per row |

Example agent tool-call input (one summary row, dropdown acknowledgement):
```json
{
  "quickFormData": [
    { "device": "dc1-leaf1", "summary": "show version failed — unsupported device_type", "incidentNumber": "INC0012773" }
  ],
  "columnDisplay": "all",
  "actionColumnHeader": "Acknowledge",
  "actionColumnKey": "acknowledged",
  "actionColumnType": "dropdown",
  "actionColumnRequired": true,
  "actionColumnLabels": ["Acknowledged", "Needs Follow-up"]
}
```

**What actually happens when an agent calls it:**
1. The tool call's session message shows up with `"status": "pending"` and `"output": null` — it does not resolve on its own.
2. The session's own `status` stays `RUNNING` the whole time — there is no distinct "awaiting input" session state. Don't rely on session `status` alone to detect a HITL wait; check whether the latest `tool-execution` message has `status: "pending"`.
3. A real work item is created in a separate service — **WorkCenter Service** (`/work-center-service/*`), not the Tools Service or Agent Session Manager. This is a distinct application with its own API surface.

**Finding and completing the pending work item:**
```
GET /work-center-service/work-items?rootExecutionId=<sessionId>
```
Returns the pending item(s) for that session, including `id`, `status`, `view`, and the `execution`/`rootExecution` metadata linking it back to the session.

```
GET /work-center-service/work-items/{id}
GET /work-center-service/work-items/{id}/variables/incoming
```
Get the full item detail or just its incoming variables (what was passed to the `view` tool call — e.g., the `quickFormData` rows and column config).

**Complete it (this is what a human does by clicking "Complete" in the WorkCenter UI):**
```
PATCH /work-center-service/work-items/{id}/complete
```
```json
{
  "finishState": "completed",
  "variables": { "acknowledged": "Acknowledged" }
}
```
`variables` is a flat key-value object — the key matches `actionColumnKey` from the original QuickForm input, the value is one of `actionColumnLabels` (for a dropdown). **Method is `PATCH`, not `POST`** — a `POST` to this path returns a plain 404. Response is the completed work item (`status: "completed"`); the agent's session then resumes on its own and reaches `COMPLETE` shortly after.

**Other work-item lifecycle endpoints:**
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/work-center-service/work-items` | List (requires `rootExecutionId` query param) |
| POST | `/work-center-service/work-items/search` | Richer search (requires `sort.field`/`sort.order`) |
| GET | `/work-center-service/work-items/count` | Count matching items |
| POST | `/work-center-service/work-items/{id}/claim` | Claim ownership before acting |
| POST | `/work-center-service/work-items/{id}/release` | Release a claimed item back to the pool |
| POST | `/work-center-service/work-items/{id}/assign` | Assign to a specific operator |
| PATCH | `/work-center-service/work-items/{id}/complete` | Submit the operator's response and resolve the item |
| POST | `/work-center-service/work-items/cancel` / `/cancel-work-items` | Cancel one or more pending items |

**Design implication:** if an agent's `instructions` call for presenting something to a human before finishing, expect the session to sit `RUNNING` indefinitely (minutes to hours, however long the human takes) until someone completes the corresponding work item. Poll or watch WorkCenter, not just the session — a session "stuck" in `RUNNING` with a `pending` `tool-execution` message is working as intended, not failing. Not just `QuickForm` — any `view`-type tool (e.g. `view:WorkFlowEngine:ViewHTML`) follows the same pause/work-item/complete pattern, and an agent can call more than one in sequence, each producing its own work item.

### Tool Executions (Tool RPC — observability only)

**Base path:** `/tool-rpc`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tool-rpc/executions` | Search tool executions (`status`: `running`\|`complete`, paginated) |
| GET | `/tool-rpc/executions/{toolExecutionId}` | Get one tool execution's full detail |

Read-only. This is where to look up the outcome of one specific tool call an agent made, without paging through the session's full message log. Response: `{ skip, limit, total, results: [...] }` for the list; a single untyped object for the detail call.

### Agent Execution Engine (internal — do not call directly)

**Base path:** `/agent_execution_engine`. Scoped `AgentExecutionEngine.admin` only — no operator/builder role exists for it. Normal users and workflows should always go through Agent Session Manager; the Execution Engine is the internal kernel Session Manager calls on your behalf. Documented here only so session behavior makes sense when debugging — **never wire a workflow task directly to `/agent_execution_engine/*`.**

**How a session actually runs, internally:**
1. Session Manager resolves `agentDefinitionId` → fetches instructions, provider/model, resolved+decorated tools from Agent Project Service and Model Registry Service.
2. Session Manager hands a fully-materialized definition to the Agent Execution Engine, which starts the inference loop.
3. The LLM decides which tool(s) to call based on the objective and `inputs`.
4. Tool execution happens **asynchronously and externally under the hood** — the engine dispatches a tool call, an external executor runs it and persists the result, then calls back into the engine with a receipt (the `handle-tool-response` callback pattern, tracked via Tool RPC). This is internal plumbing — the session's `messages` still show the actual resolved tool input/output directly, not the receipt, and a fast tool call is fully visible there within seconds.
5. The engine fetches the actual result and feeds it back to the LLM; repeats until the objective is met or an error occurs.
6. Every step is recorded as a typed session message; the session's `status` reaches a terminal state (`COMPLETE`/`FAILED`/`CANCELED`) — unless a `view`-type tool call is pending, in which case the session stays `RUNNING` until the corresponding work item is completed (see Work Items above).

---

## Using Agents in Workflows

Run an agent from inside an Itential workflow using the `run-agent` cog task, which uses the termination-callback pattern to make the workflow task wait for the session to finish:

```json
{
  "name": "runAgent",
  "app": "FlowAI",
  "type": "operation",
  "location": "Application",
  "variables": {
    "incoming": {
      "agent": "$var.job.agentId",
      "inputs": "$var.job.agentInputs"
    },
    "outgoing": {
      "sessionId": "$var.job.sessionId",
      "status": "$var.job.sessionStatus"
    }
  }
}
```

The exact task name and available FlowAI workflow tasks depend on what's registered as a `tools`-app on your platform — look it up with `jq '.[] | select(.app == "FlowAI")' tasks.json` before wiring, since task names may not map 1:1 to the raw REST operation names shown in this skill (`runAgent` above mirrors the `POST /agent-session-manager/sessions/run-agent` operation, but the literal task name is platform-specific — check your platform's `tasks.json`).

The task holds the workflow at that point until the session reaches a terminal state (`COMPLETE`/`FAILED`/`CANCELED`), then continues with the session's outcome available to downstream tasks — check `status` and branch accordingly (e.g., `evaluation` on `status == "FAILED"` to route to an error-handling path).

## Patterns

### Minimal agent (no tools, just LLM)
```json
{
  "name": "poet",
  "description": "writes poems",
  "instructions": "You are a poet. Write a haiku about the topic you're given.",
  "inputSchema": {
    "type": "object", "additionalProperties": false,
    "required": ["topic"],
    "properties": { "topic": { "type": "string" } }
  },
  "provider": { "profile": "<profile-uuid>", "model": "<model-uuid>" },
  "tools": [],
  "operators": []
}
```

### Agent with platform tools
```json
{
  "name": "device-checker",
  "description": "Checks device health using platform adapters",
  "instructions": "You check device health using the available tools. Use the exact device name given — do not guess or reformat it.",
  "inputSchema": {
    "type": "object", "additionalProperties": false,
    "required": ["deviceName"],
    "properties": { "deviceName": { "type": "string" } }
  },
  "provider": { "profile": "<profile-uuid>", "model": "<model-uuid>" },
  "tools": [{ "referenceId": "<referenceId-for-AutomationGateway-sendCommand>" }],
  "operators": []
}
```

**Agent-to-agent delegation is not supported.** There is no field in the Agent Project Service schemas for one agent to call another by name. If you need one agent's output to feed another, orchestrate it at the workflow level instead — run one agent's session, wait for its result via `run-agent`'s termination callback, then start the next session with that result as part of its `inputs`.

## Developer Scenarios

### 1. Set up from scratch

Before building, decide: what should the agent accomplish, what external systems does it need to touch, what inputs will vary between runs (→ `inputSchema`), does it need to make changes or just gather information, which project should own it, and who needs to be able to run it (`operators`) vs. edit it (project `members`).

```bash
# Discover platform tools into the Tools Service registry (idempotent — safe to re-run)
POST /tools/discover

# Pull the tool list locally (paginated — use skip/limit) and search by keyword
GET /tools?limit=200 > tools.json
GET /tools?skip=200&limit=200 >> tools.json   # repeat until fewer than `limit` returned
jq '.[] | select(.name | test("ServiceNow"; "i"))' tools.json

# Check what LLM provider profiles and provider types already exist
GET /model-registry-service/profiles
GET /model-registry-service/providers
```

```
1. POST /agent-project-service/projects                        → create (or reuse) a project — see Projects
2. GET  /model-registry-service/providers/{providerId}         → confirm credential fields — see Providers and Profiles
3. POST /model-registry-service/providers/{providerId}/fetch-models → validate credential, preview models
4. POST /model-registry-service/profiles                       → create the LLM profile, save profile+model UUIDs
5. POST /tools/discover                                        → scan platform for available tools (above)
6. GET  /tools                                                 → review what's available, note referenceIds
7. POST /agent-project-service/projects/{projId}/agents        → create agent with tools + instructions + inputSchema — see Agents
8. POST /agent-session-manager/sessions                        → run it — see Sessions
9. GET  /agent-session-manager/sessions/{id}                   → check status and results
```

**Prefer building the project + agent(s) locally and importing as one bundle** (`POST /agent-project-service/project-bundles/import`) once a project has more than one agent, or when replicating a known-good setup into a new environment — see Project Bundles above. The inline call sequence above is fine for a single quick agent in an existing project.

### 2. Debug a failed session
```
1. GET /agent-session-manager/sessions/{id}                → check status, errorMessage, errorCategory
2. Check iterationCount / totalToolCallCount / totalInputTokens+totalOutputTokens → looping or context exhaustion?
3. GET /agent-session-manager/sessions/{id}/messages       → find the failing tool-execution event
4. GET /agent-session-manager/sessions/{id}/messages/{eventId} → untruncated detail on that event
5. GET /tool-rpc/executions/{toolExecutionId}              → if the event references a stuck/failed tool execution
6. Test the tool directly (same endpoint the tool wraps) with the same parameters the agent used
7. PATCH the agent's instructions or add a decorator, then re-run the session with the same inputs
```
See **Gotchas → Quick fixes for common problems** above for a symptom → cause → fix lookup table.

### 3. Rotate or replace an LLM credential
```
1. GET  /model-registry-service/profiles/{id}/agent-impact  → see which agents use this profile
2. PATCH /model-registry-service/profiles/{id}              → update the credential (provider type stays fixed)
   { "update": { "credential": { "type": "anthropic", "apiKey": "<new-key>" } } }
3. No agent changes needed — agents reference the profile by UUID, not the credential directly
```

### 4. Add human-in-the-loop approval to an agent
```
1. Add a view-type tool reference (e.g. view:WorkCenter:QuickForm) to the agent's tools[] — same as any other tool
2. Reference it explicitly in instructions with the exact QuickForm inputSchema fields (quickFormData, actionColumnKey, actionColumnLabels, etc.)
3. Run the session — the QuickForm tool call sits at status: "pending"; session status stays RUNNING throughout
4. GET  /work-center-service/work-items?rootExecutionId=<sessionId>   → find the pending item
5. GET  /work-center-service/work-items/{id}/variables/incoming       → see exactly what was presented to the human
6. PATCH /work-center-service/work-items/{id}/complete                → resolve it; the session resumes and reaches a terminal state on its own
```
See **Work Items (WorkCenter Service)** above for the full field reference and lifecycle endpoints.

### 5. Fix a tool's schema with a decorator
```
1. Test the tool directly (see Tools → "Test a tool directly...") to find every field the underlying adapter actually requires
2. POST /tools/decorators with a toolInputSchema that covers every required field the native schema omits
3. Attach it: decoratorId in tools[] at agent creation, or PATCH .../agents/{agentId} with decorateTools on an existing agent
4. Re-run the same session inputs — the tool call should now succeed on the first attempt instead of failing and retrying
```
See **Decorators** above for the full worked example.
