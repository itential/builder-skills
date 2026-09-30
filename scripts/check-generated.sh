#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/scripts/generate-vendor-wrappers.sh" >/dev/null
"${ROOT_DIR}/scripts/check-vendor-skills.sh" >/dev/null

GENERATED=(.claude/skills .agents/skills .github/skills ':(glob)skills/*/assets')
if [[ -n "$(git -C "${ROOT_DIR}" status --porcelain -- "${GENERATED[@]}")" ]]; then
  echo "Generated files are stale or untracked:" >&2
  git -C "${ROOT_DIR}" status --short -- "${GENERATED[@]}" >&2
  exit 1
fi

echo "skills/*/assets, .claude/skills, .agents/skills, .github/skills are up to date."
