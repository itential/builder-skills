# Use Case: Change Management / Maintenance Window Orchestration

## 1. Problem Statement

Change windows are the most stressful hours in network operations. Engineers manually create tickets, wait for approvals over email, SSH into monitoring tools to suppress alerts, execute the change, check if things broke, re-enable monitoring, and update the ticket. Steps get skipped under pressure. Monitoring stays suppressed for hours after the window closes. Tickets sit in "In Progress" for days.

**Goal:** Automate the full change window lifecycle — ticket creation through close-out — so the engineer focuses on the change itself while everything around it happens reliably and in order. The actual change is pluggable: this is a wrapper that orchestrates before, during, and after.

---

## 2. High-Level Flow

```
Create/Update  →  Get Approval  →  Suppress     →  Execute    →  Verify   →  Restore     →  Close
Ticket              Gate           Monitoring      Change        Change     Monitoring     Ticket
    │                 │                │              │             │            │             │
    │                 │                │              │             │            │             │
 Open ticket,     Wait for        Put devices     Call the      Run post-   Re-enable      Update
 populate         approval or     in maint        pluggable     change      alerts,        ticket with
 details,         timeout         mode, ack       change        checks,     verify         results,
 attach plan                      suppression     process       compare     alerts are     attach
                                                                to pre-     firing         evidence
                                                                change
                                                                   │
                                                              FAIL? → Rollback + Escalate
```

---

## 3. Phases

### Ticket Creation
Create or update the change ticket with all required fields: affected devices, change type, scheduled window, risk level, and the change plan. If a ticket ID is provided as input, update the existing ticket instead of creating a new one.

### Approval Gate
Wait for the ticket to reach an approved state. Poll the ticketing system on an interval. If approval is not received within a configurable timeout (default: 4 hours), **abort and notify the engineer**. If the ticket is rejected, abort and update the ticket with the rejection reason.

### Suppress Monitoring
Place all affected devices into maintenance mode in the monitoring system. Confirm the suppression took effect. Record the suppression start time. If suppression fails, **pause and ask the engineer** — proceeding without suppression risks a flood of false alerts.

### Execute Change
Call the pluggable change process, passing it the device list, variables, and any change-specific inputs. This process is a black box to the orchestrator — it could be a software upgrade, a config push, a BGP peer addition, anything. Wait for it to complete. Capture its success/failure status and any outputs.

### Verify Change
Run post-change validation checks. These should mirror whatever pre-change checks the change process performed. Compare results. If verification fails and auto-rollback is enabled, trigger rollback within the change process. If rollback is not available, **escalate immediately**.

### Restore Monitoring
Remove maintenance mode from all affected devices. Verify alerts are flowing again. Record the suppression end time and total duration. If restore fails, **alert the engineer** — silent monitoring is dangerous.

### Close Ticket
Update the ticket with the outcome (success, failure, rolled back), attach the evidence report (timing, pre/post comparison, any errors), and transition the ticket to its final state. Calculate and record the actual change window duration.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Approval is a hard gate | Never proceed without approval | Change management compliance requires it |
| The change itself is pluggable | Orchestrator calls any change process | One wrapper handles all change types |
| Monitoring suppression is verified | Confirm maint mode before proceeding | Prevents alert storms during work |
| Monitoring restore is verified | Confirm alerts resume after work | Silent monitoring is worse than no monitoring |
| Ticket is updated at every phase | Not just at open and close | Creates a real-time audit trail |
| Timeout on every wait | Approval, change execution, reboot waits | Prevents jobs from hanging indefinitely |

---

## 5. Scope

**In scope:** Ticket lifecycle (create, update, close), approval polling, monitoring suppression and restoration, pluggable change execution, post-change verification, evidence generation, single-device and batch change windows.

**Out of scope:** The change itself (that is the pluggable process). Ticket workflow design within the ITSM tool. Approval routing rules. Monitoring tool configuration. Calendar/scheduling integration.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Approval never arrives | Change window missed | Configurable timeout with notification |
| Monitoring suppression fails silently | Alert storm during change | Verify suppression before proceeding |
| Change process hangs indefinitely | Window overruns, monitoring stays suppressed | Execution timeout, auto-restore monitoring on timeout |
| Monitoring not restored after failure | Ongoing silent monitoring | Restore monitoring in all exit paths (success, failure, abort) |
| Ticket left in wrong state | Audit trail broken | Close/update ticket in all exit paths |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Orchestrate multi-step processes with conditional logic | Yes | Cannot proceed |
| Call external processes and wait for completion | Yes | Cannot proceed |
| Poll an external system on an interval with timeout | Yes | Cannot proceed |
| Generate reports from structured data | Yes | Cannot proceed |
| Handle errors and route to different paths | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| ITSM / ticketing (e.g., ServiceNow) | Ticket lifecycle, approval tracking | Yes | Cannot proceed — ticket is the audit trail |
| Monitoring (e.g., SolarWinds, PRTG, Datadog) | Suppress and restore alerts | No | Engineer manages alerts manually |
| The change process itself | Perform the actual network change | Yes | Nothing to orchestrate |

### Discovery Questions

Ask the engineer before designing the solution:

1. What ticketing system do you use? What fields are required on a change ticket?
2. How does approval work? Is it a status field on the ticket, or a separate approval record?
3. What monitoring system do you use? Does it support API-driven maintenance windows?
4. What types of changes will this orchestrate? (upgrades, config pushes, provisioning?)
5. Do you need pre-change validation, or does the pluggable change process handle that?
6. Should rollback be automatic on failure, or should it pause for engineer review?
7. What is your maximum acceptable change window duration?
8. Do you need batch support — multiple devices in one change window?
9. Are there blackout periods when changes cannot proceed even with approval?
10. What evidence do auditors require? (timing, before/after state, approval records?)

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Single window | All devices in one ticket, one suppression, one change process call | Small batch, tightly coupled devices |
| Sequential windows | Separate ticket per device, changes executed one at a time | Risk-averse, independent devices |
| Rolling | N devices at a time within one ticket, abort if failure rate > threshold | Production environments, large batches |

---

## 9. Acceptance Criteria

1. Change does not proceed without an approved ticket
2. Monitoring is confirmed suppressed before the change begins
3. The pluggable change process receives all required inputs and its outcome is captured
4. Post-change verification runs and results are recorded
5. Monitoring is restored in all exit paths — success, failure, rollback, and timeout
6. Ticket is updated with outcome and evidence in all exit paths
7. Approval timeout aborts cleanly without leaving orphaned suppression or open tickets
8. Change window duration is recorded on the ticket
