---
name: itential-lcm
description: Manage resource models, instances, actions, and lifecycle execution in Itential Lifecycle Manager. Use when defining reusable service models, running actions against resource instances, or tracking action execution history.
argument-hint: "[action or resource-name]"
---

# Lifecycle Manager - Developer Skills Guide

Lifecycle Manager (LCM) provides a declarative framework for managing the lifecycle of reusable resources. Define a resource model (schema + actions), create instances of it, and run workflow-driven actions to create, update, or delete those instances — with full execution history and optional pre/post transformations.

## Concepts

- **Resource Model** — a template defining what a resource looks like (JSON Schema) and what actions can be performed on it. Actions link to workflows.
- **Resource Instance** — a concrete instantiation of a model. Stores `instanceData` conforming to the model's schema. Tracks state and last action.
- **Action** — an operation on an instance (create, update, delete, import). Each action can have a workflow, pre-transformation, and post-transformation.
- **Action Execution** — an audit record of running an action. Tracks 3 phases: preTransformation → workflow → postTransformation.
- **Instance Group** — a collection of instances (manual list or dynamic filter) for bulk operations. Requires `LCM_GROUPS_ENABLED=true`.

## Gotchas

- Base path is `/lifecycle-manager` (hyphens), NOT `/lifecycle_manager` (underscores)
- Response shape is `{message, data, metadata}` — same as projects, NOT `{status, result}` like inventory manager
- Pagination metadata uses `{skip, limit, total, currentPageSize, nextPageSkip, previousPageSkip}`
- Sort requires BOTH `sort` and `order` parameters: `?sort=startTime&order=-1`. The `-` prefix syntax (`sort=-startTime`) does NOT work — returns error.
- `PUT /resources/{modelId}/instances/{instanceId}` only updates `name` and `description` — NOT `instanceData`. You must run an action to modify instance data.
- Create actions: `instance` parameter is forbidden, use `instanceName` instead
- Update/delete actions: `instance` (ID or object) is required
- Action `_id` is a 4-char hex string (same as workflow task IDs)
- Instance states: `"0001"` = Ready, `"0000"` = Error, `"0002"` = Deleted
- `DELETE /resources/{id}` does NOT delete instances by default — pass `?delete-associated-instances=true` to cascade
- Bulk actions and instance groups require `LCM_GROUPS_ENABLED=true` environment variable
- **Action workflows MUST output a job variable named `instance`** containing the instance data. Without it, the action fails validation with "workflow does not output a value for 'instance'". Use a `merge` task to build the instance object and wire outgoing to `$var.job.instance`.
- **Create action — instance merge must cover every `schema.required` field.** If the merge task's `data_to_merge` omits even one field listed in the model's `schema.required` array, the platform writes all provisioned cloud/network resources first and THEN fails the instance write — leaving those resources orphaned from LCM with no tracked state. Before building the merge task, read the model's required fields: `jq '.schema.required' helpers/assets/lcm/<model>.json`. Every required field must have a corresponding key in `data_to_merge`.
- Action job type is `'resource:action'`, not `'automation'`
- Transformations are Jinja2 templates referenced by template ID (`preWorkflowJst` / `postWorkflowJst`)

## API Reference

**Base Path:** `/lifecycle-manager`

### Resource Models

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/lifecycle-manager/resources` | Create a new resource model |
| GET | `/lifecycle-manager/resources` | List resource models (searchable) |
| GET | `/lifecycle-manager/resources/{id}` | Get a single resource model |
| PUT | `/lifecycle-manager/resources/{id}` | Update a resource model |
| DELETE | `/lifecycle-manager/resources/{id}` | Delete a resource model |
| POST | `/lifecycle-manager/resources/import` | Import a resource model |
| GET | `/lifecycle-manager/resources/{modelId}/export` | Export a resource model |
| POST | `/lifecycle-manager/resources/{modelId}/edit` | Auto-generate action workflows and transformations |
| POST | `/lifecycle-manager/resources/{modelId}/actions/validate` | Validate action definitions |

**Create a resource model:**
```
POST /lifecycle-manager/resources
```
```json
{
  "name": "Network Service",
  "description": "Manages network service lifecycle",
  "schema": {
    "$id": "network-service",
    "type": "object",
    "required": ["service_name", "vlan_id"],
    "properties": {
      "service_name": {"type": "string"},
      "vlan_id": {"type": "integer"},
      "status": {"type": "string", "enum": ["provisioned", "active", "decommissioned"]}
    }
  },
  "actions": [
    {
      "_id": "a1b2",
      "name": "Provision",
      "type": "create",
      "workflow": null,
      "preWorkflowJst": null,
      "postWorkflowJst": null
    },
    {
      "_id": "c3d4",
      "name": "Update Config",
      "type": "update",
      "workflow": null,
      "preWorkflowJst": null,
      "postWorkflowJst": null
    },
    {
      "_id": "e5f6",
      "name": "Decommission",
      "type": "delete",
      "workflow": null,
      "preWorkflowJst": null,
      "postWorkflowJst": null
    }
  ]
}
```

- `schema` — JSON Schema (draft-07) defining valid instance data
- `actions[]._id` — 4-char hex ID (same convention as workflow task IDs)
- `actions[].type` — `"create"`, `"update"`, `"delete"`, or `"import"`
- `actions[].workflow` — workflow ID to execute (set after creating the workflow, or use the edit endpoint to auto-generate)
- `actions[].preWorkflowJst` / `postWorkflowJst` — template IDs for Jinja2 transformations before/after the workflow

**Response:**
```json
{
  "message": "Successfully created resource model",
  "data": {
    "_id": "687fe493ef863896dcba8d78",
    "name": "Network Service",
    "schema": {...},
    "actions": [...],
    "created": "2026-03-04T...",
    "createdBy": "user@example.com"
  },
  "metadata": {}
}
```

**Auto-generate action workflows:**
```
POST /lifecycle-manager/resources/{modelId}/edit
```
```json
{
  "editType": "generate-action-workflow",
  "actionId": "a1b2"
}
```
Edit types: `generate-action-workflow`, `generate-action-pre-transformation`, `generate-action-post-transformation`

**Delete with cascade:**
```
DELETE /lifecycle-manager/resources/{id}?delete-associated-instances=true
```

### Resource Instances

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/lifecycle-manager/resources/{modelId}/instances` | List instances (searchable) |
| GET | `/lifecycle-manager/resources/{modelId}/instances/{instanceId}` | Get a single instance |
| PUT | `/lifecycle-manager/resources/{modelId}/instances/{instanceId}` | Update instance name/description only |
| POST | `/lifecycle-manager/resources/{modelId}/instances/import` | Import an instance |
| GET | `/lifecycle-manager/resources/{modelId}/instances/{instanceId}/export` | Export an instance |

**Instance structure:**
```json
{
  "_id": "687fea14ef863896dcba8d79",
  "name": "customer-portal",
  "description": "Customer portal service",
  "modelId": "687fe493ef863896dcba8d78",
  "instanceData": {
    "service_name": "customer-portal",
    "vlan_id": 100,
    "status": "active"
  },
  "stateId": "0001",
  "lastAction": {
    "_id": "a1b2",
    "executionId": "67d07212df84d4150b6498f7",
    "name": "Provision",
    "type": "create",
    "status": "complete"
  },
  "created": "2026-03-04T...",
  "lastUpdated": "2026-03-04T..."
}
```

**Note:** `instanceData` can only be modified by running an action — NOT by PUT. The PUT endpoint only updates `name` and `description`.

### Running Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/lifecycle-manager/resources/{modelId}/run-action` | Run an action on a single instance |
| POST | `/lifecycle-manager/resources/{modelId}/run-bulk-action` | Run an action on multiple instances |

**Run a create action (new instance):**
```
POST /lifecycle-manager/resources/{modelId}/run-action
```
```json
{
  "actionId": "a1b2",
  "instanceName": "customer-portal",
  "instanceDescription": "Customer portal service",
  "inputs": {
    "service_name": "customer-portal",
    "vlan_id": 100
  }
}
```

**Run an update/delete action (existing instance):**
```json
{
  "actionId": "c3d4",
  "instance": "687fea14ef863896dcba8d79",
  "inputs": {
    "new_vlan_id": 200
  }
}
```
- `instance` — instance ID or full instance object (required for update/delete, forbidden for create)
- `inputs` — workflow input variables (optional, passed to the action workflow)

**Response:**
```json
{
  "success": true,
  "data": {
    "executionId": "67d07212df84d4150b6498f7"
  }
}
```

**Run bulk action (requires LCM_GROUPS_ENABLED):**
```json
{
  "actionId": "c3d4",
  "instances": ["id1", "id2", "id3"],
  "inputs": {"base_config": "standard"},
  "inputOverrides": [
    {"instanceId": "id1", "inputs": {"vlan_id": 100}},
    {"instanceId": "id2", "inputs": {"vlan_id": 200}}
  ]
}
```

### Action Execution History

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/lifecycle-manager/action-executions` | List all action executions (searchable) |
| GET | `/lifecycle-manager/action-executions/{id}` | Get a single execution record |
| POST | `/lifecycle-manager/action-executions/{executionId}/cancel` | Cancel a running execution |

**Execution record:**
```json
{
  "_id": "67d07212df84d4150b6498f7",
  "modelId": "687fe493ef863896dcba8d78",
  "modelName": "Network Service",
  "instanceId": "687fea14ef863896dcba8d79",
  "instanceName": "customer-portal",
  "actionId": "a1b2",
  "actionName": "Provision",
  "actionType": "create",
  "status": "complete",
  "startTime": "2026-03-04T12:00:00Z",
  "endTime": "2026-03-04T12:00:05Z",
  "jobId": "24-char-workflow-engine-job-id",
  "progress": [
    {"_id": "preTransformation", "status": "complete"},
    {"_id": "workflow", "status": "complete"},
    {"_id": "postTransformation", "status": "complete"}
  ],
  "errors": []
}
```

Execution statuses: `running`, `complete`, `error`, `canceled`, `paused`

**Query parameters for filtering:**
- `equals[status]=complete` — exact match
- `contains[modelName]=Network` — substring match
- `in[status]=running,complete` — match any in list
- `gt[startTime]=2026-03-01` — greater than
- `sort=startTime&order=-1` — sort descending (requires BOTH `sort` and `order`)
- `skip=0&limit=25` — pagination

### Instance Groups (conditional)

Requires `LCM_GROUPS_ENABLED=true` environment variable.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/lifecycle-manager/resources/{modelId}/groups` | Create a group |
| GET | `/lifecycle-manager/resources/{modelId}/groups` | List groups |
| GET | `/lifecycle-manager/resources/{modelId}/groups/{groupId}` | Get a group |
| PATCH | `/lifecycle-manager/resources/{modelId}/groups/{groupId}` | Update a group |
| DELETE | `/lifecycle-manager/resources/{modelId}/groups/{groupId}` | Delete a group |

**Group types:**
- `manual` — explicit list of instance IDs: `{"type": "manual", "instances": ["id1", "id2"]}`
- `dynamic` — filter-based: `{"type": "dynamic", "filter": {"status": "active"}}`

## Action Execution Flow

When an action runs, it goes through 3 phases:

```
1. Pre-Transformation (optional)
   └── Jinja2 template transforms inputs before workflow

2. Workflow Execution
   └── Runs the action's linked workflow with (transformed) inputs

3. Post-Transformation (optional)
   └── Jinja2 template transforms workflow outputs
   └── Can produce/update instance data
```

Errors at any phase stop execution. Each phase has its own status tracked in the `progress` array.

## Helper Templates

**Read a real LCM action workflow before building.** The VXLAN Fabric Services project contains production LCM action workflows — they show exactly how to declare and output the required `instance` variable:

```bash
# List available LCM action workflows
jq '[.data.project.components[] | select(.type=="workflow")] | .[].document.name' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/lcm/lcm-vxlan-fabric-services-project.json

# Read a specific action workflow (e.g., Create)
jq '[.data.project.components[] | select(.type=="workflow") | select(.document.name | test("Create"; "i"))] | first | .document | {name:.name, tasks:.tasks, transitions:.transitions}' \
  ${CLAUDE_PLUGIN_ROOT}/helpers/assets/lcm/lcm-vxlan-fabric-services-project.json
```

The resource model exports (in `${CLAUDE_PLUGIN_ROOT}/helpers/assets/lcm/`) show how actions are wired to workflows — import via `POST /lifecycle-manager/resources/import`:

| File | Actions |
|------|---------|
| `lcm-vxlan-fabric-management.json` | Create Network, Re-Provision, Delete, Decommission (4/5 wired) |
| `lcm-fan-device-lifecycle-management.json` | Device Onboarding, SW Compliance, Upgrade, Decommission, and more (9/10 wired) |
| `lcm-ip-blocking-service.json` | Create, Update, Delete, Retry (fully wired) |
| `lcm-interface-service-provisioning.json` | Create, Modify, Delete (fully wired) |
| `lcm-port-turn-up.json` | Create, Delete, Service Verification, Update Service Policy (4/6 wired) |

## Developer Scenarios

### 1. Create a resource model with actions
```
1. POST /lifecycle-manager/resources                    → create model with schema + actions
2. Read model's schema.required BEFORE building Create workflow
   jq '.schema.required' helpers/assets/lcm/<model>.json  -- every field here must be in the instance merge task
3. Create workflows for each action in /itential-studio
   Create action: instance-write merge task must cover ALL schema.required fields (missing one = orphaned resources)
4. PUT /lifecycle-manager/resources/{id}                → update actions with workflow IDs
5. POST /lifecycle-manager/resources/{id}/actions/validate → verify actions are valid
```

### 2. Run the full lifecycle
```
1. POST /lifecycle-manager/resources/{id}/run-action    → create action (new instance)
2. GET  /lifecycle-manager/action-executions/{execId}   → check execution status
3. GET  /lifecycle-manager/resources/{id}/instances      → see created instance
4. POST /lifecycle-manager/resources/{id}/run-action    → update action (modify instance)
5. POST /lifecycle-manager/resources/{id}/run-action    → delete action (decommission)
```

### 3. Track and debug execution history
```
1. GET /lifecycle-manager/action-executions?equals[status]=error → find failed executions
2. GET /lifecycle-manager/action-executions/{id}        → check progress phases + errors
3. Check errors[].origin to identify which phase failed
4. Fix the workflow/transformation and re-run the action
```
