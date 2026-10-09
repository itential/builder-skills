# Gateway4 → Gateway5 conversion guide

How to deliver what the `gateway4-to-gateway5` readiness report found. The report (and its
`tmp/analysis.json`) says **what** has to move; this guide says **how** each item moves. Used by:

- `/solution-arch-agent` — to design each item's target (Design, Section D/E of `solution-design.md`)
- `/iag` and `/builder-agent` — to build the Gateway5 services, the inventory, and the rewired workflows
- `/qa-agent` — to prove each migrated item behaves like the original (parity tests)

Wording: customer-facing documents say "Gateway4" / "Gateway5", like the readiness report.

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
| `itential_cli` (`_hosts`, `_groups`, `command`) | `GatewayManager.sendCommand` | `commands: [command]`; `inventory: [{"inventory": "<inv>", "nodeNames": _hosts}]` |
| `itential_set_config` (`_hosts`, `_groups`, `transactions`) | `GatewayManager.sendConfig` | `config: <config text>`; same `inventory` |
| `itential_get_config`, `itential_get_state`, `itential_get_info` | the inventory's `get-config` / `run-command` broker action | — |
| `netmikoSendCommand` (`host`, `command_string`, …) | `GatewayManager.sendCommand` | `host` → a node name in `inventory` |
| `netmikoSendConfigSet` (`host`, `config_commands`, …) | `GatewayManager.sendConfig` | `config_commands` joined into `config` |

`_groups` becomes the nodes carrying that group's tag. Output shapes differ, so re-point every task in
the report's `referenced_by`:

| Path | Output |
|---|---|
| Gateway4 `itential_cli` | `stdout` |
| `GatewayManager.sendCommand` | `result.results[]` — one `{name, command, output, success}` per node and command |
| Broker action (`run-command`, …) | `result.stdout` (the device's output as text) |

Other Ansible roles or collection modules
(`cisco.ios_ios_command` and the like) are wrapped in a small playbook and migrated as **REVIEW**.

### REVIEW — Ansible playbooks (`AutomationGateway.runPlaybook`, `AGManager.<playbook>`)

The playbook usually needs one change, and the service needs an inventory:

1. **Playbook:** change `hosts:` from a Gateway4 device or group name to `hosts: all` — the device is
   chosen at run time.
2. **Inventory file in the repo:** a one-host `inventory.yaml` whose values come from the service's
   input parameters:
   ```yaml
   all:
     hosts:
       device:
         ansible_host: "{{ device_host }}"
         ansible_network_os: "{{ device_network_os }}"
         ansible_user: "{{ device_username }}"
         ansible_password: "{{ device_password }}"   # or a gateway secret via lookup('env', ...)
         # plus whatever connection variables the playbook used on Gateway4
   ```
   Passing Inventory Manager nodes in `runService`'s `inventory` field does **not** populate Ansible's
   inventory for a playbook service — the run sees no hosts. Pass the device's attributes as
   parameters instead.
3. **Service:** `type: ansible-playbook`, a decorator declaring those parameters, `runtime.inventory:
   [inventory.yaml]`, and `runtime.req-file: requirements.txt` listing **`ansible`** (the full package —
   it brings `ansible-playbook` and the vendor collections such as `arista.eos`; the gateway has no
   Ansible of its own).
4. **Structured output:** add an `ansible.cfg` with `stdout_callback = ansible.posix.json` and point
   `runtime.config-file` at it. Setting `ANSIBLE_STDOUT_CALLBACK` in `runtime.env` has no effect — the
   playbook output stays plain text.
5. **Workflow:** read the node from Inventory Manager (`InventoryManager.getNodesByInventory`, with
   `params: {}`), pick out its attributes with `query`, then `GatewayManager.runService` with
   `serviceName`, `clusterId`, `params` (the device attributes plus the Gateway4 task's `args`) and
   `inventory: ""`.
6. **Output:** Gateway4's `runPlaybook` returned per-host structured results
   (`response[].results.ansible_facts…`). Gateway5 returns a JSON-RPC envelope whose
   `result.stdout` is the playbook's JSON output as a **string** (`plays[].tasks[].hosts.<host>…`,
   `stats`). Every task listed in the report's `referenced_by` for this task must be re-pointed:
   `query` `result.stdout`, then `parse` it.

### ARGS — scripts (`AutomationGateway.runScript`, `AGManager.<script>`)

1. **Script:** inputs become named flags (`--device_ip`, not `sys.argv[1]`) whose names match the
   decorator's property names exactly, underscores included. Print one JSON object to stdout.
   Scripts that took credentials as arguments read them from environment variables instead (gateway
   secrets).
2. **Service:** `type: python-script`, decorator, `runtime.req-file`.
3. **Workflow:** `GatewayManager.runService` with `params` built from the Gateway4 task's
   `argument_list` / `args`; downstream consumers re-pointed to `result.stdout` (a string — parse it).

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
- Repo: `ansible/arista_eos_facts/` with `arista_eos_facts.yml`, `inventory.yaml` (above) and
  `requirements.txt` (`ansible`).
- Repo also carries `ansible.cfg` (`stdout_callback = ansible.posix.json`) for structured output.
- Service: imported through `/gateway_manager/v1/gateways/{clusterId}/configuration/import`; the
  first run installed Ansible on the gateway (~40 s), later runs reuse it.
- Built-in task path: `send-command` with the Inventory Manager node returned `show version` and
  `show hostname` from the same device (the `itential_cli` replacement).
- Result: all five facts above matched between the Gateway4 and Gateway5 runs.
