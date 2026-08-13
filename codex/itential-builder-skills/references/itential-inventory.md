---
name: itential-inventory
description: Manage device inventories, nodes, actions, and tags in Itential Inventory Manager. Use when working with IAG5 inventory, bulk node population, or running actions against inventory devices.
argument-hint: "[action or inventory-name]"
---

# Inventory Manager - Developer Skills Guide

Inventory Manager provides centralized device and endpoint inventory for the Itential Platform. It maintains inventories of nodes (devices/targets), with actions that can be executed against them via IAG5 services. Required for IAG5 and Configuration Manager Enterprise.

## Concepts

- **Inventory** — a named collection of nodes with associated actions. Has groups for access control.
- **Node** — a device or target within an inventory. Has a name, attributes (key-value pairs like host, platform, credentials), and tags.
- **Action** — an operation that can be run against nodes. Currently only `iag5-service` type. Links to IAG services via `service_name` and `cluster_id`.
- **Tag** — a label for organizing inventories and nodes. Auto-created on first use, auto-cleaned when unused. Stored lowercase.

## Gotchas

- Response shape is `{status: "Success", result: {...}}` — extract data from `result`, not top-level
- Paginated responses inside `result` use `{data: [...], totalRecords, currentPage, pageSize, totalPages}`
- Inventories require at least one `group` — without it, creation fails
- Node names must be unique within an inventory (database constraint on `inventory_id + name`)
- `populateInventory` (bulk) **clears ALL existing nodes first** before inserting — it's a full replace, not append
- Action names must be unique within an inventory
- Only `iag5-service` action type is currently supported
- `cluster_id` resolves from `action_config.cluster_id` first, then falls back to `node.attributes.cluster_id`
- Tag names are stored lowercase — `"Core"` becomes `"core"`
- Identifiers accept both MongoDB ObjectId and name strings — auto-detected
- `createBrokerActions: true` auto-creates 4 standard actions (get-config, set-config, run-command, is-alive) — requires `defaultClusterId`

## API Reference

**Base Path:** `/inventory_manager/v1`

### Inventories

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/inventory_manager/v1/inventories` | Create a new inventory |
| GET | `/inventory_manager/v1/inventories` | List inventories with filtering and pagination |
| GET | `/inventory_manager/v1/inventories/{identifier}` | Get inventory by ID or name |
| DELETE | `/inventory_manager/v1/inventories/{identifier}` | Delete an inventory |
| GET | `/inventory_manager/v1/stats` | Get overview stats (total inventories, nodes, actions) |

**Create an inventory:**
```
POST /inventory_manager/v1/inventories
```
```json
{
  "name": "Lab Routers",
  "description": "Routers in the Atlanta Lab",
  "groups": ["Solutions Engineering"],
  "tags": ["routers", "lab"],
  "actions": [
    {
      "name": "get-config",
      "action_type": "iag5-service",
      "action_config": {
        "service_name": "get-config",
        "cluster_id": "labCluster"
      },
      "action_parameters": {}
    }
  ]
}
```
- `name` — required, must be unique
- `groups` — required, at least one group name for access control
- `tags` — optional, auto-created if they don't exist
- `actions` — optional, define operations runnable against nodes

**Or use `createBrokerActions` for standard actions:**
```json
{
  "name": "DC Switches",
  "description": "Data center switches",
  "groups": ["Solutions Engineering"],
  "createBrokerActions": true,
  "defaultClusterId": "dcCluster"
}
```
This auto-creates 4 actions: `get-config`, `set-config`, `run-command`, `is-alive` — all as `iag5-service` type pointing to the specified cluster.

**Response:**
```json
{
  "status": "Success",
  "result": {
    "_id": "697eb0fc4aef5efec3d7bbcf",
    "name": "Lab Routers",
    "groups": ["67c85954abe686cf9cb78b2e"],
    "description": "Routers in the Atlanta Lab",
    "actions": [
      {
        "name": "get-config",
        "action_type": "iag5-service",
        "action_config": {"service_name": "get-config", "cluster_id": "labCluster"},
        "action_parameters": {},
        "created_at": "2026-02-01T01:48:44.786Z",
        "created_by": "Pronghorn"
      }
    ],
    "tags": ["routers", "lab"]
  }
}
```

**List inventories with filtering:**
```
GET /inventory_manager/v1/inventories?page=1&pageSize=25&search=router&tags=core&sortField=name&sortOrder=1
```

**Query parameters:**
- `page` — page number (default 1)
- `pageSize` — results per page (default 25)
- `sortField` — field to sort by
- `sortOrder` — `1` ascending, `-1` descending
- `search` — text search across name/description
- `names` — filter by inventory names (array)
- `groups` — filter by group IDs or names
- `tags` — filter by tag names
- `minNodes` / `maxNodes` — filter by node count

**Stats:**
```
GET /inventory_manager/v1/stats
```
```json
{
  "status": "Success",
  "result": {
    "totalInventories": 1,
    "totalNodes": 2,
    "totalActions": 4
  }
}
```

### Nodes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/inventory_manager/v1/nodes` | List all nodes with filtering and pagination |
| GET | `/inventory_manager/v1/inventories/{identifier}/nodes` | List nodes for a specific inventory |
| GET | `/inventory_manager/v1/inventories/{inventoryId}/nodes/{nodeId}` | Get a single node |
| POST | `/inventory_manager/v1/nodes/bulk` | Bulk populate inventory with nodes (replaces all existing) |
| DELETE | `/inventory_manager/v1/nodes/clear/{identifier}` | Clear all nodes from an inventory |
| POST | `/inventory_manager/v1/nodes/expand` | Expand node identifiers to full documents |
| POST | `/inventory_manager/v1/nodes/filter/build` | Build filter structure for service execution |

**Bulk populate an inventory with nodes:**
```
POST /inventory_manager/v1/nodes/bulk
```
```json
{
  "inventory_identifier": "Lab Routers",
  "nodes": [
    {
      "name": "core-router-1",
      "attributes": {
        "itential_host": "10.1.1.1",
        "itential_platform": "iosxr",
        "cluster_id": "cluster_east",
        "itential_user": "$SECRET.network_devices.username",
        "itential_password": "$SECRET.network_devices.password"
      },
      "tags": ["core", "datacenter-1"]
    },
    {
      "name": "core-router-2",
      "attributes": {
        "itential_host": "10.1.1.2",
        "itential_platform": "iosxr",
        "cluster_id": "cluster_east"
      },
      "tags": ["core", "datacenter-1"]
    }
  ]
}
```
- `inventory_identifier` — inventory name or ID
- **WARNING:** This clears ALL existing nodes first, then inserts. It's a full replace, not append.
- Tags are auto-created if they don't exist
- Node names must be unique within the inventory

**Response:**
```json
{
  "status": "Success",
  "result": {
    "data": [
      {
        "_id": "697eb1be4aef5efec3d7bbd2",
        "inventory_id": "697eb0fc4aef5efec3d7bbcf",
        "name": "core-router-1",
        "attributes": {"itential_host": "10.1.1.1", "itential_platform": "iosxr", ...},
        "tags": ["core", "datacenter-1"]
      }
    ],
    "totalRecords": 2,
    "currentPage": 1,
    "pageSize": 25,
    "totalPages": 1
  }
}
```

**Node attributes:** Arbitrary key-value pairs. Common patterns:
- `itential_host` — device IP or hostname
- `itential_platform` — OS type (iosxr, ios, eos, etc.)
- `itential_user` / `itential_password` — credentials (use `$SECRET.` prefix for vault references)
- `cluster_id` — IAG cluster for this node (used as fallback if action doesn't specify one)

### Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/inventory_manager/v1/actions` | List all actions across all inventories |
| GET | `/inventory_manager/v1/inventories/{identifier}/actions` | List actions for a specific inventory |
| GET | `/inventory_manager/v1/inventories/{identifier}/actions/{actionId}` | Get a single action |
| POST | `/inventory_manager/v1/inventories/{identifier}/actions` | Create a new action |
| DELETE | `/inventory_manager/v1/inventories/{identifier}/actions/{actionId}` | Delete an action |

**Create an action:**
```
POST /inventory_manager/v1/inventories/Lab%20Routers/actions
```
```json
{
  "name": "backup-config",
  "action_type": "iag5-service",
  "action_config": {
    "service_name": "backup-config",
    "cluster_id": "labCluster"
  },
  "action_parameters": {}
}
```
- `action_type` — currently only `"iag5-service"` is supported
- `action_config.service_name` — the IAG service to call (required)
- `action_config.cluster_id` — IAG cluster (optional, falls back to node's `cluster_id` attribute)

**Action execution** (via workflow task `InventoryManager.runInventoryAction`):
- Calls `GatewayManager.runService` with the action's `service_name` and `cluster_id`
- Response is JSON-RPC wrapped (same as IAG service responses)
- Non-zero `return_code` or error status throws an error

### Tags

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/inventory_manager/v1/tags` | List all tags with pagination |
| GET | `/inventory_manager/v1/tags/accessible` | Get tags from accessible inventories only |
| GET | `/inventory_manager/v1/tags/{identifier}` | Get a single tag by ID or name |
| GET | `/inventory_manager/v1/tags/{identifier}/usage` | Get usage statistics for a tag |
| POST | `/inventory_manager/v1/tags/search` | Find inventories and nodes by tags |

**Search by tags:**
```
POST /inventory_manager/v1/tags/search
```
```json
{
  "tagIdentifiers": ["core", "datacenter-1"]
}
```
- Field is `tagIdentifiers`, NOT `tags`
- Returns `{inventories: [...], nodes: [...]}` matching the specified tags

## How It Connects to IAG

Inventory Manager is the bridge between device inventory and IAG5 services:

```
Inventory (Lab Routers)
  ├── Nodes: core-router-1, core-router-2
  │     └── attributes: host, platform, cluster_id, credentials
  │
  ├── Actions: get-config, set-config, run-command, is-alive
  │     └── each action → IAG5 service via GatewayManager.runService
  │
  └── In a workflow:
        InventoryManager.runInventoryAction
          → resolves node attributes + action config
          → calls GatewayManager.runService(serviceName, clusterId, params, inventory)
          → returns JSON-RPC response
```

To use inventory nodes in IAG workflow tasks, the `inventory` parameter in `GatewayManager.runService` takes:
```json
[{"inventory": "Lab Routers", "nodeNames": ["core-router-1"]}]
```

## RBAC

Access is controlled through groups:
- `inventory:read` — list, get, search
- `inventory:create` — create inventories, nodes, tags
- `inventory:update` — update inventories, nodes, actions
- `inventory:delete` — delete inventories, nodes, actions
- `inventory:run` — execute actions

Users must be in a group with the required role. The Pronghorn internal account bypasses authorization.

## Developer Scenarios

### 1. Create an inventory with devices and test an action
```
1. POST /inventory_manager/v1/inventories        → create with groups + createBrokerActions
2. POST /inventory_manager/v1/nodes/bulk          → populate with device nodes
3. GET  /inventory_manager/v1/inventories/{name}  → verify inventory + actions
4. In a workflow: InventoryManager.runInventoryAction on a node
5. Or via GatewayManager.runService with inventory parameter
```

### 2. Organize with tags
```
1. Create inventory with tags: ["production", "datacenter-1"]
2. Add nodes with tags: ["core", "border"]
3. POST /inventory_manager/v1/tags/search → find all "core" nodes across inventories
4. GET  /inventory_manager/v1/tags/{name}/usage → see how many inventories/nodes use a tag
```

### 3. Bulk refresh inventory from external source
```
1. Pull device list from external system (CMDB, IPAM, etc.)
2. Transform to node format: [{name, attributes, tags}, ...]
3. POST /inventory_manager/v1/nodes/bulk → replaces all nodes (WARNING: clears first)
4. Verify: GET /inventory_manager/v1/inventories/{name}/nodes
```
