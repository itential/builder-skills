#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/scripts/generate-vendor-wrappers.sh" >/dev/null
"${ROOT_DIR}/scripts/check-vendor-skills.sh" >/dev/null

paths=(
  ".claude/skills"
  ".claude/commands"
  ".github/copilot-instructions.md"
  ".github/prompts"
  ".cursor/rules"
  "codex/itential-builder-skills"
)

if [[ -n "$(git -C "${ROOT_DIR}" status --porcelain -- "${paths[@]}")" ]]; then
  echo "Generated vendor artifacts are stale or untracked:" >&2
  git -C "${ROOT_DIR}" status --short -- "${paths[@]}" >&2
  exit 1
fi

echo "Generated vendor artifacts are up to date."
