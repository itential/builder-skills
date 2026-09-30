# DNS A Record Provisioning — Simple (Infoblox)

## Problem Statement

Network engineers manually log into Infoblox to create DNS A records, introducing delay and risk of typos. This automation provides a self-service JSON Form in Operations Manager and fully automatic provisioning via the Infoblox adapter — no manual tasks in the workflow. On success, an email notification is sent with the provisioned record details.

---

## Flow

```
[Operations Manager]
  Trigger: Manual (legacyWrapper: false)
  Form: "DNS A Record - Simple" (JSON Form)
  Operator fills in hostname, zone (dropdown), IP, view, TTL, comment → clicks Run
         |
         v
   [workflow_start]  <-- job variables: hostname, zone, ip_address, dns_view, ttl, comment
         |
         v
   [merge FQDN vars] → [makeData FQDN] → [merge body] → [createARecord]
                                                              |
                                            success → [query _ref] → [merge email vars] → [makeData email body] → [mailWithOptions] → workflow_end
                                                                                                                        |
                                                                                                                     [error] → [email warning] → workflow_end
                                            error → [errorHandler] → workflow_end
```

**Entrypoint:** Operations Manager automation with a JSON Form bound to a manual trigger (`legacyWrapper: false`). The form collects all inputs. The workflow receives them as job variables and executes fully automatically — no manual/review tasks.

> **Important:** The trigger must set `legacyWrapper: false` so that form fields map directly to job variables. When `legacyWrapper: true` (the default), form data is nested under `formData`, breaking the variable mapping.

---

## Platform Assets

| Asset | Type | Name |
|-------|------|------|
| JSON Form | Operations Manager Form | `DNS A Record - Simple` |
| Workflow | Automation | `DNS A Record Provisioning - Simple` |
| Project | Automation Studio Project | `DNS A Record Provisioning - Simple` |

### Project Membership

| Type | Role | Reference |
|------|------|-----------|
| account | owner | `<recipient@example.com>` |
| group | editor | `<editor-group-name>` |

---

## JSON Form Fields

Form name (exact): `DNS A Record - Simple`

Bound to the Operations Manager automation as a **manual trigger form**.

| Field Key | Label | Type | Required | Default | Notes |
|-----------|-------|------|----------|---------|-------|
| `hostname` | Hostname | string | yes | — | Short name only (e.g. `web01`). Combined with `zone` to form the FQDN. |
| `zone` | DNS Zone | string (dropdown) | yes | — | Dropdown with available Infoblox authoritative zones. See **Zone Dropdown Values** below. |
| `ip_address` | IP Address | string | yes | — | IPv4, e.g. `192.0.2.100` |
| `dns_view` | DNS View | string | yes | `default` | Infoblox view name |
| `ttl` | TTL (seconds) | number | no | `3600` | Record time-to-live |
| `comment` | Comment | string | no | — | Free-text note stored on the record |

### Zone Dropdown Values

The `zone` field is a dropdown populated with the authoritative zones from Infoblox. Maintain this list when zones are added or removed.

| Value | Label |
|-------|-------|
| `corp.example.com` | corp.example.com |
| `lab.example.com` | lab.example.com |
| `dev.example.com` | dev.example.com |
| `staging.example.com` | staging.example.com |

---

## Adapter Identity

### Infoblox

| Field | Value |
|-------|-------|
| Adapter type (`app`, `locationType`) | `Infoblox` |
| Instance name (`adapter_id`) | Resolve from `adapters.json` at build time — do not hardcode a name in the spec |

> **Note:** The `adapter_id` should be hardcoded in the workflow task (not passed as a job variable) since this is a single-adapter use case.

### Email

| Field | Value |
|-------|-------|
| Adapter type (`app`, `locationType`) | `EmailOpensource` |
| Instance name (`adapter_id`) | Resolve from `adapters.json` at build time |

> **Note:** Same rule — hardcode `adapter_id` in the workflow task.

---

## Workflow Tasks

### Task 1 — Build FQDN Variables (operation)

```
name:       merge
canvasName: merge
app:        WorkFlowEngine
type:       operation
actor:      Pronghorn
```

Builds the variables object for the FQDN makeData task.

> **Why merge + makeData instead of stringConcat?** `stringConcat` takes `str` (string) and `stringN` (array), but `$var` references inside the `stringN` array do not resolve — they are stored as literal strings. The `merge` → `makeData` pattern resolves variables correctly via `<!var!>` placeholders.

**`data_to_merge` array:**

| key | source | task | variable |
|-----|--------|------|----------|
| `hostname` | job var | `job` | `hostname` |
| `zone` | job var | `job` | `zone` |

**Outgoing:** `merged_object`

**Transitions:**
- `success` → Build FQDN

---

### Task 2 — Build FQDN (operation)

```
name:       makeData
canvasName: makeData
app:        WorkFlowEngine
type:       operation
actor:      Pronghorn
```

Concatenates hostname and zone into the FQDN using `<!var!>` placeholders.

**Incoming variables:**

| Field | Type | Value |
|-------|------|-------|
| `input` | string | `<!hostname!>.<!zone!>` |
| `outputType` | string | `string` |
| `variables` | object | `$var.<mergeTaskId>.merged_object` |

**Outgoing:** `output` → `$var.job.fqdn`

**Transitions:**
- `success` → Build Infoblox Body

---

### Task 3 — Build Request Body (operation)

```
name:       merge
canvasName: merge
app:        WorkFlowEngine
type:       operation
actor:      Pronghorn
```

**`data_to_merge` array:**

| key | source | task | variable |
|-----|--------|------|----------|
| `name` | job var | `job` | `fqdn` |
| `ipv4addr` | job var | `job` | `ip_address` |
| `view` | job var | `job` | `dns_view` |
| `ttl` | job var | `job` | `ttl` |
| `comment` | job var | `job` | `comment` |

**Outgoing:** `merged_object`

**Transitions:**
- `success` → Create A Record

---

### Task 4 — Create A Record (automatic)

```
name:       createARecord
canvasName: createARecord
app:        Infoblox (from apps.json)
locationType: Infoblox
type:       automatic
actor:      Pronghorn
```

**Incoming variables:**

| Field | Type | Value |
|-------|------|-------|
| `body` | object | `$var.<mergeTaskId>.merged_object` |
| `adapter_id` | string | Hardcoded to the instance name from `adapters.json` (not a job variable) |

The `body` sent to Infoblox WAPI `POST /record:a`:
```json
{
  "name":     "<FQDN>",
  "ipv4addr": "<IPv4>",
  "view":     "<dns_view>",
  "ttl":      <integer>,
  "comment":  "<string>"
}
```

**Response shape:**
```
$var.<taskId>.result.response   →  "record:a/ZG5z..."  (the _ref string)
```

**Transitions:**
- `success` → Extract Infoblox Ref
- `error` → Error Handler

---

### Task 5 — Extract Infoblox Ref (operation)

```
name:       query
canvasName: query
app:        WorkFlowEngine
type:       operation
actor:      Pronghorn
```

Extracts the `_ref` string from the adapter response. The `createARecord` result is an object — `result.response` contains the `_ref` string.

**Incoming variables:**

| Field | Type | Value |
|-------|------|-------|
| `pass_on_null` | boolean | `false` |
| `query` | string | `response` |
| `obj` | object | `$var.<createARecordTaskId>.result` |

**Outgoing:** `return_data` → `$var.job.infoblox_ref`

**Transitions:**
- `success` → Build Email Variables

---

### Task 6 — Build Email Variables (operation)

```
name:       merge
canvasName: merge
app:        WorkFlowEngine
type:       operation
actor:      Pronghorn
```

Builds the variables object for the email body makeData task.

**`data_to_merge` array:**

| key | source | task | variable |
|-----|--------|------|----------|
| `fqdn` | job var | `job` | `fqdn` |
| `ip_address` | job var | `job` | `ip_address` |
| `dns_view` | job var | `job` | `dns_view` |
| `ref` | job var | `job` | `infoblox_ref` |

**Outgoing:** `merged_object`

**Transitions:**
- `success` → Build Email Body

---

### Task 7 — Build Email Body (operation)

```
name:       makeData
canvasName: makeData
app:        WorkFlowEngine
type:       operation
actor:      Pronghorn
```

Constructs the email body string with record details using `<!var!>` placeholders.

**Incoming variables:**

| Field | Type | Value |
|-------|------|-------|
| `input` | string | `DNS A Record Provisioned Successfully\n\nFQDN: <!fqdn!>\nIP Address: <!ip_address!>\nDNS View: <!dns_view!>\nInfoblox Ref: <!ref!>` |
| `outputType` | string | `string` |
| `variables` | object | `$var.<emailVarsMergeTaskId>.merged_object` |

**Outgoing:** `output` (wired directly to the email task via `$var.<taskId>.output` — no job variable needed)

**Transitions:**
- `success` → Send Email

---

### Task 8 — Send Email (automatic)

```
name:       mailWithOptions
canvasName: mailWithOptions
app:        EmailOpensource (from apps.json)
locationType: EmailOpensource
type:       automatic
actor:      Pronghorn
```

**Incoming variables:**

| Field | Type | Value |
|-------|------|-------|
| `from` | string | `<noreply@example.com>` |
| `to` | array | `["<recipient@example.com>"]` |
| `subject` | string | `DNS A Record Provisioned` |
| `body` | string | `$var.<makeDataTaskId>.output` (wired from previous task, not a job variable) |
| `displayName` | string | `Itential` |
| `adapter_id` | string | Hardcoded to the instance name from `adapters.json` |

**Transitions:**
- `success` → workflow_end
- `error` → Email Warning

---

### Task 9 — Email Warning (operation)

```
name:       newVariable
canvasName: newVariable
app:        WorkFlowEngine
type:       operation
actor:      Pronghorn
```

Sets `email_warning` = `"DNS record created successfully but email notification failed."`

Exists because JSON transitions cannot have duplicate keys — both success and error from the email task cannot both target `workflow_end` directly.

**Transitions:**
- `success` → workflow_end

---

### Task 10 — Error Handler (operation)

```
name:       newVariable
canvasName: newVariable
app:        WorkFlowEngine
type:       operation
actor:      Pronghorn
```

Sets `error_message` = `"DNS A Record provisioning failed or was rejected. Check job error for details."`

**Transitions:**
- `success` → workflow_end

---

## Full Task Sequence

```
workflow_start
  → merge (Build FQDN Variables)
  → makeData (Build FQDN)
  → merge (Build Infoblox Body)
  → createARecord
        success → query (Extract Infoblox Ref)
                    → merge (Build Email Variables)
                    → makeData (Build Email Body)
                    → mailWithOptions (Send Email)
                          success → workflow_end
                          error   → newVariable (Email Warning) → workflow_end
        error   → newVariable (Error Handler) → workflow_end
```

**Total: 10 tasks.** Fully automatic — no manual tasks, no child workflows.

---

## Error Handling

- **Infoblox errors:** The `createARecord` task gets a `"state": "error"` transition → error handler. No retries, no rollback. Re-running the automation is the recovery path.
- **Email errors:** The `mailWithOptions` task error transition routes to an email warning `newVariable` task, then to `workflow_end`. Email delivery failure does not fail the job — the DNS record was already created successfully.

---

## Acceptance Criteria

1. An operator opens the automation in Operations Manager, fills in the JSON Form (hostname from text field, zone from dropdown, IP, view), and clicks Run.
2. The workflow executes fully automatically — no pauses, no manual steps.
3. A successful run creates a DNS A record in Infoblox and the job output contains the `_ref` string.
4. On success, an email is sent to `<recipient@example.com>` with the provisioned record details (FQDN, IP, view, `_ref`).
5. Any Infoblox adapter error routes to the error handler; the job does not hang.
6. Email delivery failure does not block or fail the job.
7. The workflow contains exactly 10 tasks — no manual tasks, no form tasks, no child workflows.

---

## Amendments

**2026-04-06 — Initial build lessons learned:**

1. **`adapter_id` must be hardcoded from `adapters.json`** — never assume instance names from the spec. The spec originally said `infobloxv9` but the actual adapter instance was `Infoblox`. Always resolve at build time.
2. **`legacyWrapper: false` is mandatory on manual triggers** — the default (`true`) wraps form data under `formData`, breaking variable mapping to job variables.
3. **`stringConcat` does not resolve `$var` inside `stringN` arrays** — use `merge` → `makeData` with `<!var!>` placeholders instead.
4. **Adapter responses are objects, not primitives** — `createARecord` returns `{response: "<_ref>", ...}`. A `query` task is needed to extract the `_ref` string before passing it to downstream tasks.
5. **Prefer task-to-task variable wiring (`$var.taskId.output`) over job variables** — only use job variables when values need to cross non-adjacent tasks or be visible in job output.
6. **Email `displayName` field** — include `displayName` in `mailWithOptions` incoming to control the sender display name (e.g. `"Itential"`).
