# Use Case: Multi-Vendor Config Drift Detection & Remediation

## 1. Problem Statement

Device configurations drift from their intended state constantly — ad-hoc changes, emergency fixes, copy-paste errors, and forgotten temporary rules accumulate until the running config no longer matches what it should be. Teams discover drift only when something breaks or an audit flags it. Remediating drift manually across hundreds of multi-vendor devices is slow, inconsistent, and risky. There's no systematic way to know *what* drifted, *how bad* it is, and *whether it's safe to fix automatically*.

**Goal:** Automate scheduled scanning of device configs against a golden/intended standard, classify deviations by severity, auto-remediate low-risk drift, and ticket high-risk drift for human review — keeping the network in a known-good state continuously.

---

## 2. High-Level Flow

```
Scan  →  Compare  →  Classify  →  Decide  →  Remediate / Ticket  →  Report
  │          │           │           │               │                  │
  │          │           │           │               │                  │
Collect    Diff        Tag each    Low-risk:      Apply fix,         Drift
running    against     deviation   auto-fix.      verify config.     summary,
config     golden/     as low,     High-risk:     Or create          score,
from all   intended    medium,     create         ticket with        trending,
devices    standard    or high     ticket for     drift details      evidence
                       severity    review         for engineer
                                                      │
                                                 FAIL? → Rollback, escalate
```

---

## 3. Phases

### Scan
Collect the running configuration from every device in scope — routers, switches, firewalls, load balancers, across all vendors. Organize results by device group, site, or role. If a device is unreachable, **log it, skip it, and continue** — one unreachable device should not block the entire scan.

### Compare
Diff each device's running config against its golden/intended standard. The standard may be a full config template, a set of required config sections, or a set of rules (e.g., "NTP servers must be X and Y", "SNMP community must not be 'public'"). Produce a structured diff: what's missing, what's extra, what's wrong.

### Classify
Tag each deviation with a severity level. **Low** — cosmetic or operational preference (description mismatch, logging level). **Medium** — functional but non-critical (suboptimal timer, missing secondary NTP). **High** — security or stability risk (wrong ACL, SNMP community 'public', missing route-map, unauthorized user account). Classification rules are defined in the standard, not guessed at runtime.

### Decide
Route each deviation based on severity. Low-risk deviations go to auto-remediation. Medium-risk deviations go to auto-remediation if a confidence flag is set, otherwise to a ticket. High-risk deviations **always go to a ticket for human review** — never auto-remediate high-risk drift.

### Remediate
For deviations approved for auto-remediation: generate the corrective config, apply it to the device, and verify the drift is resolved by re-scanning that section. If remediation fails or introduces new errors, **rollback the change and escalate to a ticket**.

### Ticket
For deviations routed to human review: create a ticket with the device name, the specific drift, the expected vs. actual config, the severity, and the suggested fix. Group related deviations into a single ticket per device to avoid ticket flood.

### Report
Produce a drift report: how many devices scanned, how many had drift, breakdown by severity, what was auto-remediated, what was ticketed, overall compliance score, and trend vs. previous scan. Store the report for audit purposes.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| High-risk drift is never auto-remediated | Always routed to human review | Security and stability changes demand human judgment |
| One unreachable device does not block the scan | Log and continue | Partial visibility is better than no visibility |
| Classification is defined in the standard, not runtime | Severity baked into golden config rules | Consistent, auditable, not subject to runtime judgment |
| Remediation is verified by re-scan | Apply fix then re-diff that section | Confirms the fix actually resolved the drift |
| Tickets are grouped per device | One ticket per device, multiple deviations | Avoids ticket flood; gives engineer full device context |

---

## 5. Scope

**In scope:** Routers, switches, firewalls, load balancers. Multi-vendor (Cisco, Arista, Juniper, Palo Alto, F5, etc.). Scheduled and on-demand scanning. Config diff against golden/intended standard. Severity classification. Auto-remediation for low-risk drift. Ticketing for high-risk drift. Compliance scoring and trending. Rollback on failed remediation.

**Out of scope:** Defining the golden config standard itself (input to this workflow — assumed to exist). Firmware/OS-level compliance (separate use case). Physical layer checks (cabling, optics). Real-time config change detection via syslog/streaming (this is scheduled scanning, not event-driven).

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auto-remediation introduces a new issue | Service disruption | Verify by re-scan after fix; rollback if new drift appears |
| Golden standard has errors | False positives, unnecessary changes | Standard is versioned and reviewed; deviations flagged as exceptions |
| Large-scale drift overwhelms ticketing | Ticket flood, alert fatigue | Group deviations per device; summarize in a single drift report |
| Remediation on a firewall disrupts traffic | Security or connectivity outage | Firewalls classified as high-risk by default; no auto-remediation |
| Drift re-introduced by manual changes after remediation | Wasted effort, repeat drift | Trend reports highlight repeat offenders; feed back into change control |

---

## 7. Requirements

### What the automation must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Collect running config from multi-vendor devices | Yes | Cannot proceed |
| Diff config against a golden/intended standard | Yes | Cannot proceed |
| Apply corrective config commands to devices | Yes | All drift is ticketed (no auto-remediation) |
| Roll back config changes on failure | Yes | Engineer rolls back manually |
| Classify deviations by severity | Yes | All drift treated as high-risk (ticket everything) |
| Generate reports with compliance scores | Yes | Cannot proceed |
| Schedule scans on a recurring basis | Yes | Engineer triggers manually |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| Golden config / standards repository | Source of intended config | Yes | Cannot proceed |
| ITSM / ticketing | Create tickets for high-risk drift | No | Engineer reviews drift report manually |
| CMDB / inventory | Device list, groups, roles, sites | No | Engineer provides device list manually |
| Monitoring / alerting | Notify on scan completion or drift detected | No | Engineer checks reports manually |

### Discovery Questions

Ask the engineer before designing the solution:

1. What device types are in scope? (Routers, switches, firewalls, load balancers?)
2. What vendors and OS types? (Cisco IOS/NX-OS, Arista EOS, Juniper Junos, Palo Alto PAN-OS, F5?)
3. Do you have a golden config or intended config standard defined today?
4. How is the standard structured? (Full config templates, section-based rules, line-by-line checks?)
5. How should severity be classified? Do you have existing severity definitions?
6. Which categories of drift are safe to auto-remediate? Which require human review?
7. How often should scans run? (Daily, weekly, on-demand?)
8. What ticketing system should receive high-risk drift?
9. How many devices are in scope? Are they grouped by site, role, or region?
10. Do you want compliance scores and trending over time?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Full scan | All devices in scope, sequential or parallel collection | Scheduled weekly/daily scan |
| By device group | Scan one group at a time (e.g., by site or role) | Large environments, staggered scanning |
| Single device | Scan and remediate one device on demand | Ad-hoc checks or post-change validation |

---

## 9. Acceptance Criteria

1. Running config is collected from all reachable devices in scope
2. Config diff correctly identifies deviations from the golden standard
3. Each deviation is classified by severity (low, medium, high)
4. Low-risk deviations are auto-remediated and verified by re-scan
5. High-risk deviations are routed to a ticket with full context (device, deviation, expected vs. actual, suggested fix)
6. Failed remediation triggers rollback and escalation
7. Compliance score is calculated per device and across the fleet
8. Drift report is generated for every scan with trending vs. previous scans
9. Unreachable devices are logged but do not block the scan
