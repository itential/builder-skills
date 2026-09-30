# Use Case: SSL/TLS Certificate Lifecycle Management

## 1. Problem Statement

SSL/TLS certificate management is reactive and error-prone. Teams lose track of expiration dates, scramble to renew at the last minute, and manually deploy certificates across dozens of endpoints — load balancers, web servers, reverse proxies, WAFs. Expired certificates cause outages, browser warnings, and broken API integrations. There's no single source of truth for what's deployed where.

**Goal:** Automate the full certificate lifecycle — request, obtain from CA, deploy to all endpoints, verify deployment, monitor expiry, and auto-renew before expiration — eliminating certificate-related outages and manual toil.

---

## 2. High-Level Flow

```
Request  →  Obtain Cert  →  Deploy  →  Verify  →  Monitor  →  Renew
   │             │             │           │           │          │
   │             │             │           │           │          │
 Validate     Generate      Push cert   Confirm    Track      Auto-renew
 domain,      CSR, submit   to load     TLS        expiry     before
 SAN list,    to CA,        balancers,  handshake  dates,     deadline,
 key type,    retrieve      web         returns    alert on   loop back
 approval     signed cert   servers,    correct    threshold  to Obtain
              + chain       proxies,    cert +
                            WAFs        full chain
                                           │
                                      FAIL? → Rollback to previous cert
```

---

## 3. Phases

### Request & Validation
Collect the certificate request details: domain name(s), Subject Alternative Names (SANs), key type (RSA/ECDSA), key size, and intended endpoints. Validate that the requestor is authorized for those domains. If an approval gate is configured, **wait for approval before proceeding**.

### Obtain Certificate
Generate a private key and Certificate Signing Request (CSR). Submit the CSR to the appropriate Certificate Authority — internal CA for internal services, public CA for external-facing services. Retrieve the signed certificate and full chain. Store the certificate, key, and chain in the designated secrets store or vault. If CA issuance fails, **alert the requestor and stop**.

### Deploy
Push the certificate, key, and chain to every target endpoint — load balancers, web servers, reverse proxies, WAFs. Each endpoint type has its own deployment method. Deploy sequentially or in rolling fashion for redundant endpoints. If deployment to a critical endpoint fails, **rollback that endpoint to the previous certificate**.

### Verify
For each endpoint, perform a TLS handshake and confirm: the correct certificate is served, the chain is complete, the expiration date matches, and no mixed-content or protocol errors exist. If verification fails, **retry deployment once, then escalate**.

### Monitor & Renew
Record the certificate's expiration date. When it approaches a configurable threshold (default 30 days before expiry), trigger an automatic renewal. Renewal loops back to the Obtain phase with the same parameters. If auto-renewal fails, **alert the team with enough lead time to intervene manually**.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Private keys never leave the secrets store | Keys retrieved at deploy time only | Minimizes exposure of key material |
| Verification is a hard gate after deploy | Rollback if TLS handshake fails | Never leave a broken cert in production |
| Renewal triggers at configurable threshold | Default 30 days, adjustable per cert | Enough lead time for manual intervention if auto-renew fails |
| Deploy is per-endpoint, not all-or-nothing | Rolling deployment with per-endpoint rollback | One bad endpoint shouldn't block the rest |
| Both internal and public CA supported | CA selection based on cert purpose | Internal services don't need public trust; external ones do |

---

## 5. Scope

**In scope:** Certificate request intake, CSR generation, CA submission (internal and public), deployment to load balancers/web servers/proxies/WAFs, TLS verification, expiry monitoring, auto-renewal, rollback on failed deployment, secrets store integration, audit trail.

**Out of scope:** CA infrastructure setup and management. DNS validation for public CAs (assumed handled externally or as a separate workflow). Client certificate / mTLS provisioning (separate use case). Code signing certificates. Certificate pinning policy management.

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| CA issuance delayed or rejected | Service runs on expiring cert | Trigger renewal early enough to allow manual fallback |
| Deployment fails on a subset of endpoints | Inconsistent certs across infrastructure | Per-endpoint rollback + alerting; retry before escalating |
| Private key compromised during transit | Security breach | Keys stored in vault, retrieved only at deploy time, never logged |
| Auto-renewal loop fails silently | Certificate expires unnoticed | Monitoring alerts at multiple thresholds (30, 14, 7, 1 day) |
| Wildcard cert deployed too broadly | Larger blast radius if compromised | Track all endpoints per cert; flag overly broad wildcard usage |

---

## 7. Requirements

### What the automation must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Generate private keys and CSRs | Yes | Cannot proceed |
| Submit CSR to internal and public CAs | Yes | Cannot proceed |
| Deploy certificates to network/server endpoints | Yes | Cannot proceed |
| Perform TLS handshake verification | Yes | Engineer verifies manually |
| Store and retrieve secrets (keys, certs) | Yes | Cannot proceed securely |
| Schedule and trigger renewal based on expiry | Yes | Engineer monitors manually |
| Roll back to a previous certificate on failure | Yes | Engineer rolls back manually |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| Certificate Authority (internal) | Issue certs for internal services | Conditional | Only if internal certs needed |
| Certificate Authority (public) | Issue certs for external services | Conditional | Only if public certs needed |
| Secrets / vault | Store private keys and certificates | Yes | Cannot proceed securely |
| ITSM / ticketing | Track requests, approvals, audit trail | No | Engineer tracks manually |
| CMDB / inventory | Identify endpoints for a given domain | No | Engineer provides endpoint list |

### Discovery Questions

Ask the engineer before designing the solution:

1. Which domains and SANs need certificates?
2. Are these internal-only or public-facing services?
3. What CA do you use? Internal CA, Let's Encrypt, DigiCert, or other?
4. Where are private keys stored today? Do you have a secrets vault?
5. What endpoint types need certs? (Load balancers, web servers, proxies, WAFs?)
6. How many endpoints per certificate?
7. What is your desired renewal lead time before expiry?
8. Is there an approval process for new certificate requests?
9. Do you need to support both RSA and ECDSA key types?
10. Are there existing certificates to import and start monitoring?

---

## 8. Batch Strategy

| Strategy | Behavior | When to Use |
|----------|----------|-------------|
| Per-certificate | One certificate lifecycle at a time | Default for new requests |
| Rolling endpoints | Deploy to N endpoints at a time per cert | Production deployments behind redundant endpoints |
| Bulk renewal | Renew all expiring certs in a scheduled window | Monthly renewal sweep |

---

## 9. Acceptance Criteria

1. Certificate is only obtained after request validation and approval (if configured)
2. Private keys are generated and stored in the secrets vault, never exposed in logs
3. Certificate, key, and full chain are deployed to all specified endpoints
4. TLS handshake verification confirms the correct cert is served on every endpoint
5. Failed deployment triggers rollback to the previous certificate on that endpoint
6. Expiry monitoring alerts at configurable thresholds before expiration
7. Auto-renewal obtains and deploys a new certificate before the old one expires
8. Audit trail records every action: request, issuance, deployment, verification, renewal
