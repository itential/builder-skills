# Transcript — builder-agent skill test (eval-24, run-1)

## Task restated

Engineer's question:

> I'm using a `restCall` task to hit an Azure AD OAuth token endpoint, then a `query` task to extract the `access_token`. My query path is `'response.access_token'` but it always returns null even though the `restCall` task itself completed successfully. What's wrong?

This is a debugging/advice question (not a full workflow build), so the deliverable is a diagnosis + corrected wiring, illustrated with a JSON artifact.

## Steps taken

1. Read `/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md` in full (2442 lines, read across two `Read` calls due to truncation) before responding, per the test instructions treating it as the sole source of truth.
2. Since the question is specifically about `restCall` + `query` behavior, searched the skill file directly for `restCall`:
   ```bash
   grep -n "restCall" .claude/skills/builder-agent/SKILL.md
   ```
   This surfaced two relevant hits:
   - Line 375, in the **Guide 1 Pre-submit checklist**:
     > `[ ] restCall downstream query: path targets body field directly (e.g., "access_token") — NOT "response.access_token" (restCall has no wrapper, unlike adapter tasks)`
   - Lines 1676–1688, a dedicated `### restCall` subsection under **Utility Tasks (WorkFlowEngine)**.
3. Read the full `### restCall` subsection (SKILL.md lines 1676–1688):
   > **Response shape — no wrapper.** `restCall` returns the **already-parsed JSON body directly** as the outgoing value. There is no `response` or `result` wrapper. Query paths target body fields directly:
   > ```
   > Correct:   "query": "access_token"
   > Wrong:     "query": "response.access_token"   ← no response wrapper
   > Wrong:     "query": "result.access_token"     ← no result wrapper
   > ```
   > This is the opposite of adapter tasks (e.g., `genericAdapterRequest`), which always wrap the upstream response in `{response, headers, metrics}`. Don't cross-apply the adapter query paths to `restCall` output — you'll get null every time.
4. Cross-checked the `### query` utility task section (lines 1355–1376) for the general query task contract (`incoming`: `pass_on_null`, `query`, `obj`; `outgoing`: `return_data`) and its own warning that adapter responses are wrapped and paths must be verified against a real job's output rather than guessed — this is the general form of the same rule that trips people up with `restCall`.
5. Cross-checked `AGENTS.md` (repo root context file) Key Rule #20: *"Adapter responses are transformed... Don't assume the native API's response structure... Call the adapter endpoint directly or check openapi.json to verify the actual response shape before wiring query paths."* This reinforces the same "verify actual output shape, don't assume a wrapper" principle, though it's phrased for adapter tasks — the `restCall`-specific rule in the skill is the more precise match for the reported symptom.
6. Checked Guide 2b's advice ("Inspect the actual response before wiring a query path") for the general debugging procedure to recommend if the fix doesn't immediately resolve things: pull the job (`GET /operations-manager/jobs/{jobId}`), find the `restCall` task's outgoing value in `data.tasks`, and confirm the field is literally `access_token` at the top level (Azure AD's token response is `{token_type, expires_in, ext_expires_in, access_token, ...}` — a flat JSON object with no wrapper, consistent with what `restCall` will return unwrapped).
7. Searched the repo for any existing `restCall` task JSON examples in `helpers/assets/` to extract a real wired example (per the skill's "read real production JSON, don't guess" mandate):
   ```bash
   grep -rl '"name": "restCall"' helpers/assets/
   ```
   No hits — none of the shipped asset projects (`vendor-servicenow.json`, `vendor-infoblox-nios-ddi.json`, etc.) happen to use `restCall`. Also confirmed no `oauth_bootstrap.py` script exists yet in `scripts/` (referenced by the skill's Bootstrap Authentication section but not present in this checkout) and no other repo file wires a `restCall` task with full incoming field names.
   - **Consequence:** the skill's `### restCall` prose (response-shape rule) is fully documented and authoritative, but the exact `incoming` field names for a `restCall` task (`uri`/`method`/`headers`/`body`/`contentType` etc.) are not demonstrated anywhere in this repo's local assets. Per the skill's own instructions ("Do not guess task structure from memory... fetch schema via `multipleTaskDetails`"), those field names would normally be pulled from `{use-case}/tasks.json` and `POST /automation-studio/multipleTaskDetails?dereferenceSchemas=true` in a live session. Since there is no live platform in this test, I built the illustrative task JSON using the WorkFlowEngine utility-task conventions shown elsewhere in the skill (`query`/`merge`/`newVariable` field shapes) and flagged this assumption explicitly in the artifact so it isn't mistaken for a verified schema.

## Diagnosis

The root cause has nothing to do with Azure AD, the token request, or the `restCall` task failing — it's a **query-path mismatch caused by treating `restCall`'s output like an adapter task's output.**

- **Adapter tasks** (e.g., `genericAdapterRequest`, `createChangeRequest`) always wrap the upstream HTTP response in `{response, headers, metrics}`. That's why adapter query paths look like `"response.id"` or `"response.access_token"`.
- **`restCall` is different.** It is a WorkFlowEngine *utility* task, not an adapter task, and it returns the **already-parsed JSON response body directly** as its outgoing value — there is no `response` or `result` wrapper at all.

So when the Azure AD token endpoint returns:
```json
{
  "token_type": "Bearer",
  "expires_in": 3599,
  "access_token": "eyJ0eXAi..."
}
```
`restCall`'s outgoing `result` variable **is** that object — `access_token` is a top-level key of it, not nested under `response`. Querying `"response.access_token"` looks for a `response` key that doesn't exist, so `query` correctly (and silently, per `pass_on_null` behavior) returns null even though the HTTP call itself succeeded.

## Fix

Change the `query` task's `query` field from:
```
"query": "response.access_token"
```
to:
```
"query": "access_token"
```
with `obj` still pointing at the `restCall` task's outgoing value, e.g. `"obj": "$var.<restCallTaskId>.result"`.

No change is needed to the `restCall` task itself — it already completed successfully and is returning the correct payload; only the downstream extraction path was wrong.

**General rule to remember:** `restCall` output has no wrapper → query body fields directly. Adapter task output is wrapped in `{response, headers, metrics}` → query `response.<field>`. Don't cross-apply the pattern from one task type to the other.

**If changing the path doesn't fix it**, the next debugging step (per the skill's Guide 2b) is to stop guessing entirely and look at the real output: `GET /operations-manager/jobs/{jobId}`, then `jq '.data.tasks["<restCallTaskId>"]' job.json` to see the exact outgoing object and confirm the field name/casing Azure AD actually returned (it should be `access_token`, all lowercase with underscore, per the Microsoft identity platform's token response contract) — then wire the query path from that observed shape, not from documentation or memory.

## Artifact produced

`/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-24/new_skill/run-1/outputs/restcall-query-fix.json` — a workflow task/transition fragment showing:
- `a1a1`: the `restCall` task hitting the Azure AD token endpoint (illustrative `incoming` fields — flagged in the file as needing verification against `tasks.json`/`multipleTaskDetails` in a real session, since no local asset project wires a `restCall` task to copy from verbatim)
- a `c3c3_WRONG_EXAMPLE_query` block showing the broken `"response.access_token"` path for contrast (not part of the wired graph)
- `c3c3`: the corrected `query` task using `"access_token"` against `$var.a1a1.result`, writing to `$var.job.accessToken`
- `ef01`: a `newVariable` error-sink task so both the `restCall` error transition and the `query` failure transition can each independently route to `workflow_end` without duplicate-key conflicts (per the skill's mandatory error-transition rule for external calls, and the JSON duplicate-key rule for shared `workflow_end` targets)
- Full `transitions` block wiring `a1a1 → c3c3 → workflow_end` on success, with error/failure paths through `ef01 → workflow_end`

Full JSON content of that file:

```json
{
  "_comment": "Fragment illustrating the fix for extracting access_token after a restCall to the Azure AD OAuth token endpoint. Task ID/field names for restCall follow WorkFlowEngine utility-task conventions documented in the builder-agent skill (query/merge examples). In a live session, pull the exact restCall incoming field names from tasks.json + POST /automation-studio/multipleTaskDetails before finalizing — do not treat the incoming field names below as authoritative without that lookup.",

  "tasks": {
    "a1a1": {
      "name": "restCall",
      "canvasName": "restCall",
      "summary": "Get Azure AD OAuth Token",
      "description": "POSTs client_credentials grant to the Azure AD v2.0 token endpoint",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "uri": "https://login.microsoftonline.com/$var.job.tenantId/oauth2/v2.0/token",
          "method": "POST",
          "headers": {"Content-Type": "application/x-www-form-urlencoded"},
          "body": "$var.b2b2.merged_object",
          "contentType": "application/x-www-form-urlencoded"
        },
        "outgoing": {
          "result": null
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": {"x": 600, "y": 420}
    },

    "c3c3_WRONG_EXAMPLE_query": {
      "_comment": "This is the BROKEN version — shown for contrast only, not part of the wired workflow.",
      "name": "query",
      "variables": {
        "incoming": {
          "pass_on_null": false,
          "query": "response.access_token",
          "obj": "$var.a1a1.result"
        },
        "outgoing": {
          "return_data": "$var.job.accessToken"
        }
      }
    },

    "c3c3": {
      "name": "query",
      "canvasName": "query",
      "summary": "Extract Access Token",
      "description": "restCall returns the parsed JSON body directly — no response/result wrapper — so the path targets the body field by name.",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "pass_on_null": false,
          "query": "access_token",
          "obj": "$var.a1a1.result"
        },
        "outgoing": {
          "return_data": "$var.job.accessToken"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": {"x": 600, "y": 528}
    },

    "ef01": {
      "name": "newVariable",
      "canvasName": "newVariable",
      "summary": "OAuth Token Request Failed",
      "location": "Application",
      "locationType": null,
      "app": "WorkFlowEngine",
      "type": "operation",
      "displayName": "WorkFlowEngine",
      "variables": {
        "incoming": {
          "name": "taskStatus",
          "value": "error"
        },
        "outgoing": {
          "value": "$var.job.taskStatus"
        },
        "error": "",
        "decorators": []
      },
      "groups": [],
      "actor": "Pronghorn",
      "scheduled": false,
      "nodeLocation": {"x": 864, "y": 420}
    }
  },

  "transitions": {
    "a1a1": {
      "c3c3": {"type": "standard", "state": "success"},
      "ef01": {"type": "standard", "state": "error"}
    },
    "c3c3": {
      "workflow_end": {"type": "standard", "state": "success"},
      "ef01": {"type": "standard", "state": "failure"}
    },
    "ef01": {
      "workflow_end": {"type": "standard", "state": "success"}
    }
  }
}
```

## Final answer to the engineer (verbatim)

> The `restCall` task isn't the problem — it completed fine and is returning the right data. The issue is the query path: `restCall` is a WorkFlowEngine utility task, not an adapter task, so its output has **no `response`/`result` wrapper**. It returns the parsed JSON body directly as its outgoing value. Since Azure AD's token response looks like `{"token_type": "Bearer", "expires_in": 3599, "access_token": "eyJ..."}`, `access_token` is a top-level field of that object — not nested under `response`.
>
> Change your query task's path from `"response.access_token"` to just `"access_token"`, keeping `obj` pointed at the `restCall` task's output (e.g. `$var.<restCallTaskId>.result`). That's the fix — no changes needed to the `restCall` task itself.
>
> For future reference: this wrapper distinction is the single most common gotcha between `restCall` and adapter tasks like `genericAdapterRequest`. Adapter tasks always wrap upstream responses in `{response, headers, metrics}`, so adapter query paths correctly start with `response.`. `restCall` never does — always query the body field directly. If you ever hit a similar null after switching task types, pull the job (`GET /operations-manager/jobs/{jobId}`) and look at `data.tasks["<taskId>"]` to see the real outgoing shape rather than assuming it matches the pattern from a different task type.
