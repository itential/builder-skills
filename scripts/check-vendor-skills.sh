#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

diff -ru "${ROOT_DIR}/skills" "${ROOT_DIR}/.claude/skills"
