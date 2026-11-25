#!/usr/bin/env bash
set -euo pipefail

REPO="itential/builder-skills"   # override with --repo for your own copy
# A copy that must only ever install a reviewed version sets this to true (or users pass
# --require-pin, or set ITENTIAL_SKILLS_REQUIRE_PIN=true): installs then need --version.
REQUIRE_PIN="${ITENTIAL_SKILLS_REQUIRE_PIN:-false}"
AGENTS=(github-copilot claude-code cursor codex)

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") [agent] [scope] [--update] [--version <ref>] [--require-pin] [--repo <owner/repo>]

  agent      github-copilot | claude-code | cursor | codex (prompts if omitted)
  scope      project (default) | user
  --update   force re-fetch even if already installed (same as re-running install)
  --version  pin to a tag or commit SHA instead of latest (e.g. v2.0.0)
  --require-pin  refuse to install without --version (also: ITENTIAL_SKILLS_REQUIRE_PIN=true)
  --repo     install from your own copy instead (e.g. acme/builder-skills)
EOF
  exit 1
}

update=false
version=""
positional=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --update|-u) update=true; shift ;;
    --version) version="$2"; shift 2 ;;
    --require-pin) REQUIRE_PIN=true; shift ;;
    --repo) REPO="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) positional+=("$1"); shift ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh (GitHub CLI) is required. Install: https://cli.github.com/" >&2
  exit 1
fi

if ! gh skill --help >/dev/null 2>&1; then
  echo "ERROR: your gh version does not support 'gh skill'. Update gh: https://cli.github.com/" >&2
  echo "Current version: $(gh --version | head -1)" >&2
  exit 1
fi

agent="${positional[0]:-}"
if [[ -z "${agent}" ]]; then
  echo "Select an agent:"
  select agent in "${AGENTS[@]}"; do
    [[ -n "${agent:-}" ]] && break
  done
fi

scope="${positional[1]:-project}"

# What will be installed: the pinned ref, or what gh skill picks without one (the latest
# tagged release, else the default branch HEAD). Resolved to a commit so it can be recorded.
latest_release() { gh release view --repo "${REPO}" --json tagName --jq .tagName 2>/dev/null || true; }
if [[ -z "${version}" ]]; then
  if [[ "${REQUIRE_PIN}" == "true" ]]; then
    latest="$(latest_release)"
    echo "ERROR: this install requires a pinned version. Add --version <tag or commit SHA>${latest:+ (latest release: ${latest})}." >&2
    exit 1
  fi
  ref="$(latest_release)"
  ref="${ref:-$(gh api "repos/${REPO}" --jq .default_branch)}"
else
  ref="${version}"
fi
if ! commit="$(gh api "repos/${REPO}/commits/${ref}" --jq .sha 2>/dev/null)"; then
  echo "ERROR: ${REPO} has no tag, branch or commit '${ref}'." >&2
  exit 1
fi

# gh skill takes a version via --pin (a tag or commit SHA), not owner/repo@version.
pin=()
[[ -n "${version}" ]] && pin=(--pin "${version}")

action="Installing"
$update && action="Updating"
echo "${action} all ${REPO} skills (${ref}, commit ${commit:0:12}) for --agent ${agent} --scope ${scope}..."

start=$(date +%s.%N)
if $update; then
  gh skill install "${REPO}" --agent "${agent}" --scope "${scope}" --all --force ${pin[@]+"${pin[@]}"}
else
  gh skill install "${REPO}" --agent "${agent}" --scope "${scope}" --all ${pin[@]+"${pin[@]}"}
fi
end=$(date +%s.%N)

elapsed=$(python3 -c "print(f'{${end} - ${start}:.2f}')")
echo "Done. ${action%ing}ed for ${agent} (scope: ${scope}) in ${elapsed}s."
echo "Installed ${REPO} ${ref} = commit ${commit}. Record this to show exactly what was installed."
