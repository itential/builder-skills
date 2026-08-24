#!/usr/bin/env python3
"""
WorkflowBuilder: a construction-time API for building Itential workflow
documents, instead of hand-authoring the final JSON and linting it after.

Why this exists: `validate_workflow.py` checks a workflow document AFTER
it's fully hand-authored -- reactive, and only as good as the list of
gotchas someone already discovered. The canvas UI never has this problem,
not because it validates better, but because it makes wrong states
unconstructible: task ids are generated, not typed; `$var` references are
assembled from cascading pickers over tasks that already exist, not typed
as raw strings; GoJS's linkingTool physically refuses to let you draw a
self-loop, a duplicate transition, or a loop-boundary violation.

This module replicates those SAME construction-time guarantees (not the
UI, just the state-machine logic behind it) so an agent building a
workflow through this API cannot express most of the gotchas in
`.claude/skills/builder-agent/SKILL.md` in the first place. `validate_workflow.py`
remains useful as a backstop for hand-authored/legacy JSON and for
anything a task type needs that this module doesn't yet model.

Every rule here is cited against real platform source in
docs/platform-validation-model.md -- this is not a guess at what the UI
does, it's a port of the actual logic:
  - task id generation:        app-automation_studio src/WorkflowEditor/util/workflow.js (makeTaskId)
  - field defaults/auto-inject: app-automation_studio src/WorkflowEditor/util/workflow.js (getTasksData, getIncomingDefault)
  - transition validation:      app-automation_studio src/WorkflowCanvas/Diagram.jsx (linkingTool.insertLink)
                                 app-automation_studio src/WorkflowCanvas/utils/diagram.js (checkForPath, validateLoopTransitions)
  - reference wiring:           app-automation_studio src/WorkflowEditor/shared/TaskVariableSelect.jsx, InputQuery.jsx
  - task field catalog:         app-workflow_builder cog.js (buildAutoTask) -> GET workflow_builder/tasks/list -> platform/tasks.json
  - per-field type/schema:      app-automation_studio lib/automations/methods/getTaskDetails.js
                                 -> GET automation-studio/locations/:location/packages/:pckg/tasks/:method?dereferenceSchemas=true
"""
import json
import random


class WorkflowBuilderError(Exception):
    """Raised when an operation would construct a state the real platform
    is known to reject, hang on, or silently mishandle. The message always
    names the specific rule, mirroring the canvas UI's own error toasts."""


# ---------------------------------------------------------------------------
# Task catalog: real field names/types, loaded from what this repo already
# pulls via scripts/platform_pull.py (platform/tasks.json), optionally
# layered with per-field schema detail from getTaskDetails.
# ---------------------------------------------------------------------------

class TaskCatalog:
    """Looks up a task's real incoming/outgoing field names (and, when
    available, per-field type/schema) so add_task() can reject unknown
    fields immediately instead of silently accepting a typo'd field name
    that fails at job start (or never fails at all)."""

    def __init__(self):
        self._by_key = {}       # (location, app, name) -> task meta from tasks.json
        self._details = {}      # (location, app, name) -> dereferenced getTaskDetails() result

    @classmethod
    def from_tasks_json(cls, path):
        catalog = cls()
        with open(path) as f:
            tasks = json.load(f)
        for t in tasks:
            key = (t.get('location'), t.get('app'), t.get('name'))
            catalog._by_key[key] = t
        return catalog

    def add_task_details(self, location, app, name, details):
        """Layer in a getTaskDetails()/multipleTaskDetails() result (real
        per-field type/schema/description, and invalidTaskActors) for one
        task. Optional -- add_task() works with just tasks.json, but
        without this, unknown-typed fields default to an empty string
        rather than a type-appropriate value."""
        self._details[(location, app, name)] = details

    def lookup(self, location, app, name):
        key = (location, app, name)
        meta = self._by_key.get(key)
        if meta is None:
            raise WorkflowBuilderError(
                f"No task {name!r} found for app {app!r} (location={location!r}) in the "
                f"loaded task catalog. Check platform/tasks.json for the real name/app/location "
                f"-- do not guess."
            )
        return meta

    def fields(self, location, app, name):
        meta = self.lookup(location, app, name)
        return set(meta.get('variables', {}).get('incoming', {}) or {})

    def canvas_name(self, location, app, name):
        return self.lookup(location, app, name).get('canvasName', name)

    def invalid_task_actors(self, location, app, name):
        return self.lookup(location, app, name).get('invalidTaskActors') or []

    def default_for(self, location, app, name, field):
        """Best-effort type-appropriate default for a field, using dereferenced
        getTaskDetails schema when loaded. Falls back to '' (matches the
        platform's own convention of empty-string placeholders on unbuilt
        fields) when no schema detail is available for this task."""
        details = self._details.get((location, app, name))
        if not details:
            return ''
        field_schema = (details.get('variables', {}).get('incoming', {}) or {}).get(field, {})
        schema = field_schema.get('schema', {})
        return _default_primitive_from_schema(schema, field_schema.get('type'))


def _default_primitive_from_schema(schema, declared_type):
    t = schema.get('type', declared_type)
    if 'enum' in schema and schema['enum']:
        return schema['enum'][0]
    if 'default' in schema:
        return schema['default']
    return {
        'string': '', 'number': 0, 'integer': 0, 'boolean': False,
        'array': [], 'object': {},
    }.get(t, '')


# ---------------------------------------------------------------------------
# Task-type-specific auto-injection, mirroring getTasksData/getDefaultActor.
# A short, explicit, enumerable list -- exactly as many special cases as the
# UI itself has, not guessed or extrapolated.
# ---------------------------------------------------------------------------

_ACTOR_DEFAULT_JOB = {'childJob', 'runAgent', 'forEach', 'eventListenerJob'}


def _default_actor(name):
    return 'job' if name in _ACTOR_DEFAULT_JOB else 'Pronghorn'


def _task_specific_defaults(name):
    if name == 'runCode':
        return {'language': 'python', 'safety': {'timeout': 1}}
    return {}


class TaskHandle:
    """Opaque reference to a task added to a WorkflowBuilder. Never construct
    directly -- returned by add_task()."""

    __slots__ = ('id', 'name')

    def __init__(self, task_id, name):
        self.id = task_id
        self.name = name

    def __repr__(self):
        return f"TaskHandle({self.id!r}, name={self.name!r})"


WORKFLOW_START = 'workflow_start'
WORKFLOW_END = 'workflow_end'


class WorkflowBuilder:
    def __init__(self, name, catalog, description='', workflow_type='automation'):
        self.name = name
        self.description = description
        self.type = workflow_type
        self.catalog = catalog
        self.tasks = {}          # taskId -> task dict (excludes workflow_start/workflow_end)
        self.transitions = {}    # fromId -> {toId: {type, state}}
        self._task_names = {}    # taskId -> name, including 'workflow_start'/'workflow_end'
        self._task_names[WORKFLOW_START] = 'workflow_start'
        self._task_names[WORKFLOW_END] = 'workflow_end'

    # -- construction ------------------------------------------------------

    def _new_task_id(self):
        while True:
            tid = format(random.randint(0, 0xffff), 'x')
            if tid not in self.tasks and tid not in (WORKFLOW_START, WORKFLOW_END):
                return tid

    def add_task(self, location, app, name, *, actor=None, task_id=None, **incoming):
        """Add a task. `incoming` kwargs are STATIC values only -- to wire a
        $var reference to another task's output, use ref()/job_ref() after
        adding both tasks. This is the structural guarantee that makes
        "$var doesn't resolve when nested inside a static literal" and
        "$var inside an array literal" impossible to hit: nothing in this
        API ever lets you hand-embed a $var string inside a bigger value."""
        known_fields = self.catalog.fields(location, app, name)
        unknown = set(incoming) - known_fields
        if unknown:
            raise WorkflowBuilderError(
                f"{name} has no incoming field(s) {sorted(unknown)}. Real fields per the "
                f"platform's own task catalog: {sorted(known_fields)}."
            )

        tid = task_id or self._new_task_id()
        if tid in self.tasks or tid in (WORKFLOW_START, WORKFLOW_END):
            raise WorkflowBuilderError(f"Task id {tid!r} already exists in this workflow.")

        special_defaults = _task_specific_defaults(name)
        resolved_incoming = {}
        for field in known_fields:
            if field in incoming:
                resolved_incoming[field] = incoming[field]
            elif field in special_defaults:
                resolved_incoming[field] = special_defaults[field]
            else:
                resolved_incoming[field] = self.catalog.default_for(location, app, name, field)

        meta = self.catalog.lookup(location, app, name)
        self.tasks[tid] = {
            'name': name,
            'canvasName': self.catalog.canvas_name(location, app, name),
            'summary': meta.get('summary', ''),
            'description': meta.get('description', ''),
            'app': app,
            'location': location,
            'locationType': meta.get('locationType'),
            'type': meta.get('type', 'automatic'),
            'displayName': meta.get('displayName', app),
            'actor': actor or _default_actor(name),
            'groups': [],
            'variables': {
                'incoming': resolved_incoming,
                'outgoing': {k: '' for k in (meta.get('variables', {}).get('outgoing', {}) or {})},
            },
        }
        self._task_names[tid] = name
        return TaskHandle(tid, name)

    # -- referencing ---------------------------------------------------
    # The ONLY way to wire a $var reference. Mirrors TaskVariableSelect's
    # cascading picker: you can only reference a task that already exists
    # in this workflow, and the reference always replaces a field's ENTIRE
    # value -- there is no code path here (same as in the real UI) that
    # lets a $var reference land inside a key of an already-static object.

    def ref(self, task, field, source, output_field, query_path=None):
        tid = self._id(task)
        sid = self._id(source)
        if sid not in self.tasks:
            raise WorkflowBuilderError(
                f"Cannot reference {sid!r}: it is not a task already added to this workflow. "
                f"(Referenced-task-existence is checked server-side too, but only advisorily -- "
                f"catching it here is free and immediate.)"
            )
        self._set_field(tid, field, f"$var.{sid}.{output_field}", query_path)

    def job_ref(self, task, field, job_variable_name, query_path=None):
        tid = self._id(task)
        self._set_field(tid, field, f"$var.job.{job_variable_name}", query_path)

    def _set_field(self, tid, field, ref_string, query_path):
        if field not in self.tasks[tid]['variables']['incoming']:
            raise WorkflowBuilderError(
                f"{self.tasks[tid]['name']} has no incoming field {field!r}."
            )
        value = ref_string
        pointer = f"/incoming/{field}"
        if query_path:
            value = f"{ref_string}#{query_path}"
        self.tasks[tid]['variables']['incoming'][field] = value
        if query_path:
            display_path = '.' + query_path.lstrip('/').replace('/', '.')
            decorators = self.tasks[tid]['variables'].setdefault('decorators', [])
            decorators[:] = [d for d in decorators if d.get('pointer') != pointer]
            decorators.append({'type': 'query', 'pointer': pointer, 'displayPath': display_path})

    # -- transitions ---------------------------------------------------
    # Ports GoJS's linkingTool.insertLink (Diagram.jsx) + checkForPath /
    # validateLoopTransitions (utils/diagram.js) verbatim. See
    # docs/platform-validation-model.md section 1 for the source citations.

    def connect(self, from_task, to_task, state='success'):
        f = self._id(from_task)
        t = self._id(to_task)

        if f == t:
            raise WorkflowBuilderError(f"Cannot connect task {f!r} to itself.")
        if self._task_names.get(f) == 'workflow_start' and self._task_names.get(t) == 'workflow_end':
            raise WorkflowBuilderError("Cannot connect workflow_start directly to workflow_end.")
        if t in self.transitions.get(f, {}):
            raise WorkflowBuilderError(f"Duplicate transition: {f!r} -> {t!r} already exists.")
        if state in ('failure', 'error') and f == WORKFLOW_START:
            raise WorkflowBuilderError(f"Cannot build a {state!r} transition from workflow_start.")
        if state == 'loop' and t == WORKFLOW_END:
            raise WorkflowBuilderError("Cannot build a loop transition to workflow_end.")
        if not self._validate_loop_transitions(f, t):
            raise WorkflowBuilderError(
                f"Cannot connect {f!r} -> {t!r}: crosses a forEach loop boundary "
                f"(one side is inside a loop the other isn't, or they're in different loops)."
            )

        transition_type = 'revert' if self._check_for_path(t, f) else 'standard'
        self.transitions.setdefault(f, {})[t] = {'type': transition_type, 'state': state}

    def _check_for_path(self, from_task, to_task):
        """BFS over standard-type transitions only -- port of checkForPath."""
        visited = set()
        queue = [from_task]
        limit = len(self.transitions) * 2 or 1
        while queue:
            cur = queue.pop(0)
            if cur == to_task:
                return True
            visited.add(cur)
            for nxt, tr in self.transitions.get(cur, {}).items():
                if tr['type'] == 'standard' and nxt not in visited:
                    queue.append(nxt)
            if len(queue) >= limit:
                return False
        return False

    def _transitions_on_path_to_start(self, task_id):
        """Reverse-walk from task_id back to workflow_start over ALL transition
        types, collecting every transition encountered -- port of getTransitions."""
        visited = set()
        found = []
        seen_pairs = set()

        def walk(current):
            if current == WORKFLOW_START or current in visited:
                return
            visited.add(current)
            for src, targets in self.transitions.items():
                tr = targets.get(current)
                if tr is not None and (src, current) not in seen_pairs:
                    seen_pairs.add((src, current))
                    found.append({'from': src, 'to': current, **tr})
                    walk(src)

        walk(task_id)
        return found

    def _validate_loop_transitions(self, from_task, to_task):
        from_path = self._transitions_on_path_to_start(from_task)
        to_path = self._transitions_on_path_to_start(to_task)
        from_loops = sorted({(t['from'], t['to']) for t in from_path if t['state'] == 'loop'})
        to_loops = sorted({(t['from'], t['to']) for t in to_path if t['state'] == 'loop'})

        if from_loops and self._check_for_path(to_task, WORKFLOW_END):
            return False
        if not to_path:
            return True
        if len(from_loops) == len(to_loops):
            return from_loops == to_loops if from_loops else True
        return False

    # -- completeness checks --------------------------------------------
    # Everything here is a structural fact this builder already tracked
    # incrementally -- unlike validate_workflow.py, which has to rediscover
    # the whole graph from a flat JSON blob after the fact.

    def finish(self):
        violations = []
        violations.extend(self._check_reachability())
        violations.extend(self._check_evaluation_completeness())
        violations.extend(self._check_forEach_closure())
        if violations:
            raise WorkflowBuilderError(
                "Workflow is incomplete:\n" + "\n".join(f"  - {v}" for v in violations)
            )
        return self

    def _check_reachability(self):
        reachable = {WORKFLOW_START}
        queue = [WORKFLOW_START]
        while queue:
            cur = queue.pop(0)
            for nxt, tr in self.transitions.get(cur, {}).items():
                if tr['type'] == 'standard' and nxt not in reachable:
                    reachable.add(nxt)
                    queue.append(nxt)
        return [
            f"task {tid!r} ({task['name']}) is not reachable from workflow_start via any "
            f"standard transition path."
            for tid, task in self.tasks.items() if tid not in reachable
        ]

    def _check_evaluation_completeness(self):
        violations = []
        for tid, task in self.tasks.items():
            if task['name'] != 'evaluation':
                continue
            states = {tr['state'] for tr in self.transitions.get(tid, {}).values()}
            missing = {'success', 'failure'} - states
            if missing:
                violations.append(
                    f"evaluation task {tid!r} is missing a {sorted(missing)} transition -- "
                    f"reaching that state with no transition hangs the job forever with no "
                    f"error anywhere (finishTask.js has no else branch for this case)."
                )
        return violations

    def _check_forEach_closure(self):
        violations = []
        for tid, task in self.tasks.items():
            if task['name'] != 'forEach':
                continue
            loop_starts = [dst for dst, tr in self.transitions.get(tid, {}).items() if tr['state'] == 'loop']
            stack, visited = list(loop_starts), set()
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                for dst, tr in self.transitions.get(cur, {}).items():
                    if tr['type'] != 'standard':
                        continue
                    if dst == tid:
                        violations.append(
                            f"forEach {tid!r}'s loop body task {cur!r} transitions back to the "
                            f"forEach task itself -- the last loop-body task must have NO "
                            f"outgoing transition (an empty {{}} entry), not a loop-back."
                        )
                    else:
                        stack.append(dst)
        return violations

    # -- serialization ----------------------------------------------------

    def to_document(self):
        tasks = dict(self.tasks)
        tasks[WORKFLOW_START] = {'name': 'workflow_start', 'groups': []}
        tasks[WORKFLOW_END] = {'name': 'workflow_end', 'groups': []}
        # Every task the BFS visits -- which includes any task with zero outgoing
        # transitions, not just workflow_end -- must have a transitions entry,
        # even an empty one. utils.js's validate() does
        # `Object.keys(workflow.transitions[current])` with NO guard for a missing
        # key; omitting this crashes workflow_builder/workflows/save with a
        # generic, unattributed "Cannot convert undefined or null to object"
        # (confirmed live against the real platform -- not documented anywhere
        # before this, found by bisection).
        transitions = dict(self.transitions)
        for tid in tasks:
            transitions.setdefault(tid, {})
        return {
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'canvasVersion': 3,
            'groups': [],
            'inputSchema': {'type': 'object', 'properties': {}, 'required': []},
            'outputSchema': {'type': 'object', 'properties': {}, 'required': []},
            'tasks': tasks,
            'transitions': transitions,
        }

    # -- helpers ------------------------------------------------------------

    def _id(self, task_or_id):
        if isinstance(task_or_id, TaskHandle):
            return task_or_id.id
        if task_or_id in self._task_names:
            return task_or_id
        raise WorkflowBuilderError(f"{task_or_id!r} is not a task handle or task id in this workflow.")
