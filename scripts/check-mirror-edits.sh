#!/usr/bin/env bash
set -euo pipefail

# Fails a PR that edits generated files by hand: the per-harness copies
# (.claude/skills, .agents/skills, .github/skills) and the bundled skills/*/assets. Those are rebuilt from skills/ by
# .github/workflows/generate-mirrors.yml after merge, so a direct edit there would
# be silently overwritten. A PR that only changes skills/ passes -- the pipeline
# regenerates the copies. A PR that touches the copies passes only if they match
# what skills/ generates (e.g. a contributor ran the generator locally).
#
# Usage: scripts/check-mirror-edits.sh <base-ref>   (e.g. origin/main)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
BASE="${1:?usage: $0 <base-ref>}"
MIRRORS=(.claude/skills .agents/skills .github/skills ':(glob)skills/*/assets')

touched="$(git diff --name-only "${BASE}...HEAD" -- "${MIRRORS[@]}")"
if [[ -z "${touched}" ]]; then
  echo "PR doesn't touch the generated copies."
  exit 0
fi

"${ROOT_DIR}/scripts/generate-vendor-wrappers.sh" >/dev/null
stale="$(git status --porcelain -- "${MIRRORS[@]}")"
if [[ -n "${stale}" ]]; then
  echo "ERROR: this PR edits generated copies that don't match skills/:" >&2
  echo "${stale}" >&2
  echo >&2
  echo "Edit skills/<name>/ (or the shared library: helpers/, spec-files/, environments/," >&2
  echo "AGENTS.md) instead -- the copies and skills/*/assets are rebuilt from those after" >&2
  echo "merge, so direct edits there would be overwritten." >&2
  exit 1
fi
echo "Generated copies in this PR match skills/."
