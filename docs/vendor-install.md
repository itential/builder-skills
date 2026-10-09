# Install, Run, and Update — per Tool

Find your tool below. Each section is self-contained: install, check it worked, run your first skill, update later.

Every install path gets the **complete** skills: each skill carries its own templates, spec library and reference files inside its folder, so nothing depends on a clone or on which tool you use.

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

<details><summary>Working from a clone?</summary>

`git clone https://github.com/itential/builder-skills.git`, then start Claude Code with the clone loaded as a plugin: `claude --plugin-dir /path/to/builder-skills` (from inside the clone, `claude --plugin-dir .`). Same shortcuts (`/itential-builder:spec-agent`). Update with `git pull`.
</details>

---

## Codex CLI

**Install** — in a terminal:
```bash
codex plugin marketplace add itential/builder-skills
codex plugin add itential-builder@itential-builder
```

**Check it worked:** start `codex` and type `/skills` — the Itential skills are listed as `itential-builder:<skill>`.

**Run a skill:**
```text
$itential-builder:spec-agent
```
Or pick it from `/skills`, or just describe the task and Codex picks the skill.

**Update:**
```bash
codex plugin marketplace upgrade itential-builder
codex plugin add itential-builder@itential-builder
```
Both steps are needed — the first fetches the new version, the second installs it.

**Remove:** `codex plugin remove itential-builder@itential-builder`, then `codex plugin marketplace remove itential-builder`.

<details><summary>Working from a clone?</summary>

`git clone https://github.com/itential/builder-skills.git`, then use the clone as the marketplace: `codex plugin marketplace add /path/to/builder-skills` and `codex plugin add itential-builder@itential-builder`. After `git pull`, re-run the `plugin add` to pick up changes.
</details>

---

## GitHub Copilot in VS Code

**Install — option A, as a plugin** (no clone needed): open the Command Palette (⇧⌘P / Ctrl+Shift+P), run **Chat: Install Plugin From Source**, and enter:
```text
itential/builder-skills
```
VS Code reads the repo's `plugin.json`. Agent plugins are on by default (setting `chat.plugins.enabled`).

**Install — option B, from a clone:** `git clone https://github.com/itential/builder-skills.git`, then **Chat: Install Plugin From Source** with the clone's path as a `file:///` URI (e.g. `file:///Users/you/builder-skills`).

**Check it worked:** in Copilot Chat, type `/` — `spec-agent` and the other skills appear. Plugin installs also show under **Configure Skills**.

**Run a skill:** `/spec-agent`, or describe the task and Copilot picks the skill.

**Update:** option A → VS Code checks for plugin updates every 24 hours (when `extensions.autoUpdate` is on); to update now, run **Extensions: Check for Extension Updates**. Option B → `git pull`.

**Remove:** right-click the plugin in the **Agent Plugins - Installed** view → **Uninstall**.

> Using VS Code with the **Claude Code** or **Codex** extension instead of Copilot? Follow the [Claude Code](#claude-code) or [Codex CLI](#codex-cli) section — the extension uses the same install and commands.

---

## GitHub Copilot CLI

**Install** — in a terminal:
```bash
copilot plugin marketplace add itential/builder-skills
copilot plugin install itential-builder@itential-builder
```
(Copilot also accepts `copilot plugin install itential/builder-skills` directly, but warns that direct repo installs are deprecated — the marketplace form above is the supported one.)

**Check it worked:**
```bash
copilot plugin list      # shows itential-builder@itential-builder
copilot skill list       # the 17 skills appear
```

**Run a skill:** `/spec-agent`, or describe the task and Copilot picks the skill.

**Update:** `copilot plugin update itential-builder@itential-builder` (or `copilot plugin update` to update every plugin).

**Remove:** `copilot plugin uninstall itential-builder@itential-builder`.

<details><summary>Install into one project instead (gh skill)?</summary>

With GitHub CLI 2.90 or later (`gh skill --help` should work), from inside your project:
```bash
gh skill install itential/builder-skills --agent github-copilot --all
```
Skills land in the project's `.agents/skills/`. Update by re-running with `--force`; pin a release with `--pin v2.0.0`.
</details>

<details><summary>Working from a clone?</summary>

`git clone https://github.com/itential/builder-skills.git`, then `copilot plugin marketplace add /path/to/builder-skills` and `copilot plugin install itential-builder@itential-builder`. Copilot loads the skills live from the clone, so `git pull` (or your own edits) take effect in the next session.
</details>

---

## Cursor

**Install — option A, into your project** (GitHub CLI 2.90 or later):
```bash
gh skill install itential/builder-skills --agent cursor --all
```
Skills land in the project's `.agents/skills/`, which Cursor reads.

**Install — option B, from a clone:** `git clone https://github.com/itential/builder-skills.git`, then from your project: `gh skill install /path/to/builder-skills --from-local --agent cursor --all`.

**For a whole org — Team Marketplace:** a Cursor admin can add the repo under **Dashboard → Plugins & MCPs → Team Marketplaces → Import from Repo** (needs the Cursor GitHub App). The repo ships `.cursor-plugin/` for this. *(From Cursor's docs; not yet tried by hand.)*

**Check it worked:** in Cursor chat, type `/` — `spec-agent` and the other skills appear.

**Run a skill:** `/spec-agent`

**Update:** option A → re-run the install command with `--force`. Option B → `git pull`, then re-run the install with `--force`. Team Marketplace → refreshes from the repo.

---

## One script for any tool

`scripts/install-for-agent.sh` (from a clone of this repo) wraps `gh skill install` for any tool, so you don't have to remember per-tool commands. Needs GitHub CLI 2.90 or later.

```bash
scripts/install-for-agent.sh                                  # asks which tool
scripts/install-for-agent.sh cursor                           # install into this project
scripts/install-for-agent.sh cursor --update                  # update
scripts/install-for-agent.sh cursor --version v2.0.0          # pin a release (tag or commit SHA)
scripts/install-for-agent.sh cursor --repo acme/builder-skills # install from your org's copy
```

---

## Switching to your own copy

Once your org has a customized copy (see [`customization.md`](customization.md)), remove the Itential install and install from the copy:

| Tool | Remove Itential's, then install yours |
|---|---|
| Claude Code | `/plugin uninstall itential-builder@itential-builder`, `/plugin marketplace remove itential-builder`, then the install steps above with `acme/builder-skills` |
| Codex CLI | `codex plugin remove itential-builder@itential-builder`, `codex plugin marketplace remove itential-builder`, then the install steps above with `acme/builder-skills` |
| Copilot CLI | `copilot plugin uninstall itential-builder@itential-builder`, `copilot plugin marketplace remove itential-builder`, then the install steps above with `acme/builder-skills` |
| Copilot in VS Code (plugin) | Uninstall it from **Agent Plugins - Installed**, then **Chat: Install Plugin From Source** with `acme/builder-skills` |
| `gh skill` installs (Cursor, Copilot) | Re-run the install command with `acme/builder-skills` and `--force` |
| Any clone | `git remote set-url origin https://github.com/acme/builder-skills.git && git pull`, then reinstall from the clone as in your tool's "Working from a clone" note |

Nothing to migrate — your org's rules live in the copy, not on your machine.

---

## Quick reference

| Tool | Install | Run | Update |
|---|---|---|---|
| Claude Code | `/plugin install itential-builder@itential-builder` | `/itential-builder:spec-agent` | automatic, or `/plugin update itential-builder@itential-builder` |
| Codex CLI | `codex plugin add itential-builder@itential-builder` | `$itential-builder:spec-agent` | `codex plugin marketplace upgrade itential-builder` + `plugin add` |
| Copilot in VS Code | **Chat: Install Plugin From Source** → `itential/builder-skills` | `/spec-agent` | automatic, or **Extensions: Check for Extension Updates** |
| Copilot CLI | `copilot plugin install itential-builder@itential-builder` | `/spec-agent` | `copilot plugin update itential-builder@itential-builder` |
| Cursor | `gh skill install itential/builder-skills --agent cursor --all` | `/spec-agent` | same command + `--force` |

(Every plugin install first needs its marketplace added — see the tool's section.)

For maintainers: each `skills/<name>/assets/` is generated from the shared library by `scripts/check-generated.sh` — edit `skills/` and the library, then run it and commit the result. See [`multi-vendor-architecture.md`](multi-vendor-architecture.md).
