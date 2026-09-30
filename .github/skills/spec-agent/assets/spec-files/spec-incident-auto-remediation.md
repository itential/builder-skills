# Use Case: Incident Auto-Remediation

## 1. Problem Statement

When a monitoring alert fires at 2 AM, the on-call engineer wakes up, VPNs in, reads the alert, SSHes into the device, runs the same diagnostic commands they always run, applies the same fix they applied last time, and closes the ticket. Most network incidents fall into a handful of well-known categories — interface flaps, high CPU, memory exhaustion, BGP neighbor down — and the remediation steps are documented in runbooks that engineers follow manually. This is slow, error-prone, and expensive.

**Goal:** Automatically detect, classify, and remediate common network incidents using predefined playbooks — fixing known issues in seconds instead of hours, and escalating unknown or failed remediations to humans with full diagnostic context.

---

## 2. High-Level Flow

```
Alert Ingestion  →  Classify  →  Match Playbook  →  Remediate  →  Verify  →  Close Out
      |                |               |                 |            |            |
      |                |               |                 |            |            |
   Receive          Determine       Look up          Execute       Re-check     Update
   alert from       incident        known fix        remediation   the alert    ticket,
   monitoring,      type,           for this         steps from    condition,   generate
   create/update    severity,       category         the matched   confirm      evidence
   ticket           affected        and context      playbook      resolved     report
                    device
                         |                                |
                    No match? →  Escalate           FAIL? → Escalate
```

---

## 3. Phases

### Alert Ingestion
Receive the alert from the monitoring system (webhook, event bus, or polling). Extract key fields: device, alert type, severity, timestamp, and any included metrics. Create or update an incident ticket. If the alert is a duplicate of an already-open incident, **correlate and skip — do not spawn parallel remediations for the same issue**.

### Classify
Determine the incident category from the alert data. Common categories: interface flap, high CPU, high memory, BGP neighbor down, OSPF adjacency lost, link down, device unreachable, certificate expiring. Identify the affected device, interface, or protocol session. Assign a severity level.

### Match Playbook
Look up a remediation playbook for the classified incident type and device platform. A playbook defines the diagnostic commands, the remediation steps, and the verification checks. If no playbook matches, **escalate to a human immediately with the classification details and raw alert data**. Do not attempt to improvise a fix.

### Remediate
Execute the playbook steps on the affected device. This might be clearing a BGP neighbor, bouncing an interface, freeing memory by restarting a process, or adjusting a threshold. Capture the output of every command. If the remediation step fails to execute, **stop and escalate — do not retry destructive commands blindly**.

### Verify
Re-check the original alert condition. Is the interface stable? Has CPU dropped below threshold? Is the BGP session re-established? Compare against the alert trigger criteria. If the condition persists after remediation, **escalate to a human with the full diagnostic output and remediation log**.

### Close Out
Update the incident ticket with the timeline: alert received, classification, playbook executed, verification result. Generate an evidence report with before/after state, commands executed, and output. Close the ticket if verified. If escalated, attach all context and assign to the appropriate team.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No playbook = no action | Escalate immediately if unrecognized | Never guess at a fix on production devices |
| Deduplication before classification | Correlate alerts to avoid parallel fixes | Two alerts for the same BGP drop should not trigger two remediations |
| Remediation is single-attempt by default | Do not retry failed fixes automatically | Retrying a failed fix can make things worse |
| Verification uses the same criteria as the alert | Re-check the original trigger condition | Proves the specific problem is resolved, not just that the device responds |
| Every incident produces a report | Success, failure, and escalation all documented | Post-incident review and audit trail |

---

## 5. Scope

**In scope:** Alert ingestion from monitoring. Incident classification. Playbook matching and execution. Single-device remediation. Post-remediation verification. Ticket creation/update/closure. Evidence generation. Escalation path for unknown or failed remediations.

**Out of scope:** Playbook authoring and approval (input to this process). Multi-device correlated incidents (e.g., upstream router failure causing downstream alerts). Root cause analysis across incidents. Capacity planning. Monitoring system configuration.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Alert storm triggers dozens of remediations simultaneously | Device overload, conflicting fixes | Deduplicate and throttle — one active remediation per device at a time |
| Misclassification leads to wrong playbook | Incorrect fix applied | Classify conservatively; escalate if confidence is low |
| Remediation causes a secondary outage | Wider impact than original alert | Capture device state before remediation; keep rollback context |
| Monitoring system goes down | Alerts stop flowing | Health-check the alert ingestion pipeline; alert on silence |
| Playbook becomes stale after OS upgrade | Remediation commands fail | Version-tag playbooks by platform and OS; fail gracefully on command errors |

---

## 7. Requirements

### What the automation must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Receive and parse alerts from monitoring systems | Yes | Cannot proceed |
| Execute CLI commands on network devices | Yes | Cannot proceed |
| Match incidents against a playbook catalog | Yes | Cannot proceed |
| Orchestrate multi-step conditional workflows | Yes | Cannot proceed |
| Create and update tickets in a ticketing system | No | Engineer tracks manually |
| Generate reports from templates | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| Monitoring (e.g., Datadog, PagerDuty, Zabbix) | Source of alerts | Yes | No alerts to process |
| ITSM / ticketing (e.g., ServiceNow, Jira) | Incident tracking and audit trail | No | Engineer tracks manually |
| Playbook catalog / knowledge base | Stores remediation procedures per incident type | Yes | Cannot match or execute fixes |
| CMDB / inventory | Device context (platform, OS, site, criticality) | No | Classification relies solely on alert data |

### Discovery Questions

Ask the engineer before designing the solution:

1. What monitoring system generates the alerts? How are they delivered (webhook, email, API)?
2. What are the top 5-10 incident types you see most often?
3. Do you have documented runbooks for those incident types today?
4. What ticketing system do you use for incident management?
5. What device platforms and OS families are in scope?
6. Are there devices or environments that should never be auto-remediated (e.g., core routers)?
7. What is the escalation path when automation cannot fix the issue?
8. Should the system attempt remediation on critical-severity alerts, or only medium/low?
9. Do you want a human approval gate before remediation, or fully automatic?
10. How do you want to be notified of escalations? (page, email, chat, ticket assignment)

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Per-device serialized | One remediation at a time per device, queue others | Always — prevents conflicting fixes on the same device |
| Cross-device parallel | Remediate different devices concurrently | Default for unrelated alerts across different devices |
| Throttled | Cap total concurrent remediations at N | Alert storms, large-scale events |

---

## 9. Acceptance Criteria

1. Alerts are received and deduplicated — no parallel remediations for the same incident
2. Incidents are classified by type, device, and severity
3. Matching playbook is selected and executed for known incident types
4. Unknown incident types are escalated immediately with full alert context
5. Remediation failure triggers escalation — no silent failures
6. Verification confirms the original alert condition is resolved
7. Incident ticket is created, updated throughout, and closed (or escalated) with full timeline
8. Evidence report is generated for every incident (resolved, failed, or escalated)
