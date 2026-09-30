# Use Case: AWS Web Server Deployment

## 1. Problem Statement

Deploying a web server on AWS requires manual steps across multiple tools: the AWS console to create security groups and launch an instance, an SSH session or Ansible run to configure the OS and install the web server, and a manual browser check to verify the result. Each engineer does it differently, there's no audit trail, and the process is error-prone — ports get misconfigured, instances launch without tags, and nobody validates that the service is actually reachable before closing the ticket.

**Goal:** Automate the full deployment lifecycle — from bare infrastructure to a validated, live HTTP endpoint — in a single orchestrated workflow. Provision the EC2 instance with proper security group rules, configure the web server via Ansible, and verify HTTP reachability, with every step observable and every failure captured cleanly.

---

## 2. High-Level Flow

```
Provision      →  Configure      →  Validate       →  Close Out
    │                 │                 │                 │
    │                 │                 │                 │
 Create SG,        Connect via      HTTP GET           Report
 open ports        SSH, install     against            outputs:
 22 + 80,          web server       public IP,         instance_id,
 launch EC2,       (nginx),         verify             public_ip,
 poll until        deploy sample    200 OK,            service
 running,          page             content            status
 tag instance                       check
    │                 │                 │
 FAIL? → Stop     FAIL? → Stop     FAIL? → Flag
 and report       and report       deployment
                                   as unhealthy
```

---

## 3. Phases

### Provision
Create an EC2 security group scoped to the target VPC. Authorize inbound traffic on port 22 (SSH for configuration) and port 80 (HTTP for the web server). Launch a t2.micro (or specified) instance with the provided AMI, key pair, and subnet. Poll the instance state until it reaches "running." Tag the instance with a Name and a ManagedBy label for traceability. If any AWS API call fails, **stop — do not proceed to configuration**.

### Configure
Connect to the running instance via SSH through the Automation Gateway. Run an Ansible playbook that installs the web server package (nginx), deploys a sample Hello World page to the document root, and ensures the service is started and enabled. The playbook must be idempotent — safe to re-run. If the Ansible service call fails, **stop and report the error with stdout**.

### Validate
Construct the full URL (`http://{public_ip}`) and invoke an HTTP validation service against the deployed endpoint. Verify the response returns HTTP 200. If validation fails, **flag the deployment as unhealthy** — the instance is running but the web server is not serving correctly.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| EC2 adapter direct vs. IAG Python service | EC2 adapter direct | Full task-level visibility in the Itential job view; known response shapes; no black-box dependency |
| Monolithic workflow vs. child decomposition | Three child workflows + parent orchestrator | Each phase is independently testable, reusable, and observable |
| Poll loop vs. fixed delay for instance ready | Poll loop (evaluation + revert to delay) | Handles variable startup time without over-waiting or hard-coding a sleep |
| Web server configuration mechanism | IAG Ansible service | Ansible is the natural fit for idempotent OS configuration; IAG provides execution infrastructure and SSH key management |
| HTTP validation as a separate phase | Dedicated child workflow | Validation is reusable for any web endpoint, not tied to nginx specifically |

---

## 5. Scope

**In scope:** Single instance deployment, security group creation with SSH + HTTP ingress, EC2 launch and polling, instance tagging, web server installation and configuration via Ansible, HTTP endpoint validation, error handling at every phase.

**Out of scope:** Auto-scaling groups or load balancers. HTTPS/TLS certificate provisioning. DNS record creation. Multi-instance or batch deployment. Teardown/cleanup lifecycle. ITSM ticket creation. Custom application deployment beyond a sample page.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Security group already exists with same name | Phase 1 fails on duplicate | Add describeSecurityGroups check before create, reuse existing if found |
| Instance doesn't reach "running" state | Deployment hangs | Poll loop with configurable timeout; abort after max retries |
| SSH not ready when Ansible runs | Phase 2 fails on connection | Ansible playbook includes wait_for_connection with timeout |
| Port 80 blocked by network ACL or other firewall | Phase 3 fails validation | Document prerequisite: subnet/VPC must allow outbound HTTP |
| EC2 key pair doesn't match IAG host key file | Phase 2 cannot connect | Document key coordination prerequisite; consider key management automation |
| Instance left running after failed deployment | Ongoing AWS cost | Build companion teardown workflow (future enhancement) |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Call AWS EC2 API (create SG, launch instance, describe, tag) | Yes | Cannot proceed |
| Execute Ansible playbooks via Automation Gateway | Yes | Cannot proceed |
| Orchestrate multi-phase workflows with child jobs | Yes | Cannot proceed |
| Poll external resource state with retry logic | Yes | Use fixed delay (less reliable) |
| Invoke HTTP validation service | Yes | Engineer validates manually |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| AWS EC2 API (via adapter) | Provision infrastructure | Yes | Cannot proceed |
| Itential Automation Gateway | Execute Ansible playbook for OS configuration | Yes | Cannot proceed |
| IAG Ansible service (aws-nginx-config) | Install and configure nginx | Yes | Must be deployed before running workflow |
| IAG Python service (url-validator) | HTTP endpoint validation | No | Engineer validates manually |
| ITSM / ticketing (e.g., ServiceNow) | Track deployment, audit trail | No | Engineer tracks manually |

### Discovery Questions

Ask the engineer before designing the solution:

1. What AWS region and VPC should the instance deploy into?
2. What AMI should be used? (Amazon Linux 2, Ubuntu, etc.)
3. What EC2 key pair name exists in the target region?
4. What subnet should the instance launch in? Does it have auto-assign public IP enabled?
5. Is the SSH private key already available on the IAG host? What path?
6. What instance type is needed? (t2.micro default, or larger?)
7. Should the web server be nginx, Apache, or another package?
8. Is there an existing web page/application to deploy, or use a sample Hello World?
9. Should the workflow create a ServiceNow ticket for the deployment?
10. Is there a teardown requirement — should the instance auto-terminate after a period?

---

## 8. Acceptance Criteria

1. Security group created with ports 22 and 80 open to specified CIDR
2. EC2 instance launched, reaches "running" state, and has a public IP
3. Instance tagged with Name and ManagedBy labels
4. Web server (nginx) installed and serving on port 80
5. Sample page accessible via HTTP at the instance's public IP
6. HTTP validation confirms 200 OK response
7. Workflow completes without entering error state
8. All phases visible as separate child jobs in the Itential job view
9. Any phase failure produces clean error capture (no stuck jobs)
10. Workflow is re-runnable with different parameters (new instance name, different AMI)
