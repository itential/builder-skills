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

## Customization

Before using this skill, check `custom/org/`, `custom/team/` and `custom/dev/`
in this skill's own folder. Read every `.md` file found — any folder may be
empty or absent. Apply them on top of everything below; where a file overrides a
specific rule here, follow the override. More specific wins: dev > team > org >
this document. No customization may weaken this skill's safety
rules or put credentials in committed files.
---

## The Core Idea

A FlowAgent's sessions provide evidence of a use case's behavior, including failures and halts. This skill applies when the engineer wants a deterministic equivalent: remove the LLM from the execution path and specify a workflow implementing the verified behavior. Native agents can also be production designs; conversion is a user choice, not a workaround for an assumed lack of delegation.

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

The agent definition alone does not establish the runtime identity or effective permissions of its tool calls. Record observed calls and verify authorization separately; an accessible parent does not prove access to every child's definition or history.

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
GET /agent-session-manager/sessions/{sessionId}/messages?limit=100&sortBy=timestamp&sortOrder=asc
```
This returns a bare JSON array, and small page sizes can return short, empty or out-of-order pages. Use `limit=100`, de-duplicate by `eventId`, and sort by `timestamp` yourself (see `/flowagent`).

Messages contain the full execution trace, now with a formal type taxonomy:
- `category: AGENT_REASONING` (`type: inference-succeeded`/`inference-failed`) — the LLM's reasoning and decisions (`text` field)
- `category: TOOL_CALLED` (`type: tool-execution`) — which tool, with what inputs/outputs (`data` field — fetch `GET .../messages/{eventId}` for the untruncated payload)
- `category: AGENT_STATUS` — lifecycle transitions (paused/resumed/completed/failed/canceled)

Save representative sessions to `{use-case}/session-samples.json`.

For a native `agent:` tool call, follow the actual returned `data.output.sessionId`
and inspect that child's definition, inputs, metadata, and full message history.
Read `assets/helpers/flowagent/native-agent-tools.md` (relative to this skill's
folder) for discovery, correlation, truncation, and failure handling; the minimal
bodies are in `assets/helpers/flowagent/native-agent-example.json`. Preserve
independent child responsibilities and human approvals in the derived spec.
Outer tool `succeeded`, a returned session ID, or child `COMPLETE` does not prove
the requested task succeeded; a child can complete while reporting a halt.

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
(The labels above are illustrative, not tool IDs. Resolve bindings with `GET /tools/{referenceId}`; reference structure varies by type, including `agent:<child-agent-id>`. Session messages can contain `toolName` and `toolType` rather than a reference ID. Correlate with bindings, the returned child session, and its snapshot instead of inventing a reference from the name.)

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
| Adapter/app tool call | Verified native task for that adapter/app |
| Native `agent:` child call | Inspect the child's real session; specify an independent child workflow and explicit result/error mapping when deterministic conversion is requested |
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

**Tool identity has a type-specific structure.** E.g. `adapter:Servicenow:ServiceNow:createChangeRequest`, `application:ConfigurationManager:runCompliancePlan`, or `agent:<child-agent-id>`. Resolve each `referenceId` through Tools Service. Map adapter/app calls to verified task names and schemas; native child calls require reading the child's behavior, not inventing an adapter mapping.

**Decorators change what the agent actually sent.** If a tool reference has a `decoratorId`, the decorator's `toolInputSchema` — not the tool's native schema — is what the LLM populated. Fetch `GET /tools/decorators/{decoratorId}` to see the real, narrowed input contract the agent was working with.

**LLM error recovery:** The agent may retry tools on failure — that's agentic behavior that doesn't directly translate. In the deterministic version, use explicit error transitions and define the recovery path.

**Stateful reasoning:** If an `AGENT_REASONING` message said "I checked earlier and the device was reachable" — that's stateful context the LLM maintained. In the deterministic version, that check must be an explicit task that stores its result in a job variable.

**Native delegation is represented by tool bindings.** `agent:<child-agent-id>` on a parent is a native child-agent tool where available, not a coding-harness subagent or proof of external A2A protocol support. Follow actual session references recursively, tracking visited session IDs to avoid repeated traversal. If a child/history is inaccessible or a capability is unverified, record the missing evidence and the deployment-specific discovery/fallback path; do not replace it with an unsupported-delegation claim.
