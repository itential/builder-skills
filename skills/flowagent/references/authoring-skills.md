# Writing Skills for FlowAgent Agents

Use this to write a skill a FlowAgent agent loads at run time. The shape follows
[itential/infra-agent-skills](https://github.com/itential/infra-agent-skills), whose skills import
into FlowAgent as they are. How to import and attach a skill is in SKILL.md → Skills.

## Decide whether it should be a skill

A skill teaches **one operation, done the same way every time**: create a DNS record, upgrade a
device's software, close a change request. Write one only when it carries something a capable
agent with the vendor's documentation lacks — a step order, a safeguard, a platform gotcha, or
exact success and failure checks. If removing the skill wouldn't make the agent worse or less safe,
don't write it.

Put each kind of content where it belongs:

| Content | Where |
|---|---|
| The agent's role, inputs, output format, when to ask a person | The agent's `instructions` |
| How to carry out one operation, per vendor | A skill |
| The action itself — an API call, a command, a workflow | A tool on the agent |
| Your team's process, naming or approval chain | The agent's `instructions`, never a skill |

Test: could two engineers at two different companies use the skill unchanged? If it depends on
your ticketing process or naming convention, it's agent instructions, not a skill.

## Shape

```
<capability>/                    # lowercase kebab-case; equals the frontmatter name
├── SKILL.md                     # short and stable: routes to the vendor's procedure
└── references/
    ├── INDEX.md                 # table: vendor → directory → scope → notes
    └── <vendor>/
        ├── procedure.md         # the steps, in plain operation language
        └── endpoints.md         # the literal calls: method, path, fields, base URL, error strings
```

- **Name the skill for the operation, never for a tool or vendor:** `dns-record-management`, not
  `infoblox-dns`. Vendors go under `references/`. Fold a new operation into the skill it belongs to
  rather than adding a sibling skill.
- **One vendor with several platform families** (IOS-XE and IOS XR): one `<family>.md` per family,
  each with its own `<family>-endpoints.md` — never two bare `endpoints.md` files that overwrite each
  other.
- **`INDEX.md` is for choosing a vendor:** the table plus short scope notes. Nothing else.

## Write `SKILL.md`

**Frontmatter:** `name` and `description` only (add `argument-hint` if the skill takes positional
arguments). The `description` is what the agent matches requests against, so it must say what the
skill does, when to use it, which vendors it covers, and what it assumes ("Assumes an authenticated
API client for the target platform"). At most 1024 characters, and valid YAML: no `: ` or ` #`
inside an unquoted value.

**Body, in this order:**
1. Title and one-line purpose.
2. **When to use this skill.**
3. **Universal concepts** — only facts true for *every* vendor listed. A field name or path belongs
   to one vendor, so it goes under `references/<vendor>/`.
4. **Procedure** — three things only: identify the target vendor from the request, open
   `references/<vendor>/procedure.md` and follow it exactly, and report the outcome in that
   procedure's own status words.
5. **Known limitations.**
6. **Tools** — the operations the procedure needs ("look up the zone", "create the record"),
   described generically.
7. **Verification checklist.**

Keep `SKILL.md` under about 500 lines, with no JSON examples or field tables; its size shouldn't
grow as vendors are added. It only changes to fix shared content or add a vendor pointer.

## Write `procedure.md` and `endpoints.md`

- **`procedure.md` uses operation language:** "create the record with the fields below", not
  `POST /zones/{id}/dns_records`. CLI-driven procedures are the exception — the command is the
  payload, so keep it inline.
- **`endpoints.md` holds the wiring:** method, path, fields, base URL, and any exact error string
  worth matching. Refer to an error by name from the procedure step.
- **State success in plain words** — the exact output or state that proves the step worked — and
  give every documented error its handling inline.
- **Put a confirmation gate in every step that deletes, overwrites, reloads or changes a live
  system:** "stop and confirm with the operator before proceeding." Don't leave it for the agent to
  infer.
- **Ground every fact in the vendor's own documentation, in your own words.** Write unknowns as
  facts: "Not documented: rate limits."

## Match the skill to the agent's tools

An agent can only act through its tools; a skill without the matching tools is advice it can't
carry out. When you attach a skill:

- **Give the agent a tool for each operation** in the skill's Tools section, for each vendor it
  will use — an adapter method, app task, Gateway5 service or workflow. Find them with
  `GET /tools?name=<method>`. If no tool makes a call in `endpoints.md`, add one (an adapter method,
  or a workflow that makes the call), or the agent can't do that step.
- **Turn each confirmation gate into a work item.** Give the agent a view tool (ViewData or
  QuickForm) and tell it in `instructions` to get approval through it before any write tool runs
  (SKILL.md → Human approval).
- **Narrow a broad write tool with a decorator** so it only accepts the fields the procedure uses.

## Write for the agent that runs it

Every file is read by the agent at run time, so every sentence must help it do the task. Leave out
research notes ("confirmed during this pass"), references to repo rules, to-dos and authoring
rationale. A one-line source citation is fine.

Treat skill content like code: the agent follows `procedure.md` as instructions, so anyone who can
change it can direct every agent that loads it. Review each step against its source before import.

## Package, import and test

1. Zip the capability folder (`SKILL.md` inside the single top-level folder) and preview it
   (SKILL.md → Skills).
2. Import it, attach it to a test agent along with its tools, and run a session that needs one
   vendor's procedure.
3. Check the log: `loadSkill`, then `loadSkillResource` for that vendor's `procedure.md` or
   `endpoints.md`, then an answer that matches the file. If the agent didn't load the skill, the
   `description` doesn't match the request — fix it and re-import.
4. To change a skill, edit the files and import again: a new version. Agents on `latest` get it;
   pinned agents don't.

## Checklist

- [ ] One operation, named for the operation, lowercase kebab-case, folder = `name`
- [ ] Passes the "two engineers at two companies" test and carries something the agent lacks
- [ ] `description` says what, when, which vendors, and what it assumes; ≤ 1024 characters
- [ ] `SKILL.md` routes only; vendor detail is under `references/<vendor>/`; `INDEX.md` lists every vendor
- [ ] Wire-level calls only in `endpoints.md`; plain operation language in `procedure.md`
- [ ] Every destructive step has its confirmation gate, and the agent has a work-item tool for it
- [ ] The agent has a tool for every operation it will run
- [ ] A test session loads the skill and the right reference file, and the answer matches it
