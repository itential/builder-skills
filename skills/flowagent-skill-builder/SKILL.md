---
name: flowagent-skill-builder
description: Use this skill to write, package, import and test skills for FlowAgent (FlowAI) agents on the Itential Platform — the procedure packages an agent loads on demand alongside its tools. Trigger it for phrases like "write a skill for my agent", "create a FlowAgent skill", "turn this runbook into an agent skill", "import this skill into FlowAgent", or "add a vendor to this agent skill". Skills follow the Agent Skills format in the shape of itential/infra-agent-skills (one operation per skill, a short SKILL.md that routes to per-vendor procedure and endpoint files), so skills from that library import unchanged. NOT for building, configuring or running the agents themselves — use /flowagent for that.
---

# FlowAgent Skill Builder

**Purpose:** write a skill a FlowAgent agent can load at run time, import it into the platform, and
prove an agent uses it.
**Input:** an operation to teach (and the vendor documentation behind it), or an existing skill
folder — for example one from [itential/infra-agent-skills](https://github.com/itential/infra-agent-skills).
**Output:** a skill folder in the working directory, imported into Agent Project Service as a
versioned skill, and a test session showing an agent loading it and answering from it.

Building the agent that uses the skill — its tools, profile, approvals, sessions — is `/flowagent`'s
job. This skill covers the skill itself.

## Customization

Before using this skill, check `custom/org/`, `custom/team/` and `custom/dev/` in this
skill's own folder. Read every `.md` file found — any folder may be empty or absent. Apply
them on top of everything below; where a file overrides a specific rule here, follow the
override. More specific wins: dev > team > org > this document. No customization may weaken
this skill's safety rules (confirmation gates in destructive steps, checking affected agents before
a delete) or put credentials in committed files.

**Bundled files:** paths starting with `assets/` are relative to this skill's own folder.
When you read one, use this skill's folder + that relative path.

---

## How agents use skills

A tool *does* something; a skill tells the agent *how* to do it with its tools. An agent sees each
attached skill's name and description, and reads the rest only when a request needs it, through two
built-in tools: `loadSkill` (the `SKILL.md` body) and `loadSkillResource` (one file under it). Both
appear in the session log as `TOOL_CALLED` with `toolType: "built-in"`. So the `description` decides
whether the skill is used at all, and the reference files are read one at a time.

## Step 1 — Decide whether it should be a skill

A skill teaches **one operation, done the same way every time**: create a DNS record, upgrade a
device's software, close a change request. Write one only when it carries something a capable
agent with the vendor's documentation lacks — a step order, a safeguard, a platform gotcha, or
exact success and failure checks. If removing it wouldn't make the agent worse or less safe, don't
write it.

| Content | Where |
|---|---|
| The agent's role, inputs, output format, when to ask a person | The agent's `instructions` (`/flowagent`) |
| How to carry out one operation, per vendor | A skill |
| The action itself — an API call, a command, a workflow | A tool on the agent (`/flowagent`) |
| Your team's process, naming or approval chain | The agent's `instructions`, never a skill |

Test: could two engineers at two different companies use the skill unchanged? If it depends on one
team's ticketing process or naming convention, it's agent instructions, not a skill.

Before writing, check whether it exists: `GET /agent-project-service/skills?search=<word>` on the
platform, and the infra-agent-skills catalog. Extend an existing skill (a new vendor, a new
operation) rather than adding a sibling.

## Step 2 — Lay out the folder

Write it in the working directory, under `agent-skills/<capability>/`:

```
<capability>/                    # lowercase kebab-case; equals the frontmatter name
├── SKILL.md                     # short and stable: routes to the vendor's procedure
└── references/
    ├── INDEX.md                 # table: vendor → directory → scope → notes
    └── <vendor>/
        ├── procedure.md         # the steps, in plain operation language
        └── endpoints.md         # the literal calls: method, path, fields, base URL, error strings
```

- **Name it for the operation, never a tool or vendor:** `dns-record-management`, not `infoblox-dns`.
- **One vendor with several platform families** (IOS-XE and IOS XR): one `<family>.md` per family,
  each with its own `<family>-endpoints.md` — never two bare `endpoints.md` files.
- **`INDEX.md` is for choosing a vendor:** the table and short scope notes, nothing else.

## Step 3 — Write `SKILL.md`

**Frontmatter:** `name` and `description` only (add `argument-hint` if the skill takes positional
arguments). The `description` must say what the skill does, when to use it, which vendors it covers,
and what it assumes ("Assumes an authenticated API client for the target platform"). At most 1024
characters, and valid YAML: no `: ` or ` #` inside an unquoted value.

**Body, in this order:**
1. Title and one-line purpose.
2. **When to use this skill.**
3. **Universal concepts** — only facts true for *every* vendor listed. A field name or path belongs to
   one vendor, so it goes under `references/<vendor>/`.
4. **Procedure** — three things only: identify the target vendor from the request, open
   `references/<vendor>/procedure.md` and follow it exactly, and report the outcome in that
   procedure's own status words.
5. **Known limitations.**
6. **Tools** — the operations the procedure needs ("look up the zone", "create the record"),
   described generically.
7. **Verification checklist.**

Keep it under about 500 lines, with no JSON examples or field tables; its size shouldn't grow as
vendors are added. It changes only to fix shared content or to add a vendor pointer.

## Step 4 — Write `procedure.md` and `endpoints.md`

- **`procedure.md` uses operation language:** "create the record with the fields below", not
  `POST /zones/{id}/dns_records`. CLI-driven procedures are the exception — the command is the
  payload, so keep it inline.
- **`endpoints.md` holds the wiring:** method, path, fields, base URL, and any exact error string
  worth matching. Refer to an error by name from the procedure step.
- **State success in plain words** — the output or state that proves the step worked — and give
  every documented error its handling inline.
- **Put a confirmation gate in every step that deletes, overwrites, reloads or changes a live
  system:** "stop and confirm with the operator before proceeding."
- **Ground every fact in the vendor's own documentation, in your own words.** Write unknowns as
  facts: "Not documented: rate limits."
- **Write for the agent that runs it.** Every sentence must help it do the task: no research notes,
  references to repo rules, to-dos or authoring rationale. A one-line source citation is fine.

Treat skill content like code: an agent follows `procedure.md` as instructions, so anyone who can
change it can direct every agent that loads it. Check each step against its source.

## Step 5 — Match it to the agent's tools

An agent acts only through its tools; a skill without them is advice it can't carry out. Record, for
whoever builds the agent with `/flowagent`:

- **A tool for each operation** in the skill's Tools section, per vendor — an adapter method, app
  task, Gateway5 service or workflow. Find them with `GET /tools?name=<method>`. If no tool makes a
  call in `endpoints.md`, one has to be added (an adapter method, or a workflow that makes the call).
- **A work-item tool for each confirmation gate** — ViewData or QuickForm — that the agent's
  `instructions` say to use before any write.
- **A decorator on a broad write tool**, so it accepts only the fields the procedure uses.

## Step 6 — Package, preview and import

Authenticate as in `assets/AGENTS.md` ("Auth Reuse"); confirm the endpoints below against the
platform's `openapi.json`. The request body for `preview` and `import` is not typed there.

**Package** either the `SKILL.md` text alone (`"filename": "SKILL.md"`, `content` = the text), or the
folder as a `.zip`/`.tar` with `SKILL.md` at its root or in its single top-level folder, sent
base64-encoded (`"filename": "<name>.zip"`). At most 10 MB decoded. `SKILL.md` must start with `---`
frontmatter, or preview and import return 400.

**Preview** — saves nothing:
```
POST /agent-project-service/skills/preview   {"filename": "<name>.zip", "content": "<base64>"}
```
It returns the parsed `name`, `description`, folders, `warnings`, and `existing`. Fix every warning.
A non-null `existing` means the import adds a version to that skill.

**Import:**
```
POST /agent-project-service/skills/import    {"filename": "<name>.zip", "content": "<base64>",
                                              "permissions": {"writeUserIds": ["<account-id>"]}}
```
`permissions` needs at least one user or group in `writeUserIds` or `writeGroupIds` (your account ID
is `GET /whoami` → `id`). It returns `{"skill": {"id", "name", "version", "created"}}`. The skill is
matched by `name`: **every import of an existing name adds a version, even when nothing changed** —
preview first, and don't re-import just to check.

Read it back: `GET /agent-project-service/skills/{skillId}` returns the `body` and every file under
`resources`; `GET .../resource?path=<path>` returns one file.

## Step 7 — Test it with an agent

1. Attach the skill to a test agent (built with `/flowagent`) that has the tools from Step 5:
   `"skills": [{"skillId": "<id>", "version": "latest"}]` on create, or `addSkills` on update.
2. Run a session whose request needs one vendor's procedure.
3. Read the message log: `loadSkill`, then `loadSkillResource` for that vendor's `procedure.md` or
   `endpoints.md`, then an answer that matches the file. If the agent didn't load the skill, the
   `description` doesn't match the request — fix it and import again.
4. Delete the test agent when done (and its project, if you created one for the test).

## Step 8 — Update or retire a skill

- **Update:** edit the files and import again; that's a new version. Agents with
  `"version": "latest"` get it on their next session; agents pinned to a number don't.
  `GET .../skills/{skillId}/versions` lists them.
- **Before deleting**, run `GET .../skills/{skillId}/affected-agents`. The delete succeeds even if
  agents use the skill, and their entry turns to `"state": "missing"`. Tell the user which agents
  are affected and get a yes first.
- **Moving to another platform:** export (`GET .../skills/{skillId}/export`) or re-import the folder.
  A FlowAgent project bundle carries only each agent's skill reference, not the skill, so import the
  skill on the target first; its `skillId` will differ there.

## API reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/agent-project-service/skills/preview` | Parse without saving: `{filename, content}` |
| POST | `/agent-project-service/skills/import` | Create, or add a version: `{filename, content, permissions}` |
| GET | `/agent-project-service/skills` | List (`search`, `nameContains`, `limit`, `skip`, …); items have `skillId`, `name`, `version` |
| GET | `/agent-project-service/skills/{skillId}` | Get (`version`, `includeDeleted`): `body`, `resources`, `checksum` |
| GET | `/agent-project-service/skills/{skillId}/resource?path=<path>` | One file's content |
| GET | `/agent-project-service/skills/{skillId}/versions` | `currentVersion` and every version |
| GET | `/agent-project-service/skills/{skillId}/affected-agents` | Projects and agents using it, and whether each follows `latest` |
| GET | `/agent-project-service/skills/{skillId}/export` | `{filename, contentType, content}` (JSON, though the spec calls it a zip) |
| DELETE | `/agent-project-service/skills/{skillId}` | Delete (Step 8) |

## Checklist

- [ ] One operation, named for the operation, lowercase kebab-case, folder = `name`
- [ ] Passes the "two engineers at two companies" test and carries something the agent lacks
- [ ] `description` says what, when, which vendors, and what it assumes; ≤ 1024 characters
- [ ] `SKILL.md` routes only; vendor detail is under `references/<vendor>/`; `INDEX.md` lists every vendor
- [ ] Wire-level calls only in `endpoints.md`; plain operation language in `procedure.md`
- [ ] Every destructive step has its confirmation gate, with a work-item tool for it on the agent
- [ ] The agent has a tool for every operation it will run
- [ ] Preview shows no warnings; a test session loads the skill and the right file, and the answer matches it
