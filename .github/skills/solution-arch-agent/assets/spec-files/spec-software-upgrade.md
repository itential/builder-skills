# Use Case: Network Device Software Upgrade

## 1. Problem Statement

Network device software upgrades are high-risk, time-consuming change windows performed manually. Engineers SSH into devices, run commands, wait for reboots, and hope nothing breaks. If something goes wrong, rollback is manual and stressful. There's no consistent evidence trail.

**Goal:** Automate the full upgrade lifecycle — validate before, upgrade, validate after, rollback if needed, and produce auditable evidence — reducing the change window and eliminating manual errors.

---

## 2. High-Level Flow

```
Pre-Flight  →  Stage Image  →  Upgrade  →  Post-Flight  →  Close Out
    │               │             │              │              │
    │               │             │              │              │
 Validate        Transfer      Activate       Validate      Evidence
 device is       image to      new image,     device is     report,
 healthy,        device,       reload,        healthy,      update
 backup          verify        wait for       version       ticket,
 config          integrity     reboot         correct,      restore
                                              neighbors     monitoring
                                              back
                                                 │
                                            FAIL? → Rollback
```

---

## 3. Phases

### Pre-Flight
Confirm the device is ready. Check health (CPU, memory, interfaces, routing neighbors), verify disk space for the new image, backup the running config. If any critical check fails, **stop — do not proceed**.

### Stage Image
Transfer the software image to the device. Verify the file arrived intact (checksum). If transfer fails, retry once, then abort.

### Upgrade
Set the boot variable to the new image, save config, reload the device. Wait for it to come back online (configurable timeout, default 10 min). If the device doesn't come back, **alert the engineer — this requires console access**.

### Post-Flight
Verify the device is running the target version. Re-run the same health checks from pre-flight and compare: are all interfaces still up? Are all routing neighbors re-established? Is the config intact? If post-flight fails and rollback is enabled, **auto-rollback**.

### Rollback (conditional)
Restore the boot variable to the previous image, reload. Verify the device comes back on the old version. If rollback itself fails, **escalate immediately**.

### Close Out
Generate an evidence report (pre vs post state, config diff, timing). Update the change ticket. Restore monitoring alerts.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pre-flight is a hard gate | Abort if critical checks fail | Never upgrade an unhealthy device |
| Config backup is mandatory | No backup = no upgrade | Must have a restore point |
| Post-flight compares against pre-flight | Same checks, compare counts | Detects regressions objectively |
| Rollback is automatic by default | Can be overridden to manual review | Speed matters when a device is down |
| Evidence is generated regardless of outcome | Success or failure both produce a report | Audit trail is non-negotiable |

---

## 5. Scope

**In scope:** Single device upgrade, batch upgrade (sequential/rolling/parallel), pre/post validation, config backup/diff, rollback, evidence generation, ITSM integration.

**Out of scope:** Image selection and approval (input to this workflow). Physical console recovery. HA/stack-specific upgrade choreography (separate use case). Image repository management.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Device doesn't come back after reload | Service outage | Configurable reboot timeout + immediate alerting |
| Post-upgrade routing neighbors don't re-establish | Traffic loss | Wait with timeout, compare against pre-flight baseline |
| Wrong image staged | Bricked device | Checksum verification before activating |
| Rollback fails | Extended outage | Alert engineer, do not retry indefinitely |
| Batch upgrade cascading failure | Wide-scale outage | Abort batch if failure rate exceeds threshold |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on devices | Yes | Cannot proceed |
| Backup and diff device configurations | Yes | Cannot proceed |
| Transfer files to devices | Yes | Engineer pre-stages image manually |
| Orchestrate multi-step workflows with conditions | Yes | Cannot proceed |
| Test device reachability after reboot | Yes | Cannot proceed |
| Generate reports from templates | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| ITSM / ticketing | Track the change, audit trail | No | Engineer tracks manually |
| Monitoring | Suppress alerts during upgrade, restore after | No | Engineer handles manually or add a pause |
| Image repository | Source for software images | Yes | Engineer pre-stages the image |

### Discovery Questions

Ask the engineer before designing the solution:

1. Which devices are you upgrading? What OS do they run?
2. What is the target version and image filename?
3. Where is the image stored? (URL, file server, already on device?)
4. What routing protocols do these devices run? (BGP, OSPF, static?)
5. Do you use a ticketing system? Which one?
6. Do you want to suppress monitoring alerts during the upgrade?
7. Should the workflow auto-rollback on failure, or pause for review?
8. Single device or batch? If batch, sequential or rolling?
9. Is there an approval step, or should it auto-proceed after pre-flight?
10. Are there existing automations you'd like to reuse? (backup workflows, check templates, etc.)

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One device at a time, stop on first failure | Small batch, conservative |
| Rolling | N devices at a time, stop if failure rate > threshold | Medium batch, production |
| Parallel | All at once | Lab/non-prod only |

---

## 9. Acceptance Criteria

1. Upgrade only proceeds if all critical pre-flight checks pass
2. Device runs the target version after upgrade
3. All interfaces and routing neighbors match pre-flight state
4. Config backup exists before and after the upgrade
5. Config diff shows only expected changes
6. Rollback restores the previous version when post-flight fails
7. Evidence report is generated for every run (success or failure)
8. Batch mode respects the configured concurrency and failure threshold
