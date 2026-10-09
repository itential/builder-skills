# Use Case: Gateway4 → Gateway5 Migration

> **Start from the readiness report.** Run `/gateway4-to-gateway5` first. Its report
> (`gateway4-to-gateway5-readiness.md`) and `tmp/analysis.json` list exactly which workflows, JSON
> forms, scripts, playbooks and devices move — use them to fill Sections 5 and 7 instead of
> rediscovering. How each item converts: `helpers/gateway-migration/conversion-guide.md`.

## 1. Problem Statement

Itential Gateway4 is being retired. Workflows call it through the Automation Gateway adapter and the
AG Manager application; scripts, playbooks and roles are uploaded to the gateway; devices live in the
gateway's own inventory. Gateway5 works differently: services run from a git repository, scripts
take named arguments, and devices live in the platform's Inventory Manager. Moving by hand is slow
and risky — workflows are rewired one task at a time, inventories are retyped, and nothing proves
the migrated automation still does what the old one did.

**Goal:** move every in-scope Gateway4 dependency to Gateway5 with no change in behavior, prove it
item by item, and cut over without disrupting the automations already running.

---

## 2. High-Level Flow

```
Assess  →  Generate  →  Inventory  →  Services  →  Workflows  →  Parity Test  →  Cutover
   |          |            |             |            |              |              |
Readiness  Service      Gateway4      Scripts and  Rewire tasks   Same inputs    Switch
report     files,       devices to    playbooks    to Gateway5,   through old    triggers,
(read-     inventory    Inventory     to a git     as a NEW       and new,       retire
only)      nodes and    Manager,      repo;        project next   compare        Gateway4
           a review     broker        import via   to the
           list         actions       Gateway Mgr  originals
```

---

## 3. Phases

### Assess
Run `/gateway4-to-gateway5` (read-only) for the agreed scope. Its remediation codes — WRAP, REVIEW,
ARGS, INV — drive every later phase. Anything it lists as unresolved must be resolved or explicitly
excluded before design.

### Generate
Run `helpers/gateway-migration/convert_gateway4.py` against Gateway4 (read-only) or its exports. It
writes the Gateway5 service definitions with their input schemas, the service repository layout, the
Inventory Manager nodes, and a report of everything that needs a person. Resolve the report's review
items before going further.

### Inventory
Create an Inventory Manager inventory with broker actions (`createBrokerActions: true`) and move the
Gateway4 devices and groups into it, mapping their variables to broker attributes (host, user,
platform, driver, port) and groups to tags. Credentials become secret references, never plain text.
Verify each device with the `is-alive` or `run-command` broker action. If a device can't be reached
through Gateway5, **stop** — no workflow that targets it can be migrated yet.

### Services
Put the in-scope scripts and playbooks in a git repository the Gateway5 cluster can reach (the
report's recommended layout). Scripts take named arguments; playbooks target `all` with a templated
inventory. Import the service definitions through Gateway Manager (validate first). Run each service
once on its own before any workflow uses it.

### Workflows
Rebuild each in-scope workflow with its Gateway4 tasks replaced: built-in device tasks → Gateway
Manager send-command / send-config on the inventory; playbooks and scripts → `runService`; device and
group management → Inventory Manager. Re-point every task that consumed a Gateway4 output. Import the
migrated workflows as a **new project**; the originals keep running unchanged. Rebind JSON form
fields that pointed at Gateway4.

### Parity Test
Run each migrated workflow and its original with the same inputs against the same devices, and
compare the results that matter (not the raw output shape, which changes by design). Any difference
is a build defect. Read-only operations are compared directly; for changes, use a lab device or an
approved maintenance window.

### Cutover
Point triggers, automations and parent workflows at the migrated workflows. Watch a full cycle of real
runs. Then disable the Gateway4 integration, keeping it installed until rollback is no longer needed.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Migrate in place or alongside | Alongside — a new project | Originals keep running; rollback is "keep using the originals" |
| How services reach Gateway5 | Imported through Gateway Manager from a git repo | No shell access to gateways needed; the repo is the source of truth |
| Where devices live | Inventory Manager, with broker actions | Gateway5 has no inventory; broker actions replace Gateway4's built-in device tasks |
| Credentials | Secret references only | Gateway4 device variables often hold plain-text passwords |
| Proof of behavior | Parity test per workflow before cutover | "It runs" isn't evidence; matching the old result is |

---

## 5. Scope

**In scope:** the workflows, JSON forms, scripts, playbooks, roles and devices listed in the readiness
report for the agreed scope (projects, named workflows, or all). Inventory migration. Service repository
setup. Parity testing. Cutover checklist.

**Out of scope:** changing what an automation does (that's a separate delivery after migration).
Gateway5 installation and cluster registration (a platform prerequisite). Retiring Gateway4
infrastructure itself.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| A device isn't reachable through Gateway5 | Workflows targeting it can't move | Verify every device with a broker action in the Inventory phase, before building |
| Migrated output has a different shape | Downstream tasks read nothing | The report's "used by" list names every consumer; re-point each one, and the parity test catches misses |
| Credentials copied in plain text | Exposure | Secret references only; the design review checks the inventory attributes |
| A change-making automation behaves differently | Outage | Parity-test changes on a lab device or in an approved window; originals stay live until cutover |
| Gateway4 inventory lost before migration | Device list gone | Export Gateway4 devices and groups first; keep the export with the delivery |

---

## 7. Requirements

### What the automation must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Read the Gateway4 inventory, scripts and playbooks (API or files) | Yes | Engineer exports them manually |
| Gateway5 cluster registered with the platform (Gateway Manager) | Yes | Cannot proceed — platform prerequisite |
| Inventory Manager with broker actions | Yes | Cannot proceed |
| Git repository reachable from the Gateway5 cluster | Yes | Cannot proceed |
| Secret provider for device credentials | Yes | Engineer approves an interim approach in design |
| Lab device or maintenance window for change-making parity tests | Yes, if any in-scope automation makes changes | Those items stay on Gateway4 until one is available |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| Itential Gateway4 | Source of assets and the parity baseline | Yes | Migrate from exported files; no parity baseline |
| Itential Gateway5 cluster | Runs the migrated services | Yes | Cannot proceed |
| Git host (GitHub, GitLab, Bitbucket, …) | Service repository | Yes | Cannot proceed |
| Secret provider (e.g. Vault, CyberArk) | Device credentials | Yes | Interim approach approved in design |

### Discovery Questions

Ask the engineer before designing the solution:

1. Is the readiness report done, and for which scope? Are its unresolved items resolved?
2. Which Gateway5 cluster(s) take over from which Gateway4 gateway(s)?
3. Which git host and repository will hold the services? How does the cluster authenticate to it?
4. Which secret provider holds device credentials, and what are the secret paths?
5. Which in-scope automations make changes, and where can those be parity-tested?
6. Who owns cutover, and what's the rollback window before Gateway4 is disabled?
7. Are there triggers, schedules or external systems calling the in-scope workflows today?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| One workflow first | Migrate, parity-test and cut over a single read-only workflow end to end | Always first — proves the inventory, repo and service path |
| By project | Migrate a whole project per wave | Most environments |
| By remediation code | All WRAP tasks, then REVIEW, then ARGS | Many workflows sharing the same few Gateway4 tasks |

---

## 9. Acceptance Criteria

1. Every in-scope device is in Inventory Manager with broker actions, and responds to `is-alive` or `run-command` through Gateway5
2. No device credential is stored in plain text in Inventory Manager or the service repository
3. Every in-scope script and playbook runs as a Gateway5 service on its own before any workflow uses it
4. Every in-scope workflow has a migrated counterpart with no Gateway4 (Automation Gateway or AG Manager) tasks left
5. Every migrated workflow matches its original on the agreed fields in a parity test, recorded in `test-report.md`
6. JSON form fields that pointed at Gateway4 return data from their new source
7. The original workflows are unchanged until cutover
8. Cutover and rollback steps are recorded in `as-built.md`
