# Use Case: VPN Tunnel Provisioning (IPsec/GRE)

## 1. Problem Statement

Provisioning site-to-site VPN tunnels is a coordination-heavy, error-prone process. An engineer must configure both endpoints with matching crypto parameters, matching tunnel addresses, matching ACLs — and a single mismatch means the tunnel never comes up. Multiply that by hub-and-spoke or full-mesh topologies and you get hours of tedious, symmetric configuration work with no guarantee of first-time success.

**Goal:** Automate the end-to-end tunnel provisioning lifecycle — parameter generation, both-endpoint configuration, tunnel verification, and traffic validation — so that tunnels come up correctly on the first attempt every time.

---

## 2. High-Level Flow

```
Request     →  Design     →  Configure     →  Verify     →  Close Out
  │               │              │               │              │
  │               │              │               │              │
Validate        Generate      Apply           Tunnel UP?     Evidence
inputs,         crypto        config to       Ping across    report,
resolve         params,       Endpoint A      tunnel,        update
endpoints,      tunnel IPs,   and             check          ticket,
check           build         Endpoint B      routing,       update
reachability    configs       (both sides)    traffic        IPAM
                                              passes
                                                 │
                                            FAIL? → Rollback
```

---

## 3. Phases

### Request Validation
Validate the tunnel request: source site, destination site, tunnel type (IPsec, GRE, GRE-over-IPsec), topology (point-to-point, hub-and-spoke). Resolve device hostnames to management IPs. Confirm both endpoints are reachable and healthy. If either endpoint is unreachable or unhealthy, **stop — do not proceed**.

### Tunnel Design
Generate the matching parameter set for both sides: crypto algorithm, hash, DH group, SA lifetime, pre-shared key (or certificate reference), tunnel source/destination IPs, tunnel interface addresses. For GRE-over-IPsec, generate both the GRE and IPsec parameters. Allocate tunnel interface IPs from IPAM if available. Every parameter must be symmetric — what one side proposes, the other must accept.

### Configuration
Build device-specific configs for both endpoints. Apply configuration to Endpoint A, then Endpoint B. Config backup is taken on both devices before any changes are applied. If configuration fails on either endpoint, **rollback the changes already applied and stop**.

### Verification
Confirm the tunnel is operationally up: tunnel interface status is up/up, IKE SA is established (IPsec), GRE keepalives are passing (GRE). Ping across the tunnel from each side. If routing is involved (BGP/OSPF over tunnel), verify neighbor adjacency forms. If the tunnel does not come up within a configurable timeout (default 5 min), **trigger rollback**.

### Rollback (conditional)
Remove the tunnel configuration from both endpoints in reverse order (Endpoint B first, then Endpoint A). Restore original configs from backup. Verify the rollback did not impact existing services. If rollback fails, **escalate immediately**.

### Close Out
Generate an evidence report: tunnel parameters, config diffs (both sides), verification results, timing. Update the change ticket. Update IPAM with allocated tunnel IPs. Record the tunnel in inventory for lifecycle tracking.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Both endpoints configured in same workflow | Single orchestrated job | A half-configured tunnel is useless and confusing |
| Config backup is mandatory on both sides | No backup = no provisioning | Must have restore points for rollback |
| Crypto parameters are generated, not manually entered | Engineer selects a policy tier (e.g., "high", "standard") | Prevents mismatches and enforces security standards |
| Tunnel IPs allocated from IPAM when available | Falls back to manual input if no IPAM | Prevents IP conflicts across tunnels |
| Verification includes traffic test, not just state check | Ping across tunnel is required | Interface up does not guarantee end-to-end connectivity |

---

## 5. Scope

**In scope:** IPsec (IKEv1/IKEv2), GRE, GRE-over-IPsec tunnel provisioning. Point-to-point, hub-and-spoke, and full-mesh topologies. Pre-shared key and certificate-based authentication. Tunnel verification (state + traffic). Rollback. Evidence generation. ITSM and IPAM integration.

**Out of scope:** DMVPN/NHRP setup (separate use case). SD-WAN overlay provisioning. Firewall rule/ACL changes on intermediate devices. Certificate generation and PKI management. QoS policy over tunnels.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Crypto parameter mismatch | Tunnel never establishes | Generate both configs from a single parameter set — never configure independently |
| One endpoint configured, other fails | Dangling half-tunnel, possible routing issues | Rollback Endpoint A if Endpoint B config fails |
| Tunnel IP conflicts | Overlapping addresses across tunnels | Allocate from IPAM; if manual, validate uniqueness before applying |
| Existing services disrupted by tunnel config | Traffic loss on production device | Pre-flight health check, config backup, post-change service verification |
| Hub device overloaded in hub-and-spoke | Hub becomes bottleneck | Limit concurrent spoke provisioning; check hub resource utilization before adding tunnels |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on devices | Yes | Cannot proceed |
| Backup and diff device configurations | Yes | Cannot proceed |
| Apply configuration to multiple devices in sequence | Yes | Cannot proceed |
| Orchestrate multi-step workflows with conditions | Yes | Cannot proceed |
| Test device reachability (ping from device) | Yes | Manual verification by engineer |
| Generate reports from templates | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| IPAM (Infoblox, NetBox, etc.) | Allocate tunnel interface IPs | No | Engineer provides IPs manually |
| ITSM / ticketing (ServiceNow, etc.) | Track the change, audit trail | No | Engineer tracks manually |
| Configuration repository / source of truth | Store tunnel parameters for lifecycle tracking | No | Evidence report serves as record |
| Certificate authority / PKI | Provide certificates for IKEv2 cert-based auth | No | Use pre-shared key instead |

### Discovery Questions

Ask the engineer before designing the solution:

1. What type of tunnel? IPsec only, GRE only, or GRE-over-IPsec?
2. What is the topology? Point-to-point, hub-and-spoke, or full mesh?
3. What are the endpoint devices and what OS do they run?
4. What are the public (or WAN) IPs for each tunnel endpoint?
5. Do you have an IPAM system for allocating tunnel interface IPs?
6. What crypto policy do you require? (algorithm, hash, DH group, lifetime)
7. Pre-shared key or certificate-based authentication?
8. Will you run a routing protocol over the tunnel? Which one?
9. Do you use a ticketing system? Which one?
10. For hub-and-spoke or mesh: how many tunnels total? Can they be provisioned in parallel?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One tunnel (both endpoints) at a time, stop on first failure | Small batch, shared hub device |
| Rolling | N tunnels at a time, stop if failure rate > threshold | Medium/large hub-and-spoke deployments |
| Parallel | All tunnels at once | Full mesh in lab/non-prod, no shared devices |

For hub-and-spoke: the hub is a shared resource. Limit concurrency to avoid overloading it. For full mesh, each tunnel pair is independent and can be parallelized.

---

## 9. Acceptance Criteria

1. Tunnel only provisioned if both endpoints are reachable and healthy
2. Crypto parameters are identical on both sides (generated from single source)
3. Configuration is applied to both endpoints — never just one
4. Tunnel interface is operationally up on both endpoints
5. Traffic passes across the tunnel (ping succeeds from both sides)
6. Routing adjacency forms if a routing protocol is configured over the tunnel
7. Config backup exists for both devices before and after changes
8. Rollback removes tunnel config from both sides if verification fails
9. Evidence report is generated for every tunnel (success or failure)
10. Batch mode respects concurrency limits and stops on threshold breach
