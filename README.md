# Itential — Agentic Builder Skills

[![License](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)

Spec-driven infrastructure automation and orchestration — delivered by AI agents on Itential.

Most infrastructure automation is built without a delivery model. No consistent stages, no traceability, no repeatable process — just ad hoc builds that are hard to maintain, document, or hand off.

This repository introduces **Spec-Driven Development** for infrastructure automation. Every delivery follows five structured stages, with AI agents executing each stage and engineers approving the artifacts that gate the next one.

```
Requirements  →  Feasibility  →  Design  →  Build  →  As-Built
      │                │              │          │           │
  /spec-agent    /solution-       /solution-  /builder-  /builder-
                  arch-agent       arch-agent    agent      agent
      │                │              │          │           │
  customer-       feasibility.md  solution-    assets     as-built.md
  spec.md         (approved)      design.md    (delivered) (approved)
  (approved)                      (approved)
```

The result is infrastructure automation that is traceable, repeatable, and delivered faster.

---

## Getting Started

**Official** (once approved on the Claude marketplace):

```bash
/plugin install itential-builder@claude-plugins-official
```

**Early access** (available now):

```bash
/plugin marketplace add itential/builder-skills
```

```bash
/plugin install itential-builder@itential-builder
```

Copy an environment template and point at your platform:

```bash
cp environments/cloud-lab.env my-use-case/.env   # edit with your credentials
```

See [`docs/quickstart.md`](docs/quickstart.md) for the full setup and first delivery walkthrough.

---

## How to Use It

```
"I need to automate VLAN provisioning on my platform"
→ /itential-builder:spec-agent

"I have a FlowAgent that's been running in production — productionize it"
→ /itential-builder:flowagent-to-spec

"I have an existing project with no documentation"
→ /itential-builder:project-to-spec

"I want to explore what's available on my platform"
→ /itential-builder:explore

"Help me build a golden config for my devices and run compliance"
→ /itential-builder:itential-golden-config
```

---

## Skills

**Delivery**

| Skill | What It Does |
|-------|-------------|
| `/itential-builder:spec-agent` | Requirements — refine use case, produce approved HLD |
| `/itential-builder:solution-arch-agent` | Feasibility + Design — assess platform, produce solution design |
| `/itential-builder:builder-agent` | Build + As-Built — implement design, test, deliver, document |
| `/itential-builder:flowagent-to-spec` | Read a FlowAgent → produce deterministic workflow spec |
| `/itential-builder:project-to-spec` | Read an existing project → produce spec + design docs |
| `/itential-builder:explore` | Auth, discover platform, browse freely |

**Platform**

| Skill | What It Does |
|-------|-------------|
| `/itential-builder:flowagent` | Create and run AI agents (LLM providers, tools, missions) |
| `/itential-builder:iag` | IAG services — Python, Ansible, OpenTofu via iagctl |
| `/itential-builder:itential-mop` | Command templates with validation rules |
| `/itential-builder:itential-devices` | Devices, backups, diffs, device groups |
| `/itential-builder:itential-golden-config` | Golden config, compliance, grading, remediation |
| `/itential-builder:itential-inventory` | Device inventories, nodes, actions, tags |
| `/itential-builder:itential-lcm` | Resource models, instances, lifecycle actions |

---

## Spec Library

22 technology-agnostic HLD specs in [`spec-files/`](spec-files/). Each spec is ready to use with `/itential-builder:spec-agent` as the starting point for a delivery.

| Category | Specs |
|----------|-------|
| **Networking** | [Port Turn-Up](spec-files/spec-port-turn-up.md) · [VLAN Provisioning](spec-files/spec-vlan-provisioning.md) · [Circuit Provisioning](spec-files/spec-circuit-provisioning.md) · [BGP Peer Provisioning](spec-files/spec-bgp-peer-provisioning.md) · [VPN Tunnel Provisioning](spec-files/spec-vpn-tunnel-provisioning.md) · [WAN Bandwidth Modification](spec-files/spec-wan-bandwidth-modification.md) |
| **Operations** | [Software Upgrade](spec-files/spec-software-upgrade.md) · [Config Backup & Compliance](spec-files/spec-config-backup-compliance.md) · [Network Health Check](spec-files/spec-network-health-check.md) · [Device Onboarding](spec-files/spec-device-onboarding.md) · [Device Decommissioning](spec-files/spec-device-decommissioning.md) · [Change Management](spec-files/spec-change-management.md) · [Incident Auto-Remediation](spec-files/spec-incident-auto-remediation.md) |
| **Security** | [Firewall Rule Lifecycle](spec-files/spec-firewall-rule-lifecycle.md) · [Cloud Security Groups](spec-files/spec-cloud-security-groups.md) · [SSL Certificate Lifecycle](spec-files/spec-ssl-certificate-lifecycle.md) |
| **Infrastructure** | [DNS Record Management](spec-files/spec-dns-record-management.md) · [IPAM Lifecycle](spec-files/spec-ipam-lifecycle.md) · [Load Balancer VIP](spec-files/spec-load-balancer-vip.md) · [Config Drift Remediation](spec-files/spec-config-drift-remediation.md) · [Network Compliance Audit](spec-files/spec-network-compliance-audit.md) · [AWS Webserver Deploy](spec-files/spec-aws-webserver-deploy.md) |

---

## Docs

- [`docs/quickstart.md`](docs/quickstart.md) — install, setup, and first delivery walkthrough
- [`docs/developer-flow.md`](docs/developer-flow.md) — full lifecycle diagram and design principles
- [`docs/builder-flow.md`](docs/builder-flow.md) — build sequence, asset structure, and import pattern
- [`helpers/`](helpers/) — JSON scaffolds for workflows, templates, and projects
  - **Workflow & Project Helpers**: `create-workflow.json`, `create-project.json`, `import-project.json`, `add-components-to-project.json`
  - **Task Helpers**: `workflow-task-adapter.json`, `workflow-task-application.json`, `workflow-task-childjob.json`
  - **Template Helpers**: `create-template-jinja2.json`, `create-template-textfsm.json`, `create-command-template.json`, `update-command-template.json`
  - **Golden Config Helpers**: `create-golden-config-tree.json`, `create-golden-config-node.json`, `update-node-config.json`, `add-devices-to-node.json`
  - **Compliance Helpers**: `create-compliance-plan.json`, `run-compliance-plan.json`, `run-compliance.json`
  - **IAG Helpers**: `iag/example-python-service.yaml`, `iag/example-ansible-service.yaml`, `iag/example-opentofu-service.yaml`, `iag/example-multi-service-chain.yaml`
  - **Reference Workflows**: `reference-adapter-workflow.json`, `reference-child-workflow.json`, `reference-childjob-loop.json`, `reference-parent-workflow.json`, `reference-merge-makedata.json`
  - **Utility Helpers**: `create-json-form.json`, `create-ops-manager-automation.json`, `update-project-members.json`, `lcm-action-workflow.json`
  - **Bootstrap Scripts**: `bootstrap.sh`, `oauth-bootstrap.sh`

---

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) to get started. Before contributing, you'll need to sign our [Contributor License Agreement](CLA.md).

---

## Support

- **Bug Reports**: [Open an issue](https://github.com/itential/builder-skills/issues/new)
- **Questions**: [Start a discussion](https://github.com/itential/builder-skills/discussions)
- **Lead Maintainer**: [@keepithuman](https://github.com/keepithuman)
- **Maintainer**: [@wcollins](https://github.com/wcollins)

---

## License

This project is licensed under the GNU General Public License v3.0 — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ❤️ by the <a href="https://github.com/itential">Itential</a> community
</p>
