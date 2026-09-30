#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="${ROOT_DIR}/skills"
status=0

check_mirror() {
  local mirror_root="$1"
  local mirror_label="$2"

  for skill_dir in "${SKILLS_DIR}"/*; do
    [[ -d "${skill_dir}" ]] || continue
    [[ -f "${skill_dir}/SKILL.md" ]] || continue
    local skill_name mirror
    skill_name="$(basename "${skill_dir}")"
    mirror="${mirror_root}/${skill_name}"

    if [[ -L "${mirror}" ]]; then
      echo "ERROR: ${mirror_label}/${skill_name} is a symlink" >&2
      status=1
      continue
    fi

    if [[ ! -d "${mirror}" ]]; then
      echo "ERROR: ${mirror_label}/${skill_name} is missing" >&2
      status=1
      continue
    fi

    if ! diff -rq "${skill_dir}" "${mirror}" >/dev/null 2>&1; then
      echo "ERROR: ${mirror_label}/${skill_name} has drifted from skills/${skill_name}" >&2
      status=1
    fi
  done

  for mirror in "${mirror_root}"/*; do
    [[ -e "${mirror}" ]] || continue
    local skill_name
    skill_name="$(basename "${mirror}")"
    if [[ ! -d "${SKILLS_DIR}/${skill_name}" ]]; then
      echo "ERROR: ${mirror_label}/${skill_name} has no corresponding skills/${skill_name}" >&2
      status=1
    fi
  done
}

check_mirror "${ROOT_DIR}/.claude/skills" ".claude/skills"
check_mirror "${ROOT_DIR}/.agents/skills" ".agents/skills"
check_mirror "${ROOT_DIR}/.github/skills" ".github/skills"

if [[ ${status} -eq 0 ]]; then
  echo "All .claude/skills, .agents/skills, .github/skills entries match skills/."
fi

exit ${status}
