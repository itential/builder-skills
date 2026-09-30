# Use Case: WAN Circuit Bandwidth Modification

## 1. Problem Statement

Changing WAN circuit bandwidth — upgrading or downgrading — is a multi-step coordination exercise that touches the service provider, both endpoint routers, QoS policies, monitoring thresholds, and the CMDB. Today, engineers manually update QoS on each end, hope the SP has already provisioned the new rate, and discover mismatches only when users complain about packet loss or throttling. There's no consistent verification that the actual throughput matches the contracted rate.

**Goal:** Automate the end-to-end bandwidth modification — coordinate with the SP, update QoS policies on both endpoints, verify traffic shaping matches the new rate, update records — reducing misconfigurations and ensuring the circuit performs as contracted.

---

## 2. High-Level Flow

```
Validate  →  Pre-Change  →  SP Coordination  →  Apply QoS  →  Verify  →  Close Out
   │              │                │                 │            │            │
   │              │                │                 │            │            │
 Confirm       Capture          Confirm SP         Update       Test        Update
 circuit       current          has provisioned    shaper,      throughput  CMDB,
 exists,       QoS policies,    the new rate       policer,     matches     ticket,
 endpoints     interface        (or trigger        queuing on   new rate,   monitoring
 reachable,    counters,        SP workflow)       both         no drops,   thresholds
 new rate      baseline                            circuit      counters
 valid         throughput                          endpoints    clean
                                                      │
                                                 FAIL? → Rollback QoS to previous values
```

---

## 3. Phases

### Validate
Confirm the circuit exists in inventory. Identify both endpoint devices and interfaces. Verify the target bandwidth is valid for the circuit type (MPLS, internet, point-to-point). Confirm both devices are reachable. If any validation fails, **stop and report the issue**.

### Pre-Change Snapshot
Capture the current state on both endpoints: running QoS policy, interface bandwidth setting, shaper/policer rates, queue counters, interface error counters, and a baseline throughput measurement if possible. This snapshot is the rollback reference.

### SP Coordination
Confirm the service provider has provisioned (or will provision) the new bandwidth on their side. This may be a manual confirmation step (wait for SP ticket closure), an API call to the SP portal, or simply a gate where the engineer confirms readiness. **Do not apply QoS changes until the SP side is confirmed.**

### Apply QoS
Update the QoS policy on both circuit endpoints to match the new bandwidth. This includes: interface bandwidth statement, shaper rate, policer rate, and any class-based queue allocations that reference the circuit speed. Apply to the A-side first, verify, then the Z-side. If the A-side fails, **stop and rollback**.

### Verify
Confirm the changes took effect. Check that the interface bandwidth reflects the new rate, shaper/policer values are correct, and queue allocations are proportional. Run a throughput test if the circuit supports it. Compare interface counters — there should be no unexpected drops or errors. If verification fails, **rollback both endpoints to the pre-change QoS**.

### Close Out
Update the CMDB with the new circuit bandwidth. Update monitoring thresholds (utilization alerts should reference the new rate). Close the change ticket with evidence of pre/post state.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| SP confirmation is a hard gate | No QoS change until SP is ready | Applying new QoS before SP provisions causes drops |
| A-side before Z-side | Sequential, not simultaneous | If A-side fails, Z-side is untouched and rollback is simpler |
| Pre-change snapshot is mandatory | No snapshot = no modification | Must have a rollback reference |
| Verification includes counter checks | Not just config — actual behavior | Config can be correct but not applied (pending commit, etc.) |
| Monitoring thresholds updated automatically | Part of close-out, not manual | Stale thresholds cause false alerts on every bandwidth change |

---

## 5. Scope

**In scope:** MPLS circuits, internet circuits, point-to-point circuits. QoS policy updates on both endpoints. Shaper, policer, and queue adjustments. SP coordination gate. Throughput verification. CMDB and monitoring updates. Rollback on failure.

**Out of scope:** SP-side provisioning (that's the provider's responsibility or a separate integration). Circuit turn-up or decommission (separate use cases). Routing protocol changes. Physical interface upgrades (e.g., swapping a 1G SFP for a 10G). Multi-path/ECMP rebalancing.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| QoS applied before SP provisions new rate | Packet loss — shaper exceeds SP policer | Hard gate on SP confirmation before applying |
| A-side and Z-side mismatch | Asymmetric shaping, one direction throttled | Sequential apply with verification after each side |
| Rollback fails on one endpoint | One side on old policy, other on new | Alert engineer; capture both states for manual remediation |
| Throughput test disrupts production traffic | Brief service impact | Use non-intrusive measurement where possible; schedule in change window |
| CMDB not updated after change | Stale records, future changes use wrong baseline | CMDB update is part of the automated close-out, not a manual step |

---

## 7. Requirements

### What the automation must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on network devices | Yes | Cannot proceed |
| Read and modify QoS policies on devices | Yes | Cannot proceed |
| Capture interface counters and statistics | Yes | Verification is limited to config only |
| Orchestrate multi-step workflows with gates | Yes | Cannot proceed |
| Roll back configuration changes | Yes | Engineer rolls back manually |
| Run throughput or bandwidth tests | No | Verify via counters and config only |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| CMDB / circuit inventory | Identify circuit, endpoints, current rate | Yes | Engineer provides details manually |
| ITSM / ticketing | Track the change, SP coordination | No | Engineer coordinates manually |
| SP portal / API | Confirm SP-side provisioning | No | Engineer confirms manually (gate becomes a pause) |
| Monitoring | Update utilization thresholds | No | Engineer updates thresholds manually |

### Discovery Questions

Ask the engineer before designing the solution:

1. What circuit types are in scope? (MPLS, internet, point-to-point, all?)
2. What is the current bandwidth and target bandwidth?
3. How do you coordinate with the service provider? (Ticket, portal, API, phone call?)
4. What QoS model do you use? (Flat shaper, hierarchical, class-based?)
5. Are both endpoints managed by your team, or is one SP-managed?
6. Do QoS class allocations change proportionally with bandwidth, or are they fixed?
7. Do you have a way to test throughput non-disruptively?
8. What CMDB or inventory system tracks circuit bandwidth?
9. What monitoring system needs threshold updates?
10. Should this run during a change window, or can it be done live?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Single circuit | One circuit, both endpoints, sequential | Default for ad-hoc changes |
| Sequential batch | One circuit at a time from a list | Planned bandwidth refresh across multiple circuits |
| Grouped by site | All circuits at a site, then move to next site | Site-level bandwidth upgrade coordinated with SP |

---

## 9. Acceptance Criteria

1. Bandwidth modification only proceeds after SP-side provisioning is confirmed
2. QoS policies on both endpoints reflect the new bandwidth (shaper, policer, queues)
3. Interface bandwidth setting matches the new contracted rate
4. Pre-change and post-change snapshots are captured and stored
5. Rollback restores both endpoints to the original QoS policy if verification fails
6. No unexpected packet drops or errors after the change
7. CMDB reflects the updated circuit bandwidth
8. Monitoring thresholds are updated to reference the new rate
