# JST method → Python mapping reference

Every method a JST `method` step can call, with its Python equivalent. Use this while
reading a JST graph (see the "How to read a JST graph" section of SKILL.md): each `method`
step carries `library` + `method` + ordered `args`; look up `(library, method)` here.

**Flags**
- `CLEAN` — 1:1 with a Python builtin/operator. Just emit it.
- `REVIEW` — maps, but JS and Python differ semantically. Read the note; the generated code
  must account for it, and you should call it out in the final report.
- `HELPER` — needs a function from `jst_helpers.py`. Copy that function into the generated
  file (tree-shake — only the ones you use) and call it.

**Arg convention below:** `x`, `y` are the resolved args in order; `f` is a nested-function
callback (emit it as a `lambda` for a one-expression body, or a named `def` for a multi-step
body). JS array callbacks receive `(element, index, array)`;
`reduce` receives `(accumulator, currentValue, index, array)`.

---

## Array  (`library: "Array"`)

| method | Python | Flag | Note |
|---|---|---|---|
| newArray | `list(args)` or `[]` | CLEAN | |
| concat | `x + y` | CLEAN | shallow concat of lists |
| copyWithin | in-place slice copy | REVIEW | mutates; rarely used — translate explicitly |
| every | `all(f(e,i,x) for i,e in enumerate(x))` | REVIEW | wrap predicate result in `js_truthy` if it may return non-bool |
| fill | `x[a:b] = [v]*(b-a)` | REVIEW | mutates in place; returns the array |
| filter | `[e for i,e in enumerate(x) if js_truthy(f(e,i,x))]` | HELPER | predicate truthiness is JS, not Python — use `js_truthy` |
| find | `next((e for i,e in enumerate(x) if js_truthy(f(e,i,x))), None)` | HELPER | `None` when not found |
| findIndex | `next((i for i,e in enumerate(x) if js_truthy(f(e,i,x))), -1)` | HELPER | `-1` when not found |
| flat | one level: `[v for e in x for v in (e if isinstance(e,list) else [e])]` | REVIEW | default depth 1; deeper needs recursion |
| flatMap | `[v for i,e in enumerate(x) for v in _aslist(f(e,i,x))]` | REVIEW | map then flatten one level |
| from | `list(x)` | CLEAN | `Array.from` |
| getIndex | `x[i]` | REVIEW | JS tolerates out-of-range → `undefined`; Python raises — guard if needed |
| includes | `v in x` | CLEAN | |
| indexOf | `x.index(v) if v in x else -1` | REVIEW | JS returns -1 when absent |
| isArray | `isinstance(x, list)` | CLEAN | |
| join | `sep.join(map(_jsstr, x))` | REVIEW | JS stringifies items (null→"", nested via toString); default sep is "," |
| lastIndexOf | `len(x)-1-x[::-1].index(v) if v in x else -1` | REVIEW | -1 when absent |
| length | `len(x)` | CLEAN | |
| map | `[f(e,i,x) for i,e in enumerate(x)]` | CLEAN | |
| pop | `x.pop()` | REVIEW | mutates; returns removed element (`None` if empty in JS) |
| push | `x.append(v)` then value is `len(x)` | REVIEW | JS `push` returns the NEW length, not the item |
| reduce | `functools.reduce(lambda a,c: f(a,c,...), x, init)` | REVIEW | import `functools`; handle optional initial value |
| reduceRight | `functools.reduce(lambda a,c: f(a,c,...), reversed(x), init)` | REVIEW | right-to-left |
| reverse | `x.reverse()` returns `x` | REVIEW | mutates in place |
| setIndex | `x[i] = v` | REVIEW | mutates |
| shift | `x.pop(0)` | REVIEW | mutates; returns removed first element |
| slice | `x[a:b]` | REVIEW | JS negative indices behave like Python; omitted end → `x[a:]` |
| some | `any(js_truthy(f(e,i,x)) for i,e in enumerate(x))` | HELPER | |
| sort | `x.sort(key=functools.cmp_to_key(cmp))` | REVIEW | DEFAULT JS sort is LEXICOGRAPHIC on stringified items — `x.sort(key=str)`, not numeric. With a comparator use `cmp_to_key` |
| splice | explicit slice delete/insert | REVIEW | mutates; returns removed elements |
| toLocaleString | `",".join(map(str, x))` | REVIEW | locale-dependent in JS; approximate |
| unshift | `x.insert(0, v)` then value is `len(x)` | REVIEW | returns NEW length |

---

## String  (`library: "String"`)

| method | Python | Flag | Note |
|---|---|---|---|
| new | `str(x)` | CLEAN | |
| charAt | `x[i] if 0<=i<len(x) else ""` | REVIEW | JS returns "" out of range |
| charCodeAt | `ord(x[i])` | REVIEW | UTF-16 code unit in JS; fine for BMP |
| codePointAt | `ord(x[i])` | CLEAN | |
| concat | `x + y` | CLEAN | |
| endsWith | `x.endswith(y)` | CLEAN | |
| fromCharCode | `chr(n)` | CLEAN | |
| fromCodePoint | `chr(n)` | CLEAN | |
| includes | `y in x` | CLEAN | |
| indexOf | `x.find(y)` | CLEAN | `.find` returns -1 like JS (do NOT use `.index`) |
| lastIndexOf | `x.rfind(y)` | CLEAN | -1 when absent |
| length | `len(x)` | CLEAN | |
| localeCompare | `(x>y)-(x<y)` | REVIEW | locale-naive |
| match | `re.search`/`re.findall` | REVIEW | JS regex dialect — see Regex notes |
| matchAll | `list(re.finditer(p, x))` | REVIEW | regex dialect |
| normalize | `unicodedata.normalize("NFC", x)` | REVIEW | import `unicodedata`; pass the requested form |
| padEnd | `x.ljust(n, pad)` | REVIEW | JS repeats a multi-char pad string; `ljust` only pads single char |
| padStart | `x.rjust(n, pad)` | REVIEW | same multi-char caveat |
| repeat | `x * n` | CLEAN | |
| replace | `x.replace(a, b, 1)` / `re.sub` | REVIEW | string form replaces FIRST only in JS; regex form replaces per flags |
| search | `m.start() if (m:=re.search(p,x)) else -1` | REVIEW | regex dialect |
| slice | `x[a:b]` | CLEAN | |
| split | `x.split(sep)` | REVIEW | `split("")` in JS → list of chars → use `list(x)`; no-arg → `[x]` |
| startsWith | `x.startswith(y)` | CLEAN | |
| substring | `x[a:b]` | REVIEW | JS `substring` swaps args if a>b and clamps negatives to 0 |
| templateLiteral | f-string / `"".join` | REVIEW | rebuild from the pieces the JST concatenated |
| toLocaleLowerCase | `x.lower()` | CLEAN | |
| toLocaleUpperCase | `x.upper()` | CLEAN | |
| toLowerCase | `x.lower()` | CLEAN | |
| toUpperCase | `x.upper()` | CLEAN | |
| trim | `x.strip()` | CLEAN | |
| trimEnd | `x.rstrip()` | CLEAN | |
| trimStart | `x.lstrip()` | CLEAN | |

---

## Object  (`library: "Object"`)

| method | Python | Flag | Note |
|---|---|---|---|
| new | `{}` or `dict(x)` | CLEAN | |
| entries | `list(x.items())` | CLEAN | emit as list of `[k, v]` pairs for JSON parity |
| fromEntries | `dict(x)` | CLEAN | |
| getProperty | `x.get(k)` | REVIEW | JS missing prop → `undefined`→ use `.get(k)` → `None` |
| hasOwnProperty | `k in x` | CLEAN | |
| keys | `list(x.keys())` | CLEAN | |
| setProperty | `x[k] = v` | REVIEW | mutates |
| optionalChaining | `x.get(k) if isinstance(x, dict) else None` | HELPER-ish | `?.` — guard None at each hop |
| deleteProperty | `x.pop(k, None)` | REVIEW | mutates |
| toString | `json.dumps(x)` | REVIEW | JS gives "[object Object]"; usually JSON is what's wanted — confirm intent |
| values | `list(x.values())` | CLEAN | |

---

## Json  (`library: "Json"`)

| method | Python | Flag | Note |
|---|---|---|---|
| parse | `json.loads(x)` | CLEAN | |
| stringify | `json.dumps(x)` | REVIEW | add `separators=(",",":")` to match JS compact output; `indent` if a space arg was given |
| typeof | `js_typeof(x)` | HELPER | null/array/object all → "object" |

---

## Equality  (`library: "Equality"`)

| method | Python | Flag | Note |
|---|---|---|---|
| equality (`==`) | `js_loose_eq(x, y)` | HELPER | JS loose equality with coercion |
| identity (`===`) | `js_strict_eq(x, y)` | HELPER | keeps bool distinct from number |
| inequality (`!=`) | `not js_loose_eq(x, y)` | HELPER | |
| nonidentity (`!==`) | `not js_strict_eq(x, y)` | HELPER | |
| deepEquals | `deep_equals(x, y)` | HELPER | structural |

> If both operands are plainly the same primitive type, `x == y` is fine (CLEAN) and you can
> skip the helper. Use the helper when types may differ or bool/number coercion matters.

## Relational  (`library: "Relational"`)

| method | Python | Flag |
|---|---|---|
| greaterThan `>` | `x > y` | CLEAN |
| greaterThanOrEqual `>=` | `x >= y` | CLEAN |
| lessThan `<` | `x < y` | CLEAN |
| lessThanOrEqual `<=` | `x <= y` | CLEAN |

## Logical  (`library: "Logical"`)

| method | Python | Flag | Note |
|---|---|---|---|
| and `&&` | `x if not js_truthy(x) else y` | HELPER | JS returns an OPERAND, not a bool; short-circuit on JS truthiness |
| or `\|\|` | `x if js_truthy(x) else y` | HELPER | returns an operand |
| not `!` | `not js_truthy(x)` | HELPER | returns a real bool |
| nullish `??` | `y if x is None else x` | CLEAN | only `null`/`undefined` trigger fallback (NOT 0/"") |

> When the result feeds straight into a boolean context (a filter predicate, an `if`),
> `not js_truthy(x)` for `not` is right. For `&&`/`||` that feed a value, preserve the
> operand-returning behavior above.

## Conditional  (`library: "Conditional"`)

| method | Python | Flag | Note |
|---|---|---|---|
| ternary | `a if js_truthy(cond) else b` | HELPER | |
| if/else | `if`/`else` statements | HELPER | guard with `js_truthy(cond)` |
| switch | `if/elif/else` chain or dict dispatch | REVIEW | JS switch matches with `===`; no fallthrough assumed |

---

## Math  (`library: "Math"`)

| method | Python | Flag | Note |
|---|---|---|---|
| abs | `abs(x)` | CLEAN | |
| add | `x + y` | CLEAN | |
| subtract | `x - y` | CLEAN | |
| multiply | `x * y` | CLEAN | |
| divide | `x / y` | REVIEW | FLOAT division — never `//` |
| remainder | `js_remainder(x, y)` | HELPER | JS `%` sign follows the dividend |
| exponentiation | `x ** y` | CLEAN | |
| ceil | `math.ceil(x)` | CLEAN | import `math` |
| floor | `math.floor(x)` | CLEAN | |
| round | `math.floor(x + 0.5)` | REVIEW | JS rounds half UP; Python `round` is banker's — use floor(x+0.5) |
| max | `max(x, y)` / `max(seq)` | CLEAN | |
| min | `min(x, y)` / `min(seq)` | CLEAN | |
| random | `random.random()` | REVIEW | import `random`; non-deterministic — flag in report |

## Number  (`library: "Number"`)

| method | Python | Flag | Note |
|---|---|---|---|
| new | `float(x)` | CLEAN | |
| isFinite | `math.isfinite(x)` | CLEAN | |
| isInteger | `isinstance(x,int) or (isinstance(x,float) and x.is_integer())` | REVIEW | |
| isNaN | `isinstance(x,float) and math.isnan(x)` | CLEAN | |
| isSafeInteger | `isinstance(x,int) and abs(x) <= 2**53-1` | REVIEW | |
| parseFloat | `float(x)` | REVIEW | JS parses leading numeric prefix, returns NaN on fail — guard |
| parseInt | `int(x, base)` | REVIEW | JS parses prefix & honors radix; strip non-digits if needed |
| toExponential | `to_exponential(x, d)` | HELPER | |
| toFixed | `to_fixed(x, d)` | HELPER | returns a STRING |
| toLocaleString | `f"{x:,}"` | REVIEW | locale-approximate |
| toPrecision | `to_precision(x, p)` | HELPER | |
| toString | `str(x)` | REVIEW | with radix arg → base conversion (e.g. hex) |

## Boolean  (`library: "Boolean"`)

| method | Python | Flag | Note |
|---|---|---|---|
| new | `js_truthy(x)` | HELPER | `Boolean(x)` uses JS truthiness |
| toString | `"true" if x else "false"` | REVIEW | JS lowercase, not Python `"True"` |

## Null  (`library: "Null"`)

| method | Python | Flag |
|---|---|---|
| new | `None` | CLEAN |

---

## Bitwise  (`library: "Bitwise"`)

> JS bitwise ops coerce operands to 32-bit signed integers first. For the small integer
> values transformations use, plain Python operators match; flag REVIEW if large/negative.

| method | Python | Flag |
|---|---|---|
| and `&` | `x & y` | REVIEW |
| or `\|` | `x \| y` | REVIEW |
| xor `^` | `x ^ y` | REVIEW |
| not `~` | `~x` | REVIEW |
| leftShift `<<` | `x << y` | REVIEW |
| rightShift `>>` | `x >> y` | REVIEW |

## Regex  (`library: "Regex"`)

> **Dialect gap — always REVIEW.** Translate the JS pattern to Python `re`: map flags
> (`g`→use `findall`/`finditer`, `i`→`re.I`, `m`→`re.M`, `s`→`re.S`), named groups
> `(?<name>)`→`(?P<name>)`, and be wary of `\d`/`\w` Unicode defaults differing. There is
> no sticky (`y`) flag in Python.

| method | Python | Flag |
|---|---|---|
| new | `re.compile(pattern, flags)` | REVIEW |
| exec | `re.search(p, s)` (loop for `g`) | REVIEW |
| test | `bool(re.search(p, s))` | REVIEW |
| toString | `f"/{pattern}/{flags}"` | REVIEW |

## Set  (`library: "Set"`)

> JS `Set` preserves insertion order and stores objects by reference. Python `set` is
> unordered and needs hashable members. For primitives a `set` is fine; if order matters
> use `dict.fromkeys(...)`; if members are dict/list, model it as a list with membership checks.

| method | Python | Flag | Note |
|---|---|---|---|
| new | `set(x)` | REVIEW | order lost — see above |
| add | `s.add(v)` | REVIEW | |
| clear | `s.clear()` | CLEAN | |
| delete | `s.discard(v)` | CLEAN | |
| has | `v in s` | CLEAN | |
| size | `len(s)` | CLEAN | |
| entries | `[(v, v) for v in s]` | REVIEW | JS Set entries are `[v, v]` |
| values | `list(s)` | REVIEW | order |

## Date  (`library: "Date"`)  — all REVIEW

> JS `Date` is millisecond-epoch, month is **0-indexed**, and the `toLocale*` family is
> locale/timezone dependent. Use `datetime`/`time`; convert ms↔s (`/1000`), add 1 to months
> on the way in and subtract 1 on the way out, and treat locale strings as approximate.
> Flag any date-heavy transformation for human review.

| method group | Python approach |
|---|---|
| now | `int(time.time()*1000)` |
| new Date(ms) | `datetime.datetime.fromtimestamp(ms/1000, tz=datetime.timezone.utc)` |
| parse | `datetime.datetime.fromisoformat(...)` → epoch ms |
| getFullYear / getMonth / getDate / getHours / … | `dt.year`, `dt.month-1`, `dt.day`, `dt.hour`, … (note month-1) |
| getUTC* | build `dt` in UTC, then read the same fields |
| getTime | `int(dt.timestamp()*1000)` |
| getTimezoneOffset | `-int(dt.utcoffset().total_seconds()/60)` |
| setFullYear / setMonth / … | `dt.replace(...)` (remember month+1) |
| toISOString | `dt.isoformat()` → normalise to `...Z` |
| toString / toDateString / toLocale* | `dt.strftime(...)` — approximate |

---

## WorkflowEngine custom  (`library: "WorkflowEngine"` / method `query`)

| method | Python | Flag | Note |
|---|---|---|---|
| query | `query(obj, path)` | HELPER | JSONPath subset; returns a LIST of matches. If the JST expected a single value, take `[0]`. Unsupported expressions (filters `[?()]`, slices, unions) must be hand-translated — do NOT guess. |

---

## General semantic reminders (apply everywhere)

- **JS truthiness ≠ Python truthiness.** `[]`, `{}`, `"0"` are truthy in JS, falsy-ish in
  Python. Any value used as a condition that came from JS logic should pass through `js_truthy`.
- **Missing / undefined → `None`.** Prefer `.get()` over `[]` for object access the JST
  tolerated as possibly-absent.
- **Mutating array methods** (`push`/`pop`/`shift`/`unshift`/`splice`/`sort`/`reverse`/
  `fill`/`setIndex`/`copyWithin`) mutate in place and return a JS-specific value — emit a
  statement, then use the correct return value (e.g. `push`→new length).
- **Default `Array.sort` is lexicographic**, not numeric. Don't emit a bare `sorted()` for a
  numeric sort unless the JST supplied a numeric comparator.
- **Division is float** (`/`), remainder sign follows the dividend (`js_remainder`).
- **When a method/behavior isn't covered here or is ambiguous, STOP and flag it** in the
  report rather than emitting a plausible-looking guess.
