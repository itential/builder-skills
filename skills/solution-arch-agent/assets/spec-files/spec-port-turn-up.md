# Use Case: Port Turn-Up

## 1. Problem Statement

Port turn-up — provisioning a switch port for a new server, workstation, or appliance — is the most frequent hands-on network change in enterprise environments. Engineers receive a request (ticket, email, spreadsheet row), walk to the closet or log into the switch, configure the port, then manually update three or four systems: the ticket, the IPAM, the cable database, the monitoring tool. The configuration itself takes two minutes; the paperwork takes twenty. Mistakes happen when the port is configured correctly but the records don't match, or when the wrong port is configured because the patch panel label was misread.

**Goal:** Automate the full port turn-up lifecycle — validate the request, configure the port, verify the result, and update all surrounding systems — so the engineer submits a request and gets a working, documented port back.

---

## 2. High-Level Flow

```
Request  →  Validate  →  Pre-Check  →  Configure  →  Post-Check  →  Update Systems  →  Close Out
   │            │            │             │              │                │                 │
   │            │            │             │              │                │                 │
 Port,       Confirm      Device is     Apply L2/L3    Confirm port    Update IPAM,      Evidence
 VLAN,       port exists,  reachable,   config via     is in correct   DCIM/cable DB,    report,
 IP (if L3), VLAN valid,   capture      template,      VLAN, link up,  monitoring,       close
 device,     IP available  baseline     save config    IP responds     ticketing          ticket
 speed/duplex (if L3)                                  (if L3)
                                                           │
                                                      FAIL? → Rollback
```

---

## 3. Phases

### Request Intake
Accept the port turn-up request: target device, port name, VLAN assignment, port mode (access or trunk), speed/duplex (or auto), description. If Layer 3, include IP address and subnet. The request can come from a ticket, a form, or a CSV for bulk turn-ups. Determine if this is a new turn-up, a modification, or a decommission (port shutdown + VLAN removal).

### Validate Input
Confirm the target device exists in inventory. Confirm the port exists on the device. For access mode: confirm the VLAN exists on the device (or will be created as part of the request). For L3: confirm the IP address is available in IPAM — not assigned, not responding to ping. Reject invalid requests before touching any device.

### Pre-Check
Connect to the device. Verify reachability. Capture the current port state (admin status, operational status, VLAN assignment, speed/duplex, description, error counters). This snapshot is the rollback baseline. If the port is already in use (link up, non-default VLAN, active MAC addresses), **warn the engineer — this port may be serving another connection**.

### Configure Port
Apply the port configuration via rendered template. For access: set VLAN, description, speed/duplex, enable port. For trunk: set native VLAN, allowed VLAN list (additive), description, enable port. For L3: set IP address, subnet, description, enable port. Save the running config after changes.

### Post-Check
Verify the port configuration matches the request: correct VLAN, correct mode, correct description, link status. For L3: verify IP is reachable (ping from the device or from a test source). Check for interface errors that appeared after turn-up. If post-check fails, **rollback**.

### Rollback (conditional)
Restore the pre-check port configuration. Re-verify the port returns to its baseline state. If rollback fails, **escalate to the engineer**.

### Update External Systems
After successful post-check, update all connected systems:
- **ITSM**: update the change ticket with results and evidence
- **IPAM**: mark the IP as assigned (L3) or update the VLAN-to-port mapping
- **DCIM / cable database**: update the port record with the new connection details
- **Monitoring**: add the port to monitoring or update thresholds

Each external system update is independent — one failure does not roll back the network change or block other updates. Failed updates create follow-up tickets.

### Close Out
Generate an evidence report: request details, pre/post port state, configuration applied, external system updates, pass/fail. Close the change ticket.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Validate before touching the device | Reject bad requests early | Prevents partial deployments from invalid data |
| Warn on in-use ports, don't block | Engineer decides whether to proceed | Automation can't know if the existing connection is decommissioned but not cleaned up |
| External system updates are non-blocking | One IPAM failure doesn't roll back the port | The port config is the primary objective; record-keeping failures create follow-up tickets |
| Config rendered from template, not raw CLI | Template per device OS/role | Consistent config across the fleet, testable before deployment |
| IP availability checked via IPAM + ping | Belt and suspenders | IPAM may be stale; ping catches IPs in use but not in IPAM |
| Port decommission is the same workflow in reverse | Shutdown port, remove VLAN, release IP | One workflow handles turn-up and tear-down |

---

## 5. Scope

**In scope:** L2 access port turn-up. L2 trunk port turn-up. L3 routed port turn-up. Port modification (change VLAN, change mode). Port decommission (shutdown + cleanup). Multi-vendor (IOS, NX-OS, EOS, Junos). ITSM integration. IPAM integration. DCIM/cable DB integration. Monitoring integration. Bulk turn-up via CSV. Evidence generation.

**Out of scope:** VLAN creation (separate use case — see `spec-vlan-provisioning.md`). Physical cabling and patch panel work. PoE configuration. Port-channel / LAG provisioning (separate use case). 802.1X / NAC policy assignment. QoS policy assignment.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Wrong port configured | Disrupts existing service | Pre-check warns if port is in use (link up, active MACs) |
| VLAN doesn't exist on the device | Port goes to VLAN but no traffic flows | Validate VLAN exists during input validation |
| IP conflict (L3) | Duplicate IP, both hosts intermittent | Check IPAM + ping before assigning |
| External system update fails | Records out of sync | Non-blocking updates, follow-up tickets for failures |
| Port shows link-down after config | Physical layer issue (cable, SFP) | Post-check reports link status; not a config problem, escalate |
| Bulk turn-up cascading failure | Many ports misconfigured | Per-port success/failure tracking, abort batch on threshold |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on multi-vendor switches | Yes | Cannot proceed |
| Retrieve port status and VLAN assignments | Yes | Cannot proceed |
| Push configuration to devices via template | Yes | Cannot proceed |
| Orchestrate multi-step workflows with conditions | Yes | Cannot proceed |
| Generate reports from templates | No | Engineer documents manually |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| ITSM / ticketing | Source of request, audit trail, change tracking | No | Request comes via direct input, engineer tracks manually |
| IPAM | Validate IP availability, record assignments, track VLAN-to-port mappings | No | Engineer validates IP manually, records in spreadsheet |
| DCIM / cable management | Update port-to-device mapping, track physical connections | No | Engineer updates cable DB manually |
| Monitoring | Add port to monitoring, set thresholds, alert on errors | No | Engineer adds to monitoring manually |

### Discovery Questions

Ask the engineer before designing the solution:

1. What switch vendors and OS types are in scope? (IOS, NX-OS, EOS, Junos?)
2. What port modes do you need? (access only, trunk, L3 routed, all three?)
3. Do you have an IPAM system? Which one? Should the workflow check IP availability there?
4. Do you have a DCIM or cable management system? Should the workflow update it?
5. Do you use a ticketing system? Should the workflow create/update tickets?
6. Should the workflow add ports to monitoring after turn-up?
7. What does your port naming/description convention look like?
8. Should in-use ports block the turn-up, or just warn?
9. Do you need port decommission (reverse turn-up) in the same workflow?
10. Single port or bulk? If bulk, where does the list come from? (CSV, ticket, API?)

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One port at a time, stop on first failure | Small batch, high-risk environment |
| Parallel (per-port) | All ports at once, track per-port results | Standard — ports are independent |
| Grouped by device | All ports on one switch first, then next switch | Reduces device connections, faster for multi-port-per-switch changes |

Each port is independent — one failure does not affect other ports, even on the same device.

---

## 9. Acceptance Criteria

1. Port is in the correct VLAN and mode after turn-up
2. Port description matches the request
3. Port link status is reported (up/down — automation can't fix physical layer)
4. L3 port responds to ping after turn-up (when applicable)
5. Pre-check captures baseline state for rollback
6. Post-check confirms requested state matches actual state
7. Rollback restores baseline on any port where post-check fails
8. ITSM ticket is updated with results (when ITSM is available)
9. IPAM is updated with IP/VLAN assignment (when IPAM is available)
10. External system update failures create follow-up tickets, not rollbacks
11. Evidence report documents request, changes, verification, and external system updates
12. Bulk mode tracks per-port success/failure independently
