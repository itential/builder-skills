# Use Case: Network Compliance Audit

## 1. Problem Statement

Network teams must prove their devices meet security baselines and regulatory standards (PCI-DSS, SOX, HIPAA, NIST, CIS benchmarks). Today this means an engineer manually pulls configs from hundreds of devices, eyeballs them against a spreadsheet of required settings, writes up exceptions, and produces a report for the auditor. It takes weeks, it's inconsistent, and by the time the report is done, configs have already drifted. Violations discovered late in the audit cycle are expensive to remediate under time pressure.

**Goal:** Continuously scan device configurations against defined compliance standards, grade every device, produce audit-ready reports, and optionally auto-remediate violations — turning compliance from a quarterly fire drill into an always-current posture.

---

## 2. High-Level Flow

```
Define Standards  →  Collect Configs  →  Evaluate  →  Grade  →  Report  →  Remediate
      |                    |                |           |           |            |
      |                    |                |           |           |            |
   Build or            Pull running     Compare      Score       Generate    Optionally
   import              config from      each         each        audit-      push fixes
   compliance          every device     config       device      ready       for
   rules per           in scope         against      (pass /     report      violations,
   standard                             applicable   partial /   with        re-scan
   and platform                         rules        fail)       drill-down  to confirm
                                                                    |
                                                               VIOLATIONS? → Flag or auto-fix
```

---

## 3. Phases

### Define Standards
Express each compliance requirement as a machine-evaluable rule. Group rules into standards (e.g., "PCI Baseline," "Corporate Security Standard," "SOX Network Controls"). Rules specify what must be present, what must be absent, and what values are acceptable. Standards are versioned — changing a rule creates a new version so historical audits remain valid.

### Collect Configs
Pull the running configuration from every device in scope. Scope can be defined by device group, site, platform, or ad-hoc list. Configs must be collected as close to simultaneously as practical to represent a consistent point-in-time snapshot. Store the raw configs for audit evidence.

### Evaluate
Compare each device's config against every applicable rule in the standard. Rules are matched by platform and context (a rule about BGP only applies to devices running BGP). Each rule produces a result: compliant, non-compliant, or not-applicable. Capture the specific config lines that pass or fail each rule.

### Grade
Score each device based on its evaluation results. A device with all rules passing is fully compliant. A device with critical violations is non-compliant. Devices in between receive a partial score. Aggregate scores by site, platform, region, or standard to produce executive-level summaries.

### Report
Generate audit-ready reports at multiple levels: executive summary (overall posture, trend over time), standard-level detail (which rules pass/fail across the fleet), device-level detail (specific violations with config excerpts). Reports must be exportable in formats auditors accept (PDF, CSV, structured data). Include timestamps, standard version, and device list for reproducibility.

### Remediate (optional)
For violations with known fixes, optionally push the corrective config to the device. Remediation follows the same pattern as any config change: backup first, apply fix, verify fix took effect by re-evaluating the specific rule. If remediation fails, flag the device and do not retry. Remediation can be automatic or gated behind approval.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Standards are versioned | Changing a rule creates a new version | Historical audit results must remain valid against the standard that was active at the time |
| Evaluation is per-rule, not pass/fail per device | Granular results for each rule | Auditors need to see exactly which controls pass and which fail |
| Remediation is optional and off by default | Must be explicitly enabled per standard or per run | Compliance scanning should be safe to run anytime without changing anything |
| Point-in-time snapshot | Configs collected at audit start, not live during evaluation | Ensures consistent comparison — no drift mid-scan |
| Reports include raw evidence | Config excerpts and rule match details | Auditors must be able to verify findings independently |

---

## 5. Scope

**In scope:** Compliance standard definition (rules, grouping, versioning). Config collection from devices. Rule evaluation against configs. Device and fleet grading. Audit-ready report generation. Optional auto-remediation of violations. Scheduled and on-demand scans. Trend tracking over time.

**Out of scope:** Defining what the compliance rules should be (input from security/compliance team). Firmware or OS-level compliance (this covers configuration only). Physical security audits. User access reviews. Policy exceptions and waiver management.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rules are too broad and generate false positives | Alert fatigue, audit noise | Scope rules by platform and context; allow not-applicable results |
| Config collection fails on some devices | Incomplete audit | Report which devices were unreachable; do not mark them as compliant |
| Standard changes mid-audit | Inconsistent results | Lock standard version at scan start; evaluate against that version |
| Auto-remediation introduces a config error | Service impact | Backup before fix, verify after, disable auto-remediate by default |
| Large fleet makes scanning slow | Audit window exceeded | Parallelize config collection; evaluate locally after collection |

---

## 7. Requirements

### What the automation must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Pull running config from network devices | Yes | Cannot proceed |
| Evaluate config text against pattern-based rules | Yes | Cannot proceed |
| Score and aggregate results across devices | Yes | Cannot proceed |
| Generate formatted reports (PDF, CSV) | Yes | Cannot proceed |
| Apply config changes to devices (for remediation) | No | Remediation is manual |
| Schedule recurring scans | No | Engineer triggers manually |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| CMDB / inventory (e.g., ServiceNow, NetBox) | Device list, platform info, site grouping | No | Engineer provides device list manually |
| Compliance / GRC platform | Store standards, track posture over time | No | Standards defined locally, reports exported |
| ITSM / ticketing (e.g., ServiceNow, Jira) | Track remediation tasks for violations | No | Engineer tracks manually |
| Report storage (e.g., SharePoint, S3) | Archive audit reports for retention | No | Reports stored locally |

### Discovery Questions

Ask the engineer before designing the solution:

1. What compliance standards do you need to audit against? (PCI, SOX, HIPAA, internal policy, CIS benchmarks?)
2. Do you have the rules documented today, or do they need to be defined from scratch?
3. What device platforms are in scope? (IOS, NX-OS, EOS, JunOS, PAN-OS, etc.)
4. How many devices are in the audit scope?
5. Should the scan run on a schedule or on-demand?
6. Do you want auto-remediation for any violation categories, or scan-only?
7. If auto-remediation, does it need an approval gate?
8. What report format does your audit team require? (PDF, CSV, both?)
9. Do you need to track compliance posture over time (trend reporting)?
10. Is there an existing GRC platform where results should be sent?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Full sweep | Scan all devices in scope in one run | Quarterly or annual audit, on-demand assessment |
| Rolling | Scan a subset of devices each day, cover full fleet over N days | Continuous compliance posture for large fleets |
| Targeted | Scan a specific device group, site, or platform | Post-change verification, incident response |

---

## 9. Acceptance Criteria

1. Compliance standards are defined with versioned, platform-aware rules
2. Running configs are collected from all in-scope devices (unreachable devices are flagged, not skipped silently)
3. Every device is evaluated against every applicable rule with a clear pass/fail/not-applicable result
4. Devices are graded and scores are aggregated by site, platform, and standard
5. Audit-ready report is generated with executive summary and device-level detail
6. Reports include timestamps, standard version, device list, and config evidence
7. Optional remediation applies fixes only with backup and post-fix verification
8. Scan can run on-demand or on a recurring schedule without manual intervention
