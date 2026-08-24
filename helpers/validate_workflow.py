#!/usr/bin/env python3
"""
Static validator for workflow JSON documents.

Every rule here is grounded in the real Itential Platform source
(app-workflow_builder / app-workflow_engine / app-automation_studio), not
just an empirically-observed symptom. See docs/platform-validation-model.md
for the full findings this validator is built from -- in short: the
platform's own workflow validation is almost entirely advisory (it never
blocks a save), and several of these mistakes cause a job to hang forever
with zero error surfaced anywhere. This script is the only real safety net
for most of them; run it before saving or starting a job against a workflow
you built by hand.

Usage:
    python3 validate_workflow.py path/to/workflow.json
    echo '{"tasks": {...}, ...}' | python3 validate_workflow.py -

Exit code 0 = no violations. Exit code 1 = one or more violations found (printed to stdout).
"""
import json
import re
import sys

TASK_VAR_RE = re.compile(r'^\$var\.([^.]+)\.')

# The real, closed enum for evaluation operators. Confirmed against
# openapi.json's workflow_engine_wfEngineCommon_evaluationItem.properties.operator.enum --
# anything else (e.g. "regex", "contains_key", "in", "startsWith") does not exist
# and silently returns false with no error.
EVALUATION_OPERATORS = {'contains', '!contains', '<', '<=', '>', '>=', '==', '!='}

# Product policy, not a platform bug: Golden Config detects and reports drift, it
# never applies fixes to a device. `updateNodeConfig` is deliberately excluded --
# it authors the GC node template, not a device.
_PROHIBITED_REMEDIATION_TASKS = {
    'runAutoRemediation', 'advancedAutoRemediation', 'convertChangesToConfig',
    'patchDeviceConfiguration', 'advancedPatchDeviceConfiguration',
    'patchCMDeviceConfiguration', 'ManualRemediation', 'ManualRemediationResults',
}


def collect_strings(value, path=""):
    """Recursively yield (path, string) for every string nested inside value."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from collect_strings(item, f"{path}[{i}]")
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from collect_strings(v, f"{path}.{k}" if path else k)


def find_violations(workflow: dict) -> list[str]:
    violations = []
    tasks = workflow.get('tasks', {})
    transitions = workflow.get('transitions', {})

    # NOTE: workflowDocument.json declares task ids as hex [0-9a-f]{1,4}, but this
    # is NOT enforced here -- tracing the real request path (core/WebServer.js)
    # found no AJV call against this schema for a normal POST /workflows/save body,
    # and this repo has a directly live-tested, working reference asset
    # (runcode-taskquery-reference.json) with a non-hex task id ("tagCreate").
    # Flagging it would be a confirmed false positive against known-working data.

    # Every task -- including workflow_end, and any other task with zero outgoing
    # transitions -- MUST have a key in `transitions`, even an empty {}. Confirmed
    # live against the real platform by bisection: utils.js's validate() does
    # `Object.keys(workflow.transitions[current])` during its BFS with no guard for
    # a missing key. Omitting this crashes workflow_builder/workflows/save with a
    # generic, unattributed "Cannot convert undefined or null to object" -- not
    # documented anywhere else. A real canvas-saved document always carries an
    # explicit "workflow_end": {} for exactly this reason.
    all_task_ids = set(tasks) | {'workflow_start', 'workflow_end'} if tasks else set()
    for tid in sorted(all_task_ids):
        if tid not in transitions:
            violations.append(
                f"[{tid}] has no entry in \"transitions\" at all (not even {{}}) -- if "
                f"anything transitions to this task, saving the workflow crashes with "
                f"\"Cannot convert undefined or null to object\". Add "
                f"\"transitions\": {{..., {tid!r}: {{}}}} even if this task has no "
                f"real outgoing transitions."
            )

    for tid, task in tasks.items():
        name = task.get('name')
        incoming = task.get('variables', {}).get('incoming', {})
        outgoing = task.get('variables', {}).get('outgoing', {})

        # Golden Config remediation tasks are a product-policy prohibition, not a
        # platform bug: Golden Config detects and reports drift, it never applies
        # fixes to a device. A workflow that wires one of these -- even if a spec
        # asks for fully automatic remediation -- is doing something the platform
        # will happily run but this org has decided never to build. Mechanically
        # checkable (it's just a task name), so it's a rule here, not just prose.
        if name in _PROHIBITED_REMEDIATION_TASKS:
            violations.append(
                f"[{tid}] {name!r} is a Configuration Manager remediation task -- "
                f"prohibited in every workflow, even when a spec asks for fully "
                f"automatic remediation. Golden Config detects and reports drift; it "
                f"never applies fixes to a device. Build a normal config-push delivery "
                f"instead. (`updateNodeConfig` is fine -- it authors the GC node "
                f"template, not a device.)"
            )

        # childJob can't resolve project-scoped workflow names ("@<projectId>: <name>").
        # jobStart.js resolves purely by `{name}` against the workflows collection with
        # no prefix-stripping -- this fails at runtime with "Cannot find workflow ...",
        # even from a caller in the same project.
        if name == 'childJob':
            workflow_ref = incoming.get('workflow')
            if isinstance(workflow_ref, str) and workflow_ref.strip().startswith('@'):
                violations.append(
                    f"[{tid}] childJob.workflow = {workflow_ref!r} looks project-scoped "
                    f"-- jobStart.js resolves by exact name with no '@projectId:' stripping, "
                    f"so this will fail at job start with \"Cannot find workflow ...\". "
                    f"Inline the target task(s) instead; there is no known childJob workaround."
                )

            # childJob.actor must be "Pronghorn", "job", or an existing task id.
            # getActor() (worker/helpers/utils.js) only special-cases those two literals;
            # anything else is indexed as a task id and throws a generic
            # "Cannot read properties of undefined (reading 'owner')" if it isn't real.
            actor = task.get('actor')
            if actor not in ('Pronghorn', 'job') and actor not in tasks:
                violations.append(
                    f"[{tid}] childJob.actor = {actor!r} is not \"Pronghorn\", \"job\", or "
                    f"an existing task id in this workflow -- job start will throw "
                    f"\"Cannot read properties of undefined (reading 'owner')\"."
                )

        # merge entries must have a real "value": {"task": ..., "variable": ...} wrapper.
        # The compiler (jobStart compile path) unconditionally reads data.value.task with
        # no guard -- a missing or misnamed wrapper throws "Cannot read properties of
        # undefined (reading 'task')" at job start. This is silent at save time: schema
        # computation uses a defensive copy that doesn't crash on the same bad input.
        if name == 'merge':
            for entry in incoming.get('data_to_merge', []) or []:
                value = entry.get('value')
                if not isinstance(value, dict) or 'task' not in value:
                    violations.append(
                        f"[{tid}] merge entry {entry.get('key')!r} is missing a proper "
                        f"\"value\": {{\"task\": ..., \"variable\": ...}} wrapper (got "
                        f"{entry!r}) -- fails at job start with \"Cannot read properties "
                        f"of undefined (reading 'task')\", not at save time."
                    )

        # push: incoming.job_id must be omitted. The platform injects the real job id
        # THEN spreads authored incoming over it, so an authored job_id silently wins
        # and is wrong -- no error, just bad data.
        if name == 'push':
            if 'job_id' in incoming:
                violations.append(
                    f"[{tid}] push.incoming includes \"job_id\" -- the real job id is "
                    f"injected first and then silently overwritten by this authored "
                    f"value (utils.js spreads incoming after injection). No error is "
                    f"raised; the job just uses the wrong id."
                )
            # Empirically confirmed bad, but NOT backed by any platform-side check --
            # no code reads/validates this value, only its key name. Keep this rule
            # narrowly scoped to the one confirmed-bad shape; don't extend without
            # live verification.
            if outgoing.get('job_variable_value') == {}:
                violations.append(
                    f"[{tid}] push.outgoing.job_variable_value is an empty object -- "
                    f"confirmed bad in practice, must be a real declared value."
                )

        # parse's real fields are text/textObject (string/index.js + string/ph.json),
        # not stringToParse/result -- that's a stale doc name, not a real field.
        if name == 'parse':
            wrong_fields = {'stringToParse', 'result'} & set(incoming.keys())
            if wrong_fields:
                violations.append(
                    f"[{tid}] parse.incoming uses {sorted(wrong_fields)} -- the real field "
                    f"names are \"text\"/\"textObject\", not \"stringToParse\"/\"result\"."
                )

        # objectToString's replacer is passed straight into JSON.stringify with no
        # guard (object/index.js) -- an empty array replacer allow-lists zero keys,
        # silently producing "{}" for any input. No error, ever.
        if name == 'objectToString':
            if 'replacer' in incoming and incoming['replacer'] in ([], None):
                violations.append(
                    f"[{tid}] objectToString.incoming.replacer is {incoming['replacer']!r} "
                    f"-- this is a property whitelist passed straight to JSON.stringify, "
                    f"not a no-op. An empty list silently produces \"{{}}\" for every "
                    f"input. Omit the \"replacer\" key entirely if you don't need it."
                )

        # InventoryManager.getNodesByInventory requires "params" at runtime even though
        # the live schema doesn't mark it required (empirically confirmed, not traced
        # to a specific source line -- this is app-specific model behavior, not
        # workflow_engine's own logic).
        if name == 'getNodesByInventory' and 'params' not in incoming:
            violations.append(
                f"[{tid}] getNodesByInventory is missing \"params\" -- required at "
                f"runtime despite the live schema not marking it required:true. "
                f"Omitting it fails job start with \"Cannot find match for input: "
                f"\\\"params\\\" from model\". Always pass \"params\": {{}} explicitly."
            )

        # Manual tasks (ViewData/ViewHTML/viewTemplateResults/etc): draft-validation-
        # error traps, mechanically checkable from the JSON alone. Confirmed live.
        # `workflow_builder.py`'s add_task() gets these right automatically; this is
        # the backstop for hand-authored JSON.
        if task.get('type') == 'manual':
            # "view" required and "actor" forbidden are structural requirements of
            # type:manual itself -- confirmed to apply generically, not tied to one
            # specific manual task's field schema.
            if not task.get('view'):
                violations.append(
                    f"[{tid}] manual task {name!r} has no top-level \"view\" field (or "
                    f"it's empty) -- fails with \"Manual Tasks require 'view' key with "
                    f"path to task view\". Must be a sibling of \"name\"/\"type\"/\"app\", "
                    f"not inside \"variables\"."
                )
            if 'actor' in task:
                violations.append(
                    f"[{tid}] manual task {name!r} has an \"actor\" key ({task['actor']!r}) "
                    f"-- manual tasks have no actor at all, not \"Pronghorn\", not null. "
                    f"Omit the key entirely."
                )
            # incoming.variables being required-if-present is specific to ViewData/
            # ViewHTML's own field schema -- OTHER manual tasks (e.g. MOP's
            # viewTemplateResults, whose only real field is mop_template_results)
            # don't declare a "variables" field at all, so checking for it there
            # would be a false positive. Confirmed by reading both schemas directly.
            if name in ('ViewData', 'ViewHTML') and 'variables' not in incoming:
                violations.append(
                    f"[{tid}] manual task {name!r} is missing incoming.\"variables\" -- "
                    f"fails with \"Input: 'variables' is not defined in task model\" even "
                    f"though it's optional in the schema. Always include it, even as {{}}."
                )

        # evaluation needs both a "success" and a "failure" outgoing transition.
        # A failed evaluation explicitly returns undefined -> mapped to 'failure'
        # state. If that state has no transition, finishTask.js's addSubsuquentTaskUpdates
        # has NO ELSE BRANCH -- nothing happens: no error, no queue, the job just hangs.
        # Nothing in the platform's own validation checks this either.
        if name == 'evaluation':
            states = {t.get('state') for t in transitions.get(tid, {}).values()}
            missing = {'success', 'failure'} - states
            if missing:
                violations.append(
                    f"[{tid}] evaluation task is missing a {sorted(missing)} transition "
                    f"-- if execution reaches that state with no transition defined, the "
                    f"job hangs forever with NO error surfaced anywhere (confirmed: the "
                    f"only safety net, updateJob.js's \"no available transitions\" check, "
                    f"doesn't fire for this case)."
                )

            # evaluation operators are a closed enum -- anything else silently
            # compiles to a no-match, returning false with an empty outgoing and
            # no error message at all. Source of truth: openapi.json's
            # workflow_engine_wfEngineCommon_evaluationItem.properties.operator.enum.
            for group in incoming.get('evaluation_groups', []) or []:
                for entry in group.get('evaluations', []) or []:
                    op = entry.get('operator')
                    if op is not None and op not in EVALUATION_OPERATORS:
                        violations.append(
                            f"[{tid}] evaluation operator {op!r} is not in the real closed "
                            f"enum {sorted(EVALUATION_OPERATORS)} -- an invalid operator "
                            f"silently returns false with no error message, it does not fail "
                            f"loudly."
                        )

        # forEach: the last loop-body task must end in an empty {} transition, not a
        # loop-back to the forEach task's own id. getEndTasks/markIterationTasks walk
        # forward over standard transitions with no boundary check for re-entering the
        # forEach task -- a loop-back corrupts the endTasks/iterationTask bookkeeping
        # that handleNextIteration depends on to detect "iteration finished, start next."
        if name == 'forEach':
            loop_starts = [
                target for target, t in transitions.get(tid, {}).items()
                if t.get('state') == 'loop'
            ]
            visited = set()
            stack = list(loop_starts)
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                for target, t in transitions.get(cur, {}).items():
                    if t.get('type') != 'standard':
                        continue
                    if target == tid:
                        violations.append(
                            f"[{tid}] forEach loop body task {cur!r} has a standard "
                            f"transition back to the forEach task itself ({tid!r}) -- "
                            f"the last loop-body task must end in an empty {{}} "
                            f"transition instead. This silently corrupts loop-iteration "
                            f"bookkeeping (no error raised)."
                        )
                    else:
                        stack.append(target)

            # $var.<taskId>.<field> does not resolve inside a forEach loop body when
            # <taskId> is the forEach task itself or any task OUTSIDE the loop body --
            # confirmed live (documented example: $var.n01.current_item, n01 being the
            # forEach task). This does NOT apply to sibling-to-sibling references
            # between two tasks that are BOTH inside the same loop body -- confirmed
            # against real production assets that wire loop-body tasks to each other
            # this way extensively. `visited` here is exactly the set of loop-body
            # task ids already computed above.
            for body_tid in visited:
                if body_tid not in tasks:
                    continue
                body_incoming = tasks[body_tid].get('variables', {}).get('incoming', {})
                for field, value in body_incoming.items():
                    if not isinstance(value, str):
                        continue
                    m = TASK_VAR_RE.match(value)
                    if not m or m.group(1) == 'job':
                        continue
                    ref_tid = m.group(1)
                    if ref_tid == tid or ref_tid not in visited:
                        violations.append(
                            f"[{body_tid}] incoming.{field} = {value!r} is inside forEach "
                            f"{tid!r}'s loop body and references a task outside the loop "
                            f"body (the forEach task itself or an external task) -- this "
                            f"does not resolve inside a loop body, for any reference style. "
                            f"Bind the source task's outgoing to a job variable and use "
                            f"$var.job.<name> instead."
                        )

        # $var does not resolve inside array or nested-object literal VALUES -- only
        # a field whose entire top-level value is a string gets classified/resolved
        # (standardTaskIncomings does a plain `typeof value === 'string'` check per
        # key of whatever object it's handed). Anything nested one level further is
        # stored as an opaque static literal, $var and all, with no recursive walk.
        #
        # Exceptions confirmed in compileIncomingValues (jobs/helpers/utils.js):
        # - transformation.variableMap, runCode.data, runAgent.inputs, and
        #   runService(Static).params are each handed to standardTaskIncomings
        #   DIRECTLY (not as part of the outer incoming object), so $var DOES
        #   resolve one level deep inside these specific fields -- only flag
        #   $var found nested a level BEYOND that unwrap.
        # - merge/deepmerge, evaluation, childJob, and runAction compile their
        #   incoming entirely through custom per-task logic using a
        #   {"task": ..., "variable": ...} addressing shape, not "$var." text --
        #   skip them here; the merge-specific and childJob-specific checks above
        #   already cover their real failure modes.
        ONE_LEVEL_UNWRAPPED_FIELD = {
            'transformation': 'variableMap',
            'runCode': 'data',
            'runAgent': 'inputs',
            'runService': 'params',
            'runServiceStatic': 'params',
        }
        CUSTOM_COMPILED_TASKS = {'merge', 'deepmerge', 'evaluation', 'childJob', 'runAction'}

        if name not in CUSTOM_COMPILED_TASKS:
            unwrapped_field = ONE_LEVEL_UNWRAPPED_FIELD.get(name)
            for field, value in incoming.items():
                if field == unwrapped_field and isinstance(value, dict):
                    # This field's own direct children resolve like top-level
                    # incoming fields would -- only recurse into grandchildren.
                    scan_value, scan_prefix = value, field
                    children = scan_value.items()
                else:
                    children = [(field, value)]

                for child_field, child_value in children:
                    if not isinstance(child_value, (list, dict)):
                        continue
                    full_field = f"{field}.{child_field}" if child_field != field else field
                    for subpath, s in collect_strings(child_value, full_field):
                        if '$var.' in s:
                            violations.append(
                                f"[{tid}] incoming.{subpath} is nested inside a "
                                f"{'list' if isinstance(child_value, list) else 'object'} "
                                f"literal and contains {s!r} -- $var never resolves here; "
                                f"the containing value is stored as an opaque static "
                                f"literal. Build the value with newVariable + push instead, "
                                f"then reference the whole result as a single top-level "
                                f"$var.job.<name>."
                            )

        # Referenced-task existence: $var.<taskId>.<field> must point at a task
        # that actually exists in this workflow. The platform does check this at
        # validate time, but only advisorily (never blocks a save) -- free to check
        # statically, so do it here too. Applies to every task type, including the
        # custom-compiled ones skipped above.
        for field, value in incoming.items():
            if isinstance(value, str):
                m = TASK_VAR_RE.match(value)
                if m and m.group(1) != 'job' and m.group(1) not in tasks:
                    violations.append(
                        f"[{tid}] incoming.{field} = {value!r} references task "
                        f"{m.group(1)!r}, which does not exist in this workflow's tasks."
                    )

    return violations


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)

    src = sys.stdin if sys.argv[1] == '-' else open(sys.argv[1])
    with src:
        workflow = json.load(src)

    # Accept either a bare workflow document or the {"components": [...]} project-export
    # wrapper used by this repo's helper assets -- validate every workflow found in either.
    if 'components' in workflow:
        docs = [c['document'] for c in workflow['components'] if c.get('type') == 'workflow']
    else:
        docs = [workflow]

    all_violations = []
    for doc in docs:
        all_violations.extend(find_violations(doc))

    if all_violations:
        print(f"{len(all_violations)} violation(s) found:\n")
        for v in all_violations:
            print(f"  - {v}\n")
        sys.exit(1)

    print("No violations found.")
    sys.exit(0)


if __name__ == '__main__':
    main()
