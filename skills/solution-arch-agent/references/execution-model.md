# Designing the Execution Model

Use this in Design to decide, with the engineer, where LCM, FlowAgent and Gateway5
come into a delivery alongside deterministic workflows. How to build each one is in
`/itential-lcm`, `/flowagent` and `/iag` — this covers when to use them.

Work in this order:

1. **Start from what the platform has** — the Execution Capabilities section of
   `feasibility.md` (`platform-summary.json` → `execution_capabilities`). Don't
   offer a model the platform can't run. Treat an existing resource model, agent or
   service as the first candidate, and reuse it only after checking that it fits.
2. **Ask what the spec and the inventory leave open** — pick from the questions
   below. Never ask the whole list.
3. **Propose a model for each phase**, state the answer or inventory fact behind
   it, and confirm it with the engineer in design review.

Default to a deterministic workflow. Use LCM, FlowAgent or Gateway5 only for a
specific reason in this use case, and state that reason.

---

## LCM

### What LCM gives the customer

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
under management, an IP block, a firewall rule.

Don't use LCM when the deliverable is a **task** — a backup, a compliance run, a
report. The task can still become an action on another resource model.

A noun alone isn't enough. Treat an incident or request that is opened and closed
within one run as a task — the ITSM ticket already records it — unless the customer
wants it tracked and acted on across several runs.

### Before proposing LCM, check the inventory

- **A resource model for the same thing exists** → read it
  (`GET /lifecycle-manager/resources/{id}`). If its schema fits this spec's object
  and its owners agree, add a new action to it instead of creating a model. If its
  schema was built for another use case, its actions have no workflows, or another
  team owns it and hasn't agreed, create a new model. If two models overlap, ask
  the engineer which, if either.
- **Two specs cover the same thing** (turn-up and turn-down, create and modify) →
  design one model with several actions, not separate workflows.

### Questions to ask the engineer

1. **"What is the thing being delivered, and who is it delivered to?"** If there's
   no thing, stop — don't use LCM.
2. **"What happens to it after it's built?"** List every day-2 operation. Then ask:
   "When someone changes one today, where do they get the original parameters?"
   "From the old ticket" or "we look at the device" is the strongest reason to use
   LCM.
3. **"When it's removed, do you know exactly what was configured for it?"** If not,
   design a delete action that removes what the instance record says was built.
4. **"Do you ever need to run something across all of them?"** If yes, add bulk
   actions and instance groups.
5. **"Do some already exist that should come under management?"** If yes, add an
   import action and a brownfield discovery step.
6. **"Which systems hold a piece of this object?"** If more than one, store each
   system's ID in the instance schema.

### What to put in the design

- The **instance schema**: the fields every action needs, including external system
  IDs. Every create action must write every `required` field (see `/itential-lcm`).
- **One action per lifecycle operation**, each backed by a deterministic workflow
  that outputs `instance`. Say which actions need pre/post transformations to map
  the instance onto the workflow's inputs.
- How each action is **triggered**: the LCM UI, a workflow
  (`LifecycleManager.runAction`), or an agent (the
  `application:LifecycleManager:runAction` tool).

---

## FlowAgent

An agent can be **how a phase gets built**, **what runs in production**, or both.
Make these two decisions separately for each phase:

| Decision | Options |
|----------|---------|
| **Delivery path** | **Agent first** — build an agent on existing tools, prove the idea, then convert it to deterministic assets with `/flowagent-to-spec`. **Direct** — build the deterministic assets from the start. |
| **Production** | The agent, a workflow, or a workflow with one `runAgent` step |

### What FlowAgent gives the customer

| FlowAgent | What it means |
|-----------|---------------|
| The platform is its toolbox — adapter methods, app tasks, Gateway5 services, workflows, LCM actions and other agents are all tools | Combines what already exists, at run time, with no new build per combination |
| Its logic is written instructions, not wired tasks | A working first version quickly; cheap to change while the idea is being proven |
| Session history of every call and why | The record of a proven procedure — `/flowagent-to-spec` turns it into a deterministic spec |
| Writes language | Summaries, root-cause write-ups, ticket text, explanations for a person |
| Stops for a person (work items) | Proposes, gets approval, then acts |

### When to build agent first, when direct, and when to keep the agent

In a workflow, the designer decides every step and branch at build time. An agent
decides its next step at run time.

- **Build direct** when the procedure is known and proven (a runbook, an existing
  asset), when the tools don't exist yet (they have to be built either way), and
  for LCM action workflows. Propose direct without asking.
- **Agent first is an option** when the tools the idea needs already exist (the
  agent is mostly instructions and a tool list), the idea isn't proven yet, or
  nobody has written the procedure down — the agent's sessions will. Don't choose
  for the engineer: ask, and give the trade-off. Agent first shows the idea working
  sooner and records the real procedure, but the phase is built twice (the agent,
  then its deterministic assets) with a conversion in between. Direct is one build,
  but the procedure has to be right on paper first.
- **Keep the agent in production** when the value comes only from run-time
  decisions: a long tail of request types, each too rare to justify its own
  workflow; an answer or explanation as the output; a path too open to list in
  advance. Route every change through a workflow tool, behind a work item wherever
  a person has to approve.

Neither path is the default.

### Before proposing an agent, check the inventory

- **An LLM profile** the engineer can build with (`/agent-project-service/profiles`).
  If there is none, FlowAgent isn't available on this platform — don't propose it.
- **Agents whose names match the job** → read their instructions and tools
  (`GET /agent-project-service/agents/{id}`). If one does part of the job, reuse it
  as a tool (parent and child agents) or extend it. If the path is direct, ask
  whether a matching agent's sessions are a proven version of the procedure and
  should be the starting point (`/flowagent-to-spec`).
- **The tools each agent would need** (`GET /tools?name=...`). List a missing tool
  as build work in the design.

### Questions to ask the engineer

1. **"Has this idea been proven, or do we need to try it first?"**
2. **"Can your best engineer write the procedure down today, step by step?"** Yes →
   direct. "It depends what I find" → an agent is a candidate. "It's in people's
   heads" → offer agent first, then convert.
3. **"Do the systems and actions it needs already exist on the platform?"** Check
   the tool registry first; ask only about what it doesn't have.
4. **"What does the requester get at the end — a changed device, or an answer?"**
5. **"How many different kinds of request are there, and how often does each come?"**
6. **"What may it change without a person approving it?"**

### What to put in the design

- For agent first, **two build stages**: (1) the agent and its test sessions;
  (2) `/flowagent-to-spec` writes `<phase>-converted-spec.md`, which comes back
  through `/solution-arch-agent design-only` and Build. The delivery's approved
  `customer-spec.md` stays as it is. Say what "proven" means (e.g., N sessions on
  real requests with the expected result) and who decides. The engineer can still
  keep the agent at that point.
- For an agent in production: its inputs, its tools, which tools write, and the
  work item in front of each write.
- For a workflow with one judgment step: the `runAgent` task, and how the workflow
  checks the agent's answer, not only its status.

---

## Gateway5

### What Gateway5 gives the customer

| Gateway5 | What it means |
|----------|---------------|
| Existing Python, Ansible and OpenTofu become services, from a git repository | The customer's automation is reused, not rewritten |
| Services live in git — versions, CI/CD, promotion between environments | The team that writes code maintains it, separately from the people who build in Studio |
| Clusters placed in each zone or site | Reaches networks the platform itself can't |
| `sendCommand` / `sendConfig` against Inventory Manager nodes | CLI and config push without an adapter or a service |
| The Python and SDK ecosystem — netmiko, NAPALM, cloud SDKs, OpenTofu state | Protocols and APIs no adapter covers |
| Services are also agent tools | One service serves workflows and agents |

### When to use a Gateway5 service

Put each piece of logic where the people who maintain it after delivery work:

- **In the workflow**, for Studio builders: a native task or adapter,
  `sendCommand`/`sendConfig`, or `runCode` to reshape data.
- **In a Gateway5 service**, for a team that writes code: when the code already
  exists, needs packages or an SDK, provisions infrastructure (OpenTofu), or is
  reused by several workflows and agents.

### Before proposing a service, check the inventory

- **Connected clusters.** Don't target a `disconnected` cluster. The platform
  doesn't record which zone a cluster serves — ask (question 2).
- **Services already registered** on those clusters → reuse one before writing a
  new one.
- **Inventory Manager inventories** and their node counts → if the devices aren't
  there, list populating them as build work (`/itential-inventory`).
- **Workflows still on Gateway4** (`gateway4_workflows`, which call `AGManager`
  tasks) → never design new work on Gateway4. If any of them are in this spec's
  scope, point to `/gateway4-to-gateway5`.

### Questions to ask the engineer

1. **"What scripts, Ansible playbooks or Terraform do you already have — where do
   they live, and who maintains them?"** A spec's "playbook" often means a runbook
   entry, not Ansible — confirm which before treating it as Gateway5 code.
2. **"Which zones or sites are the devices in? Can the platform reach them, or only
   a gateway placed there?"**
3. **"After delivery, who maintains this logic — people who write code, or people
   who build in Studio?"**
4. **"Does it provision cloud or infrastructure resources? Who keeps the state?"**
5. **"Are the devices in Inventory Manager, or in another inventory (NetBox,
   Ansible)?"**

### What to put in the design

- Each service: type (`python-script`, `ansible-playbook`, `opentofu-plan`), source
  repository, decorator (inputs), the cluster it runs on, and who maintains it.
- Which steps use `sendCommand`/`sendConfig` or `runCode` instead of a service.
- Inventory Manager work, if the devices aren't there yet.

---

## Common combinations

| Use case shape | Design |
|----------------|--------|
| A service with a lifecycle | LCM model → action workflows → adapters / Gateway5 services |
| Request intake or triage | Agent → workflows as tools for changes, read-only tools for the rest |
| A fixed change with one judgment step | Workflow → `runAgent` → workflow continues |
| Reusing the customer's automation | Workflow → Gateway5 services |
| Operating LCM services on request | Agent → `LifecycleManager.runAction` tool |
| An unproven idea | Agent first → `/flowagent-to-spec` → any of the above |

## The engineer decides

Propose; the engineer chooses. If the spec names a model ("build an agent", "use
LCM"), follow it and record any concern as a risk — don't override it.
