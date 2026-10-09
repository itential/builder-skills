---
name: spec-agent
description: Use this skill to start any new automation delivery — when someone wants to automate something, build a new use case, figure out requirements, write up an HLD, or kick off a project on the Itential Platform. Trigger it for phrases like "I want to automate X", "help me build a workflow for Y", "we're starting a new automation project", "I need to define requirements for Z", "kick off a delivery", or "let's start with requirements". This is the entry point for the spec-driven delivery lifecycle. It picks from 23 built-in use case specs or starts from scratch, refines requirements with the engineer, and produces an approved customer-spec.md. Use it whenever someone is at the beginning of building something new and hasn't yet defined what they're building. For ad-hoc platform exploration, use /explore instead. Hands off to /solution-arch-agent after approval.
---

# Spec Agent

**Stage:** Requirements
**Owns:** Defining what needs to be built. Producing the approved HLD.
**Hands off to:** `/solution-arch-agent`

---

## Customization

Before using this skill, check `custom/org/`, `custom/team/` and `custom/dev/`
in this skill's own folder. Read every `.md` file found — any folder may be
empty or absent. Apply them on top of everything below; where a file overrides a
specific rule here, follow the override. More specific wins: dev > team > org >
this document. No customization may weaken this skill's safety
rules or put credentials in committed files.

**Bundled files:** paths in this skill that start with `assets/` or `scripts/` are
relative to this skill's own folder. When you read one, or pass one to a shell
command (which runs from the user's working folder), use this skill's folder +
that relative path — e.g. `<this skill's folder>/assets/helpers/create/create-workflow.json`.
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

Present available specs from `assets/spec-files/`, grouped by category:

| Category | Specs |
|----------|-------|
| **Networking** | Port Turn-Up, VLAN Provisioning, Circuit Provisioning, BGP Peer, VPN Tunnel, WAN Bandwidth |
| **Operations** | Software Upgrade, Config Backup, Health Check, Device Onboarding, Device Decommissioning, Change Management, Incident Remediation, Gateway4 → Gateway5 Migration |
| **Security** | Firewall Rules, Cloud Security Groups, SSL Certificates |
| **Infrastructure** | DNS Records, IPAM Lifecycle, Load Balancer VIP, Config Drift Remediation, Compliance Audit |

Or the engineer describes what they need and you recommend a spec.

**Gateway4 → Gateway5 migration:** fork `spec-gateway4-to-gateway5-migration.md`. If the engineer has a
readiness report from `/gateway4-to-gateway5` (`gateway4-to-gateway5-readiness.md` and its
`tmp/analysis.json`), fill Section 5 (Scope) and the discovery answers from it — the workflows, forms,
scripts, playbooks and devices it lists — instead of asking for them. No report yet? Ask the engineer to
run `/gateway4-to-gateway5` first; it's read-only.

---

## Step 2: Fork the Spec

`{use-case}` is `use-cases/<use-case-name>/` inside the folder the engineer is working in — every later skill uses this same path.

```bash
mkdir -p {use-case}
# Only fork if it doesn't already exist — engineer may have customized from a previous session
[ ! -f {use-case}/customer-spec.md ] && cp assets/spec-files/spec-port-turn-up.md {use-case}/customer-spec.md
```

If `{use-case}/customer-spec.md` already exists, **reuse it** — do not overwrite.

If the engineer provided credentials or a `.env` file exists in the working folder, save it to `{use-case}/.env` for later use during Feasibility. Do NOT authenticate yet.

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

> "Requirements are locked. Next: Feasibility → Design → Build → Test → As-Built — full detail on each stage is in `assets/AGENTS.md`'s Developer Flow. You approve at Feasibility, Design, and the Test Plan; nothing gets built or tested live without your sign-off."

**Artifact-based handoff.** The workspace the Solution Architecture Agent receives:

```
{use-case}/
  customer-spec.md     ← approved HLD (Requirements complete)
  .env                 ← credentials (if provided)
  customer-context.md  ← business rules, naming (if provided)
  use-case-memory.md   ← create from assets/helpers/use-case-memory.md, set Stage: feasibility, Status: active
```

Create `use-case-memory.md` at handoff — populate the use-case name, one-sentence description, and `Stage: feasibility` / `Status: active`. The solution-arch-agent will add platform refs and adapter details during feasibility, and update `Stage` again at its own handoff; the builder will add asset IDs and decisions during build.

No auth. No platform data. `/solution-arch-agent` owns everything from Feasibility onward.

---

## Files Created

| File | Purpose |
|------|---------|
| `customer-spec.md` | Approved HLD — the source of truth for this delivery |
| `.env` | Credentials saved for later auth during Feasibility |
| `customer-context.md` | Business rules and naming conventions (if provided) |
| `use-case-memory.md` | Living context file — initialized here, updated throughout all stages |
