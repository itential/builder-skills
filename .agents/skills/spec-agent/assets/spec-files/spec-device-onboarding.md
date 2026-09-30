# Use Case: Device Onboarding (Day-0 / Day-1)

## 1. Problem Statement

Adding a new device to the network is a multi-team, multi-system process. Engineers manually configure base settings (NTP, AAA, SNMP, syslog, DNS, banners), then update IPAM, monitoring, and inventory systems one at a time. Each step is a different tool, a different login, a different ticket. Devices sit in limbo for hours or days between racking and being fully operational. Mistakes in base config lead to security gaps or blind spots in monitoring.

**Goal:** Automate the full onboarding lifecycle — from initial reachability through base configuration, system registration, and verification — so that a device goes from powered-on to production-ready in minutes with zero manual touch.

---

## 2. High-Level Flow

```
Discovery  →  Base Config  →  Register  →  Enable Monitoring  →  Verify  →  Close Out
    |              |              |               |                  |            |
    |              |              |               |                  |            |
 Confirm        Apply          Add to          Add device        Ping,        Update
 device is      NTP, AAA,      IPAM,           to monitoring     SSH,         ticket,
 reachable,     SNMP, DNS,     update          system,           validate     generate
 identify       syslog,        inventory       configure         AAA login,   evidence
 platform/      banner,        system          alert             check SNMP   report
 OS type        save config                    thresholds        response
                    |
               FAIL? → Quarantine & alert
```

---

## 3. Phases

### Discovery
Confirm the device is reachable over the management network. Identify the platform type and OS version (e.g., IOS-XE, NX-OS, EOS, JunOS). Collect baseline facts: hostname, serial number, management IP, model. If the device is unreachable, **stop — flag for physical layer troubleshooting**.

### Base Configuration (Day-1)
Apply the standard configuration template for the identified platform. This includes NTP servers, AAA (TACACS+/RADIUS), SNMP communities/v3 users, syslog destinations, DNS resolvers, and login banners. Save the configuration. If any section fails to apply, **stop and quarantine the device** — do not proceed with a partially configured device.

### Register
Add the device to IPAM with the assigned management IP, subnet, and site metadata. Create or update the device record in the network inventory system with hostname, model, serial, OS version, and site. If IPAM or inventory registration fails, retry once, then flag for manual review.

### Enable Monitoring
Add the device to the monitoring platform. Configure standard alert thresholds (CPU, memory, interface utilization, reachability). Suppress initial burn-in alerts for a configurable window (default 15 minutes) to avoid noise during settling.

### Verify
Run end-to-end validation: ping the management IP, SSH into the device, authenticate via AAA (not local credentials), poll SNMP, confirm syslog messages are arriving at the collector, and verify NTP is synchronized. If any check fails, **flag the device as partially onboarded and alert the engineer**.

### Close Out
Generate an onboarding evidence report: device facts, config applied, systems registered, verification results. Update the change ticket with the outcome. Mark the device as production-ready in inventory.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Platform auto-detection before config push | Identify OS type first, select matching template | One workflow handles all vendors |
| Base config is all-or-nothing | Abort on partial failure | A half-configured device is worse than an unconfigured one |
| IPAM and inventory registration before monitoring | Device must have proper records before alerting starts | Prevents orphaned alerts |
| Post-onboarding verification is mandatory | Must prove every system integration works | Catches silent failures (e.g., wrong SNMP community) |
| Evidence report generated for every device | Success or failure | Audit trail for every onboarding |

---

## 5. Scope

**In scope:** Physical and virtual device onboarding across vendors. Base config application (Day-1). IPAM registration. Inventory registration. Monitoring enrollment. End-to-end verification. Evidence generation. Batch onboarding of multiple devices.

**Out of scope:** Physical racking and cabling (Day-0 physical). ZTP/DHCP bootstrap (separate process that feeds into this workflow). Advanced service configuration (Day-2). Firewall rule provisioning. Certificate enrollment. License activation.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Device unreachable after racking | Onboarding blocked | Auto-detect and flag immediately, don't queue silently |
| Wrong platform detected | Incorrect config template applied | Verify platform facts against expected values before pushing config |
| AAA server unreachable during config push | Device locked out | Ensure local fallback credentials exist in base template |
| IPAM record conflict (IP already assigned) | Registration fails | Check for conflicts before creating, flag for resolution |
| Monitoring floods with alerts on new device | Alert fatigue | Suppress alerts during configurable burn-in window |

---

## 7. Requirements

### What the automation must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Connect to devices via SSH/NETCONF | Yes | Cannot proceed |
| Detect device platform and OS type | Yes | Engineer provides platform manually |
| Render and apply config templates per platform | Yes | Cannot proceed |
| Register records in external systems via API | Yes | Engineer registers manually |
| Validate device reachability and management plane | Yes | Cannot proceed |
| Generate reports from collected data | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| IPAM (e.g., Infoblox, NetBox) | IP address registration and management | Yes | Engineer updates manually |
| Inventory / CMDB (e.g., ServiceNow, Nautobot) | Device record of truth | Yes | Engineer updates manually |
| Monitoring (e.g., Datadog, Zabbix, SolarWinds) | Add device to alerting | No | Engineer adds device manually |
| ITSM / ticketing | Track the onboarding change | No | Engineer tracks manually |
| AAA server (TACACS+/RADIUS) | Validate authentication works | Yes | Verification step is incomplete |

### Discovery Questions

Ask the engineer before designing the solution:

1. What types of devices are you onboarding? What OS families?
2. Do you have standard base config templates per platform, or do they need to be created?
3. What IPAM system do you use? Is there an API available?
4. What is your inventory system of record?
5. What monitoring platform do you use?
6. Do you use TACACS+ or RADIUS for AAA?
7. Should the workflow handle both physical and virtual devices?
8. Is there an existing ZTP process that precedes this workflow?
9. Single device or batch? If batch, are they typically the same platform?
10. What ticketing system should be updated on completion?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One device at a time, stop on first failure | Small batch, first-time rollout |
| Rolling | N devices at a time, continue on individual failure | Medium batch, mixed platforms |
| Parallel | All at once | Large batch of identical devices (same model, same site) |

---

## 9. Acceptance Criteria

1. Device platform and OS are correctly identified before config is applied
2. Base configuration (NTP, AAA, SNMP, syslog, DNS, banner) is fully applied and saved
3. Device is registered in IPAM with correct IP and metadata
4. Device record exists in inventory with hostname, model, serial, and OS version
5. Device is enrolled in monitoring with standard alert thresholds
6. Post-onboarding verification confirms SSH, AAA, SNMP, syslog, and NTP all work
7. Evidence report is generated for every device (success or failure)
8. Batch mode respects concurrency limits and handles individual failures without blocking the batch
