#!/usr/bin/env bash
# OAuth Bootstrap for Itential SaaS/Cloud Platforms
# Reads CLIENT_ID and CLIENT_SECRET from .env, authenticates via /oauth/token,
# and writes the bearer token to .auth.json
#
# Usage: ./oauth-bootstrap.sh [path-to-env-file]
#
# IMPORTANT:
# - The endpoint is /oauth/token (NOT /login)
# - Content-Type MUST be application/x-www-form-urlencoded (NOT JSON — JSON returns 415)
# - The /login endpoint does NOT support OAuth client_credentials on SaaS instances

set -euo pipefail

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found" >&2
  exit 1
fi

# Source the env file
set -a
source "$ENV_FILE"
set +a

# Validate required variables
if [ -z "${PLATFORM_URL:-}" ] || [ -z "${CLIENT_ID:-}" ] || [ -z "${CLIENT_SECRET:-}" ]; then
  echo "ERROR: PLATFORM_URL, CLIENT_ID, and CLIENT_SECRET must be set in $ENV_FILE" >&2
  exit 1
fi

# Strip trailing slash from PLATFORM_URL
PLATFORM_URL="${PLATFORM_URL%/}"

echo "Authenticating to ${PLATFORM_URL}..."

RESPONSE=$(curl -s -X POST "${PLATFORM_URL}/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}" \
  -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" != "200" ]; then
  echo "ERROR: Authentication failed with HTTP ${HTTP_CODE}" >&2
  echo "$BODY" >&2
  exit 1
fi

# Extract token and write .auth.json
TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "ERROR: Could not extract access_token from response" >&2
  echo "$BODY" >&2
  exit 1
fi

# Write to .auth.json in the same directory as the env file
AUTH_DIR=$(dirname "$ENV_FILE")
echo "{\"token\": \"${TOKEN}\"}" > "${AUTH_DIR}/.auth.json"

echo "OK — token written to ${AUTH_DIR}/.auth.json"
