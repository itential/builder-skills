# Designing the Execution Model

How a solution design decides where LCM, FlowAgent and Gateway5 come into a
delivery, alongside deterministic workflows. Used by `/solution-arch-agent` in the
Design stage; the building itself is in `/itential-lcm`, `/flowagent` and `/iag`.

The order is always the same:

1. **What the platform has** — the capability inventory from feasibility
   (`platform-summary.json` → `execution_capabilities`). A model the platform can't
   run is not offered. An existing resource model, agent or service is the first
   candidate to build on — once it's checked and actually fits.
2. **What the spec doesn't say** — ask the discovery questions below that the spec
   and the inventory leave open. Ask only those; never the whole list.
3. **Where each one comes in** — propose the model per phase, citing the answer that
   drove it, and confirm it with the engineer in design review.

The deterministic workflow is the default. LCM, FlowAgent and Gateway5 each come in
because of something specific about the use case — name it.

---

## LCM — when the deliverable is a thing, not a task

### What it gives the customer

| LCM | What it means |
|-----|---------------|
| An instance record with a schema | A list of what has been delivered, in the shape the customer thinks in |
| Actions bound to the instance | Day-2 changes start from the stored data — nobody re-enters parameters or digs through the original ticket |
| Actions beyond create/update/delete | Verify, check compliance, validate, block — operations run against the record (update-type actions) |
| A correlation record | One object tied together across systems — the instance holds the NetBox, CMDB, monitoring and controller IDs; it doesn't replace those systems |
| History and state per instance | An audit trail per service; failed instances stay visible |
| Bulk actions and instance groups | One action across the fleet: verify every port, re-apply after a standard change |
| Import | Services that already exist come under management |

### When to use LCM

Use LCM when the deliverable is a **thing that outlives the run that created it and
is acted on again later** — a port service, a circuit, a VXLAN network, a device
under management, an IP block, a firewall rule. Don't use it when the deliverable is
a **task** — a backup, a compliance run, a report (the task may still become an
action on someone else's resource model).

A noun alone isn't enough. An incident or a request that is opened and closed
within one run is a task record — the ITSM ticket already holds it — unless the
customer wants it tracked and acted on across several runs.

### Discovery questions

1. **"What is the thing being delivered, and who is it delivered to?"** If there's no
   noun, stop here — no LCM.
2. **"What happens to it after it's built?"** List every day-2 operation. Then: "When
   someone changes one today, where do they get the original parameters?" — "the old
   ticket" or "we look at the device" is the strongest LCM signal.
3. **"When it's removed, do you know exactly what was configured for it?"** Orphaned
   config from partial teardowns is what a delete action built from the record fixes.
4. **"Do you ever need to run something across all of them?"** → bulk actions,
   instance groups.
5. **"Do some already exist that should come under management?"** → an import action
   and a brownfield discovery step.
6. **"Which systems hold a piece of this object?"** More than one → the instance
   becomes the correlation record; store each system's ID in the schema.

### Check the inventory first

- An **existing resource model** for the same thing → read its schema and actions
  (`GET /lifecycle-manager/resources/{id}`). If the schema fits this spec's object
  and its owners agree, the new use case is a new action on it, not a new model.
  A schema built for another use case, actions with no workflow, or a model owned
  by another team who hasn't agreed → a new model. Overlapping models → ask.
- **Two specs on the same thing** (turn-up and turn-down, create and modify) → one
  model with several actions, not separate workflows.

### What it puts in the design

- The **instance schema**: the fields every action needs, including external system
  IDs. Every create action must write every `required` field (see `/itential-lcm`).
- **One action per lifecycle operation**, each backed by a deterministic workflow
  that outputs `instance`. Say which actions need pre/post transformations to map the
  instance onto the workflow's inputs.
- How actions are **triggered**: the LCM UI, a workflow (`LifecycleManager.runAction`),
  or an agent (the `application:LifecycleManager:runAction` tool).

---

## FlowAgent — two separate decisions

An agent can be **how the delivery gets built**, **what runs in production**, or
both. Decide them separately for each phase.

| Decision | Options |
|----------|---------|
| **Delivery path** | **Agent first** — build an agent on existing tools, prove the idea, then convert it to deterministic assets with `/flowagent-to-spec`. **Direct** — build the deterministic assets from the start. |
| **Production** | The agent, a workflow, or a workflow with one `runAgent` step |

Neither path is the default. When "When to build agent first, when direct, and when
to keep the agent" below says direct, propose direct
without asking. When agent first is a real option, ask the engineer, with the
trade-off: agent first shows the idea working sooner and records the real procedure,
but the phase is built twice (the agent, then its deterministic assets) with a
conversion in between; direct is one build, but the procedure has to be right on
paper first.

### What it gives the customer

| FlowAgent | What it means |
|-----------|---------------|
| The platform is its toolbox — adapter methods, app tasks, Gateway5 services, workflows, LCM actions and other agents are all tools | Combines what already exists, at run time, with no new build per combination |
| Its logic is written instructions, not wired tasks | A working first version quickly; cheap to change while the idea is being proven |
| Session history of every call and why | The record of a proven procedure — `/flowagent-to-spec` turns it into a deterministic spec |
| Writes language | Summaries, root-cause write-ups, ticket text, explanations for a person |
| Stops for a person (work items) | Proposes, gets approval, then acts |

### When to build agent first, when direct, and when to keep the agent

The difference: in a workflow, the designer decides every step and branch at build
time; an agent decides its next step at run time.

- **Agent first** fits when the tools the idea needs already exist (the agent is
  mostly instructions and a tool list), the idea isn't proven yet, or nobody has
  written the procedure down — the agent's sessions will.
- **Direct** fits when the procedure is known and proven (a runbook, an existing
  asset), when the tools don't exist yet (they have to be built either way), and for
  LCM action workflows.
- **Keep the agent in production** when the value only comes from run-time decisions:
  a long tail of request types, each too rare to justify its own workflow; an answer
  or explanation as the output; a path too open to list in advance. Changes still go
  through workflow tools, behind a work item where a person has to approve.

### Discovery questions

1. **"Has this idea been proven, or do we need to try it first?"**
2. **"Can your best engineer write the procedure down today, step by step?"** Yes →
   direct. "It depends what I find" → agent candidate. "It's in people's heads" →
   agent first, then convert.
3. **"Do the systems and actions it needs already exist on the platform?"** Answer
   this from the tool registry (`GET /tools?name=...`) before asking; ask only about
   what it can't find.
4. **"What does the requester get at the end — a changed device, or an answer?"**
5. **"How many different kinds of request are there, and how often does each come?"**
6. **"What may it change without a person approving it?"**

### Check the inventory first

- An **LLM profile** the engineer can build with (`/agent-project-service/profiles`).
  If there is none, FlowAgent isn't available on this platform.
- **Existing agents** whose names match the job → read their instructions and tools
  (`GET /agent-project-service/agents/{id}`). One that does part of the job → reuse
  as a tool (parent and child agents), or extend. If the path is direct, a matching
  agent may still be a proven version of the procedure — ask whether its sessions
  should be the starting point (`/flowagent-to-spec`).
- The **tools** each agent would need. A missing tool is build work in the design.

### What it puts in the design

- For agent first, **two build phases**: (1) the agent and its test sessions, which
  prove the idea; (2) `/flowagent-to-spec` produces `<phase>-converted-spec.md`,
  which comes back through `/solution-arch-agent design-only` and Build — the
  delivery's approved `customer-spec.md` is left as is. Plan the conversion — say
  what "proven" means (e.g., N sessions on real requests with the expected result)
  and who decides. Keeping the agent is still an option at that point.
- For an agent in production: its tools, which of them write and the work item in
  front of each write, and its inputs.
- For a workflow with one judgment step: the `runAgent` task and how the workflow
  checks the agent's answer, not only its status.

---

## Gateway5 — where the logic lives, and who maintains it

### What it gives the customer

| Gateway5 | What it means |
|----------|---------------|
| Existing Python, Ansible and OpenTofu become services, from a git repository | The customer's automation is reused, not rewritten |
| Services live in git — versions, CI/CD, promotion between environments | The team that writes code maintains it, separately from the people who build in Studio |
| Clusters placed in each zone or site | Reaches networks the platform itself can't |
| `sendCommand` / `sendConfig` against Inventory Manager nodes | CLI and config push without an adapter or a service |
| The Python and SDK ecosystem — netmiko, NAPALM, cloud SDKs, OpenTofu state | Protocols and APIs no adapter covers |
| Services are also agent tools | One service serves workflows and agents |

### When to use a Gateway5 service

Decide where each piece of logic lives, based on who maintains it after delivery:

- **In the orchestration**, as workflow tasks maintained by Studio builders: a native
  task or adapter, `sendCommand`/`sendConfig`, `runCode` for reshaping data.
- **In code**, as a Gateway5 service maintained by a code team: the code already
  exists, it needs packages or an SDK, it provisions infrastructure (OpenTofu), or
  several workflows and agents reuse it.

### Discovery questions

1. **"What scripts, Ansible playbooks or Terraform do you already have — where do
   they live, and who maintains them?"** (A spec's "playbook" often means a runbook
   entry, not Ansible — check which before treating it as Gateway5 code.)
2. **"Which zones or sites are the devices in? Can the platform reach them, or only
   a gateway placed there?"**
3. **"After delivery, who maintains this logic — people who write code, or people
   who build in Studio?"**
4. **"Does it provision cloud or infrastructure resources? Who keeps the state?"**
5. **"Are the devices in Inventory Manager, or in another inventory (NetBox,
   Ansible)?"**

### Check the inventory first

- **Connected clusters**. A cluster that is `disconnected` isn't available. The
  platform doesn't record which zone a cluster serves — that comes from question 2.
- **Services already registered** on those clusters → reuse before writing new ones.
- **Inventory Manager inventories** and their node counts → whether devices are
  ready to target, or populating them is build work (`/itential-inventory`).
- **Workflows still on Gateway4** (`gateway4_workflows`, those calling `AGManager`
  tasks) → no new work on Gateway4; if any are in this spec's scope, point to
  `/gateway4-to-gateway5`.

### What it puts in the design

- Each service: type (`python-script`, `ansible-playbook`, `opentofu-plan`), source
  repository, decorator (inputs), the cluster it runs on, and who maintains it.
- Which steps use `sendCommand`/`sendConfig` or `runCode` instead of a service.
- Inventory Manager work, if the devices aren't there yet.

---

## How they combine

| Use case shape | Design |
|----------------|--------|
| A service with a lifecycle | LCM model → action workflows → adapters / Gateway5 services |
| Request intake or triage | Agent → workflows as tools for changes, read-only tools for the rest |
| A fixed change with one judgment step | Workflow → `runAgent` → workflow continues |
| Reusing the customer's automation | Workflow → Gateway5 services |
| Operating LCM services on request | Agent → `LifecycleManager.runAction` tool |
| An unproven idea | Agent first → `/flowagent-to-spec` → any of the above |

## Who decides

The proposal is the agent's; the choice is the engineer's. If the spec already names
a model ("build an agent", "use LCM"), follow it and record any concern as a risk
instead of overriding it.
