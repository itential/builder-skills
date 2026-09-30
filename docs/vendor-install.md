# Install, Run, and Update — per Tool

Find your tool below. Each section is self-contained: install, check it worked, run your first skill, update later.

**Which repo to install from?**
- Using the skills as Itential ships them → `itential/builder-skills` (what the commands below show).
- Your org has its own copy with customizations → use your copy's name instead (e.g. `acme/builder-skills`) in every command. Setting up a copy: [`customization.md`](customization.md).

Not sure yet? Start with Itential's. Moving to your own copy later is just a reinstall — see [Switching to your own copy](#switching-to-your-own-copy).

**Know when there's an update:** on GitHub, **Watch → Custom → Releases** on `itential/builder-skills`.

---

## Claude Code

**Install** — in Claude Code:
```text
/plugin marketplace add itential/builder-skills
/plugin install itential-builder@itential-builder
```
Or from a terminal: `claude plugin marketplace add itential/builder-skills && claude plugin install itential-builder@itential-builder`.

Restart Claude Code once it finishes.

**Check it worked:** run `/plugin` and look for `itential-builder` under installed plugins, or type `/itential-builder:` — the skills appear as suggestions.

**Run a skill:**
```text
/itential-builder:spec-agent
```

**Update:** Claude Code updates plugins in the background. To update now: `/plugin update itential-builder@itential-builder`, then restart.

<details><summary>Prefer working from a clone instead?</summary>

`git clone https://github.com/itential/builder-skills.git`, open Claude Code in that folder, and run `/spec-agent` (no prefix — skills load from `.claude/skills/`). Update with `git pull`.
</details>

---

## Codex CLI

**Install** — in a terminal:
```bash
codex plugin marketplace add itential/builder-skills
codex plugin add itential-builder@itential-builder
```

**Check it worked:** start `codex`, type `/skills` — the Itential skills are listed.

**Run a skill:**
```text
$spec-agent
```
Or pick from `/skills`, or just describe the task and Codex picks the skill.

**Update:**
```bash
codex plugin marketplace upgrade itential-builder
codex plugin add itential-builder@itential-builder
```
Both steps are needed — the first fetches the new version, the second installs it.

<details><summary>Prefer working from a clone instead?</summary>

`git clone https://github.com/itential/builder-skills.git`, run `codex` in that folder — skills load from `.agents/skills/`. Update with `git pull`.
</details>

---

## GitHub Copilot in VS Code

**Install — option A, as a plugin** (no clone needed): open the Command Palette (⇧⌘P / Ctrl+Shift+P), run **Chat: Install Plugin From Source**, and enter:
```text
itential/builder-skills
```
VS Code reads the repo's `plugin.json`. Agent plugins are on by default (setting `chat.plugins.enabled`).

**Install — option B, clone and open:**
```bash
git clone https://github.com/itential/builder-skills.git && code builder-skills
```
Copilot Chat reads skills straight from `.github/skills/` — no install step.

**Check it worked:** in Copilot Chat, type `/` — `spec-agent` and the other skills appear. Plugin installs also show under **Configure Skills**.

**Run a skill:** `/spec-agent`, or describe the task and Copilot picks the skill.

**Update:** option A → VS Code checks for plugin updates every 24 hours (when `extensions.autoUpdate` is on); to update now, run **Extensions: Check for Extension Updates**. Option B → `git pull`.

**Remove:** right-click the plugin in the **Agent Plugins - Installed** view → **Uninstall**.

> Using VS Code with the **Claude Code** or **Codex** extension instead of Copilot? Follow the [Claude Code](#claude-code) or [Codex CLI](#codex-cli) section — the extension uses the same install and commands.

---

## GitHub Copilot CLI

**Install** — in a terminal (needs a recent GitHub CLI; `gh skill --help` should work):
```bash
gh skill install itential/builder-skills --agent github-copilot --all
```

**Check it worked:**
```bash
copilot skill list
```
The Itential skills appear under project skills.

**Run a skill:** `/spec-agent`, or describe the task and Copilot picks the skill.

**Update:**
```bash
gh skill install itential/builder-skills --agent github-copilot --all --force
```

<details><summary>Prefer working from a clone instead?</summary>

`git clone https://github.com/itential/builder-skills.git` and open that folder — Copilot reads `.github/skills/` directly, no install step. Update with `git pull`.
</details>

---

## Cursor

Itential isn't listed in the Cursor marketplace, so use either option:

**Install — option A, clone** (simplest):
```bash
git clone https://github.com/itential/builder-skills.git
```
Open the folder in Cursor. Skills load from `.agents/skills/`.

**Install — option B, into an existing project** (needs a recent GitHub CLI):
```bash
gh skill install itential/builder-skills --agent cursor --all
```

**Check it worked:** in Cursor chat, type `/` — `spec-agent` and the other skills appear.

**Run a skill:** `/spec-agent`

**Update:** option A → `git pull`. Option B → re-run the install command with `--force`.

---

## One script for any tool

If you'd rather not remember per-tool commands, `scripts/install-for-agent.sh` (from a clone of this repo) wraps `gh skill install` for all of them:

```bash
scripts/install-for-agent.sh                                  # asks which tool
scripts/install-for-agent.sh codex                            # install
scripts/install-for-agent.sh codex --update                   # update
scripts/install-for-agent.sh codex --version v1.6.7           # pin a version
scripts/install-for-agent.sh codex --repo acme/builder-skills # install from your org's copy
```

---

## Switching to your own copy

Once your org has a customized copy (see [`customization.md`](customization.md)), remove the Itential install and install from the copy:

| Tool | Remove Itential's, then install yours |
|---|---|
| Claude Code | `/plugin uninstall itential-builder@itential-builder`, `/plugin marketplace remove itential-builder`, then the install steps above with `acme/builder-skills` |
| Codex CLI | `codex plugin marketplace remove itential-builder`, then the install steps above with `acme/builder-skills` |
| Copilot in VS Code (plugin) | Uninstall it from **Agent Plugins - Installed**, then **Chat: Install Plugin From Source** with `acme/builder-skills` |
| Copilot CLI / Cursor (`gh skill`) | Re-run the install command with `acme/builder-skills` and `--force` |
| Any clone | `git remote set-url origin https://github.com/acme/builder-skills.git && git pull` |

Nothing to migrate — your org's rules live in the copy, not on your machine.

---

## Quick reference

| Tool | Install | Run | Update |
|---|---|---|---|
| Claude Code | `/plugin install itential-builder@itential-builder` | `/itential-builder:spec-agent` | automatic, or `/plugin update itential-builder@itential-builder` |
| Codex CLI | `codex plugin add itential-builder@itential-builder` | `$spec-agent` | `codex plugin marketplace upgrade itential-builder` + `plugin add` |
| Copilot in VS Code | **Chat: Install Plugin From Source** → `itential/builder-skills` | `/spec-agent` | automatic, or **Extensions: Check for Extension Updates** |
| Copilot CLI | `gh skill install itential/builder-skills --agent github-copilot --all` | `/spec-agent` | same command + `--force` |
| Cursor | clone, or `gh skill install ... --agent cursor --all` | `/spec-agent` | `git pull`, or `--force` |

For maintainers: `.claude/skills/`, `.agents/skills/`, `.github/skills/` are generated from `skills/` by CI (`.github/workflows/generate-mirrors.yml`) — edit `skills/` only. See [`multi-vendor-architecture.md`](multi-vendor-architecture.md).
