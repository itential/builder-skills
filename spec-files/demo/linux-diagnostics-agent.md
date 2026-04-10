# Linux Diagnostics Agent — FlowAI Agent Spec

**Version:** 1.0  
**Date:** 2026-04-10  
**Status:** Ready for builder  
**Platform:** <iag-cluster-id> / Itential FlowAI

---

## 1. Overview

| Field | Value |
|---|---|
| Agent name | `Linux Diagnostics` |
| Description | Runs on-demand comprehensive health diagnostics across Linux inventory hosts, produces a structured per-host report, and delivers an HTML summary email to the ops team |
| LLM Provider | `<llm-provider-id>` |
| Model | `claude-sonnet-4-5-20250929` (or latest Claude Sonnet available) |
| Temperature | `0.3` |
| Entry point | System prompt + default user prompt (see Section 5) |

---

## 2. Tools

The agent requires exactly **three** tools.

| # | Tool Identifier | Type | Purpose |
|---|-----------------|------|---------|
| 1 | `<iag-cluster-id>//linux-diagnostics` | IAG service (Ansible) | Run comprehensive diagnostics playbook against target hosts; returns structured JSON per host |
| 2 | `<iag-cluster-id>//send-email` | IAG service (Python) | Send the HTML diagnostic report via Outlook365 SMTP |
| 3 | `WorkFlowEngine//restCall` | Workflow adapter | Post a brief plain-text summary notification to Slack |

### Tool 1: `linux-diagnostics` (NEW — must be built)

This is a new IAG5 Ansible service that does not yet exist. It must be created alongside this agent. See Section 7 for the full build spec.

**Input schema:**
```
target_hosts  string  required  Ansible inventory host pattern (default: "all")
                                Examples: "all", "linux-host-1", "linux-host-2"
```

**Expected output (set_stats):**
```json
{
  "diagnostics_results": [
    {
      "hostname": "linux-host-1",
      "ip_address": "192.0.2.10",
      "timestamp": "2026-04-10T14:00:00Z",
      "overall_status": "WARNING",
      "disk": { ... },
      "memory": { ... },
      "cpu": { ... },
      "uptime": { ... },
      "services": { ... },
      "network": { ... },
      "inodes": { ... },
      "failed_units": [ ... ],
      "oom_events": [ ... ],
      "zombie_processes": 0
    }
  ],
  "summary": {
    "total_hosts": 4,
    "ok_count": 2,
    "warning_count": 1,
    "critical_count": 1,
    "unreachable_count": 0
  }
}
```

### Tool 2: `send-email` (EXISTING)

Already deployed on `<iag-cluster-id>`. Sends HTML email via Outlook365 SMTP.

**Input schema (from existing decorator):**
```
to            string  required  Recipient email address
subject       string  required  Email subject line
body          string  required  HTML body content
display_name  string  optional  Sender display name (default: "IAG5 Automation")
```

### Tool 3: `WorkFlowEngine//restCall` with `slackPostMarkdownMessage` decorator (EXISTING)

Posts a brief Slack notification after the email is sent. Use the `slackPostMarkdownMessage` decorator already configured on the platform.

**Decorator:** `slackPostMarkdownMessage`

**Input schema:**
```
message  string  required  Markdown-formatted Slack message body
```

**Message format:**
```
*Linux Diagnostics — {date}*
Hosts: {total} | ✅ OK: {ok} | ⚠️ Warning: {warning} | 🔴 Critical: {critical}
Report sent to {recipient_email}
```

Use the overall status to set the leading emoji on the first line: ✅ if all OK, ⚠️ if any WARNING, 🔴 if any CRITICAL.

---

## 3. Input Parameters

The agent accepts one context variable set at invocation time:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `target_hosts` | string | `"all"` | Ansible inventory host pattern. Accepts any pattern valid for the inventory: `"all"`, a single hostname (`"linux-host-1"`), or a comma-separated list (`"linux-host-2,linux-host-3"`) |

The ops team should be a hardcoded recipient in the system prompt (`<ops-team@example.com>`). If a different recipient is needed, it can be overridden in the user prompt at runtime.

---

## 4. Inventory Reference

The `linux-diagnostics` service reuses the existing inventory at:
```
ansible/linux_patch_check/inventory.yaml
```

**Hosts:**

| Hostname | IP | User | Notes |
|---|---|---|---|
| `linux-host-1` | 192.0.2.10 | ec2-user | Amazon Linux / RHEL-family |
| `linux-host-2` | 192.0.2.20 | ubuntu | Debian-family, runs MySQL |
| `linux-host-3` | 192.0.2.30 | ec2-user | Amazon Linux, runs Kafka |
| `linux-host-4` | 192.0.2.40 | ec2-user | Amazon Linux, runs Zabbix |

SSH access: all hosts use the `<SSH-SECRET-NAME>` secret, injected as env var and written to a temp file via `tasks/prepare_ssh.yml` (existing shared task).

---

## 5. Agent Configuration

### 5.1 System Prompt

```
You are a Linux Infrastructure Diagnostics Specialist. Your job is to run
comprehensive health checks across the Linux server inventory and deliver
a clear, actionable report to the operations team.

## Your Tools
1. <iag-cluster-id>//linux-diagnostics — Runs a full diagnostics
   playbook across target Linux hosts. Returns structured JSON with disk,
   memory, CPU, uptime, service status, network, inode usage, failed systemd
   units, OOM events, and zombie process counts per host.
   Input: target_hosts (string, e.g. "all" or "linux-host-1").

2. <iag-cluster-id>//send-email — Sends an HTML email via Outlook365.
   Inputs: to (recipient address), subject (string), body (HTML string),
   display_name (optional sender label).

## Execution Flow — Complete Every Step Without Pausing

### Step 1: Run Diagnostics
Call linux-diagnostics with the target_hosts value provided in context
(default: "all"). Wait for the full response before proceeding.

### Step 2: Parse and Classify Results
For each host in diagnostics_results, classify overall status:
  - OK       — No thresholds breached, no anomalies
  - WARNING  — At least one soft threshold breached (see thresholds below)
  - CRITICAL — At least one hard threshold breached, host unreachable, or
               any OOM event in the last 24 hours

### Status Thresholds

DISK (per mount):
  WARNING  > 80% used
  CRITICAL > 90% used

MEMORY (RAM):
  WARNING  < 256 MB free
  CRITICAL < 64 MB free

SWAP:
  WARNING  > 50% used
  CRITICAL > 90% used

CPU Load Average (1m, relative to CPU count):
  WARNING  load/cores > 2.0
  CRITICAL load/cores > 5.0

INODES (per mount):
  WARNING  > 80% used
  CRITICAL > 90% used

SERVICES:
  WARNING  if any expected service is inactive (not running)
  CRITICAL if sshd is not running

FAILED SYSTEMD UNITS:
  WARNING  if 1 or more units in failed state

OOM EVENTS (last 24h):
  CRITICAL if any OOM kill detected

ZOMBIE PROCESSES:
  WARNING  if zombie count > 0

### Step 3: Build HTML Report
Construct the full HTML report using the template in Section 6 of the spec.
The report must include:
  - Executive summary banner (color-coded by worst overall status)
  - Per-host cards with all metric sections
  - Timestamp and inventory scope

### Step 4: Send Email
Call send-email with:
  to: "<ops-team@example.com>"
  subject: "Linux Diagnostics Report — [OVERALL_STATUS] — [timestamp]"
  body: <the full HTML report from Step 3>
  display_name: "Linux Diagnostics Agent"

### Step 5: Send Slack Notification
Call WorkFlowEngine//restCall with the slackPostMarkdownMessage decorator.
Build a brief plain-text Slack message using the summary counts from Step 1.
Use the leading status emoji based on worst overall status:
  - All OK     → ✅
  - Any WARNING → ⚠️
  - Any CRITICAL → 🔴

Message format:
  *Linux Diagnostics — [date]*
  [emoji] Hosts: [total] | ✅ OK: [ok] | ⚠️ Warning: [warning] | 🔴 Critical: [critical]
  Report sent to <ops-team@example.com>

### Step 6: Confirm and Stop
After Slack is sent, respond with a one-line summary:
"Diagnostics complete. [N] hosts checked: [X] OK, [Y] WARNING, [Z] CRITICAL.
Report sent to <ops-team@example.com>."
Then stop. Do not repeat output already in the email.

## Rules
- Always run Step 1 first — never skip diagnostics.
- Always send the email in Step 4 even if some hosts were unreachable.
- Always send the Slack notification in Step 5 after the email.
- Mark unreachable hosts as CRITICAL with reason "Host unreachable".
- Never ask the user for confirmation between steps.
- Do not truncate or summarize the per-host data — include all metrics in
  the HTML report, even if values are within normal range.
```

### 5.2 User Prompt (Default Objective)

```
Run a full diagnostics check on all Linux hosts in the inventory and email
the ops team a complete health report. Use target_hosts: "all" unless
specific hosts were provided in this request.
```

---

## 6. HTML Report Structure

The report sent via email must follow this structure. The builder should render this as a complete `<!DOCTYPE html>` document with inline CSS (no external stylesheets — Outlook strips them).

### 6.1 Overall Layout

```
┌─────────────────────────────────────────────────────┐
│  HEADER BANNER  (color by worst status)             │
│  "Linux Diagnostics Report"                         │
│  Ran: 2026-04-10 14:05:22 UTC | Scope: all (4 hosts)│
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  EXECUTIVE SUMMARY TABLE                            │
│  Hostname | IP | Status | # Warnings | # Criticals  │
│  linux-host-1 | 192.0.2.10 | ✅ OK | 0 | 0           │
│  linux-host-2 | 192.0.2.20 | ⚠️ WARNING | 2 | 0    │
│  linux-host-3 | 192.0.2.30 | 🔴 CRITICAL | 1 | 1   │
│  linux-host-4 | 192.0.2.40 | ✅ OK | 0 | 0         │
└─────────────────────────────────────────────────────┘

[Per-host card × N hosts]
┌─────────────────────────────────────────────────────┐
│  HOST: linux-host-1 (192.0.2.10)        ✅ OK         │
│  ─────────────────────────────────────────────────  │
│  Uptime: 14 days, 3:22  |  Last reboot: 2026-03-27  │
│  OS: Amazon Linux 2023  |  Kernel: 6.1.82           │
│                                                     │
│  DISK                                               │
│  /         45G used / 100G  (45%)  ✅               │
│  /boot     180M used / 512M (35%)  ✅               │
│                                                     │
│  MEMORY                                             │
│  Total: 8192 MB | Used: 5120 MB | Free: 3072 MB     │
│  Cached: 1500 MB | Swap: 512 MB used / 2048 MB      │
│                                                     │
│  CPU                                                │
│  Cores: 4 | Load: 0.42 / 0.55 / 0.61 (1m/5m/15m)  │
│  Top Processes by CPU:                              │
│    1. java        8.2%                              │
│    2. python3     2.1%                              │
│    ...                                              │
│                                                     │
│  SERVICES                                           │
│  sshd   ✅ active    cron  ✅ active                │
│  mysql  N/A (not detected on this host)             │
│                                                     │
│  NETWORK                                            │
│  eth0: 192.0.2.10/24                               │
│  Listening ports: 22 (sshd), 8080 (java)           │
│                                                     │
│  INODES                                             │
│  /        12% used  ✅                              │
│  /boot    8% used   ✅                              │
│                                                     │
│  FAILED SYSTEMD UNITS: none ✅                      │
│  OOM EVENTS (24h): none ✅                          │
│  ZOMBIE PROCESSES: 0 ✅                             │
└─────────────────────────────────────────────────────┘
```

### 6.2 Color Palette (inline CSS)

| Status | Banner background | Badge background | Badge text |
|---|---|---|---|
| OK | `#1a7f37` (dark green) | `#d1fae5` | `#065f46` |
| WARNING | `#b45309` (amber) | `#fef3c7` | `#92400e` |
| CRITICAL | `#991b1b` (dark red) | `#fee2e2` | `#7f1d1d` |
| Header/card bg | `#1f2937` (dark slate) | — | — |
| Card body bg | `#f9fafb` | — | — |
| Table stripe | `#f3f4f6` | — | — |

### 6.3 Status Badge Rules

- If the agent cannot reach a host: show `UNREACHABLE` in red with a note explaining the host was not accessible during the run.
- A host's badge is the worst of all its individual check results.
- The header banner color is the worst across all hosts.

---

## 7. New Service: `linux-diagnostics` (Ansible)

### 7.1 Service Identity

| Field | Value |
|---|---|
| Service name | `linux-diagnostics` |
| IAG tool identifier | `<iag-cluster-id>//linux-diagnostics` |
| Service type | `ansible-playbook` |
| Working directory | `linux_patch_check` (reuse existing service dir) |
| Playbook | `linux_diagnostics.yml` (new file, add alongside existing playbooks) |
| Inventory | `inventory.yaml` (existing, no changes needed) |
| SSH secret | `<SSH-SECRET-NAME>` (same pattern as all other linux services) |
| Repository | `<ansible-repo-name>` |
| Reference | `devel` |

### 7.2 Gateway Service YAML

**File:** `ansible/.gateway/services/linux-diagnostics.yml`

```yaml
services:
  - name: linux-diagnostics
    type: ansible-playbook
    description: >
      Runs comprehensive Linux health diagnostics across inventory hosts.
      Collects disk, memory, CPU, uptime, service status, network interfaces,
      inode usage, failed systemd units, OOM events, and zombie process counts.
      Returns structured JSON per host via set_stats.
    playbooks:
      - linux_diagnostics.yml
    working-directory: linux_patch_check
    repository: <ansible-repo-name>
    reference: devel
    decorator: linux-diagnostics
    secrets:
      - name: <SSH-SECRET-NAME>
        type: env
        target: <SSH-SECRET-NAME>
    runtime:
      inventory:
        - inventory.yaml
      config-file: ansible.cfg
      env:
        ANSIBLE_HOST_KEY_CHECKING: "false"
        ANSIBLE_STDOUT_CALLBACK: json

repositories:
  - name: <ansible-repo-name>
    url: git@gitlab.com:itential/sales-engineer/iag5/ansible.git
    private-key-name: git-key

decorators:
  - name: linux-diagnostics
    schema:
      $id: linux-diagnostics
      type: object
      additionalProperties: false
      properties:
        target_hosts:
          type: string
          description: >
            Ansible inventory host pattern. Use "all" for all hosts,
            a single hostname like "linux-host-1", or a comma-separated
            list like "linux-host-2,linux-host-3".
          default: "all"
          examples: ["all", "linux-host-1", "linux-host-2,linux-host-3"]
      required:
        - target_hosts
```

**Critical:** Do NOT include `$schema` in the decorator. The `$schema` field causes Anthropic's API to reject the tool definition at runtime. `$id` is fine; `$schema` is not.

### 7.3 New Playbook: `linux_diagnostics.yml`

**File location:** `ansible/linux_patch_check/linux_diagnostics.yml`

This playbook follows the same three-play pattern as the existing playbooks in this service directory.

#### Play 1 — SSH Setup (localhost)

Same pattern as all existing playbooks: include `tasks/prepare_ssh.yml`, then use `add_host` to build the dynamic `diag_targets` group from `target_hosts`.

```yaml
- name: Prepare SSH and Dynamic Inventory
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Run SSH setup
      ansible.builtin.include_tasks: tasks/prepare_ssh.yml

    - name: Add target hosts to dynamic group
      ansible.builtin.add_host:
        name: "{{ item }}"
        groups: diag_targets
      loop: "{{ target_hosts.split(',') | map('trim') | list }}"
      # Handle "all" specially — expand from inventory groups
      when: target_hosts != 'all'

    - name: Add ALL hosts to dynamic group when target is 'all'
      ansible.builtin.add_host:
        name: "{{ item }}"
        groups: diag_targets
      loop: "{{ groups['all'] }}"
      when: target_hosts == 'all'
```

#### Play 2 — Diagnostics Collection (diag_targets)

```yaml
- name: Linux Diagnostics Collection
  hosts: diag_targets
  gather_facts: yes
  become: yes
  vars:
    ansible_ssh_private_key_file: "{{ hostvars['localhost']['ssh_key_path'] | default(omit) }}"
  tasks:
    - block:

        # ── DISK ──────────────────────────────────────────────────────────
        - name: Collect disk usage (df -h)
          ansible.builtin.command: df -h --output=source,size,used,avail,pcent,target
          register: df_output
          changed_when: false

        - name: Parse disk usage into structured list
          ansible.builtin.set_fact:
            disk_mounts: >-
              {{
                df_output.stdout_lines[1:] | map('split') | list
                | map('zip', ['source','size','used','avail','percent_str','mount'])
                | map('community.general.dict') | list
              }}
          # Note: builder may need to adjust parsing approach depending on
          # available filters. Alternative: use ansible_mounts from gather_facts.

        - name: Flag mounts with disk usage > 80%
          ansible.builtin.set_fact:
            disk_warnings: >-
              {{
                ansible_mounts
                | selectattr('mount', 'in', ['/', '/boot', '/var', '/tmp', '/home'])
                | selectattr('size_total', 'gt', 0)
                | map(attribute='mount')
                | list
              }}
          # Use ansible_mounts (from gather_facts) for threshold logic.
          # Calculate used_pct = (size_total - size_available) / size_total * 100

        - name: Build disk facts from gather_facts mounts
          ansible.builtin.set_fact:
            diag_disk: >-
              {{
                ansible_mounts | selectattr('size_total', 'gt', 0) | list
                | map(attribute_map) | list
              }}
          # Structure per mount: { mount, device, size_total_gb, size_available_gb,
          #                         used_pct, status }
          # status = "CRITICAL" if used_pct > 90, "WARNING" if > 80, else "OK"

        # ── MEMORY ────────────────────────────────────────────────────────
        - name: Collect /proc/meminfo
          ansible.builtin.command: cat /proc/meminfo
          register: meminfo_raw
          changed_when: false

        - name: Build memory facts
          ansible.builtin.set_fact:
            diag_memory:
              total_mb: "{{ ansible_memtotal_mb }}"
              free_mb: "{{ ansible_memfree_mb }}"
              used_mb: "{{ ansible_memtotal_mb - ansible_memfree_mb }}"
              cached_mb: "{{ ansible_memory_mb.nocache.free | default(0) }}"
              swap_total_mb: "{{ ansible_swaptotal_mb }}"
              swap_free_mb: "{{ ansible_swapfree_mb }}"
              swap_used_mb: "{{ ansible_swaptotal_mb - ansible_swapfree_mb }}"
              swap_used_pct: >-
                {{
                  (((ansible_swaptotal_mb - ansible_swapfree_mb) / ansible_swaptotal_mb * 100)
                  | round(1)) if ansible_swaptotal_mb > 0 else 0
                }}
              status: >-
                {{
                  'CRITICAL' if ansible_memfree_mb < 64
                  else 'WARNING' if ansible_memfree_mb < 256
                  else 'OK'
                }}

        # ── CPU ───────────────────────────────────────────────────────────
        - name: Get top 5 processes by CPU
          ansible.builtin.shell: |
            ps aux --sort=-%cpu | awk 'NR>1 {print $1, $3, $11}' | head -5
          register: top_cpu_procs
          changed_when: false

        - name: Build CPU facts
          ansible.builtin.set_fact:
            diag_cpu:
              cores: "{{ ansible_processor_vcpus }}"
              load_1m: "{{ ansible_loadavg['1m'] }}"
              load_5m: "{{ ansible_loadavg['5m'] }}"
              load_15m: "{{ ansible_loadavg['15m'] }}"
              load_per_core_1m: "{{ (ansible_loadavg['1m'] | float / ansible_processor_vcpus | float) | round(2) }}"
              top_processes_by_cpu: "{{ top_cpu_procs.stdout_lines }}"
              status: >-
                {{
                  'CRITICAL' if (ansible_loadavg['1m'] | float / ansible_processor_vcpus | float) > 5.0
                  else 'WARNING' if (ansible_loadavg['1m'] | float / ansible_processor_vcpus | float) > 2.0
                  else 'OK'
                }}

        # ── UPTIME ────────────────────────────────────────────────────────
        - name: Get uptime and last reboot
          ansible.builtin.shell: |
            echo "uptime=$(uptime -p)"
            echo "reboot=$(who -b | awk '{print $3, $4}')"
          register: uptime_raw
          changed_when: false

        - name: Build uptime facts
          ansible.builtin.set_fact:
            diag_uptime:
              uptime_human: "{{ ansible_uptime_seconds | int | human_readable(unit='s') }}"
              uptime_seconds: "{{ ansible_uptime_seconds }}"
              last_reboot: "{{ uptime_raw.stdout_lines | select('match', '^reboot=') | map('regex_replace', '^reboot=', '') | first | default('unknown') }}"

        # ── SERVICES ──────────────────────────────────────────────────────
        - name: Check core services status
          ansible.builtin.systemd:
            name: "{{ item }}"
          register: service_status_results
          loop:
            - sshd
            - cron
            - crond       # RHEL-family alias
            - mysql
            - mysqld
            - kafka
            - zabbix-agent
            - zabbix-server
          ignore_errors: yes
          failed_when: false

        - name: Build services facts
          ansible.builtin.set_fact:
            diag_services: >-
              {{
                service_status_results.results
                | selectattr('status', 'defined')
                | map(attribute_map_services)
                | list
              }}
          # For each service: { name, state: "active"|"inactive"|"not-found", status }
          # status = "CRITICAL" if sshd is not active
          # status = "WARNING" if any other service is inactive (not "not-found")
          # Note: "not-found" means the service doesn't exist on this host — that is OK,
          # not a warning (mysql on a kafka host, for example)

        # ── NETWORK ───────────────────────────────────────────────────────
        - name: Get listening ports
          ansible.builtin.shell: ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null
          register: listening_ports
          changed_when: false
          ignore_errors: yes

        - name: Build network facts
          ansible.builtin.set_fact:
            diag_network:
              interfaces: >-
                {{
                  ansible_interfaces
                  | map('extract', hostvars[inventory_hostname], 'ansible_' + item)
                  | ... 
                }}
              # Use ansible_all_ipv4_addresses and per-interface facts from gather_facts
              # Structure: [ { interface: "eth0", ip: "192.0.2.10", netmask: "255.255.255.0" } ]
              listening_ports_raw: "{{ listening_ports.stdout_lines | default([]) }}"

        # ── INODES ────────────────────────────────────────────────────────
        - name: Get inode usage
          ansible.builtin.command: df -i --output=source,iused,iavail,ipcent,target
          register: inode_output
          changed_when: false

        - name: Build inode facts
          ansible.builtin.set_fact:
            diag_inodes: >-
              {{
                inode_output.stdout_lines[1:]
                | ... parse into list of { mount, used_pct, status }
              }}
          # status = "CRITICAL" if used_pct > 90, "WARNING" if > 80, else "OK"

        # ── FAILED SYSTEMD UNITS ──────────────────────────────────────────
        - name: Get failed systemd units
          ansible.builtin.command: systemctl --failed --no-legend --plain
          register: failed_units
          changed_when: false
          ignore_errors: yes

        - name: Build failed units facts
          ansible.builtin.set_fact:
            diag_failed_units: "{{ failed_units.stdout_lines | default([]) | reject('equalto', '') | list }}"
            diag_failed_units_status: "{{ 'WARNING' if failed_units.stdout_lines | reject('equalto','') | list | length > 0 else 'OK' }}"

        # ── OOM EVENTS ────────────────────────────────────────────────────
        - name: Check for OOM kills in last 24 hours (journalctl)
          ansible.builtin.shell: |
            journalctl -k --since "24 hours ago" 2>/dev/null | grep -i "oom\|out of memory\|killed process" || true
          register: oom_check_journal
          changed_when: false
          ignore_errors: yes

        - name: Check for OOM kills in dmesg (fallback)
          ansible.builtin.command: dmesg
          register: oom_check_dmesg
          changed_when: false
          ignore_errors: yes
          when: oom_check_journal.stdout_lines | length == 0

        - name: Build OOM facts
          ansible.builtin.set_fact:
            diag_oom:
              events: "{{ oom_check_journal.stdout_lines | default([]) | reject('equalto','') | list }}"
              status: "{{ 'CRITICAL' if oom_check_journal.stdout_lines | reject('equalto','') | list | length > 0 else 'OK' }}"

        # ── ZOMBIE PROCESSES ──────────────────────────────────────────────
        - name: Count zombie processes
          ansible.builtin.shell: ps aux | awk '$8 == "Z" {count++} END {print count+0}'
          register: zombie_count
          changed_when: false

        - name: Build zombie facts
          ansible.builtin.set_fact:
            diag_zombies:
              count: "{{ zombie_count.stdout | int }}"
              status: "{{ 'WARNING' if zombie_count.stdout | int > 0 else 'OK' }}"

        # ── ROLL UP HOST STATUS ────────────────────────────────────────────
        - name: Determine overall host status
          ansible.builtin.set_fact:
            host_overall_status: >-
              {{
                'CRITICAL' if (
                  diag_disk | selectattr('status','equalto','CRITICAL') | list | length > 0
                  or diag_memory.status == 'CRITICAL'
                  or diag_cpu.status == 'CRITICAL'
                  or diag_inodes | selectattr('status','equalto','CRITICAL') | list | length > 0
                  or diag_services | selectattr('status','equalto','CRITICAL') | list | length > 0
                  or diag_oom.status == 'CRITICAL'
                )
                else 'WARNING' if (
                  diag_disk | selectattr('status','equalto','WARNING') | list | length > 0
                  or diag_memory.status == 'WARNING'
                  or diag_cpu.status == 'WARNING'
                  or diag_inodes | selectattr('status','equalto','WARNING') | list | length > 0
                  or diag_services | selectattr('status','equalto','WARNING') | list | length > 0
                  or diag_failed_units_status == 'WARNING'
                  or diag_zombies.status == 'WARNING'
                )
                else 'OK'
              }}

        # ── ASSEMBLE HOST RESULT ───────────────────────────────────────────
        - name: Assemble host diagnostic result
          ansible.builtin.set_fact:
            host_diag_result:
              hostname: "{{ inventory_hostname }}"
              ip_address: "{{ ansible_host }}"
              os_distribution: "{{ ansible_distribution }} {{ ansible_distribution_version }}"
              kernel: "{{ ansible_kernel }}"
              timestamp: "{{ ansible_date_time.iso8601 }}"
              overall_status: "{{ host_overall_status }}"
              disk: "{{ diag_disk }}"
              memory: "{{ diag_memory }}"
              cpu: "{{ diag_cpu }}"
              uptime: "{{ diag_uptime }}"
              services: "{{ diag_services }}"
              network: "{{ diag_network }}"
              inodes: "{{ diag_inodes }}"
              failed_units: "{{ diag_failed_units }}"
              failed_units_status: "{{ diag_failed_units_status }}"
              oom: "{{ diag_oom }}"
              zombies: "{{ diag_zombies }}"

      rescue:
        - name: Record host as unreachable/failed
          ansible.builtin.set_fact:
            host_diag_result:
              hostname: "{{ inventory_hostname }}"
              ip_address: "{{ ansible_host | default('unknown') }}"
              timestamp: "{{ ansible_date_time.iso8601 | default(lookup('pipe','date -u +%Y-%m-%dT%H:%M:%SZ')) }}"
              overall_status: "CRITICAL"
              error: "Host failed diagnostics collection — check connectivity and sudo access"

      always:
        - name: Cleanup SSH key
          ansible.builtin.include_tasks: tasks/cleanup_ssh.yml
```

#### Play 3 — Aggregate Results (localhost)

```yaml
- name: Aggregate Diagnostic Results
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Build diagnostics_results list from all hosts
      ansible.builtin.set_fact:
        diagnostics_results: >-
          {{
            hostvars | dict2items
            | selectattr('value.host_diag_result', 'defined')
            | map(attribute='value.host_diag_result')
            | list
          }}

    - name: Build summary counts
      ansible.builtin.set_fact:
        diag_summary:
          total_hosts: "{{ diagnostics_results | length }}"
          ok_count: "{{ diagnostics_results | selectattr('overall_status','equalto','OK') | list | length }}"
          warning_count: "{{ diagnostics_results | selectattr('overall_status','equalto','WARNING') | list | length }}"
          critical_count: "{{ diagnostics_results | selectattr('overall_status','equalto','CRITICAL') | list | length }}"

    - name: Set custom stats for IAG output
      ansible.builtin.set_stats:
        data:
          diagnostics_results: "{{ diagnostics_results }}"
          summary: "{{ diag_summary }}"
        aggregate: true
        per_host: false
```

---

## 8. Implementation Notes for the Builder

### 8.1 Reuse Pattern — Do Not Copy Files

The `linux-diagnostics` service uses the **same working directory** (`linux_patch_check`) as all existing linux patch services. This means:
- `inventory.yaml` — shared, no changes
- `ansible.cfg` — shared, no changes  
- `tasks/prepare_ssh.yml` and `tasks/cleanup_ssh.yml` — shared, no changes
- `requirements.yml` — shared, verify `community.general` collection is listed (needed for some filters)

Only **one new file** is added to the service directory: `linux_diagnostics.yml`.

### 8.2 Dynamic Group for target_hosts

The existing playbooks use a `from_json` filter pattern for array inputs:
```yaml
loop: "{{ target_hosts if target_hosts is iterable and target_hosts is not string else target_hosts | from_json }}"
```

For this playbook, `target_hosts` is a plain string (not JSON array), so use `split(',')` with `map('trim')` to handle comma-separated values. The `"all"` case must expand from `groups['all']` rather than trying to use "all" as a literal host name.

### 8.3 Interface Fact Extraction

Ansible's network interface facts use dynamic keys (`ansible_eth0`, `ansible_ens3`, etc.) based on what `gather_facts` discovers. Use `ansible_interfaces` to enumerate them, then extract IP info per interface. Exclude loopback (`lo`) from the report.

### 8.4 Service Detection Strategy

Do not hard-code which app services to check on which host. Instead:
- Always check `sshd` and `cron`/`crond` (core services)
- Probe `mysql`, `mysqld`, `kafka`, `zabbix-agent`, `zabbix-server` with `ignore_errors: yes` and `failed_when: false`
- A service returning "not-found" via systemd is silently excluded from the report — it is not a warning
- Only flag services that exist (are installed) but are not active

### 8.5 OOM Detection

`journalctl` is preferred. On older Amazon Linux instances that use SysV init instead of systemd, journalctl may not be available — fall back to parsing `dmesg` output. Use `ignore_errors: yes` on both and combine the results.

### 8.6 No $schema in Decorator

See the Known Issues section of the SKILL.md for the IAG5 CI pipeline. The `$schema` field in decorator schemas causes Anthropic's API to reject the tool at runtime. Omit it entirely from the decorator YAML. The `$id` field is fine.

### 8.7 Commit Scope

When committing to the ansible repo:
```bash
git add ansible/.gateway/services/linux-diagnostics.yml
git add ansible/linux_patch_check/linux_diagnostics.yml
git commit -m "feat: add linux-diagnostics ansible service"
git push origin devel
```

Do not modify any existing files in `linux_patch_check/`. The new service is purely additive.

### 8.8 Agent Deployment

Deploy the FlowAI agent via the platform API or UI after the service is confirmed deployed:
- Verify `<iag-cluster-id>//linux-diagnostics` appears in the tool registry before creating the agent
- Verify `<iag-cluster-id>//send-email` is still present and working
- Agent capabilities: toolset = `["<iag-cluster-id>//linux-diagnostics", "<iag-cluster-id>//send-email"]`
- No LCM projects, sub-agents, or workflows needed

---

## 9. Acceptance Criteria

The implementation is complete when:

1. `linux-diagnostics.yml` playbook runs successfully against all 4 inventory hosts with `target_hosts: "all"`
2. IAG service `<iag-cluster-id>//linux-diagnostics` appears in the FlowAI tool registry
3. A single agent invocation with no arguments produces a diagnostic run, builds an HTML report, and delivers it to `<ops-team@example.com>`
4. The HTML email correctly badges each host as OK / WARNING / CRITICAL based on the threshold rules in Section 5.1
5. A host that is unreachable appears in the email as CRITICAL with an error note rather than crashing the agent
6. Targeting a single host (`target_hosts: "linux-host-1"`) produces a report scoped to that host only

---

## 10. File Checklist for Builder

| File | Action | Path |
|---|---|---|
| `linux_diagnostics.yml` | CREATE | `ansible/linux_patch_check/linux_diagnostics.yml` |
| `linux-diagnostics.yml` | CREATE | `ansible/.gateway/services/linux-diagnostics.yml` |
| `inventory.yaml` | NO CHANGE | `ansible/linux_patch_check/inventory.yaml` |
| `ansible.cfg` | NO CHANGE | `ansible/linux_patch_check/ansible.cfg` |
| `tasks/prepare_ssh.yml` | NO CHANGE | `ansible/linux_patch_check/tasks/prepare_ssh.yml` |
| `tasks/cleanup_ssh.yml` | NO CHANGE | `ansible/linux_patch_check/tasks/cleanup_ssh.yml` |
| `requirements.yml` | VERIFY `community.general` is listed | `ansible/linux_patch_check/requirements.yml` |
| FlowAI agent | CREATE via API/UI | Platform: <iag-cluster-id> |

