# Transcript — builder-agent skill test: LCM Create action instance-write merge task

## Task restated

The engineer is building the **Create action workflow** for a new LCM (Lifecycle Manager) resource
model. The model's `schema.required` array lists four fields: `subscription_id`, `resource_group`,
`vnet_name`, `vlan_id`. The workflow's instance-write `merge` task currently has a `data_to_merge`
that only includes `vnet_name` and `vlan_id` (missing `subscription_id` and `resource_group`).
Question: is that a problem?

## Steps taken

1. **Read the builder-agent SKILL.md in full** (`/Users/ankitrbhansali/builderskills/builder-skills/.claude/skills/builder-agent/SKILL.md`,
   2442 lines, read in full via paginated Read + targeted grep) before answering, per the eval
   instructions and per the skill's own "STOP — read asset projects before writing task JSON"
   directive.

2. **Located the exact rule governing this scenario** in Guide 1, Step 9 ("Pre-submit checklist"),
   at line 373:

   > `[ ] **LCM Create actions only:** the instance-write merge task's `data_to_merge` covers every
   > field in the resource model's `schema.required` array — missing even one field causes an
   > instance write failure after provisioning (resources are orphaned from LCM). Read the model's
   > `schema.required` before building the merge task: `jq '.schema.required' helpers/assets/lcm/<model>.json``

   This is a direct, explicit, named rule for exactly this situation — not an inference.

3. **Verified the rule's context against the real LCM asset library** referenced by the skill
   (`${CLAUDE_PLUGIN_ROOT}/helpers/assets/lcm/`), which resolved to
   `/Users/ankitrbhansali/builderskills/builder-skills/helpers/assets/lcm/`:
   - Listed the LCM model files: `lcm-fan-device-lifecycle-management.json`,
     `lcm-interface-service-provisioning.json`, `lcm-ip-blocking-service.json`,
     `lcm-port-turn-up.json`, `lcm-vxlan-fabric-management.json`,
     `lcm-vxlan-fabric-services-project.json`.
   - Pulled `schema.required` from each real model with
     `jq -r '.data.schema.required // .schema.required // "N/A"' <file>` to confirm real production
     models do carry non-empty `required` arrays (e.g., `lcm-fan-device-lifecycle-management.json`
     requires `becentralId`, `mac`, `serialNumber`, `customerId`; `lcm-interface-service-provisioning.json`
     requires `customerName`, `orderId`). This confirms the checklist rule reflects a real, recurring
     platform constraint, not a hypothetical edge case.
   - Inspected the backing project `lcm-vxlan-fabric-services-project.json` (`.data.components[]`
     wrapper) to study real LCM action workflow structure: listed its workflows (`VXLAN Fabric
     Services - Create`, `- Parent Create`, `- Delete Service`, `- Re-provision`, `- Decommission`,
     `- Day 2 Operations`), and inspected the `LifecycleManager.runAction` task and the child
     `transformation`/`merge`-adjacent tasks that feed instance data, to ground the answer in how
     LCM instance data actually flows through a Create workflow (formData → transformation/merge →
     `runAction` → instance write). This confirmed the general pattern: whatever fields end up in
     the object written to the instance must be a complete superset of `schema.required`, because
     LCM validates the instance write against the model's schema.

4. **Cross-referenced the general `merge` task rules** (SKILL.md `### merge` section, ~line 1378)
   to make sure any fix respects the platform's other merge constraints:
   - `data_to_merge` needs at least 2 items (already true here).
   - Reference field is `"variable"`, not `"value"` (this is a merge task, so that's correct already).
   - `{"task": "job", "variable": "x"}` should be used **only** for genuine workflow inputs — using
     it for internally-produced values incorrectly adds them to `inputSchema.required` and prompts
     operators for values they should never supply. This matters when fixing the merge: whether
     `subscription_id` / `resource_group` should be added as `{task:"job", ...}` refs depends on
     whether they are true operator inputs (most likely, for Azure-style scoping fields) or values
     produced earlier in the workflow (e.g., resolved/looked up).
   - Duplicate keys across merged sources produce arrays instead of overwriting — not directly
     relevant here (all 4 keys are added once, flat), but worth a callout since it's an easy
     follow-on mistake when engineers "helpfully" merge two objects that both contain overlapping
     keys.

5. **Also confirmed the standing LCM rule in AGENTS.md / the Helper Templates table**: "every LCM
   action workflow **must** declare and output an `instance` variable — this is what LCM uses to
   track resource state between actions," reinforcing why an incomplete instance write is
   catastrophic specifically for LCM (not just a generic missing-field bug) — LCM's whole
   state-tracking model depends on the instance record being complete after the Create action runs.

## Diagnosis

**Yes — this is a problem, and it is called out explicitly in the builder-agent skill as a
mandatory pre-submit check specifically for this scenario.**

- The resource model's `schema.required` (`subscription_id`, `resource_group`, `vnet_name`,
  `vlan_id`) defines the fields LCM will validate against when it writes/updates the instance
  record for this resource.
- The `merge` task that builds the instance-write payload only supplies 2 of the 4 required
  fields (`vnet_name`, `vlan_id`). `subscription_id` and `resource_group` are missing.
- Per the skill's explicit rule: *"missing even one field causes an instance write failure after
  provisioning (resources are orphaned from LCM)."* This is not a soft warning — it's a hard
  failure mode with a specific and costly consequence: the underlying resource (e.g., the Azure
  VNet/VLAN) gets provisioned successfully by the earlier tasks in the workflow, but the LCM
  instance write step then fails schema validation because the object is incomplete. The result is
  an **orphaned resource** — something now exists in the target system that LCM has no record of,
  so it can never be tracked, updated, or deleted through subsequent LCM lifecycle actions
  (Update, Delete, Re-provision, etc.). That's a materially worse failure than a normal task error,
  because it isn't just a failed job — it leaves real infrastructure untracked and unmanageable
  through the platform going forward.

## Recommended fix

1. Add `subscription_id` and `resource_group` as entries in the merge task's `data_to_merge`, the
   same way `vnet_name` and `vlan_id` are already wired.
2. Before wiring, confirm the *source* of each value:
   - If `subscription_id` / `resource_group` are values the operator supplies when triggering the
     Create action (the common case for Azure-style scoping fields), reference them as
     `{"task": "job", "variable": "subscription_id"}` / `{"task": "job", "variable":
     "resource_group"}` — same pattern as `vnet_name`/`vlan_id`.
   - If either value is actually produced earlier in the workflow (e.g., resolved by a lookup or
     default-injection task rather than supplied directly by the operator), reference the
     *producing task's* output instead (e.g., `{"task": "<taskId>", "variable": "return_data"}`).
     Do **not** use `{"task":"job", ...}` for internally-produced values — that incorrectly adds
     them to `inputSchema.required` and forces operators to supply something that should be
     computed internally.
3. Re-verify against the **actual** model file for this use case with
   `jq '.schema.required' helpers/assets/lcm/<model>.json` (or the live/exported model) — don't
   assume the four field names quoted in the question are the final, authoritative set; confirm
   directly from the schema before finalizing the merge task.
4. After fixing, re-run the pre-submit checklist item verbatim: the instance-write merge's
   `data_to_merge` must cover every entry in `schema.required` — no more, no less is required, but
   nothing in `required` can be missing.
5. Test the Create action end-to-end and confirm via `GET` on the created instance (or by
   inspecting the job's outgoing `instance` variable) that all four fields — `subscription_id`,
   `resource_group`, `vnet_name`, `vlan_id` — are present in the written instance record, not just
   that the job status shows "complete."

## Artifacts produced

- `/Users/ankitrbhansali/builderskills/builder-skills/evals/workspace/iteration-3/eval-27/new_skill/run-1/outputs/instance-write-merge-task-fixed.json`
  — a before/after JSON showing the broken merge task (2 of 4 required fields) and the corrected
  merge task (all 4 required fields wired), plus inline notes on the caveats above (source of each
  field, `merge` task constraints, and where to re-verify the required-field list for the real
  model).

## Final answer to the engineer (verbatim)

> Yes, that's a problem — and a serious one for LCM specifically. Your model's `schema.required`
> has 4 fields (`subscription_id`, `resource_group`, `vnet_name`, `vlan_id`), but your
> instance-write merge only builds 2 of them (`vnet_name`, `vlan_id`). The builder-agent skill has
> a hard rule for exactly this case: the instance-write merge's `data_to_merge` has to cover
> *every* field in `schema.required`, because missing even one causes the instance write to fail
> after the underlying resource has already been provisioned — which orphans the resource from
> LCM. That's worse than a normal failed job: your VNet/VLAN gets created in the target system, but
> LCM never records the instance, so nobody can manage, update, or delete that resource through
> LCM afterward.
>
> Fix: add `subscription_id` and `resource_group` to the merge task's `data_to_merge`, the same way
> `vnet_name`/`vlan_id` are already wired. If those two are values the operator supplies when
> kicking off Create, wire them as `{"task": "job", "variable": "subscription_id"}` and
> `{"task": "job", "variable": "resource_group"}`. If either is actually computed by an earlier
> task in your workflow rather than supplied directly, wire it from that task's output instead
> (`{"task": "<taskId>", "variable": "<outVar>"}`) — don't use a `{task:"job"}` ref for something
> that isn't a genuine operator input, because that silently adds it to `inputSchema.required` and
> starts prompting operators for a value they shouldn't have to give. Before you finalize, re-pull
> `schema.required` straight from your actual model file (`jq '.schema.required'
> helpers/assets/lcm/<your-model>.json`) to make sure those are really the only 4 required fields —
> don't rely on memory of the spec. Then test the Create action and inspect the written instance
> (not just the job status) to confirm all 4 fields actually landed in it.
