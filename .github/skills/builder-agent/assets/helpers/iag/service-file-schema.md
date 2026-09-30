# IAG Service File Schema Reference

The IAG service file is a YAML document that defines all resources managed by the Automation Gateway. Import with `iagctl db import <file>` and export with `iagctl db export`.

## Root Structure

```yaml
decorators: []          # Input schemas for services
repositories: []        # Git repos holding scripts/playbooks/plans
services: []            # Executable services (python, ansible, opentofu)
registries: []          # Package registries (PyPI, Ansible Galaxy)
secrets: []             # Credentials and keys
users: []               # Gateway user accounts
executable-objects: []  # Custom executable definitions
mcp_servers: []         # MCP server connections
```

---

## Decorators

JSON Schema definitions that validate service inputs and generate API docs.

```yaml
decorators:
  - name: "my-decorator"            # required — unique name
    schema:                          # option 1: inline JSON Schema
      $id: "root"
      $schema: "https://json-schema.org/draft/2020-12/schema"
      type: "object"
      required: ["device_ip"]
      properties:
        device_ip:
          type: "string"
          description: "Target device IP"
        device_type:
          type: "string"
          enum: ["ios", "nxos", "eos"]
    # file: "./path/to/schema.json"  # option 2: external file (instead of inline schema)
    # argument_order: ["device_ip", "device_type"]  # optional: ordered arg list
```

**Rules:** Provide either `schema` (inline) or `file` (path), not both.

---

## Repositories

Git repos containing scripts, playbooks, or plans.

```yaml
repositories:
  - name: "my-repo"                  # required — unique name
    url: "git@github.com:org/repo.git"  # required — git URL (ssh or https)
    reference: "main"                # optional — branch or commit SHA
    description: "My automation repo"  # optional
    tags: ["demo", "network"]        # optional

    # Auth for private repos (choose ONE method):
    # SSH key auth:
    private-key-name: "git-ssh-key"  # name of secret holding SSH private key

    # HTTPS auth:
    # username: "myuser"             # requires password-name
    # password-name: "git-password"  # name of secret holding password
```

**Rules:**
- Use `private-key-name` for SSH URLs (`git@...`)
- Use `username` + `password-name` for HTTPS URLs
- Cannot mix both auth methods

---

## Services

### Python Script

```yaml
services:
  - name: "my-python-service"        # required — unique name
    type: "python-script"            # required
    description: "Does something"    # optional
    repository: "my-repo"            # required — which repo has the code
    working-directory: "scripts/"    # required — path within repo
    filename: "main.py"             # required (unless pyproj-script)
    decorator: "my-decorator"        # optional — input validation schema
    tags: ["network", "automation"]  # optional
    secrets:                         # optional — injected as env vars at runtime
      - name: "api-token"
        type: "env"
        target: "API_TOKEN"          # env var name your script reads
    runtime:                         # optional
      env:                           # extra environment variables
        PYTHONPATH: "/usr/local/lib"
      req-file: "requirements.txt"   # or "pyproject.toml"
      # pyproj-script: "speak"       # alternative to filename (from pyproject.toml)
      # pyproj-optional-deps: ["fancy"]  # optional deps from pyproject.toml
```

**Rules:**
- Exactly one of `filename` OR `runtime.pyproj-script` must be set
- `runtime.req-file` must point to `requirements.txt` or `pyproject.toml`

### Ansible Playbook

```yaml
services:
  - name: "my-ansible-service"
    type: "ansible-playbook"         # required
    description: "Runs a playbook"
    repository: "my-repo"            # required
    working-directory: "ansible/"    # required
    playbooks:                       # required — at least one
      - "site.yml"
      - "deploy.yml"
    decorator: "my-decorator"        # optional
    tags: ["cisco", "network"]
    secrets:
      - name: "vault-key"
        type: "env"
        target: "ANSIBLE_VAULT_PASSWORD"
    runtime:                         # optional — ansible-specific settings
      inventory: ["./inventory.ini"] # inventory file(s)
      extra-vars: ["env=prod"]       # extra variables
      extra-vars-file: ["vars.yml"]  # variable files
      check: false                   # dry-run mode
      diff: false                    # show diffs
      verbose: false                 # verbose output
      verbose-level: 2               # 1-4 (like -v, -vv, -vvv, -vvvv)
      forks: 50                      # parallel processes
      tags: "webservers"             # only run tasks with these tags
      skip-tags: "debug"             # skip tasks with these tags
      limit: ["host1", "host2"]      # limit to these hosts
      config-file: "./ansible.cfg"   # custom ansible config
```

### OpenTofu Plan

```yaml
services:
  - name: "my-tofu-service"
    type: "opentofu-plan"            # required
    description: "Deploys infra"
    repository: "my-repo"            # required
    working-directory: "terraform/"  # required — directory containing .tf files
    decorator: "my-decorator"        # optional
    action: "apply"                  # required — "apply", "plan", or "destroy"
    vars: []                         # optional — passed as -var flags, e.g. ["region=us-east-1"]
    var-files: []                    # optional — passed as -var-file flags, e.g. ["prod.tfvars"]
    state-file: null                 # optional — custom state file path
    tags: ["infrastructure"]
    secrets:
      - name: "aws-key"
        type: "env"
        target: "TF_VAR_aws_access_key"  # OpenTofu reads TF_VAR_* as variables
```

**Rules:**
- `action` is required — must be `apply`, `plan`, or `destroy`
- `vars` and `var-files` are arrays (NOT `plan-vars` / `plan-var-files`)
- Decorator params pass directly as OpenTofu variables
- Backend/provider config lives in `.tf` files, not the service YAML

### Executable (Custom)

```yaml
services:
  - name: "custom-exec"
    type: "executable"               # required
    description: "Runs a shell script"
    repository: "my-repo"            # required
    working-directory: "./"          # required
    filename: "scripts/deploy.sh"    # required
    arg-format: "-{{.Key}}={{.Value}}"  # required — Go template for args
```

**Rules:** `arg-format` must be a valid Go template with `{{.Key}}` and `{{.Value}}`.

---

## Registries

Package registries for Python (PyPI) or Ansible (Galaxy).

```yaml
registries:
  # PyPI registry
  - name: "private-pypi"
    type: "pypi"                     # required: "pypi" or "ansible-galaxy"
    url: "http://private:8080/simple"  # required
    default: false                   # optional — mark as default for this type
    description: "Private PyPI"
    username: "admin"                # auth option 1: username + password
    password-name: "pypi-password"   # name of secret

  # Ansible Galaxy with token
  - name: "private-galaxy"
    type: "ansible-galaxy"
    url: "https://galaxy.example.com"
    token-name: "galaxy-token"       # auth option 2: token
    auth-url: "https://galaxy.example.com/api/v1/auth/"  # galaxy-only
    client-id: "my-client"           # galaxy-only, requires auth-url
    insecure: false                  # skip SSL verification
```

**Rules:**
- Cannot mix `username` with `token-name`
- `auth-url` and `client-id` only valid for `ansible-galaxy` type
- If `auth-url` is provided, `token-name` is required

---

## Secrets

Credentials stored encrypted at rest.

```yaml
secrets:
  - name: "git-ssh-key"             # required — unique name
    value: "-----BEGIN OPENSSH PRIVATE KEY-----\n..."  # required

  - name: "api-token"
    value: "token-abc123"
```

**Note:** Secrets in YAML files contain raw values. For interactive creation (never in shell history), use `iagctl create secret <name> --prompt-value` instead.

---

## Users

Gateway user accounts (server mode only).

```yaml
users:
  - name: "admin"                    # required
    password: "admin-password"       # required
```

---

## Executable Objects

Custom executable definitions that services can reference.

```yaml
executable-objects:
  - name: "python-interpreter"       # required
    exec-command: "/usr/bin/python3"  # required — command to execute
    description: "System Python"     # optional
    tags: ["python"]                 # optional
```

---

## MCP Servers

Model Context Protocol server connections.

```yaml
mcp_servers:
  # Local stdio transport
  - name: "local-mcp"
    transport: "stdio"               # required: "stdio", "sse", or "streamable-http"
    command: "/usr/local/bin/mcp-server"  # required — command (stdio) or URL (sse/http)
    description: "Local MCP server"
    tags: ["local"]
    env:                             # stdio only — environment variables
      PATH: "/usr/local/bin"

  # Remote SSE transport
  - name: "remote-mcp"
    transport: "sse"
    command: "https://mcp.example.com/sse"
    headers:                         # sse/http only — HTTP headers
      Authorization: "Bearer token123"
```

---

## Import/Export Commands

```bash
# Export current state to YAML
iagctl db export <file.yaml>

# Validate a service file (dry run, no changes)
iagctl db import <file.yaml> --validate

# Dry run with checks
iagctl db import <file.yaml> --check

# Import (additive — new resources added, existing skipped)
iagctl db import <file.yaml>

# Import with overwrite (existing resources replaced)
iagctl db import <file.yaml> --force

# Import directly from a Git repo
iagctl db import --repository <git-url> --reference <branch>
```

**Import behavior:**
- **New resources** → added
- **Existing resources (same name)** → skipped (use `--force` to overwrite)
- **Resources not in the YAML** → untouched (never deleted)
