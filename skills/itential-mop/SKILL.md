---
name: itential-mop
description: Build command templates with validation rules, run CLI checks against devices, and use analytic templates for pre/post comparison. Use when building pre-checks, post-checks, or compliance validations that run show commands and evaluate output.
argument-hint: "[action or template-name]"
---

# MOP (Method of Procedure) - Developer Skills Guide

MOP manages command templates and analytic templates for running CLI commands against network devices with validation rules. Command templates execute show commands and evaluate the output against rules. Analytic templates compare command output before and after a change.

**MOP is for read-only validation only -- never use it to push configuration to devices.** Use Jinja2 templates and workflow tasks for config changes.

## Concepts

- **Command template** = a set of CLI commands + validation rules, run against one or more devices
- **Analytic template** = pre/post comparison of command output to detect drift
- **Variable syntax** = `<!variable_name!>` in both commands and rules (NOT `{{ var }}` or `$var`)
- **Pass/fail logic** = hierarchical: template-level -> command-level -> rule-level, each with AND/OR control

## API Reference

All `/mop/*` endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/mop/createTemplate` | Create a command template |
| GET | `/mop/listTemplates` | List all command templates |
| GET | `/mop/listATemplate/{name}` | Get a command template by name |
| POST | `/mop/updateTemplate/{mopID}` | Update a command template (full replacement) |
| POST | `/mop/deleteTemplate/{id}` | Delete a command template |
| POST | `/mop/exportTemplate` | Export template (body: `{"_id": "..."}` or `{"name": "..."}`) |
| POST | `/mop/importTemplate` | Import a template |
| POST | `/mop/RunCommandTemplate` | Run a command template against devices |
| POST | `/mop/RunCommand` | Run a single ad-hoc command on one device (workflow task) |
| POST | `/mop/RunCommandDevices` | Run a single ad-hoc command on multiple devices |
| POST | `/mop/RunCommandTemplateSingleCommand` | Run one command from a template by index |
| POST | `/mop/GetBootFlash` | Get boot flash image name from a device |
| POST | `/mop/reattempt` | Retry/delay mechanism for workflows |
| POST | `/mop/createAnalyticTemplate` | Create an analytic template |
| GET | `/mop/listAnalyticTemplates` | List all analytic templates |
| GET | `/mop/listAnAnalyticTemplate/{name}` | Get an analytic template by name (path param) |
| POST | `/mop/updateAnalyticTemplate/{id}` | Update an analytic template |
| POST | `/mop/deleteAnalyticTemplate/{id}` | Delete an analytic template |
| POST | `/mop/runAnalyticsTemplate` | Run an analytic template (workflow task) |

## Template Structure

Create with `POST /mop/createTemplate`. The body uses a `{"mop": {...}}` wrapper.

```json
{
  "mop": {
    "name": "Port_Turn_Up_Pre_Check",
    "description": "Validates interface and VLAN before port turn-up",
    "os": "",
    "passRule": true,
    "ignoreWarnings": false,
    "commands": [
      {
        "command": "show interface <!interface!>",
        "passRule": true,
        "rules": [
          {
            "rule": "line protocol is",
            "eval": "contains",
            "severity": "error"
          }
        ]
      },
      {
        "command": "show vlan brief",
        "passRule": true,
        "rules": [
          {
            "rule": "<!vlan_id!>",
            "eval": "contains",
            "severity": "error",
          }
        ]
      }
    ]
  }
}
```

**Field reference:**
- **`name`** -- template name (required, must be unique)
- **`description`** -- human-readable description
- **`os`** -- target OS filter (empty string = any OS)
- **`passRule`** (template-level) -- `true` = ALL commands must pass (AND), `false` = ONE command must pass (OR)
- **`ignoreWarnings`** -- see ignoreWarnings section below
- **`commands[]`** -- array of commands to execute
  - **`command`** -- the CLI command string. Variables use `<!variable_name!>` syntax
  - **`passRule`** (command-level) -- `true` = ALL rules must pass (AND), `false` = ONE rule must pass (OR)
  - **`rules[]`** -- validation rules applied to the command output
    - **`rule`** -- the string or pattern to match against. Can contain `<!variables!>`
    - **`eval`** -- evaluation operator (case-sensitive, see Rule Evaluation below)
    - **`severity`** -- `"error"`, `"warning"`, or `"info"`
    - **`flags`** -- optional evaluation flags (see Flags below)

**Only "name" is required** -- template validation uses AJV with strict=false, so minimal templates are accepted.

### passRule Logic

- **Template-level `passRule: true`** = ALL commands must pass (AND logic)
- **Template-level `passRule: false`** = at least ONE command must pass (OR logic)
- **Command-level `passRule: true`** = ALL rules in this command must pass (AND logic)
- **Command-level `passRule: false`** = at least ONE rule must pass (OR logic)

### ignoreWarnings

Template-level field, default `false`. When `true`: only rules with `severity: "error"` count as real failures. Rules with `severity: "warning"` or `"info"` that fail are treated as passing. When `false` (default): all severity levels count.

```json
{
  "mop": {
    "name": "...",
    "passRule": true,
    "ignoreWarnings": true,
    "commands": [...]
  }
}
```

## Rule Evaluation

The `eval` field determines how rule matching works. **Eval types are case-sensitive.**

| Eval | Purpose | Example Rule |
|------|---------|-------------|
| `contains` | String exists in output | `"line protocol is"` |
| `!contains` | String does NOT exist in output | `"ERROR"` |
| `contains1` | String exists exactly once | `"Active"` |
| `RegEx` | Regex matches output (capital R and E!) | `"/\\d+\\.\\d+/"` |
| `!RegEx` | Regex does NOT match | `"/ERROR/"` |
| `#comparison` | Extract + compare two values | See details below |

### Flags

Optional `flags` object on each rule:
- **`case: true`** = case-INSENSITIVE matching (confusing name -- `case: true` does NOT mean case-sensitive)
- **`global: true`** = global search (RegEx only)
- **`multiline: true`** = `^`/`$` match start/end of lines, not just start/end of string (RegEx only)

`case` is available for all eval types. `global` and `multiline` are only meaningful for `RegEx` and `!RegEx`.

### #comparison Details

Extract two values from command output using regex, then compare numerically.

```json
{
  "rule": "/Available: (\\d+)/",
  "ruleB": "/Total: (\\d+)/",
  "eval": "#comparison",
  "evaluator": ">=",
  "severity": "error"
}
```

- **`rule`** / **`ruleB`** -- regex patterns (in `/pattern/` format) to extract values from the command output
- **`evaluator`** -- comparison operator: `=`, `!=`, `<`, `>`, `<=`, `>=`, `%`
- **`%` operator** -- passes if `ruleB/rule * 100 <= percentage`. Set `"percentage": 80` to pass if ruleB is at most 80% of rule.

Example with percentage:
```json
{
  "rule": "/Total: (\\d+)/",
  "ruleB": "/Used: (\\d+)/",
  "eval": "#comparison",
  "evaluator": "%",
  "percentage": 80,
  "severity": "error"
}
```

## Variable Substitution

- **Syntax:** `<!variable_name!>` in both commands and rules
- Variables are substituted BEFORE execution
- If a variable is missing, the command is **SKIPPED** (not failed!) and counts as **PASSED**
- This syntax is different from Jinja2 templates (`{{ var }}`) and workflow variable references (`$var.job.x`)

Example command with variables:
```json
{
  "command": "show running-config interface <!interface!>",
  "passRule": true,
  "rules": [
    {
      "rule": "switchport access vlan <!vlan_id!>",
      "eval": "contains",
      "severity": "error",
      "evaluation": "pass"
    }
  ]
}
```

## Execution

### Standalone (without a workflow)

```
POST /mop/RunCommandTemplate
```
```json
{
  "template": "Port_Turn_Up_Pre_Check",
  "variables": {
    "interface": "GigabitEthernet0/1",
    "vlan_id": "100"
  },
  "devices": ["IOS-CAT8KV-1"]
}
```

- **`template`** -- template name (string)
- **`variables`** -- object with values for `<!variable!>` substitutions
- **`devices`** -- array of device names (or single device name string)

### In a Workflow

Use the `MOP.RunCommandTemplate` task. See `/itential-studio` for full workflow task wiring patterns.

```json
{
  "incoming": {
    "template": "$var.job.templateName",
    "variables": "$var.job.templateVariables",
    "devices": "$var.job.devices"
  },
  "outgoing": {
    "mop_template_results": null
  }
}
```

- **`template`** -- name of the command template (string or `$var` reference)
- **`variables`** -- object with values for `<!variable!>` substitutions
- **`devices`** -- array of device names to run against

See `/itential-builder` for running the workflow via `POST /operations-manager/jobs/start`.

### Ad-Hoc Commands (without a template)

Run a single command directly without creating a template first:

```
POST /mop/RunCommand
```
```json
{
  "command": "show version",
  "variables": {},
  "device": "IOS-CAT8KV-1"
}
```
Returns: `{raw, evaluated, device, response, result}` — same shape as one entry in `commands_results`.

For multiple devices: `POST /mop/RunCommandDevices` with `"devices": ["dev1", "dev2"]` (array instead of singular `device`).

To run a single command from an existing template by index: `POST /mop/RunCommandTemplateSingleCommand` with `{"templateId": "name", "commandIndex": 0, "variables": {}, "devices": ["dev1"]}`.

### Response Shape

```json
{
  "all_pass_flag": true,
  "result": true,
  "name": "Port_Turn_Up_Pre_Check",
  "commands_results": [
    {
      "raw": "show interface <!interface!>",
      "evaluated": "show interface GigabitEthernet0/1",
      "all_pass_flag": true,
      "device": "IOS-CAT8KV-1",
      "response": "...command output...",
      "result": true,
      "parameters": {"interface": "GigabitEthernet0/1"},
      "rules": [
        {"rule": "line protocol is", "eval": "contains", "result": true, "severity": "error"}
      ]
    }
  ]
}
```

- **`result`** (top-level) -- overall template pass/fail (boolean)
- **`all_pass_flag`** (top-level) -- the template's passRule setting
- **`commands_results[]`** -- one entry per command per device
  - **`raw`** -- original command string (before variable substitution)
  - **`evaluated`** -- command with variables substituted
  - **`response`** -- raw device output
  - **`result`** -- whether this command passed (boolean)
  - **`all_pass_flag`** -- this command's passRule setting
  - **`device`** -- the device this command ran against
  - **`parameters`** -- the variables that were substituted
  - **`rules[].result`** -- `true`/`false` for each individual rule

### Update

```
POST /mop/updateTemplate/{mopID}
```

The `mopID` is the template name (URL-encoded). Uses the same `{"mop": {...}}` body wrapper as create. The body is a **full replacement** -- include ALL fields, not just changed ones.

Response on success:
```json
{
  "n": 1,
  "ok": 1,
  "nModified": 1
}
```

## Analytic Templates

Analytic templates compare command output before and after a change to detect drift or validate results. Endpoints are listed in the API Reference table above.

### Create an Analytic Template

```
POST /mop/createAnalyticTemplate
```
```json
{
  "name": "Interface_Change_Validation",
  "os": "cisco-ios",
  "passRule": true,
  "prepostCommands": [
    {
      "preRawCommand": "show interface GigabitEthernet0/1",
      "postRawCommand": "show interface GigabitEthernet0/1",
      "passRule": true,
      "rules": [
        {
          "type": "matches",
          "preRegex": "/line protocol is (\\w+)/",
          "postRegex": "/line protocol is (\\w+)/",
          "evaluator": "="
        }
      ]
    }
  ]
}
```

### Structure

- **`name`** -- template name
- **`os`** -- target OS
- **`passRule`** -- `true` = ALL prepostCommands must pass (AND), `false` = ONE must pass (OR)
- **`prepostCommands[]`** -- array of pre/post command pairs
  - **`preRawCommand`** -- CLI command to run before the change
  - **`postRawCommand`** -- CLI command to run after the change
  - **`passRule`** -- `true` = ALL rules must pass, `false` = ONE must pass
  - **`rules[]`** -- comparison rules
    - **`type`** -- `matches`, `!matches`, `regex`, or `table`
    - **`preRegex`** -- regex to extract value from pre-change output
    - **`postRegex`** -- regex to extract value from post-change output
    - **`evaluator`** -- comparison operator: `=`, `!=`, `<`, `>`, `<=`, `>=`, `%`

### Rule Types

| Type | Purpose |
|------|---------|
| `matches` | Pre and post extracted values must match per evaluation operator |
| `!matches` | Pre and post extracted values must NOT match |
| `regex` | Regex-based extraction and comparison |
| `table` | Table-based comparison of structured output |

### Running an Analytic Template

In a workflow, use the `MOP.runAnalyticsTemplate` task:

```json
{
  "incoming": {
    "pre": "$var.preCheckTaskId.mop_template_results",
    "post": "$var.postCheckTaskId.mop_template_results",
    "analytic_template_name": "Interface_Change_Validation",
    "variables": {}
  },
  "outgoing": {
    "analytic_result": null
  }
}
```

**Critical:** The `pre` and `post` inputs must be the full `RunCommandTemplate` output object (which contains a `commands_results` property). Do NOT pass just the `commands_results` array — pass the entire result object.

**Gotcha:** Pre and post commands must have **exactly 1 match each** in the collected results. If 0 or >1 match, it produces an error. The matching compares against both the `raw` and `evaluated` command strings — if variables were used, the `evaluated` string (with variables replaced) is what will match.

## Gotchas

1. **Missing variable = skip = PASS (not fail)** -- if a `<!var!>` token has no value, the command is silently skipped and counts as PASSED. Verify variables are passed correctly.

2. **`case: true` = case-INsensitive** -- confusing naming. `"flags": {"case": true}` enables case-insensitive matching. It does NOT mean case-sensitive.

3. **Empty rules = auto-pass** -- a command with no rules (`"rules": []`) always passes. Add at least one rule if you want validation.

4. **RegEx 5-second timeout** -- complex regex patterns run in a sandboxed VM with a 5-second limit. Patterns prone to catastrophic backtracking will timeout.

5. **`contains` does substring matching** -- `"100"` matches `"1002"`. For exact matching, use `RegEx` with multiline flag:
   ```json
   {"rule": "^<!vlanId!>\\s+", "eval": "RegEx", "severity": "error", "flags": {"multiline": true}}
   ```

6. **Eval types are case-sensitive** -- `"RegEx"` not `"regex"` or `"REGEX"`. `"#comparison"` not `"Comparison"`.

7. **Only "name" is required** -- template validation uses AJV with strict=false. Minimal templates are accepted.

8. **Update is full replacement** -- `POST /mop/updateTemplate/{mopID}` replaces the entire template. Include ALL fields when updating, not just changed ones.

9. **MOP is read-only** -- command templates run show commands and evaluate output. Never use MOP to push configuration changes. Use Jinja2 templates and workflow adapter tasks for config changes.

10. **`_id` equals `name`** -- the engine sets `_id = name` on create. They are always identical. Use either for lookups.

11. **Rule-level missing variable ≠ command-level skip** -- if a *command* has `<!var!>` missing, the whole command is skipped (passes). But if a *rule* has `<!var!>` missing, it gets `eval: "missing_parameters"` and returns `"Invalid Rule: Missing Parameters"` with `result: false`. The rule fails, not skips.

12. **Template name change on update = delete + create** -- if you update with a different name, the engine deletes the old template and creates a new one. This is destructive — the old `_id` is gone.

13. **Import renames on collision** -- `importTemplate` does not fail on duplicate names. It appends ` (N)` to the name (e.g., `My_Template` becomes `My_Template (1)`).

14. **Cannot set `namespace` directly** -- providing `namespace` in the create body throws an error. Namespaces are managed through project membership.


## Helper Templates

Always start from a helper template when creating assets. Read the helper file first, then modify it.

| File | API Call | Purpose |
|------|----------|---------|
| `${CLAUDE_PLUGIN_ROOT}/helpers/create-command-template.json` | `POST /mop/createTemplate` | Command template with rules |
| `${CLAUDE_PLUGIN_ROOT}/helpers/update-command-template.json` | `POST /mop/updateTemplate/{mopID}` | Update template (full replacement) |

## Developer Scenarios

### 1. Build a pre-check command template

1. Identify the show commands needed (e.g., `show interface`, `show vlan brief`)
2. Read `${CLAUDE_PLUGIN_ROOT}/helpers/create-command-template.json` as a starting template
3. Fill in `name`, `description`, add commands with `<!variable!>` placeholders
4. Add rules for each command -- use `contains` for simple checks, `RegEx` for pattern matching
5. Set `passRule` at template and command level (AND vs OR logic)
6. Create with `POST /mop/createTemplate`
7. Test standalone with `POST /mop/RunCommandTemplate` providing variables and devices
8. Check `result` (top-level) and `commands_results[].rules[].result` for pass/fail details

### 2. Wire RunCommandTemplate into a workflow

After standalone testing passes:

1. Use `/itential-studio` to build a workflow
2. Add a `MOP.RunCommandTemplate` task to the workflow
3. Wire incoming variables: `template`, `variables`, `devices` using `$var.job.*` references
4. Wire outgoing: capture results in a variable like `mop_template_results`
5. Add downstream logic to branch on `$var.taskName.result` (true/false)
6. Use `/itential-builder` to run via `POST /operations-manager/jobs/start`

### 3. Build an analytic template for pre/post comparison

1. Identify the commands to run before and after the change
2. Create an analytic template with `POST /mop/createAnalyticTemplate`
3. Define `prepostCommands` with pre/post command pairs
4. Add rules with `preRegex`/`postRegex` to extract values for comparison
5. Set `evaluation` operator (`=` to verify values match, `!=` to verify they changed)
6. In a workflow: run pre-change commands, execute the change, run post-change commands, compare
7. Remember: pre and post commands must have exactly 1 match each in results
