---
name: itential-golden-config
description: Build golden config trees, config specs, compliance plans, run compliance checks, grade reports, and remediate violations. Use when the user needs to define configuration standards or check device compliance.
argument-hint: "[action or tree-name]"
---

# Golden Configurations - Developer Skills Guide

Golden Configurations define the "desired state" for device configurations. They enable compliance checking, grading, and remediation of configuration drift across your network.

## Gotchas

- `deviceType` must match exactly: `"cisco-ios"` not `"Cisco IOS"` or `"ios"`
- `variables` in `PUT /configuration_manager/node/config` must be a **JSON object**, not a string
- `updateVariables` boolean is **REQUIRED** in node config update — omitting it silently skips variable merge
- Compliance run is **async** — returns `batchId`, not the report. Poll with `GET /compliance_reports/batch/{batchId}`
- Plan instance results are inside `groups[].plans[]`, not top-level
- `nodeId` in compliance plan is the **`configId`**, NOT the node name — get it from the tree version response
- Node path uses node **name** separated by `/` — root varies by tree (e.g., `base`, `Global`)
- Parser name must match the device's `ostype` or compliance parsing produces wrong results
- Parser `template` must reference an existing parser — list with `GET /configurations/parser`
- Parser lexRules are validated with `safe-regex` — unsafe patterns (catastrophic backtracking) are rejected
- Config spec regex patterns need escaped backslashes in JSON (`"\\d+"` not `"\d+"`)
- Duplicate tree names blocked — `"A tree with the name already exists"`
- Node path leading `/` is auto-stripped — `/base/DataCenter` and `base/DataCenter` are equivalent
- Creating a new tree version requires a `base` parameter specifying which version to clone from

## What is Golden Config?

Golden Config provides a hierarchical, version-controlled system for defining what device configurations should look like:

- **Trees** - Top-level containers associated with a device type (e.g., `cisco-ios`, `arista-eos`)
- **Versions** - Each tree can have multiple versions (e.g., `initial`) to evolve standards over time
- **Nodes** - Hierarchical structure within a version (e.g., `Global` → `EMEA` → `London`). Child nodes inherit from parents.
- **Config Specs** - Rules attached to each node that define required, disallowed, or informational configuration lines
- **Variables** - Tree-level variables accessible by all node templates via Jinja2 `{{ var }}` syntax
- **Configuration Parsers** - Define how raw CLI config is tokenized for comparison against config specs
- **Compliance Reports** - Results of checking device configs against golden config specs
- **Grading** - Scoring formula that produces a grade (Pass/Review/Fail) from compliance results
- **Remediation** - Auto-fix or manual remediation of compliance violations

### How Inheritance Works

```
Global (base node)
  ├── config spec: service password-encryption, aaa new-model, ntp server
  │
  ├── DataCenter
  │     ├── config spec: ip http secure-server, ip ssh version 2
  │     │
  │     └── Atlanta
  │           ├── devices: [IOS-CAT8KV-1]
  │           └── config spec: (empty or site-specific rules)
  │
  └── Branch
        └── ...
```

A device assigned to `Atlanta` is checked against **all inherited specs**: `Global` + `DataCenter` + `Atlanta`. This allows global standards at the top with site-specific overrides at the leaves.

## API Reference

**Base Path:** `/configuration_manager`

### Trees

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/configuration_manager/configs` | List all golden config trees |
| POST | `/configuration_manager/configs` | Create a new golden config tree |
| GET | `/configuration_manager/configs/{treeId}` | Get tree summary |
| GET | `/configuration_manager/configs/{treeId}/{version}` | Get tree version details (full node hierarchy) |
| PUT | `/configuration_manager/configs/{treeId}` | Update tree properties |
| PUT | `/configuration_manager/configs/{treeId}/{version}` | Update tree version properties |
| DELETE | `/configuration_manager/configs/{treeId}` | Delete a tree |
| DELETE | `/configuration_manager/configs` | Bulk delete trees by IDs |
| DELETE | `/configuration_manager/configs/{treeId}/{version}` | Delete a tree version |
| POST | `/configuration_manager/configs/{treeId}` | Create a new tree version (clone from existing) |
| POST | `/configuration_manager/search/configs` | Search trees by name/deviceType |
| DELETE | `/configuration_manager/configs/variables/{treeId}/{version}` | Delete tree-level variables |
| POST | `/configuration_manager/devices/device/trees` | Find which trees contain a specific device |
| POST | `/configuration_manager/devices/tree` | List all devices assigned to a tree |
| POST | `/configuration_manager/export/goldenconfigs` | Export a tree |
| POST | `/configuration_manager/import/goldenconfigs` | Import tree documents |

**Create a golden config tree:**
```
POST /configuration_manager/configs
```
```json
{
  "name": "Cisco IOS Baseline",
  "deviceType": "cisco-ios"
}
```
Response creates the tree with version `initial`, a root node, and an empty config spec:
```json
{
  "id": "699b70325ae7d527cda5fff0",
  "name": "Cisco IOS Baseline",
  "version": "initial",
  "deviceType": "cisco-ios",
  "root": {
    "name": "base",
    "attributes": {
      "devices": [],
      "deviceGroups": [],
      "remediationWorkflow": null,
      "configId": "699b70325ae7d527cda5ffef"
    },
    "children": []
  },
  "variables": {}
}
```

**Device types:** `cisco-ios`, `cisco-ios-xr`, `cisco-nx`, `arista-eos`, `json` (for non-CLI structured data like AWS Security Groups)

**Real-world tree example (multi-region hierarchy):**
```json
{
  "name": "Global DC",
  "deviceType": "cisco-ios",
  "root": {
    "name": "Global",
    "attributes": { "configId": "...c00", "devices": [] },
    "children": [
      {
        "name": "EMEA",
        "attributes": { "configId": "...c01" },
        "children": [
          { "name": "London", "attributes": { "configId": "...c02" }, "children": [] }
        ]
      },
      {
        "name": "North America",
        "attributes": { "configId": "...c03" },
        "children": [
          { "name": "Atlanta", "attributes": { "configId": "...c04" }, "children": [] }
        ]
      },
      {
        "name": "APAC",
        "attributes": { "configId": "...c05" },
        "children": [
          { "name": "Sydney", "attributes": { "configId": "...c06" }, "children": [] }
        ]
      }
    ]
  },
  "variables": {
    "hostname": "www.itential.io",
    "ntp_server_name": "ntp.itential.io",
    "version_regex": "\\d+\\.\\d+",
    "interfaces": [
      { "name": "Loopback101", "description": "This is a test", "ip_address": "192.1.3.1" },
      { "name": "Loopback102", "description": "This is a test loopback", "ip_address": "192.2.3.1" }
    ]
  }
}
```

### Nodes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/configs/{treeId}/{version}/{parentNodePath}` | Create a child node |
| PUT | `/configuration_manager/configs/{treeId}/{version}/{nodePath}` | Update a node |
| DELETE | `/configuration_manager/configs/{treeId}/{version}/{nodePath}` | Delete a node |
| POST | `/configuration_manager/configs/{treeId}/{version}/{nodePath}/devices` | Add devices to a node |
| DELETE | `/configuration_manager/configs/{treeId}/{version}/{nodePath}/devices` | Remove devices from a node |
| POST | `/configuration_manager/configs/devices/groups` | Add device groups to a node |
| DELETE | `/configuration_manager/configs/devices/groups` | Remove device groups from a node |

**Create a child node:**
```
POST /configuration_manager/configs/{treeId}/initial/base
```
```json
{
  "name": "DataCenter"
}
```
Response includes the auto-created config spec:
```json
{
  "name": "DataCenter",
  "attributes": {
    "devices": [],
    "deviceGroups": [],
    "remediationWorkflow": null,
    "configId": "699b705b5ae7d527cda5fff2"
  },
  "children": []
}
```

**Add devices to a node:**
```
POST /configuration_manager/configs/{treeId}/initial/base/DataCenter/Atlanta/devices
```
```json
{
  "devices": ["IOS-CAT8KV-1"]
}
```

**Node path format:** Node paths use the node `name` separated by `/`. Root varies by tree (e.g., `Global`, `base`). Example: `Global/EMEA/London`, `base/DataCenter/Atlanta`.

### Node Configuration (Template)

This is where you define the golden config rules for a node. You write config as a template string, and the platform parses it into structured config spec lines.

```
PUT /configuration_manager/node/config
```
```json
{
  "treeId": "699b70325ae7d527cda5fff0",
  "treeVersion": "initial",
  "nodePath": "base",
  "data": {
    "template": "service password-encryption\naaa new-model\n<e/>ntp server {{ ntp_server }}\n<i/>version {/ {{ version_regex }} /}\n{d/}ip domain-lookup",
    "variables": {
      "ntp_server": "ntp1.east.itential.com",
      "version_regex": "\\d+\\.\\d+"
    }
  },
  "updateVariables": true
}
```

- `template` - config text using golden config template syntax (see below)
- `variables` - **JSON object** (NOT a string) with variable values for `{{ var }}` substitutions
- `updateVariables` - **required boolean** - whether to merge variables into the tree-level variables

Response: `{"status": "success", "message": "Node Config updated"}`

The platform automatically parses the template text into structured `lines` in the config spec.

## Golden Config Template Syntax

The template uses special prefixes to control how each line is evaluated during compliance checks.

### Line Prefixes

Control `evalMode` and `severity` for each line:

| Prefix | evalMode | severity | Meaning |
|--------|----------|----------|---------|
| _(none)_ | `required` | `warning` | Line must exist on device |
| `<i/>` | `required` | `info` | Required, informational only |
| `<e/>` | `required` | `error` | Required, critical - fails compliance |
| `{i/}` | `ignored` | `warning` | Informational, not evaluated |
| `{i/}<i/>` | `ignored` | `info` | Ignored, info severity |
| `{i/}<e/>` | `ignored` | `error` | Ignored but flagged as error if found |
| `{d/}` | `disallowed` | `warning` | Line must NOT exist on device |
| `{d/}<e/>` | `disallowed` | `error` | Disallowed, critical |

### Variable and Pattern Syntax

| Syntax | Purpose | Example |
|--------|---------|---------|
| `{{ variable }}` | Jinja2 variable from tree variables | `ntp server {{ ntp_server }}` |
| `{/regex/}` | Inline regex pattern match | `hostname {/\S+/}` |
| `{/ {{ var }} /}` | Regex pattern from a variable | `version {/ {{ version_regex }} /}` where `version_regex` = `\d+\.\d+` |
| `{% for ... %}` / `{% endfor %}` | Jinja2 loop (generates lines from array variables) | See example below |
| Indentation | Nested config lines (interface children) | `interface Gi1.1\n description ...` |

### Regex as Variable

You can store regex patterns in tree variables and reference them in the template. This is useful when the same pattern is reused or needs to be configurable:

```
version {/ {{ version_regex }} /}
ip access-list extended ACL-VLAN100-IN
 10 permit tcp 10.100.1.0 0.0.0.255 any eq www
 {/ {{ acl_line_regex }} /} permit tcp 10.100.1.0 0.0.0.255 any eq 443
 30 deny ip any any log
```
With variables:
```json
{
  "version_regex": "\\d+\\.\\d+",
  "acl_line_regex": "^(10000|[1-9][0-9]{0,3})"
}
```

### Template Examples

**Global baseline (mixed evalModes):**
```
<i/>version {/\d+\.\d+/}
service password-encryption
{i/}hostname {/\S+/}
aaa new-model
aaa authentication login default local
<e/>ntp server {{ ntp_server }}
{d/}service internal
{d/}<e/>ip domain-lookup
```

**Interface blocks with nested children:**
```
<e/>interface GigabitEthernet1.1
 description reserved for dev1
<e/>interface GigabitEthernet1.2
 description reserved for dev2
```
Child lines (indented) inherit the parent's evalMode. The interface line is `required`+`error`, its child `description` line is also checked.

**Jinja2 loops for dynamic interface generation:**
```
{% for interface in interfaces %}
{i/}interface {{ interface['name'] }}
  {i/}description {{ interface['description']|upper }}
  {i/}ip address {{ interface['ip'] }} {{ interface['mask'] }}
  {i/}no shutdown
{% endfor %}
```
This generates lines for each entry in the `interfaces` array variable. Jinja2 filters like `|upper` are supported.

**Disallowed with regex:**
```
{d/}<e/>access-list 4 permit 14.126.166.15
{i/}<e/>access-list 5 permit {/192\.168\.1/}
```

## Config Specs

Config specs are the parsed representation of the template. When you update a node's template, the platform auto-parses it into a config spec with structured `lines`. You can also create/update config specs directly.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/config_specs` | Create a config spec |
| GET | `/configuration_manager/config_specs/{id}` | Get a config spec |
| PUT | `/configuration_manager/config_specs/{id}` | Update a config spec |
| POST | `/configuration_manager/config_template` | Get a rendered config spec template |
| POST | `/configuration_manager/generate/config_spec` | Build a config spec from raw device config |
| POST | `/configuration_manager/translate/config_spec` | Convert a config spec to readable string |

**Config spec structure:**
```json
{
  "id": "699b70325ae7d527cda5ffef",
  "deviceType": "cisco-ios",
  "template": "service password-encryption\naaa new-model\n<e/>ntp server {{ ntp_server }}",
  "lines": [
    {
      "id": "699b6f14c9ed5903",
      "words": [
        { "type": "literal", "value": "service" },
        { "type": "literal", "value": "password-encryption" }
      ],
      "lines": [],
      "evalMode": "required",
      "fixMode": "manual",
      "severity": "warning",
      "ordering": "none",
      "membership": "default"
    },
    {
      "id": "699b6f14dec62d74",
      "words": [
        { "type": "literal", "value": "ntp" },
        { "type": "literal", "value": "server" },
        { "type": "literal", "value": "ntp1.east.itential.com" }
      ],
      "lines": [],
      "evalMode": "required",
      "fixMode": "manual",
      "severity": "error",
      "ordering": "none",
      "membership": "default"
    }
  ]
}
```

**Word types:**
- `literal` - exact match (e.g., `service`, `password-encryption`)
- `variable` - matches any value, captures it
- `regex` - matches a regex pattern (from `{/pattern/}` or `{/ {{ var }} /}`)

**Config spec fields:**
- `evalMode` - `required`, `disallowed`, `ignored`
- `fixMode` - `manual` or `automatic`
- `severity` - `error`, `warning`, `info`
- `ordering` - `none` or `strict`
- `membership` - `default`
- `lines` - nested child lines (for hierarchical configs like interface blocks)

**JSON Specs** (for `json` device type):

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/json_specs/create` | Create a JSON spec |
| GET | `/configuration_manager/json_specs/{id}` | Get a JSON spec |
| PUT | `/configuration_manager/json_specs/{id}` | Update a JSON spec |

## Configuration Parsers

Parsers define how raw CLI configuration text is tokenized into words and lines for comparison against config specs. Different OS types need different parsing rules.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/configurations/parser` | Create a config parser |
| GET | `/configuration_manager/configurations/parser` | List all config parsers |
| POST | `/configuration_manager/configurations/parser/search` | Search for a parser |
| PUT | `/configuration_manager/configurations/parser` | Update a parser |
| DELETE | `/configuration_manager/configurations/parser` | Delete a parser |
| DELETE | `/configuration_manager/configurations/parsers` | Bulk delete parsers by ID array |
| POST | `/configuration_manager/import/parsers` | Import parser documents |

**Config parser structure:**
```json
{
  "id": "67c5c272cd98641b4bae74ad",
  "name": "a10-acos",
  "template": "cisco-ios",
  "lexRules": [
    ["(\\r\\n|\\r|\\n)", "end_line"],
    ["$", "end_line"],
    ["\"(?:[^\\\\\"\\r\\n]|\\\\.)*\"", "word"],
    ["\\S+", "word"]
  ]
}
```

- `name` - Parser name (typically matches the OS type)
- `template` - Base parser template to inherit rules from (e.g., `'cisco-ios'`). List available parsers with `GET /configuration_manager/configurations/parser`.
- `lexRules` - Array of `[regex_pattern, token_type]` pairs. Token types: `end_line`, `word`, `comment`. Patterns are validated with `safe-regex` — unsafe patterns are rejected.

## Compliance Plans

Compliance plans group golden config nodes with their target devices into a runnable plan. Running a plan triggers compliance checks for all nodes and produces a batch of reports.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/compliance_plans` | Create a compliance plan |
| GET | `/configuration_manager/compliance_plans/{planId}` | Get a compliance plan |
| PUT | `/configuration_manager/compliance_plans` | Update a compliance plan |
| DELETE | `/configuration_manager/compliance_plans` | Delete compliance plans |
| POST | `/configuration_manager/compliance_plans/run` | Run a compliance plan |
| POST | `/configuration_manager/compliance_plans/nodes` | Add nodes to a compliance plan |
| DELETE | `/configuration_manager/compliance_plans/nodes` | Remove nodes from a compliance plan |
| POST | `/configuration_manager/search/compliance_plans` | Search compliance plans |
| POST | `/configuration_manager/search/compliance_plan_instances` | Search plan run instances |
| POST | `/configuration_manager/import/plans` | Import compliance plan documents |

**Create a compliance plan:**
```
POST /configuration_manager/compliance_plans
```
```json
{
  "name": "IOS Baseline Compliance",
  "options": {
    "description": "Checks all Cisco IOS devices against the baseline golden config",
    "nodes": [
      {
        "treeId": "699b70325ae7d527cda5fff0",
        "version": "initial",
        "nodeId": "699b705b5ae7d527cda5fff3",
        "devices": ["IOS-CAT8KV-1"],
        "deviceGroups": [],
        "variables": {}
      }
    ]
  }
}
```

**Node fields (all required):**
- `treeId` - the golden config tree ID
- `version` - tree version (e.g., `"initial"`)
- `nodeId` - the **`configId`** of the node (NOT the node name)
- `devices` - array of device names to check
- `deviceGroups` - array of device group IDs (use `[]` if none)
- `variables` - variable overrides for this node (use `{}` if none)

**Response:**
```json
{
  "_id": "699b8c3b5ae7d527cda5fff6",
  "name": "IOS Baseline Compliance",
  "description": "Checks all Cisco IOS devices against the baseline golden config",
  "throttle": 5,
  "nodes": [
    {
      "treeId": "699b70325ae7d527cda5fff0",
      "version": "initial",
      "nodeId": "699b705b5ae7d527cda5fff3",
      "variables": {},
      "devices": ["IOS-CAT8KV-1"],
      "deviceGroups": []
    }
  ]
}
```

**Run a compliance plan:**
```
POST /configuration_manager/compliance_plans/run
```
```json
{
  "planId": "699b8c3b5ae7d527cda5fff6",
  "options": {}
}
```
Response:
```json
{
  "message": "Successfully started compliance plan.",
  "planId": "699b8c3b5ae7d527cda5fff6",
  "instanceId": "699b8c4a5ae7d527cda5fff7"
}
```

**Get plan run instance** (shows status, processed devices, batch ID):
```
POST /configuration_manager/search/compliance_plan_instances
```
```json
{
  "searchParams": {
    "instanceId": "699b8c4a5ae7d527cda5fff7"
  }
}
```
Response (plans are inside `groups[]`, not top-level):
```json
{
  "totalCount": 1,
  "groups": [
    {
      "totalCount": 1,
      "plans": [
        {
          "id": "699b8c4a5ae7d527cda5fff7",
          "name": "IOS Baseline Compliance",
          "jobStatus": "complete",
          "planId": "699b8c3b5ae7d527cda5fff6",
          "batchId": "699b8c4a5ae7d527cda5fff8",
          "started": "2026-02-22T23:07:54.697Z",
          "finished": "2026-02-22T23:07:59.735Z",
          "nodes": [
            {
              "treeId": "699b70325ae7d527cda5fff0",
              "nodeId": "699b705b5ae7d527cda5fff3",
              "status": "completed",
              "devices": ["IOS-CAT8KV-1"],
              "processedDevices": ["IOS-CAT8KV-1"]
            }
          ]
        }
      ]
    }
  ]
}
```
Use the `batchId` to retrieve compliance reports via `GET /configuration_manager/compliance_reports/batch/{batchId}`.

**Add nodes to an existing plan:**
```
POST /configuration_manager/compliance_plans/nodes
```
```json
{
  "planId": "699b8c3b5ae7d527cda5fff6",
  "nodes": [
    {
      "treeId": "699b70325ae7d527cda5fff0",
      "version": "initial",
      "nodeId": "699b705b5ae7d527cda5fff2",
      "devices": ["IOS-CAT8KV-2"],
      "deviceGroups": [],
      "variables": {}
    }
  ]
}
```

## Compliance Reports

Results of compliance checks showing what passed, what failed, and what needs remediation.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configuration_manager/compliance_reports` | Run compliance reports |
| GET | `/configuration_manager/compliance_reports/details/{reportId}` | Get a compliance report |
| GET | `/configuration_manager/compliance_reports/batch/{batchId}` | Get reports for a batch |
| POST | `/configuration_manager/compliance_reports/grade` | Get graded compliance reports for a node |
| POST | `/configuration_manager/compliance_reports/grade/history` | Get historical graded reports |
| POST | `/configuration_manager/compliance_reports/grade/single` | Grade a single report |
| POST | `/configuration_manager/compliance_reports/history` | Compliance report totals for a device |
| POST | `/configuration_manager/compliance_reports/topissues` | Get top issues from reports |
| GET | `/configuration_manager/compliance_reports/tree/{treeId}` | Summarize reports for a tree |
| GET | `/configuration_manager/compliance_reports/node/{treeId}/{nodePath}` | Summarize reports for a node |
| POST | `/configuration_manager/compliance_reports/backups` | Run compliance on backup configs |
| POST | `/configuration_manager/compliance_reports/config` | Run compliance against a raw config string |
| POST | `/configuration_manager/compliance_reports/details` | Get details of multiple reports at once |
| POST | `/configuration_manager/compliance_reports/history/backups` | Compliance report history for backups |
| POST | `/configuration_manager/compliance_reports/query/history` | Paginated grading history |

**Run compliance:**
```
POST /configuration_manager/compliance_reports
```
```json
{
  "options": {
    "treeId": "699b70325ae7d527cda5fff0",
    "version": "initial",
    "nodePath": "base/DataCenter/Atlanta",
    "devices": ["IOS-CAT8KV-1"]
  }
}
```
Response (async - compliance runs in background):
```json
{
  "status": 202,
  "message": "compliance batch 699b70d55ae7d527cda5fff4 started",
  "batchId": "699b70d55ae7d527cda5fff4"
}
```

**Run compliance against a raw config string** (without fetching from device):
```
POST /configuration_manager/compliance_reports/config
```
```json
{
  "options": {
    "treeId": "699b70325ae7d527cda5fff0",
    "version": "initial",
    "nodePath": "base/DataCenter/Atlanta",
    "deviceName": "IOS-CAT8KV-1",
    "configuration": "service password-encryption\naaa new-model\n..."
  }
}
```
Useful for testing compliance against a config you already have (e.g., from a backup or generated config) without connecting to the device.

**Get batch results** (returns array of report summaries):
```
GET /configuration_manager/compliance_reports/batch/{batchId}
```
Each entry has `id` (report ID), `batchId`, `treeId`, `nodePath`, `deviceName`, `specId`, `inheritedSpecIds`.

**Get detailed report:**
```
GET /configuration_manager/compliance_reports/details/{reportId}
```
```json
{
  "id": "699b70d95ae7d527cda5fff5",
  "deviceName": "IOS-CAT8KV-1",
  "nodePath": "base/DataCenter/Atlanta",
  "timestamp": "2026-02-22T21:03:16.136Z",
  "inheritedSpecIds": ["699b70325ae7d527cda5ffef", "699b705b5ae7d527cda5fff2"],
  "totals": {
    "errors": 1,
    "warnings": 2,
    "infos": 0,
    "passes": 7
  },
  "issues": [
    {
      "severity": "error",
      "type": "required",
      "message": "Required config not found",
      "spec": {
        "words": [
          {"type": "literal", "value": "ntp"},
          {"type": "literal", "value": "server"},
          {"type": "literal", "value": "ntp1.east.itential.com"}
        ],
        "evalMode": "required",
        "severity": "error"
      }
    }
  ]
}
```

**Report fields:**
- `totals` - counts of `errors`, `warnings`, `infos`, `passes`
- `issues` - array of violations, each with `severity`, `type` (required/disallowed), `message`, and the `spec` line that failed
- `inheritedSpecIds` - parent node specs that were also evaluated (shows inheritance in action)

## Compliance Grading

Compliance reports can be graded to produce a score and letter grade.

**Scoring formula:**
```
Score = (totalNumPassLines / ((numOfErrorLines * errorWeight) + (numOfWarnLines * warnWeight) + (numOfInfoLines * infoWeight) + totalNumPassLines)) * 100
```

**Default severity weights:**
| Severity | Weight |
|----------|--------|
| Error | 2 |
| Warning | 1 |
| Info | 0.5 |

**Default grade benchmarks:**
| Grade | Minimum Score |
|-------|--------------|
| Pass | 90 |
| Review | 80 |
| Fail | 0 |

Errors count double because they represent critical compliance violations.

**Grade a report:**
```
POST /configuration_manager/compliance_reports/grade/single
```
```json
{
  "reportId": "699b70d95ae7d527cda5fff5"
}
```

## Remediation

When compliance violations are found, Configuration Manager supports auto-remediation and manual remediation.

**Workflow tasks for remediation:**
- **`runAutoRemediation`** - Automatically fix violations: `in: [complianceReportId, removeDisallowedConfig]`
- **`advancedAutoRemediation`** - Auto remediate with options: `in: [complianceReportId, removeDisallowedConfig, options]`
- **`ManualRemediation`** - Present violations for manual review: `in: [compliance_report] → out: [device, changes]`
- **`patchDeviceConfiguration`** - Apply specific changes: `in: [deviceName, changes]`

## Helper JSON Templates

| File | API Call | Description |
|------|----------|-------------|
| `create-golden-config-tree.json` | `POST /configuration_manager/configs` | Create a golden config tree |
| `update-node-config.json` | `PUT /configuration_manager/node/config` | Update node template with all syntax features |
| `create-golden-config-node.json` | `POST /configuration_manager/configs/{treeId}/{version}/{parentPath}` | Create a child node |
| `add-devices-to-node.json` | `POST /configuration_manager/configs/{treeId}/{version}/{nodePath}/devices` | Assign devices |
| `run-compliance.json` | `POST /configuration_manager/compliance_reports` | Run compliance directly (async) |
| `create-compliance-plan.json` | `POST /configuration_manager/compliance_plans` | Create a compliance plan with nodes, devices, variables |
| `run-compliance-plan.json` | `POST /configuration_manager/compliance_plans/run` | Run a compliance plan |

## Developer Scenarios

### 1. Set up golden config compliance from scratch
```
1. POST /configuration_manager/configs → create tree with {name, deviceType}
2. PUT /configuration_manager/node/config → write template with prefixes, variables, regex
3. POST /configuration_manager/configs/{treeId}/initial/base → create child nodes
4. PUT /configuration_manager/node/config → set child node templates (inherited + overrides)
5. POST /configuration_manager/configs/{treeId}/initial/{nodePath}/devices → assign devices
6. POST /configuration_manager/compliance_reports → run compliance (returns batchId)
7. GET /configuration_manager/compliance_reports/batch/{batchId} → get report IDs
8. GET /configuration_manager/compliance_reports/details/{reportId} → see totals + issues
9. POST /configuration_manager/compliance_reports/grade/single → grade the report
```

### 2. Build config spec from existing device config
```
1. GET /configuration_manager/devices/{name}/configuration → get live config
2. POST /configuration_manager/generate/config_spec → auto-generate spec from raw config
3. Use the generated spec as a starting template for your golden config node
```

### 3. Import/Export for CI/CD
```
POST /configuration_manager/export/goldenconfigs → export tree as JSON
POST /configuration_manager/import/goldenconfigs → import to another environment
```
