---
name: itential-devices
description: Manage network devices, backups, diffs, device groups, and device templates in Itential Configuration Manager. Use when the user needs to work with device inventory, configs, or backups.
argument-hint: "[device-name or action]"
---

# Configuration Manager - Developer Skills Guide

Configuration Manager is the Itential Platform application for managing devices, their configurations, and compliance. It provides the tools to retrieve, back up, apply, and diff device configurations.

For Golden Configurations, compliance, and grading, use `/itential-golden-config`.

## Gotchas

- `POST /configuration_manager/devices` is a **POST**, not GET — requires `{"options": {...}}` body
- Device list is in the **`list`** field, not `devices` or `results`
- Backup response returns `{status, message, id}` — the `id` is the backup's MongoDB insertedId
- Apply config body has nested structure: `{"config": {"device": "...", "config": "..."}}` — config inside config
- Diff endpoint is **PUT** `/configuration_manager/lookup_diff`, not POST. Supports `options.type`: `'line'`, `'word'` (default), `'char'`
- Create group: `/devicegroup` (singular), list groups: `/deviceGroups` (plural)
- `deviceNames` in create group is a **comma-separated string**, NOT an array: `"dev1, dev2"`
- `provider` in backup can be a string OR an array depending on the adapter
- Empty device config → backup silently not created (returns error, no backup stored)
- Large configs auto-stored in GridFS — `rawConfig` field is empty in the document, config is in GridFS
- Cannot delete device groups referenced by a Compliance Plan or Golden Config — deletion is blocked
- Device group update only accepts: `name`, `devices`, `description`, `gbac` — other fields silently dropped
- Duplicate group names blocked on create and rename
- `searchDeviceGroups` caps page size at 100 regardless of requested limit
- `getDeviceGroupById` accepts both ID and name — auto-detects which one you passed
- Device template apply checks OS type compatibility — fails if device `ostype` doesn't match template's `deviceOSTypes`
- Backup search uses regex by default — set `options.regex: false` for exact matching

## What is Configuration Manager?

Configuration Manager handles the full lifecycle of device configuration:

- **Devices** - Inventory of network devices discovered through adapters, with the ability to retrieve, back up, and apply configurations
- **Device Groups** - Logical groupings of devices for bulk operations
- **Template Designer** - Reusable Jinja2 config templates that can be applied to devices
- **Backups & Diff** - Backup device configs and compare versions to see what changed
- **Golden Configurations** - Use `/itential-golden-config` for trees, config specs, compliance, grading, and remediation

### How They Connect

```
Devices ──────────────────────────────────────────────────┐
   │                                                       │
   ├── belong to Device Groups                             │
   │                                                       │
   ├── configs can be backed up and diffed                 │
   │                                                       │
   ├── Device Templates can be applied to devices          │
   │                                                       │
   ├── are assigned to Golden Config tree nodes             │
   │        │                                              │
   │        └── See /itential-golden-config for full details  │
   │                                                       │
   └── Compliance runs compare device config ◄─────────────┘
        against Config Specs → produce Compliance Reports
```

## API Reference

**Base Path:** `/configuration_manager`
**Authentication:** Bearer token (OAuth), Query token, Basic Auth, or Cookie

### Devices

Devices are discovered through adapters (e.g., IAG, Cisco DNA). Configuration Manager can retrieve, back up, and apply configurations to them.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/devices` | Find devices with filtering and pagination |
| GET | `/configuration_manager/devices/{name}` | Get device details by name |
| GET | `/configuration_manager/devices/{name}/configuration` | Get current device configuration |
| POST | `/configuration_manager/devices/{deviceName}/configuration` | Apply a config to a device |
| POST | `/configuration_manager/devices/backups` | Backup device configuration |
| POST | `/configuration_manager/backups` | Search/list backups with filtering and pagination |
| GET | `/configuration_manager/backups/{id}` | Get a backup by ID |
| PUT | `/configuration_manager/backups/{id}` | Update backup metadata (description, notes) |
| DELETE | `/configuration_manager/backups` | Delete backups by array of IDs |
| GET | `/configuration_manager/devices/{name}/isAlive` | Check if device is connected |

**Get device details:**
```
GET /configuration_manager/devices/IOS-CAT8KV-1
```
```json
{
  "name": "IOS-CAT8KV-1",
  "device-type": "network_cli",
  "ipaddress": "10.1.8.80",
  "port": 22,
  "ostype": "cisco-ios",
  "chosenAdapter": "AutomationGateway",
  "origin": "AutomationGateway"
}
```

**Find devices with filtering:**
```
POST /configuration_manager/devices
```
```json
{
  "options": {
    "filter": { "name": "" },
    "start": 0,
    "limit": 25,
    "sort": [{ "name": 1 }],
    "order": "ascending"
  }
}
```

**Options fields:**
- **`limit`** (integer, required) - max results to return (min: 1)
- **`start`** (integer) - pagination offset (min: 0)
- **`filter`** (object) - filter by `name`, `address` (IP), `port`
- **`sort`** (array) - sort objects, e.g. `[{"name": 1}]` (1 = ascending, -1 = descending)
- **`order`** (string) - `"ascending"` or `"descending"`
- **`adapterType`** (array) - filter by adapter type, e.g. `["AnsibleManager", "NSO"]`
- **`adapterId`** (array) - filter by adapter instance ID
- **`exactMatch`** (boolean) - `true` for exact match, `false` for partial/contains match

**Response:**
```json
{
  "entity": "device",
  "total": 24,
  "unique_device_count": 24,
  "return_count": 24,
  "start_index": 0,
  "list": [
    {
      "name": "IOS-CAT8KV-1",
      "device-type": "network_cli",
      "ipaddress": "10.1.8.80",
      "port": 22,
      "ostype": "cisco-ios",
      "host": "AutomationGateway",
      "chosenAdapter": "AutomationGateway"
    }
  ]
}
```
Note: devices are in the **`list`** field, not `devices`.

**Get device config response:**
```json
{
  "device": "IOS-CAT8KV-1",
  "config": "! Last configuration change at ...\nversion 17.15\nservice timestamps debug datetime msec\n..."
}
```
The `config` field contains the full running configuration as a string.

**Backup device config:**
```
POST /configuration_manager/devices/backups
```
```json
{
  "name": "IOS-CAT8KV-1",
  "options": {
    "description": "Pre-change backup",
    "notes": "Backup before port turn-up"
  }
}
```
Response:
```json
{
  "status": "success",
  "message": "Device IOS-CAT8KV-1 backed up successfully",
  "id": "699b69e25ae7d527cda5ffe4"
}
```
The `id` field is the backup's MongoDB ID — use it to retrieve the backup later.

**Note:** If the device returns an empty configuration, the backup is NOT created and returns an error.

**Backup structure** (GET `/configuration_manager/backups/{id}`):
```json
{
  "_id": "699b69e25ae7d527cda5ffe4",
  "name": "IOS-CAT8KV-1",
  "provider": "AutomationGateway",
  "type": "native",
  "date": "2026-02-22T20:41:06.160Z",
  "rawConfig": "...(full config text)...",
  "description": "Pre-change backup",
  "notes": "Backup before port turn-up"
}
```

Note: `provider` can be a string or array depending on the adapter. For very large configs, `rawConfig` may be empty — the config is stored in GridFS (check `storage.type === 'gridfs'`).

**Search/list backups:**
```
POST /configuration_manager/backups
```
```json
{
  "options": {
    "filter": { "name": "IOS-CAT8KV-1" },
    "start": "0",
    "limit": 25,
    "sort": { "date": -1 },
    "regex": true
  }
}
```
Response:
```json
{
  "total": 3,
  "list": [
    { "_id": "699b69e25ae7d527cda5ffe4", "name": "IOS-CAT8KV-1", "date": "...", "description": "..." }
  ]
}
```
- `options.start` must be a string (not integer)
- `options.regex` defaults to `true` (filter values use regex). Set `false` for exact matching.
- Backups are in the `list` field.

**Update backup metadata:**
```
PUT /configuration_manager/backups/{id}
```
```json
{
  "description": "Updated description",
  "notes": "Updated notes"
}
```

**Delete backups:**
```
DELETE /configuration_manager/backups
```
```json
{
  "backupIds": ["699b69e25ae7d527cda5ffe4", "699b6c745ae7d527cda5ffe8"]
}
```

**Apply config to a device** (`POST /configuration_manager/devices/{deviceName}/configuration`):

The `deviceName` is a **path parameter**, not in the body. The `config` field is an object:
```json
{
  "config": {
    "device": "IOS-CAT8KV-1",
    "config": "interface GigabitEthernet0/1\n switchport access vlan 100\n no shutdown"
  },
  "options": {}
}
```

**Compare two backups (diff):**
```
PUT /configuration_manager/lookup_diff
```
```json
{
  "id": "699b69e25ae7d527cda5ffe4",
  "nextId": "699b6c745ae7d527cda5ffe8",
  "collection": "backups",
  "nextCollection": "backups"
}
```
- `collection` - must be one of: `backups`, `nodes`, `deviceGroups`
- `nextCollection` - must be one of: `devices`, `backups`, `nodes`, `deviceGroups`
- `options` (optional) - `{"type": "word"}` where type is `"line"`, `"word"` (default), or `"char"`
- Response is an array of `[operation, text]` tuples:
  - `0` = unchanged text
  - `1` = added text
  - `-1` = removed text

**Run compliance on backups** (compare backup against golden config without touching the device):
```
POST /configuration_manager/compliance_reports/backups
```
```json
{
  "treeInfo": { "treeId": "...", "version": "initial", "nodePath": "base" },
  "backupIds": ["699b69e25ae7d527cda5ffe4"]
}
```

**DiffViewer** (workflow task for visual diff):
- Task: `ConfigurationManager.DiffViewer`
- Incoming: `compareFirstString`, `firstTitle`, `compareSecondString`, `secondTitle`, `darkMode`
- Displays a side-by-side diff for manual review in a workflow

### Device Groups

Logical groupings of devices for running bulk compliance checks, golden config assignments, and operational tasks.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/configuration_manager/deviceGroups` | List all device groups |
| POST | `/configuration_manager/devicegroup` | Create a device group |
| GET | `/configuration_manager/deviceGroups/{id}` | Get a device group by ID |
| GET | `/configuration_manager/name/devicegroups` | Get a device group by name |
| PUT | `/configuration_manager/deviceGroups/{id}` | Update a device group |
| DELETE | `/configuration_manager/deviceGroups` | Delete device groups |
| POST | `/configuration_manager/deviceGroups/{id}/devices` | Add devices to a group |
| DELETE | `/configuration_manager/deviceGroups/{id}/devices` | Remove devices from a group |
| POST | `/configuration_manager/deviceGroups/search` | Search groups with pagination |
| GET | `/configuration_manager/groups/device/{deviceName}` | Find all groups containing a device |

**Create a device group:**
```
POST /configuration_manager/devicegroup
```
```json
{
  "groupName": "Cisco Devices",
  "groupDescription": "All Cisco IOS devices in the lab",
  "deviceNames": "IOS-CAT8KV-1, IOS-CSR-AWS-1"
}
```

**Device group structure:**
```json
{
  "_id": "683a07a602c95837ccbfd39f",
  "name": "Cisco Devices",
  "devices": ["IOS-CAT8KV-1", "IOS-CSR-AWS-1"],
  "description": "",
  "created": "2025-05-30T19:31:50.069Z",
  "createdBy": "ankit.bhansali@itential.com"
}
```

### Template Designer (Device Templates)

Device templates are reusable Jinja2 configuration snippets that can be applied to devices. They store both the template text and default variable values.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/templates` | Create a device template |
| POST | `/configuration_manager/templates/search` | Search/get device templates |
| PUT | `/configuration_manager/templates` | Update a device template |
| DELETE | `/configuration_manager/templates` | Delete device templates by ID |
| POST | `/configuration_manager/templates/apply` | Apply a template to a device |
| POST | `/configuration_manager/import/templates` | Import device templates |

**Create a device template:**
```
POST /configuration_manager/templates
```
```json
{
  "name": "IOS_Subinterface_Config",
  "template": "interface GigabitEthernet1.{{ vlan_id }}\n description {{ description }}\n encapsulation dot1Q {{ vlan_id }}\n ip address {{ ip_address }} {{ subnet_mask }}",
  "variables": {
    "vlan_id": "800",
    "description": "Test Subinterface",
    "ip_address": "10.80.0.1",
    "subnet_mask": "255.255.255.0"
  }
}
```
- `template` - Jinja2 template text with `{{ variable }}` placeholders
- `variables` - default values for the template variables (used when applying without overrides)

**Response:**
```json
{
  "result": "success",
  "data": {
    "_id": "699b6b8a5ae7d527cda5ffe7",
    "name": "IOS_Subinterface_Config",
    "template": "interface GigabitEthernet1.{{ vlan_id }}\n ...",
    "variables": { "vlan_id": "800", "description": "Test Subinterface", ... },
    "deviceOSTypes": []
  }
}
```

**Apply a template to a device:**
```
POST /configuration_manager/templates/apply
```
```json
{
  "deviceName": "IOS-CAT8KV-1",
  "templateId": "699b6b8a5ae7d527cda5ffe7",
  "options": {}
}
```

**Response:**
```json
{
  "status": "success",
  "result": [{ "value": "4 Command(s) Sent." }],
  "chosenAdapter": "AutomationGateway"
}
```
The template is rendered with the stored variables and pushed to the device as CLI commands.

**Search templates:**
```
POST /configuration_manager/templates/search
```
```json
{
  "name": "IOS_Subinterface",
  "options": {}
}
```

### Import/Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/import/backups` | Import backup documents |
| POST | `/configuration_manager/import/groups` | Import device group documents |
| POST | `/configuration_manager/import/templates` | Import device config templates |

For golden config import/export, use `/itential-golden-config`.

## Developer Scenarios

### 1. Device configuration management
```
GET /configuration_manager/devices/{name} → get device details
GET /configuration_manager/devices/{name}/configuration → get current config
POST /configuration_manager/devices/backups → backup before changes
POST /configuration_manager/templates/apply → apply a template
GET /configuration_manager/devices/{name}/configuration → verify change
POST /configuration_manager/devices/backups → backup after changes
PUT /configuration_manager/lookup_diff → diff pre vs post backups
```

### 2. Create and apply a device template
```
POST /configuration_manager/templates → create template with Jinja2 text + variables
POST /configuration_manager/templates/apply → apply to device {deviceName, templateId}
Verify: GET /configuration_manager/devices/{name}/configuration
```

### 3. Golden config and compliance
Use `/itential-golden-config` for the full flow.
