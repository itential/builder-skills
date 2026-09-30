#!/usr/bin/env bash
set -euo pipefail

# Itential's repo must never ship real content under any skill's custom/ folder --
# those folders belong to customers' own copies, and keeping them empty upstream is
# what makes pulling Itential updates conflict-free. Only .gitkeep placeholders allowed.
# Run by .github/workflows/guard-custom.yml, in itential/builder-skills only.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

found="$(git ls-files -- \
  ':(glob)skills/*/custom/**' \
  ':(glob).claude/skills/*/custom/**' \
  ':(glob).agents/skills/*/custom/**' \
  ':(glob).github/skills/*/custom/**' \
  | grep -v '/\.gitkeep$' || true)"

if [[ -n "${found}" ]]; then
  echo "ERROR: custom/ folders must stay empty in itential/builder-skills (customer content only):" >&2
  echo "${found}" >&2
  exit 1
fi

echo "All custom/ folders contain only .gitkeep placeholders."
