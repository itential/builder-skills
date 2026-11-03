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
    {use-case}/workflows.json     — every workflow ({"items": [...], "total": N})
    {use-case}/projects.json      — projects visible to this client
    {use-case}/devices.json       — every device ({"list": [...], "total": N})
    {use-case}/device-groups.json — device groups
    {use-case}/lcm-models.json    — LCM resource models with their actions
    {use-case}/agents.json        — FlowAgent agents this client can see
    {use-case}/llm-profiles.json  — LLM profiles this client can build agents with
    {use-case}/gateways.json      — Gateway5 clusters, with connection state
    {use-case}/gateway-services.json — services registered on Gateway5 clusters
    {use-case}/inventories.json   — Inventory Manager inventories
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
    token = auth.get("token") or auth["access_token"]
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
            "projects":      pool.submit(get, "/automation-studio/projects?limit=100", "projects.json"),
            "device_groups": pool.submit(get, "/configuration_manager/deviceGroups", "device-groups.json"),
        }
        # Workflows are paged (the API returns at most 100 per request) -- fetch every page,
        # sorted by _id (the default order shifts between pages, duplicating some workflows
        # and skipping others), so reuse searches see all of them. Saved as {"items": [...], "total": N}.
        def get_workflows():
            items, total = [], None
            try:
                while total is None or len(items) < total:
                    req = Request(f"{base}/automation-studio/workflows?limit=100&skip={len(items)}&sort=_id&order=1", headers=headers)
                    with urlopen(req, timeout=120) as r:
                        page = json.loads(r.read().decode("utf-8"))
                    total = page.get("total", 0)
                    if not page.get("items"):
                        break
                    items.extend(page["items"])
                data = {"items": items, "total": total}
                with open(os.path.join(use_case, "workflows.json"), "w") as f:
                    json.dump(data, f)
                return data
            except Exception as e:
                print(f"  WARN: workflows.json failed — {e}")
                return None
        futures["workflows"] = pool.submit(get_workflows)

        # Devices need POST. Paging them is unreliable (pages overlap and skip devices), so
        # ask for the total first, then fetch every device in one request.
        def get_devices():
            url = f"{base}/configuration_manager/devices"
            def fetch(limit):
                body = json.dumps({"options": {"start": 0, "limit": limit, "sort": [{"name": 1}], "order": "ascending"}}).encode()
                req = Request(url, data=body, headers={**headers, "Content-Type": "application/json"})
                with urlopen(req, timeout=300) as r:
                    return json.loads(r.read().decode("utf-8"))
            try:
                data = fetch(1)
                if data.get("total", 0) > len(data.get("list", [])):
                    data = fetch(data["total"])
                with open(os.path.join(use_case, "devices.json"), "w") as f:
                    json.dump(data, f)
                return data
            except Exception as e:
                print(f"  WARN: devices.json failed — {e}")
                return None
        futures["devices"] = pool.submit(get_devices)

        # Execution-model capability inventory: what LCM, FlowAgent and Gateway5 already
        # have on this platform. A missing app returns an error; that file is just skipped.
        def get_lcm_models():
            items, total = [], None
            try:
                while total is None or len(items) < total:
                    req = Request(f"{base}/lifecycle-manager/resources?limit=100&skip={len(items)}", headers=headers)
                    with urlopen(req, timeout=120) as r:
                        page = json.loads(r.read().decode("utf-8"))
                    total = page.get("metadata", {}).get("total", 0)
                    if not page.get("data"):
                        break
                    items.extend(page["data"])
                data = {"data": items, "total": total}
                with open(os.path.join(use_case, "lcm-models.json"), "w") as f:
                    json.dump(data, f)
                return data
            except Exception as e:
                print(f"  WARN: lcm-models.json failed — {e}")
                return None
        futures["lcm_models"] = pool.submit(get_lcm_models)
        futures["agents"] = pool.submit(get, "/agent-project-service/agent-names/accessible", "agents.json")
        futures["llm_profiles"] = pool.submit(get, "/agent-project-service/profiles", "llm-profiles.json")
        futures["gateways"] = pool.submit(get, "/gateway_manager/v1/gateways", "gateways.json")
        futures["gateway_connections"] = pool.submit(get, "/gateway_manager/v1/connections", "gateway-connections.json")
        futures["gateway_services"] = pool.submit(get, "/gateway_manager/v1/services", "gateway-services.json")
        futures["inventories"] = pool.submit(get, "/inventory_manager/v1/inventories?pageSize=100", "inventories.json")
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
                    "name": a.get("id"),
                    "package_id": a.get("package_id"),
                    "connection": a.get("connection", {}).get("state")
                })

    # Running applications
    if results["applications"] and isinstance(results["applications"], dict):
        for a in results["applications"].get("results", []):
            if a.get("state") == "RUNNING":
                summary["applications"].append({
                    "name": a.get("id"),
                    "package_id": a.get("package_id")
                })

    # Adapter type names from apps (needed for workflow task app/locationType fields)
    if results["apps"] and isinstance(results["apps"], list):
        for a in results["apps"]:
            if a.get("type") == "Adapter":
                summary["adapter_type_names"].append(a.get("name"))

    # Counts only — AI searches raw files for details
    if results["workflows"] and isinstance(results["workflows"], dict):
        summary["workflow_count"] = len(results["workflows"].get("items", []))

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

    # Execution-model capabilities — what the design can build on (see ../references/execution-model.md)
    running = {a["name"] for a in summary["applications"]}
    caps = {
        "lcm": {"running": "LifecycleManager" in running, "models": []},
        "flowagent": {
            "running": {"AgentProjectService", "AgentSessionManager", "AgentExecutionEngine"} <= running,
            "llm_profiles": [], "agent_count": 0,
        },
        "gateway5": {"running": "GatewayManager" in running, "clusters": [], "inventories": []},
        "gateway4_running": "AGManager" in running,
    }
    if isinstance(results["lcm_models"], dict):
        for m in results["lcm_models"].get("data", []):
            caps["lcm"]["models"].append({"name": m.get("name"), "id": m.get("_id"),
                                          "actions": [a.get("name") for a in m.get("actions") or []]})
    if isinstance(results["llm_profiles"], dict):
        for p in results["llm_profiles"].get("data", {}).get("items", []):
            caps["flowagent"]["llm_profiles"].append({"name": p.get("name"), "provider": p.get("provider"),
                                                      "models": [m.get("name") for m in p.get("models") or []]})
    if isinstance(results["agents"], dict):
        caps["flowagent"]["agent_count"] = len(results["agents"].get("data", {}).get("items", []))
    services_by_cluster = {}
    if isinstance(results["gateway_services"], dict):
        for s in results["gateway_services"].get("result", []):
            loc = (s.get("service_metadata") or {}).get("location")
            services_by_cluster[loc] = services_by_cluster.get(loc, 0) + 1
    conns = results["gateway_connections"] if isinstance(results["gateway_connections"], dict) else {}
    if isinstance(results["gateways"], dict):
        for g in results["gateways"].get("results", []):
            cid = g.get("cluster_id")
            caps["gateway5"]["clusters"].append({"cluster_id": cid, "connection": conns.get(cid, "unknown"),
                                                 "services": services_by_cluster.get(cid, 0)})
    if isinstance(results["inventories"], dict):
        for i in results["inventories"].get("result", {}).get("data", []):
            caps["gateway5"]["inventories"].append({"name": i.get("name"), "nodes": i.get("nodeCount")})
    summary["execution_capabilities"] = caps

    out =os.path.join(use_case, "platform-summary.json")
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
    connected = [c for c in caps["gateway5"]["clusters"] if c["connection"] == "connected"]
    print(f"  LCM resource models:  {len(caps['lcm']['models'])}")
    print(f"  Agents / LLM profiles: {caps['flowagent']['agent_count']} / {len(caps['flowagent']['llm_profiles'])}")
    print(f"  Gateway5 clusters:    {len(connected)} connected of {len(caps['gateway5']['clusters'])}")
    print(f"  Inventories:          {len(caps['gateway5']['inventories'])}")
    print(f"  Summary:              {out}")
    print(f"\nFiles written to {use_case}/:")
    print(f"  platform-summary.json — read this for feasibility")
    print(f"  openapi.json, tasks.json, apps.json, adapters.json, applications.json")
    print(f"  workflows.json, projects.json, devices.json, device-groups.json")
    print(f"  lcm-models.json, agents.json, llm-profiles.json, gateways.json, gateway-connections.json,")
    print(f"  gateway-services.json, inventories.json")
    print(f"\nSearch raw files locally with jq — never load them into context.")

if __name__ == "__main__":
    main()
