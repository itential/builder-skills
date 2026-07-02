# Transcript — builder-agent skill test (old skill), eval-24

## Task as given

> I'm using a restCall task to hit an Azure AD OAuth token endpoint, then a query task to
> extract the access_token. My query path is `response.access_token` but it always returns
> null even though the restCall task itself completed successfully. What's wrong?

This is a debugging/advice question under the `builder-agent` skill (Guide 2: "Debug a failed
job" / Guide 2b: "Work with any unfamiliar adapter task" territory, even though restCall is not
technically an adapter task). No live Itential platform is connected in this session, so no real
HTTP calls or job fetches were made — the diagnosis below is built entirely from what
`SKILL.md` documents plus what's actually present in the repo's `helpers/assets/` production
exports.

## Skill sections consulted (in order)

1. **Full read of `/tmp/eval-old-skill/builder-agent/SKILL.md`** (2314 lines, read in two passes
   due to truncation) to make sure nothing later in the file overrode or extended what I found
   early on.
2. **`### query`** (~line 1279-1300) — the query task's documented behavior:
   - Incoming: `pass_on_null`, `query` (dot-path), `obj`
   - Outgoing: `return_data`
   - **Key line (verbatim):** *"Don't guess the query path for adapter responses. Adapters
     transform upstream API responses — the field path in the adapter's output is NOT the same
     as the native API's response structure. The adapter's `result` outgoing is always a
     `{response, headers, metrics}` object, never a primitive... Always verify the actual
     response shape from a test job (`GET /operations-manager/jobs/{jobId}` → `data.tasks`)
     before wiring a path."*
   - This tells us the `{response, headers, metrics}` envelope is a property of **Adapter**
     tasks specifically — it's explicitly framed as something adapters do to transform
     responses.
3. **`### restCall`** (~line 1560) — this is the entirety of what the skill documents for this
   task:
   > "Make external HTTP calls from within a workflow. Use when calling APIs not exposed
   > through adapters."
   No incoming/outgoing field list, no example JSON, no note about response shape — unlike
   every other Utility Task in that section (`query`, `merge`, `parse`, `evaluation`,
   `transformation`, `decision`, `modify`, `validateJsonSchema` all get an Incoming/Outgoing
   breakdown; `restCall` does not). **This is a real documentation gap in the skill as it stands
   today.**
4. **Guide 2b — "Inspect the actual response before wiring a query path"** (~line 464-479):
   the mandated debugging technique — after a successful test run, `GET
   /operations-manager/jobs/{jobId}`, find the task by ID in `data.tasks`, read its outgoing
   variables directly, and wire the query path from what's actually there, "not from the
   upstream API docs." This is the single most load-bearing instruction for this exact
   symptom, and it applies to any task type, not just adapters.
5. **Gotcha #24** (line 2176): *"Adapter task `result` is always an object — never a primitive.
   When the upstream API returns a simple string... it's at `result.response`."* Again scoped
   to adapter tasks specifically.
6. **Guide 1 STOP block** — instructs to look up real task JSON from
   `${CLAUDE_PLUGIN_ROOT}/helpers/assets/` before guessing task structure. I resolved
   `CLAUDE_PLUGIN_ROOT` to the real repo (`/Users/ankitrbhansali/builderskills/builder-skills`)
   and checked:
   ```bash
   ls helpers/assets/
   grep -rl '"restCall"' helpers/assets/
   ```
   Result: **no asset project in the repo has a wired `restCall` task** to extract as a
   real example (only `vendor-servicenow.json`, `vendor-infoblox-nios-ddi.json`,
   `vendor-netbox.json`, `vendor-cisco-ios.json`, `vendor-arista-eos.json`,
   `vendor-juniper-junos.json`, `itential-platform-configuration-management.json`,
   `itential-platform-data-manipulation.json`, `itential-platform-email.json`,
   `itential-platform-regex-operations.json`, and the `lcm/` project exist — none contain
   `restCall`). So the skill's own instruction to "extract a real example first, don't guess
   from memory" cannot be fully satisfied for this specific task type with what's currently in
   the repo.
   I also checked whether a `tasks.json` / `task-schemas.json` for this use-case's workspace
   existed anywhere reachable — none was provided for this ad-hoc debugging question (there's
   no `{use-case}/` workspace attached to this conversation), so I could not pull the exact
   `multipleTaskDetails` schema for `restCall` either. Per the skill, that lookup (`POST
   /automation-studio/multipleTaskDetails?dereferenceSchemas=true`) is the authoritative next
   step the engineer should run themselves against their real platform to get restCall's exact
   outgoing variable name and shape.

## Reasoning / diagnosis

Putting together what the skill *does* say:

- The `{response, headers, metrics}` wrapper is explicitly and repeatedly described as an
  **Adapter**-task behavior (`query` section's "IMPORTANT" note, and Gotcha #24) — it exists
  because adapters sit between the workflow and an upstream vendor API and normalize/transform
  that upstream response into a consistent envelope.
- `restCall` is listed under **"Utility Tasks (WorkFlowEngine)"** — an **Application**-location
  task, not an Adapter-location task. It talks straight to an external HTTP endpoint with no
  adapter in between to apply that transformation/wrapping. There is no documented reason for
  it to apply the same `{response, headers, metrics}` envelope, and the skill doesn't claim it
  does.
- The practical symptom matches this exactly: `restCall` finishes with a "success" job status
  (so the HTTP round-trip to Azure AD's token endpoint worked and returned a 200 with a JSON
  body containing `access_token`), but the `query` task's path `response.access_token` resolves
  to `null` — consistent with the outgoing variable already **being** the parsed JSON body
  (i.e., `access_token` is at the top level), so reaching one level down into a `response` key
  that doesn't exist returns nothing. With `pass_on_null: false` (the convention shown
  everywhere else in the skill), a query that can't find the path returns null/undefined and
  routes to `failure` — but even wired with `pass_on_null: true` it will just silently carry
  `null` forward, which matches "always returns null."

**Root cause:** the query path is written as if `restCall`'s response were wrapped the way an
Adapter task's response is (`response.<field>`), but `restCall` is a plain WorkFlowEngine
Application task and its outgoing value is already the parsed token response — there's no
extra `response` envelope to descend through.

**Fix:** change the query task's `incoming.query` from `"response.access_token"` to
`"access_token"` (leaving `incoming.obj` pointed at whatever restCall's outgoing variable
name actually is, e.g. `$var.<restCallTaskId>.response` — the *variable name* `response` and
the *query path* `response` are two different things; only the path needs to change).

**Mandatory verification step (per Guide 2b, since no live platform is connected in this
session):** before treating this as final, the engineer should pull the actual completed job
and look at the real shape:
```
GET /operations-manager/jobs/{jobId}
→ data.tasks["<restCall task id>"]   (read the resolved outgoing value directly)
```
This confirms the exact field name Azure AD's token response uses at the top level
(`access_token`, per the OAuth2 client-credentials spec) and rules out any customization. I
could not run this call myself in this session — no live platform, no job ID — so the fix
above is the correct diagnosis given everything documented, but should be spot-checked against
one real job before being treated as the final answer.

## Documentation gap surfaced

While working this, `SKILL.md`'s `### restCall` entry (line ~1560) is a one-line stub with no
Incoming/Outgoing field list and no worked example — every other Utility Task in that section
has one. There's also no asset project in `helpers/assets/` demonstrating a wired `restCall`
task. Per the skill's own Step 14 ("Update this skill" — add detail to the relevant body
section when hitting undocumented platform behavior), this is exactly the kind of gap that
should be closed: add an Incoming/Outgoing breakdown for `restCall` explicitly stating that its
outgoing value is the raw parsed response body (no `{response, headers, metrics}` envelope, that
being an Adapter-only convention), plus a worked example, and ideally save a real exported
restCall-using project to `helpers/assets/` the next time one is built.

## Artifacts produced

- `outputs/query-task-fix.json` — before/after JSON for the `query` task (broken path
  `response.access_token` vs. corrected path `access_token`), plus the full diagnosis and
  caveats inline.

## Final answer to the engineer (verbatim)

> Your `restCall` task isn't broken — the query path is looking one level too deep.
>
> `restCall` is a plain WorkFlowEngine utility task (Application location), not an Adapter
> task. The `{response, headers, metrics}` wrapper you may be used to (e.g. `result.response`
> on a ServiceNow/Infoblox/etc. adapter call) is something Adapter tasks specifically apply
> when they normalize an upstream vendor API's response — it doesn't apply to `restCall`. When
> `restCall` hits Azure AD's token endpoint and gets back a 200 with a JSON body like
> `{"token_type": "Bearer", "expires_in": 3599, "access_token": "eyJ0..."}`, that parsed body
> *is* the task's outgoing value — there's no extra `response` key wrapping it.
>
> So your query, wired as `obj: $var.<restCallTaskId>.response, query: "response.access_token"`,
> is trying to read `.response.access_token` off an object that only has `.access_token` at the
> top level — hence the silent null (this also matches the platform's general behavior:
> `query` with a path that doesn't exist returns null/undefined rather than erroring, so the
> restCall task itself correctly reports success while the query quietly comes back empty).
>
> **Fix:** change the query task's `query` field from `"response.access_token"` to
> `"access_token"`. Leave `obj` pointed at the same outgoing variable you're already using.
>
> Before you call this fully closed, pull one real completed job and look at the actual
> resolved value on the restCall task (`GET /operations-manager/jobs/{jobId}` →
> `data.tasks["<restCall task id>"]`) to confirm the top-level field name matches exactly (it
> should be `access_token` per the OAuth2 client-credentials response spec, but worth
> eyeballing once against your tenant's real response) — that's the standard "don't guess a
> query path, verify it against a live job" rule this skill uses everywhere else, and I wasn't
> able to run that check myself since there's no platform connected in this session.
>
> Separately, worth flagging: the skill I'm working from doesn't actually document `restCall`'s
> input/output shape at all (it's a one-line stub, unlike every other utility task which lists
> Incoming/Outgoing fields), and none of the production asset exports in the repo have a wired
> `restCall` example either. This diagnosis is correct based on how `restCall` behaves as a
> plain WorkFlowEngine task and matches the OAuth2 spec, but I'd treat filling in that gap in
> the skill (with a worked example) as a good follow-up so the next person doesn't have to
> re-derive this.
