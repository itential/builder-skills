#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True

"""Deterministic IAG4 usage analysis for the /iag4-to-iag5 skill.

Pure analysis over already-pulled data in a working directory's tmp/ folder. Reads
wf_all.ndjson, apps.json, adapters.json and json-forms.json; resolves the IAG4
identifiers, applies a scope filter, scans workflows and JSON forms, classifies each
IAG4 reference, and writes a sorted, structured analysis.json.

Read-only: the ONLY file this writes is the --out analysis JSON (default <tmp>/analysis.json).
It never touches IAP/IAG and never re-pulls data. Scripts + inventory analysis stay with
the skill's AI. The report is rendered by the skill from this JSON.

The recommendation strings below are the single source of truth and MUST stay identical to
helpers/iag-migration/readiness-report-template.md.
"""

import argparse
import json
import os
import re
import sys

# don't write bytecode for anything this process imports (belt-and-suspenders; the skill also
# invokes us with `python3 -B`, which is what actually prevents a __pycache__ for this module).
sys.dont_write_bytecode = True

# --- verbatim recommendation strings (keep in sync with readiness-report-template.md) ---
REC_ANSIBLE = "register playbook as an IAG5 ansible-playbook service; call via GatewayManager.runService"
REC_PYTHON = "re-implement as an IAG5 python-script service; call via GatewayManager.runService"
REC_SELFMGMT = "move to the Inventory Manager application; drop this task"
REC_FORM = "rebind to the IAG5/replacement endpoint — returns no data once IAG4 is removed."
REC_DEVICE = "device sourced from an IAG4 gateway adapter; re-home it in Inventory Manager before removing IAG4"

# IAG4 application name (agmanager). GatewayManager (IAG5) must NEVER be flagged.
IAG4_APP = "AGManager"
# adapter package that identifies the IAG4 automation_gateway adapter
IAG4_ADAPTER_PACKAGE = "automation_gateway"
# canonical adapter type token as it appears on workflow tasks' `app` field
IAG4_ADAPTER_TYPE = "AutomationGateway"

# self-management: device/group inventory ops that go away in IAG5
_SELFMGMT_RE = re.compile(
    r"(add|create|remove|delete|update|get|list)[_\s-]*(device|group)s?\b|"
    r"\b(device|group)[_\s-]*(add|create|remove|delete|update|management)\b",
    re.IGNORECASE,
)
_PLAYBOOK_RE = re.compile(r"\b(playbook|role)\b", re.IGNORECASE)
# form endpoint tokens that indicate an IAG4 binding
_FORM_IAG4_TOKENS = ("automationgateway", "automation_gateway", "automation-gateway", "agmanager")


def _norm(s):
    return re.sub(r"[\s_-]", "", (s or "").lower())


def load_ndjson(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


def resolve_identifiers(adapters_path):
    """Return (adapter_type, sorted instance ids, routePrefixes) for the IAG4 adapter."""
    instances, prefixes = set(), set()
    if adapters_path and os.path.exists(adapters_path):
        data = load_json(adapters_path)
        results = data.get("results") if isinstance(data, dict) else data
        for a in results or []:
            if IAG4_ADAPTER_PACKAGE in str(a.get("package_id", "")):
                if a.get("id"):
                    instances.add(a["id"])
                if a.get("routePrefix"):
                    prefixes.add(a["routePrefix"])
    return IAG4_ADAPTER_TYPE, sorted(instances), sorted(prefixes)


def load_project_names(projects_path):
    """Return {project_id: name} from projects.json. The project list wrapper varies by endpoint
    (`data`, `items`, `results`, or a bare array), so probe each. Missing/orphaned/deleted project
    ids simply won't be in the map — the caller falls back to the bare id."""
    names = {}
    if projects_path and os.path.exists(projects_path):
        data = load_json(projects_path)
        if isinstance(data, dict):
            rows = data.get("data") or data.get("items") or data.get("results") or []
        else:
            rows = data or []
        for p in rows:
            if isinstance(p, dict) and p.get("_id"):
                names[p["_id"]] = p.get("name")
    return names


def is_iag4_task(task, instance_ids, prefixes):
    """True if a workflow task references IAG4 (adapter or AGManager app). Never GatewayManager."""
    app = task.get("app")
    loc = task.get("location")
    if app == "GatewayManager":
        return False
    if app == IAG4_APP:
        return True
    if _norm(app) == _norm(IAG4_ADAPTER_TYPE):
        return True
    if app in instance_ids or loc in instance_ids:
        return True
    return False


def classify(task):
    """Return (iag4_type, short_recommendation) for an IAG4 task."""
    hay = " ".join(str(task.get(k) or "") for k in ("name", "summary", "description", "canvasName"))
    if _SELFMGMT_RE.search(hay):
        return "self-management", REC_SELFMGMT
    if _PLAYBOOK_RE.search(hay):
        return "ansible-playbook", REC_ANSIBLE
    return "python-script", REC_PYTHON


_PREFIX_RE = re.compile(r"^@([0-9a-fA-F]+):\s*(.*)$")


def split_name(raw):
    """(project_id or None, display_name) from a workflow/form name."""
    m = _PREFIX_RE.match(raw or "")
    if m:
        return m.group(1), m.group(2)
    return None, (raw or "")


def wf_location(wf, project_names):
    """Resolve a workflow's project membership from the authoritative `namespace` field.

    A workflow is IN A PROJECT iff `namespace` is a project object (carries the live `_id`
    and `name`); then the report shows that name. Otherwise it is GLOBAL — even if its NAME
    still starts with a stale `@<id>:` prefix (a leftover string from a bulk import whose
    project was deleted). The name prefix alone is NOT proof of project membership.

    Returns (location_type, project_id, project_name, prefix_id, display_name).
    """
    raw = wf.get("name") or ""
    prefix_id, display = split_name(raw)
    ns = wf.get("namespace")
    if isinstance(ns, dict) and ns.get("type") == "project" and ns.get("_id"):
        return "project", ns.get("_id"), ns.get("name"), prefix_id, display
    # defensive fallback: no namespace, but the name prefix resolves to a live project
    if prefix_id and prefix_id in project_names:
        return "project", prefix_id, project_names.get(prefix_id), prefix_id, display
    return "global", None, None, prefix_id, display


def in_scope(project_id, prefix_id, display, raw, scope):
    mode = scope["mode"]
    if mode == "all":
        return True
    if mode == "projects":
        want = scope["value"]
        return (project_id in want) or (prefix_id in want)
    if mode == "workflows":
        wanted = scope["value"]
        return raw in wanted or display in wanted
    return False


def scan_workflows(wf_rows, instance_ids, prefixes, scope, project_names):
    workflows, n_tasks = [], 0
    for wf in wf_rows or []:
        raw = wf.get("name") or ""
        loc_type, project_id, project_name, prefix_id, display = wf_location(wf, project_names)
        if not in_scope(project_id, prefix_id, display, raw, scope):
            continue
        tasks = wf.get("tasks") or {}
        hits = []
        for tid, t in tasks.items():
            if tid in ("workflow_start", "workflow_end"):
                continue
            if not is_iag4_task(t, instance_ids, prefixes):
                continue
            iag4_type, rec = classify(t)
            hits.append({
                "task_id": tid,
                "task_name": t.get("name"),
                "app": t.get("app"),
                "summary": t.get("summary"),
                "iag4_type": iag4_type,
                "short_recommendation": rec,
            })
        if hits:
            hits.sort(key=lambda x: x["task_id"])
            workflows.append({
                "workflow_name": display,
                "workflow_id": wf.get("_id"),
                "location_type": loc_type,
                "project_id": project_id,
                "project_name": project_name,
                "tasks": hits,
            })
            n_tasks += len(hits)
    workflows.sort(key=lambda w: (w["workflow_name"], w["project_id"] or "", w["workflow_id"] or ""))
    return workflows, n_tasks


def _endpoint_urls(field):
    """Collect the REST endpoint path(s) a form field binds to. ONLY the endpoint URL matters —
    base+href, originalHref, links[].href, and the binding:hyperSchema mirror. We deliberately do
    NOT look inside the request body (e.g. body.options.adapterType): a Configuration Manager query
    that FILTERS by adapterType is a CM endpoint, not an IAG4-bound endpoint, and must not be flagged.
    """
    urls = []
    if not isinstance(field, dict):
        return urls
    base = field.get("base") or ""
    if field.get("base") or field.get("href"):
        urls.append(base + (field.get("href") or ""))
    if field.get("originalHref"):
        urls.append(base + field["originalHref"])
    for lk in field.get("links") or []:
        if isinstance(lk, dict) and lk.get("href"):
            urls.append(base + lk["href"])
    hs = field.get("binding:hyperSchema") or field.get("hyperSchema")
    if isinstance(hs, dict):
        hb = hs.get("base") or ""
        if hs.get("base"):
            urls.append(hb)
        for lk in hs.get("links") or []:
            if isinstance(lk, dict) and lk.get("href"):
                urls.append(hb + lk["href"])
    return urls


def _endpoint_iag4_token(field, tokens):
    """Return (matched_token, endpoint_url) if any of the field's endpoints points at IAG4."""
    for url in _endpoint_urls(field):
        norm = _norm(url)
        for tok in tokens:
            if tok and tok in norm:
                return tok, url
    return None


def scan_forms(forms_path, prefixes):
    """Flag form fields whose BINDING ENDPOINT points at the IAG4 automation_gateway adapter or the
    agmanager app — dropdowns and any other REST-bound field alike. Matching is on the endpoint URL
    only, never the request body: a form bound to /configuration_manager/... that merely filters by
    adapterType=AutomationGateway is a Config Manager form, NOT an IAG4-bound form."""
    forms = []
    if not (forms_path and os.path.exists(forms_path)):
        return forms
    tokens = tuple(_FORM_IAG4_TOKENS) + tuple(_norm(p) for p in (prefixes or []))
    for f in load_json(forms_path) or []:
        raw = f.get("name") or ""
        _, display = split_name(raw)
        struct = f.get("struct") or {}
        binding_props = (f.get("bindingSchema") or {}).get("properties") or {}
        seen_keys = set()

        # visible fields (struct.items[]) — check each field's binding endpoint
        for item in struct.get("items") or []:
            if not isinstance(item, dict):
                continue
            hit = _endpoint_iag4_token(item, tokens)
            if not hit:
                continue
            field_key = item.get("title") or item.get("nodeId") or "(field)"
            seen_keys.add(field_key)
            forms.append({
                "form_name": display,
                "field_key": field_key,
                "bound_endpoint": hit[1],
                "matched_on": hit[0],
            })

        # bindingSchema mirror — catch fields whose endpoint lives only in the backing schema
        for key, v in binding_props.items():
            if key in seen_keys or not isinstance(v, dict):
                continue
            hit = _endpoint_iag4_token(v, tokens)
            if hit:
                forms.append({
                    "form_name": display,
                    "field_key": key,
                    "bound_endpoint": hit[1],
                    "matched_on": hit[0],
                })
    forms.sort(key=lambda x: (x["form_name"], str(x["field_key"])))
    return forms


def scan_devices(devices_path, instance_ids):
    """Flag Configuration Manager devices whose origin/broker is an IAG4 gateway adapter.
    devices.json shape: {"list":[{"name":..., "origins":[adapter_instance,...]}]}."""
    flagged, total, iag4_set = [], 0, set(instance_ids)
    if not (devices_path and os.path.exists(devices_path)):
        return {"present": False, "n_devices": 0, "n_iag4": 0, "devices": []}
    data = load_json(devices_path)
    rows = data.get("list") if isinstance(data, dict) else data
    for dev in rows or []:
        total += 1
        origins = dev.get("origins") or ([dev.get("origin")] if dev.get("origin") else [])
        iag4_origins = sorted({o for o in origins if o in iag4_set})
        if iag4_origins:
            flagged.append({
                "device_name": dev.get("name"),
                "origins": iag4_origins,
                "recommendation": REC_DEVICE,
            })
    flagged.sort(key=lambda d: (str(d["device_name"]), str(d["origins"])))
    return {"present": True, "n_devices": total, "n_iag4": len(flagged), "devices": flagged}


def build_checklist(workflows, forms):
    agg = {}
    for w in workflows:
        for t in w["tasks"]:
            key = (t["task_name"], t["app"], t["short_recommendation"])
            agg[key] = agg.get(key, 0) + 1
    wf_items = [
        {"key": k[0], "app": k[1], "count": c, "recommendation": k[2]}
        for k, c in agg.items()
    ]
    wf_items.sort(key=lambda x: (x["recommendation"], str(x["key"]), str(x["app"])))
    form_items = [
        {"form_name": f["form_name"], "field_key": f["field_key"],
         "bound_endpoint": f["bound_endpoint"], "recommendation": REC_FORM}
        for f in forms
    ]
    return {"workflows": wf_items, "forms": form_items}


def parse_args(argv):
    p = argparse.ArgumentParser(description="Deterministic IAG4 usage analysis (workflows + JSON forms).")
    p.add_argument("--tmp", required=True, help="tmp dir holding wf_all.ndjson, apps.json, adapters.json, json-forms.json")
    p.add_argument("--out", help="output path (default <tmp>/analysis.json)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="scan every workflow")
    g.add_argument("--projects", help="comma-separated project ids (workflows named @<id>: ...)")
    g.add_argument("--workflows", help="semicolon-separated workflow names (full or display)")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    tmp = args.tmp
    wf_path = os.path.join(tmp, "wf_all.ndjson")
    if not os.path.exists(wf_path):
        sys.stderr.write("error: %s not found — run the skill's pull step first\n" % wf_path)
        return 2

    # An EMPTY wf_all.ndjson is NOT "no IAG4 usage" — it means the workflow pull returned nothing
    # (almost always a silent auth failure: the OAuth token was sent as a ?token= query param
    # instead of an 'Authorization: Bearer <token>' header, so every page 401'd and `.items[]`
    # matched nothing). Fail loudly here rather than emitting a misleading all-zeros report.
    wf_rows = load_ndjson(wf_path)
    if not wf_rows:
        sys.stderr.write(
            "error: %s is empty — the workflow pull returned 0 workflows. Do NOT trust an all-zeros "
            "report; the pull failed. For OAuth (AUTH_METHOD=oauth) the token MUST be sent as an "
            "'Authorization: Bearer <token>' HEADER, never a ?token= query param. Re-run the Step 1 "
            "pull, confirm the ndjson line count matches the workflows 'total', then re-run this script.\n"
            % wf_path
        )
        return 2

    # A NON-EMPTY ndjson that holds no workflow documents is ALSO a failed pull, not "no IAG4 usage".
    # The usual cause is a mid-pull auth failure (token expiry, or an OAuth token sent as ?token=
    # instead of the Bearer header): the paginated GETs return error bodies like
    # {"message":"Unauthorized"} that parse as JSON and land in the ndjson, so the empty-check above
    # passes but every row lacks a `tasks` map. Every REAL workflow carries a `tasks` object (at
    # minimum workflow_start/workflow_end), so if NOT ONE row has one, the file is non-workflow data.
    # Fail loudly here — otherwise the scan finds nothing and emits a misleading "0 workflows / 0
    # tasks" report that exits 0 and looks successful. (A platform with genuinely zero IAG4 usage
    # still has real workflows WITH tasks, so this guard never fires on a legitimate zero result.)
    if not any(isinstance(w, dict) and isinstance(w.get("tasks"), dict) for w in wf_rows):
        sys.stderr.write(
            "error: %s has %d rows but none are workflow documents (no `tasks` object on any row). "
            "The workflow pull FAILED — almost always a mid-pull auth failure that wrote error bodies "
            "(e.g. {\"message\":\"Unauthorized\"}) into the ndjson instead of workflows. Do NOT trust a "
            "0-workflow report. For OAuth the token MUST be an 'Authorization: Bearer <token>' HEADER "
            "(never a ?token= query param); confirm the ndjson line count matches the workflows "
            "'total', then re-run this script.\n" % (wf_path, len(wf_rows))
        )
        return 2

    if args.all:
        scope = {"mode": "all", "value": None}
    elif args.projects:
        scope = {"mode": "projects", "value": [s.strip() for s in args.projects.split(",") if s.strip()]}
    else:
        scope = {"mode": "workflows", "value": [s.strip() for s in args.workflows.split(";") if s.strip()]}

    adapter_type, instance_ids, prefixes = resolve_identifiers(os.path.join(tmp, "adapters.json"))
    project_names = load_project_names(os.path.join(tmp, "projects.json"))
    workflows, n_tasks = scan_workflows(wf_rows, instance_ids, prefixes, scope, project_names)
    forms = scan_forms(os.path.join(tmp, "json-forms.json"), prefixes)
    devices = scan_devices(os.path.join(tmp, "devices.json"), instance_ids)
    checklist = build_checklist(workflows, forms)

    result = {
        "identifiers": {
            "adapter_type": adapter_type,
            "adapter_instances": instance_ids,
            "adapter_route_prefixes": prefixes,
            "app": IAG4_APP,
        },
        "scope": scope,
        "counts": {
            "n_workflows": len(workflows),
            "n_iag4_tasks": n_tasks,
            "n_forms": len(forms),
            "n_iag4_devices": devices["n_iag4"],
        },
        "workflows": workflows,
        "forms": forms,
        "devices": devices,
        "checklist": checklist,
    }

    out = args.out or os.path.join(tmp, "analysis.json")
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=False)
        fh.write("\n")

    sys.stderr.write(
        "analyzed scope=%s -> %d workflows, %d IAG4 tasks, %d IAG4 form fields, %d IAG4-origin devices -> %s\n"
        % (scope["mode"], len(workflows), n_tasks, len(forms), devices["n_iag4"], out)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
