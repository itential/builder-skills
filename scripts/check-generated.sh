#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/scripts/generate-vendor-wrappers.sh" >/dev/null
"${ROOT_DIR}/scripts/check-vendor-skills.sh" >/dev/null

if [[ -n "$(git -C "${ROOT_DIR}" status --porcelain -- ".claude/skills" ".agents/skills" ".github/skills")" ]]; then
  echo "Generated mirrors are stale or untracked:" >&2
  git -C "${ROOT_DIR}" status --short -- ".claude/skills" ".agents/skills" ".github/skills" >&2
  exit 1
fi

echo ".claude/skills, .agents/skills, .github/skills are up to date."
