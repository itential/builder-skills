---
name: flowagent-to-spec
description: Convert a FlowAgent into a deterministic workflow spec. Reads the agent config, tools, and mission history to understand what the agent does, then produces a customer-spec.md that describes the same use case as structured, deterministic automation. Turns agentic → deterministic.
argument-hint: "[agent-name or agent-id]"
---

# FlowAgent to Spec

**Purpose:** Read a FlowAgent → produce a deterministic workflow spec
**Output:** `customer-spec.md` describing the same use case as deterministic automation
**Feeds into:** `/spec-agent` for refinement → `/solution-arch-agent` → `/builder-agent`

---

## The Core Idea

A FlowAgent proves a use case works. The LLM figured out which tools to call in what order to accomplish an objective. Now you want to productionize it — remove the LLM from the execution path and replace it with a deterministic workflow that does the same thing reliably every time.

```
FlowAgent (agentic)          →    Deterministic Workflow
─────────────────────              ────────────────────────
LLM decides what to call           Explicit task sequence
LLM interprets results             query/evaluation tasks
LLM handles errors                 error transitions
LLM formats output                 merge/makeData tasks
Non-deterministic                  Same result every run
```

The spec produced by this skill describes the deterministic equivalent — same outcome, no LLM in the loop.

---

## Step 1: Read the Agent

Pull the agent configuration:

```
GET /flowai/agents/{agentId}
```

Or find by name:
```
GET /flowai/agents
```

Extract:
- **`details.messages`** — the system prompt (tells you the agent's purpose and constraints) and user message template (tells you what objective it's given)
- **`details.capabilities.toolset`** — which tools the agent is allowed to use (in `AdapterName//methodName` format)
- **`details.llm`** — which LLM provider (not needed for the spec, but useful context)
- **`details.identity`** — which platform user the agent runs as

Save to `{use-case}/agent-config.json`.

---

## Step 2: Read Mission History

Pull completed missions to understand what the agent actually did:

```
GET /flowai/missions?limit=20
```

For the most recent successful missions for this agent:
```
GET /flowai/missions/{missionId}
```

From each mission extract:
- **`objective`** — what was the agent asked to do?
- **`conclusion`** — what did the agent report at the end?
- **`toolStats.tools`** — which tools were called and how many times
- **`startTime` / `endTime`** — how long did it take?

Then read the mission events to see the actual tool call sequence:
```
GET /flowai/missions/{missionId}/events
```

Events contain the full execution trace:
- AI messages (the LLM's reasoning and decisions)
- Tool calls (which tool, with what inputs)
- Tool results (what came back)

Save representative missions to `{use-case}/mission-samples.json`.

---

## Step 3: Analyze the Pattern

From the agent config and mission events, reconstruct the deterministic pattern.

### Identify the fixed sequence

Look across multiple missions for the tool call pattern that repeats. The LLM may phrase things differently each time, but the underlying tool sequence is usually consistent:

```
Example from mission events:
  1. ServiceNow//getChangeRequest   (input: changeId)
  2. Infoblox//getHostRecord        (input: hostname)
  3. Infoblox//updateHostRecord     (input: hostname, ipv4addr)
  4. ServiceNow//updateChangeRequest (input: changeId, work_notes)
```

This becomes your deterministic workflow task sequence.

### Identify the decision points

Where did the LLM branch? Look for:
- Missions where different tools were called based on a condition
- AI messages that say "since X is Y, I will call Z instead of W"
- Tool results that caused the agent to take a different path

Each branch point becomes an `evaluation` task in the deterministic workflow.

### Identify the data flow

For each tool call in the sequence:
- What inputs did it take? → these are incoming variables
- What outputs did it return? → these are outgoing variables that feed the next step
- Did the LLM extract a specific field? → that's a `query` task

### Identify error handling

Where did missions fail, and what did the agent do?
- Did it retry? → add retry logic or `revert` transitions
- Did it stop and report? → add error transitions to `workflow_end`
- Did it create a ticket? → add a ServiceNow error-handling task

### Identify inputs and outputs

**Inputs:** What did the objective vary across missions? These become the workflow `inputSchema`.

**Outputs:** What did the conclusion always contain? These become the workflow `outputSchema`.

---

## Step 4: Map Agentic → Deterministic

Convert each observed agent behavior to a workflow construct:

| Agent behavior | Deterministic equivalent |
|----------------|--------------------------|
| Tool call | Adapter task |
| LLM extracts a field from tool result | `query` task |
| LLM decides which path to take | `evaluation` task |
| LLM builds a request body | `merge` task |
| LLM formats output | `makeData` or `renderJinjaTemplate` |
| LLM asks for approval | `ViewData` manual task |
| LLM calls multiple tools for each item in a list | `childJob` with `loopType: parallel` |
| LLM retries a failed call | `revert` transition |
| Agent conclusion | workflow `outputSchema` variables |

---

## Step 5: Produce `customer-spec.md`

Write the spec for the deterministic equivalent.

```markdown
# Use Case: {Derived from agent system prompt and mission objectives}

> **Note:** This spec was derived from FlowAgent `{agentName}` ({agentId}).
> It describes the same use case as deterministic automation — no LLM in the execution path.
> Review the inferred phases and acceptance criteria before using as a delivery baseline.

## 1. Problem Statement
{Derived from agent system prompt — what problem was the agent solving?}

## 2. High-Level Flow
{Derived from the dominant tool call sequence across missions}

## 3. Phases
{One phase per logical cluster of tool calls}

### Phase N: {Name}
{What happens, what tools are called, what conditions are checked}
Decision points: {list evaluation conditions observed}
Stop conditions: {when does this phase fail/stop?}

## 4. Key Design Decisions
{What choices did the agent consistently make? These become explicit design decisions}

Example:
- Always verified the change ticket existed before updating it
- Skipped DNS update if the IP hadn't changed
- Created a follow-up ticket if the primary action failed

## 5. Scope

**In scope (observed in missions):**
{tools used, systems touched}

**Not in scope:**
{things the agent could theoretically do with its tools but didn't}

## 6. Risks & Mitigations
{Derived from mission failures and error patterns}

## 7. Requirements

### Capabilities
| Capability | Required | Source |
|-----------|----------|--------|
| {e.g., Update DNS records} | Yes | Observed in all missions |

### Integrations
| System | Purpose | Adapter Used |
|--------|---------|-------------|
| {e.g., ServiceNow} | Change tickets | Servicenow |

### Inputs (from mission objectives)
| Variable | Type | Description |
|----------|------|-------------|
| {e.g., changeId} | string | ServiceNow change request ID |

## 8. Batch Strategy
{Did the agent loop over multiple items? If so, describe the pattern}

## 9. Acceptance Criteria
{Derived from mission conclusions and final tool states}
1. {e.g., DNS record updated and verified}
2. {e.g., Change ticket updated with work notes}
3. {e.g., Workflow completes within N seconds}
```

---

## Step 6: Present to Engineer

Show the spec with clear attribution — what was observed vs what was inferred:

**Observed (high confidence):**
- Tool call sequence that appeared in >80% of missions
- Input variables that varied across missions
- Output values the agent always reported in its conclusion

**Inferred (needs verification):**
- Business purpose (from system prompt interpretation)
- Phase boundaries (grouping of tool calls)
- Error handling intent (from failure missions)
- Acceptance criteria (from conclusion patterns)

Ask the engineer:
1. "Does this correctly capture what the agent was doing?"
2. "Are there edge cases the agent handled that I should capture as phases?"
3. "The agent made these decisions dynamically — should the deterministic version always follow the dominant path, or do we need all branches?"
4. "What inputs should the workflow accept?"

Then offer next steps:
- **Refine and deliver** → hand to `/spec-agent` for requirements refinement → `/solution-arch-agent` → `/builder-agent`
- **Accept as-is** → hand directly to `/solution-arch-agent` with the approved spec

---

## Gotchas

**LLM verbosity ≠ complexity:** The agent may write long conclusions but the actual tool sequence is short. Focus on tool calls, not the LLM's narrative.

**One-off missions aren't reliable:** Look for the pattern across 5+ missions. A single mission may show unusual branching.

**Tool name → adapter mapping:** Agent tools use `AdapterName//methodName` format. Map back to `app` (from apps.json) and `adapter_id` (from adapters.json) for the workflow.

**LLM error recovery:** The agent may retry tools on failure — that's agentic behavior that doesn't directly translate. In the deterministic version, use explicit error transitions and define the recovery path.

**Stateful reasoning:** If the agent said "I checked earlier and the device was reachable" — that's stateful context the LLM maintained. In the deterministic version, that check must be an explicit task that stores its result in a job variable.

**Sub-agents:** If the agent called sub-agents, each sub-agent becomes a candidate child workflow. Recurse — pull each sub-agent's missions and apply the same analysis.
