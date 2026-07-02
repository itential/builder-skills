---
name: flowagent-to-spec
description: Convert a FlowAgent into a deterministic workflow spec. Reads the agent definition, tools, and session history (Agent Project Service / Agent Session Manager APIs) to understand what the agent does, then produces a customer-spec.md that describes the same use case as structured, deterministic automation. Turns agentic → deterministic.
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

**Note on the typed `inputSchema`:** an agent's `inputSchema` already declares its input contract as typed fields. This makes Step 3's "identify inputs" analysis mostly a lookup, not an inference — read the agent's `inputSchema` directly rather than reverse-engineering input variance across session objectives.

---

## Step 1: Read the Agent

Pull the agent definition:

```
GET /agent-project-service/agents/{agentId}
```

Or find it by name (no direct name-search endpoint — filter client-side):
```
GET /agent-project-service/agent-names/accessible
```

Extract:
- **`instructions`** — the system prompt; tells you the agent's purpose and constraints
- **`inputSchema`** — the declared, typed input contract (properties + required) — this is your starting point for the deterministic workflow's `inputSchema`, not something you need to infer from session history
- **`tools`** — array of `{referenceId, decoratorId?}` the agent can use. Resolve each `referenceId` via `GET /tools/{referenceId}` to get its name/description; if a `decoratorId` is present, fetch `GET /tools/decorators/{decoratorId}` too — the decorator's `toolInputSchema` is what the agent actually sends, not the tool's native schema
- **`provider`** — `{profile, model}` UUIDs (not needed for the spec, but useful context on which LLM ran it)
- **`operators`** — who could invoke this agent (informational, not usually spec-relevant)

The agent definition doesn't declare what platform identity its tool calls run as — if you need to know what permissions the agent's tool calls actually exercised, infer it from which adapters/apps the tools in `tools[]` touch.

Save to `{use-case}/agent-config.json`.

---

## Step 2: Read Session History

Pull completed sessions to understand what the agent actually did:

```
GET /agent-session-manager/sessions?filters=[{"field":"agentDefinitionId","value":"<agentId>"}]&sortBy=startedAt&sortOrder=desc&limit=20
```

For the most recent successful sessions for this agent:
```
GET /agent-session-manager/sessions/{sessionId}
```

From each session extract:
- **`inputs`** — what the session was started with (the typed inputs, matching the agent's `inputSchema` — no need to reverse-engineer these from free text)
- **`status`** — `COMPLETE` vs `FAILED` vs `CANCELED`; `errorMessage`/`errorCategory` on failure
- **`totalToolCallCount`** / **`iterationCount`** — how much work it did
- **`startedAt`** / **`endTime`** / **`duration`** — how long it took

Then read the session's activity log to see the actual tool call sequence:
```
GET /agent-session-manager/sessions/{sessionId}/messages?sortBy=timestamp&sortOrder=asc
```

Messages contain the full execution trace, now with a formal type taxonomy:
- `category: AGENT_REASONING` (`type: inference-succeeded`/`inference-failed`) — the LLM's reasoning and decisions (`text` field)
- `category: TOOL_CALLED` (`type: tool-execution`) — which tool, with what inputs/outputs (`data` field — fetch `GET .../messages/{eventId}` for the untruncated payload)
- `category: AGENT_STATUS` — lifecycle transitions (paused/resumed/completed/failed/canceled)

Save representative sessions to `{use-case}/session-samples.json`.

---

## Step 3: Analyze the Pattern

From the agent config and session messages, reconstruct the deterministic pattern.

### Identify the fixed sequence

Look across multiple sessions for the tool call pattern that repeats. The LLM may phrase its reasoning differently each time, but the underlying tool sequence is usually consistent:

```
Example from session messages (category: TOOL_CALLED):
  1. ServiceNow//getChangeRequest   (input: changeId)
  2. Infoblox//getHostRecord        (input: hostname)
  3. Infoblox//updateHostRecord     (input: hostname, ipv4addr)
  4. ServiceNow//updateChangeRequest (input: changeId, work_notes)
```
(Tool names here are shown resolved from `referenceId` via `GET /tools/{referenceId}` — the raw session message will reference the structured `referenceId`/`toolId` string (`<type>:<source>:<method>`, e.g. `adapter:Servicenow:ServiceNow:createChangeRequest`), not a plain readable name. Resolve every distinct tool call in the sequence before presenting it.)

This becomes your deterministic workflow task sequence.

### Identify the decision points

Where did the LLM branch? Look for:
- Sessions where different tools were called based on a condition
- `AGENT_REASONING` messages that say "since X is Y, I will call Z instead of W"
- Tool results that caused the agent to take a different path

Each branch point becomes an `evaluation` task in the deterministic workflow.

### Identify the data flow

For each tool call in the sequence:
- What inputs did it take? → these are incoming variables
- What outputs did it return? → these are outgoing variables that feed the next step
- Did the LLM extract a specific field? → that's a `query` task

### Identify error handling

Where did sessions fail (`status: FAILED`), and what did the agent do?
- Did it retry? → add retry logic or `revert` transitions
- Did it stop and report (`errorMessage`/`errorCategory`)? → add error transitions to `workflow_end`
- Did it create a ticket? → add a ServiceNow error-handling task

### Identify inputs and outputs

**Inputs:** Read the agent's `inputSchema` directly (Step 1) — agents already declare a typed input contract, so this is a lookup, not an inference. Cross-check against the `inputs` actually supplied across several sessions (Step 2) to confirm which declared properties are used in practice vs. rarely populated.

**Outputs:** What did the final `AGENT_REASONING` message (the session's concluding text) consistently report? These become the workflow `outputSchema`.

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
# Use Case: {Derived from agent instructions and inputSchema}

> **Note:** This spec was derived from FlowAgent `{agentName}` ({agentId}).
> It describes the same use case as deterministic automation — no LLM in the execution path.
> Review the inferred phases and acceptance criteria before using as a delivery baseline.

## 1. Problem Statement
{Derived from agent system prompt — what problem was the agent solving?}

## 2. High-Level Flow
{Derived from the dominant tool call sequence across sessions}

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

**In scope (observed in sessions):**
{tools used, systems touched}

**Not in scope:**
{things the agent could theoretically do with its tools but didn't}

## 6. Risks & Mitigations
{Derived from session failures (status: FAILED) and error patterns}

## 7. Requirements

### Capabilities
| Capability | Required | Source |
|-----------|----------|--------|
| {e.g., Update DNS records} | Yes | Observed in all sessions |

### Integrations
| System | Purpose | Adapter Used |
|--------|---------|-------------|
| {e.g., ServiceNow} | Change tickets | Servicenow |

### Inputs (from agent's inputSchema)
| Variable | Type | Description |
|----------|------|-------------|
| {e.g., changeId} | string | ServiceNow change request ID |

## 8. Batch Strategy
{Did the agent loop over multiple items? If so, describe the pattern}

## 9. Acceptance Criteria
{Derived from session concluding messages and final tool states}
1. {e.g., DNS record updated and verified}
2. {e.g., Change ticket updated with work notes}
3. {e.g., Workflow completes within N seconds}
```

---

## Step 6: Present to Engineer

Show the spec with clear attribution — what was observed vs what was inferred:

**Observed (high confidence):**
- Tool call sequence that appeared in >80% of sessions
- The agent's declared `inputSchema` (already typed — not inferred)
- Output values the agent always reported in its final message

**Inferred (needs verification):**
- Business purpose (from `instructions` interpretation)
- Phase boundaries (grouping of tool calls)
- Error handling intent (from failed sessions)
- Acceptance criteria (from concluding-message patterns)

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

**LLM verbosity ≠ complexity:** The agent may write long reasoning messages but the actual tool sequence is short. Focus on `TOOL_CALLED` messages, not the LLM's narrative (`AGENT_REASONING`).

**One-off sessions aren't reliable:** Look for the pattern across 5+ sessions. A single session may show unusual branching.

**Tool identity is a colon-separated `<type>:<source>:<method>` string.** E.g. `adapter:Servicenow:ServiceNow:createChangeRequest` (adapter instance + app type + method) or `application:ConfigurationManager:runCompliancePlan` (app + method). Resolve each `referenceId` via `GET /tools/{referenceId}` to confirm its exact name/description, and map the `<source>` segment(s) back to `app` (apps.json) and `adapter_id` (adapters.json) for the deterministic workflow.

**Decorators change what the agent actually sent.** If a tool reference has a `decoratorId`, the decorator's `toolInputSchema` — not the tool's native schema — is what the LLM populated. Fetch `GET /tools/decorators/{decoratorId}` to see the real, narrowed input contract the agent was working with.

**LLM error recovery:** The agent may retry tools on failure — that's agentic behavior that doesn't directly translate. In the deterministic version, use explicit error transitions and define the recovery path.

**Stateful reasoning:** If an `AGENT_REASONING` message said "I checked earlier and the device was reachable" — that's stateful context the LLM maintained. In the deterministic version, that check must be an explicit task that stores its result in a job variable.

**Sub-agents / delegation is not a supported field.** There's no way for an agent to call another agent by name in the Agent Project Service schemas. If session messages show what looks like delegation (a `sessionType: child` session, or tool calls that look like they're invoking another agent), treat each as its own candidate deterministic workflow and confirm with the engineer how the two were actually being orchestrated — don't assume a direct agent-to-agent call pattern exists.
