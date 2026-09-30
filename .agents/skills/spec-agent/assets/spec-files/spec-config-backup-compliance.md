# Use Case: Device Configuration Backup & Compliance

## 1. Problem Statement

Network device configurations change constantly — planned maintenance, emergency fixes, undocumented tweaks at 2 AM. Most teams have no reliable way to know what changed, when it changed, or whether the current config still meets their standards. Config backups are ad hoc. Drift detection is manual diffing. Unauthorized changes go unnoticed until something breaks.

**Goal:** Automate scheduled and on-demand config backups across multi-vendor devices, maintain versioned config history, detect drift from a defined baseline, and alert when configurations deviate from compliance standards.

---

## 2. High-Level Flow

```
Schedule/Trigger  →  Collect Configs  →  Store & Version  →  Compliance Check  →  Report & Alert
       │                   │                   │                    │                    │
       │                   │                   │                    │                    │
   Cron, on-demand,    Connect to          Save config          Compare current      Generate drift
   or change-event     each device,        with timestamp,      config against       report, alert
   trigger             pull running        detect if changed    baseline/standard,   on violations,
                       config              since last backup    grade compliance     update ticket
                                                                    │
                                                               DRIFT? → Flag & Notify
```

---

## 3. Phases

### Trigger
Backups run on a schedule (daily, weekly), on demand, or triggered by an external event (e.g., change ticket closed, syslog config-change trap). The trigger determines which devices to target — all devices, a device group, or a specific list.

### Collect Configurations
Connect to each target device and retrieve the running configuration. Handle multi-vendor differences — different commands, different output formats. If a device is unreachable, **log the failure and continue with the rest**. Do not let one unreachable device block the entire batch.

### Store & Version
Save each collected config with a timestamp. Compare against the previously stored version. If the config has changed, store the new version and record a diff. If unchanged, skip — do not create duplicate entries. Maintain a configurable retention window (e.g., 90 days, 50 versions).

### Compliance Check
Compare the current config against a defined compliance baseline. The baseline is a set of rules — required lines that must be present, forbidden lines that must not exist, patterns that must match. Grade each device: compliant, non-compliant, or partially compliant. Flag specific violations with line-level detail.

### Report & Alert
Generate a summary report: devices backed up, devices unreachable, configs changed since last run, compliance scores. Alert on drift (config changed outside a change window), alert on compliance violations. Optionally update a ticket or CMDB record.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Unreachable devices do not block the batch | Log failure, continue | One down device should not prevent backing up the other 500 |
| Only store configs that changed | Compare before writing | Avoids bloated storage and makes change history meaningful |
| Compliance is a separate phase from backup | Decouple collection from evaluation | Backups are useful even without compliance; compliance can run independently against stored configs |
| Baseline is defined as rules, not a golden config file | Rules are composable and partial | Different device roles need different rules; a monolithic golden config is too rigid |
| Drift alerting is time-aware | Distinguish planned vs unplanned changes | A config change during a change window is expected; the same change at 3 AM is not |

---

## 5. Scope

**In scope:** Scheduled and on-demand backup of running configs, versioned storage with diff, compliance checking against a rule-based baseline, drift detection and alerting, summary reporting, multi-vendor support.

**Out of scope:** Config remediation (separate use case — this detects, it does not fix). Startup config vs running config reconciliation. Configuration deployment or push. Backup of non-network devices (servers, cloud resources).

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Device unreachable during backup window | Missing config snapshot | Retry once after delay, log failure, include in report |
| Credentials expired or rotated | Backup fails for all devices using that credential | Validate credentials before starting batch, fail fast with clear error |
| Large device count overwhelms collection | Timeouts, partial results | Batch with concurrency limits, stagger collection |
| Compliance baseline is stale or incomplete | False positives/negatives | Review and version baselines alongside config changes |
| Storage grows unbounded | Disk/DB pressure | Enforce retention policy, prune old versions automatically |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on multi-vendor devices | Yes | Cannot proceed |
| Store and retrieve versioned configuration text | Yes | Cannot proceed |
| Compare two config versions and produce a diff | Yes | Cannot proceed |
| Evaluate config text against a set of compliance rules | Yes | Manual compliance review |
| Schedule recurring jobs | Yes | Engineer triggers manually each time |
| Send notifications (email, webhook, chat) | No | Engineer checks reports manually |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| ITSM / ticketing | Log backup results, flag drift as incidents | No | Engineer reviews reports manually |
| CMDB | Record last-known config state per device | No | Config history lives only in backup store |
| Monitoring / alerting | Receive drift and compliance alerts | No | Engineer checks reports on schedule |
| Syslog / event collector | Trigger backup on config-change events | No | Rely on scheduled backups only |

### Discovery Questions

Ask the engineer before designing the solution:

1. How many devices need to be backed up? What vendors and OS types?
2. How often should backups run? (daily, weekly, after every change?)
3. Is there an existing config repository or should we start fresh?
4. What does your compliance baseline look like today? Written rules, a reference config, tribal knowledge?
5. Do you need to distinguish between planned changes (during a change window) and unplanned drift?
6. How long should config history be retained?
7. Where should alerts go — email, Slack/Teams, ticketing system?
8. Are there device groups with different compliance standards? (e.g., core routers vs access switches)
9. Do you have a syslog or event source that signals config changes in real time?
10. Are there existing backup scripts or processes to replace or integrate with?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One device at a time | Small inventory, conservative |
| Parallel (throttled) | N devices at a time (e.g., 20 concurrent) | Large inventory, production — most common |
| Group-based | Backup one device group at a time | Different groups have different schedules or compliance baselines |

---

## 9. Acceptance Criteria

1. Running configs are collected from all reachable devices in the target scope
2. Unreachable devices are logged and reported, not silently skipped
3. Configs are only stored when they differ from the previous version
4. A diff is available for every config change
5. Compliance check produces a per-device pass/fail with specific violation details
6. Drift outside a change window triggers an alert
7. Summary report is generated for every backup run
8. Retention policy is enforced — old versions are pruned automatically
