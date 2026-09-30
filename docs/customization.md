# Customizing the Skills for Your Org

Every skill is owned and updated by Itential — don't edit a skill's `SKILL.md`, your changes would be overwritten by the next update. Instead, each skill has a `custom/` folder for your org's rules. The skill reads that folder every time it runs, and applies your rules on top of its own.

You write plain markdown files. A pipeline that ships with the repo takes care of getting them to every AI tool — nobody runs a script.

## At a glance

| Who | When | What |
|---|---|---|
| One admin | Once | [Set up your org's copy](#1-set-up-your-orgs-copy-once) |
| Anyone adding a rule | Whenever | [Add a rule](#2-add-a-rule) — write a file, push, check |
| Everyone on the team | Once | [Install from your copy](#3-everyone-installs-from-your-copy) |
| One admin | When Itential releases | [Take Itential's updates](#5-take-itentials-updates) |

---

## 1. Set up your org's copy (once)

Make a **private** copy — not GitHub's Fork button, because a fork of a public repo can't be made private:

```bash
gh repo create acme/builder-skills --private
git clone --bare https://github.com/itential/builder-skills.git
cd builder-skills.git && git push --mirror https://github.com/acme/builder-skills.git
cd .. && rm -rf builder-skills.git
```

(Or use GitHub's **Import repository** page with `https://github.com/itential/builder-skills`.)

Then, in the new repo on GitHub:
- **Actions tab** — if you see a banner saying workflows are disabled, enable them. This is what turns your files into each tool's format.
- **If you protect `main`** (require PRs): **Settings → Actions → General → Workflow permissions → tick "Allow GitHub Actions to create and approve pull requests"**. Without it, the pipeline can't open its update PR. If `main` isn't protected, skip this.

Itential's own maintenance workflows (version bumps, release notes) switch themselves off in your copy — only the customization pipeline runs.

---

## 2. Add a rule

### Decide where it goes

**Which skill?** Put the file in the folder of the skill that should follow it — `skills/builder-agent/custom/…` for how things get built, `skills/solution-arch-agent/custom/…` for how solutions get designed, and so on. If a rule applies to several stages (e.g. a design standard that design, build, and QA should all honor), put a copy in each of those skills.

**Which layer?** Match it to who needs to agree:

| If the rule is… | Put it in | Example |
|---|---|---|
| Company policy — wrong for any team to do differently | `org/` | "No workflow may ever call `runAutoRemediation`" |
| A convention your team agreed on | `team/` | "Our team names workflows `NETAUTO_<usecase>`" |
| Just yours — your sandbox, your test device, an experiment | `dev/` — see [Personal settings](#personal-settings-dev) | "My sandbox IAG cluster is `cluster_dev_ankit`" |

### Write it

One or more `.md` files per folder, any names. Use `## ADD:` for a new rule. To replace one of the skill's own rules, use `## OVERRIDE:` and say what you're replacing and why, so it stays reviewable:

```markdown
## ADD: workflow naming
All workflows must be prefixed ACME_.

## OVERRIDE: task ID format
Original rule: "Task IDs are hex-only [0-9a-f]{1,4}"
Replacement: Task IDs must start with a letter a-f, not a digit — our ticket
numbers are numeric and we don't want task IDs that look like them.
```

### Push it and check

```bash
git clone https://github.com/acme/builder-skills.git && cd builder-skills   # first time only
# create skills/builder-agent/custom/org/naming.md
git add skills/builder-agent/custom/org/naming.md
git commit -m "org: ACME workflow naming"
git push
```

The GitHub web editor works just as well. Then check the **Actions** tab — within a minute you should see:
- a green **Generate Vendor Mirrors** run, and
- a new commit on `main` by `github-actions[bot]`: `chore: regenerate vendor mirrors`.

If `main` is protected, you'll get a PR with that title instead — merge it. That's the rule delivered.

---

## 3. Everyone installs from your copy

Team members follow [`vendor-install.md`](vendor-install.md) for their tool, using `acme/builder-skills` in place of `itential/builder-skills`. Already installed Itential's version? See [Switching to your own copy](vendor-install.md#switching-to-your-own-copy).

After a new rule is added, people pick it up with their tool's normal update (or `git pull` if they work from a clone).

---

## 4. Check the agent is using it

Run the skill and ask it directly — for example, start `/builder-agent` and ask *"Which customization files are you applying?"* It should list your file. If it doesn't, see [Troubleshooting](#troubleshooting).

---

## 5. Take Itential's updates

When Itential publishes a release (**Watch → Custom → Releases** on `itential/builder-skills` to get notified), pull it into your copy the way your team normally syncs from upstream — for example:

```bash
git remote add upstream https://github.com/itential/builder-skills.git   # once
git pull upstream main
git push
```

That's it: the push re-runs the pipeline, and your `custom/` files come through untouched. They can't conflict — Itential never puts anything in `custom/` folders (a check in Itential's repo blocks it). Then let the team know to update their installs.

---

## Personal settings (`dev/`)

`dev/` files are personal, so they're **gitignored** — they never get committed to your org's copy by accident. Where to keep them depends on how you work:

- **Working from a clone:** put them in `skills/<name>/custom/dev/`, then run `scripts/generate-vendor-wrappers.sh` once locally so your tool sees them. This is the one case where you run the script yourself — it's only needed for files that never leave your machine.
- **Installed as a plugin:** there's no local copy to put them in. Use your tool's own personal instructions instead — e.g. `~/.claude/CLAUDE.md` (Claude Code) or `~/.codex/AGENTS.md` (Codex).

Keep `dev/` for facts about your environment and short-lived experiments. If you find yourself permanently overriding a team rule there, raise it with the team instead — that's what `team/` is for.

---

## Reference

### Folder layout

```
skills/<skill-name>/
├── SKILL.md          ← Itential's — never edit
└── custom/
    ├── org/          ← company-wide, committed
    ├── team/         ← your team, committed
    └── dev/          ← personal, gitignored
```

Always edit under `skills/`. The copies under `.claude/skills/`, `.agents/skills/`, `.github/skills/` are generated by the pipeline — edits there get overwritten.

### Which rule wins

More specific wins: `dev` over `team` over `org` over the skill's own defaults. Rules that don't conflict all apply together. Two files in the same layer shouldn't contradict each other — if they do, fix the files.

The repo also has a repo-wide `customizations/` folder, used by Itential's internal team; see `AGENTS.md` → Customization Layers for how it combines with the per-skill folders.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No **Generate Vendor Mirrors** run after pushing | Actions disabled in your copy | Actions tab → enable workflows, then push again or use **Run workflow** |
| Run failed: "not permitted to create or approve pull requests" | `main` is protected and Actions can't open PRs | Tick the setting in [step 1](#1-set-up-your-orgs-copy-once), then re-run — or open the PR from the link in the log |
| Agent doesn't mention your file | File not under `skills/<name>/custom/`, or your install is older than the rule | Check the path, then update your install (or `git pull`) |
| A teammate sees your `dev/` rule | It was committed with `git add -f` | `git rm --cached` it and push |
