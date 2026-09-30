# Use Case: VLAN Provisioning

## 1. Problem Statement

VLAN changes are the most common network change in enterprise environments. Engineers create tickets, log into switches one by one, type commands, and hope they got the trunk list right. A single VLAN provisioning request can touch dozens of switches across campus and data center fabrics. The work is repetitive, error-prone, and slow. Mistakes cause outages — a wrong trunk config drops an entire floor.

**Goal:** Automate the creation, modification, and deletion of VLANs across multi-vendor switches, including trunk and access port assignment, with pre/post validation to confirm the VLAN is active and reachable end-to-end.

---

## 2. High-Level Flow

```
Request  →  Validate Input  →  Pre-Check  →  Deploy Config  →  Post-Check  →  Close Out
   │              │                │               │                │              │
   │              │                │               │                │              │
 VLAN ID,      Check VLAN ID    Verify target   Push VLAN        Confirm VLAN   Update ticket,
 name,         not conflicting,  switches are    config to        exists on all  generate
 switches,     ports exist,      reachable,      each device:     targets,       evidence
 port          adapters are      capture         create VLAN,     trunks carry   report
 assignments   healthy           current state   assign ports     it, ports are
                                                                  in correct VLAN
                                                                      │
                                                                 FAIL? → Rollback
```

---

## 3. Phases

### Request Intake
Accept the VLAN provisioning request: VLAN ID, VLAN name, target switches, port assignments (access ports and trunk ports). The request can come from a ticket, a form, or direct input. Determine the operation type — create, modify, or delete.

### Validate Input
Check that the VLAN ID is valid (1-4094, not reserved). For create: confirm the VLAN does not already exist on the target switches. For modify/delete: confirm it does exist. Verify that the specified ports exist on the target switches. If any input is invalid, **reject the request with a clear reason before touching any device**.

### Pre-Check
Connect to each target switch. Confirm reachability. Capture the current VLAN table and port assignments as a baseline. This snapshot is the rollback reference. If a switch is unreachable, **stop for that switch** — do not partially provision a VLAN across half the fabric.

### Deploy Configuration
Push the VLAN configuration to each target switch. For create: add the VLAN, assign it to access ports, add it to trunk allowed lists. For modify: update the VLAN name or port assignments. For delete: remove port assignments first, then remove the VLAN. Save the running config after changes.

### Post-Check
Verify the VLAN exists in the VLAN table on every target switch. Verify access ports are assigned to the correct VLAN. Verify trunk ports carry the new VLAN. Optionally, run an end-to-end reachability test (ping across the VLAN). If post-check fails, **rollback the changes on the failed device**.

### Rollback (conditional)
Restore the pre-check configuration snapshot on any device where post-check failed. Re-verify that the rollback succeeded. If rollback itself fails, **escalate to an engineer**.

### Close Out
Generate an evidence report: what was requested, what was configured, pre vs post state, any failures. Update the change ticket. Notify the requestor.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Input validation before any device contact | Reject bad requests early | Prevents partial deployments from invalid data |
| Per-device rollback, not all-or-nothing | Only roll back the device that failed | A working VLAN on 9 of 10 switches is better than rolling back all 10 |
| Trunk and access port assignment in same workflow | Single request, single execution | Engineers think of VLAN provisioning as one task, not three |
| Delete removes port assignments before VLAN | Ports first, VLAN second | Deleting a VLAN with active ports causes traffic drops |
| Config save after each device | Persist changes immediately | Prevents config loss on reboot |

---

## 5. Scope

**In scope:** VLAN create, modify, delete. Access port assignment. Trunk allowed-list update. Multi-switch deployment. Pre/post validation. Rollback on failure. Evidence report. ITSM integration.

**Out of scope:** SVI / Layer 3 interface creation (separate use case). Spanning tree tuning. VTP/GVRP propagation (relies on device-native protocol, not automation). QoS policy assignment to VLANs. VLAN design or IP address planning.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| VLAN ID conflict with existing VLAN | Overwrite or error | Validate VLAN does not exist before creating |
| Trunk allowed-list overwritten instead of appended | Other VLANs dropped from trunk | Use additive commands, not replace — verify syntax per vendor |
| Partial deployment across fabric | VLAN works on some switches, not others | Track per-device success, report partial state clearly |
| Port assigned to wrong VLAN | User traffic on wrong segment | Post-check verifies port VLAN assignment matches request |
| Switch unreachable mid-deployment | Inconsistent state | Pre-check reachability, abort that device if it drops |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on multi-vendor switches | Yes | Cannot proceed |
| Retrieve VLAN table and port assignments | Yes | Cannot proceed |
| Push configuration changes to devices | Yes | Cannot proceed |
| Orchestrate multi-step workflows with per-device tracking | Yes | Cannot proceed |
| Compare pre and post device state | Yes | Manual verification |
| Generate reports from collected data | No | Engineer documents manually |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| ITSM / ticketing | Source of change request, audit trail | No | Request comes via direct input |
| IPAM | Validate VLAN ID availability, reserve subnets | No | Engineer confirms VLAN ID is free manually |
| CMDB | Record VLAN-to-switch mapping | No | Mapping tracked manually or in spreadsheet |

### Discovery Questions

Ask the engineer before designing the solution:

1. What switch vendors and OS types are in scope? (IOS, NX-OS, EOS, Junos, etc.)
2. How do you manage trunk allowed lists today — additive or full replace?
3. Do you use VTP, GVRP, or manage VLANs statically per switch?
4. Is there an IPAM system that tracks VLAN assignments?
5. Do VLAN changes require a change ticket, or can they be self-service?
6. Should the workflow handle Layer 3 SVI creation, or is that a separate request?
7. What does your VLAN naming convention look like?
8. How many switches does a typical VLAN change touch?
9. Are there switches that should never be modified automatically? (e.g., core, spine)
10. Do you need end-to-end reachability testing after provisioning, or is VLAN table verification enough?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One switch at a time, stop on first failure | Small change, high-risk environment |
| Parallel (per-device) | All switches at once, track per-device results | Standard provisioning — most common for VLANs |
| Fabric-aware | Deploy to distribution/aggregation first, then access | Hierarchical campus designs where order matters |

---

## 9. Acceptance Criteria

1. VLAN exists in the VLAN table on every target switch after create
2. VLAN is removed from every target switch after delete
3. Access ports are assigned to the correct VLAN
4. Trunk ports include the VLAN in their allowed list (additive, not replacing)
5. Pre-check captures baseline state for rollback
6. Post-check confirms the requested state matches the actual state
7. Rollback restores pre-check state on any device where deployment failed
8. Evidence report documents the request, changes, and verification results
9. Invalid requests are rejected before any device is contacted
