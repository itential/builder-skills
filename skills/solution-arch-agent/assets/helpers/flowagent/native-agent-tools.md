# Native Itential agent tools

Use this reference when designing, building, inspecting, or testing a FlowAI
parent that delegates to a saved child agent. Native delegation uses the Tools
Service and Agent Session Manager; it does not require a workflow wrapper.

## Three different meanings of agent-to-agent

| Mechanism | Identity and execution |
|---|---|
| Native Itential child-agent tool | A saved Itential agent exposed as `agent:<child-agent-id>`, attached to a parent's `tools`, with its own platform session and history |
| Coding-harness subagent | A Claude Code, Codex, Copilot, or Cursor assistant working on a coding task; its availability says nothing about Itential runtime capabilities |
| External A2A protocol | A separate interoperability protocol; a native `agent:` binding is not evidence of an external A2A endpoint or protocol support |

## Discover capability before choosing orchestration

1. Read the deployment's fresh `openapi.json`. Confirm the Tools Service,
   Agent Project Service, and Agent Session Manager operations below, including
   request wrappers, query parameters, and response shapes. An unrestricted
   `referenceId` string or an untyped response schema alone proves neither
   support nor absence.
2. Locate the existing child through
   `GET /agent-project-service/agent-names/operable` and read
   `GET /agent-project-service/operable-agents/{agentId}` (or the editable
   definition at `GET /agent-project-service/agents/{agentId}` when permitted).
   Inspect the returned wrapper first; the inspected deployment returned
   `{data, message}`. Keep the child's own instructions, provider, tools,
   input contract, and responsibility separate from the parent.
3. Search `GET /tools?type=agent&limit=100&skip=0`, paging to completion.
   The inspected response is `{data: [...], total, skip, limit}`. Do not use
   `excludeToolChildren=true`: individual agents can be children of an
   `agentProject` registry entry. Read the chosen
   `GET /tools/{referenceId}` with the whole reference ID URL-encoded once.
   Verify `type: agent`, `active: true`, the exact returned `referenceId`,
   and `inputSchema`. Do not register a fabricated tool or resolve by display
   name alone.
4. If a newly saved child is not registered, `POST /tools/discover` is the
   registry refresh operation. It **writes registry state**; use it only within
   authorized build/refresh scope, never as a read-only probe. Then repeat the
   paginated lookup. The UI also exposes agents under Agent Project tools.
5. If unresolved: record HTTP status, query encoding, pagination, tool activity,
   application availability, and caller access. Try the documented operable
   endpoint when an editable definition is denied. A 403 on one agent is not
   proof that native delegation is unsupported; do not grant yourself access.
   If native support is unavailable or still unverified, explicitly report that
   limitation for this deployment. Offer a design using workflow `run-agent`
   tasks and termination callbacks **if those tasks are verified and that
   design is acceptable**, or leave the dependency blocked for the owner/admin.
   Do not silently substitute runCode, a shell wrapper, or a workflow for a
   requested native-agent design.

## Attach an existing child and supply its input

The saved child becomes callable through its discovered tool entry. There is
no extra `delegateTo`/`subAgents` field and no need to attach the generic
AgentSessionManager `runAgent` application method.

On **parent creation**, include this in the normal, unwrapped agent-create body
for `POST /agent-project-service/projects/{projId}/agents`:

```json
{"tools": [{"referenceId": "agent:<child-agent-id>"}]}
```

On an **existing parent**, use the update delta at
`PATCH /agent-project-service/agents/{parent-agent-id}`:

```json
{"addTools": [{"referenceId": "agent:<child-agent-id>"}]}
```

Read back the parent and verify the binding. Re-resolve IDs after import or
cloning; automatic remapping of intra-bundle agent references was not verified.
For a new pair, save the child first, discover its actual reference, then attach
it to the parent. Do not import a bundle containing guessed child IDs.

The inspected child declared `inputSchema.properties.context.type: string`.
Its native tool exposed that same schema (plus `$schema`), directly:

```json
{"context": "Summarize this supplied observation: the scheduled check completed."}
```

That is the **tool-call argument object**, not `{"inputs": {...}}` and not an
object in place of the string `context`. Other children can declare different
fields; use their live schema, including any attached decorator. Conversely,
starting the parent through `POST /agent-session-manager/sessions` does use
`{"agentDefinitionId": "<parent-agent-id>", "inputs": {...}}`.

`native-agent-example.json` in this same directory supplies separate child and
parent create bodies, an update delta, parent session input, and child tool
arguments. Extract only the relevant body; the file itself is not an import
payload. Replace placeholders using discovery. The child summarizes supplied
text with no tools; the parent delegates and reports the outcome. This keeps
responsibilities independent without device access or notifications. The
example is schema-validated, not a claim that this example pair was executed.

## Results and evidence: three separate success checks

An existing parent history returned this **tool result shape**:

```json
{
  "sessionId": "<actual-child-session-id-returned-by-platform>",
  "sessionStatus": "COMPLETE",
  "lastMessage": "<child's actual final response text>"
}
```

The containing `tool-execution` message had `data.toolType: agent` and
`data.status: succeeded`. These names come from read-only platform evidence;
the OpenAPI tool response is untyped. Inspect the live response before relying
on these paths in another version. `lastMessage` is text, not a guaranteed
structured JSON `result` field. Parse only when the child's contract calls for
JSON, and handle malformed or missing content as unresolved.

1. **Transport/tool outcome:** inspect the parent's tool event's `status`,
   `errorMessage`, and `errorCategory`. A returned session ID is a correlation
   reference, never proof of success. Preserve it exactly; never invent one or
   reuse a prior run's ID.
2. **Child session outcome:** follow `output.sessionId` to
   `GET /agent-session-manager/sessions/{sessionId}`. Check `status`, errors,
   `agentDefinitionId`, `inputs`, and the frozen `agentSnapshot`. Reconcile
   these with the intended child and actual parent call, not the current edited
   definition. `FAILED`/`CANCELED` means failure; nonterminal states mean pending.
   Missing, inaccessible, mismatched, or contradictory evidence is unresolved,
   not success. Do not require `sessionType: child` as the only link: the schema
   permits it, but the inspected child omitted it and used `trigger.type: session`.
3. **Task outcome:** inspect `lastMessage` and the child's own tool results and
   concluding messages against the requested responsibility. A real inspected
   child was `COMPLETE` while its response reported **STOPPED** because required
   evidence was unavailable. That is a task halt, even with outer `succeeded`.
   Preserve failures/refusals and escalate; do not continue a dependent action,
   manufacture a successful result, or automatically retry a side effect.

For **both** parent and returned child session IDs, read:

```text
GET /agent-session-manager/sessions/{sessionId}
GET /agent-session-manager/sessions/{sessionId}/messages?page=1&limit=100&sortBy=timestamp&sortOrder=asc
GET /agent-session-manager/sessions/{sessionId}/messages/{eventId}
```

Page through the entire history. The inspected message list is an array; keep
requesting pages until an empty page, not merely fewer rows than requested.
The inspected service returned 48 normalized rows and then another 6 despite
`limit=100`, so stopping at that first short page would miss a child outcome.
Check `isInputTruncated`/`isOutputTruncated`; use the single-event endpoint for
full evidence. For an output, follow the tool row's `outcomeEventId` when
present, not just the start `eventId`. The raw event can use
`data.toolOutput` with a resolved payload instead of the list's `data.output`;
inspect its shape and match session/tool-call identity before interpreting it.
Record parent session, child session, tool-call/event IDs, supplied inputs,
terminal status, and task result in the engagement memory/test report.

A pending child `view` tool may be waiting for a real human while session status
remains `RUNNING`. Inspect WorkCenter items for the relevant session using the
FlowAgent skill's Work Items guidance. Neither the parent nor the builder/QA
assistant should manufacture approval or complete a human work item merely to
finish a test. Bound polling and report pending approval honestly.

## Availability and evidence limits

- Itential's [Cloud July 2026 announcement](https://docs.itential.com/itential-cloud/release-notes/feature-announcements/july-2026)
  and [Platform 6.5 announcement](https://docs.itential.com/itential-platform/release-notes/feature-announcements/650)
  list other agents among FlowAI tools. This is not a compatibility promise for
  older versions or every deployment.
- [On-prem Agent Builder](https://docs.itential.com/itential-platform/6/flowai/agent-projects/agent-builder)
  is marked Platform 6.5+. Its [quickstart](https://docs.itential.com/itential-platform/6/flowai/quickstart)
  requires a FlowAI subscription, Gateway 5.5 and Gateway Manager 1.1.1 or later,
  enabled model profiles, and FlowAI roles. Treat these as documented FlowAI
  prerequisites, not a separately measured minimum version for `agent:` tools.
- [Cloud Agent Builder](https://docs.itential.com/itential-cloud/flowai/agent-projects/agent-builder)
  requires application access plus project permissions; tool visibility also
  depends on subscription/application availability and run access to the child.
  Editing a parent requires Editor access; agent run access can be granted
  separately. Permission names differ between Cloud and on-prem. Consult the
  deployment's authorization schemas; do not widen permissions automatically.
- On 2026-10-14, read-only GETs confirmed fresh schemas, an active `agent:` tool
  with `parentType: agentProject`, matching child input schema, three native
  child bindings on an existing parent, and existing parent/child histories.
  An editable child GET returned 403 while its operable GET returned 200.
  The exact deployment build was not established; OpenAPI `info.version: 1.0.0`
  is the API document version, not the platform release. No agent was started,
  tool executed, registry refreshed, permission changed, or approval completed.
