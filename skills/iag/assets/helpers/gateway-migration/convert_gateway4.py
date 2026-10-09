#!/usr/bin/env python3
"""Generate the Gateway5 side of a Gateway4 -> Gateway5 migration.

Reads Gateway4's scripts, playbooks (with their schemas and source) and built-in inventory
(devices, groups) -- read-only -- and writes, into --out:

  services.yaml           Gateway5 decorators + services for every script and playbook, ready for
                          POST /gateway_manager/v1/gateways/{clusterId}/configuration/import
  repo/                   the service repository layout: scripts/<service>/ and
                          playbooks/<service>/ with the original files (playbooks retargeted to
                          `hosts: all`), an inventory.py that turns the Inventory Manager nodes
                          Gateway5 passes on stdin into Ansible hosts, ansible.cfg and requirements.txt
  inventory-nodes.json    body for POST /inventory_manager/v1/nodes/bulk: Gateway4 devices as
                          Inventory Manager nodes with broker attributes; passwords become
                          $SECRET references, never plain text
  conversion-report.md    what was converted automatically, and what a person must review

Sources (pick one):
  live   --gw4-url https://gw4:8083  with GW4_USERNAME / GW4_PASSWORD in the environment
         (read-only GETs: /scripts, /playbooks, /devices, /groups with detail=full)
  files  --from-dir DIR  containing scripts.json, playbooks.json, devices.json, groups.json saved
         from those same GETs

Deterministic: the same input always produces the same files. Never writes to Gateway4.
See conversion-guide.md in this folder for how each item migrates and how to import the output.
"""
import argparse
import ast
import json
import os
import re
import ssl
import sys
import urllib.request
from pathlib import Path

# Gateway4 ansible_network_os -> Inventory Manager itential_platform (netmiko device types)
PLATFORMS = {
    "arista.eos.eos": "arista_eos", "eos": "arista_eos",
    "cisco.ios.ios": "cisco_ios", "ios": "cisco_ios",
    "cisco.iosxr.iosxr": "cisco_xr", "iosxr": "cisco_xr",
    "cisco.nxos.nxos": "cisco_nxos", "nxos": "cisco_nxos",
    "junipernetworks.junos.junos": "juniper_junos", "junos": "juniper_junos",
}
# Gateway4 device variables that map onto broker attributes (the rest are kept as-is)
MAPPED_VARS = {"ansible_host", "ansible_user", "ansible_password", "ansible_ssh_pass",
               "ansible_network_os", "ansible_port"}
PASSWORD_VARS = ("ansible_password", "ansible_ssh_pass", "ansible_become_password",
                 "ansible_become_pass")

# Written next to every device playbook. When a workflow calls runService with `inventory`,
# Gateway5 passes the chosen Inventory Manager nodes on stdin; this turns them into hosts.
INVENTORY_SCRIPT = '''#!/usr/bin/env python3
"""Ansible inventory from the Inventory Manager nodes Gateway5 passes on stdin.

When a workflow calls runService with `inventory`, Gateway5 hands this script
{"inventory_nodes": [{"name", "attributes", "tags"}, ...]} on stdin. Each node becomes a
host named after the node, its tags become groups, every attribute becomes a host
variable, and the broker attributes (itential_host, itential_user, ...) fill in the
matching Ansible connection variables when the node doesn't set them itself.
"""
import json
import sys

# Inventory Manager itential_platform -> Ansible network OS
NETWORK_OS = {
    "arista_eos": "arista.eos.eos", "cisco_ios": "cisco.ios.ios", "cisco_xe": "cisco.ios.ios",
    "cisco_xr": "cisco.iosxr.iosxr", "cisco_nxos": "cisco.nxos.nxos",
    "juniper_junos": "junipernetworks.junos.junos",
}


def host_vars(attrs):
    hv = dict(attrs)
    for ansible, itential in (("ansible_host", "itential_host"), ("ansible_user", "itential_user"),
                              ("ansible_password", "itential_password")):
        if ansible not in hv and itential in attrs:
            hv[ansible] = attrs[itential]
    port = ((attrs.get("itential_driver_options") or {}).get("netmiko") or {}).get("port")
    if "ansible_port" not in hv and port:
        hv["ansible_port"] = port
    platform = attrs.get("itential_platform")
    if "ansible_network_os" not in hv and platform:
        hv["ansible_network_os"] = NETWORK_OS.get(platform, platform)
    return hv


def main():
    raw = "" if sys.stdin.isatty() else sys.stdin.read().strip()
    data = json.loads(raw) if raw else {}
    inventory = {"_meta": {"hostvars": {}}, "all": {"hosts": []}}
    for node in data.get("inventory_nodes") or []:
        name = node["name"]
        inventory["all"]["hosts"].append(name)
        inventory["_meta"]["hostvars"][name] = host_vars(node.get("attributes") or {})
        for tag in node.get("tags") or []:
            inventory.setdefault(tag, {"hosts": []})["hosts"].append(name)
    if "--host" in sys.argv:
        print(json.dumps(inventory["_meta"]["hostvars"].get(sys.argv[-1], {})))
    else:
        print(json.dumps(inventory))


if __name__ == "__main__":
    main()
'''


# ---------------------------------------------------------------- sources

def fetch_live(url, verify_tls):
    user, password = os.environ.get("GW4_USERNAME"), os.environ.get("GW4_PASSWORD")
    if not user or not password:
        sys.exit("Set GW4_USERNAME and GW4_PASSWORD for a live read of Gateway4.")
    base = url.rstrip("/") + "/api/v2.0"
    ctx = None if verify_tls else ssl._create_unverified_context()

    def call(method, path, body=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = token
        req = urllib.request.Request(base + path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            return json.loads(r.read().decode())

    token = call("POST", "/login", {"username": user, "password": password})["token"]
    out = {}
    for kind in ("scripts", "playbooks", "devices", "groups"):
        detail = "?detail=full" if kind in ("scripts", "playbooks") else ""
        out[kind] = call("GET", f"/{kind}{detail}", token=token).get("data", [])
    return out


def load_files(folder):
    out = {}
    for kind in ("scripts", "playbooks", "devices", "groups"):
        f = Path(folder) / f"{kind}.json"
        if not f.exists():
            out[kind] = []
            continue
        data = json.loads(f.read_text())
        out[kind] = data.get("data", data) if isinstance(data, dict) else data
    return out


# ---------------------------------------------------------------- helpers

def service_name(filename):
    stem = Path(filename).stem
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")


def effective_schema(item):
    schemas = item.get("schemas") or {}
    kind = item.get("effective_schema_type") or schemas.get("effective_schema_type")
    if kind and schemas.get(kind):
        return schemas[kind]
    return item.get("schema")


def argparse_flags(source):
    """Named flags a Python script declares with argparse: [(flag, spec)] in declaration order."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None, []
    flags, positionals = [], []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument"):
            continue
        names = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not names:
            continue
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        long = [n for n in names if n.startswith("--")]
        if not long:
            if not names[0].startswith("-"):
                positionals.append(names[0])
            continue
        spec = {"flag": long[0][2:]}
        if isinstance(kw.get("required"), ast.Constant):
            spec["required"] = bool(kw["required"].value)
        if isinstance(kw.get("default"), ast.Constant) and kw["default"].value is not None:
            spec["default"] = kw["default"].value
        if isinstance(kw.get("help"), ast.Constant):
            spec["description"] = str(kw["help"].value)
        t = kw.get("type")
        spec["type"] = {"int": "integer", "float": "number"}.get(getattr(t, "id", ""), "string")
        action = kw.get("action")
        if isinstance(action, ast.Constant) and action.value in ("store_true", "store_false"):
            spec["type"] = "boolean"
        flags.append(spec)
    return positionals, flags


def third_party_imports(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    std = set(getattr(sys, "stdlib_module_names", ()))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module.split(".")[0])
    return sorted(m for m in mods if m not in std)


def yaml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return json.dumps(v)
    return json.dumps(str(v))


def dump_yaml(obj, indent=0):
    """Minimal YAML writer for the services.yaml structure (dicts, lists, scalars)."""
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.extend(dump_yaml(v, indent + 1))
            elif isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}: {'{}' if isinstance(v, dict) else '[]'}")
            else:
                lines.append(f"{pad}{k}: {yaml_scalar(v)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                sub = dump_yaml(item, indent + 1)
                lines.append(f"{pad}- {sub[0].strip()}")
                lines.extend(sub[1:])
            else:
                lines.append(f"{pad}- {yaml_scalar(item)}")
    return lines


def decorator(name, properties, required):
    schema = {"$id": name, "$schema": "https://json-schema.org/draft/2020-12/schema",
              "type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return {"name": name, "schema": schema}


# ---------------------------------------------------------------- converters

def convert_script(item, repo_dir, args):
    name = service_name(item["name"])
    source = item.get("content") or ""
    schema = effective_schema(item) or {}
    order = schema.get("script_argument_order") or []
    props_in = schema.get("properties") or {}
    review, props, required = [], {}, []

    custom = [a for a in order if a != "argument_list"]
    if custom:
        # A Gateway4 schema with named arguments: each becomes a Gateway5 property named after
        # the flag Gateway4 put on the command line (its prefix).
        for arg in custom:
            spec = props_in.get(arg, {})
            prefix = (spec.get("prefix") or "").strip()
            flag = re.match(r"^--([A-Za-z0-9_-]+)=?$", prefix)
            if not flag:
                review.append(f"argument `{arg}` is positional on Gateway4 (prefix `{prefix or 'none'}`) — "
                              "give the script a named flag (argparse) and rename the property to match")
                continue
            prop = {"type": spec.get("type") if spec.get("type") in ("string", "boolean", "array", "number", "integer") else "string"}
            if spec.get("description"):
                prop["description"] = spec["description"]
            if spec.get("type") in ("array", "boolean") or spec.get("type") == "secret":
                review.append(f"argument `{arg}` is type `{spec.get('type')}` on Gateway4 — check how the script "
                              "receives it on Gateway5 (one `--flag value` per property; secrets belong in gateway secrets)")
            props[flag.group(1)] = prop
            if arg in (schema.get("required") or []):
                required.append(flag.group(1))
            if flag.group(1) != arg:
                review.append(f"workflows pass `{flag.group(1)}` instead of `{arg}`")
    else:
        positionals, flags = argparse_flags(source)
        if positionals is None:
            review.append("script is not valid Python 3 — inputs could not be read; write the decorator by hand")
        else:
            for f in flags:
                prop = {"type": f["type"]}
                if "description" in f:
                    prop["description"] = f["description"]
                if "default" in f:
                    prop["default"] = f["default"]
                props[f["flag"]] = prop
                if f.get("required"):
                    required.append(f["flag"])
                if f["type"] in ("number", "integer") and not f.get("required"):
                    review.append(f"`--{f['flag']}` is an optional {f['type']} — Gateway5 passes an unset property as "
                                  f"an empty string (the decorator default isn't applied), which argparse `type=` rejects; have workflows always pass it, "
                                  "or let the script accept an empty value")
                if f["type"] == "boolean":
                    review.append(f"`--{f['flag']}` is a store_true flag — Gateway5 always passes `--{f['flag']} <value>`; "
                                  "accept a value instead")
                if re.search(r"pass(word)?|secret|token|key", f["flag"], re.I):
                    review.append(f"`--{f['flag']}` carries a credential — read it from an environment variable "
                                  "injected from a gateway secret instead of an argument")
            if positionals or (not flags and re.search(r"sys\.argv\[", source)):
                review.append("script reads positional arguments — Gateway5 passes only named flags "
                              "(`--name value`); add argparse flags (code ARGS)")
            if not flags and not positionals and "sys.argv" not in source:
                review.append("no arguments detected — confirm the script takes no input")
    if (schema.get("properties") or {}).get("env_vars") and "env_vars" not in custom \
            and re.search(r"os\.environ|os\.getenv|getenv\(", source):
        review.append("Gateway4 callers may pass `env_vars` per run — Gateway5 sets environment only "
                      "statically (`runtime.env`) or from secrets; move per-run values to flags")

    folder = repo_dir / "scripts" / name
    folder.mkdir(parents=True, exist_ok=True)
    filename = Path(item.get("file") or item["name"]).name
    (folder / filename).write_text(source)
    service = {"name": name, "type": "python-script",
               "description": f"Migrated from the Gateway4 script {item['name']}",
               "repository": args.repo_name, "working-directory": f"scripts/{name}",
               "filename": filename, "decorator": name}
    deps = third_party_imports(source)
    if deps:
        (folder / "requirements.txt").write_text("\n".join(deps) + "\n")
        service["runtime"] = {"req-file": "requirements.txt"}
        review.append(f"third-party imports {', '.join(deps)} listed unpinned in requirements.txt — pin versions")
    return name, decorator(name, props, sorted(required)), service, review


def convert_playbook(item, repo_dir, args, inventory_names, local_names=frozenset()):
    name = service_name(item["name"])
    source = item.get("content") or ""
    review = []
    hosts = re.findall(r"^\s*-?\s*hosts:\s*(.+)$", source, re.M)
    targets = {h.strip().strip("'\"") for h in hosts}
    known = sorted(t for t in targets if t in inventory_names)
    local = sorted(t for t in known if t in local_names)
    is_local = bool(local) and len(local) == len(known)
    if is_local:
        # Gateway4 ran these against ansible_connection: local hosts -- on Gateway5 that's the gateway itself
        retargeted = re.sub(r"^(\s*-?\s*hosts:\s*)(.+)$", lambda m: m.group(1) + "localhost", source, flags=re.M)
        review.append(f"`hosts: {', '.join(local)}` only held `ansible_connection: local` hosts — retargeted to "
                      "`hosts: localhost` (runs on the gateway); no device parameters needed")
        known = []
    else:
        retargeted = re.sub(r"^(\s*-?\s*hosts:\s*)(.+)$",
                            lambda m: m.group(1) + ("all" if m.group(2).strip().strip("'\"") in inventory_names else m.group(2)),
                            source, flags=re.M)
    if known:
        review.append(f"`hosts: {', '.join(known)}` (Gateway4 inventory) retargeted to `hosts: all` — the workflow "
                      "chooses the devices by passing Inventory Manager nodes in runService's `inventory`")
    others = sorted(t for t in targets if t not in inventory_names and t != "all")
    if others:
        review.append(f"`hosts: {', '.join(others)}` isn't a Gateway4 device or group — check the target")

    schema = effective_schema(item) or {}
    props, required = {}, []
    for k, v in (schema.get("properties") or {}).items():
        if k in ("hosts", "groups"):
            continue
        props[k] = {"type": v.get("type", "string")} | ({"description": v["description"]} if v.get("description") else {})
    for k in schema.get("required") or []:
        if k in props and k not in required:
            required.append(k)

    folder = repo_dir / "playbooks" / name
    folder.mkdir(parents=True, exist_ok=True)
    filename = Path(item.get("file") or f"{item['name']}.yml").name
    (folder / filename).write_text(retargeted)
    runtime = {"config-file": "ansible.cfg", "req-file": "requirements.txt",
               "env": {"ANSIBLE_HOST_KEY_CHECKING": "false"}}
    if not is_local:
        runtime = {"inventory": ["inventory.py"]} | runtime
        (folder / "inventory.py").write_text(INVENTORY_SCRIPT)
        (folder / "inventory.py").chmod(0o755)
    (folder / "ansible.cfg").write_text("[defaults]\nhost_key_checking = False\nstdout_callback = ansible.posix.json\n")
    (folder / "requirements.txt").write_text("# the full package: ansible-playbook plus vendor collections\nansible\n")
    service = {"name": name, "type": "ansible-playbook",
               "description": f"Migrated from the Gateway4 playbook {item['name']}",
               "repository": args.repo_name, "working-directory": f"playbooks/{name}",
               "playbooks": [filename], "decorator": name, "runtime": runtime}
    return name, decorator(name, props, required), service, review


def convert_inventory(devices, groups, args):
    tags = {}
    for g in groups:
        for d in g.get("devices") or []:
            tags.setdefault(d, []).append(g["name"])
    nodes, review = [], []
    for d in sorted(devices, key=lambda x: x["name"]):
        v = d.get("variables") or {}
        if v.get("ansible_connection") == "local":
            review.append(f"`{d['name']}` uses `ansible_connection: local` — not a network device; not migrated")
            continue
        attrs = {"itential_driver": "netmiko", "cluster_id": args.cluster_id}
        if "ansible_host" in v:
            attrs["itential_host"] = v["ansible_host"]
        if "ansible_user" in v:
            attrs["itential_user"] = v["ansible_user"]
        if any(p in v for p in PASSWORD_VARS):
            attrs["itential_password"] = f"{args.secret_prefix}.{d['name']}.password"
        nos = v.get("ansible_network_os")
        if nos in PLATFORMS:
            attrs["itential_platform"] = PLATFORMS[nos]
        elif nos:
            review.append(f"`{d['name']}`: no broker platform known for `{nos}` — set `itential_platform` by hand")
        if "ansible_port" in v:
            attrs["itential_driver_options"] = {"netmiko": {"port": v["ansible_port"]}}
        for k in sorted(v):
            if k not in MAPPED_VARS and k not in PASSWORD_VARS:
                attrs[k] = v[k]
        nodes.append({"name": d["name"], "attributes": attrs, "tags": sorted(tags.get(d["name"], []))})
    if any(any(p in (d.get("variables") or {}) for p in PASSWORD_VARS) for d in devices):
        review.append(f"passwords became `{args.secret_prefix}.<device>.password` references — create those "
                      "secrets in your secret provider before importing")
    return {"inventory_identifier": args.inventory_name, "nodes": nodes}, review


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--gw4-url", help="Gateway4 base URL (read-only GETs; GW4_USERNAME/GW4_PASSWORD in env)")
    src.add_argument("--from-dir", help="folder with scripts.json, playbooks.json, devices.json, groups.json")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--repo-name", default="gateway5-services", help="repository name in services.yaml")
    ap.add_argument("--repo-url", default="<your service repository URL>", help="git URL the Gateway5 cluster clones")
    ap.add_argument("--repo-ref", default="main")
    ap.add_argument("--cluster-id", default="<your Gateway5 cluster id>")
    ap.add_argument("--inventory-name", default="gateway4-migrated")
    ap.add_argument("--secret-prefix", default="$SECRET.gateway4_migration")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification for --gw4-url")
    args = ap.parse_args()

    data = fetch_live(args.gw4_url, not args.insecure) if args.gw4_url else load_files(args.from_dir)
    out = Path(args.out)
    repo = out / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    inventory_names = {d["name"] for d in data["devices"]} | {g["name"] for g in data["groups"]}
    local_devices = {d["name"] for d in data["devices"] if (d.get("variables") or {}).get("ansible_connection") == "local"}
    local_names = local_devices | {g["name"] for g in data["groups"]
                                   if g.get("devices") and set(g["devices"]) <= local_devices}
    decorators, services, report = [], [], []
    for item in sorted(data["scripts"], key=lambda x: x["name"]):
        name, dec, svc, review = convert_script(item, repo, args)
        decorators.append(dec); services.append(svc)
        report.append(("script", item["name"], name, review))
    for item in sorted(data["playbooks"], key=lambda x: x["name"]):
        name, dec, svc, review = convert_playbook(item, repo, args, inventory_names, local_names)
        decorators.append(dec); services.append(svc)
        report.append(("playbook", item["name"], name, review))

    config = {"decorators": decorators,
              "repositories": [{"name": args.repo_name, "url": args.repo_url, "reference": args.repo_ref}],
              "services": services}
    (out / "services.yaml").write_text(
        "# Generated by convert_gateway4.py — review conversion-report.md before importing.\n"
        + "\n".join(dump_yaml(config)) + "\n")

    nodes, inv_review = convert_inventory(data["devices"], data["groups"], args)
    (out / "inventory-nodes.json").write_text(json.dumps(nodes, indent=2, sort_keys=False) + "\n")

    lines = ["# Gateway4 → Gateway5 conversion report", "",
             f"- Services: {len(services)} ({sum(1 for r in report if r[0] == 'script')} scripts, "
             f"{sum(1 for r in report if r[0] == 'playbook')} playbooks) → `services.yaml`, files in `repo/`",
             f"- Inventory: {len(nodes['nodes'])} devices → `inventory-nodes.json` (inventory `{args.inventory_name}`)",
             "", "Import: push `repo/` to the service repository, then "
             "`POST /gateway_manager/v1/gateways/{clusterId}/configuration/import` with the content of "
             "`services.yaml` (`validate: true` first). Create the inventory with `createBrokerActions: true`, "
             "then `POST /inventory_manager/v1/nodes/bulk` with `inventory-nodes.json`.", "",
             "## Services", "", "| Gateway4 | Type | Gateway5 service | Review |", "|---|---|---|---|"]
    for kind, original, name, review in report:
        lines.append(f"| `{original}` | {kind} | `{name}` | {'<br>'.join(review) if review else 'Converted automatically'} |")
    lines += ["", "## Inventory", ""]
    lines += [f"- {r}" for r in inv_review] or ["- Converted automatically"]
    (out / "conversion-report.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {out}/services.yaml ({len(services)} services), {out}/inventory-nodes.json "
          f"({len(nodes['nodes'])} devices), {out}/repo/, {out}/conversion-report.md")


if __name__ == "__main__":
    main()
