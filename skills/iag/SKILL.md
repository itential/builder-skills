---
name: iag
description: Build and run IAG (Itential Automation Gateway) services — Python scripts, Ansible playbooks, OpenTofu plans. YAML-driven service definitions, imported with iagctl. Call services from Itential workflows via GatewayManager.
argument-hint: "[action or service-name]"
---

# IAG — Itential Automation Gateway

IAG exposes Python scripts, Ansible playbooks, and OpenTofu plans as REST APIs. Everything is defined in YAML, imported with `iagctl db import`.

```
Write YAML → iagctl db import → Services available → Workflows call them
```

---

## Gotchas

- **`clusterId` must match** the IAG cluster config — discover with `GET /gateway_manager/v1/gateways/`
- **`params` maps to decorator schema** — check with `iagctl run service <type> <name> --use`
- **`inventory` is `""` (empty string)** when not targeting nodes, not `[]` or `null`
- **OpenTofu services require `action: apply|plan|destroy`** in the service YAML — field names are `vars` and `var-files` (NOT `plan-vars` / `plan-var-files`)
- **`runService` result is JSON-RPC wrapped** — extract with `query` path `result.stdout`, not `stdout`
- **`stdout` is always a string** — even when a Python script prints valid JSON, `result.stdout` is a string (e.g., `"{\"hostname\":\"Router1\"}"`). You must parse it before referencing fields inside it. Use a `parse` task (WorkFlowEngine) or `transformation` to convert the JSON string to an object.
- **`req-file` path is relative to `working-directory`** — if `working-directory: scripts`, then `req-file: requirements.txt` looks for `scripts/requirements.txt` inside the cloned repo, not the repo root
- **`$var` doesn't resolve inside `newVariable` objects** — use separate `query` tasks instead
- **Secrets in YAML files contain raw values** — prefer `iagctl create secret --prompt-value`. Keep `secrets:` out of `services.yaml` so `--force` never overwrites them.
- **Import is additive** — use `--force` to overwrite existing services
- **`--force` overwrites secrets too** — placeholder secrets replace real ones
- **Decorators reject unknown params** — every `--set` key must exist in the decorator schema
- **Validate first** — always run `iagctl db import file.yaml --validate` before importing
- **Ansible `network_cli` needs `paramiko` + `look_for_keys = False`** — add `paramiko` to `runtime.req-file` (requirements.txt), and in `ansible.cfg` add `[paramiko_connection]\nlook_for_keys = False`. Without `look_for_keys = False`, password auth fails with "No existing session". Use `cisco.iosxr.iosxr_command` (or `ansible.netcommon.cli_command`) for show commands — NOT `ansible.builtin.raw`
- **OpenTofu CLI syntax differs** — `iagctl run service opentofu-plan apply <name> --set key=value` (the `apply`/`destroy` subcommand goes between the type and service name)
- **OpenTofu results include `state_file`** — outputs are in `state_file.outputs`, not `result.stdout` like Python/Ansible

## How It Works

1. **Write a YAML service file** — defines repos, decorators, secrets, services
2. **`iagctl db import`** — loads into IAG
3. **`iagctl run service`** — test from CLI
4. **`GatewayManager.runService`** — call from Itential workflows

**Always start from a helper template.** Read the matching example from `${CLAUDE_PLUGIN_ROOT}/helpers/iag/` first, then modify:
- Python service → `${CLAUDE_PLUGIN_ROOT}/helpers/iag/example-python-service.yaml`
- Ansible service → `${CLAUDE_PLUGIN_ROOT}/helpers/iag/example-ansible-service.yaml`
- OpenTofu service → `${CLAUDE_PLUGIN_ROOT}/helpers/iag/example-opentofu-service.yaml`
- Multi-service chain → `${CLAUDE_PLUGIN_ROOT}/helpers/iag/example-multi-service-chain.yaml`
- Full schema reference → `${CLAUDE_PLUGIN_ROOT}/helpers/iag/service-file-schema.md`

**Do NOT build YAML from scratch. Read the helper first.**

---

## Authentication

| Mode | Auth | How |
|------|------|-----|
| **Local** | None needed | `iagctl` talks to local IAG directly |
| **Server/Client** | Login required | `iagctl login <username>` → interactive password prompt |
| **Itential workflows** | Pre-configured | Platform admin sets up gateway. `clusterId` references it. |

**The agent cannot run `iagctl login`** — it requires an interactive terminal. If the engineer hasn't logged in yet, tell them:
> "Run `iagctl login admin` in your terminal and enter your password. Once done, I can continue."

Quick check — if this works, you're authenticated:
```bash
iagctl get services
```

---

## Writing Service Files

### YAML Structure

A service file has these top-level sections (all optional — include only what you need):

```yaml
decorators: []      # Input schemas for services
repositories: []    # Git repos with code
services: []        # Python/Ansible/OpenTofu services
registries: []      # Package registries (PyPI, Galaxy)
secrets: []         # Credentials and keys
```

### Service Types

| Type | Key fields | Runs |
|------|-----------|------|
| `python-script` | `filename`, `runtime.env`, `runtime.req-file` | Python file from repo |
| `ansible-playbook` | `playbooks`, `runtime.inventory`, `runtime.env` | Ansible playbook(s) from repo |
| `opentofu-plan` | `action`, `vars`, `var-files`, `state-file` | OpenTofu apply/plan/destroy |
| `executable` | `filename`, `arg-format` | Custom executable |

### Python Script Services

**Complete service YAML with all common fields:**

```yaml
decorators:
  - name: my-service                       # should match service name
    schema:
      $id: my-service                      # should match service name
      $schema: https://json-schema.org/draft/202012/schema
      properties:
        device_ip:
          type: string
          description: "Target device IP"
          examples: ["10.0.0.1", "172.20.100.63"]
        device_type:
          type: string
          description: "Netmiko device type"
          enum: ["cisco_ios", "cisco_xr", "cisco_nxos"]
          default: "cisco_ios"
        interfaces:
          type: string
          description: "Comma-separated interface names"
      required:
        - device_ip
        - interfaces
      type: object

repositories:
  - name: my-repo
    url: https://github.com/org/repo.git
    reference: main

services:
  - name: my-service
    type: python-script
    description: Connects to device and returns interface health report
    filename: main.py
    working-directory: scripts              # directory containing main.py in repo
    repository: my-repo
    decorator: my-service                   # links to decorator above
    secrets:                                # injected as env vars at runtime
      - name: device-username
        type: env
        target: DEVICE_USERNAME             # script reads os.environ['DEVICE_USERNAME']
      - name: device-password
        type: env
        target: DEVICE_PASSWORD
    runtime:
      req-file: requirements.txt            # or pyproject.toml — installs dependencies
      env:                                  # extra environment variables
        NETMIKO_TIMEOUT: "30"
```

**Python script contract — how IAG runs your script:**

1. **Inputs arrive as `--property_name` CLI args.** Decorator schema property names become argparse flags. A property named `device_ip` becomes `--device_ip`.
2. **Credentials arrive as env vars** from the `secrets` block. Use `os.environ.get('DEVICE_USERNAME')`.
3. **Behavior selection via `runtime.env`** — use this to make one script serve multiple services (see pattern below).
4. **Output: JSON to stdout.** Always `print(json.dumps(result))`. Even on errors, return JSON with `"success": false`.
5. **Exit code:** 0 for any parseable result (success or handled error). 1 only for fatal setup failures (missing credentials).

**Script template:**

```python
#!/usr/bin/env python3
import argparse
import json
import os
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device_ip", required=True)
    parser.add_argument("--device_type", default="cisco_ios")
    parser.add_argument("--interfaces", required=True)
    args = parser.parse_args()

    username = os.environ.get("DEVICE_USERNAME")
    password = os.environ.get("DEVICE_PASSWORD")
    if not username or not password:
        print(json.dumps({"success": False, "error": "DEVICE_USERNAME and DEVICE_PASSWORD env vars required"}))
        sys.exit(1)

    try:
        result = {"success": True, "data": do_work(args, username, password)}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

if __name__ == "__main__":
    main()
```

**One-file-multi-service pattern:** Same Python file, different services with different `runtime.env`:

```yaml
services:
  - name: aws-ec2-add
    type: python-script
    filename: aws-ec2.py                   # same file
    working-directory: aws-operations
    repository: my-repo
    decorator: aws-ec2-add
    runtime:
      env:
        OPERATION: add                     # script checks os.environ.get('OPERATION')
        OUTPUT_FORMAT: json
    secrets:
      - name: aws_access_key_id
        type: env
        target: AWS_ACCESS_KEY_ID

  - name: aws-ec2-delete
    type: python-script
    filename: aws-ec2.py                   # same file
    working-directory: aws-operations
    repository: my-repo
    decorator: aws-ec2-delete
    runtime:
      env:
        OPERATION: delete                  # different operation
        OUTPUT_FORMAT: json
    secrets:
      - name: aws_access_key_id
        type: env
        target: AWS_ACCESS_KEY_ID
```

The script checks env vars first, then falls back to argparse:
```python
operation = os.environ.get('OPERATION') or args.op
```

### Ansible Playbook Services

**Complete service YAML — `runtime` block is critical for Ansible:**

```yaml
decorators:
  - name: sros-config
    schema:
      $id: sros-config
      $schema: https://json-schema.org/draft/202012/schema
      properties:
        sros_cli_commands:
          type: array
          items:
            type: string
          minItems: 1
          description: "CLI commands to execute"
        target_hosts:
          type: string
          description: "Target hosts or inventory groups"
          default: "all"
      required:
        - sros_cli_commands
      type: object

repositories:
  - name: my-ansible-repo
    url: git@github.com:org/ansible-playbooks.git
    private-key-name: git-ssh-key

services:
  - name: sros-config
    type: ansible-playbook
    description: Execute CLI commands on Nokia SROS devices
    playbooks:
      - sros_config.yml                    # one playbook per service (array but always single)
    working-directory: sros_config         # directory containing the playbook
    repository: my-ansible-repo
    decorator: sros-config
    runtime:
      inventory:                           # REQUIRED for Ansible — inventory file(s)
        - inventory.yaml
      config-file: ansible.cfg             # optional — custom ansible config
      env:                                 # IMPORTANT — controls Ansible behavior
        ANSIBLE_HOST_KEY_CHECKING: "false"  # disable SSH host key checking
        ANSIBLE_STDOUT_CALLBACK: json       # JSON output — critical for structured results
```

**Ansible service with secrets (SSH key injection):**

```yaml
services:
  - name: linux-patch-check
    type: ansible-playbook
    playbooks:
      - patch_check.yml
    working-directory: linux_patch_check
    repository: my-ansible-repo
    decorator: linux-patch-check
    secrets:
      - name: SELAB-PEM                    # secret name in IAG
        type: env
        target: SELAB-PEM                  # playbook reads with lookup('env', 'SELAB-PEM')
    runtime:
      inventory:
        - inventory.yaml
      env:
        ANSIBLE_HOST_KEY_CHECKING: "false"
        ANSIBLE_STDOUT_CALLBACK: json
```

The playbook writes the injected key to a temp file:
```yaml
- name: Write PEM to temp file
  ansible.builtin.copy:
    content: "{{ lookup('env', 'SELAB-PEM') }}"
    dest: "/tmp/ssh_key.pem"
    mode: '0600'
```

**Multiple services sharing a working-directory** — different playbooks in the same directory:

```yaml
services:
  - name: linux-patch-check
    playbooks: [patch_check.yml]
    working-directory: linux_patch_check   # same directory
    # ...
  - name: linux-execute-patch
    playbooks: [execute_patch.yml]
    working-directory: linux_patch_check   # same directory
    # ...
  - name: linux-mock-patch
    playbooks: [mock_patch.yml]
    working-directory: linux_patch_check   # same directory
    # ...
```

**Ansible runtime options** (all optional, in the `runtime:` block):

| Field | Purpose | Example |
|-------|---------|---------|
| `inventory` | Inventory file(s) | `["inventory.yaml"]` |
| `config-file` | ansible.cfg path | `"ansible.cfg"` |
| `env` | Environment variables | `{ANSIBLE_HOST_KEY_CHECKING: "false"}` |
| `req-file` | pip requirements or ansible-galaxy requirements.yml | `"requirements.txt"` or `"requirements.yml"` |
| `extra-vars` | Extra variables | `["env=prod"]` |
| `extra-vars-file` | Variable files | `["vars.yml"]` |
| `check` | Dry-run mode | `false` |
| `diff` | Show diffs | `true` |
| `forks` | Parallel processes | `10` |
| `tags` | Run only these tags | `"webservers"` |
| `limit` | Limit to hosts | `["host1"]` |

**Ansible `network_cli` for network devices (Cisco XR, IOS, NXOS, Nokia SROS):**

Use `network_cli` connection with vendor modules (e.g., `cisco.iosxr.iosxr_command`, `ansible.netcommon.cli_command`). This is the recommended approach for network devices.

Required files in the working directory:

`requirements.txt` — pip dependencies for `network_cli`:
```
paramiko
```

`ansible.cfg` — must include `look_for_keys = False` for password auth:
```ini
[defaults]
host_key_checking = False
stdout_callback = json
timeout = 30

[persistent_connection]
connect_timeout = 30
command_timeout = 30

[paramiko_connection]
look_for_keys = False
```

`inventory.yaml` — use Jinja2 refs to decorator schema properties:
```yaml
all:
  children:
    xr_device:
      hosts:
        xr-router:
          ansible_host: "{{ device_ip }}"
          ansible_user: "{{ device_username }}"
          ansible_password: "{{ device_password }}"
          ansible_connection: network_cli
          ansible_network_os: cisco.iosxr.iosxr
          ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
          ansible_host_key_checking: false
          ansible_paramiko_host_key_checking: false
```

`health_check.yml` — playbook using vendor module:
```yaml
---
- name: Cisco XR Health Check
  hosts: xr_device
  gather_facts: false

  tasks:
    - name: Run show commands
      cisco.iosxr.iosxr_command:
        commands:
          - show version
          - show platform
          - show ip interface brief
      register: command_output

    - name: Display results
      ansible.builtin.debug:
        msg:
          device_ip: "{{ ansible_host }}"
          show_version: "{{ command_output.stdout[0] }}"
          show_platform: "{{ command_output.stdout[1] }}"
          show_ip_interface_brief: "{{ command_output.stdout[2] }}"
```

`services.yaml` — wire it all together with `runtime.req-file`:
```yaml
services:
  - name: xr-health-check
    type: ansible-playbook
    playbooks:
      - health_check.yml
    working-directory: playbooks
    repository: xr-health-check-repo
    decorator: xr-health-check
    runtime:
      inventory:
        - inventory.yaml
      config-file: ansible.cfg
      req-file: requirements.txt
      env:
        ANSIBLE_HOST_KEY_CHECKING: "false"
        ANSIBLE_STDOUT_CALLBACK: json
```

**Key points:**
- `paramiko` in `requirements.txt` — IAG installs it in the service venv
- `look_for_keys = False` in `ansible.cfg` — fixes "No existing session" error with password auth
- `ansible_network_os` must match the vendor collection (e.g., `cisco.iosxr.iosxr`, `sros`)
- Inventory uses `{{ var }}` Jinja2 refs matching decorator schema property names
- `runtime.req-file` can be a pip `requirements.txt` or ansible-galaxy `requirements.yml`

### OpenTofu Plan Services

**Complete service YAML — note the correct field names:**

```yaml
decorators:
  - name: azure-landing-zone
    schema:
      $id: azure-landing-zone
      $schema: https://json-schema.org/draft/202012/schema
      properties:
        resource_group_name:
          type: string
          description: "Resource group name"
          default: "lz-demo-rg"
        vnet_address_space:
          type: array
          items:
            type: string
            pattern: "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"
          default: ["10.0.0.0/16"]
      required:
        - resource_group_name
      type: object

repositories:
  - name: my-tofu-repo
    url: git@github.com:org/opentofu.git
    private-key-name: git-ssh-key

services:
  - name: azure-landing-zone
    type: opentofu-plan
    description: Deploy Azure landing zone infrastructure
    working-directory: infra/modules/landing-zone   # directory with .tf files
    repository: my-tofu-repo
    decorator: azure-landing-zone
    action: apply                          # REQUIRED: apply, plan, or destroy
    vars: []                               # optional: ["-var flags"] e.g. ["region=us-east-1"]
    var-files: []                          # optional: ["-var-file flags"] e.g. ["prod.tfvars"]
    state-file: null                       # optional: custom state file path
```

**IMPORTANT — field names:** The fields are `vars` and `var-files`, NOT `plan-vars` / `plan-var-files`. The `action` field is required.

**Secrets for cloud credentials use the `TF_VAR_` convention:**

```yaml
services:
  - name: deploy-infra
    type: opentofu-plan
    working-directory: infra
    repository: my-tofu-repo
    decorator: deploy-infra
    action: apply
    vars: []
    var-files: []
    state-file: null
    secrets:
      - name: aws-access-key
        type: env
        target: TF_VAR_aws_access_key     # OpenTofu reads TF_VAR_* as variables
      - name: aws-secret-key
        type: env
        target: TF_VAR_aws_secret_key
```

**Decorator params pass directly as OpenTofu variables** — each property in the decorator schema becomes a variable available to your `.tf` files. Backend/provider config lives in the `.tf` files, not the service YAML.

### Decorators — Input Validation

Every service should have a decorator. The `$id` should match the service name:

```yaml
decorators:
  - name: my-service
    schema:
      $id: my-service                      # match service name, not "root"
      $schema: https://json-schema.org/draft/202012/schema
      properties:
        device_ip:
          type: string
          description: "Target device IP"
        format:
          type: string
          enum: ["json", "table"]          # restricted values
          default: "json"
        commands:
          type: array                      # array with item validation
          items:
            type: string
          minItems: 1
        verbose:
          type: string
          enum: ["true", "false"]          # booleans as strings (common pattern)
          default: "false"
      required:
        - device_ip
      type: object
      additionalProperties: false          # reject unknown params (recommended)
```

### Adding Secrets

**Best practice:** Never put real secret values in YAML. Define secret references in the service, create actual secrets separately.

```yaml
# In services.yaml — only references, no values
services:
  - name: my-service
    type: python-script
    filename: main.py
    working-directory: scripts
    repository: my-repo
    secrets:                               # injected as env vars at runtime
      - name: api-token                    # secret name in IAG
        type: env
        target: API_TOKEN                  # script reads os.environ['API_TOKEN']
```

```bash
# Create secrets separately — never in the YAML file
iagctl create secret api-token --prompt-value
```

**WARNING:** `--force` import overwrites secrets too. If your YAML has a top-level `secrets:` section with placeholder values, `--force` will replace real secrets with placeholders. **Keep the top-level `secrets:` section out of `services.yaml` entirely.** Only define secret references inside each service's `secrets:` array.

### Private Git Repos

```yaml
repositories:
  # SSH auth (most common):
  - name: private-repo
    url: git@github.com:org/private.git
    private-key-name: git-ssh-key          # name of secret holding SSH key
    reference: main

  # HTTPS auth:
  - name: https-repo
    url: https://github.com/org/repo.git
    username: myuser
    password-name: git-password            # name of secret holding password
```

Create the SSH key secret separately: `iagctl create secret git-ssh-key --prompt-value`

---

## Import / Export

```bash
# Validate only (no changes)
iagctl db import services.yaml --validate

# Dry run with checks
iagctl db import services.yaml --check

# Import (additive — new added, existing skipped)
iagctl db import services.yaml

# Import with overwrite (existing replaced by name)
iagctl db import services.yaml --force

# Export current state
iagctl db export state.yaml

# Import directly from Git repo
iagctl db import --repository https://github.com/org/repo.git --reference main
```

**Import behavior:**
- New resources → **added**
- Existing (same name) → **skipped** without `--force`, **replaced** with `--force`
- Resources not in the YAML → **untouched** (never deleted)

---

## Development Loop

When iterating on service code, every change requires pushing to Git and re-importing — IAG pulls code from the repo, not from local files.

```
Edit code → git commit + push → iagctl db import services.yaml --force → iagctl run service → repeat
```

**Tip:** Keep secrets out of `services.yaml` so `--force` imports don't clobber them (see Secrets warning above).

---

## Testing Services (CLI)

```bash
# List services
iagctl get services
iagctl get services --type python-script

# See what inputs a service expects
iagctl run service python-script my-service --use

# Run with inputs
iagctl run service python-script my-service \
  --set device_ip=10.0.0.1 \
  --set device_type=ios

# Ansible
iagctl run service ansible-playbook my-playbook --set target_host=router1

# OpenTofu apply
iagctl run service opentofu-plan apply my-plan --set region=us-east-1

# OpenTofu destroy
iagctl run service opentofu-plan destroy my-plan

# Raw JSON output
iagctl run service python-script my-service --raw
```

---

## Calling IAG from Itential Workflows

### Finding the clusterId

The `clusterId` is required for all GatewayManager tasks. Discover it via the platform API:

```
GET /gateway_manager/v1/gateways/
```

This returns the list of configured gateway clusters. Use the cluster name as the `clusterId` value in workflow tasks.

### GatewayManager Tasks

| Task | What it does |
|------|-------------|
| `runService` | Run an IAG service by name |
| `sendCommand` | Send CLI commands to inventory nodes |
| `sendConfig` | Send config text to inventory nodes |
| `getServices` | List available services |
| `getGateways` | List connected gateways |

### runService Task Wiring

```json
{
  "name": "runService",
  "app": "GatewayManager",
  "type": "automatic",
  "location": "Application",
  "displayName": "GatewayManager",
  "actor": "Pronghorn",
  "variables": {
    "incoming": {
      "serviceName": "device-info",
      "clusterId": "ankitcluster",
      "params": {"device_ip": "10.0.0.1", "device_type": "ios"},
      "inventory": ""
    },
    "outgoing": {
      "result": "$var.job.iagResult"
    }
  }
}
```

**Incoming:**
| Field | Type | Description |
|-------|------|-------------|
| `serviceName` | string | IAG service name (same name as in YAML/iagctl) |
| `clusterId` | string | Gateway cluster ID — ask the engineer |
| `params` | object | Key/value inputs matching the decorator schema |
| `inventory` | array or `""` | Target nodes: `[{"inventory": "inv-name", "nodeNames": ["node1"]}]` or `""` if not needed |

**Outgoing:**
| Field | Type | Description |
|-------|------|-------------|
| `result` | object | JSON-RPC envelope with service execution result |

### Result Shape — JSON-RPC Wrapper

`runService` returns a JSON-RPC envelope, NOT raw stdout:

```json
{
  "id": "dc7c4a5d-...",
  "jsonrpc": "2.0",
  "result": {
    "return_code": 0,
    "stdout": "{ ... script output ... }",
    "stderr": "",
    "start_time": "2026-03-03T19:26:37Z",
    "end_time": "2026-03-03T19:26:37Z",
    "elapsed_time": 0.659
  },
  "status": "completed"
}
```

**To extract stdout in a workflow:** use a `query` task with path `result.stdout`:

```json
{
  "name": "query",
  "app": "WorkFlowEngine",
  "type": "operation",
  "variables": {
    "incoming": {
      "pass_on_null": false,
      "query": "result.stdout",
      "obj": "$var.job.iagResult"
    },
    "outgoing": {
      "return_data": "$var.job.serviceOutput"
    }
  }
}
```

### Chaining Services in a Workflow

Pass output from one service as input to the next:

```
runService(device-info)
    → query: extract result.stdout → parse JSON
        → runService(config-generator) with params from previous output
            → query: extract result.stdout
                → runService(config-validator)
```

Each `query` extracts `result.stdout` from the JSON-RPC envelope. If the stdout is JSON, parse it before passing as params to the next service.

### sendCommand Task Wiring

```json
{
  "name": "sendCommand",
  "app": "GatewayManager",
  "type": "automatic",
  "actor": "Pronghorn",
  "variables": {
    "incoming": {
      "clusterId": "ankitcluster",
      "commands": ["show version", "show ip interface brief"],
      "inventory": [{"inventory": "my-inventory", "nodeNames": ["router1"]}]
    },
    "outgoing": {
      "result": "$var.job.commandResult"
    }
  }
}
```

### sendConfig Task Wiring

```json
{
  "name": "sendConfig",
  "app": "GatewayManager",
  "type": "automatic",
  "actor": "Pronghorn",
  "variables": {
    "incoming": {
      "clusterId": "ankitcluster",
      "config": "$var.job.renderedConfig",
      "inventory": [{"inventory": "my-inventory", "nodeNames": ["switch1"]}]
    },
    "outgoing": {
      "result": "$var.job.configResult"
    }
  }
}
```

### Testing IAG Services via Workflow

After CLI testing passes (`iagctl run service`), test the full workflow integration:

**1. Create the workflow** (runService → query to extract stdout):
```
POST /automation-studio/automations
```

**2. Start a job:**
```
POST /operations-manager/jobs/start
```
```json
{
  "workflow": "My IAG Workflow",
  "options": {
    "type": "automation",
    "variables": {
      "device_ip": "172.20.100.63",
      "device_type": "cisco_xr",
      "interfaces": "GigabitEthernet0/0/0/0",
      "clusterId": "ankitcluster"
    }
  }
}
```

**3. Check the job:**
```
GET /operations-manager/jobs/{jobId}
```
Verify:
- `data.status` is `"complete"` (not `"error"`)
- `data.error` is `null` (no task errors)
- `data.variables.serviceOutput` contains the extracted stdout from the IAG service

**If the job errors with "Service not found on cluster":** the `clusterId` is wrong. Check `GET /gateway_manager/v1/gateways/` for the correct cluster name.

---

## When to Use Which

| Need | Use |
|------|-----|
| Run a Python/Ansible/OpenTofu service | `GatewayManager.runService` |
| Send ad-hoc CLI commands | `GatewayManager.sendCommand` or `AGManager.itential_cli` |
| Push config text to device | `GatewayManager.sendConfig` or `AGManager.itential_set_config` |
| Run MOP validation checks | `MOP.RunCommandTemplate` (separate from IAG) |

### AGManager vs GatewayManager

| | AGManager | GatewayManager |
|---|-----------|---------------|
| **Tasks** | One per script/playbook (e.g., `itential_cli`) | Generic (`runService`, `sendCommand`) |
| **Input style** | Task-specific variables | `serviceName` + `params` object |
| **When to use** | Built-in IAG capabilities | Custom services built with iagctl |

---

## Operational Commands (Inspect, Verify, Clean Up)

After importing, use these to verify and manage resources:

```bash
# === LIST RESOURCES ===
iagctl get services
iagctl get services --type python-script
iagctl get services --type ansible-playbook
iagctl get services --type opentofu-plan
iagctl get repositories
iagctl get secrets
iagctl get decorators
iagctl get registries
iagctl get clusters                          # find clusterId for workflows

# === INSPECT A SPECIFIC RESOURCE ===
iagctl describe service <name>               # full details: repo, decorator, secrets, runtime
iagctl describe repository <name>            # URL, reference, auth method
iagctl describe decorator <name>             # JSON schema
iagctl describe secret <name>                # secret metadata (value redacted)

# === DELETE ===
iagctl delete service <name>
iagctl delete repository <name>
iagctl delete decorator <name>
iagctl delete secret <name>

# === EXPORT CURRENT STATE ===
iagctl db export current-state.yaml          # full dump of everything in IAG
```

**After every import, verify with:**
```bash
iagctl describe service <name>
```
This confirms the service was created with the correct repo, decorator, secrets, and working directory.

---

## Organizing Services for Teams

### Naming Conventions

```
Services:     {team}-{domain}-{action}        e.g. netops-device-health-check
Decorators:   {service-name}                  e.g. netops-device-health-check
Repositories: {team}-{purpose}                e.g. netops-automation
Secrets:      {team}-{system}-{purpose}        e.g. netops-git-ssh-key
```

Tag services: `tags: [team:netops, domain:network]` — filter with `iagctl get services --tag team:netops`

### Repository Layouts

| Layout | When | Structure |
|--------|------|-----------|
| **Standalone repo** | One service per repo | `services.yaml` at repo root, code in subdirectory |
| **Mono-repo** | < 20 services, one team | `.gateway/services/{name}.yml` per service, shared repo |
| **Multi-repo** | 20+ services, domain ownership | Each team owns a repo with its own `services.yaml` |

**Standalone repo** (cleanest for individual services):
```
cisco-interface-check/
├── services.yaml           ← decorators + repos + services in one file
└── scripts/
    ├── main.py
    └── requirements.txt
```

**Mono-repo** (shared codebase, per-file service definitions):
```
automation-services/
├── .gateway/services/      ← one YAML per service
│   ├── device-info.yml
│   └── config-push.yml
├── device-info/main.py
└── config-push/main.py
```

### Environment Promotion

| Setting | Dev | Staging | Production |
|---------|-----|---------|------------|
| Git `reference` | branch | release branch | tagged version (e.g., `v1.2.3`) |
| Secrets | `--prompt-value` | vault or `--prompt-value` | vault only |
| Import mode | `--force` | `--check` then import | `--validate` → `--check` → import |
| Who imports | developer | CI/CD pipeline | CI/CD with approval |

### CI/CD Integration

**GitLab CI:**
```yaml
stages: [validate, deploy]
validate:
  stage: validate
  script: iagctl db import services.yaml --validate
  only: [merge_requests]
deploy-dev:
  stage: deploy
  script:
    - iagctl login $IAG_USER
    - iagctl db import services.yaml --force
  only: [develop]
deploy-prod:
  stage: deploy
  script:
    - iagctl db import services.yaml --check
    - iagctl db import services.yaml
  only: [main]
  when: manual
```

**GitHub Actions:**
```yaml
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: iagctl db import services.yaml --validate
      - run: iagctl db import services.yaml --force
```

---

## Before Handing Off

**Service quality:**
- [ ] Service has a decorator with `additionalProperties: false`
- [ ] Service tested: `iagctl run service <type> <name> --set ...`
- [ ] Output is valid JSON (for Python: `print(json.dumps(result))`)
- [ ] Error cases return JSON with `"success": false`, not stderr
- [ ] Service YAML validates: `iagctl db import file.yaml --validate`

**Workflow integration:**
- [ ] Itential workflow tested end-to-end with `runService` task
- [ ] Workflow extracts `result.stdout` from JSON-RPC envelope via `query` task
- [ ] Error transitions on `runService` task (handles service failures)

**Security and ops:**
- [ ] Secrets created via `iagctl create secret --prompt-value` (never in YAML)
- [ ] No top-level `secrets:` section in committed service files
- [ ] Git references pinned to tags (not branches) for production
- [ ] Naming conventions followed

## Helper Templates

**Always start from a helper template.** Read the matching example from `${CLAUDE_PLUGIN_ROOT}/helpers/iag/` first, then modify:

| File | Purpose |
|------|---------|
| `${CLAUDE_PLUGIN_ROOT}/helpers/iag/example-python-service.yaml` | Python script service |
| `${CLAUDE_PLUGIN_ROOT}/helpers/iag/example-ansible-service.yaml` | Ansible playbook service |
| `${CLAUDE_PLUGIN_ROOT}/helpers/iag/example-opentofu-service.yaml` | OpenTofu plan service |
| `${CLAUDE_PLUGIN_ROOT}/helpers/iag/example-multi-service-chain.yaml` | Multi-service orchestration |
| `${CLAUDE_PLUGIN_ROOT}/helpers/iag/service-file-schema.md` | Full YAML schema reference |
