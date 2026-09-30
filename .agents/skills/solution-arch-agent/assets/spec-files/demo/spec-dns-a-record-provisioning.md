# Use Case: DNS A Record Provisioning

## 1. Problem Statement

Engineers create DNS A records manually through provider consoles or ad-hoc scripts. There's no pre-flight validation — duplicate records get created, IP conflicts go undetected, and mistakes propagate before anyone notices. There's no human review step for changes that could impact production services. When something goes wrong, rollback is manual and there's no record of what changed or who approved it.

**Goal:** Automate DNS A record creation with pre-flight conflict detection, human approval before the change goes live, automatic rollback if denied, and notification to the engineering team — producing a deterministic, auditable workflow that behaves the same on every run.

---

## 2. High-Level Flow

```
Phase 1          Phase 2          Phase 3               Phase 4
Pre-Check   →   Execution   →   Post-Check + HITL   →   Notify
(Verify)        (Act)           (Validate)              (Inform)
    │               │                │                      │
 Query existing  Create the       Confirm record       Send notification
 records,        A record         is live,             with change
 detect          if clear         present to           details
 conflicts                        operator
                                     │
                              Approved? → Proceed to notify
                              Denied?   → Rollback the record
```

---

## 3. Phases

### Phase 1: Pre-Check (Verify)

Before any write operation, query the DNS provider for existing A records matching the requested hostname. Three possible outcomes:

| Outcome | Condition | Action |
|---------|-----------|--------|
| **Clear** | No existing record for this hostname | Proceed to Phase 2 |
| **Idempotent** | Record exists with the exact same IP | Stop — the desired state already exists. No action needed. |
| **Conflict** | Record exists with a different IP | Stop — flag the conflict. Do not overwrite silently. |

The idempotency check makes this workflow safe to re-run. The conflict check prevents silent IP overwrites that could take down services.

### Phase 2: Execution (Act)

Create the A record in the DNS provider using the validated inputs. Extract the provider's record reference ID for use in rollback and audit trail.

### Phase 3: Post-Check + Human Review (Validate)

After creation, query the DNS provider again to confirm the record is live. Then present the change details to a human operator for review — including the hostname, IP, zone, and provider reference.

The operator can **approve** (proceed to notification) or **deny** (trigger rollback).

**Key design question:** Should the record be created before or after human review?

- **Create-then-review** — the reviewer sees confirmed system state (the record exists, the Ref-ID is real). If denied, rollback deletes it. More information for the reviewer, but requires rollback capability.
- **Review-then-create** — nothing changes until approved. Simpler, but the reviewer is approving a plan, not a confirmed state.

### Phase 4: Notify (Inform)

Send a notification to the engineering team with the change details: hostname, IP, zone, record reference, and the reviewer's decision. Notification failure should not roll back the DNS change — the record is the primary deliverable, notification is secondary.

### Rollback

If the human reviewer denies the change, delete the record that was created in Phase 2 using the captured reference ID. If rollback itself fails, escalate immediately — a record exists that shouldn't.

---

## 4. Key Design Decisions

| Decision | Options | Considerations |
|----------|---------|----------------|
| Create-then-review vs review-then-create | Create first, then seek approval / Get approval first, then create | Create-first gives reviewer real state; review-first avoids needing rollback |
| HITL mechanism | Manual task in workflow / Separate child workflow / External approval system | Simplicity vs reusability vs integration with existing approval flows |
| Notification channel | Email / ITSM ticket / Chat (Slack, Teams) / Multiple | What does the team already use? Is email sufficient? |
| Notification failure handling | Block and retry / Non-blocking warning / Skip silently | Is notification critical or informational? |
| Rollback failure handling | Retry / Escalate immediately / Both | A failed rollback means an unauthorized record persists |
| Post-check failure handling | Block the workflow / Non-blocking warning, proceed to HITL | Replication delays may cause transient failures — is a warning enough? |
| API approach | REST API via adapter / CLI via SSH / Direct SDK calls | What does the DNS provider support? What adapter is available? |
| Service exposure | Manual form only / API endpoint only / Both | Who triggers this — operators via UI, or upstream systems via API? |

---

## 5. Scope

**In scope:** A record creation for a single hostname. Pre-flight conflict and idempotency detection. Post-creation verification. Human approval gate with rollback on denial. Notification to engineering team.

**Out of scope:** Other record types (AAAA, CNAME, MX, TXT, SRV, PTR, NS). Record update or delete as a primary operation (delete is only used for rollback). Bulk/batch record operations. Multi-provider support. PTR/reverse record synchronization. DNSSEC. Propagation verification via external resolvers. TTL management. IPAM integration. ITSM ticket creation.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| DNS provider API unavailable during create | Record cannot be created | Error transition to a clear outcome — no partial state since nothing was written |
| Rollback fails after reviewer denial | Unauthorized record persists in DNS | Escalation path — set outcome to CRITICAL, alert immediately |
| Post-check fails due to replication delay | Reviewer sees stale data | Non-blocking warning — proceed to HITL, note the delay |
| Duplicate workflow runs for same hostname | Multiple records created | Phase 1 idempotency check prevents duplicates — safe to re-run |
| Notification system down | Team not informed of change | Non-blocking — DNS change is the deliverable, not the email |
| Operator ignores HITL gate | Workflow stalled indefinitely | Platform timeout or escalation policy (outside workflow scope) |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Query existing DNS A records by hostname | Yes | Cannot detect conflicts or idempotency — unsafe to proceed |
| Create DNS A record via provider API | Yes | Cannot proceed |
| Delete DNS A record (for rollback) | Yes | Cannot offer rollback — review-then-create becomes the only option |
| Human-in-the-loop gate (pause for operator decision) | Yes | Cannot proceed — HITL is mandatory per spec |
| Send email notification | No | Skip Phase 4 — DNS change still works without notification |
| Build dynamic request bodies from job variables | Yes | Cannot assemble API payloads |
| Branch on conditions (record exists, IP matches) | Yes | Cannot implement pre-check logic |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| DNS provider (e.g., Infoblox, Route53, Cloudflare) | Authoritative source for A records — receives query, create, delete calls | Yes | Cannot proceed |
| Email server | Deliver notification to engineering team | No | Phase 4 skipped — DNS change still works |

### Discovery Questions

1. **Which DNS provider do you use?** (Infoblox, Route53, Cloudflare, Azure DNS, other?) Is the adapter installed and connected?
2. **Which adapter methods are available?** Specifically: query/get A records, create A record, delete A record. What are the exact task names?
3. **What zone are you targeting?** Does the zone already exist? Is there a default zone?
4. **Create-then-review or review-then-create?** Do you want the reviewer to see the confirmed state (record already created, real Ref-ID) or approve a plan before anything changes?
5. **Who reviews changes?** Is there a specific operator role, or does the requestor self-review? Should the reviewer be different from the requestor?
6. **How should the team be notified?** Email? Chat? Ticket? Who receives the notification?
7. **What happens if notification fails?** Should it block the workflow or proceed with a warning?
8. **How should this be triggered?** Operator filling out a form in the UI? API call from an upstream system? Both?
9. **What input fields are needed?** Hostname, IP, zone — anything else? Adapter selection? Notification recipient?
10. **What does the operator need to see in the review step?** Hostname and IP only? Or also zone, Ref-ID, record key?
11. **Are there existing DNS workflows or templates to reuse?** Any prior automation for this provider?

---

## 8. Batch Strategy

Not applicable for v1 — this spec covers single-record operations only. Batch support (CSV import, bulk provisioning) is a future extension.

---

## 9. Acceptance Criteria

1. Phase 1 detects idempotency — workflow stops cleanly when the exact record already exists
2. Phase 1 detects conflict — workflow stops cleanly when a record exists with a different IP
3. Phase 2 creates the A record and captures the provider reference ID
4. Phase 3 post-check confirms the record is live in the DNS provider
5. HITL gate pauses for operator review with change details visible
6. Approve → record persists, notification sent, outcome: SUCCESS
7. Deny → record deleted (rollback), outcome: ROLLED BACK
8. Every adapter/external call has an error path — no stuck workflows
9. Notification failure does not roll back the DNS change
10. Workflow produces a clear outcome variable on every run (SUCCESS, IDEMPOTENT, CONFLICT, ROLLED BACK, ERROR, CRITICAL)
