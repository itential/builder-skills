# Contributing to builder-skills

Thank you for your interest in contributing to the builder-skills project! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Contributor License Agreement](#contributor-license-agreement)
- [Development Setup](#development-setup)
- [Contributing Process](#contributing-process)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Pull Request Labels](#pull-request-labels)
- [Testing](#testing)
- [Code Style](#code-style)
- [Documentation](#documentation)
- [Getting Help](#getting-help)

## Code of Conduct

By participating in this project, you are expected to uphold our Code of Conduct. Please report unacceptable behavior to [opensource@itential.com](mailto:opensource@itential.com).

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Set up the development environment**
4. **Create a feature branch** for your changes
5. **Make your changes** and test them
6. **Submit a pull request**

## Contributor License Agreement

**All contributors must sign a Contributor License Agreement (CLA) before their contributions can be merged.** 

The CLA ensures that:
- You have the right to contribute the code
- Itential has the necessary rights to use and distribute your contributions
- The project remains legally compliant

When you submit your first pull request, you will be prompted to sign the CLA. Please complete this process before your contribution can be reviewed.

## Development Setup

<!--
MAINTAINER: Replace the Prerequisites and Setup Instructions sections below
with project-specific requirements and commands for your tech stack.
-->

### Prerequisites

<!-- List your project's prerequisites here. Examples:
- Python 3.10+ with uv package manager
- Node.js 18+ with npm/yarn
- Go 1.21+
- Rust 1.70+ with cargo
-->

- Git

### Setup Instructions

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YOUR-USERNAME/builder-skills.git
   cd builder-skills
   ```

2. **Add the upstream remote:**
   ```bash
   git remote add upstream https://github.com/itential/builder-skills.git
   ```

3. **Set up the development environment:**
   ```bash
   # Add your setup commands here
   # Examples:
   # - Python: uv sync --all-extras --dev
   # - Node.js: npm install
   # - Go: go mod download
   # - Rust: cargo build
   ```

4. **Verify the setup:**
   ```bash
   # Add your verification commands here
   # Examples:
   # - Python: make test && make lint
   # - Node.js: npm test && npm run lint
   # - Go: go test ./... && golangci-lint run
   # - Rust: cargo test && cargo clippy
   ```

## Contributing Process

### Fork and Pull Model

This project uses a fork and pull request model for contributions:

1. **Fork the repository** to your GitHub account
2. **Create a topic branch** from `main`:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes** in logical, atomic commits — every commit message must follow the [Commit Message Format](#commit-message-format) below; CI will reject the PR otherwise
4. **Test your changes** thoroughly
5. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a pull request** against the `main` branch

### Branch Naming Conventions

Branch names are validated by CI against this regex:

```
^(feature|fix|refactor|docs|chore)/[a-z][a-z0-9-]*$
```

Format: `<type>/<description>` where:

| Field | Rule |
|---|---|
| Type | One of `feature`, `fix`, `refactor`, `docs`, `chore` |
| Description | Lowercase letters, numbers, and hyphens only; must start with a letter |

Type meanings:
- `feature/` — new features
- `fix/` — bug fixes
- `refactor/` — code restructuring without changing behavior
- `chore/` — maintenance tasks (dependencies, tooling, build)
- `docs/` — documentation updates

**Read this before picking `docs/` for a skill-content change.** In most repos, "it's a `.md` file" and "it's documentation" mean the same thing. They don't here. `AGENTS.md` and every `.claude/skills/*/SKILL.md` file are this repo's **code** — Claude reads them and they directly determine what actions an agent takes. There is no separate interpreter or compiled artifact standing between this prose and agent behavior; the wording *is* the behavior spec. This is not a theoretical distinction — a wording change to one of these files has been directly measured (via fresh sub-agent runs, before/after) to change which API endpoint an agent calls and whether it independently verifies a risky path. That is a behavior change, full stop, regardless of the file extension.

So classify skill-content changes (`AGENTS.md`, any `.claude/skills/*/SKILL.md`) by **behavior impact**, not file type:
- **`feature/`** — adds a capability or default pattern the agent didn't have before
- **`fix/`** — corrects wrong, incomplete, or misleading guidance that was producing (or could produce) wrong agent behavior — including "the explanation was technically inaccurate" even if no one filed a bug about it
- **`refactor/`** — restructures how guidance is organized/worded with the underlying instruction genuinely unchanged (reordering, consolidating duplicates, renumbering) — the bar is that a behavioral eval run before and after would show no difference
- **`docs/`** — reserve this for files that are *actually* documentation with no direct behavioral role: `README.md`, this file, issue/PR templates, comments. If you're touching `AGENTS.md` or a `SKILL.md` and the change could plausibly alter what an agent does in some situation, it is not `docs/`, even if it's phrased as "just consolidating duplicate content" — verify that claim (e.g., confirm every deleted line's content still exists verbatim at its pointer target) before defaulting to `docs/`.

Examples:
- `feature/add-authentication-support`
- `fix/handle-connection-timeout`
- `refactor/extract-token-helper`
- `chore/update-dependencies`
- `docs/improve-api-examples`

### Commit Message Format

Every commit on a PR is validated by CI against the [Conventional Commits](https://www.conventionalcommits.org/) regex:

```
^(feat|fix|docs|style|refactor|test|chore|perf)(\(.+\))?: .{1,72}
```

Format: `<type>[(scope)]: <description>` where:

| Field | Rule |
|---|---|
| Type | One of `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf` |
| Scope | *(Optional)* parenthesized, e.g. `(builder-agent)` |
| Description | 1–72 characters |

> **Note** — the commit type list is **different from the branch type list**. Branches use `feature/` (full word); commits use `feat:` (Conventional Commits short form). Branches don't have `style`, `test`, or `perf`.

Type meanings (commit-side):
- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation only
- `style` — formatting, whitespace, missing semicolons (no code logic change)
- `refactor` — code restructuring without behavior change
- `test` — adding or fixing tests
- `chore` — build process, tooling, dependencies
- `perf` — performance improvements

**Merge commits are not allowed** on PR branches — the CI rejects them. Use squash or rebase to integrate updates from `main`.

**`git revert`'s default message never conforms** — it produces `Revert "<original message>"`, and `Revert` isn't a valid type. Reword it before pushing:

```bash
git revert --no-edit <sha>
git commit --amend -m "fix: revert <what and why>"
```

If reverting multiple commits, squash them into a single properly-typed commit instead of leaving several auto-generated `Revert "..."` messages:

```bash
git reset --soft <sha-before-the-commits-being-reverted>
git commit -m "fix: revert <what and why>"
```

Examples:
- `feat(auth): add JWT token validation`
- `fix: handle empty response from upstream`
- `docs(contributing): document commit and branch CI rules`
- `chore: bump dependency versions`

## Pull Request Guidelines

### Before Submitting

- [ ] Ensure your branch is up to date with `main`
- [ ] Run the full test suite: `make test`
- [ ] Run code quality checks: `make lint`
- [ ] Add tests for new functionality
- [ ] Update documentation if needed
- [ ] Sign the Contributor License Agreement (CLA)

### Pull Request Description

Your pull request should include:

1. **Clear title** describing the change
2. **Detailed description** explaining:
   - What the change does
   - Why the change is needed
   - How it was tested
3. **References to related issues** (if applicable)
4. **Breaking changes** (if any)

### Example Pull Request Template

```markdown
## Summary
Brief description of what this PR does.

## Changes
- List of specific changes made
- Another change

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Related Issues
Closes #123
```

## Pull Request Labels and Versioning

There are **two separate, deliberately decoupled version concepts** in this repo — don't assume they track each other.

**1. The plugin manifest version** (`.claude-plugin/plugin.json` / `marketplace.json`) — what Claude Code's `/plugin update` reads. `.github/workflows/version-bump.yml` bumps this by exactly **+0.0.1 on every single merge to `main`, no exceptions.** It does not look at labels, branch prefix, or PR content — every merge is a patch release of the manifest, whether it's a one-line typo fix or a new skill. This is intentionally dumb: no categorization logic to get wrong, no label to forget, no ambiguity about whether something "counts." If a change is significant enough to deserve a minor/major bump to the manifest, bump it by hand in that PR instead of relying on this workflow — it will only ever add 0.0.1.

**2. The GitHub Release version** — [Release Drafter](https://github.com/release-drafter/release-drafter) (`.github/release-drafter.yml`) maintains a draft release with computed notes and a *suggested* next semver tag, based on PR labels. This is the "real," human-meaningful version number for release notes; publishing the draft (and its tag) is still a manual, deliberate step, independent of the manifest bumping above.

**Labels are applied automatically from your branch name** by `.github/workflows/pr-labeler.yml` — you don't need to apply them yourself for the common cases. They only affect Release Drafter's changelog/tag suggestion (concept 2) — they have **no effect on the manifest version** (concept 1) anymore:

| Branch prefix | Label(s) applied | Release Drafter category |
|---|---|---|
| `feature/` | `feature` | minor |
| `fix/` | `fix` | patch |
| `refactor/` | `refactor` | patch |
| `docs/` | `documentation`, `skip-changelog` | excluded from release notes |
| `chore/` | `chore`, `skip-changelog` | excluded from release notes |

**Major version bumps for the GitHub Release are never inferred automatically** — apply the `breaking-change` label yourself when a change would break an existing consumer's setup. For this repo that means things like renaming or removing a skill, changing a script's CLI (`scripts/platform_pull.py`, `scripts/use_case_init.py`), or changing the `custom/org/team/dev` customization-layer contract. Clarifying/correcting existing skill guidance is usually `fix`, not breaking — see the behavior-impact test above for the `fix` vs. `refactor` vs. `docs` line.

**Expect the two version numbers to drift, and that's fine.** The manifest might read `1.9.3` (nine patch-bump merges) while Release Drafter's draft suggests the next real release should be `v2.0.0` (one of those merges was labeled `feature`) — the manifest number is just an ever-incrementing "something changed" counter for Claude Code's update mechanism, not a semver-meaningful release identity.

**How `version-bump.yml` actually lands its change:** it opens its own PR (branch `chore/bump-version-to-X-Y-Z`) rather than pushing to `main` directly — a direct push was tried first and rejected (`GH006`: unsigned commits, no PR, and required status checks that never ran on a bare push), and no branch-protection bypass fixes that, since a raw push can never satisfy "status checks must run on a pull request." Going through a PR means it gets reviewed and merged exactly like everything else, and GitHub signs the resulting squash-merge itself.

**Recommended (not required) for the version-bump workflow:** set a repo secret `VERSION_BUMP_TOKEN` to a fine-grained PAT with `contents`/`pull-requests` write on this repo. Without it, the workflow falls back to the default `GITHUB_TOKEN`, which works but won't trigger `pr-compliance.yml`/`pr-labeler.yml` on the PR it opens (GitHub deliberately blocks `GITHUB_TOKEN`-authored events from triggering other workflows) — its required status checks will show as permanently pending until someone pushes a trivial commit to nudge them, same workaround used elsewhere in this repo for out-of-date branches. See the comment at the top of `version-bump.yml`.

## Changelog

`CHANGELOG.md` is hand-maintained, not auto-generated — nothing in CI writes to it. Format follows Claude Code's own `CHANGELOG.md`: a flat bullet list under each version heading, no subsections, no dates — each bullet leads with `Added`/`Fixed`/`Changed`/`Improved`/`Removed` inline. If your PR is user-facing (a new or changed skill, a fixed bug, a behavior change), add a bullet under `## Unreleased` in that style. Skip it for anything that would carry the `skip-changelog` label (docs, chore) — same exclusion Release Drafter already applies.

Periodically, a maintainer renames `Unreleased` to whatever the current manifest version happens to be, and adds a new empty `Unreleased` heading above it — this is a manual snapshot, not tied to any single merge (the manifest version bumps on every merge, so a 1:1 mapping would defeat the point of batching entries).

## Testing

<!--
MAINTAINER: Replace this section with project-specific testing instructions.
Examples for common tech stacks are provided as comments.
-->

### Running Tests

```bash
# Add your test commands here
# Examples:
# - Python: make test, pytest, uv run pytest
# - JavaScript: npm test, yarn test
# - Go: go test ./..., make test
# - Rust: cargo test
```

### Test Coverage

```bash
# Add your coverage commands here
# Examples:
# - Python: make coverage, pytest --cov
# - JavaScript: npm run coverage, nyc npm test
# - Go: go test -cover ./...
# - Rust: cargo tarpaulin
```

### Writing Tests

- Place tests in the appropriate directory for your language/framework
- Use descriptive test names that explain the expected behavior
- Include both positive and negative test cases
- Mock external dependencies appropriately
- Aim for meaningful coverage of critical paths

<!--
MAINTAINER: Add project-specific test structure and conventions here.
Example: "Place tests in `tests/` directory mirroring `src/` structure"
-->

## Code Style

<!--
MAINTAINER: Replace this section with project-specific code style guidelines.
Examples for common tech stacks are provided as comments.
-->

### Code Quality Commands

```bash
# Add your linting/formatting commands here
# Examples:
# - Python: make lint, ruff check ., black --check .
# - JavaScript: npm run lint, eslint ., prettier --check .
# - Go: golangci-lint run, go fmt ./...
# - Rust: cargo clippy, cargo fmt --check
```

### Style Guidelines

<!--
MAINTAINER: Add your project's style guidelines here. Examples:

Python:
- Follow PEP 8 conventions
- Use type hints for all function parameters and return values
- Keep line length to 88 characters (Black default)

JavaScript/TypeScript:
- Follow ESLint recommended rules
- Use TypeScript strict mode
- Prefer const over let, avoid var

Go:
- Follow Effective Go guidelines
- Use gofmt for formatting
- Keep functions focused and small

Rust:
- Follow Rust API Guidelines
- Use clippy lints
- Prefer Result over panics
-->

- Use meaningful variable and function names
- Keep functions focused and single-purpose
- Write self-documenting code where possible

### Documentation Standards

- Document public APIs and exported functions
- Include usage examples for complex functionality
- Keep documentation up-to-date with code changes

<!--
MAINTAINER: Add project-specific documentation conventions here.
Example: "Use Google-style docstrings with Args, Returns, and Raises sections"
-->

## Documentation

### Types of Documentation

1. **Code documentation** - Docstrings and inline comments
2. **API documentation** - Tool descriptions and examples
3. **User documentation** - README and usage guides
4. **Developer documentation** - This CONTRIBUTING.md and AGENTS.md

### Documentation Updates

- Update docstrings when changing function signatures
- Add examples for new tools and features
- Update README.md for user-facing changes
- Maintain the AGENTS.md file for development guidelines

## Getting Help

### Resources

- **Documentation**: Check the README.md and AGENTS.md files
- **Issues**: Search existing issues for similar problems
- **Discussions**: Use GitHub Discussions for questions
- **Maintainer**: [@keepithuman](https://github.com/keepithuman)

### Reporting Issues

When reporting issues, please include:

1. **Clear description** of the problem
2. **Steps to reproduce** the issue
3. **Expected vs actual behavior**
4. **Environment information** (runtime version, OS, etc.)
5. **Error messages** and stack traces (if applicable)

### Asking Questions

- Use GitHub Discussions for general questions
- Search existing discussions and issues first
- Provide context and specific details
- Be patient and respectful

## Recognition

Contributors who have their pull requests merged will be:
- Listed in the project's contributors
- Mentioned in release notes (when appropriate)
- Recognized in the project documentation

Thank you for contributing to builder-skills!

---

For questions about contributing, please contact [opensource@itential.com](mailto:opensource@itential.com).