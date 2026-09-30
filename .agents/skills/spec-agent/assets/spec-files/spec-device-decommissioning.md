# Use Case: Device Decommissioning

## 1. Problem Statement

When a network device reaches end-of-life or is replaced, engineers must remove it from every system that knows about it: monitoring, IPAM, CMDB, inventory, device groups, and more. This is done manually, system by system, and steps get missed. The result is orphaned records — monitoring alerts for devices that no longer exist, stale IPAM reservations blocking new allocations, CMDB entries that erode trust in the inventory. Months later, someone discovers the ghost and has to figure out what happened.

**Goal:** Automate the full decommissioning lifecycle — final backup, systematic removal from all systems, archive, and close-out — ensuring no orphaned references survive.

---

## 2. High-Level Flow

```
Validate    →  Final     →  Remove from   →  Remove from  →  Remove from  →  Archive   →  Close
Device        Backup       Monitoring       IPAM            Inventory       & Cleanup     Out
   │            │               │               │               │               │           │
   │            │               │               │               │               │           │
 Confirm     Take final      Remove          Release         Remove from    Archive       Update
 device      config &        device from     all IP          CMDB, remove   configs,      ticket,
 exists,     state           monitoring,     addresses,      from device    record        generate
 get all     backup,         confirm no      subnets,        groups, mark   final         evidence
 current     record          active alerts   DNS records     as decom'd     state         report
 refs        serial/asset    remain          remain
```

---

## 3. Phases

### Validate Device
Confirm the device exists in inventory and is the correct device (match hostname, serial number, or asset tag). Gather all current references: which monitoring groups include it, what IPs are assigned, what device groups it belongs to, what CMDB records exist. This reference list drives the removal phases. If the device cannot be found, **stop — do not guess**.

### Final Backup
Take a final configuration backup and capture the device state (interfaces, routing table, inventory/serial info). This is the last known good state and must be preserved for audit purposes. Label this backup explicitly as "decommission final." If backup fails because the device is already unreachable, **log the failure but continue** — the device may already be powered off.

### Remove from Monitoring
Remove the device from the monitoring system. Confirm it is no longer being polled. Verify no active alerts remain for this device. If removal fails, **retry once, then flag for manual cleanup** — do not leave a device being monitored that no longer exists.

### Remove from IPAM
Release all IP address reservations associated with the device. Remove any DNS records pointing to the device. Confirm the addresses are returned to the available pool. If partial removal occurs (some IPs released, some not), **log what succeeded and what failed** — do not leave ambiguous state.

### Remove from Inventory
Remove the device from the CMDB or inventory system. Remove it from all device groups it belongs to. If the organization's policy is to mark as decommissioned rather than delete, update the status instead. Confirm no active references remain in any group.

### Archive and Cleanup
Move all configuration backups to long-term archive storage. Record the decommission date, the engineer who authorized it, and the final device state. Remove any temporary files or staging data created during the process.

### Close Out
Update or close the decommission ticket. Generate an evidence report listing every system the device was removed from, what was archived, and any items that require manual follow-up. Include the full reference list from the validate phase and the removal confirmation from each phase.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Validate collects all references first | Build a removal checklist before starting | Ensures nothing is missed |
| Final backup is attempted but not a hard gate | Continue if device is unreachable | Device may already be powered down |
| Each removal phase confirms success | Not just fire-and-forget | Orphaned references are the core problem to solve |
| Partial failures are logged, not hidden | Report shows what succeeded and what needs manual cleanup | Transparency over silent failure |
| Archive before delete | Configs preserved in long-term storage | Audit and forensic needs |
| Device groups cleaned up explicitly | Not just CMDB removal | Group membership is often a separate system |

---

## 5. Scope

**In scope:** Device validation, final config/state backup, removal from monitoring, IPAM, DNS, CMDB/inventory, device groups. Config archival, evidence generation, ticket management.

**Out of scope:** Physical decommissioning (rack-and-stack removal). Cable management updates. License reclamation. Circuit decommissioning (separate use case). Asset disposal tracking. Power and cooling adjustments.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Wrong device decommissioned | Production outage | Validate with serial number or asset tag, not just hostname |
| Removal from one system fails | Orphaned reference persists | Per-system confirmation, clear report of what failed |
| Device still handling traffic | Service interruption | Pre-check for active sessions, routing adjacencies, or traffic counters |
| IPAM records not fully released | Address space leak | Enumerate all IPs from device before removal, verify each is released |
| Backup fails, no archive | Audit gap | Attempt backup, log failure, check if recent backups exist in archive |
| Device group membership missed | Stale group references | Enumerate all group memberships during validate phase |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Query device inventory and retrieve device details | Yes | Cannot proceed |
| Backup device configurations | Yes | Cannot proceed (attempt is mandatory even if it fails) |
| Remove or update records in external systems via API | Yes | Cannot proceed |
| Orchestrate multi-step processes with error handling | Yes | Cannot proceed |
| Generate reports from structured data | Yes | Cannot proceed |
| Archive files to long-term storage | No | Engineer archives manually |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| CMDB / inventory | Remove device record or mark as decommissioned | Yes | Cannot ensure clean decommission |
| Monitoring (e.g., Nagios, Zabbix, SolarWinds) | Remove device from polling | No | Engineer removes manually, log as follow-up |
| IPAM (e.g., Infoblox, NetBox) | Release IP reservations, remove DNS | No | Engineer releases manually, log as follow-up |
| ITSM / ticketing (e.g., ServiceNow) | Track the decommission request | No | Engineer tracks manually |
| Archive storage | Long-term config backup retention | No | Configs remain in primary backup system |

### Discovery Questions

Ask the engineer before designing the solution:

1. What systems does this device exist in? (monitoring, IPAM, CMDB, others?)
2. How do you identify the device uniquely? Hostname, serial number, asset tag?
3. Is the device still reachable, or has it already been powered off?
4. Should the device record be deleted or marked as decommissioned in the CMDB?
5. Are there DNS records that need to be removed?
6. What device groups does this device belong to?
7. Where should archived configs be stored? How long must they be retained?
8. Is there an active ticket, or should one be created?
9. Is this a single device or a batch decommission?
10. Are there dependent devices or circuits that must be decommissioned together?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One device at a time, full lifecycle per device | Small batch, careful audit trail per device |
| Grouped | Batch devices by site or role, process each group together | Site decommission, hardware refresh |
| Parallel | Multiple devices simultaneously, independent removal | Lab teardown, large-scale decommission |

For batch runs, generate a summary report showing per-device status: fully decommissioned, partially decommissioned (with details of what remains), or failed.

---

## 9. Acceptance Criteria

1. Device identity is confirmed before any removal begins
2. Final configuration backup is attempted and result is recorded
3. Device is removed from monitoring and no active alerts remain for it
4. All IP addresses are released and DNS records are removed
5. Device is removed from CMDB/inventory or marked as decommissioned per policy
6. Device is removed from all device groups
7. Configs are archived to long-term storage
8. Evidence report lists every system touched, every action taken, and any manual follow-ups required
9. No orphaned references remain in any integrated system
