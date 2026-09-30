# Use Case: Network Health Check / Pre-Change Validation

## 1. Problem Statement

Network health checks are performed inconsistently. One engineer checks BGP neighbors, another checks interfaces, a third checks nothing. When used as pre/post validation for change windows, the checks are ad hoc, results aren't recorded, and there's no objective comparison between "before" and "after." If a change breaks something subtle — a single BGP peer drops, error counters spike — it goes unnoticed until users complain.

**Goal:** Define a standardized, repeatable health check that collects device metrics (CPU, memory, interfaces, routing neighbors, error counters, reachability), compares them against baselines or thresholds, and produces a clear pass/fail report. This check should work standalone and as a reusable building block for any change workflow.

---

## 2. High-Level Flow

```
Collect         →  Normalize     →  Evaluate      →  Report
    │                  │                │                │
    │                  │                │                │
 Run check          Parse raw        Compare          Build
 commands on        output into      against          pass/fail
 each device,       structured       thresholds       summary per
 gather CPU,        key-value        or baseline      device,
 memory,            metrics          snapshot,        flag failures,
 interfaces,                         flag any         attach to
 neighbors,                          deviation        ticket or
 counters,                                            parent job
 reachability                             │
                                     FAIL? → Stop parent workflow
```

---

## 3. Phases

### Collect
Run a defined set of check commands against each device in scope. The check catalog is standardized per device OS: CPU utilization, memory utilization, interface admin/oper status, routing neighbor count and state, interface error/discard counters, and reachability to critical next-hops. If a device is unreachable, **mark it as failed immediately — do not skip it silently**.

### Normalize
Parse raw command output into structured metrics. Each metric becomes a named key-value pair (e.g., "cpu_percent: 42", "bgp_neighbors_established: 12"). Normalization must handle vendor-specific output differences so that the evaluation phase works against a common schema regardless of device OS.

### Evaluate
Compare each metric against its threshold or baseline. Two modes:

- **Threshold mode:** Compare against static limits (e.g., CPU < 80%, memory < 85%, zero critical interface errors). Used for standalone health checks.
- **Baseline mode:** Compare against a previously captured snapshot (e.g., same BGP neighbor count, same interfaces up). Used for pre/post change validation.

If any critical metric fails, the overall device result is **FAIL**. If only warning-level metrics deviate, the result is **WARN**.

### Report
Produce a structured report: one row per device, one column per metric, color-coded pass/warn/fail. Include raw values, thresholds or baseline values, and the delta. Attach to the change ticket if one exists, or return to the calling workflow.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Check catalog is per-OS, not per-device | Standardize by OS family | Maintainable, consistent checks across fleet |
| Two evaluation modes (threshold vs baseline) | Support both standalone and pre/post use | One check definition, two contexts |
| Critical failure = hard stop | FAIL blocks the parent workflow | Never proceed with a change on an unhealthy device |
| Warning = proceed with flag | WARN does not block, but is recorded | Avoids false-positive gate on minor deviations |
| Report is always generated | Even if all devices pass | Evidence trail for audit and troubleshooting |

---

## 5. Scope

**In scope:** Standardized check catalog per OS family, CLI-based metric collection, structured parsing, threshold evaluation, baseline snapshot capture and comparison, per-device pass/warn/fail grading, summary report generation, integration as a reusable pre/post check for other workflows.

**Out of scope:** Streaming telemetry or SNMP-based collection (different data path). Remediation of failed checks (that's the parent workflow's job). Monitoring system integration beyond report generation. Custom per-device check overrides (use device groups instead).

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Device unreachable during check | No data collected, false pass if skipped | Treat unreachable as FAIL, never skip |
| Parsing fails on unexpected output format | Metric missing, incorrect evaluation | Treat parse failure as FAIL for that metric |
| Thresholds too strict | Excessive false failures blocking changes | Separate critical vs warning thresholds, tune over time |
| Baseline snapshot is stale | Comparison against outdated state | Capture baseline immediately before the change, not days ahead |
| Check commands impact device performance | CPU spike on already stressed device | Use non-intensive show commands, avoid debug or trace |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on devices | Yes | Cannot proceed |
| Parse unstructured command output into structured data | Yes | Cannot proceed |
| Compare values against thresholds or baseline snapshots | Yes | Cannot proceed |
| Store and retrieve baseline snapshots | Yes (for baseline mode) | Threshold mode only |
| Generate reports from structured data | Yes | Cannot proceed |
| Expose results to a parent workflow | Yes (for pre/post use) | Standalone only |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| ITSM / ticketing (e.g., ServiceNow) | Attach report to change ticket | No | Report saved locally or returned to caller |
| CMDB / inventory (e.g., ServiceNow, NetBox) | Resolve device list and OS type | No | Device list provided as input |
| Monitoring (e.g., Datadog, PRTG) | Cross-reference alerts during check | No | Check runs independently |

### Discovery Questions

Ask the engineer before designing the solution:

1. What devices are in scope? Provide a list, a device group, or a CMDB query.
2. What OS families are represented? (IOS, IOS-XE, NX-OS, EOS, Junos, etc.)
3. Is this a standalone health check or a pre/post check for a change workflow?
4. If pre/post: what change is this validating? (upgrade, config push, migration?)
5. What are the critical thresholds? (CPU %, memory %, acceptable error counter delta?)
6. Which routing protocols matter? (BGP, OSPF, ISIS, static?)
7. Are there interfaces expected to be down? (so they don't flag as failures)
8. Do you want to store the baseline for future comparison or discard after use?
9. Should results be attached to a change ticket? Which ticketing system?
10. Are there existing check templates or command sets you already use?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One device at a time, stop on first failure | Pre-change validation where any failure aborts the change |
| Parallel | All devices at once, collect all results | Standalone fleet health check, need full picture |
| Rolling | N devices at a time, aggregate pass/fail | Large-scale pre-check where partial results are useful |

---

## 9. Acceptance Criteria

1. All defined check commands execute successfully on reachable devices
2. Unreachable devices are marked FAIL, never silently skipped
3. Raw output is parsed into structured metrics for every check
4. Threshold mode correctly flags metrics outside defined limits
5. Baseline mode correctly detects deviations from the captured snapshot
6. Each device receives an overall PASS, WARN, or FAIL grade
7. A summary report is generated for every run, regardless of outcome
8. When used as a pre-check, a FAIL result prevents the parent workflow from proceeding
9. When used as a post-check, a FAIL result triggers rollback or escalation in the parent workflow
