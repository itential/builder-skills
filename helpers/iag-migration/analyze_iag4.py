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
# NOTE: these strings are rendered into the markdown report, which must NOT contain "iag"/"IAG4"/
# "IAG5" — use "Gateway4"/"Gateway5" instead. Literal API/app names (GatewayManager.runService,
# AG Manager) and actual adapter names stay verbatim so the reader can identify them on the platform.
# Each Gateway4 workflow task gets ONE short CODE + a recommendation. The codes are defined once in
# the report's "Recommended Actions" legend; task tables show only the code. Codes/recs are a
# best-effort classification from the task's name/summary/description — the legend says "review each".
REC_WRAP = "wrap in a Python script or an Ansible playbook and run as a Gateway5 service, or replace with an Inventory Manager send_command/set_config task if that covers the same logic"
REC_REVIEW = "likely no code change — review how inventory is handled (Gateway5 has no built-in inventory)"
REC_ARGS = "change positional args to named args (--flag / argparse); run as a Gateway5 python-script service"
REC_INV = "move to the Inventory Manager application; use a device send-command / set-config task instead of the Gateway4 device operation"
# code + recommendation by classification type (1:1); CODE_ORDER is the legend / grouping order.
CODE_BY_TYPE = {
    "collection-or-role": "WRAP",
    "ansible-playbook": "REVIEW",
    "python-script": "ARGS",
    "self-management": "INV",
}
REC_BY_CODE = {"WRAP": REC_WRAP, "REVIEW": REC_REVIEW, "ARGS": REC_ARGS, "INV": REC_INV}
CODE_ORDER = ["WRAP", "REVIEW", "ARGS", "INV"]
REC_FORM = "rebind to the Gateway5/replacement endpoint — returns no data once Gateway4 is removed."
REC_DEVICE = "device sourced from a Gateway4 adapter; re-home it in Inventory Manager before removing Gateway4"

# Gateway4 application name (agmanager). GatewayManager (Gateway5) must NEVER be flagged.
# (Internal constant name kept as IAG4_APP — script-internal only, never rendered.)
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
_PLAYBOOK_RE = re.compile(r"\bplaybook\b", re.IGNORECASE)
_ROLE_RE = re.compile(r"\b(role|collection)\b", re.IGNORECASE)
# ansible collection module name in a task's `name` field, e.g. cisco.ios_ios_command,
# arista.eos_eos_ospf_interfaces — a letter-led token, a dot, then a module token. (A leading digit,
# e.g. "33.j2", is NOT matched, so jinja/template names don't get misread as collection modules.)
_FQCN_RE = re.compile(r"^[a-z][a-z0-9]*\.[a-z][a-z0-9_]*")
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
    """Return (iag4_type, code, short_recommendation) for an IAG4 task — a best-effort classification
    from the task's name/summary/description (the report legend says "review each"). Order matters:
      1. device/group op on the Gateway4 adapter        -> self-management / INV
      2. ansible playbook                                -> ansible-playbook / REVIEW
      3. ansible collection-module task or role          -> collection-or-role / WRAP
      4. everything else (treated as a python script)    -> python-script / ARGS

    e.g. itential_cli/itential_set_config are Ansible roles -> WRAP (wrap in a Python script or
    Ansible playbook, or use an Inventory Manager send_command/set_config task instead).
    """
    hay = " ".join(str(task.get(k) or "") for k in ("name", "summary", "description", "canvasName"))
    name = task.get("name") or ""
    if _SELFMGMT_RE.search(hay):
        t = "self-management"
    elif _PLAYBOOK_RE.search(hay):
        t = "ansible-playbook"
    elif _ROLE_RE.search(hay) or _FQCN_RE.search(name):
        t = "collection-or-role"
    else:
        t = "python-script"
    code = CODE_BY_TYPE[t]
    return t, code, REC_BY_CODE[code]


def task_interface(task):
    """Which Gateway4 interface a task runs over (req a — needed for Gateway5 cluster mapping):
      - "AG Manager"  when the task uses the AGManager application (app == "AGManager")
      - the ACTUAL adapter name otherwise (the adapter-backed automation_gateway task) — returned
        verbatim from the task's own `app`/`location` so the reader recognizes it on the platform.
    Only ever called for a task already confirmed IAG4 by is_iag4_task()."""
    if task.get("app") == IAG4_APP:
        return "AG Manager"
    return task.get("app") or task.get("location") or IAG4_ADAPTER_TYPE


def find_referrers(tasks, tid):
    """req (b) — other tasks in the SAME workflow that consume this Gateway4 task's output.
    A consumer references it either as a `$var.<tid>.<field>` string (wiring an input from its
    output) or as a structural job reference `{"task":"<tid>", ...}` (childJob / merge / evaluation).
    Returns [{task_id, task_name}] sorted by task id."""
    pat_var = re.compile(r"\$var\." + re.escape(tid) + r"\b")
    pat_task = re.compile(r'"task"\s*:\s*"' + re.escape(tid) + r'"')
    refs = []
    for oid, ot in (tasks or {}).items():
        if oid == tid or oid in ("workflow_start", "workflow_end"):
            continue
        blob = json.dumps(ot)
        if pat_var.search(blob) or pat_task.search(blob):
            refs.append({"task_id": oid, "task_name": (ot or {}).get("name")})
    refs.sort(key=lambda x: x["task_id"])
    return refs


def child_workflow_names(tasks):
    """The workflow NAMES this workflow calls via childJob (req c call-graph edges).
    A childJob task runs on the WorkFlowEngine app and names its target in
    variables.incoming.workflow. Returns a sorted, de-duplicated list of names."""
    names = set()
    for tid, t in (tasks or {}).items():
        if tid in ("workflow_start", "workflow_end") or not isinstance(t, dict):
            continue
        if t.get("app") != "WorkFlowEngine":
            continue
        child = (((t.get("variables") or {}).get("incoming") or {}).get("workflow"))
        if isinstance(child, str) and child.strip():
            names.add(child.strip())
    return sorted(names)


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


def build_pool(wf_rows, project_names):
    """Normalize every workflow doc once. Each pool entry carries its display name, id, resolved
    location, its raw `tasks` map, and the child workflow names it calls (childJob edges)."""
    pool = []
    for wf in wf_rows or []:
        if not isinstance(wf, dict) or not isinstance(wf.get("tasks"), dict):
            continue
        raw = wf.get("name") or ""
        loc_type, project_id, project_name, prefix_id, display = wf_location(wf, project_names)
        pool.append({
            "raw": raw,
            "display": display,
            "prefix_id": prefix_id,
            "workflow_id": wf.get("_id"),
            "location_type": loc_type,
            "project_id": project_id,
            "project_name": project_name,
            "tasks": wf.get("tasks") or {},
            "child_names": child_workflow_names(wf.get("tasks") or {}),
        })
    return pool


def seed_indices(pool, scope):
    """Indices of pool entries that DIRECTLY match the requested scope (before closure)."""
    mode = scope["mode"]
    if mode == "all":
        return set(range(len(pool)))
    seeds = set()
    if mode == "projects":
        want = set(scope["value"])
        for i, w in enumerate(pool):
            if (w["project_id"] in want) or (w["prefix_id"] in want):
                seeds.add(i)
    elif mode == "workflows":
        want = set(scope["value"])
        for i, w in enumerate(pool):
            if w["raw"] in want or w["display"] in want:
                seeds.add(i)
    return seeds


def resolve_scope(pool, scope):
    """Transitive-closure scope (req 3): start at the seed workflows and walk DOWN every childJob
    reference, pulling referenced children into scope — nothing else on the platform is analyzed.
    Returns (in_scope_indices, unresolved_children) where unresolved_children are child workflow
    names referenced from in-scope workflows but NOT present in the local pool (drives the skill's
    scoped-pull loop, and — as a last resort — a report warning)."""
    name_index = {}
    for i, w in enumerate(pool):
        name_index.setdefault(w["display"], []).append(i)
        if w["raw"] != w["display"]:
            name_index.setdefault(w["raw"], []).append(i)

    in_scope = set(seed_indices(pool, scope))
    unresolved = set()
    queue = list(in_scope)
    while queue:
        idx = queue.pop()
        for child_name in pool[idx]["child_names"]:
            matches = name_index.get(child_name)
            if not matches:
                unresolved.add(child_name)
                continue
            for m in matches:
                if m not in in_scope:
                    in_scope.add(m)
                    queue.append(m)
    return in_scope, sorted(unresolved)


def scan_workflows(wf_rows, instance_ids, prefixes, scope, project_names):
    pool = build_pool(wf_rows, project_names)
    in_scope, unresolved_children = resolve_scope(pool, scope)

    # call graph over the IN-SCOPE set only (rule 3 — never look outside scope): display-name -> the
    # in-scope indices that carry that name, so we can list a child's in-scope parent callers.
    scope_by_name = {}
    for i in in_scope:
        scope_by_name.setdefault(pool[i]["display"], []).append(i)
    callers = {}  # child index -> [parent index, ...]
    for i in in_scope:
        for child_name in pool[i]["child_names"]:
            for c in scope_by_name.get(child_name, []):
                callers.setdefault(c, [])
                if i not in callers[c]:
                    callers[c].append(i)

    workflows, n_tasks, adapter_names = [], 0, set()
    for i in sorted(in_scope):
        w = pool[i]
        tasks = w["tasks"]
        hits = []
        for tid, t in tasks.items():
            if tid in ("workflow_start", "workflow_end"):
                continue
            if not is_iag4_task(t, instance_ids, prefixes):
                continue
            iag4_type, code, rec = classify(t)
            iface = task_interface(t)
            if iface != "AG Manager":
                adapter_names.add(iface)
            hits.append({
                "task_id": tid,
                "task_name": t.get("name"),
                "app": t.get("app"),
                "summary": t.get("summary"),
                "interface": iface,                       # req (a): "AG Manager" or actual adapter name
                "iag4_type": iag4_type,               # internal: also drives the Repo-Structure section
                "code": code,                             # short remediation code (WRAP/REVIEW/ARGS/INV)
                "short_recommendation": rec,              # full text — used by the legend + checklist
                "referenced_by": find_referrers(tasks, tid),  # req (b)
            })
        if hits:
            hits.sort(key=lambda x: x["task_id"])
            # distinct interfaces (req a) in task-id order — factual AG Manager vs adapter, for the index
            interfaces = []
            for h in hits:
                if h["interface"] not in interfaces:
                    interfaces.append(h["interface"])
            # distinct recommendation codes for this workflow, in CODE_ORDER (for the group index)
            codes = [c for c in CODE_ORDER if any(h["code"] == c for h in hits)]
            called_by = [
                {"workflow_name": pool[p]["display"], "workflow_id": pool[p]["workflow_id"]}
                for p in callers.get(i, [])
            ]
            called_by.sort(key=lambda x: (x["workflow_name"], x["workflow_id"] or ""))
            workflows.append({
                "workflow_name": w["display"],
                "workflow_id": w["workflow_id"],
                "location_type": w["location_type"],
                "project_id": w["project_id"],
                "project_name": w["project_name"],
                "interfaces": interfaces,                 # req (a): distinct interfaces (AG Manager / adapter names)
                "codes": codes,                           # distinct recommendation codes (CODE_ORDER)
                "called_by": called_by,                   # req (c)
                "tasks": hits,
            })
            n_tasks += len(hits)
    workflows.sort(key=lambda w: (w["workflow_name"], w["project_id"] or "", w["workflow_id"] or ""))
    return workflows, n_tasks, unresolved_children, sorted(adapter_names)


def group_workflows(workflows):
    """Group the (already name-sorted) workflows by location so the report can headline each project
    then list its workflows. Deterministic: projects first (by project name, then id), then Global
    LAST; workflows within a group keep the flat name/id order. Each group carries a plain `label`
    ("project_name (project_id)" or "Global"), aggregate `n_workflows`/`n_tasks` counts (for the
    Workflows Summary table — the report renders these, never recomputes them), and the same
    workflow dicts (no data change)."""
    buckets = {}
    for w in workflows:
        if w["location_type"] == "project":
            key = ("0", w["project_name"] or "", w["project_id"] or "")
            label = "%s (%s)" % (w["project_name"], w["project_id"])
        else:
            key = ("1", "", "")
            label = "Global"
        if key not in buckets:
            buckets[key] = {
                "label": label,
                "location_type": w["location_type"],
                "project_id": w.get("project_id"),
                "project_name": w.get("project_name"),
                "workflows": [],
            }
        buckets[key]["workflows"].append(w)
    groups = [buckets[k] for k in sorted(buckets.keys())]
    for g in groups:
        g["n_workflows"] = len(g["workflows"])
        g["n_tasks"] = sum(len(w["tasks"]) for w in g["workflows"])
    return groups


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
    # Per-workflow, per-code counts (not per-task-name) — the checklist needs to say WHICH workflow
    # needs the work, not just how many tasks of a given kind exist across the whole environment.
    wf_items = []
    for w in workflows:
        counts = {}
        for t in w["tasks"]:
            counts[t["code"]] = counts.get(t["code"], 0) + 1
        for code, count in counts.items():
            wf_items.append({
                "code": code,
                "workflow_name": w["workflow_name"],
                "workflow_id": w["workflow_id"],
                "count": count,
            })
    # group by code (CODE_ORDER, matches the Recommended Actions legend) then workflow name/id
    wf_items.sort(key=lambda x: (CODE_ORDER.index(x["code"]), x["workflow_name"], x["workflow_id"] or ""))
    form_items = [
        {"form_name": f["form_name"], "field_key": f["field_key"],
         "bound_endpoint": f["bound_endpoint"], "recommendation": REC_FORM}
        for f in forms
    ]
    return {"workflows": wf_items, "forms": form_items}


def extract_workflows(obj):
    """Pull workflow docs out of an arbitrary local JSON value so the skill can run against files on
    disk with no API (local-files-only mode). Handles: a bare workflow doc (has a `tasks` map), a
    project export (`components[]` where type=="workflow" -> `document`), and list wrappers
    (`items`/`data`/`results`/`workflows` or a bare array)."""
    out = []
    if isinstance(obj, dict):
        if isinstance(obj.get("tasks"), dict):
            out.append(obj)
        for c in obj.get("components") or []:
            if isinstance(c, dict) and c.get("type") == "workflow" and isinstance(c.get("document"), dict):
                out.append(c["document"])
        for key in ("items", "data", "results", "workflows"):
            v = obj.get(key)
            if isinstance(v, list):
                for it in v:
                    out.extend(extract_workflows(it))
    elif isinstance(obj, list):
        for it in obj:
            out.extend(extract_workflows(it))
    return out


def load_local_workflows(dirs):
    """Scan every *.json in the given dirs for workflow docs. Deduped by _id (docs without an _id
    are all kept). Returns a list of workflow docs."""
    seen_ids, rows = set(), []
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json"):
                continue
            try:
                obj = load_json(os.path.join(d, fn))
            except (ValueError, OSError):
                continue
            for wf in extract_workflows(obj):
                wid = wf.get("_id")
                if wid and wid in seen_ids:
                    continue
                if wid:
                    seen_ids.add(wid)
                rows.append(wf)
    return rows


def parse_args(argv):
    p = argparse.ArgumentParser(description="Deterministic Gateway4 usage analysis (workflows + JSON forms).")
    p.add_argument("--tmp", required=True, help="tmp/output dir; also holds apps.json, adapters.json, json-forms.json and (live mode) wf_all.ndjson")
    p.add_argument("--out", help="output path (default <tmp>/analysis.json)")
    p.add_argument("--local", action="store_true",
                   help="local-files-only mode: no API was used; missing/unresolvable data becomes a warning, not a hard error")
    p.add_argument("--local-dir",
                   help="comma-separated dirs of *.json workflow/project-export files to scan (local mode); defaults to --tmp")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="scan every workflow (not recommended — bulk)")
    g.add_argument("--projects", help="comma-separated project ids (scope seed; closure follows childJob refs)")
    g.add_argument("--workflows", help="semicolon-separated workflow names (scope seed; closure follows childJob refs)")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    tmp = args.tmp
    warnings = []

    # Build the workflow pool. Live mode reads wf_all.ndjson (the scoped/paginated pull). Local mode
    # (and, additively, any run) reads workflow docs straight from local *.json files (bare workflow
    # docs, project exports, or list wrappers) so the skill can analyze a working directory with NO
    # API access at all.
    wf_path = os.path.join(tmp, "wf_all.ndjson")
    wf_rows = load_ndjson(wf_path) if os.path.exists(wf_path) else []
    local_dirs = [s.strip() for s in (args.local_dir or "").split(",") if s.strip()] or ([tmp] if args.local else [])
    if local_dirs:
        wf_rows = wf_rows + load_local_workflows(local_dirs)

    has_tasks = any(isinstance(w, dict) and isinstance(w.get("tasks"), dict) for w in wf_rows)

    if args.local:
        # LOCAL mode — never hard-fail on missing/empty data (req 4: analyze what's on disk, warn as a
        # last resort). If there is nothing to analyze, emit an empty report WITH a warning, exit 0.
        if not has_tasks:
            warnings.append(
                "local mode: no workflow documents found on disk (looked in: %s) — nothing to analyze. "
                "Point --local-dir at a directory of workflow/project-export JSON files." % ", ".join(local_dirs)
            )
    else:
        # LIVE mode — an empty or non-workflow ndjson is a FAILED PULL, not "no Gateway4 usage"
        # (almost always a silent auth failure: an OAuth token sent as a ?token= query param instead
        # of the 'Authorization: Bearer <token>' header, so every page 401'd). Fail loudly rather
        # than emitting a misleading all-zeros report. (A platform with genuinely zero Gateway4 usage
        # still has real workflows WITH a `tasks` object, so this guard never fires on a legit zero.)
        if not os.path.exists(wf_path):
            sys.stderr.write("error: %s not found — run the skill's pull step first (or pass --local)\n" % wf_path)
            return 2
        if not wf_rows:
            sys.stderr.write(
                "error: %s is empty — the workflow pull returned 0 workflows. Do NOT trust an all-zeros "
                "report; the pull failed. For OAuth (AUTH_METHOD=oauth) the token MUST be sent as an "
                "'Authorization: Bearer <token>' HEADER, never a ?token= query param. Re-run the Step 1 "
                "pull, confirm the ndjson line count matches the workflows 'total', then re-run this script.\n"
                % wf_path
            )
            return 2
        if not has_tasks:
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
    workflows, n_tasks, unresolved_children, adapter_names = scan_workflows(
        wf_rows, instance_ids, prefixes, scope, project_names)
    forms = scan_forms(os.path.join(tmp, "json-forms.json"), prefixes)
    devices = scan_devices(os.path.join(tmp, "devices.json"), instance_ids)
    checklist = build_checklist(workflows, forms)

    # Referenced child workflows we could NOT find in the pool. In live mode the skill's closure loop
    # should pull them and re-run; anything still unresolved (or all of them in local mode) becomes a
    # last-resort report warning — the skill must NOT invent what those workflows contain.
    if unresolved_children:
        warnings.append(
            "referenced child workflow(s) not available for analysis: %s — could not follow these "
            "childJob references. Pull them into scope (live) or add their JSON to --local-dir, then "
            "re-run. Do NOT assume their contents." % ", ".join(unresolved_children)
        )

    result = {
        "identifiers": {
            "adapter_type": adapter_type,
            "adapter_instances": instance_ids,
            "adapter_route_prefixes": prefixes,
            "adapter_display_names": adapter_names,
            "app": IAG4_APP,
        },
        "scope": scope,
        "mode": "local" if args.local else "live",
        "counts": {
            "n_workflows": len(workflows),
            "n_iag4_tasks": n_tasks,
            "n_forms": len(forms),
            "n_iag4_devices": devices["n_iag4"],
        },
        "workflows": workflows,
        "workflow_groups": group_workflows(workflows),
        "forms": forms,
        "devices": devices,
        "checklist": checklist,
        "unresolved_children": unresolved_children,
        "warnings": warnings,
    }

    out = args.out or os.path.join(tmp, "analysis.json")
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=False)
        fh.write("\n")

    sys.stderr.write(
        "analyzed mode=%s scope=%s -> %d workflows, %d Gateway4 tasks, %d Gateway4 form fields, "
        "%d Gateway4-origin devices, %d unresolved children -> %s\n"
        % (result["mode"], scope["mode"], len(workflows), n_tasks, len(forms),
           devices["n_iag4"], len(unresolved_children), out)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
