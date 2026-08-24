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

    for tid, task in tasks.items():
        name = task.get('name')
        incoming = task.get('variables', {}).get('incoming', {})
        outgoing = task.get('variables', {}).get('outgoing', {})

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

        # forEach: the last loop-body task must end in an empty {} transition, not a
        # loop-back to the forEach task's own id. getEndTasks/markIterationTasks walk
        # forward over standard transitions with no boundary check for re-entering the
        # forEach task -- a loop-back corrupts the endTasks/iterationTask bookkeeping
        # that handleNextIteration depends on to detect "iteration finished, start next."
        if name == 'forEach':
            loop_starts = [
                target for target, t in transitions.get(tid, {}).items()
                if t.get('type') == 'loop'
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
