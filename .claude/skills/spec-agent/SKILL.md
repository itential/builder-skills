---
name: spec-agent
description: Use this skill to start any new automation delivery — when someone wants to automate something, build a new use case, figure out requirements, write up an HLD, or kick off a project on the Itential Platform. Trigger it for phrases like "I want to automate X", "help me build a workflow for Y", "we're starting a new automation project", "I need to define requirements for Z", "kick off a delivery", or "let's start with requirements". This is the entry point for the spec-driven delivery lifecycle. It picks from 22 built-in use case specs or starts from scratch, refines requirements with the engineer, and produces an approved customer-spec.md. Use it whenever someone is at the beginning of building something new and hasn't yet defined what they're building. For ad-hoc platform exploration, use /explore instead. Hands off to /solution-arch-agent after approval.
---

# Spec Agent

**Stage:** Requirements
**Owns:** Defining what needs to be built. Producing the approved HLD.
**Hands off to:** `/solution-arch-agent`

---

## Stage Expectations

| | |
|--|--|
| **Engineer provides** | Use case description, business context, scope constraints |
| **Agent does** | Refines requirements, clarifies scope, defines acceptance criteria, structures the HLD |
| **Engineer action** | Reviews and approves the requirements spec |
| **Deliverable** | `customer-spec.md` (HLD, approved) |
| **Customer receives** | Approved statement of what will be built — scope, constraints, acceptance criteria. Nothing is assessed or built until this is signed off. |

Requirements defines what is needed. Nothing is built or assessed until this is approved.

**No auth. No API calls. Pure conversation.**

---

## How to Begin

```
/spec-agent
    │
    ├── Deliver from Spec → Pick spec → Fork → Refine → Approve → /solution-arch-agent
    │
    └── Already set up? → Reuse existing working directory
```

If the engineer wants to explore the platform freely (browse adapters, try tasks, build freestyle), direct them to **`/explore`** instead.

---

## Step 1: Pick a Spec

Present available specs from `${CLAUDE_PLUGIN_ROOT}/spec-files/`, grouped by category:

| Category | Specs |
|----------|-------|
| **Networking** | Port Turn-Up, VLAN Provisioning, Circuit Provisioning, BGP Peer, VPN Tunnel, WAN Bandwidth |
| **Operations** | Software Upgrade, Config Backup, Health Check, Device Onboarding, Device Decommissioning, Change Management, Incident Remediation |
| **Security** | Firewall Rules, Cloud Security Groups, SSL Certificates |
| **Infrastructure** | DNS Records, IPAM Lifecycle, Load Balancer VIP, Config Drift Remediation, Compliance Audit |

Or the engineer describes what they need and you recommend a spec.

---

## Step 2: Fork the Spec

```bash
mkdir -p {use-case-name}
# Only fork if it doesn't already exist — engineer may have customized from a previous session
[ ! -f {use-case}/customer-spec.md ] && cp ${CLAUDE_PLUGIN_ROOT}/spec-files/spec-port-turn-up.md {use-case}/customer-spec.md
```

If `{use-case}/customer-spec.md` already exists, **reuse it** — do not overwrite.

If the engineer provided credentials or a `.env` file exists, save it to `{use-case}/.env` for later use during Feasibility. Do NOT authenticate yet.

---

## Step 3: Understand and Refine

Read `{use-case}/customer-spec.md` and extract:
- **Phases** from Section 3 (workflow stages)
- **Design decisions** from Section 4 (constraints)
- **Capabilities** and **Integrations** tables from Section 7
- **Discovery questions** from Section 7
- **Acceptance criteria** from Section 9

Ask: *"Do you have existing documentation I should follow? Naming conventions, change policies, runbooks, config standards?"*

Write to `{use-case}/customer-context.md` if provided.

Then go through the spec's discovery questions — skip anything the spec already answers, ask only what the engineer must decide.

Incorporate all input into `{use-case}/customer-spec.md`:
- Added requirements → Section 7
- Changed scope → Section 5
- Business rules → relevant sections
- Changed decisions → Section 4

---

## Step 4: Present for Approval

Show the engineer the updated spec:
- Summary of changes from the generic spec
- What's in scope vs out of scope
- Discovery question answers captured

Ask: *"Here's your spec. Review it — add, remove, or change anything. When you approve it, I'll hand off to the Solution Architecture Agent."*

**When the engineer approves: the spec is locked.** Save the file.

---

## Step 5: Set Expectations and Hand Off

Tell the engineer what happens next:

> "Requirements are locked. Here's the rest of the delivery:
>
> 1. **Feasibility** — The Solution Architecture Agent connects to your platform and assesses what's possible against your approved spec.
> 2. **Design** — A solution design is produced with exactly what to build, reuse, and skip. You approve it before anything is built.
> 3. **Build** — The Builder Agent implements the approved design, tests each component, and delivers the project.
> 4. **As-Built** — What was actually delivered is recorded, including any deviations and learnings.
>
> You own approval at Feasibility and Design. Nothing gets built without your sign-off."

**Artifact-based handoff.** The workspace the Solution Architecture Agent receives:

```
{use-case}/
  customer-spec.md    ← approved HLD (Requirements complete)
  .env                ← credentials (if provided)
  customer-context.md ← business rules, naming (if provided)
```

No auth. No platform data. `/solution-arch-agent` owns everything from Feasibility onward.

---

## Files Created

| File | Purpose |
|------|---------|
| `customer-spec.md` | Approved HLD — the source of truth for this delivery |
| `.env` | Credentials saved for later auth during Feasibility |
| `customer-context.md` | Business rules and naming conventions (if provided) |
