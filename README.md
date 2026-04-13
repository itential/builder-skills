# Itential — Agentic Builder Skills

[![License](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)

Spec-driven infrastructure automation and orchestration — delivered by AI agents on Itential.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [How to Use It](#how-to-use-it)
- [Skills](#skills)
- [Spec Library](#spec-library)
- [Demo Specs](#demo-specs)
- [Docs](#docs)
- [Contributing](#contributing)
- [Support](#support)

---

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

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Itential Platform | 6.x | |
| IAG | 5.x | Required only for the `/iag` skill |
| Claude Code | Latest | [Install guide](https://claude.ai/code) |

---

## Getting Started

**Install the plugin:**

```bash
/plugin install itential-builder@claude-plugins-official
```

**Already installed? Update to the latest version:**

```bash
/plugin update itential-builder@claude-plugins-official
```

**First-time setup:**

Create a folder for your use case and add a `.env` file with your platform credentials:

```bash
mkdir my-use-case && cd my-use-case
```

**Cloud / OAuth:**
```bash
# my-use-case/.env
PLATFORM_URL=https://your-instance.itential.io
AUTH_METHOD=oauth
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
```

**Local / Password:**
```bash
# my-use-case/.env
PLATFORM_URL=http://localhost:4000
AUTH_METHOD=password
USERNAME=admin
PASSWORD=admin
```

Then start your first delivery from inside that folder:

```
/itential-builder:spec-agent
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

"Document all my global workflows and group them by use case"
→ /itential-builder:documentation

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
| `/itential-builder:spec-agent` | Refines a use case into an approved requirements spec (HLD). Picks from 22 built-in specs or starts from scratch. Produces `customer-spec.md` — the input to every downstream stage. |
| `/itential-builder:solution-arch-agent` | Connects to your platform, assesses what it can support, and produces a feasibility decision and a concrete implementation plan. Outputs `feasibility.md` and `solution-design.md`. |
| `/itential-builder:builder-agent` | Implements the approved solution design end-to-end — workflows, templates, configs, projects. Tests each component, verifies acceptance criteria, and produces `as-built.md`. |
| `/itential-builder:flowagent-to-spec` | Reads a FlowAgent's config and mission history, reconstructs what it actually did, and produces a `customer-spec.md` for the deterministic equivalent. Turns agentic exploration into a governed delivery path. |
| `/itential-builder:project-to-spec` | Reads an existing Itential project — workflows, templates, MOP — and reverse-engineers a `customer-spec.md` and `solution-design.md`. Use to document undocumented automation or create a baseline for a rebuild. |
| `/itential-builder:documentation` | Surveys global assets on a platform — collects workflows, templates, LCM models, golden config, and OM automations, discovers their relationships, groups them into use cases, and produces `customer-spec.md` + `solution-design.md` per use case plus a master README. Optionally creates a project per use case and moves assets in with a reference impact report. For a named project, use `/project-to-spec` instead. |
| `/itential-builder:explore` | Authenticates to a platform, pulls live data, and lets you browse capabilities freely. Use for ad-hoc investigation before starting a delivery or when you need to work outside the lifecycle. |

**Platform**

| Skill | What It Does |
|-------|-------------|
| `/itential-builder:flowagent` | Creates and runs AI agents on the Itential Platform. Configures LLM providers, registers tools (adapters, workflows, IAG services), and runs missions. Use when building or operating Flow AI agents. |
| `/itential-builder:iag` | Builds and runs IAG 5 services — Python scripts, Ansible playbooks, OpenTofu plans. Manages YAML service definitions, imports via `iagctl`, and calls services from Itential workflows via GatewayManager. |
| `/itential-builder:itential-mop` | Builds Method of Procedure command templates with variable substitution and validation rules. Runs CLI pre-checks and post-checks against devices, and uses analytic templates for before/after config comparison. |
| `/itential-builder:itential-devices` | Manages network devices in Itential Configuration Manager — onboard devices, take config backups, diff configurations, organize device groups, and apply device templates. |
| `/itential-builder:itential-golden-config` | Builds golden config trees and node-level config specs that define the expected configuration standard for your devices. Runs compliance plans, grades results, and generates remediation configs for violations. |
| `/itential-builder:itential-inventory` | Builds and manages device inventories in Itential Inventory Manager. Populates nodes in bulk, assigns tags, runs actions against inventory devices, and manages inventory-level access and grouping. |
| `/itential-builder:itential-lcm` | Defines reusable service resource models in Itential Lifecycle Manager, creates and manages resource instances, runs lifecycle actions, and tracks execution history. Use for service models that have create, update, and delete lifecycle phases. |

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

## Demo Specs

Ready-to-run specs in [`spec-files/demo/`](spec-files/demo/) for walkthroughs and demonstrations.

| Spec | Description |
|------|-------------|
| [Device Health Troubleshooting Agent](spec-files/demo/device-health-agent.md) | FlowAI agent spec for device health triage — runs diagnostics and surfaces findings |
| [Linux Diagnostics Agent](spec-files/demo/linux-diagnostics-agent.md) | FlowAI agent spec for Linux system diagnostics |
| [DNS A Record Provisioning — Simple](spec-files/demo/spec-dns-a-record-infoblox-simple.md) | Simplified DNS A record provisioning via Infoblox |
| [DNS A Record Provisioning](spec-files/demo/spec-dns-a-record-provisioning.md) | Full DNS A record provisioning lifecycle |

---

## Docs

- [`docs/quickstart.md`](docs/quickstart.md) — install, setup, and first delivery walkthrough
- [`docs/developer-flow.md`](docs/developer-flow.md) — full lifecycle diagram and design principles
- [`docs/builder-flow.md`](docs/builder-flow.md) — build sequence, asset structure, and import pattern
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — common issues and fixes
- [`helpers/`](helpers/) — JSON scaffolds for workflows, templates, projects, and reference patterns

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
