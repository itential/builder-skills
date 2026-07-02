# Transcript — builder-agent skill test (old skill)

## Task restated

The engineer is building the **Create action workflow** for a new LCM (Lifecycle Manager) resource model. The resource model's `schema.required` lists four fields: `subscription_id`, `resource_group`, `vnet_name`, `vlan_id`. Inside the workflow, the merge task that assembles the instance-write body (`data_to_merge`) currently only includes `vnet_name` and `vlan_id`. The engineer asked: is that a problem?

This is a debugging/advice question, not a from-scratch build request — so the deliverable is a diagnosis plus corrected task JSON, not a brand-new multi-task workflow.

## Steps taken

1. **Read `/tmp/eval-old-skill/builder-agent/SKILL.md` in full** (2313 lines, read in two passes) as the sole source of truth for conventions, per the test instructions.
2. **Searched the skill for LCM-specific and merge-specific guidance:**
   - `grep -n -i "instance-write\|instance_write\|LCM\|schema.required\|resource model\|instance\b"` — found the skill references `helpers/assets/lcm/lcm-vxlan-fabric-services-project.json` for "LCM action workflow tasks" and a table row: *"LCM action workflow (must output `instance`)"* pointing at that same asset with the jq filter `select(.document.name | test("Create|Delete"))`.
   - The skill does **not** have a dedicated "LCM resource model" section walking through `schema.required` vs. `data_to_merge`. The applicable guidance is the general-purpose sections: **Guide 1 Step 5 (Handle object inputs — merge)**, **Utility Tasks → merge**, and **Guide 2: Debug a failed job**, which has this exact row:
     > `"Schema validation failed on must have required property 'X'"` → Cause: *Missing field in adapter body* → Fix: *Add the field to merge task*
   - Also: pre-submit checklist item — *"Child workflow's `inputSchema.required` matches what you're passing"* — the same "does the receiving schema's required list match what you're actually handing it" discipline applies here, just one level down (model schema vs. child workflow schema).
3. **Pulled the real production LCM asset files under `helpers/assets/lcm/`** (per the REPO CONTEXT instruction to resolve `CLAUDE_PLUGIN_ROOT` to the real repo and pull real JSON rather than guessing from memory):
   - `helpers/assets/lcm/lcm-fan-device-lifecycle-management.json` — a real LCM **resource model** document (`.data.schema`, `.data.actions`). Confirmed the shape of `schema.required`, e.g.:
     ```json
     "required": ["becentralId", "mac", "serialNumber", "customerId"]
     ```
   - `helpers/assets/lcm/lcm-vxlan-fabric-management.json` — another real resource model whose **action** objects (`.data.actions[]`) carry their own `inputSchema`/`outputSchema`. Critically, the `outputSchema` for the update/delete actions is:
     ```json
     "outputSchema": {
       "type": "object",
       "required": ["instance"],
       "properties": {
         "instance": {
           "description": "Schema defining the possible values within instances of resource model 'VXLAN Fabric Services'",
           "type": "object",
           "required": [],
           "additionalProperties": true,
           "properties": { ... same fields as the resource model schema ... }
         }
       }
     }
     ```
     This is direct, real evidence (not fabricated) that an LCM action workflow's job is to produce a job variable named `instance` whose shape mirrors the resource model's schema — including whatever that model's top-level `schema.required` demands. That's the concrete mechanism behind the skill's one-line note *"LCM action workflow (must output `instance`)"*.
   - `helpers/assets/lcm/lcm-vxlan-fabric-services-project.json` — the full project export referenced by the skill. Confirmed it uses `.data.components[]` (not `.data.project.components[]` as literally written in the skill's own jq snippet — a real path discrepancy in the skill text, noted here but out of scope for this answer). Inspected its `LifecycleManager.runAction` tasks to see how instance data is passed on other action calls (`variables: {field: {task, value}}` — same `{task,value}` shape as `childJob`, confirming that whichever task ultimately writes fields into an instance, every property the model's `schema.required` demands has to be present in that payload or the write is rejected).
   - `helpers/create/create-lcm-resource-model.json` — confirmed the model-definition wrapper: `schema.required` is a flat array of property names the instance object must contain, and each `action` (`Create`/`Update`/`Delete`) links to a workflow.
4. **Synthesized the general skill rule with the concrete LCM evidence** to answer the question and produced corrected task JSON.

## Diagnosis

**Yes — this is a real, load-bearing problem, not a style nitpick.**

The resource model's `schema.required` is the validation gate the platform applies to every instance record for that model. It does not matter which specific task in the workflow physically constructs the instance payload (a `merge` task building `$var.job.instance`, a `LifecycleManager.runAction`-style call, or a direct adapter write) — the object that ends up representing the instance must contain **every** key listed in `schema.required`, because that list is enforced independent of which task assembled the data.

Concretely, in the real `lcm-vxlan-fabric-management.json` resource model, the action's `outputSchema` requires a job variable literally named `instance`, and `instance`'s own `required` array is expected to line up with the resource model's `schema.required`. The Create action workflow's entire job is to produce that `instance` object correctly populated. If the merge task that builds it only wires two of the four required fields (`vnet_name`, `vlan_id`) and omits `subscription_id` and `resource_group`, the resulting `instance` object is missing two required properties.

Per the skill's own debug guide (Guide 2 table), this exact shape of bug surfaces at runtime as:
```
"Schema validation failed on must have required property 'subscription_id'"
```
(then again for `resource_group` once the first is fixed) — and the fix documented in that same table is: *"Add the field to merge task."* That is exactly the corrective action needed here.

There's a second, quieter failure mode even if the platform didn't hard-reject the write: the instance record would persist with `subscription_id`/`resource_group` silently `undefined`. Any Update/Delete/Day-2 action workflow for this same model that reads those fields off the existing instance (a very common LCM pattern — see the `runAction` tasks in `lcm-vxlan-fabric-services-project.json`, which pull prior instance fields forward as `{"task": "<prevTask>", "value": "<field>"}`) would then propagate `undefined` values downstream, which is worse than an immediate loud failure because it surfaces later, in a different workflow.

## Recommended fix

Add `subscription_id` and `resource_group` as two more entries in the merge task's `data_to_merge`, sourced the same way the existing two fields are (job variables, most likely fed by the trigger form or a prior lookup task). Per the skill's merge-task rules:
- Use `"variable"` in the reference object, **not** `"value"` (that's the childJob syntax — mixing them is Gotcha #15 in the skill).
- `data_to_merge` already has ≥2 items so the "1 item silently returns null" gotcha (#16) doesn't apply, but double-check for duplicate keys across merges — duplicate keys silently become arrays, not overwrites (documented merge gotcha).
- After the merge task's `merged_object` is wired to `$var.job.instance` (writing to a job variable, not leaving `outgoing` as an unread task output, per the "Outgoing must write to job var" rule), confirm the workflow's `outputSchema.required` includes `"instance"` and that the workflow's own `inputSchema.required` includes all four source fields (`subscription_id`, `resource_group`, `vnet_name`, `vlan_id`) so the merge task can't even run with any of them missing.
- Before importing/running, use `POST /automation-studio/workflows/validate` (documented in the skill) and, if you want to directly confirm what the platform will reject, deliberately submit with a field still missing and read the exact validation message — the skill's Guide 1 Step 6 documents this "let the error tell you what's missing" technique for opaque schemas, and it applies here too.

## Artifacts produced

- `outputs/merge-task-BEFORE-problem.json` — the current (broken) merge task, reconstructed from the engineer's description, showing only `vnet_name` and `vlan_id` in `data_to_merge`.
- `outputs/merge-task-AFTER-fixed.json` — the corrected merge task with all four required fields (`subscription_id`, `resource_group`, `vnet_name`, `vlan_id`) added to `data_to_merge`, output wired to `$var.job.instance`.
- `outputs/create-action-workflow-fragment.json` — a minimal workflow fragment (`workflow_start` → fixed merge task → `workflow_end`) plus `inputSchema`/`outputSchema`, modeled directly on the real `outputSchema.required: ["instance"]` pattern confirmed in `helpers/assets/lcm/lcm-vxlan-fabric-management.json`, showing the fields required in and the `instance` object required out.

## Final answer to the engineer (verbatim)

Yes, that's a problem — and it will bite you. Your resource model's `schema.required` lists four fields (`subscription_id`, `resource_group`, `vnet_name`, `vlan_id`), and that requirement is enforced on the instance object itself, not on any one task in your workflow. Your Create action workflow's job is ultimately to produce a job variable named `instance` whose shape satisfies that model schema — I confirmed this exact contract (`outputSchema.required: ["instance"]`) against a real LCM resource model in the asset library (`helpers/assets/lcm/lcm-vxlan-fabric-management.json`). If your instance-write merge task's `data_to_merge` only populates `vnet_name` and `vlan_id`, the `instance` object you hand back will be missing `subscription_id` and `resource_group`, and the write will fail schema validation — you'll see something like `"Schema validation failed on must have required property 'subscription_id'"` (this is a documented, generic Itential failure mode, not LCM-specific).

Fix: add two more entries to `data_to_merge` for `subscription_id` and `resource_group`, using the same `{"task": "job", "variable": "..."}` reference shape as your existing two entries (remember merge uses the `"variable"` key, not `"value"` — that's childJob's syntax, and mixing them up is a common, silent-failure mistake). Then re-verify that the merge's `merged_object` is wired out to `$var.job.instance` and that your workflow's own `outputSchema` declares `instance` as required, with all four fields present in it. I've dropped a before/after of the merge task and a minimal workflow skeleton with the correct `inputSchema`/`outputSchema` into the outputs folder so you can diff against what you have.
