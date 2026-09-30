#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="${ROOT_DIR}/skills"

if [[ ! -d "${SKILLS_DIR}" ]]; then
  echo "ERROR: skills directory not found: ${SKILLS_DIR}" >&2
  exit 1
fi

sync_mirror() {
  local mirror_dir="$1"
  rm -rf "${mirror_dir}"
  mkdir -p "${mirror_dir}"
  for skill_dir in "${SKILLS_DIR}"/*; do
    [[ -d "${skill_dir}" ]] || continue
    [[ -f "${skill_dir}/SKILL.md" ]] || continue
    local skill_name
    skill_name="$(basename "${skill_dir}")"
    cp -R "${skill_dir}" "${mirror_dir}/${skill_name}"
  done
}

sync_mirror "${ROOT_DIR}/.claude/skills"
sync_mirror "${ROOT_DIR}/.agents/skills"
sync_mirror "${ROOT_DIR}/.github/skills"

echo "Synced .claude/skills, .agents/skills, .github/skills from ${SKILLS_DIR}"
