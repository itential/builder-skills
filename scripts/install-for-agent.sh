#!/usr/bin/env bash
set -euo pipefail

REPO="itential/builder-skills"   # override with --repo for your own copy
AGENTS=(github-copilot claude-code cursor codex)

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") [agent] [scope] [--update] [--version <ref>] [--repo <owner/repo>]

  agent      github-copilot | claude-code | cursor | codex (prompts if omitted)
  scope      project (default) | user
  --update   force re-fetch even if already installed (same as re-running install)
  --version  pin to a tag or commit SHA instead of latest (e.g. v2.0.0)
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

# gh skill takes a version via --pin (a tag or commit SHA), not owner/repo@version.
pin=()
[[ -n "${version}" ]] && pin=(--pin "${version}")

action="Installing"
$update && action="Updating"
echo "${action} all ${REPO} skills for --agent ${agent} --scope ${scope}..."

start=$(date +%s.%N)
if $update; then
  gh skill install "${REPO}" --agent "${agent}" --scope "${scope}" --all --force ${pin[@]+"${pin[@]}"}
else
  gh skill install "${REPO}" --agent "${agent}" --scope "${scope}" --all ${pin[@]+"${pin[@]}"}
fi
end=$(date +%s.%N)

elapsed=$(python3 -c "print(f'{${end} - ${start}:.2f}')")
echo "Done. ${action%ing}ed for ${agent} (scope: ${scope}) in ${elapsed}s."
