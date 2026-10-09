#!/usr/bin/env python3
"""Enable Query decorators for Itential workflow JSON.

An Enable Query reference has two halves that must agree:
  - the value carries a `#/<path>` suffix        (what the job runs)
  - `decorators` has a matching query entry       (what Studio shows)
Without the decorator the job still runs, but Studio shows no query text, and opening then
saving the workflow silently strips the `#/<path>` -- the task then receives the whole object.

Usage:
  python3 enable_query.py check workflow.json        # list tasks whose decorators are missing/wrong
  python3 enable_query.py fix   workflow.json        # rewrite query decorators in place from the references

`fix` replaces only query decorators (others, e.g. `encryption`, are kept), lists what it can't repair
(those need a change to the references themselves) and exits 1 if anything is left. It writes the file
back as 2-space JSON, so on a hand-formatted file (e.g. helpers/assets) apply `check`'s findings by hand.

Library:
  from enable_query import apply_decorators
  apply_decorators(task)   # sets the query decorators a task's references call for, keeps the rest

Pointer rules (verified against Studio saves):
  top-level field        $var.x#/a/b                          /incoming/<field>
  key inside an object   $var.x#/a/b   (e.g. runCode data.k)  /incoming/<field>/<key>
  merge item             {"task","variable": "x#/a/b"}        /incoming/data_to_merge/<i>/value/variable
  childJob variable      {"task","value": "x#/a/b"}           /incoming/variables/<name>
  childJob data_array    $var.x#/a/b   (loop mode)            /incoming/data_array
  transformation input   variableMap.<input>: $var.x#/a/b     /incoming/variableMap/<input>
  evaluation             no decorator: use `query` / `rightQuery` on the evaluation object itself
"""
import json
import sys


def display_path(ref):
  """Studio's displayPath for a '#/' reference: array indexes as [n], JSON Pointer escapes (~1, ~0) undone,
  keys containing a dot as ["a.b"]."""
  out = ""
  for segment in ref.split("#/", 1)[1].split("/"):
    if segment.isdigit():
      out += f"[{segment}]"
    else:
      key = segment.replace("~1", "/").replace("~0", "~")
      out += (f'["{key}"]' if out else f'.["{key}"]') if "." in key else "." + key   # Studio: .body["a.b"], top level .["a.b"]
  return out


def has_query(value):
  return isinstance(value, str) and "#/" in value


def _walk(value, path):
  """Yield (pointer_path, string) for every '$var...#/...' string under an incoming value."""
  if isinstance(value, str):
    if value.startswith("$var.") and "#/" in value:
      yield path, value
  elif isinstance(value, dict):
    for key, item in value.items():
      yield from _walk(item, path + [key])
  elif isinstance(value, list):
    for index, item in enumerate(value):
      yield from _walk(item, path + [str(index)])


# Tasks whose object field resolves `$var` one key deep (verified: runCode data, transformation variableMap;
# the others per the skill's $var rules).
ONE_KEY_DEEP = {("runCode", "data"), ("transformation", "variableMap"), ("runService", "params"),
                ("runServiceStatic", "params"), ("runAgent", "inputs")}


def nested_refs(task):
  """`$var` strings placed inside a static object/array where they will NOT resolve (sent as literal text)."""
  incoming = task.get("variables", {}).get("incoming", {})
  if task.get("name") in ("childJob", "merge", "evaluation"):
    return []
  out = []
  for field, value in incoming.items():
    if isinstance(value, (dict, list)):
      for parts, ref in _walk_all(value, [field]):
        allowed = (task.get("name"), field) in ONE_KEY_DEEP and len(parts) == 2
        if not allowed:
          out.append(("/incoming/" + "/".join(parts), ref))
  return out


def _walk_all(value, path):
  if isinstance(value, str):
    if value.startswith("$var."):
      yield path, value
  elif isinstance(value, dict):
    for key, item in value.items():
      yield from _walk_all(item, path + [key])
  elif isinstance(value, list):
    for index, item in enumerate(value):
      yield from _walk_all(item, path + [str(index)])


def decorators_for(task):
  """Return the decorators a task's current references call for."""
  incoming = task.get("variables", {}).get("incoming", {})
  name = task.get("name")
  decorators = []

  def add(pointer_parts, ref):
    decorators.append({"type": "query", "pointer": "/incoming/" + "/".join(pointer_parts),
                       "displayPath": display_path(ref)})

  if name == "childJob":
    for key, ref in incoming.get("variables", {}).items():
      if isinstance(ref, dict) and has_query(ref.get("value")):
        add(["variables", key], ref["value"])
    for field, value in incoming.items():   # childJob's own fields, e.g. data_array in loop mode
      if field != "variables" and has_query(value) and str(value).startswith("$var."):
        add([field], value)
  elif name == "merge":
    for index, item in enumerate(incoming.get("data_to_merge", [])):
      ref = item.get("value")
      if isinstance(ref, dict) and has_query(ref.get("variable")):
        add(["data_to_merge", str(index), "value", "variable"], ref["variable"])
  elif name != "evaluation":
    unresolvable = {pointer for pointer, _ in nested_refs(task)}
    for field, value in incoming.items():
      for parts, ref in _walk(value, [field]):
        if "/incoming/" + "/".join(parts) not in unresolvable:
          add(parts, ref)
  return decorators


def apply_decorators(task):
  """Set the query decorators a task's references call for, keeping any other decorators.
  Returns True if the task changed."""
  variables = task.setdefault("variables", {})
  current = variables.get("decorators", [])
  updated = [d for d in current if d.get("type") != "query"] + decorators_for(task)
  if updated == current:
    return False
  variables["decorators"] = updated
  return True


def check_task(task):
  """Return a list of problems for one task (empty list means decorators agree with references)."""
  want = {d["pointer"]: d["displayPath"] for d in decorators_for(task)}
  have = {d.get("pointer"): d.get("displayPath")
          for d in task.get("variables", {}).get("decorators", []) if d.get("type") == "query"}
  problems = []
  for pointer, shown in want.items():
    if pointer not in have:
      problems.append(f"missing decorator for {pointer} (Studio will show no query)")
    elif have[pointer] != shown:
      problems.append(f"{pointer}: displayPath {have[pointer]!r} does not match reference ({shown!r})")
  nested = {pointer for pointer, _ in nested_refs(task)}
  for pointer in have:
    if pointer not in want and pointer not in nested:
      problems.append(f"decorator {pointer} points at no '#/' reference (dangling)")
  for pointer, ref in nested_refs(task):
    problems.append(f"{pointer}: `$var` inside a static object does not resolve (sent as the literal text {ref!r}); "
                    "reference the whole field and build the object upstream")
  incoming = task.get("variables", {}).get("incoming", {})
  if task.get("name") == "merge":
    refs = [("data_to_merge/%d" % i, item.get("value")) for i, item in enumerate(incoming.get("data_to_merge", []))]
  elif task.get("name") == "childJob":
    refs = [("variables/" + k, v) for k, v in incoming.get("variables", {}).items()]
  else:
    refs = []
  for where, ref in refs:
    if (task.get("name") == "merge" and isinstance(ref, dict) and has_query(ref.get("value"))
        and not has_query(ref.get("variable"))):
      problems.append(f"{where}: query on `value` resolves to null at runtime; put '<output>#/path' on `variable` "
                      "(Studio keeps `value: <output>` and adds `variable: <output>#/path`)")
    if isinstance(ref, dict) and "query" in ref:
      problems.append(f"{where}: a `query` key beside the reference is ignored at runtime and invisible in "
                      "Studio; use '<var>#/path' plus a decorator instead")
  if task.get("name") == "evaluation":
    for group in task.get("variables", {}).get("incoming", {}).get("evaluation_groups", []):
      for item in group.get("evaluations", []):
        for side in ("operand_1", "operand_2"):
          operand = item.get(side)
          if isinstance(operand, dict) and "query" in operand:
            problems.append(f"{side}.query is ignored at runtime and invisible in Studio; "
                            "put query/rightQuery on the evaluation object instead")
  return problems


def find_tasks(document):
  """Yield (location, task) for every workflow task found anywhere in a JSON document."""
  if isinstance(document, dict):
    tasks = document.get("tasks")
    if isinstance(tasks, dict) and "transitions" in document:
      for task_id, task in tasks.items():
        if isinstance(task, dict) and "variables" in task:
          yield f"{document.get('name', '?')}:{task_id}", task
    for value in document.values():
      yield from find_tasks(value)
  elif isinstance(document, list):
    for value in document:
      yield from find_tasks(value)


def main(argv):
  if len(argv) != 3 or argv[1] not in ("check", "fix"):
    print(__doc__)
    return 2
  mode, path = argv[1], argv[2]
  with open(path) as handle:
    document = json.load(handle)
  failures, changed = 0, False
  for location, task in find_tasks(document):
    problems = check_task(task)
    if not problems:
      continue
    if mode == "fix" and apply_decorators(task):
      changed = True
      print(f"fixed decorators: {location} ({task.get('name')})")
      problems = check_task(task)
    if not problems:
      continue
    failures += 1
    for problem in problems:
      prefix = "needs a manual change: " if mode == "fix" else ""
      print(f"{prefix}{location} ({task.get('name')}): {problem}")
  if changed:
    with open(path, "w") as handle:
      json.dump(document, handle, indent=2, ensure_ascii=False)
      handle.write("\n")
  print("OK" if not failures else f"{failures} task(s) need attention")
  return 1 if failures else 0


if __name__ == "__main__":
  sys.exit(main(sys.argv))
