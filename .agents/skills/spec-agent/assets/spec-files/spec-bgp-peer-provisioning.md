# Use Case: BGP Peer Provisioning

## 1. Problem Statement

Adding a BGP peering session requires precise coordination between two routers, often managed by different teams or organizations. Engineers must agree on AS numbers, peer IPs, route policies, and prefix limits — then configure both sides correctly and verify the session establishes. A typo in an AS number or a missing route-map on one side means the session never comes up, and troubleshooting is a back-and-forth between teams. For service providers managing hundreds of peering sessions, this manual process does not scale.

**Goal:** Automate the full BGP peer lifecycle — validate inputs, deploy config to both sides, verify session establishment and route exchange — with rollback if the session fails to come up.

---

## 2. High-Level Flow

```
Validate     →  Pre-Flight   →  Deploy       →  Deploy      →  Verify     →  Post-Flight  →  Close
Inputs          Checks          Near Side       Far Side       Session       Checks          Out
   │               │               │               │              │              │              │
   │               │               │               │              │              │              │
 AS numbers,    Check both      Apply BGP      Apply BGP     Wait for       Confirm        Update
 peer IPs,      devices are     config to      config to     session to     routes are     ticket,
 route policy,  reachable,      the local      the remote    reach          exchanged,     generate
 prefix         backup          router         router        Established    prefix         evidence
 limits         configs                                      state          counts         report
                                                                │            match
                                                           FAIL? → Rollback both sides
```

---

## 3. Phases

### Validate Inputs
Validate all peering parameters before touching any device. Confirm the AS numbers are valid (1-4294967295 for 4-byte ASN). Confirm the peer IP addresses are valid and in the correct address family (IPv4 or IPv6). Confirm the route policy names are provided for both sides. If prefix limits are specified, confirm they are reasonable. If any input is invalid, **stop with a clear error — do not deploy bad config**.

### Pre-Flight Checks
Verify both devices are reachable and healthy. Backup the running config on both sides. Check that the peer IP addresses are routable between the two devices (a ping or traceroute from near side to far side). Confirm the BGP process is running on both devices. Check that the proposed peer does not already exist — if it does, **stop and ask if this is a modify operation instead**.

### Deploy Near Side
Generate and apply the BGP neighbor configuration to the local router. This includes the neighbor statement, remote AS, route-map references (inbound and outbound), prefix limits, timers, and any authentication (MD5 or TCP-AO). Verify the config was applied by reading it back. If the apply fails, **stop — do not configure the far side**.

### Deploy Far Side
Generate and apply the mirror BGP configuration to the remote router. The far side config uses the near side's IP as the neighbor address and the near side's AS as the remote AS. Same route-map, prefix limit, and authentication settings (matched to the near side). Verify the config was applied by reading it back. If the apply fails, **rollback the near side**.

### Verify Session
Wait for the BGP session to reach the Established state. Poll the BGP neighbor status on both devices with a configurable timeout (default: 3 minutes). If the session does not establish, capture the current state on both sides (Idle, Active, OpenSent, OpenConfirm) and the last reset reason. If verification fails and auto-rollback is enabled, **rollback both sides**.

### Post-Flight Checks
Confirm routes are being exchanged. Check that the near side is receiving prefixes from the far side and vice versa. Verify prefix counts are within the expected range. If route exchange looks healthy, save the running config on both devices to make the change persistent.

### Close Out
Update the change ticket with the peering details: local and remote AS, peer IPs, session state, prefix counts, and timing. Generate an evidence report with before/after BGP neighbor tables. If the peering was part of a larger provisioning request, update the parent record.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Input validation is a hard gate | Reject bad AS numbers, IPs, or missing policies | A misconfigured BGP peer can leak routes or black-hole traffic |
| Near side deploys first | If it fails, nothing to roll back on far side | Reduces the blast radius of a failed deploy |
| Both sides must be rolled back together | Partial config is worse than no config | A one-sided BGP config will never establish and creates confusion |
| Session verification has a timeout | BGP can take time to negotiate | But it should not take more than a few minutes in most cases |
| Config is saved only after verification | Not immediately after deploy | Ensures a reload will clear a bad peering if something goes wrong later |
| Duplicate peer check before deploy | Stop if peer already exists | Prevents accidental overwrite of existing sessions |

---

## 5. Scope

**In scope:** eBGP and iBGP peer addition, peer modification (update route policy, prefix limits, timers), peer removal, session verification, route exchange validation, config backup/rollback, evidence generation.

**Out of scope:** Route policy design and creation (input to this process). BGP route reflector topology design. Internet peering exchange (IX) port provisioning. BGP security (RPKI, ROA validation) setup. Traffic engineering and path manipulation. Full mesh or confederation design.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Config applied to wrong device | Peering with unintended neighbor | Validate device identity and peer IPs before deploy |
| Session never establishes | No traffic flow on new peer | Timeout with detailed state capture, auto-rollback |
| Route leak due to missing or wrong policy | Unintended traffic paths, potential outage | Validate route-map exists on both devices before deploy |
| Prefix limit exceeded immediately | Session torn down right after establishing | Check current prefix count against limit before applying |
| Far side managed by another team | Cannot deploy both sides automatically | Support "near side only" mode with instructions for far side |
| Authentication mismatch | Session stuck in Active state | Ensure both sides use the same auth config, verify in template |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on network devices | Yes | Cannot proceed |
| Generate device config from templates with variables | Yes | Cannot proceed |
| Apply config and read it back for verification | Yes | Cannot proceed |
| Backup and restore device configurations | Yes | Cannot proceed |
| Poll device state with timeout | Yes | Cannot proceed |
| Orchestrate multi-step processes with conditional rollback | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| Near-side router | Apply BGP config, verify session | Yes | Cannot proceed |
| Far-side router | Apply mirror BGP config, verify session | Depends | "Near side only" mode if not accessible |
| ITSM / ticketing (e.g., ServiceNow) | Track the change | No | Engineer tracks manually |
| IPAM (e.g., Infoblox, NetBox) | Validate peer IPs, allocate link addresses | No | Engineer provides IPs manually |
| Route policy repository | Validate route-map names exist | No | Engineer confirms policies exist |

### Discovery Questions

Ask the engineer before designing the solution:

1. Is this eBGP (between different AS) or iBGP (within the same AS)?
2. What are the local and remote AS numbers?
3. What are the peer IP addresses on both sides? IPv4, IPv6, or both?
4. What route policies (route-maps) should be applied inbound and outbound?
5. What are the prefix limits for each direction?
6. Is MD5 or TCP-AO authentication required?
7. Do you have access to configure both sides, or only the near side?
8. What device OS are the routers running? (IOS, IOS-XR, NX-OS, Junos, EOS, etc.)
9. Should the session use BFD for fast failure detection?
10. Is this a single peer addition, or do you need to provision multiple peers in batch?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One peering session at a time, verify each before moving on | Mixed device types, first-time peers |
| Grouped by router | All peers on one router at once, then verify all sessions together | Adding multiple peers to a single device |
| Parallel | Multiple independent peering sessions simultaneously | Large-scale peering buildout, IX provisioning |

For batch runs, abort if any session fails to establish and auto-rollback is enabled. Generate a summary showing per-peer status: established with prefix counts, failed with state and reason, or rolled back.

---

## 9. Acceptance Criteria

1. Invalid inputs (bad AS numbers, unreachable IPs, missing policies) are rejected before any config is deployed
2. Both devices have a config backup before any changes are made
3. BGP config is applied to both sides and verified by reading it back
4. BGP session reaches Established state within the configured timeout
5. Routes are exchanged and prefix counts are within expected range
6. If the session fails to establish, both sides are rolled back cleanly
7. Running config is saved to startup only after successful verification
8. Evidence report includes peering parameters, before/after BGP tables, session state, and prefix counts
