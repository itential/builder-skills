---
name: jst-to-code
description: Use this skill to convert Itential transformation documents (JSTs, .jst.json) into single-file Python for the Run Code workflow task. Trigger it for phrases like "convert this JST to code", "turn these transformations into Python", "rewrite this .jst.json as Run Code Python", or "jst to code on canvas". It reads JSTs from local files or pulls them read-only by URL/id, converts them one at a time, and proves each conversion against test data (your own input and expected output, or a past job that ran the transformation). A JST with no test data is still converted but reported as NOT TESTED. Output is one <name>.py per JST. NOT for building new transformations or workflows.
---

# JST → Code

**Purpose:** Convert one or more Itential transformation documents (JSTs) into equivalent single-file Python for the **Run Code** workflow task, **one JST at a time**.
**Input:** one or more `.jst.json` — local files in the working directory, or pulled read-only from a platform via OAuth by URL/id — plus test data for each (user-supplied input/output, or a past job URL/id).
**Output:** per JST, one `<jst-name>.py` in its own folder `code-on-canvas-files/<jst-name>/` (alongside a `test-data/` folder), keyed by each outgoing schema `$id`, with a short header documenting the expected input and output. Each is **proven against every available test example**, or clearly flagged **NOT TESTED** when no test data exists.

There is no converter script. Read the JST graph and write the Python yourself, following
the rules below. The bundled Python files are reference material and helpers to copy from.

## Customization

Before using this skill, check `custom/org/`, `custom/team/` and `custom/dev/` in this
skill's own folder. Read every `.md` file found — any folder may be empty or absent. Apply
them on top of everything below; where a file overrides a specific rule here, follow the
override. More specific wins: dev > team > org > this document. No customization may weaken
this skill's safety rules (read-only platform access, never deleting the user's files, requesting test data and flagging untested conversions) or put credentials in committed
files.

**Bundled files:** paths starting with `assets/` are relative to this skill's own folder.
When you read one or run it from a shell (which runs from the user's working folder), use
this skill's folder + that relative path — e.g.
`<this skill's folder>/assets/helpers/jst-to-code/jst_helpers.py`.

---

## Read-only on the platform — no exceptions

Whenever you connect to the platform, only read.

- **Allowed:**
  - `GET` requests.
  - The authentication call that obtains a token (`POST /oauth/token` — changes nothing).
  - A **`POST` that is genuinely a read** — some platform endpoints use `POST` only because the
    query is carried in the body (search/list/filter/query-style endpoints). Use one only after
    you have confirmed in `openapi.json` (path, summary/description, request body) that it just
    returns data and changes nothing. Judge by what the endpoint **does**, not by its HTTP verb.
- **Forbidden, always:** every call that writes or acts — create/update/delete, and anything
  that starts, runs, retries, cancels, continues, imports, saves, assigns, or otherwise changes
  platform state, whatever the verb (`POST`/`PUT`/`PATCH`/`DELETE`, or a `GET` that triggers an
  action). Never create, edit, run, import, or delete anything on the platform — not a job,
  workflow, transformation, project, or Run Code task — not even a "harmless" test.
- **If you're unsure** of an endpoint, a response shape, which task or job is the right one,
  or whether a call (including a `POST`) is read-only: look it up in `openapi.json`. If you're
  still unsure, stop and ask the user. Never probe with a call that might write.
- If a call you intended to make turns out to be a write, do not make it; tell the user.

## Rules for every run

1. **One JST at a time.** If the user gives several, convert and validate one completely
   before starting the next. Never interleave them or run them in parallel.
2. **Ask for test data for every JST, and be honest about it.** Get input and expected-output
   examples for each (user samples, or a past job URL/id — see Step 2). If the user has none
   for a JST, still convert it, but mark it **NOT TESTED** in the file header and the report,
   and call the mapping best effort. Never present an untested conversion as verified.
3. **Stop after the report.** When every JST is done, give the Step 6 report and hand-off,
   then stop — see "Stop after the hand-off" under Step 6.

---

## What a JST is

A JST (`.jst.json`) is a JSON **dataflow graph**, always 100% JSON in and 100% JSON out:

- **`incoming`** — array of JSON-Schema inputs; each has a `$id`, `type`, optional `examples`.
- **`outgoing`** — array of JSON-Schema outputs; each has a `$id`. One output object can be
  assembled from several `assign`s writing different JSON-pointer sub-paths (e.g.
  `info/originalSize` and `info/newSize` are two assigns into the same `info` object).
- **`steps`** — two kinds, mixed in arbitrary order:
  - `method` — a native-JS library call: `id` + `library` + `method` + `args`. An `args` slot
    holds `null` until an `assign` fills it, a literal value, or a string naming a nested
    function (e.g. `"ƒ_query_1"`).
  - `assign` — a wire: `from {location, name, ptr}` → `to {location, name, ptr}`, where
    `location` is `incoming` / `outgoing` / `method` / `function`, `name` is a schema `$id`
    (for incoming/outgoing) or a method `id`, and `ptr` is a JSON Pointer like `/args/0/value`
    or `/return`.
- **`functions`** — nested functions used as callbacks for `filter`/`map`/`reduce`/`sort`/etc.
  Each has the **same** structure recursively (its own incoming/outgoing/steps/functions) and
  a `name`/`id` like `ƒ_query_1`.

Only native JS methods run inside a JST, plus one custom method: WorkflowEngine **`query`**
(a JSON-path query over an object). The full method catalog and its Python mapping is in
`assets/helpers/jst-to-code/jst-method-map.md`.

## How to read a JST graph

Work this out before writing any code.

The `steps` array is **not** in execution order — order is implied by the wiring. Resolve it:

1. **Separate steps.** Collect the `method` steps (the operations, each with an `id`) and the
   `assign` steps (the wires). Ignore `view` (canvas coordinates) — it does not affect logic.
2. **Resolve each method's arguments.** For method `M`, look at every `assign` whose `to` is
   `{location: "method", name: M, ptr: "/args/N/value"}`. Its `from` tells you where arg `N`
   comes from:
   - `from.location == "incoming"` → the input `data["<$id>"]`.
   - `from.location == "method"` (ptr `/return`) → the result of that other method.
   - `from.location == "function"` → a nested callback (resolve it as in step 4).
   - No assign targets arg `N` → use the literal already sitting in that `args[N]` slot. A
     string literal that matches a nested function's name is a **callback reference**, not text.
3. **Order by data dependency (topological).** A method that consumes another method's
   `/return` must run after it. Chain each result into a clearly named local variable. Methods
   with no dependency between them can go in any order (match the natural read order).
4. **Translate nested functions.** A function used by `filter`/`map`/`some`/`every`/`find`/
   `findIndex` receives `(element, index, array)`; `reduce`/`reduceRight` receives
   `(accumulator, currentValue, index, array)`; `sort` receives a comparator. Resolve the
   function's own inner graph the same way (steps 1–3) and emit it as a **`lambda`** for a
   one-expression body or a named **`def`** for a multi-step body. Its `outgoing` is the
   return value.
5. **Assemble the outputs.** For every `assign` whose `to.location == "outgoing"`, place the
   resolved source value at that outgoing `$id` + `ptr`. Group multiple pointer sub-paths into
   one nested object (so `/originalSize` + `/newSize` build a single `info`). The final result
   is one object **keyed by each outgoing `$id`**.

Work through the example in `assets/helpers/jst-to-code/examples/` end to end before
converting an unfamiliar JST — `demo-fruits.jst.json` → `demo-fruits.py` shows every rule above.

## The Run Code contract (the conversion target)

The generated Python runs as a single file in a Run Code task:

- **Input:** `data = json.load(sys.stdin)` where `data` is an object **keyed by each incoming
  `$id`**. (In the task's Data tab the user maps one key per incoming to a workflow variable.)
- **Output:** `print(json.dumps(result))` where `result` has **a key per outgoing `$id`**,
  e.g. `{"info": {"originalSize": 3, "newSize": 2}, "newFruits": ["APPLE", "BANANA"]}`. The
  task parses stdout into `result.stdout_json`.
- **Constraints:** single file ≤ 2 MB, **native Python / PyPI only** (prefer native — a JST
  only uses native JS, so native Python always covers it), timeout 1–1000s.

**Header comment (required, kept SHORT).** Open the file with a brief docstring and nothing
else — no walkthrough of the JST's steps, no test-data filenames, no run commands, no caveats:
- **Line 1:** `Replaces the "<JST name>" transformation.`
- **Optionally one more line** saying what it does — only if you are sure; otherwise omit it.
  Two lines maximum in total.
- **INPUT / OUTPUT — mirror the JST's structure exactly, and make the shape unmistakable.**
  Each incoming/outgoing `$id` is **one variable** (one key of `data` / of `result`). State the
  variable count in the heading, then list **one variable per line** with its type:
  - JST with 3 incoming `$id`s → `INPUT (3 variables):` and three lines.
  - JST with ONE incoming `$id` that is an object with keys → `INPUT (1 variable):` and one
    line, `name  object {key1, key2, key3}`. Never flatten an object's keys into separate
    variables, and never list separate variables as if they were keys of one object.
  - If an object is large, show only the main keys the code actually reads (not the full
    schema); for a very large output, just give the type or the top-level key shape.

See `assets/helpers/jst-to-code/examples/demo-fruits.py` for the exact style.

**File shape:**
```python
"""Replaces the "<JST name>" transformation. <optional: one line on what it does.>

INPUT (<n> variable(s)):
  <id>  <type>  [object {main keys}]
OUTPUT (<n> variable(s)):
  <id>  <type>  [object {main keys}]
"""
import sys, json          # + math / re / datetime / functools only if used
# --- inlined helpers (only the ones this file uses) ---
def js_truthy(v): ...
# --- main ---
def main():
    data = json.load(sys.stdin)
    <ordered operations into named locals>
    result = { "<outgoingId>": ..., ... }
    print(json.dumps(result))
if __name__ == "__main__":
    main()
```

For any method flagged `HELPER` in `jst-method-map.md`, **copy only the helper functions you
use** from `assets/helpers/jst-to-code/jst_helpers.py` into the top of the generated file
(Run Code is single-file — never `import` it, never paste the whole module). `CLEAN` methods
need nothing; honor the `REVIEW` notes.

---

## Flow

```
/jst-to-code
   ├── Step 0: Working directory (required — don't start without one)
   ├── Step 1: Get the JST(s) (local files, or OAuth pull by URL/id)
   ├── Step 2: Get test data per JST — every example available (user samples, or every run in a past job)
   ├── For EACH JST, one at a time, in sequence:
   │     ├── Step 3: Convert — read the graph, write <name>.py → code-on-canvas-files/<name>/
   │     └── Step 4: Validate — run every example and diff it (or mark NOT TESTED if no data)
   ├── Step 5: Clean up — remove only the temporary files this run created
   └── Step 6: Report per JST, hand off to the user, then stop
```

### Step 0 — Working directory (hard gate)

Don't start without a working directory. If the user didn't name one, ask: "Which directory
should I work in?" Write everything there and nowhere else — never into this repo: the pulled
JSTs, any job data, and `code-on-canvas-files/` (one subfolder per JST, holding its `.py` and
a `test-data/` folder).

### Step 1 — Get the JST(s)

Build the list of JSTs to convert, from either source (or a mix):

- **Local:** `.jst.json` files the user has placed in the working directory (typically in a
  `jst/` folder there). Use the ones the user names; if they point at a folder, every
  `.jst.json` in it.
- **Remote (OAuth):** one or more URLs/ids of transformations. Authenticate using the
  `.auth.json` / `.env` reuse pattern in `assets/AGENTS.md` ("Auth Reuse") — read `.auth.json`
  for a token, fall back to `.env` creds, silently re-auth on 401/403, never ask for
  credentials if `.env` exists. **Read-only: reads only (see the Hard rule above).** Fetch each
  transformation (confirm the endpoint and response shape against the working directory's
  `openapi.json` — do not guess paths; see `assets/AGENTS.md`, "Look Up Before You Act") and
  save it as a `.jst.json` in the working directory.

List the JSTs back to the user (name, source) before going on. Process them in the order
given (or alphabetical for a folder).

### Step 2 — Get the test data for each JST

Each JST needs **examples**: one concrete input (keyed by each incoming `$id`) plus its
expected output (keyed by each outgoing `$id`). Collect every example available, not just the
first — more examples make stronger proof that the code does what the JST does. Accept either source, per JST or shared across several:

- **(a) Local / user-provided examples.** Sample input(s) and expected output(s) the user gives
  in the chat or places in the working directory. **Matching them to JSTs:** with a single
  JST it is obvious. With several, match by file name, by folder, or by shape (a sample's keys
  equal that JST's incoming `$id`s / its output keys equal the outgoing `$id`s). **If you are
  not sure which sample belongs to which JST, stop and ask the user to say explicitly which
  is which — never guess.**
- **(b) A past job run (URL or id)**, pulled via OAuth. **Every task in the job has its own
  incoming and outgoing data — each transformation task's pair is one example.** (This is NOT
  the job's flat output variables.) A job may run the same JST **several times** (several
  tasks, and/or several iterations per task, e.g. loops or reruns) — **take all of them.** One
  job may also contain several different JSTs; pull the job once and **auto-match** each
  transformation task to the right JST by `tr_id`. Procedure:
  1. Take the job id from the URL. `GET /operations-manager/jobs/{id}` (confirm the endpoint
     against `openapi.json`). In `data.tasks`, the job document holds only **placeholders** —
     values like `variableMap.*: null` — so do not read test data from here; use it only to
     locate the tasks.
  2. **Find the transformation tasks:** the entries in `data.tasks` whose
     `variables.incoming.tr_id` exists (`app: WorkFlowEngine`, `name: transformation`). `tr_id`
     is the transformation's id.
  3. **Match each to a JST in your list.** Compare `tr_id` with the JST's `_id`; if the JST has
     no `_id` (local file), `GET /transformations/{tr_id}` and compare `name` and the
     incoming/outgoing `$id`s. Keep only tasks that match a JST you are converting; ignore
     other transformations in the job. If a task's match is ambiguous, ask the user. If no
     task matches a given JST, that job gave it no data.
  4. **Get the real data from each matching task's iterations.** Each matching task lists
     iteration ids in `iterations`. For **every** iteration, `GET
     /operations-manager/tasks/{iterationId}` (the task document) and read:
     - **input** = `data.variables.incoming.variableMap` (keyed by incoming `$id`)
     - **expected output** = `data.variables.outgoing` (keyed by outgoing `$id`)
     Each successful iteration (`status: complete` / `metrics.finish_state: success`) is one
     example. Skip failed iterations and any with an empty/null input or output (not usable) —
     and say how many you skipped.

**If any JST still has no usable examples, ask the user for them** (samples or a job URL/id) —
once, covering every JST that lacks data. If the user has none, **convert that JST anyway,
mark it NOT TESTED**, and carry that flag through to the file header and the report. Never
invent test data yourself to make a conversion look verified.

**Save the examples** (JSTs that have any) in a `test-data/` folder next to that JST's
generated code, **one file per example**, named `example1.json`, `example2.json`, … Each file holds exactly two keys — the
input and the expected output for that one example:

```json
{
  "example1Input":  { "<incomingId>": ... },
  "example1Output": { "<outgoingId>": ... }
}
```

(For `example2.json` the keys are `example2Input` / `example2Output`, and so on.)

Resulting layout:

```
code-on-canvas-files/
└── <jst-name>/
    ├── <jst-name>.py
    └── test-data/
        ├── example1.json
        ├── example2.json
        └── ...
```

### Step 3 — Convert (one JST at a time)

Take the JSTs **one at a time, in order**; run Steps 3 and 4 completely for one before starting
the next. Read the JST's graph using **"How to read a JST graph"** above, map each
`(library, method)` via `assets/helpers/jst-to-code/jst-method-map.md`, inline any needed
helpers from `jst_helpers.py`, and write the Python in the file shape shown under the Run Code
contract, including the short header comment. Save it as `<jst-name>.py` (same base name as
the JST) in `code-on-canvas-files/<jst-name>/`, next to its `test-data/` folder.

If the JST has **no test data**, add one extra line to the header docstring, right under the
title line: `NOT TESTED - best-effort mapping, verify before use.` Tested JSTs get no such line.

### Step 4 — Validate against every example

**With test data**, run the code against every `test-data/exampleN.json`:

1. For each example, pipe its `exampleNInput` value to the code on stdin:
   `python3 code-on-canvas-files/<name>/<name>.py` (stdin = the `exampleNInput` JSON).
2. **Diff** the printed JSON against that example's `exampleNOutput`. They must match — same
   outgoing `$id` keys and the same values (compare structurally; ignore insignificant key
   ordering).
3. On any mismatch, fix the generated Python (re-check your graph reading and the `REVIEW`
   notes for the methods involved) and **re-run all examples** — a fix for one can break
   another. If the same class of error recurs twice (see `assets/AGENTS.md`, Repeat-Failure
   Circuit Breaker), stop working on this JST: mark it **FAILED** with the specific difference
   and **move on to the next JST** — do not keep guessing.

A JST is **PASSED** only when **all** its examples match their expected outputs exactly.

**Without test data** — you cannot diff. Only check that the file is syntactically valid
(e.g. `python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" <file>` — do not
`py_compile`, which writes `__pycache__`) and mark the JST **NOT TESTED**.

**A failure never stops the batch.** If a JST fails validation, or hits an unsupported/
ambiguous method (see Edge cases), mark it **FAILED** / **NEEDS REVIEW** with the reason,
leave its best-effort `.py` in its folder, and continue with the next JST. The final report
lists everything.

### Step 5 — Clean up (only what you created)

Once all JSTs are processed, remove the temporary files **this run generated** in the working
directory that are not part of the task's deliverable.

**Keep (never delete):**
- **Everything that was already in the working directory** before the skill started — the
  user's files, folders, JSTs, `.env`, `.auth.json`, `openapi.json`, notes, anything. If you
  did not create it in this run, it is not yours to touch.
- The deliverables: each `code-on-canvas-files/<jst-name>/` (the `.py` and `test-data/`).
- The JSTs you were converting (including copies you pulled remotely) and the
  credential/auth files (`.env`, `.auth.json`).

**Remove (only if you created it this run):** scratch artifacts unrelated to the task's
input/output — raw job/task/transformation API response dumps, intermediate or scratch
scripts, helper snippets, temp/test-run output files, `__pycache__`, and anything else that
was only a stepping stone (e.g. an `openapi.json` you pulled because none existed).

Rules:
- **Track what you create** as you go so you know exactly what is yours. If you cannot tell
  whether a file was there before the run, **leave it** and mention it to the user.
- Delete by explicit path only — never wildcard/recursive deletes over the working directory
  or any folder you didn't create.
- Never delete anything outside the working directory.

### Step 6 — Report

Give a **per-JST status list** so the user sees at a glance what to trust. For each JST state:
its name, the generated `.py` path, and one status:

- **PASSED** — all N examples matched (say N, the test-data source — user samples or job
  URL — and how many examples were skipped as unusable).
- **NOT TESTED** — no test data; conversion is **best effort**, the mapping was not verified
  against any real input/output.
- **FAILED / NEEDS REVIEW** — what differed (actual vs expected) or which method was
  unsupported/ambiguous.

Also list any methods handled under a `REVIEW` caveat (regex, dates, randomness, `query`
expressions outside the supported subset) for the user to eyeball. Make any NOT TESTED / FAILED
items impossible to miss — put them first.

Then close with this **hand-off to the user** (adapt the paths, keep the content):

> The converted code is in `code-on-canvas-files/` — one folder per JST, each with its
> `<jst-name>.py` and test data. To use it, **you** do the following:
> 1. Open the JST's folder and take the `.py` code.
> 2. In each workflow that uses that JST, add a **Run Code** task and paste the code in.
> 3. Update the task's code, **input variables** (one per incoming `$id`) and **output
>    variables** (read from `result.stdout_json`, keyed by outgoing `$id`) to fit that workflow.
> 4. **Do not delete any JST** until you have replaced it in every workflow that might use it
>    and confirmed those workflows still work. For anything marked NOT TESTED, FAILED or
>    NEEDS REVIEW, check the code yourself first.

### Stop after the hand-off

Once you've given the hand-off, you're done. Replacing the JSTs in workflows is the user's
work, not yours.

- Don't suggest further work or follow-ups (no "want me to convert more?", no offers to edit
  workflows, run jobs or clean up).
- Don't start other skills or tools on your own, and don't touch the platform: don't add a
  Run Code task to any workflow, don't change or delete any JST, workflow or project, and
  don't search for which workflows use the JST.
- Only act further if the user explicitly asks in a new message.

---

## Edge cases & failure modes

- **JS truthiness ≠ Python.** `[]`, `{}`, `"0"` are truthy in JS. Any value used as a
  condition (filter predicate, `if`, ternary, `&&`/`||`/`!`) goes through `js_truthy`.
- **Loose `==` vs strict `===` vs `deepEquals`** → `js_loose_eq` / `js_strict_eq` /
  `deep_equals`; bool is distinct from number in JS.
- **`typeof`** (`Json.typeof`) → `js_typeof`: null, array and object all return `"object"`.
- **`nullish ??`** falls back only on `null`/`undefined`, not on `0`/`""` (unlike `||`).
- **Division is float** (`/`, never `//`); **`remainder`** sign follows the dividend
  (`js_remainder`, not Python `%`); **`Math.round`** is half-up (`math.floor(x+0.5)`).
- **Default `Array.sort` is lexicographic**, not numeric — don't emit a bare numeric sort
  unless the JST supplied a numeric comparator.
- **Mutating array methods** (`push`/`pop`/`shift`/`unshift`/`splice`/`sort`/`reverse`/
  `fill`/`setIndex`/`copyWithin`) mutate in place and return a JS-specific value
  (`push` → new length, `pop` → removed element, `splice` → removed slice).
- **Regex** — JS and Python `re` differ (flags, named groups, Unicode classes, no sticky
  flag); translate carefully and flag `REVIEW`.
- **Dates/locale** — JS months are 0-indexed, epoch is in ms, `toLocale*` is locale/timezone
  dependent; approximate and flag `REVIEW`.
- **Custom `query`** — `jst_helpers.query` supports a JSONPath subset (`$`, `.key`, `[i]`,
  `[*]`/`.*`, `..key`) and returns a LIST of matches. Filters `[?()]`, slices, unions are NOT
  supported — hand-translate those, don't guess.
- **`null`/`undefined` → `None`.** Prefer `.get()` over `[]` for possibly-absent object keys.
- **Multiple outgoing / pointer sub-paths** — assemble nested objects per the graph-reading
  rules.
- **Closures** — a nested function referencing an outer-scope value is rare; handle explicitly
  and flag if seen.
- **Unsupported or ambiguous method → mark that JST NEEDS REVIEW and flag it.** Never emit a
  plausible-looking guess for semantics you can't verify from the map, the schema, or the
  test-data diff; leave the unverified part clearly marked and continue with the next JST.

## Bundled assets

- `assets/helpers/jst-to-code/jst-method-map.md` — full JST method → Python mapping table.
- `assets/helpers/jst-to-code/jst_helpers.py` — pure-Python runtime helpers to inline.
- `assets/helpers/jst-to-code/examples/demo-fruits.jst.json`,
  `assets/helpers/jst-to-code/examples/demo-fruits.py`,
  `assets/helpers/jst-to-code/examples/test-data/example1.json`,
  `assets/helpers/jst-to-code/examples/test-data/example2.json` — worked example
  with its header comment and two test examples (the `exampleNInput` / `exampleNOutput` format).
- `assets/AGENTS.md` — platform auth-reuse, look-up-before-you-act, job-variable path, and
  circuit-breaker rules (remote mode).
