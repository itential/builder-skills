---
name: explore
description: Use this skill whenever someone wants to connect to an Itential platform and browse, inspect, or discover what's there — without starting a formal delivery. Trigger it for phrases like "connect to my platform", "show me what adapters are running", "authenticate and pull platform data", "I want to poke around before starting", "what workflows exist?", "give me an inventory of the platform", "browse capabilities freely", "check if adapter X is running", or "I just set up a new environment — show me what's there". Also use it for ad-hoc freestyle work where the user wants to build something directly without going through the full spec→design→build lifecycle.
---

# Explore

**Path:** Freeform — not part of the delivery lifecycle
**Owns:** Auth, environment discovery, freestyle skill use
**Use when:** You want to browse adapters, try tasks, build something experimental, or understand the platform before committing to a spec

---

## What This Does

Connects you to a platform, pulls everything needed to work freely, and routes you to the right skill for whatever you want to do.

```
/explore
    │
    ├── Auth (from env file or interactive)
    ├── Pull platform data
    ├── Summarize environment
    └── Use skills directly
```

---

## Step 1: Authenticate

Check for credentials in this order:
1. `{use-case}/.env` — use-case-specific
2. `${CLAUDE_PLUGIN_ROOT}/environments/*.env` — pre-configured environments at repo root

If found, authenticate automatically. If not, ask:
1. Platform URL
2. Credentials (username/password or client_id/secret)

**Local Development (username/password):**
```
POST /login
Content-Type: application/json

{"username": "admin", "password": "admin"}
```
Returns a token string. Use as query parameter: `?token=TOKEN`

**Cloud / OAuth:**
```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET&grant_type=client_credentials
```
Returns `{"access_token": "..."}`. Use as Bearer header.

Save to `.auth.json`:
```json
{
  "platform_url": "https://...",
  "auth_method": "oauth",
  "token": "eyJhbG...",
  "timestamp": "2026-03-25T10:00:00Z"
}
```

---

## Step 2: Pull Platform Data

Run in two groups. Do not run all in one parallel batch — if one fails, parallel cancellation kills the others.

**Group 1 (core — run in parallel):**
```bash
curl -s "{BASE}/help/openapi?url={ENCODED_BASE}&token=TOKEN" > {use-case}/openapi.json
curl -s "{BASE}/workflow_builder/tasks/list?token=TOKEN"     > {use-case}/tasks.json
curl -s "{BASE}/automation-studio/apps/list?token=TOKEN"    > {use-case}/apps.json
curl -s "{BASE}/health/adapters?token=TOKEN"                > {use-case}/adapters.json
curl -s "{BASE}/health/applications?token=TOKEN"            > {use-case}/applications.json
```

**Group 2 (environment-specific — run in parallel after Group 1):**

Devices (note: POST, not GET):
```bash
curl -s -w "\n%{http_code}" -X POST "{BASE}/configuration_manager/devices?token=TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"options":{"start":0,"limit":1000,"sort":[{"name":1}],"order":"ascending"}}' \
  > {use-case}/devices.json
```

Existing workflows:
```bash
curl -s "{BASE}/automation-studio/workflows?limit=500&token=TOKEN" > {use-case}/workflows.json
```

Before parsing any saved file, validate JSON:
```bash
jq type {use-case}/devices.json 2>/dev/null || echo "empty"
```
If invalid, treat as no data — don't block.

---

## Step 3: Present Summary

Show:
- Adapters: name, state, connection
- Apps: count, key platform apps running
- Tasks: count
- Devices: count and OS types (if available)
- Existing workflows: count

> **Visibility note:** Itential Automation Studio access control has two layers. **Project-scoped assets** (anything inside a named project) are gated by **per-project ACLs** — the calling client only sees projects whose ACL includes the client or one of its groups, and there is no platform-wide "admin" or "all-projects" role. **Global Automation Studio assets** (workflows, templates, etc. that live outside any project) are not access-restricted that way and are visible to any authenticated client. If the engineer expects a specific *project* (or any asset inside one) and it does not appear, treat it as *possibly access-restricted*, not *missing* — see the gotcha below. For global assets, absence is real absence.

---

## Step 3b: Initialize Memory File

After pulling platform data, check for `{use-case}/use-case-memory.md`:
- **Exists** → read it. It has context from a previous session — platform URL, prior decisions, open items.
- **Missing** → create it from `${CLAUDE_PLUGIN_ROOT}/helpers/use-case-memory.md`. Populate Platform URL, `Stage: requirements` (explore is freeform — set the real stage once the engineer commits to a delivery path), `Status: active`, and any adapter/app names discovered in Step 2.

---

## Step 4: Route to Skills

Point to the right skill for what the engineer wants to do:

| I want to... | Use |
|-------------|-----|
| Build workflows, templates, or projects | `/builder-agent` |
| Manage devices, backups, diffs | `/itential-devices` |
| Build compliance and golden config | `/itential-golden-config` |
| Build IAG services (Python, Ansible, OpenTofu) | `/iag` |
| Create AI agents | `/flowagent` |
| Manage lifecycle resources | `/itential-lcm` |
| Manage device inventories (IAG5) | `/itential-inventory` |

---

## Gotchas

- OAuth MUST use `Content-Type: application/x-www-form-urlencoded`, not JSON
- Tokens expire mid-session — re-authenticate silently from `.env` on auth errors
- OpenAPI spec is ~1.5MB — search locally with `jq`, never load into context
- `tasks/list` `app` field has WRONG casing for adapters — use `apps/list` for correct names
- Devices endpoint is POST not GET — body required
- **Project list responses are RBAC-filtered — absence in the project list does NOT mean the project doesn't exist.** Itential projects use per-project ACLs only: every project explicitly grants access to specific users or groups, and there is no platform-wide "admin" or "all-projects" role. If the engineer names a specific *project* (or any asset inside one) you can't find, say *"not visible to this client (`{client_id}`) — possibly access-restricted; ask the project owner (or someone with manage rights on that project) to add `{client_id}` to its ACL"* rather than *"doesn't exist"*. Never grant access to yourself — ask the engineer how to proceed. **Global Automation Studio assets** (anything outside a named project) are not access-restricted in the same way; for those, absence in the API response is real absence.
- `PATCH /automation-studio/projects/{id}` silently ignores an `accessControl` body — use the `members` array instead: `[{"type": "account"|"group", "reference": "<id>", "role": "owner"|"editor"|"operator"|"viewer"}]`. See [#62](https://github.com/itential/builder-skills/issues/62)
