# Use Case: DNS Record Management

## 1. Problem Statement

DNS record changes are error-prone and invisible. Engineers make changes through provider consoles or scripts with no conflict checking, no propagation verification, and no audit trail. A bad record can take down services, and nobody knows who changed what or when. Rollback means finding the old value in someone's notes.

**Goal:** Automate DNS record CRUD with conflict detection, propagation verification, optional TTL orchestration, and automatic rollback on failure -- producing a complete audit trail of every change.

---

## 2. High-Level Flow

```
Pre-Flight  →  Approval  →  TTL Staging  →  Execute  →  Verify  →  Restore TTL  →  Close Out
    │          (prod only)   (optional)      Change     Propagation   (optional)        │
    │                                          │            │                            │
 Validate                                   Apply        Query                       Evidence
 zone exists,                               record       resolvers                   report,
 no conflicts,                              change,      to confirm,                 update
 format checks,                             sync PTR     configurable                ticket
 snapshot existing                          (optional)   max wait
                                                            │
                                                       FAIL? → Rollback
                                                               (restore snapshot)
```

---

## 3. Phases

### Pre-Flight
Validate the requested change before touching DNS. Confirm the zone exists and the provider is reachable. Check for conflicts: does a record already exist (for creates)? Does it exist (for updates/deletes)? Enforce CNAME exclusivity per RFC 1034 -- no CNAME where other types exist, no CNAME at the zone apex. Validate IP format for A/AAAA records. If reverse record sync is requested, confirm the reverse zone exists. Snapshot the existing record for rollback. If any critical check fails, **stop**.

### Approval
Production zone changes require human approval before proceeding. Non-production zones skip this gate entirely. The approver sees the pre-check report and change summary.

### TTL Staging (optional, best-effort)
Lower the TTL on the existing record to a short value (e.g., 300s) so caches drain faster before the actual change. This is best-effort: if it fails, proceed with a warning. **Never block the workflow waiting for the old TTL to expire.** Ideally, TTL lowering happens well in advance of the change window as a separate pre-staging step. Skipped for create operations (no existing record).

### Execute Change
Apply the DNS record change (create, update, or delete) via the provider API. If reverse record sync is enabled and this is an A/AAAA record, create or update the corresponding PTR record. If IPAM sync is enabled, update the IPAM system. Trigger DNSSEC re-signing if the zone is signed (the provider handles signing; the workflow just triggers it).

### Propagation Verification
Query DNS resolvers to confirm the change is live. Check the authoritative nameservers first (must pass), then recursive resolvers (best-effort). Poll at intervals up to a configurable maximum wait time (default 10 minutes). **Verification works by querying resolvers, not by sleeping for a fixed duration.** If the authoritative check fails after the timeout, trigger rollback.

### TTL Restoration (optional)
After successful verification, restore the TTL to the desired long-term value. Verify the TTL update took effect.

### Rollback (conditional)
If verification fails and rollback is enabled, restore the previous record value from the snapshot taken during pre-flight. For creates, delete the new record. Re-verify the rollback succeeded. If reverse or IPAM sync was done, revert those too. If rollback itself fails, **escalate immediately**.

### Close Out
Generate an evidence report with before/after snapshots, propagation results, and timing. Update the change ticket. Write an immutable audit log entry.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Conflict detection before any change | Pre-flight checks for existing records, CNAME exclusivity, IP format | Prevent DNS corruption; catch mistakes before they propagate |
| TTL staging is optional and best-effort | Never blocks for full old TTL; proceeds with warning if lowering fails | Old TTLs can be hours or days; blocking is impractical |
| Propagation verified by querying resolvers | Polls authoritative + recursive resolvers, not a fixed sleep | Actual confirmation, not a guess based on TTL math |
| Rollback reverts to snapshot | Previous record value captured before change | Guaranteed known-good state to restore |
| Production zones require approval | Non-prod auto-proceeds | Matches change management discipline without slowing dev |
| Reverse record sync is non-blocking | PTR failure logs a warning and creates a follow-up ticket | Don't roll back a successful forward record for a PTR failure |
| IPAM sync is non-blocking | IPAM failure logs a warning and creates a follow-up ticket | DNS change is the primary objective |
| Batch records have independent success/failure | One bad record doesn't kill the batch | Maximizes throughput; failures are individually reported |
| Evidence is generated regardless of outcome | Success, failure, and rollback all produce a report | Audit trail is non-negotiable |

---

## 5. Scope

**In scope:** CRUD operations for A, AAAA, CNAME, MX, TXT, SRV, PTR, NS records. Multi-provider support (Infoblox, Route53, Cloudflare, Azure DNS, BIND, Windows DNS). Conflict detection. TTL staging. Propagation verification. Rollback. Forward/reverse record sync. IPAM sync. Approval for production zones. Audit trail. Bulk operations (CSV import, provider migration).

**Out of scope:** Zone creation and delegation. DNSSEC key management and rotation. DNS server installation or patching. Resolver/cache configuration. Domain registration and renewal. SSL/TLS certificate management.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Propagation takes longer than expected | Stale records served to clients | Poll resolvers up to configurable max wait; don't rely on fixed sleep |
| Provider API unavailable during change | Change cannot be applied | Retry with backoff, abort if still down; no partial state since change hasn't been applied |
| Rollback fails | Bad record persists | Critical alert, immediate escalation; never retry indefinitely |
| CNAME conflict not detected | DNS resolution breaks for the name | Pre-flight enforces RFC 1034 exclusivity before any change |
| Batch operation overwhelms provider | Rate limiting, throttled API calls | Enforce per-provider rate limits; configurable batch abort threshold |
| Split-horizon DNS targets wrong view | Change applied to wrong internal/external view | Discovery question captures which view; provider adapter targets explicitly |
| DNSSEC re-sign fails after change | Validating resolvers return SERVFAIL | Alert engineer; record is correct but unsigned |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Create/update/delete DNS records via provider API | Yes | Cannot proceed |
| Query existing DNS records for conflict detection | Yes | Cannot proceed |
| Perform DNS lookups from multiple vantage points | Yes | Cannot proceed -- no propagation verification |
| Orchestrate multi-step workflows with conditions and loops | Yes | Cannot proceed |
| Render templates for reports and PTR name derivation | Yes | Cannot proceed |
| Parse CSV for bulk operations | No | Batch mode unavailable; single-record still works |
| Manual approval gate | No | All changes auto-proceed; add controls outside the workflow |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| DNS provider (Infoblox, Route53, Cloudflare, etc.) | Authoritative source for zone data; receives CRUD calls | Yes | Cannot proceed |
| IPAM system (NetBox, Infoblox IPAM, etc.) | IP validation and forward/reverse sync | No | Skip IPAM checks; engineer manages manually |
| ITSM / ticketing | Track changes, audit trail, production approvals | No | Engineer tracks manually |
| Monitoring / alerting | Notify on DNS changes or failures | No | Engineer monitors manually |

### Discovery Questions

1. What DNS provider do you use? (Infoblox, Route53, Cloudflare, Azure DNS, BIND, Windows DNS?)
2. What zone are you modifying? Does it already exist?
3. What record types do you need to manage? (A, AAAA, CNAME, MX, TXT, SRV, PTR, NS?)
4. Is this a production or non-production zone? Do you need an approval step?
5. Is DNSSEC enabled on this zone?
6. Do you need reverse (PTR) record synchronization for A/AAAA changes?
7. Do you have an IPAM system? Which one?
8. Is this a single record change or a bulk operation?
9. Do you want to pre-stage TTL lowering before the change window?
10. What are your propagation verification requirements? (Authoritative only? Specific resolvers?)
11. Do you use split-horizon DNS (internal vs external views)?
12. Do you use a ticketing system? Which one?
13. Are there existing automations you'd like to reuse? (DNS workflows, IPAM sync, ticket creation?)

---

## 8. Bulk Operations

Bulk mode accepts a list of records (directly or via CSV import) and runs each through the single-record workflow independently. Records are grouped by zone and provider. Each record succeeds or fails on its own -- one failure does not kill the batch. Rate limits are respected per provider. If the failure rate exceeds a configurable threshold (default 20%), the batch aborts.

For provider migrations (moving all records from one provider to another), the workflow exports records from the source, validates them against the destination, executes the import, and verifies each record. NS delegation cutover is out of scope and flagged for manual action.

---

## 9. Acceptance Criteria

1. Pre-flight detects and blocks conflicting record creates (e.g., CNAME where A record exists)
2. Pre-flight validates IP format and rejects invalid addresses
3. Create, update, and delete operations produce the correct DNS state verified by authoritative query
4. Propagation is verified by querying resolvers, not by sleeping for a fixed duration
5. Rollback restores the previous record value when propagation verification fails
6. TTL staging lowers TTL before the change and restores it after -- without blocking for the old TTL
7. Reverse (PTR) record is created when forward A record is created with sync enabled
8. Production zone changes are blocked until approval is granted
9. Evidence report is generated for every run (success, failure, or rollback)
10. Batch mode processes records independently, respects rate limits, and aborts on configurable failure threshold
