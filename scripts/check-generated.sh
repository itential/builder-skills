#!/usr/bin/env bash
set -euo pipefail

# The Skills Valid PR check. Bundles the shared library into skills/*/assets (fails if a
# SKILL.md mentions a library file that doesn't exist), fails if the committed assets are
# out of date, then checks every skill against the Agent Skills format.
# Run it locally before pushing and commit any skills/*/assets changes it makes.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${ROOT_DIR}/scripts/bundle_skill_assets.py"

# Unstaged or untracked bundle output means the committed/staged assets are stale.
ASSETS=(':(glob)skills/*/assets/**')
stale="$(git -C "${ROOT_DIR}" diff --name-only -- "${ASSETS[@]}"; git -C "${ROOT_DIR}" ls-files --others --exclude-standard -- "${ASSETS[@]}")"
if [[ -n "${stale}" ]]; then
  echo "skills/*/assets is out of date -- run scripts/check-generated.sh locally and commit the result:" >&2
  echo "${stale}" >&2
  exit 1
fi

python3 "${ROOT_DIR}/scripts/check-skills.py"
