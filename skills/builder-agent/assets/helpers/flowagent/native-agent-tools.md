# Agents as tools (parent and child agents)

A FlowAI agent can call another saved agent as one of its tools. The parent
agent decides when to call the child, passes it the child's declared inputs,
and gets back the child's final answer. Each call starts a separate child
session with its own history.

This is FlowAI's sub-agent model: both agents run on the same platform. It is
not the external A2A protocol, and it is unrelated to the subagents of a coding
assistant.

**Availability:** Itential Platform 6.5 and later, and Itential Cloud from the
July 2026 release
([6.5 announcement](https://docs.itential.com/itential-platform/release-notes/feature-announcements/650),
[Cloud announcement](https://docs.itential.com/itential-cloud/release-notes/feature-announcements/july-2026)).
FlowAI itself needs a FlowAI subscription, Gateway 5.5, Gateway Manager 1.1.1
or later, an enabled model profile and FlowAI roles
([quickstart](https://docs.itential.com/itential-platform/6/flowai/quickstart)).

## How it works

- Every saved agent is registered as a tool with the reference ID
  `agent:<agent-id>` as soon as it is created. You don't need to run tool
  discovery.
- The tool's input schema is the child agent's `inputSchema`.
- You attach the child to a parent the same way as any other tool. There is no
  separate delegation field, and you don't need the `runAgent` application
  method.

## Build a parent and child

1. **Create the child** with `POST /agent-project-service/projects/{projId}/agents`.
   Give it its own instructions, `inputSchema` and tools.
2. **Check the child's tool:**
   `GET /tools/agent%3A<child-id>` (URL-encode the colon). Confirm
   `active: true` and read its `inputSchema`. If it is missing, run
   `POST /tools/discover` once and read it again. Discovery writes to the tool
   registry, so only run it when you are allowed to make changes. If the tool is
   still missing, the platform doesn't support agent tools; see
   [If agent tools aren't available](#if-agent-tools-arent-available).
3. **Attach the child to the parent.** When creating the parent, include:

   ```json
   {"tools": [{"referenceId": "agent:<child-id>"}]}
   ```

   For a parent that already exists, use
   `PATCH /agent-project-service/agents/{parent-id}`:

   ```json
   {"addTools": [{"referenceId": "agent:<child-id>"}]}
   ```

4. **Read the parent back** and confirm the binding is in its `tools`.
5. **Tell the parent when to use the child** in its `instructions`, and that it
   must report the child's actual answer.

`native-agent-example.json` in this folder has the create bodies for a child
and a parent, the `addTools` body, the parent's session input, and the child's
tool arguments. It is not an import bundle; take the body you need and replace
the placeholders.

### What the parent sends and gets back

The parent passes the child's fields directly. For a child whose `inputSchema`
declares a `context` string, the tool call argument is:

```json
{"context": "Summarize this: the scheduled check completed."}
```

It is not wrapped in `inputs`. (Only starting a session through
`POST /agent-session-manager/sessions` uses
`{"agentDefinitionId": "...", "inputs": {...}}`.)

The tool returns:

```json
{
  "sessionId": "<child session id>",
  "sessionStatus": "COMPLETE",
  "lastMessage": "<the child's final answer, as text>"
}
```

In the parent's message history, this is a `tool-execution` message with
`data.toolType: "agent"`. `data.artifactId` is the child's session ID.

## Checking whether the child did its job

A child session's `COMPLETE` status means the child finished. It doesn't mean
the child's task succeeded. In testing, a child that stopped because it lacked
the information it needed still ended `COMPLETE`, and the parent's tool call
was marked `succeeded`. The only sign of the stop was the text in
`lastMessage`.

Check three things:

1. **The tool call:** the parent's `tool-execution` message has
   `status: succeeded`, with no `errorMessage` or `errorCategory`.
2. **The child session:** `GET /agent-session-manager/sessions/{sessionId}`
   using the returned `sessionId`. `FAILED` or `CANCELED` is a failure. Any
   other status except `COMPLETE` is still running. Check that
   `agentDefinitionId` and `inputs` match what the parent intended. The
   session's `agentSnapshot` shows the child's definition when it ran.
   Child sessions have `trigger.type: session`. Don't rely on
   `sessionType: child`, which can be absent.
3. **The child's answer:** read `lastMessage`, plus the child's own tool
   results if needed, and judge it against what the child was asked to do. A
   refusal, a stop or missing data is a failure even when steps 1 and 2 pass.
   Don't let the parent carry on with dependent actions, invent a result, or
   automatically retry an action that changes something.

`lastMessage` is free text. If you need structured output, put the format in the
child's instructions and treat anything that doesn't parse as unresolved.

## Reading session history

```text
GET /agent-session-manager/sessions/{sessionId}/messages?limit=100&sortBy=timestamp&sortOrder=asc
GET /agent-session-manager/sessions/{sessionId}/messages/{eventId}
```

The message list is a JSON array, and its paging is unreliable:

- Pages can be short, or even empty, in the middle of a history. On a 6-event
  session, `limit=2` returned pages of 2, 1, 0, 1, 2 and 0 events.
- Events can come back out of order across pages.

Use `limit=100` and read pages until several pages in a row are empty.
Remove duplicates by `eventId` and sort by `timestamp` yourself.

If a message has `isOutputTruncated: true`, fetch the full result from the
single-event endpoint using the message's `outcomeEventId`. There, the result
is in `data.toolOutput.payload`, not `data.output`.

When testing, record the parent session ID, the child session ID, the inputs,
both final statuses and the child's answer.

### Waiting for a person

If the child uses a WorkCenter view tool (for example an approval form), its
session stays `RUNNING` while it waits. Find the work item with
`GET /work-center-service/work-items?rootExecutionId=<sessionId>`. Only the
assigned person should complete it. Never complete an approval just to finish a
build or a test.

## Export and import

- **Export:** `GET /agent-project-service/project-bundles/{projId}/export` keeps
  the parent's `agent:<child-id>` references. It replaces each agent's provider
  with `{profileName, modelName}`.
- **Import:** `POST /agent-project-service/project-bundles/import` with
  `conflictMode: keep-both` gives the children new IDs and updates the parent's
  `agent:` references to match. The imported parent calls the imported child.
- **`providerResolutions` is required** on import. Without it, the call fails
  with HTTP 500 "Missing Params". It maps each agent's `_id` from the bundle to
  a model profile and model in the target platform; that profile and model must
  already exist:

  ```json
  "providerResolutions": {
    "<agent _id>": {"profileName": "<profile>", "modelName": "<model>"}
  }
  ```

Not yet tested: `conflictMode: replace` and importing into a different
platform. After either, read the parent back and confirm each `agent:`
reference resolves with `GET /tools/{referenceId}`.

## Permissions

- To attach a child to a parent, you need Editor access to the parent's
  project. To call the child, the person running the parent needs run access to
  the child (a project role or the child's `operators` list).
- If `GET /agent-project-service/agents/{id}` returns 403 for an agent you can
  run, read it with `GET /agent-project-service/operable-agents/{id}` instead.
  A 403 there means you lack edit access, not that agent tools are unsupported.
- Permission names differ between Cloud and on-premises. Never grant yourself
  access to make a design work; ask the project owner.

## If agent tools aren't available

On an older platform, there is no `agent:` tool. Report that this platform
doesn't support agent tools. If the design allows, offer the workflow
alternative instead: a workflow runs each agent with the `runAgent` task and
passes one agent's result to the next agent's inputs (see "Using Agents in
Workflows" in the `flowagent` skill). Don't swap in a workflow, a script or
`runCode` without telling the engineer.
