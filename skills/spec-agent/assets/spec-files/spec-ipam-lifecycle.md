# Use Case: IP Address Management Lifecycle

## 1. Problem Statement

IP address management is tracked in spreadsheets, scattered across IPAM tools, and never reconciled against what is actually configured on the network. Addresses are allocated but never reclaimed. Subnets run out while stale entries sit unused. DNS records drift from reality. Duplicate IPs cause outages that take hours to diagnose because nobody has a single source of truth.

**Goal:** Automate the full IP lifecycle — allocate, assign, track, and reclaim — integrated with DNS and DHCP, validated against live network state, so that the IPAM system always reflects reality and conflicts are caught before they cause outages.

---

## 2. High-Level Flow

```
Allocate     →  Assign     →  Track      →  Reclaim     →  Close Out
    │              │             │              │              │
    │              │             │              │              │
 Reserve        Create        Periodic       Detect         Release
 next           DNS           scan:          stale/unused   IP in IPAM,
 available      records,      verify IP      addresses,     remove DNS
 IP/subnet      update        in use,        confirm        records,
 in IPAM,       DHCP          check DNS      not in use,    update
 validate       scope,        matches,       notify         DHCP,
 no conflict    configure     detect         owner          generate
                device        conflicts                     report
```

---

## 3. Phases

### Allocate
Receive a request for an IP address or subnet (size, site, VLAN, purpose). Query the IPAM system for the next available address in the appropriate scope. Validate the candidate IP is not already in use — ping sweep and ARP check on the network segment. If a conflict is detected, **skip that address and try the next**. Reserve the address in IPAM with requestor, date, and purpose metadata.

### Assign
Create the corresponding DNS records: forward (A/AAAA) and reverse (PTR). If DHCP is involved, create or update the DHCP reservation/scope. Apply the IP configuration to the target network device interface if applicable. Verify the assignment is consistent: IPAM record matches DNS matches device config.

### Track
Run periodic reconciliation scans. For every allocated IP: is it responding on the network? Does the DNS record still resolve correctly? Does the device config match IPAM? Flag discrepancies: IP allocated in IPAM but not found on network (potentially stale), IP found on network but not in IPAM (rogue/shadow IT), DNS record pointing to wrong IP (drift). Generate a reconciliation report.

### Reclaim
Identify addresses that have been unused beyond a configurable threshold (default 90 days). Notify the owner/requestor with a grace period. If no response or confirmation of non-use, release the IP: remove DNS records (forward and reverse), remove DHCP reservation, update IPAM status to available. If the address IS still in use but was flagged, update the last-seen timestamp and keep it.

### Close Out
Generate a lifecycle report: what was allocated, when, to whom, current state. Update any tickets or CMDBs. For subnet-level operations, update utilization metrics.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Ping + ARP check before allocation | Always verify, even if IPAM says available | IPAM may be stale — the network is the source of truth for conflicts |
| DNS records created with the allocation | Not deferred to later | Prevents DNS gaps that cause troubleshooting headaches |
| Reclamation requires owner notification | No silent deletion | Avoids pulling an IP out from under a running service |
| IPv4 and IPv6 handled by the same process | Unified lifecycle regardless of version | Prevents two parallel manual processes |
| Conflict detection runs continuously, not just at allocation | Periodic scan catches drift | Conflicts introduced outside the process are still detected |

---

## 5. Scope

**In scope:** IPv4 and IPv6 address allocation, subnet allocation, DNS record management (forward and reverse), DHCP scope/reservation management, conflict detection (duplicate IP), stale address reclamation, reconciliation reporting, IPAM system integration.

**Out of scope:** IPAM system installation or migration. DHCP server deployment. DNS server deployment. Layer 2 VLAN provisioning (separate use case). BGP/OSPF route management for new subnets. NAT/PAT configuration. IP planning and subnet design (input to this process).

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Allocating a duplicate IP | Service outage for existing device | Ping sweep + ARP check before committing; never trust IPAM alone |
| Reclaiming an IP that is actually in use | Service outage | Owner notification with grace period; verify via network scan before release |
| DNS record drift from actual IP assignments | Name resolution failures, misdirected traffic | Periodic reconciliation scan catches drift; alert on mismatches |
| IPAM system unavailable during allocation | Cannot allocate IPs | Queue requests and retry; fallback to manual allocation with post-sync |
| Subnet exhaustion not detected early | Emergency requests cannot be fulfilled | Track utilization metrics; alert when subnet crosses threshold (e.g., 80%) |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Query and update IPAM records via API | Yes | Cannot proceed |
| Create and delete DNS records (A, AAAA, PTR) | Yes | Engineer manages DNS manually |
| Execute network scans (ping, ARP) on target subnets | Yes | Cannot validate — conflict detection disabled |
| Orchestrate multi-step workflows with conditions | Yes | Cannot proceed |
| Schedule periodic jobs (reconciliation scans) | Yes | Engineer triggers scans manually |
| Generate reports from templates | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| IPAM (Infoblox, NetBox, BlueCat, phpIPAM, etc.) | Source of truth for IP allocation | Yes | Cannot proceed |
| DNS server (BIND, Windows DNS, Infoblox DNS, etc.) | Forward and reverse record management | Yes | Engineer manages DNS manually |
| DHCP server (ISC DHCP, Infoblox, Windows, etc.) | Reservation and scope management | No | Static assignments only |
| Network devices (routers, switches) | Verify IPs on the wire, apply interface configs | No | Allocation only, no device config |
| ITSM / ticketing (ServiceNow, etc.) | Track requests and changes | No | Engineer tracks manually |
| CMDB | Update asset records with IP assignments | No | IPAM serves as record |

### Discovery Questions

Ask the engineer before designing the solution:

1. Which IPAM system do you use? (Infoblox, NetBox, BlueCat, phpIPAM, other?)
2. Do you manage both IPv4 and IPv6, or just one?
3. How are DNS records managed today? Same system as IPAM or separate?
4. Do you use DHCP reservations, or are assignments purely static?
5. What metadata do you track per IP? (owner, purpose, site, VLAN, expiration?)
6. How do you handle IP requests today? Tickets, email, self-service portal?
7. What is your threshold for "stale" addresses? (30 days, 90 days, custom?)
8. Are there subnets that should be excluded from automated reclamation? (infrastructure, management, etc.)
9. Do you need conflict detection for existing allocations, or only for new requests?
10. Do you use a ticketing system? Which one?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One IP/subnet at a time, stop on first conflict | On-demand allocation requests |
| Bulk allocation | Allocate a range of IPs from a subnet, validate batch, commit all at once | New site/VLAN provisioning |
| Scheduled scan | Sweep all allocated IPs in a subnet, report discrepancies | Periodic reconciliation (daily/weekly) |
| Stale reclamation | Process all candidates past threshold, notify in batch, reclaim after grace period | Monthly hygiene cycle |

For reconciliation scans, process one subnet at a time to avoid overwhelming the network with scan traffic. For bulk allocation, validate the entire batch for conflicts before committing any.

---

## 9. Acceptance Criteria

1. No IP is allocated without a conflict check (ping + ARP) against the live network
2. IPAM record, DNS record, and device config are consistent after assignment
3. Forward (A/AAAA) and reverse (PTR) DNS records are created with every allocation
4. Duplicate IPs detected on the network are flagged and reported immediately
5. Stale addresses are only reclaimed after owner notification and grace period
6. Reclamation removes IPAM reservation, DNS records, and DHCP entries
7. Reconciliation report identifies IPAM-vs-network discrepancies for every scanned subnet
8. Subnet utilization alerts fire when usage crosses the configured threshold
9. IPv4 and IPv6 addresses follow the same lifecycle process
10. Evidence report is generated for every allocation, reclamation, and reconciliation run
