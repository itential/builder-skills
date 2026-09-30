# Use Case: Circuit Provisioning (Service Turn-Up)

## 1. Problem Statement

Circuit provisioning requires coordinated configuration across two endpoints (A-side and Z-side) that must both succeed for traffic to flow. Engineers manually configure each side, test connectivity, and troubleshoot failures with no structured rollback plan. When one side fails, the other is left half-configured.

**Goal:** Automate the full circuit turn-up lifecycle — validate both endpoints, configure sequentially, verify end-to-end traffic, and roll back cleanly if anything fails — producing auditable evidence at every step.

---

## 2. High-Level Flow

```
Pre-Flight     →  Configure   →  Configure   →  Traffic        →  Close Out
(Both Sides)       A-Side         Z-Side         Verification       │
    │                │              │                │            Evidence
    │                │              │                │            report,
 Validate         Apply          Apply           Verify          update
 both devices     config,        config,          end-to-end     ticket
 are healthy,     verify         verify           data plane
 backup           A-side         Z-side
 configs          operational    operational
                                                     │
                                                FAIL? → Rollback
                                                   (Z first, then A)
```

---

## 3. Phases

### Pre-Flight (Both Sides)
Validate that both the A-side and Z-side devices are reachable, healthy, and ready for configuration. Backup the running config on each device. Confirm the target interfaces exist and are in the expected state. If either device fails pre-flight, **stop — do not configure anything**.

### Configure A-Side
Apply the circuit configuration to the A-side device. Verify the configuration was accepted and the interface is operationally correct. If A-side configuration fails, **stop — do not touch Z-side**. Roll back A-side and exit.

### Configure Z-Side
Apply the circuit configuration to the Z-side device. Verify the configuration was accepted and the interface is operationally correct. If Z-side configuration fails, **roll back Z-side first, then roll back A-side**.

### Traffic Verification
Prove end-to-end connectivity across the circuit. This means data-plane verification (ping, traceroute, or protocol neighbor adjacency), not just checking that config was applied. Compare against expected values. If traffic verification fails and retries are exhausted, **trigger rollback of both sides**.

### Rollback (conditional)
Undo configuration in reverse order: Z-side first, then A-side. Restore each device to its pre-change config. Verify each device returns to its original state. If rollback itself fails on either side, **escalate immediately**.

### Close Out
Generate an evidence report covering pre-state, applied config, post-state, and traffic test results for both sides. Update the change ticket with outcome and evidence. Report succeeds regardless of whether the circuit was provisioned or rolled back.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| A-side before Z-side (sequential) | Never configure both in parallel | If A-side fails, Z-side is untouched — simpler recovery |
| Pre-flight gates both sides | Abort if either device fails | Never half-provision a circuit |
| Rollback unwinds in reverse order | Z-side first, then A-side | Matches the order of configuration to avoid transient loops |
| Traffic verification proves data plane | Ping/traceroute/protocol adjacency, not just config check | Config can be applied correctly and still not pass traffic |
| Both sides must succeed or both roll back | No partial circuits left behind | A half-configured circuit is worse than no circuit |
| Config backup is mandatory | No backup = no provisioning | Must have a restore point for each device |
| Evidence is generated on every outcome | Success, failure, and rollback all produce reports | Audit trail is non-negotiable |

---

## 5. Scope

**In scope:** Single circuit turn-up across two endpoints, pre/post validation on both sides, sequential configuration with rollback, end-to-end traffic verification, config backup/diff, evidence generation, ITSM integration, batch provisioning of multiple circuits.

**Out of scope:** Circuit design and IP address planning (inputs to this workflow). Physical layer turn-up (fiber, cross-connects). Provider-side configuration for WAN circuits. Capacity planning. Multi-hop or multi-segment circuits requiring more than two endpoints (separate use case).

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| A-side succeeds but Z-side fails | Half-configured circuit, potential traffic black-hole | Automatic rollback of both sides in reverse order |
| Traffic verification fails despite correct config | Circuit appears down, possible physical issue | Retry with backoff; if still failing, rollback and escalate for physical investigation |
| Rollback fails on one side | One device stuck in changed state | Alert engineer immediately; do not retry indefinitely |
| Wrong interface configured | Traffic disruption on unrelated circuit | Pre-flight validates target interface state before applying config |
| Batch provisioning cascading failure | Multiple circuits left half-configured | Abort batch if failure rate exceeds threshold |
| Device unreachable mid-change | Partial config applied, unknown state | Timeout and escalate; do not attempt blind rollback |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on devices | Yes | Cannot proceed |
| Backup and diff device configurations | Yes | Cannot proceed |
| Orchestrate multi-step workflows with conditions | Yes | Cannot proceed |
| Test device reachability | Yes | Cannot proceed |
| Generate reports from templates | Yes | Cannot proceed |
| Support sequential task execution with rollback logic | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| ITSM / ticketing | Track the change, audit trail | No | Engineer tracks manually |
| IPAM | Source of truth for IP addressing | No | Engineer provides addresses as input |
| Monitoring | Suppress alerts during change, restore after | No | Engineer handles manually or add a pause |
| Order management | Source of circuit parameters | No | Engineer provides parameters as input |

### Discovery Questions

Ask the engineer before designing the solution:

1. What devices are on the A-side and Z-side? What OS do they run?
2. What type of circuit is this? (point-to-point L2, L3 routed, MPLS, VXLAN, etc.)
3. What interfaces are being configured on each side?
4. Where do the circuit parameters come from? (order system, spreadsheet, manual input?)
5. What does "traffic is working" mean for this circuit? (ping, BGP neighbor up, LLDP adjacency, etc.)
6. Do you use a ticketing system? Which one?
7. Should the workflow auto-rollback on failure, or pause for engineer review?
8. Are there existing templates or automations to reuse? (config templates, backup workflows, etc.)
9. Single circuit or batch? If batch, sequential or rolling?
10. Are there maintenance window constraints or approval gates?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One circuit at a time, stop on first failure | Small batch, conservative |
| Rolling | N circuits at a time, stop if failure rate > threshold | Medium batch, production |
| Parallel | All circuits at once | Lab/non-prod only |

Each circuit is independent (its own A-side/Z-side pair), so batch orchestration is at the circuit level, not the device level.

---

## 9. Acceptance Criteria

1. Provisioning only proceeds if both A-side and Z-side pass pre-flight checks
2. A-side is configured and verified before Z-side is touched
3. Z-side is only configured if A-side succeeds
4. End-to-end traffic verification confirms data-plane connectivity, not just config presence
5. If any step fails, both sides are rolled back to pre-change state (Z first, then A)
6. Config backup exists for both devices before and after the change
7. Evidence report is generated for every run — success, failure, or rollback
8. Batch mode respects configured concurrency and aborts if failure rate exceeds threshold
9. No partial circuits are left behind — both sides succeed or both revert
