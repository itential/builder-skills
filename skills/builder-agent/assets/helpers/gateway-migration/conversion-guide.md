# Gateway4 → Gateway5 conversion guide

How to deliver what the `gateway4-to-gateway5` readiness report found. The report (and its
`tmp/analysis.json`) says **what** has to move; this guide says **how** each item moves. Used by:

- `/solution-arch-agent` — to design each item's target (Design, Section D/E of `solution-design.md`)
- `/iag` and `/builder-agent` — to build the Gateway5 services, the inventory, and the rewired workflows
- `/qa-agent` — to prove each migrated item behaves like the original (parity tests)

Wording: customer-facing documents say "Gateway4" / "Gateway5", like the readiness report.

---

## Start with the converter

`convert_gateway4.py` (next to this guide in the builder-agent and iag skills) generates the Gateway5
side from Gateway4 itself — read-only against Gateway4, it only writes files:

```bash
GW4_USERNAME=... GW4_PASSWORD=... python3 convert_gateway4.py --gw4-url https://gateway4:8083 \
  --out migration/ --repo-url <service repo URL> --cluster-id <Gateway5 cluster> --inventory-name <inventory>
# or, from exported JSON (GET /api/v2.0/{scripts,playbooks}?detail=full, /devices, /groups):
python3 convert_gateway4.py --from-dir exports/ --out migration/ ...
```

| Output | What it is | Next step |
|---|---|---|
| `services.yaml` | A decorator and a service for every script and playbook. Script inputs come from the script's Gateway4 schema, or — for Gateway4's generic `argument_list` — from the script's own `argparse` flags | Import through Gateway Manager (`validate: true` first) |
| `repo/` | `scripts/<service>/` and `playbooks/<service>/` with the original files, playbooks retargeted, plus `inventory.py` (Inventory Manager nodes → Ansible hosts), `ansible.cfg`, `requirements.txt` | Push to the service repository |
| `inventory-nodes.json` | Gateway4 devices as Inventory Manager nodes with broker attributes; passwords as `$SECRET.` references; groups as tags | Create the inventory (`createBrokerActions: true`), then `POST /inventory_manager/v1/nodes/bulk` |
| `conversion-report.md` | What converted automatically and what a person must review, per item | Resolve every review item before import |

The same input always produces the same files. Everything below explains what the converter does and
how to finish the items it flags.

---

## Rules for every migration

1. **Build alongside, cut over later.** Never edit the Gateway4 workflows in place. Build the migrated
   workflows as a **new project** (via `POST /automation-studio/projects/import`, Rule 11 in
   `AGENTS.md`), so the originals keep running until cutover — and rollback is simply "keep using the
   originals".
2. **Import Gateway5 services through the platform, not the gateway CLI.**
   `POST /gateway_manager/v1/gateways/{clusterId}/configuration/import` with
   `{"options": {"source": "content", "content": "<service YAML>", "validate": true}}` validates without
   changing anything; run it again with `"validate": false` to import (`"force": true` replaces services
   that already exist). `"source": "git"` with `{"git": {"url", "file", "reference"}}` imports a
   service file straight from the repo. No shell access to the gateway is needed.
3. **After every import, re-read the service list before running.** The platform keeps its own copy
   of each service. Until `GET /gateway_manager/v1/services` shows the service's new `id` (a few seconds
   after a `force` import), runs fail with *"… has an Id that does not match what was provided with your
   request"*. Wait for the new id; don't re-import.
4. **Services run from git.** Every migrated script and playbook lives in a git repository the gateway
   can reach — the report's *Recommended Repository Structure* (Option A, one repo) is the layout.
5. **Inventory moves to Inventory Manager — with broker actions.** See *Inventory* below.
6. **Credentials never move as plain text.** Gateway4 devices often carry `ansible_password` /
   `ansible_ssh_pass` in their variables. In Inventory Manager use secret references
   (`$SECRET.<provider path>`) for `itential_password`; in services, use gateway secrets injected as
   environment variables (`/iag` → *Secrets*).
7. **Prove each item before cutover** — same input through the Gateway4 path and the Gateway5 path,
   compared field by field (see *Parity tests*).

---

## Inventory (Gateway4 built-in inventory → Inventory Manager)

Gateway5 has no inventory of its own. Move Gateway4's devices and groups into an **Inventory Manager
inventory created with broker actions**:

```
POST /inventory_manager/v1/inventories
{"name": "<inventory>", "groups": ["<auth group>"], "defaultClusterId": "<cluster>", "createBrokerActions": true}
```

`createBrokerActions: true` adds the platform's standard device actions to the inventory —
`run-command`, `set-config`, `get-config`, `is-alive` — which run on the Gateway5 cluster against any
node in it. Then add the devices (`POST /inventory_manager/v1/nodes/bulk` — this **replaces** every
node in the inventory, so send them all in one call).

**Map Gateway4 device variables to broker attributes:**

| Gateway4 variable | Inventory Manager attribute |
|---|---|
| `ansible_host` | `itential_host` |
| `ansible_user` | `itential_user` |
| `ansible_password` / `ansible_ssh_pass` | `itential_password` — as a `$SECRET.` reference, never plain text |
| `ansible_network_os` (e.g. `arista.eos.eos`, `cisco.ios.ios`) | `itential_platform` (e.g. `arista_eos`, `cisco_ios`) |
| SSH `ansible_port` | `itential_driver_options.netmiko.port` |
| — | `itential_driver: netmiko` |
| — | `cluster_id: <Gateway5 cluster>` |
| Gateway4 group membership | node `tags` (one tag per Gateway4 group) |

Keep any other Gateway4 variables a playbook needs (e.g. `ansible_httpapi_port`) as extra attributes —
workflows read them and pass them to the playbook service (see REVIEW below).

---

## Workflow tasks, by remediation code

The readiness report gives every Gateway4 task a code. Each code has one migration pattern.

### WRAP — built-in device tasks and Ansible roles/modules

Gateway4's built-in device tasks map to Gateway5's broker actions on the Inventory Manager inventory:

| Gateway4 task (`AGManager`) | Gateway5 replacement | Input change |
|---|---|---|
| `itential_cli` running show commands (`_hosts`, `_groups`, `command`) | `GatewayManager.sendCommand` | `commands: [command]`; `inventory: [{"inventory": "<inv>", "nodeNames": _hosts}]` |
| `itential_cli` pushing configuration (`command` is config text, often `conf t` … `end`) | `GatewayManager.sendConfig` | `config: <the rendered text, one string>`; same `inventory` |
| `itential_set_config` (`_hosts`, `_groups`, `transactions`) | `GatewayManager.sendConfig` | `config: <config text>`; same `inventory` |
| `itential_get_config`, `itential_get_state`, `itential_get_info` | the inventory's `get-config` / `run-command` broker action | — |
| `netmikoSendCommand` (`host`, `command_string`, …) | `GatewayManager.sendCommand` | `host` → a node name in `inventory` |
| `netmikoSendConfigSet` (`host`, `config_commands`, …) | `GatewayManager.sendConfig` | `config_commands` joined into `config` |

`_groups` becomes the nodes carrying that group's tag. `inventory` is an array of objects, so build it
with `merge` (`inventory`, `nodeNames` from job variables) and wrap it with `arrayPush` — `$var` doesn't
resolve inside it. For `sendConfig` the node needs `itential_driver_options.netmiko.become: true` (the
converter maps it from Gateway4's `ansible_become`); without it every push times out waiting for the
config prompt. Worked, tested examples: the "Push Configuration" workflows in the asset library.

Output shapes differ, so re-point every task in the report's `referenced_by`:

| Path | Output |
|---|---|
| Gateway4 `itential_cli` | `stdout` |
| `GatewayManager.sendCommand` | `result.results[]` — one `{name, command, output, success}` per node and command |
| `GatewayManager.sendConfig` | `result.results[]` — one `{name, host, output, success}` per node; no overall `state` |
| Broker action (`run-command`, …) | `result.stdout` (the device's output as text) |

Two ways to move the tasks that read the old output:

1. **Re-point each one** — e.g. a success check becomes `query: "result.results"` `!=` `[]` and
   `query: "result.results[*].success"` `!contains` `false`. Best when few tasks read it.
2. **Rebuild the old shape** with one `runCode` task after `sendConfig` (`data: {"result":
   "$var.<task>.result"}`) that prints `{"completed": [{"icode": "AD.200", "response": [{"host",
   "status": "SUCCESS"|"FAILURE", "stdout"}]}]}`; point the consumers at it and prefix their queries
   with `stdout_json.` (its `result` is flat — no JSON-RPC envelope). Best when many tasks or
   transformations parse the Gateway4 shape. builder-agent has the script.

Either way, run the migrated check once against a push that can't land: a check like "not empty and
doesn't contain FAILURE" also passes when its query path resolves to nothing. And Gateway4's
`icode: "AD.200"` only meant the call reached the gateway — a workflow that checked only `icode`
never caught a rejected push, so its parity baseline is weaker than it looks.

Other Ansible roles or collection modules
(`cisco.ios_ios_command` and the like) are wrapped in a small playbook and migrated as **REVIEW**.

### REVIEW — Ansible playbooks (`AutomationGateway.runPlaybook`, `AGManager.<playbook>`)

The playbook usually needs one change, and the service needs a way to read its devices:

1. **Playbook:** change `hosts:` from a Gateway4 device or group name to `hosts: all` — the workflow
   chooses the devices at run time.
2. **Devices come from Inventory Manager, not the repo.** When a workflow calls `runService` with
   `inventory` (`[{"inventory": "<name>", "nodeNames": ["<node>"]}]`), Gateway5 passes those nodes to
   the service on stdin as `{"inventory_nodes": [{"name", "attributes", "tags"}, ...]}`. A playbook
   service reads them through a small inventory script in `runtime.inventory`; the converter writes
   one (`inventory.py`) next to each playbook. It makes each node a host named after the node, its
   tags groups, and every attribute a host variable, and fills `ansible_host`, `ansible_user`,
   `ansible_password`, `ansible_port` and `ansible_network_os` from the broker attributes. Gateway4
   connection variables (`ansible_httpapi_port`, `ansible_httpapi_use_ssl`, …) travel as node
   attributes, so nothing device-specific lives in the repo or in the service's parameters.
3. **Service:** `type: ansible-playbook`, a decorator for the playbook's own inputs only,
   `runtime.inventory: [inventory.py]`, and `runtime.req-file: requirements.txt` listing **`ansible`**
   (the full package — it brings `ansible-playbook` and the vendor collections such as `arista.eos`;
   the gateway has no Ansible of its own).
4. **Structured output:** add an `ansible.cfg` with `stdout_callback = ansible.posix.json` and point
   `runtime.config-file` at it. Setting `ANSIBLE_STDOUT_CALLBACK` in `runtime.env` has no effect — the
   playbook output stays plain text.
5. **Workflow:** `GatewayManager.runService` with `serviceName`, `clusterId`, `params` (the Gateway4
   task's `args`) and `inventory` naming the Inventory Manager inventory and the nodes that replace
   the Gateway4 task's `hosts` / `groups`.
6. **Output:** Gateway4's `runPlaybook` returned per-host structured results
   (`response[].results.ansible_facts…`). Gateway5 returns a JSON-RPC envelope whose
   `result.stdout` is the playbook's JSON output as a **string** (`plays[].tasks[].hosts.<host>…`,
   `stats`). Every task listed in the report's `referenced_by` for this task must be re-pointed:
   `query` `result.stdout`, then `parse` it.

### ARGS — scripts (`AutomationGateway.runScript`, `AGManager.<script>`)

On Gateway4 a script's inputs are described by a schema stored in Gateway4's database (`GET
/api/v2.0/scripts/{name}/schema`); Gateway4 builds the command line by walking
`script_argument_order` and putting each argument's `prefix` + value + `suffix` on it. On Gateway5
the inputs are a **decorator in `services.yaml`**, and every property is passed as
`--<property> <value>`. So:

1. **Schema → decorator.** A Gateway4 argument whose prefix is a flag (`--hosts ` or `--hosts=`)
   becomes a Gateway5 property named after that flag. A script that only has Gateway4's generic
   `argument_list` gets its properties from its own `argparse` flags (name, type, default, required,
   help). Positional arguments (no flag) need a code change — add an `argparse` flag (code ARGS).
2. **Optional numbers and booleans:** Gateway5 passes an unset property as an empty string — the
   decorator's `default` is not applied — so `--timeout ""` fails `argparse`'s `type=float`. Have
   workflows always pass such properties, or let the script accept an empty value. `store_true`
   switches don't fit `--flag <value>` either.
3. **Credentials and environment:** credential arguments move to gateway secrets injected as
   environment variables. Gateway4's per-run `env_vars` have no Gateway5 equivalent — static values go
   in `runtime.env`, per-run values become flags. A script that took device addresses or credentials
   as arguments can instead read the devices from stdin: when the workflow passes `inventory` to
   `runService`, the script receives `{"inventory_nodes": [...]}` with each node's attributes.
4. **Service:** `type: python-script`, the decorator, `runtime.req-file` for third-party imports.
5. **Workflow:** `GatewayManager.runService` with `params` built from the Gateway4 task's
   `argument_list` / `args`; downstream consumers re-pointed to `result.stdout` (a string). When the
   script prints JSON, Gateway5 also returns it parsed as `result.stdout_json`.

### INV — device and group management

Gateway4 tasks that add, remove or change devices and groups don't become services. Replace them with
Inventory Manager operations on the migrated inventory (nodes and tags) — see `/itential-inventory`.

---

## JSON forms

A form field bound to a Gateway4 endpoint (`/automationgateway/...`, `/agmanager/...`) returns nothing
once Gateway4 is gone. Rebind it to Inventory Manager — e.g. a device dropdown on
`/inventory_manager/v1/inventories/<inventory>/nodes` — following `/itential-json-forms`.

---

## Parity tests

For every migrated workflow, `/qa-agent` runs the original (Gateway4) and the migrated (Gateway5)
workflow with the same inputs against the same devices and compares the facts that matter — not the
raw output, whose shape differs by design. Example from the reference migration (Arista EOS facts
playbook, see *Worked example*):

| Fact | Gateway4 (`runPlaybook`) | Gateway5 (`runService`) |
|---|---|---|
| `ansible_net_hostname` | `ceos1` | `ceos1` |
| `ansible_net_model` | `cEOSLab` | `cEOSLab` |
| `ansible_net_version` | `4.36.2F-49692632.4362F.1 (engineering build)` | same |
| `ansible_net_serialnum` | `05521ABFAB0BF25118742E52916AB49B` | same |
| `ansible_net_system` | `eos` | `eos` |

Record each comparison in `test-report.md`. A parity failure goes back to `/builder-agent` like any
other failed test case.

---

## Cutover

Recorded in `as-built.md` as a checklist the customer runs:

1. Point triggers, automations and parent workflows at the migrated workflows.
2. Watch a full cycle of real runs.
3. Disable the Gateway4 adapter / AG Manager integration; keep it installed until rollback is no
   longer needed.
4. Remove Gateway4 devices from Configuration Manager origins once they're re-homed.

---

## Worked example

A real migration, verified against a live platform with Gateway4 and Gateway5 side by side:
**"Run Arista EOS Facts Playbook"** — one `AutomationGateway.runPlaybook` task (`playbookName:
arista_eos_facts`, `hosts: ["ceos1"]`), code REVIEW.

- Inventory: `ceos1`'s Gateway4 variables mapped to broker attributes in an inventory created with
  `createBrokerActions: true`; `run-command` → `show version` returned the device's identity through
  Gateway5.
- Playbook: copied unchanged except `hosts: ceos1` → `hosts: all`.
- Repo: `playbooks/arista-eos-facts/` with `arista_eos_facts.yml`, `inventory.py` and
  `requirements.txt` (`ansible`), as the converter writes them.
- Repo also carries `ansible.cfg` (`stdout_callback = ansible.posix.json`) for structured output.
- Run: `runService` with no parameters and `inventory: [{"inventory": "<inventory>", "nodeNames":
  ["ceos1"]}]` — the node's attributes became the Ansible host.
- Service: imported through `/gateway_manager/v1/gateways/{clusterId}/configuration/import`; the
  first run installed Ansible on the gateway (~40 s), later runs reuse it.
- Built-in task path: `send-command` with the Inventory Manager node returned `show version` and
  `show hostname` from the same device (the `itential_cli` replacement).
- Result: all five facts above matched between the Gateway4 and Gateway5 runs.
