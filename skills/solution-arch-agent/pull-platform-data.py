#!/usr/bin/env python3
"""
Pull platform data for feasibility assessment.
Writes raw files + platform-summary.json with only what the AI needs.

Usage:
    python3 pull-platform-data.py <use-case-dir>

Reads: {use-case}/.auth.json
Writes:
    {use-case}/openapi.json       — full OpenAPI spec (search locally, never load into context)
    {use-case}/tasks.json         — full task catalog
    {use-case}/apps.json          — adapter/app type names
    {use-case}/adapters.json      — adapter instances and status
    {use-case}/applications.json  — running applications
    {use-case}/platform-summary.json — compact summary for AI context
"""

import json, sys, os, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen, Request
from urllib.error import URLError

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 pull-platform-data.py <use-case-dir>")
        sys.exit(1)

    use_case = sys.argv[1]
    auth_file = os.path.join(use_case, ".auth.json")

    if not os.path.exists(auth_file):
        print(f"ERROR: {auth_file} not found. Run authentication first.")
        sys.exit(1)

    with open(auth_file) as f:
        auth = json.load(f)

    base = auth["platform_url"].rstrip("/")
    token = auth["token"]
    headers = {"Authorization": f"Bearer {token}"}

    def get(path, out_file):
        url = f"{base}{path}"
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=120) as r:
                data = r.read().decode("utf-8")
            with open(os.path.join(use_case, out_file), "w") as f:
                f.write(data)
            return json.loads(data)
        except Exception as e:
            print(f"  WARN: {out_file} failed — {e}")
            return None

    encoded_base = urllib.parse.quote(base, safe="")

    print("Pulling platform data...")
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            "openapi":       pool.submit(get, f"/help/openapi?url={encoded_base}", "openapi.json"),
            "tasks":         pool.submit(get, "/workflow_builder/tasks/list", "tasks.json"),
            "apps":          pool.submit(get, "/automation-studio/apps/list", "apps.json"),
            "adapters":      pool.submit(get, "/health/adapters", "adapters.json"),
            "applications":  pool.submit(get, "/health/applications", "applications.json"),
            "workflows":     pool.submit(get, "/automation-studio/workflows?limit=500", "workflows.json"),
            "projects":      pool.submit(get, "/automation-studio/projects?limit=100", "projects.json"),
            "device_groups": pool.submit(get, "/configuration_manager/deviceGroups", "device-groups.json"),
        }
        # devices needs POST
        def get_devices():
            import json as _json
            url = f"{base}/configuration_manager/devices"
            body = _json.dumps({"options": {"start": 0, "limit": 1000, "sort": [{"name": 1}], "order": "ascending"}}).encode()
            req = Request(url, data=body, headers={**headers, "Content-Type": "application/json"})
            try:
                with urlopen(req, timeout=120) as r:
                    data = r.read().decode("utf-8")
                with open(os.path.join(use_case, "devices.json"), "w") as f:
                    f.write(data)
                return _json.loads(data)
            except Exception as e:
                print(f"  WARN: devices.json failed — {e}")
                return None
        futures["devices"] = pool.submit(get_devices)
        results = {k: v.result() for k, v in futures.items()}

    # Build compact summary — only what's needed for feasibility
    summary = {
        "platform_url": base,
        "adapters": [],
        "applications": [],
        "adapter_type_names": [],
        "workflow_count": 0,
        "device_count": 0,
        "device_group_count": 0,
        "projects": []
    }

    # Running adapters (name, package, state, connection)
    if results["adapters"] and isinstance(results["adapters"], dict):
        for a in results["adapters"].get("results", []):
            if a.get("state") == "RUNNING":
                summary["adapters"].append({
                    "id": a.get("id"),
                    "package": a.get("package_id"),
                    "connection": a.get("connection", {}).get("state")
                })

    # Running applications
    if results["applications"] and isinstance(results["applications"], dict):
        for a in results["applications"].get("results", []):
            if a.get("state") == "RUNNING":
                summary["applications"].append({
                    "id": a.get("id"),
                    "package": a.get("package_id")
                })

    # Adapter type names from apps (needed for workflow task app/locationType fields)
    if results["apps"] and isinstance(results["apps"], list):
        for a in results["apps"]:
            if a.get("type") == "Adapter":
                summary["adapter_type_names"].append(a.get("name"))

    # Counts only — AI searches raw files for details
    if results["workflows"] and isinstance(results["workflows"], dict):
        summary["workflow_count"] = results["workflows"].get("count", 0)

    if results["devices"] and isinstance(results["devices"], dict):
        summary["device_count"] = len(results["devices"].get("list", []))

    # Projects — name, id, component count in summary
    if results["projects"] and isinstance(results["projects"], dict):
        for p in results["projects"].get("data", []):
            summary["projects"].append({
                "name": p.get("name"),
                "id": p.get("_id"),
                "components": len(p.get("components") or [])
            })

    if results["device_groups"] and isinstance(results["device_groups"], (list, dict)):
        dg = results["device_groups"]
        summary["device_group_count"] = len(dg) if isinstance(dg, list) else len(dg.get("results", dg.get("list", [])))

    out = os.path.join(use_case, "platform-summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nDone.")
    print(f"  Running adapters:     {len(summary['adapters'])}")
    print(f"  Running applications: {len(summary['applications'])}")
    print(f"  Adapter type names:   {len(summary['adapter_type_names'])}")
    print(f"  Workflows:            {summary['workflow_count']}")
    print(f"  Projects:             {len(summary['projects'])}")
    print(f"  Devices:              {summary['device_count']}")
    print(f"  Device groups:        {summary['device_group_count']}")
    print(f"  Summary:              {out}")
    print(f"\nFiles written to {use_case}/:")
    print(f"  platform-summary.json — read this for feasibility")
    print(f"  openapi.json, tasks.json, apps.json, adapters.json, applications.json")
    print(f"  workflows.json, projects.json, devices.json, device-groups.json")
    print(f"\nSearch raw files locally with jq — never load them into context.")

if __name__ == "__main__":
    main()
