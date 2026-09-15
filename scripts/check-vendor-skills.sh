#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="${ROOT_DIR}/skills"
CLAUDE_SKILLS_DIR="${ROOT_DIR}/.claude/skills"

# .claude/skills/<name> must be a symlink resolving to skills/<name> -- not a copy.
# A copy would silently drift from the canonical source; this check catches that
# by comparing realpaths, not diffing file contents.
status=0
for skill_dir in "${SKILLS_DIR}"/*; do
  [[ -d "${skill_dir}" ]] || continue
  [[ -f "${skill_dir}/SKILL.md" ]] || continue
  skill_name="$(basename "${skill_dir}")"
  mirror="${CLAUDE_SKILLS_DIR}/${skill_name}"

  if [[ ! -L "${mirror}" ]]; then
    echo "ERROR: .claude/skills/${skill_name} is not a symlink (expected a symlink to skills/${skill_name})" >&2
    status=1
    continue
  fi

  canonical_real="$(cd "${skill_dir}" && pwd -P)"
  mirror_real="$(cd "${mirror}" 2>/dev/null && pwd -P || true)"
  if [[ "${canonical_real}" != "${mirror_real}" ]]; then
    echo "ERROR: .claude/skills/${skill_name} resolves to '${mirror_real}', expected '${canonical_real}'" >&2
    status=1
  fi
done

# Every symlink under .claude/skills must correspond to a real skill directory --
# catches a stale mirror entry left behind after a skill was removed from skills/.
for mirror in "${CLAUDE_SKILLS_DIR}"/*; do
  [[ -e "${mirror}" ]] || continue
  skill_name="$(basename "${mirror}")"
  if [[ ! -d "${SKILLS_DIR}/${skill_name}" ]]; then
    echo "ERROR: .claude/skills/${skill_name} has no corresponding skills/${skill_name}" >&2
    status=1
  fi
done

if [[ ${status} -eq 0 ]]; then
  echo "All .claude/skills entries are correct symlinks to skills/."
fi

exit ${status}
