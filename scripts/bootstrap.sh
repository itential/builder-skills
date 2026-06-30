#!/bin/bash
# Bootstrap script for Itential Automation Studio development
# Creates a use-case directory with the full platform catalog and environment overview
#
# Usage:
#   ./bootstrap.sh <use-case-name> <platform-url> <client-id> <client-secret>
#
# Example:
#   ./bootstrap.sh port-turn-up https://platform.example.com client123 secret456

set -e

USE_CASE="${1:?Usage: ./bootstrap.sh <use-case-name> <platform-url> <client-id> <client-secret>}"
BASE="${2:?Missing platform URL}"
CLIENT_ID="${3:?Missing client ID}"
CLIENT_SECRET="${4:?Missing client secret}"

mkdir -p "$USE_CASE"

echo "Authenticating..."
TOKEN=$(curl -s "$BASE/oauth/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "client_secret=$CLIENT_SECRET" \
  --data-urlencode 'grant_type=client_credentials' | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$TOKEN" ]; then
  echo "ERROR: Authentication failed"
  exit 1
fi
echo "Authenticated."

echo "Pulling OpenAPI spec (API reference)..."
ENCODED_URL=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$BASE', safe=''))")
curl -s "$BASE/help/openapi?url=$ENCODED_URL" -H "Authorization: Bearer $TOKEN" > "$USE_CASE/openapi.json"

echo "Pulling task catalog..."
curl -s "$BASE/workflow_builder/tasks/list" -H "Authorization: Bearer $TOKEN" > "$USE_CASE/tasks.json"

echo "Pulling apps list..."
curl -s "$BASE/automation-studio/apps/list" -H "Authorization: Bearer $TOKEN" > "$USE_CASE/apps.json"

echo "Pulling adapter health..."
curl -s "$BASE/health/adapters" -H "Authorization: Bearer $TOKEN" > "$USE_CASE/adapters.json"

echo "Pulling application health..."
curl -s "$BASE/health/applications" -H "Authorization: Bearer $TOKEN" > "$USE_CASE/applications.json"

echo "Generating environment overview..."
python3 - "$USE_CASE" << 'PYEOF'
import json, sys

d = sys.argv[1]
tasks = json.load(open(f"{d}/tasks.json"))
apps = json.load(open(f"{d}/apps.json"))
adapters_raw = json.load(open(f"{d}/adapters.json"))
applications_raw = json.load(open(f"{d}/applications.json"))

adapters = adapters_raw if isinstance(adapters_raw, list) else adapters_raw.get("results", [])
applications = applications_raw if isinstance(applications_raw, list) else applications_raw.get("results", [])

from collections import Counter
task_locations = Counter(t.get("location","") for t in tasks)
task_apps = Counter(t.get("app","") for t in tasks)

out = []
out.append("# Environment Overview\n")
out.append(f"**Total tasks in palette:** {len(tasks)}")
out.append(f"  - Application tasks: {task_locations.get('Application', 0)}")
out.append(f"  - Adapter tasks: {task_locations.get('Adapter', 0)}")
out.append(f"  - Broker tasks: {task_locations.get('Broker', 0)}\n")

out.append("## Applications\n")
out.append("| Application | State | Description | Task Count |")
out.append("|-------------|-------|-------------|-----------|")
for a in sorted(applications, key=lambda x: x.get("id","")):
    name = a.get("id","")
    desc = (a.get("description","") or "")[:60]
    count = task_apps.get(name, 0)
    out.append(f"| {name} | {a.get('state','')} | {desc} | {count} |")
out.append("")

out.append("## Adapters\n")
out.append("When building workflows, use the **Instance Name** as the task `app` field.\n")
out.append("| Instance Name | Adapter Type | Package | State | Task Count |")
out.append("|---------------|-------------|---------|-------|-----------|")
for a in sorted(adapters, key=lambda x: x.get("id","")):
    name = a.get("id","")
    pkg = a.get("package_id","")
    adapter_type = pkg.split("adapter-")[-1] if "adapter-" in pkg else pkg.split("/")[-1]
    state = a.get("state","")
    count = task_apps.get(name, 0)
    out.append(f"| {name} | {adapter_type} | {pkg} | {state} | {count} |")
out.append("")

out.append("## Top Task Sources\n")
out.append("| Source | Location | Task Count |")
out.append("|--------|----------|-----------|")
for app, cnt in task_apps.most_common(20):
    loc = ""
    for t in tasks:
        if t.get("app") == app:
            loc = t.get("location","")
            break
    out.append(f"| {app} | {loc} | {cnt} |")
out.append("")

with open(f"{d}/environment.md", "w") as f:
    f.write("\n".join(out) + "\n")
PYEOF

echo ""
echo "=== Bootstrap Complete ==="
echo "Directory: $USE_CASE/"
TASK_COUNT=$(python3 -c "import json; print(len(json.load(open('$USE_CASE/tasks.json'))))" 2>/dev/null || echo '?')
APP_COUNT=$(python3 -c "import json; print(len(json.load(open('$USE_CASE/apps.json'))))" 2>/dev/null || echo '?')
echo "  openapi.json      - full API reference (search locally, don't load into context)"
echo "  tasks.json        - $TASK_COUNT tasks (searchable catalog)"
echo "  apps.json         - $APP_COUNT apps/adapters"
echo "  adapters.json     - adapter instance details"
echo "  applications.json - application details"
echo "  environment.md    - environment overview with task counts"
