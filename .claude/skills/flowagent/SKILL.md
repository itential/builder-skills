---
name: flowagent
description: Create and run AI agents on the Itential Platform using the GA FlowAI APIs (Agent Project Service, Model Registry Service, Tools Service, Agent Session Manager). Agents use LLMs to autonomously call platform tools (adapters, workflows, IAG services) to complete objectives. Use when setting up agents, configuring LLM provider profiles, managing tools and decorators, or running/tracking agent sessions.
argument-hint: "[action or agent-name]"
---

# FlowAI - Agent Skills Guide (GA)

FlowAI lets you create AI agents that use LLMs (Anthropic, OpenAI, Google, Ollama, AWS Bedrock, Databricks, or platform-managed models) to autonomously operate the Itential Platform. Agents can call adapters, run workflows, and invoke IAG services — all driven by natural language instructions and a typed input contract.

**This skill documents the GA API surface** — six decomposed services that replaced the old flat `/flowai/*` prototype API: **Agent Project Service** (projects + agents), **Model Registry Service** (LLM provider profiles + models), **Tools Service** (tools + decorators), **Agent Session Manager** (running and tracking agents), **Agent Execution Engine** (internal execution kernel — not called directly), and **Tool RPC** (tool-call execution tracking).

**Response schema caveat:** several GA endpoints (notably most of Agent Project Service and the Tools Service) declare their success response as a bare `{"type": "object"}` in the OpenAPI spec — the exact response field names are not formally typed. Where this skill states a response shape, it's inferred from request-body schemas, the project-bundle export format (which IS fully typed), or cross-referenced fields — not guessed. When in doubt, call the endpoint against your live platform and inspect the actual response before hardcoding field access in a workflow task.

## Concepts

- **Project** — the top-level container that owns agents. GBAC-controlled (`owner`/`editor`/`viewer` roles via `members`). Agents cannot exist outside a project. Supports portable bundle import/export.
- **Agent** — a named AI entity: `instructions` (system prompt), a typed `inputSchema` (what parameters it accepts), a `provider` reference (which LLM profile + model it uses), a `tools` list, and an `operators` access list.
- **Profile** — a configured, credentialed instance of an LLM provider (e.g., "Production Anthropic"). Owned by Model Registry Service. Holds masked credentials and a curated list of enabled models, each with its own UUID.
- **Model** — one specific model enabled on a profile (e.g., a Claude or GPT model), addressed by a UUID assigned when it's added to the profile. An agent's `provider` field is `{profile: <uuid>, model: <uuid>}` — both required together.
- **Tool** — a callable platform capability (adapter method, IAG service, app method), addressed by an opaque `referenceId`. Discovered via `POST /tools/discover`, never created by hand.
- **Decorator** — a standalone, ID-addressed override of a tool's description and input schema for a specific use case. Cloneable and portable (bulk export/import). An agent attaches a decorator to a specific tool reference, not globally.
- **Session** — a single run of an agent. Replaces the old "mission." Has an 8-state lifecycle (`PENDING` → `RUNNING` → `COMPLETE`/`FAILED`/`CANCELED`, plus `PAUSING`/`PAUSED`/`CANCELING`) and a typed activity log (`messages`).
- **Operators** — an agent-level access-control list (account/group IDs) granting specific callers the right to run that agent, independent of their project role. Only project owners can edit it.
- **Builder Groups** — a profile-level access-control list controlling which groups can build agents against a given LLM profile.

## How to Build an Agent

### Step 1: Understand the intent

Before building anything, ask:
- What is the agent supposed to accomplish?
- What external systems does it need to interact with? (ServiceNow, devices, cloud, etc.)
- What inputs will vary between runs? (This becomes the agent's `inputSchema`.)
- Does it need to make changes or just gather information?
- Which project should own it, and who needs to be able to run it (`operators`) vs. edit it (project `members`)?

### Step 2: Discover the environment

```bash
# Discover platform tools into the Tools Service registry (idempotent — safe to re-run)
POST /tools/discover

# Pull the tool list locally (paginated — use skip/limit)
GET /tools?limit=200 > tools.json
GET /tools?skip=200&limit=200 >> tools.json   # repeat until fewer than `limit` returned

# Search by keyword (exact field names may vary — verify against a live response first)
jq '.[] | select(.name | test("ServiceNow"; "i"))' tools.json

# Check what adapters/integrations are available (unchanged from platform basics)
GET /health/adapters
GET /integrations

# Check what LLM provider profiles already exist
GET /model-registry-service/profiles

# Check what provider types are supported on this deployment
GET /model-registry-service/providers
```

### Step 3: Set up a project

Agents cannot exist without a project. Check for an existing one first — don't create a new project per agent unless the use case genuinely needs isolated GBAC:

```bash
GET /agent-project-service/projects?search=<keyword>
```

If none fits:
```
POST /agent-project-service/projects
```
```json
{
  "name": "Network Operations",
  "description": "Agents that monitor and remediate network device health"
}
```
Response: the created project, including its `_id` (UUID) — you'll need this for every agent you create inside it. The creator becomes the sole `owner` by default; add other members via `PATCH` if others need edit access (see API Reference below).

### Step 4: Set up an LLM provider profile

Skip this if a suitable profile already exists (`GET /model-registry-service/profiles`) — profiles are meant to be shared across agents, not created per-agent.

```bash
# 1. Confirm the provider type and its required credential fields
GET /model-registry-service/providers/anthropic

# 2. (Optional) Validate the credential and preview available models before saving anything
POST /model-registry-service/providers/anthropic/fetch-models
```
```json
{ "credential": { "type": "anthropic", "apiKey": "sk-ant-..." } }
```
```bash
# 3. Create the profile — this is the actual "register a provider" step
POST /model-registry-service/profiles
```
```json
{
  "profile": {
    "category": "direct",
    "name": "Production Anthropic",
    "provider": "anthropic",
    "credential": { "type": "anthropic", "apiKey": "sk-ant-..." },
    "models": [
      { "name": "claude-opus-4-6-20260201" },
      { "name": "claude-sonnet-4-6-20260201" }
    ],
    "builderGroups": []
  }
}
```
Response includes `id` (the profile UUID — this is `provider.profile` on an agent) and `models[]`, each with its own `id` (UUID — this is `provider.model`). **Save both UUIDs** — Step 8 needs them.

### Step 5: Plan the agent

1. **Which tools does the agent need?** Search your pulled `tools.json` for matching capabilities.
2. **What's the execution flow?** Map out the steps: "first get device info, then check config, then create ticket if needed."
3. **What inputs vary between runs?** These become `inputSchema` properties — e.g., a device name or ticket priority the caller supplies at session-start time.
4. **Who can run it?** Decide `operators` (specific accounts/groups who can invoke this agent regardless of their project role) vs. relying on project `editor`/`owner` access.

### Step 6: Write the instructions and input schema

**`instructions`** (a single string, not a chat array) — tell the agent WHO it is and HOW to work: its role, what tools are available and when to use each, expected output format, and constraints (read-only, require approval, etc.).

**`inputSchema`** — a strict, flat contract for what a caller must supply when starting a session:
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
Only `string` and `number` property types are allowed — `additionalProperties` must be `false` — `required` lists which of the declared properties are mandatory. This is a real function-signature-style contract now, not a free-form context bag — the platform validates session inputs against it.

### Step 7: Test tools before wiring them to the agent

Don't give an agent a tool you haven't tested yourself — every tool wraps a real platform API call.

```bash
# Look up the tool's registry entry (schema/description the LLM will see)
GET /tools/{referenceId}

# Test the underlying endpoint directly — same as testing any platform call, independent of FlowAI:
# Adapter:     POST /ServiceNow/createChangeRequest   {"body": {...}}
# App:         POST /configuration_manager/getDevice  {"name": "IOS-CAT8KV-1"}
# IAG service: POST /gateway_manager/v1/gateways/{clusterId}/services/{serviceName}/run  {"params": {...}}
# Workflow:    POST /operations-manager/jobs/start     {"workflow": "...", "options": {...}}
```
Look up the exact route and request body from `openapi.json` (`jq '.paths | keys[] | select(contains("<adapter-or-app-name>"))' openapi.json`) the same way you would for any platform call — this step doesn't depend on FlowAI at all. If the direct call fails, the agent will fail too; fix the inputs first.

**If the tool's native schema is too broad or the LLM keeps sending wrong/incomplete inputs**, create a decorator (Step 9) — but only after confirming the native tool actually works when called correctly.

### Step 8: Create the agent

```
POST /agent-project-service/projects/{projId}/agents
```
```json
{
  "name": "network-ops-agent",
  "description": "Monitors device health and creates ServiceNow tickets for issues",
  "instructions": "You are a network operations agent. Check device health using the available tools and create a ServiceNow ticket for any device that is unreachable. Use the exact device name provided — do not guess or reformat it.",
  "inputSchema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["deviceName"],
    "properties": { "deviceName": { "type": "string" } }
  },
  "provider": {
    "profile": "<profile-uuid-from-step-4>",
    "model": "<model-uuid-from-step-4>"
  },
  "tools": [
    { "referenceId": "<referenceId-for-sendCommand>" },
    { "referenceId": "<referenceId-for-createChangeRequest>" }
  ],
  "operators": []
}
```
Requires editor/owner GBAC role on the project. Response is the created Agent Definition, including its `_id` (UUID) — needed to start sessions in Step 9.

### Step 9: (Optional) Attach a decorator to a tool

Only if Step 7 revealed the native tool schema causes bad inputs:
```
POST /tools/decorators
```
```json
{
  "toolDecorator": {
    "referenceId": "<referenceId-for-createChangeRequest>",
    "name": "network-ops-change-request",
    "description": "Requires team-specific fields for network ops change requests",
    "toolDescription": "Creates a ServiceNow change request for a network device issue.",
    "toolInputSchema": {
      "type": "object",
      "properties": {
        "body": {
          "type": "object",
          "properties": {
            "short_description": { "type": "string", "description": "One-line summary, e.g. 'IOS-CAT8KV-1 unreachable'" },
            "summary": { "type": "string", "description": "Full description of the issue" }
          },
          "required": ["short_description", "summary"],
          "additionalProperties": false
        }
      },
      "required": ["body"],
      "additionalProperties": false
    }
  }
}
```
Response contains the created `decoratorId` (24-char hex). **The decorator replaces the entire input schema the LLM sees for that tool** — any field you omit will never be sent, even if the underlying adapter requires it. Test the tool directly first (Step 7) to find every required field, then include all of them.

Attach it to the agent by adding `decoratorId` to that tool's entry (via `PATCH`, using `decorateTools` — see API Reference):
```json
{ "decorateTools": [{ "referenceId": "<referenceId-for-createChangeRequest>", "decoratorId": "<24-char-hex>" }] }
```

### Step 10: Run the agent and check the result

```
1. POST /agent-session-manager/sessions        → { agentDefinitionId, inputs }
2. GET  /agent-session-manager/sessions/{id}   → poll `status` until COMPLETE/FAILED/CANCELED
3. GET  /agent-session-manager/sessions/{id}/messages → see what it actually did
```

**When a session fails, debug like this:**

1. **Check the session** — `GET /agent-session-manager/sessions/{sessionId}`
   - `status` — `FAILED` means an unrecoverable error; check `errorMessage`/`errorCategory`
   - `iterationCount` / `totalToolCallCount` — very high numbers suggest looping or confusion
   - `totalInputTokens` / `totalOutputTokens` — cost/context tracking
2. **Read the activity log** — `GET /agent-session-manager/sessions/{sessionId}/messages` — chronological `AGENT_REASONING` / `TOOL_CALLED` / `AGENT_STATUS` events. Find the `tool-execution` event that failed.
3. **Get the untruncated detail** — `GET /agent-session-manager/sessions/{sessionId}/messages/{eventId}` for the failing event, using its `eventId` from step 2.
4. **Test that tool directly** — same as Step 7 — call the underlying endpoint with the same parameters the agent used.
5. **Fix the instructions** — if the agent passed wrong parameters, add explicit guidance: *"The device name for getDevice is the exact name like 'IOS-CAT8KV-1', not an IP address."*
6. **Re-run** — `PATCH` the agent if instructions changed, then `POST /agent-session-manager/sessions` again with the same inputs.

**Common issues and fixes:**

| Problem | Cause | Fix |
|---------|-------|-----|
| Tool execution fails | Wrong parameters | Test tool directly (Step 7), check openapi for correct inputs, update `instructions` or add a decorator |
| Agent calls wrong tool | Unclear objective | Be more specific in `instructions` about what to do and when |
| Agent loops (`iterationCount` high) | Too many tools or vague instructions | Reduce the `tools` array, add step-by-step guidance in `instructions` |
| Session input validation error | Inputs don't match `inputSchema` | Check `required`/`properties`/`additionalProperties` — only `string`/`number` types allowed |
| Agent doesn't use a tool | Tool not in `tools` array or instructions don't mention it | Add the tool's `referenceId`, mention it by purpose in `instructions` |
| Session stuck in `PENDING`/`RUNNING` | Long-running tool call, or a stuck external tool executor | `POST /agent-session-manager/sessions/{sessionId}` with `{"action":"CANCEL"}` |
| High token usage | Agent is exploring too many options | Constrain with "use ONLY these tools, in this order" in `instructions` |

### How the agent runs

1. Session Manager resolves `agentDefinitionId` → fetches instructions, provider/model, resolved+decorated tools from Agent Project Service and Model Registry Service
2. Session Manager hands a fully-materialized definition to the Agent Execution Engine, which starts the inference loop (internal call — not made directly by users)
3. The LLM decides which tool(s) to call based on the objective and `inputs`
4. Tool execution happens **asynchronously and externally** — the engine dispatches a tool call, an external executor runs it and persists the result, then calls back into the engine with a receipt (tracked via Tool RPC)
5. The engine fetches the actual result and feeds it back to the LLM; repeats until the objective is met or an error occurs
6. Every step is recorded as a typed session message; the session's `status` reaches a terminal state (`COMPLETE`/`FAILED`/`CANCELED`)

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

**`operators` — what it actually is:** a direct, agent-level access grant (array of 24-hex account/group IDs) letting those specific callers *operate* (run) this one agent, independent of their project role. It's additive to project GBAC, not a replacement — a project editor/owner can already operate every agent in the project; `operators` extends operate-access to accounts that otherwise wouldn't have it. This is **not** the same as the old prototype's `identity.agent_account`/`agent_password` (which was the identity the agent ran platform API calls *as*) — that execution-identity concept has no direct equivalent documented in this service; it likely now lives inside the session/execution layer.

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

**Base path:** `/tools` (top-level — distinct from the legacy `/flowai/tools`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools` | Search tools (see query params below) |
| GET | `/tools/{referenceId}` | Get a single tool |
| POST | `/tools/bulk` | Batch lookup by `referenceIds` |
| POST | `/tools/discover` | Scan the platform and register/refresh tools |

**`GET /tools` query parameters:** `skip`, `limit`, `type`, `name`, `referenceIds` (comma-separated), `description` (keyword), `active` (boolean), `parentIds`/`parentTypes`/`parentTitles` (comma-separated — tools can be hierarchical, e.g. children of an adapter instance), `excludeToolChildren` (top-level only), `sort` (`name`\|`type`\|`description`\|`source`\|`referenceId`), `order` (`asc`\|`desc`).

**Discover:**
```
POST /tools/discover
```
No body. Scans adapters, IAG services, and app methods, persisting each as a registry entry addressed by `referenceId`. Safe to re-run — refreshes the registry rather than duplicating entries.

**Note on tool identity:** the old prototype used a composite `"adapter//method"` string as the tool identifier. The GA registry addresses tools by an opaque `referenceId` — the response schema for tool objects is not formally typed in the OpenAPI spec, so **confirm the actual `referenceId` format and shape on your deployment** via a live `GET /tools` call before writing code that parses or constructs one.

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

**Create:**
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
`referenceId`, `name`, `description`, `toolDescription`, `toolInputSchema` are all required. Response contains the generated `decoratorId` (24-char hex Mongo ObjectId).

**How decorators attach to an agent:** an agent's `tools[]` entry carries an optional `decoratorId` alongside `referenceId` — decorators are looked up by ID when an agent runs, not embedded inline. This means the same decorator can be referenced by multiple agents, and `clone` lets you start from an existing decorator rather than hand-authoring overrides from scratch for a new team/use case.

**CRITICAL — same rule as the old API:** a decorator's `toolInputSchema` **replaces the entire schema the LLM sees**. Any field you omit will never be sent by the agent, even if the underlying adapter requires it. Test the tool directly (Guide Step 7) to find every required field before writing the decorator.

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

**Session object:**
```json
{
  "sessionId": "string",
  "agentDefinitionId": "string",
  "agentSnapshot": { "_id": "...", "name": "...", "instructions": "...", "namespace": { "_id": "...", "name": "..." } },
  "status": "PENDING | RUNNING | PAUSING | PAUSED | COMPLETE | FAILED | CANCELING | CANCELED",
  "startedAt": "...", "endTime": "...", "duration": 0,
  "createdAt": "...", "createdBy": "...",
  "sessionType": "root | child",
  "trigger": { "type": "eventSystem|endpoint|schedule|manual|job|session", "name": "...", "source": "..." },
  "errorMessage": "...", "errorCategory": "...",
  "iterationCount": 0, "toolGroupCount": 0, "totalToolCallCount": 0,
  "totalInputTokens": 0, "totalOutputTokens": 0,
  "inputs": {}
}
```
`agentSnapshot` is a copy of the agent's config **at session-start time** — updating the agent afterward does not retroactively change what a past session ran. `sessionType: child` implies sessions can spawn child sessions; the mechanism for that isn't exposed in this API slice — treat as informational unless you see it triggered from elsewhere.

**Start a session (async):**
```
POST /agent-session-manager/sessions
```
```json
{ "agentDefinitionId": "<agent-uuid>", "inputs": { "deviceName": "IOS-CAT8KV-1" } }
```
`inputs` must satisfy the agent's `inputSchema`. Response: `{ "sessionId": "...", "status": "PENDING" }` — returns immediately, does not wait for completion. This is the direct successor to the old async `start` call.

**Cancel / Pause / Resume:**
```
POST /agent-session-manager/sessions/{sessionId}
```
```json
{ "action": "CANCEL", "canceledBy": "<username>", "correlationId": "<for tracing>" }
```
`action` is one of `CANCEL` | `PAUSE` | `RESUME`. Response: the full updated Session object. Pause/resume have no equivalent in the old prototype API.

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
Note the field is `agent`, not `agentDefinitionId`. `terminationCallbackSignature` is an IAP cog hook invoked when the session reaches a terminal state — **the calling workflow task stays "running" until then**, which is what makes this feel synchronous from the workflow's perspective, even though the HTTP response itself returns immediately with `{sessionId, status}`. This is the GA analog to the old blocking `call` endpoint, but the "wait" happens at the workflow-engine layer, not the HTTP layer — see "Using Agents in Workflows" below.

**Activity log:**
```
GET /agent-session-manager/sessions/{sessionId}/messages?sortBy=timestamp&sortOrder=asc
```
Each message: `{ sessionId, eventId, timestamp, type, category, sequenceNumber?, text?, data }`.
- `type`: `inference-pending` | `inference-succeeded` | `inference-failed` | `tool-execution` | `agent-session-paused` | `agent-session-resumed` | `agent-session-completed` | `agent-session-failed` | `agent-session-canceled`
- `category`: `AGENT_REASONING` | `TOOL_CALLED` | `AGENT_STATUS`
- Payloads are truncated by default — fetch `GET .../messages/{eventId}` for the full, untruncated event.

### Tool Executions (Tool RPC — observability only)

**Base path:** `/tool-rpc`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tool-rpc/executions` | Search tool executions (`status`: `running`\|`complete`, paginated) |
| GET | `/tool-rpc/executions/{toolExecutionId}` | Get one tool execution's full detail |

Read-only. This is where to look up the outcome of one specific tool call an agent made, without paging through the session's full message log. Response: `{ skip, limit, total, results: [...] }` for the list; a single untyped object for the detail call.

### Agent Execution Engine (internal — do not call directly)

**Base path:** `/agent_execution_engine`. Scoped `AgentExecutionEngine.admin` only — no operator/builder role exists for it. Normal users and workflows should always go through Agent Session Manager; the Execution Engine is the internal kernel Session Manager calls on your behalf. Documented here only so session behavior (async tool dispatch, `handle-tool-response` callback pattern) makes sense when debugging — **never wire a workflow task directly to `/agent_execution_engine/*`.**

---

## Gotchas

- **`inputSchema` only allows `string`/`number` property types**, requires `additionalProperties: false`, and validates session `inputs` at start time — a session start with inputs that don't match returns a validation error, not a soft failure inside the agent run.
- **Agent create vs. update field asymmetry:** `instructions`/`inputSchema` are top-level on create, but nested under `prompt` on `PATCH`. Tool changes are a full array on create (`tools`) but deltas on update (`addTools`/`removeTools`/`decorateTools`/`authorizeTools`).
- **`provider.profile` and `provider.model` are two separate UUIDs, both required together** (`additionalProperties: false` — no inline API key, temperature, or other override at the agent level; all of that lives on the Profile).
- **Profile credentials are always masked on read** (`credential.masked: true`) — there's no way to retrieve a saved secret via the API, by design.
- **Provider type is immutable on a profile once created.** To switch providers, create a new profile and repoint agents at it — `GET /model-registry-service/profiles/{id}/agent-impact` first to see what breaks.
- **Deleting a profile is irreversible (hard delete)** — always check `agent-impact` first.
- **Deleting a project cascades to every agent inside it** — no soft-delete/recovery.
- **Updating an agent's `operators` requires the owner GBAC role**, even though other agent fields only need editor — a common source of unexpected 403s.
- **`operators` grants operate-access; it is not the old execution identity.** There's no documented equivalent of the old `identity.agent_account`/`agent_password` (what the agent runs API calls *as*) in Agent Project Service — don't assume one exists without checking the session/execution layer on your platform version.
- **Decorators replace the ENTIRE tool input schema**, not just the fields you specify. Omitting a required field means the agent will never send it, and the underlying adapter call fails with a schema validation error. Always test the tool directly first to enumerate every required field.
- **`agentSnapshot` on a session is frozen at session-start time.** Editing the agent afterward does not change what an already-running or already-completed session executed.
- **Tool execution is asynchronous and externalized** — a `tool-execution` message may sit at `inference-pending`-adjacent states for longer than you'd expect from an old-style synchronous call; check `GET /tool-rpc/executions?status=running` if a session seems stuck mid-tool-call.
- **No bulk session delete.** Unlike the old `DELETE /flowai/missions`, you must delete sessions one at a time.
- **No documented ad-hoc/ephemeral agent capability.** Every session-start path requires a saved `agentDefinitionId` — there is no "run this agent definition once without saving it" endpoint in the GA surface.
- **`run-agent`'s HTTP response is not the final answer** — it returns `{sessionId, status}` immediately just like plain `sessions` start. The "wait for the result" behavior only happens through the `terminationCallbackSignature` mechanism at the workflow-engine layer, not by blocking the HTTP call.
- **Most Agent Project Service and Tools Service responses are untyped in the OpenAPI spec** (`{"type":"object"}`). Verify exact field names against a live call before hardcoding a `$var` path in a workflow task.

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

The exact task name and available FlowAI workflow tasks depend on what's registered as a `tools`-app on your platform — confirm via `jq '.[] | select(.app == "FlowAI")' tasks.json` before wiring, since task names may not map 1:1 to the raw REST operation names shown in this skill (`runAgent` above mirrors the `POST /agent-session-manager/sessions/run-agent` operation, not a confirmed literal task name — verify against your platform's `tasks.json`).

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

**Agent-to-agent delegation has no documented GA equivalent.** The old prototype's `capabilities.agents` (call another agent by name) doesn't appear anywhere in the Agent Project Service schemas audited for this skill. If you need one agent's output to feed another, orchestrate it at the workflow level instead — run one agent's session, wait for its result via `run-agent`'s termination callback, then start the next session with that result as part of its `inputs`.

## Developer Scenarios

### 1. Set up from scratch
```
1. POST /agent-project-service/projects                        → create (or reuse) a project
2. GET  /model-registry-service/providers/{providerId}         → confirm credential fields
3. POST /model-registry-service/providers/{providerId}/fetch-models → validate credential, preview models
4. POST /model-registry-service/profiles                       → create the LLM profile, save profile+model UUIDs
5. POST /tools/discover                                        → scan platform for available tools
6. GET  /tools                                                 → review what's available, note referenceIds
7. POST /agent-project-service/projects/{projId}/agents        → create agent with tools + instructions + inputSchema
8. POST /agent-session-manager/sessions                        → run it
9. GET  /agent-session-manager/sessions/{id}                   → check status and results
```

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

### 3. Rotate or replace an LLM credential
```
1. GET  /model-registry-service/profiles/{id}/agent-impact  → see which agents use this profile
2. PATCH /model-registry-service/profiles/{id}              → update the credential (provider type stays fixed)
   { "update": { "credential": { "type": "anthropic", "apiKey": "<new-key>" } } }
3. No agent changes needed — agents reference the profile by UUID, not the credential directly
```
