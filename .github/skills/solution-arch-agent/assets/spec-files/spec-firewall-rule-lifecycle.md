# Use Case: Firewall Rule Lifecycle

## 1. Problem Statement

Firewall rules accumulate. Teams request new rules urgently, security reviews them in a spreadsheet, engineers deploy them manually, and nobody cleans them up. Over time, rule bases become bloated with shadowed rules, expired exceptions, and conflicting entries. Recertification is a quarterly nightmare of chasing down rule owners. Decommissioning a rule takes as long as creating one.

**Goal:** Automate the full firewall rule lifecycle — request, validate, deploy, verify, recertify, and decommission — across network firewalls, ensuring every rule is conflict-free, auditable, and has an expiration date.

---

## 2. High-Level Flow

```
Request  →  Validate  →  Approve  →  Deploy  →  Verify  →  Recertify  →  Decommission
   │            │           │           │           │            │              │
   │            │           │           │           │            │              │
 Source,     Check for    Security    Push rule   Confirm      Periodic       Remove
 dest, port, conflicts,   review,    to target   rule is      review:        expired
 protocol,  shadowed     approve/    firewall,   active,      owner          rules,
 justifi-   rules,       reject     commit       traffic      confirms       verify
 cation,    syntax                               matches      still needed   removal,
 expiry     valid                                expected     or expire      audit log
                │
           CONFLICT? → Reject with details
```

---

## 3. Phases

### Request Intake
Accept the rule request: source, destination, port/protocol, action (permit/deny), justification, requested duration, and rule owner. Every rule must have an owner and an expiration date — no permanent rules without explicit exception approval.

### Validate
Check the proposed rule against the existing rule base. Detect conflicts: does this rule contradict an existing rule? Is it shadowed by a broader rule that already permits/denies the same traffic? Is the syntax valid for the target firewall? Check that source and destination objects exist in the firewall's address book. If conflicts are found, **reject the request with a detailed explanation of what conflicts and why**.

### Approve
Route the validated request to the security team for review. Include the validation results, conflict analysis, and risk assessment. The approver can approve, reject, or request modification. No rule deploys without approval.

### Deploy
Push the approved rule to the target firewall. Insert it at the correct position in the rule base (order matters — firewalls evaluate rules top-down). Commit the change. If the firewall rejects the rule, **capture the error and report it — do not retry blindly**.

### Verify
Confirm the rule is active in the firewall's running rule base. Optionally, generate test traffic or check logs to confirm the rule permits/blocks as expected. Compare the deployed rule against the approved request to ensure nothing was altered during deployment.

### Recertify (periodic)
On a schedule (e.g., every 90 days), notify rule owners that their rules are approaching expiration. The owner must confirm the rule is still needed. If confirmed, extend the expiration. If not confirmed within the grace period, **mark the rule for decommission**.

### Decommission
Remove expired or rejected rules from the firewall. Disable the rule first (if the platform supports it), wait a monitoring period to catch unexpected traffic drops, then delete. Generate an audit record of the removal. If disabling the rule causes alerts or traffic issues, **re-enable and escalate**.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Every rule has an expiration date | No permanent rules by default | Prevents rule base bloat; exceptions require explicit approval |
| Conflict detection before approval | Reject shadowed/conflicting rules early | Saves security team from reviewing rules that cannot work |
| Rule position matters | Insert at specified position, not just append | Firewall rule order determines match behavior — appending may never match |
| Decommission uses disable-then-delete | Two-step removal with monitoring period | Catches dependencies before permanent removal |
| Recertification is automated | System notifies owners, auto-expires unconfirmed rules | Removes the quarterly manual audit burden |

---

## 5. Scope

**In scope:** Rule request and validation, conflict and shadow detection, approval workflow, deployment to network firewalls, post-deploy verification, periodic recertification, rule decommission, audit trail.

**Out of scope:** Cloud security groups and NACLs (similar concept, different mechanics — separate use case). Firewall policy design or architecture. URL filtering and application-layer rules. NAT rule management. Firewall firmware upgrades.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rule deployed at wrong position | Traffic permitted or denied incorrectly | Validate position before deploy, verify post-deploy |
| Conflict detection misses a shadowed rule | Redundant or ineffective rule deployed | Use firewall-native conflict analysis where available, supplement with custom checks |
| Rule decommission breaks production traffic | Outage for dependent applications | Disable-then-delete with monitoring period; re-enable on alert |
| Rule owner unreachable during recertification | Rule expires, potentially dropping needed traffic | Grace period with escalation to owner's manager and security team |
| Firewall commit fails after rule push | Rule in candidate config but not active | Detect commit failure, remove uncommitted rule, report clearly |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Push configuration to network firewalls | Yes | Cannot proceed |
| Read the current rule base from firewalls | Yes | Cannot proceed |
| Detect conflicts and shadowed rules | Yes | Security team reviews manually (high risk) |
| Orchestrate multi-step workflows with approvals | Yes | Cannot proceed |
| Schedule recurring jobs (recertification) | Yes | Manual recertification process |
| Send notifications to rule owners | Yes | Manual outreach for recertification |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| ITSM / ticketing | Track rule requests, approvals, audit trail | No | Approval tracked via email or internal process |
| IPAM / address management | Validate source/destination objects exist | No | Engineer validates addresses manually |
| CMDB | Map firewalls to network zones and applications | No | Engineer identifies the correct firewall manually |
| Monitoring / SIEM | Detect traffic impact after rule changes | No | Disable-then-delete monitoring period is manual |

### Discovery Questions

Ask the engineer before designing the solution:

1. What firewall vendors are in scope? (Palo Alto, Fortinet, Check Point, Cisco ASA/FTD, Juniper SRX, etc.)
2. How is the rule base organized today — zones, policies, contexts?
3. Does the firewall support candidate configs and commits, or are changes immediate?
4. Is there an existing approval process? Where does it live — ticketing system, email, manual?
5. What is the desired rule expiration policy? (e.g., 90 days default, 1 year max)
6. How do you handle rule recertification today?
7. Are there rules that should never be auto-decommissioned? (e.g., infrastructure rules)
8. Do you use address objects/groups, or raw IPs in rules?
9. What is the acceptable monitoring period before deleting a disabled rule?
10. How many firewalls and how many rules per firewall are we managing?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Single rule | One rule request through the full lifecycle | Standard operational requests |
| Batch deploy | Multiple approved rules deployed to the same firewall in one commit | Bulk changes from a project or migration |
| Batch recertification | All rules expiring within a window reviewed together | Quarterly or monthly recertification cycles |

---

## 9. Acceptance Criteria

1. Rule requests are validated for conflicts and shadows before reaching approval
2. Conflicting rules are rejected with a clear explanation of the conflict
3. No rule is deployed without documented approval
4. Deployed rules are verified as active in the firewall's running rule base
5. Rules are inserted at the correct position, not blindly appended
6. Every rule has an owner and an expiration date
7. Owners are notified before rule expiration and given a window to recertify
8. Unconfirmed rules are disabled, monitored, then removed
9. Decommissioned rules are re-enabled if disabling causes traffic issues
10. Full audit trail exists for every rule: request, approval, deploy, recertify, decommission
