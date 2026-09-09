# Customizing Foundational Skills

Every skill in `.claude/skills/` is foundational — owned and updated by Itential. Customers should never edit a skill's `SKILL.md` directly: doing so gets silently overwritten or produces merge conflicts the next time that skill is updated upstream.

Instead, each skill has a `custom/` folder reserved for customer-owned content. The skill's own `SKILL.md` reads it before acting. This document is the shared reference every skill's pointer line links back to — read it once, apply it everywhere.

## Structure

```
.claude/skills/<skill-name>/
├── SKILL.md              ← foundational, Itential-owned, never edited by customers
└── custom/
    ├── org/               ← company-wide (e.g. all of ACME Corp)
    │   ├── naming-conventions.md
    │   └── security-policies.md
    ├── team/              ← this team only (e.g. Network Automation)
    │   └── task-id-format.md
    └── dev/               ← this individual developer only
        └── scratch-overrides.md
```

Any of `org/`, `team/`, `dev/` may be empty or absent. Each may contain zero, one, or several `.md` files — split by topic/owner as the layer grows, rather than forcing everything into one file.

## Precedence

When multiple layers speak to the same rule, **more specific wins**: `dev` overrides `team` overrides `org` overrides the foundational skill. Non-conflicting additions from every layer that exists still apply — this is layering, not replacement.

Files within the same layer should not conflict with each other. If they do, that's an authoring error in that layer to fix directly, not something to resolve by guessing which one "wins."

## Where does a given customization belong?

The organizing question isn't "how specific is this" — it's **who needs to agree to it, or be aware of it, for it to be safe.** Match the blast radius of the change to the layer:

| Ask yourself... | If yes → | Why |
|---|---|---|
| Is this a fact about *my* environment (a sandbox URL, a personal cluster ID, my own test device, a secret path only I use) — not an opinion about how things should be done? | `dev/` | Nobody else needs to agree to this; it's a config detail that happens to differ per person, not a convention. |
| Is this something I want to try before I know if it works, with real intent to promote or delete it soon? | `dev/`, temporary | Team/org shouldn't be affected by something unproven. This should have an expiration, not live here forever. |
| Does this apply to everyone on my team, and would a teammate be confused if they didn't know about it? | `team/` | The blast radius is "my team" — the review bar is "my team agrees," not "I decided alone." |
| Does this represent a company-wide policy (security, compliance, branding) — or would it be actively wrong for one team to do differently from another? | `org/` | The blast radius is everyone; silent divergence per team has organization-level consequences. |

**Examples:**
- "My sandbox IAG cluster is `cluster_dev_ankit`" → `dev/` — a config fact, mine alone
- "Let me try requiring a ticket number in every task description before proposing it to the team" → `dev/`, temporary
- "Our team always names workflows `NETAUTO_<usecase>`" → `team/` — everyone on the team needs to follow it
- "No workflow may ever call `runAutoRemediation`" → `org/` — a policy line, wrong for even one team to cross

### A caution on `dev/`

`dev/` is for environment/config differences and temporary drafts pending promotion — **not** a general-purpose personal override of team or org conventions. If you find yourself permanently overriding a `team/`-level rule in your own `dev/` file because you personally disagree with it, that override belongs in a conversation with your team (and, if adopted, in `team/`), not in an unreviewed file only you ever see. A `dev/` layer used that way quietly recreates the exact fragmentation problem this whole structure exists to prevent — just scoped to one person instead of the whole org.

## Writing an override — required format

Every override (not addition) must state what it's replacing and why, so it stays auditable as layers accumulate:

```markdown
## OVERRIDE: task ID format
Original rule: "Task IDs are hex-only [0-9a-f]{1,4}"
Replacement: Task IDs must start with a letter a-f, not a digit — our
ticket-numbering scheme is purely numeric, and we don't want task IDs
that look like ticket numbers. Valid: `a1b2`. Invalid: `1a2b`.
```

Pure additions don't need this format — just state the new rule under an `## ADD:` heading.

## Why customer content never lives in the foundational repo's tracked history

`.claude/skills/*/custom/**` is gitignored in this repo (see `.gitignore`) except for placeholder files. Itential's own commits never contain real content under a `custom/` path, so pulling an upstream update can never conflict with or overwrite a customer's override — there's nothing there to conflict with.

If your team wants your own `org/`/`team/` files version-controlled and shared (e.g. across a fork), track them in your own fork and protect the path with a merge strategy so future upstream pulls can't touch them even by accident:

```
# .gitattributes, in your fork
.claude/skills/*/custom/** merge=ours
```
```bash
git config merge.ours.driver true   # one-time, per clone
```
