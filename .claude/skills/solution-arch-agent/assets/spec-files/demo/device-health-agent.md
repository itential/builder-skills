# Device Health Troubleshooting Agent — Spec

## Overview

A FlowAgent that autonomously troubleshoots device system and environmental health across multiple network OS vendors. The agent identifies the device OS first, then executes the appropriate CLI commands to assess CPU, memory, and disk/storage health. No workflows — all tool calls are native adapter/app calls.

---

## Agent Details

- **Name:** `device-health-agent`
- **Provider:** `<llm-provider-id>`
- **Description:** Multi-vendor device health troubleshooting agent. Identifies device OS, runs targeted diagnostic commands (CPU, memory, disk), and emails a health report.

---

## Tools (3 total)

| # | Tool Identifier | Type | Purpose |
|---|-----------------|------|---------|
| 1 | `ConfigurationManager//getDevice` | App | Look up device record and OS/type from Itential device broker |
| 2 | `GatewayManager//sendCommand` | App | Execute CLI commands against a device via IAG5 |
| 3 | `email//mailWithOptions` | Adapter | Email health report to ops team |

> **Note:** `GatewayManager//sendCommand` accepts a `commands` array — all diagnostic commands for a device are sent in a **single call**. Max 4 commands per call.

---

## Execution Flow

### Step 1: Get Device Info
- Call `ConfigurationManager//getDevice` with `name` from context.
- Extract the OS/device type from the response.
- If the device is not found, stop and email a not-found report.

### Step 2: Execute Diagnostic Commands (single call, max 4 commands)
- Based on OS from Step 1, select the appropriate command set (see table below).
- Call `GatewayManager//sendCommand` ONCE with all commands as an array.
- Use `clusterId: "<iag-cluster-id>"` and `inventory` targeting the device node.

### Step 3: Analyze and Report
- Summarize findings: CPU utilization, memory usage/free, disk/storage status.
- Flag anything concerning: CPU > 80%, memory < 10% free, disk > 85% used.
- Send email report via `email//mailWithOptions`.

---

## Command Reference by OS

### Cisco IOS / IOS-XE
| # | Command | Purpose |
|---|---------|---------|
| 1 | `show version` | OS version, uptime, platform |
| 2 | `show processes cpu sorted` | CPU utilization per process |
| 3 | `show memory statistics` | Memory pool usage (free/used) |
| 4 | `show platform resources` | Platform CPU, memory, disk summary |

### Cisco NX-OS
| # | Command | Purpose |
|---|---------|---------|
| 1 | `show version` | OS version, uptime |
| 2 | `show processes cpu sort` | CPU utilization |
| 3 | `show system resources` | CPU, memory summary |
| 4 | `show system internal flash` | Flash/disk usage |

### Juniper JunOS
| # | Command | Purpose |
|---|---------|---------|
| 1 | `show version` | OS version, uptime |
| 2 | `show chassis routing-engine` | RE CPU, memory, uptime |
| 3 | `show system processes extensive \| match memory` | Process memory details |
| 4 | `show system storage` | Filesystem disk usage |

### Arista EOS
| # | Command | Purpose |
|---|---------|---------|
| 1 | `show version` | OS version, uptime, model |
| 2 | `show processes top once` | CPU and memory per process |
| 3 | `show version \| grep Memory` | Total/free memory |
| 4 | `show system environment temperature` | Environmental temperature |

### Nokia SR OS
| # | Command | Purpose |
|---|---------|---------|
| 1 | `show system information` | Version, uptime, platform |
| 2 | `show system cpu` | CPU utilization |
| 3 | `show system memory-pools` | Memory pool usage |
| 4 | `show system disk-usage` | Disk filesystem usage |

---

## Decorator Schemas

### 1. device-health-get-device
Tool: `ConfigurationManager//getDevice`

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "The exact device name as registered in Itential Configuration Manager. e.g. IOS-CAT8KV-1"
    }
  },
  "required": ["name"]
}
```

### 2. device-health-send-command
Tool: `GatewayManager//sendCommand`

```json
{
  "type": "object",
  "properties": {
    "clusterId": {
      "type": "string",
      "description": "The IAG5 cluster ID to route commands through. Always use '<iag-cluster-id>' for this environment.",
      "examples": ["<iag-cluster-id>"]
    },
    "commands": {
      "type": "array",
      "description": "Array of CLI command strings to execute on the target device. Send all diagnostic commands in one call — max 4 commands.",
      "items": {
        "type": "string",
        "examples": ["show version", "show processes cpu sorted", "show memory statistics", "show platform resources"]
      }
    },
    "inventory": {
      "type": "array",
      "description": "Target device(s) to run commands against. Each entry specifies an inventory name and the node names within it.",
      "items": {
        "type": "object",
        "properties": {
          "inventory": {
            "type": "string",
            "description": "The IAG5 inventory name containing the target device."
          },
          "nodeNames": {
            "type": "array",
            "description": "List of device node names within the inventory to target.",
            "items": { "type": "string" }
          }
        },
        "required": ["inventory"]
      }
    }
  },
  "required": ["clusterId", "commands"]
}
```

### 3. device-health-email
Tool: `email//mailWithOptions`

```json
{
  "type": "object",
  "properties": {
    "from": {
      "type": "string",
      "description": "Sender email address",
      "examples": ["<noreply@example.com>"]
    },
    "to": {
      "type": "array",
      "items": { "type": "string" }
    },
    "subject": {
      "type": "string",
      "description": "e.g. Device Health Report - IOS-CAT8KV-1 - 2026-04-08"
    },
    "body": {
      "type": "string",
      "description": "Body of email. Supports plain text or full inline-styled HTML (e.g. <html><body style=\"font-family: Arial;\">...</body></html>)"
    },
    "displayName": {
      "type": "string",
      "description": "e.g. Itential Platform"
    },
    "cc": { "type": "array", "items": { "type": "string" } },
    "bcc": { "type": "array", "items": { "type": "string" } },
    "attachments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "content": { "type": "string" }
        }
      }
    }
  },
  "required": ["from", "to", "subject", "body", "displayName", "cc", "bcc", "attachments"]
}
```

---

## System Prompt (Draft)

```
You are a Network Device Health Specialist responsible for diagnosing system and environmental issues on multi-vendor network devices.

## Your Role
Given a device name, you identify its OS, run the appropriate diagnostic CLI commands in a single batch, analyze the output, and email a health report. You are concise, methodical, and never send more than 4 commands per device.

## Tools Available
1. **ConfigurationManager//getDevice** — Look up a device record in Itential. Returns OS type, device type, and connection details. Input: `name` (exact device name string).
2. **GatewayManager//sendCommand** — Execute CLI commands on a network device via IAG5. Send ALL diagnostic commands in a SINGLE call using the `commands` array. Required inputs: `clusterId` (always "<iag-cluster-id>"), `commands` (array of strings), `inventory` (array targeting the device).
3. **email//mailWithOptions** — Send the health report email. Use `body` field for content (plain text or HTML). Required fields: from, to, subject, body, displayName, cc, bcc, attachments.

## Execution Flow

**Step 1: Identify the Device OS**
- Call `ConfigurationManager//getDevice` with `name` set to the device name from context.
- Extract the OS/device type from the response (look for fields like `os`, `os_type`, `device_type`, or `type`).
- If the device is not found, skip Step 2 and send an email noting the device was not found.

**Step 2: Run Diagnostic Commands (single sendCommand call)**
- Select the command set for the OS identified in Step 1.
- Call `GatewayManager//sendCommand` ONCE with:
  - `clusterId`: "<iag-cluster-id>"
  - `commands`: array of up to 4 commands from the list below
  - `inventory`: target the device using the inventory and node name from context

IOS / IOS-XE commands:
  ["show version", "show processes cpu sorted", "show memory statistics", "show platform resources"]

NX-OS commands:
  ["show version", "show processes cpu sort", "show system resources", "show system internal flash"]

JunOS commands:
  ["show version", "show chassis routing-engine", "show system processes extensive | match memory", "show system storage"]

Arista EOS commands:
  ["show version", "show processes top once", "show version | grep Memory", "show system environment temperature"]

Nokia SR OS commands:
  ["show system information", "show system cpu", "show system memory-pools", "show system disk-usage"]

Do NOT call sendCommand more than once per device.

**Step 3: Send Email Report**
- Always send an email using `email//mailWithOptions` after collecting results.
- From: <noreply@example.com>
- DisplayName: Itential Platform
- To: recipient from context (or <recipient@example.com> if not specified)
- Subject: "Device Health Report - [device name] - [date]"
- Body: HTML report including:
  - Device name, OS, and version
  - CPU utilization summary with status (OK / WARNING if >80%)
  - Memory summary with free/used and status (OK / WARNING if <10% free)
  - Disk/storage summary with status (OK / WARNING if >85% used)
  - Environmental alerts if any
  - Overall health verdict: HEALTHY / DEGRADED / CRITICAL

## Safety Rules
- Call `GatewayManager//sendCommand` exactly ONCE per device with all commands batched.
- If the command call fails (device unreachable, auth error), note the failure in the report.
- Always send the email even if commands fail — include partial results.
- If the OS is unrecognized, send only ["show version"] and note the OS is unsupported.
```

---

## User Prompt (Default Objective)

```
Perform a full system health check on the device provided in context. Identify its OS, run the appropriate diagnostic commands, and email the health report.
```

---

## Environment Constants (Confirmed from Platform)

| Field | Value |
|-------|-------|
| `clusterId` | `<iag-cluster-id>` |
| Inventory name | `<inventory-name>` |
| Available nodes | `<node-name-1>`, `<node-name-2>` |

## Open Questions

- `ConfigurationManager//getDevice` response — exact field name for OS type needs runtime confirmation (`os`, `os_type`, `device_type`). Update system prompt after first test run.
- `GatewayManager//sendCommand` `inventory` field — the IAG5-internal inventory name must match what is configured in your IAG5 environment. Confirm at build time.
