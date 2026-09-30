# Use Case: Load Balancer VIP Provisioning

## 1. Problem Statement

Provisioning a new Virtual IP (VIP) on a load balancer is a multi-step, error-prone process. Engineers must create the VIP, define a server pool, add pool members with correct ports, attach health monitors, configure persistence profiles, and bind it all together. Every load balancer platform has different terminology and workflows. Mistakes — wrong port, missing health monitor, typo in a pool member IP — cause outages for the application team waiting on the VIP. There's no consistency between requests, and no verification that the VIP actually works before handing it off.

**Goal:** Automate end-to-end VIP provisioning across any load balancer platform — define the VIP, pool, members, health monitor, and persistence profile from a single request, verify the VIP is serving traffic, and produce evidence for the application team.

---

## 2. High-Level Flow

```
Validate       →  Build         →  Deploy        →  Verify        →  Close Out
    │                 │                │                │                │
    │                 │                │                │                │
 Check inputs,     Assemble        Push config      Test VIP        Update
 resolve IPs,      VIP, pool,      to the load      responds,       ticket,
 confirm pool      members,        balancer,        health          notify
 members are       monitor,        activate         monitors        requestor,
 reachable,        persistence                      pass, pool      record
 no IP             into a                           members         evidence
 conflicts         config set                       healthy
                                                        │
                                                   FAIL? → Rollback VIP
```

---

## 3. Phases

### Validate
Confirm all inputs are complete and consistent. Resolve hostnames to IPs if needed. Verify pool member IPs are reachable from the load balancer network. Check for IP conflicts — is the requested VIP address already in use? Verify the target load balancer is reachable and the requested partition/tenant exists. If any critical validation fails, **stop — do not push partial config**.

### Build
Assemble the full configuration set: VIP (address, port, protocol), server pool (name, load balancing method), pool members (IP, port, weight, priority group), health monitor (type, interval, timeout, expected response), and persistence profile (source-IP, cookie, SSL session). The configuration is platform-neutral at this stage — a standard input format that gets translated to platform-specific syntax during deploy.

### Deploy
Push the assembled configuration to the target load balancer. Create objects in dependency order: health monitor first, then pool with monitor attached, then pool members, then VIP bound to the pool with persistence. If any step fails mid-deploy, **roll back all objects created so far** to avoid orphaned config.

### Verify
Confirm the VIP is functional. Check that the VIP is active and listening. Check that pool members show as healthy according to the attached monitor. Optionally send a synthetic test request through the VIP and verify the response. If verification fails and auto-rollback is enabled, **remove the VIP and all associated objects**.

### Close Out
Record the provisioned VIP details (address, port, pool members, monitor type). Update the service request or change ticket. Notify the application team with connection details. Generate evidence showing the VIP is live and healthy.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Platform-neutral input format | Single request schema for all LB platforms | Requestors don't need to know LB internals |
| Deploy in dependency order | Monitor → Pool → Members → VIP | Avoids broken references during creation |
| Rollback on partial deploy failure | Remove all objects created in this run | No orphaned config left behind |
| Verification includes synthetic test | Optional health probe through VIP | Proves end-to-end path, not just config exists |
| IP conflict check before deploy | Query LB and IPAM for existing VIPs | Prevents silent conflicts that cause outages |

---

## 5. Scope

**In scope:** VIP creation with pool, members, health monitor, and persistence profile. Platform-specific translation for F5, Citrix ADC, NSX-ALB, HAProxy, and cloud ALBs (AWS ALB/NLB, Azure LB, GCP LB). IP conflict detection. Post-deploy verification. Rollback on failure. ITSM ticket update. Evidence report.

**Out of scope:** SSL certificate management (separate lifecycle). DNS record creation for the VIP (separate use case). WAF policy attachment. Global server load balancing (GSLB) across sites. Capacity planning or LB selection. Modifying existing VIPs (update/delete is a separate workflow).

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| VIP IP conflict with existing entry | Traffic blackholed or split | Pre-deploy check against LB config and IPAM |
| Pool member unreachable | VIP active but no healthy backends | Pre-validate member reachability, flag before deploy |
| Health monitor misconfigured | Members marked down incorrectly | Verify monitor parameters match application protocol |
| Partial deploy leaves orphaned objects | Config drift, confusing cleanup | Rollback all objects on any mid-deploy failure |
| Platform API unavailable during deploy | Incomplete provisioning | Retry with backoff, abort and rollback after max retries |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Configure load balancer objects via API or CLI | Yes | Cannot proceed |
| Query existing LB config for conflict detection | Yes | Cannot proceed |
| Test network reachability to pool member IPs | Yes | Skip pre-validation, risk deploying to unreachable members |
| Orchestrate multi-step workflows with rollback | Yes | Cannot proceed |
| Translate platform-neutral input to vendor-specific config | Yes | Cannot proceed |
| Send synthetic HTTP/TCP requests for verification | No | Skip synthetic test, rely on LB health status only |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| IPAM (e.g., Infoblox, NetBox) | IP conflict check, VIP address allocation | No | Manual IP provided, conflict check limited to LB only |
| ITSM / ticketing (e.g., ServiceNow) | Track service request, audit trail | No | Evidence report returned to requestor directly |
| DNS (e.g., Infoblox, Route53) | Create A/CNAME record for VIP | No | DNS handled separately |
| CMDB | Resolve application-to-server mappings for pool members | No | Pool members provided explicitly in request |

### Discovery Questions

Ask the engineer before designing the solution:

1. Which load balancer platform and version? (F5 BIG-IP, Citrix ADC, NSX-ALB, cloud?)
2. What partition, tenant, or virtual server group should the VIP be created in?
3. What is the VIP address and port? Is the IP pre-allocated or should it be requested from IPAM?
4. What protocol does the application use? (HTTP, HTTPS, TCP, UDP?)
5. What are the pool members? (IP:port pairs, weights, priority groups?)
6. What load balancing method? (round-robin, least-connections, IP-hash?)
7. What health monitor type? (HTTP 200 check, TCP connect, custom URI?)
8. Do you need session persistence? What type? (source-IP, cookie, SSL session?)
9. Should the workflow auto-rollback the VIP on verification failure, or pause for review?
10. Is there a service request or change ticket to update?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One VIP at a time, stop on first failure | Default for production, safest |
| Parallel | Multiple VIPs simultaneously on different LBs | Multi-site deployments, independent targets |
| Rolling | N VIPs at a time, pause between batches | Large application rollout across shared LBs |

---

## 9. Acceptance Criteria

1. VIP is created with the correct address, port, and protocol
2. Server pool is created with the correct load balancing method
3. All pool members are added with correct IP, port, and weight
4. Health monitor is attached and pool members show as healthy
5. Persistence profile is configured as requested
6. No IP conflicts exist with pre-existing VIPs
7. Synthetic test through the VIP returns an expected response (if enabled)
8. Partial deploy failure results in full rollback with no orphaned objects
9. Evidence report is generated with VIP details, pool member status, and verification results
