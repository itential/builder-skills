# Use Case: Cloud Security Group Management

## 1. Problem Statement

Cloud security group rules are the perimeter firewall of every cloud workload, but they're managed through tickets and manual console clicks. Engineers copy-paste rules from spreadsheets, mistype CIDR blocks, open ports too broadly, and create conflicting or redundant rules. There's no blast-radius analysis before a change — one overly permissive rule can expose an entire subnet. Cleanup never happens, so rule sets grow until nobody understands what's allowed and why. Auditors ask for evidence and get screenshots.

**Goal:** Automate the lifecycle of cloud security group rules — create, update, and delete rules with conflict detection, blast-radius analysis, and post-change verification — across AWS Security Groups, Azure NSGs, and GCP firewall rules, producing auditable evidence for every change.

---

## 2. High-Level Flow

```
Request        →  Analyze       →  Deploy        →  Verify        →  Close Out
    │                 │                │                │                │
    │                 │                │                │                │
 Parse rule        Check for       Apply rule      Confirm rule     Update
 request:          conflicts,      change to       is active,       ticket,
 action, CIDR,     overlaps,       the cloud       test traffic     record
 port, protocol,   blast-radius    provider        flow matches     evidence,
 direction,        assessment,     API, tag        expected         notify
 target group      approval gate   the rule        behavior         requestor
                       │                                │
                  CONFLICT? →                      FAIL? → Rollback
                  Flag + pause                     rule change
```

---

## 3. Phases

### Request
Parse the incoming rule change: action (create, update, delete), target security group or NSG, rule direction (ingress/egress), protocol, port range, source/destination CIDR or security group reference, and justification. Validate the inputs — reject malformed CIDRs, invalid port ranges, or rules that reference non-existent groups. If the request is incomplete, **stop and ask for clarification**.

### Analyze
Evaluate the proposed change against the existing rule set. Detect conflicts: does this rule overlap with an existing rule? Does it contradict a deny rule? Does it widen access beyond what's intended? Perform blast-radius analysis: how many instances or workloads are affected by this security group? What other groups reference this one? Present findings to the requestor. If the blast radius exceeds a defined threshold or a conflict is detected, **require explicit approval before proceeding**.

### Deploy
Apply the rule change through the cloud provider's API. For creates, add the rule with proper tagging (owner, ticket, expiration date). For updates, modify in place or replace the rule. For deletes, remove the rule. Capture the before and after state of the security group. If the API call fails, **retry once, then abort and report**.

### Verify
Confirm the rule is active in the cloud provider's state. Query the security group and validate the rule exists (or was removed) with the correct parameters. Optionally run a connectivity test — attempt traffic on the affected port/CIDR and confirm it's allowed or denied as expected. If verification fails and auto-rollback is enabled, **revert the rule change**.

### Close Out
Generate an evidence report: the before-state, the change made, the after-state, blast-radius summary, and verification results. Update the change ticket. Notify the requestor. If the rule has an expiration date, schedule a future review or auto-deletion.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Blast-radius analysis before every change | Mandatory, not optional | One rule can affect hundreds of instances silently |
| Conflict detection flags, does not auto-resolve | Human decides on conflicts | Conflicts often indicate a design misunderstanding |
| Rules are tagged with owner, ticket, and expiration | Every rule has metadata | Enables cleanup, audit, and accountability |
| Before/after state captured for every change | Snapshot the full security group | Enables diff, rollback, and evidence |
| Expiration dates trigger automatic review | Schedule future cleanup | Prevents rule sprawl over time |

---

## 5. Scope

**In scope:** Create, update, and delete rules on AWS Security Groups, Azure NSGs, and GCP firewall rules. Conflict detection. Blast-radius analysis (instance count, cross-group references). Rule tagging. Post-change verification. Rollback on failure. Evidence generation. Expiration-based lifecycle.

**Out of scope:** Web application firewall (WAF) rules. Network ACLs (AWS) or route table changes. Cross-account or cross-subscription rule management (requires additional trust setup). Firewall-as-a-service (Palo Alto, Fortinet cloud). Security group creation/deletion (this manages rules within existing groups). Policy-as-code authoring (rules are provided as input, not generated).

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Overly permissive rule deployed (0.0.0.0/0) | Workload exposed to internet | Flag broad CIDRs, require explicit approval for /0 rules |
| Rule conflicts create unpredictable behavior | Traffic allowed or denied unexpectedly | Pre-deploy conflict detection against existing rules |
| Blast radius larger than expected | Change affects production workloads | Blast-radius threshold triggers approval gate |
| Cloud API rate limiting during batch changes | Partial rule set deployed | Implement backoff and retry, rollback partial on abort |
| Stale rules accumulate over months | Security posture degrades | Expiration tags, scheduled review reminders |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Call cloud provider APIs (AWS, Azure, GCP) | Yes | Cannot proceed |
| Query existing security group rules | Yes | Cannot proceed |
| Determine which instances are bound to a security group | Yes (for blast-radius) | Skip blast-radius analysis, proceed with warning |
| Tag cloud resources with metadata | Yes | Rules created without traceability tags |
| Orchestrate multi-step workflows with approval gates | Yes | Cannot proceed |
| Test network connectivity on specific ports | No | Skip connectivity verification, rely on API state only |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| Cloud provider API (AWS, Azure, GCP) | Apply and query security group rules | Yes | Cannot proceed |
| ITSM / ticketing (e.g., ServiceNow) | Track change request, audit trail | No | Evidence report returned directly |
| CMDB / cloud inventory (e.g., ServiceNow, CloudHealth) | Identify affected workloads for blast-radius | No | Blast-radius based on cloud API instance query only |
| Approval system | Gate high-risk changes | No | Manual approval via pause/resume |

### Discovery Questions

Ask the engineer before designing the solution:

1. Which cloud provider and account/subscription/project is the target?
2. What is the action? (Create a new rule, modify an existing rule, delete a rule?)
3. What is the target security group or NSG name/ID?
4. What is the rule? (Direction, protocol, port range, source/destination CIDR or group reference?)
5. What is the justification or ticket number for this change?
6. Should the rule have an expiration date? If so, when?
7. What blast-radius threshold should require approval? (e.g., more than 10 instances affected?)
8. Should broad rules (0.0.0.0/0, ::/0) be allowed, or always flagged?
9. Should the workflow auto-rollback on verification failure, or pause for review?
10. Are there existing security policies or naming conventions to follow for rule tags?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Sequential | One rule change at a time, stop on first failure | Default for production changes |
| Grouped | All rules for one security group at once, atomic rollback | Application onboarding with multiple rules |
| Parallel | Rules across independent security groups simultaneously | Multi-application deployment, no shared groups |

---

## 9. Acceptance Criteria

1. Rule is created, updated, or deleted as requested with correct parameters
2. Conflict detection identifies overlapping or contradictory rules before deploy
3. Blast-radius analysis reports the number of affected instances and cross-group references
4. Changes exceeding the blast-radius threshold require explicit approval
5. Broad CIDR rules (0.0.0.0/0) are flagged and require explicit approval
6. Every rule is tagged with owner, ticket, and expiration date
7. Before and after security group state is captured for every change
8. Verification confirms the rule is active (or removed) in the cloud provider's state
9. Evidence report is generated for every change, regardless of outcome
