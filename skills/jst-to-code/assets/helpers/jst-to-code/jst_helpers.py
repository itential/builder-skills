#!/usr/bin/env python3
"""Pure-Python stand-ins for JST/JS semantics that native Python does NOT match 1:1.

This is a SOURCE LIBRARY, not an import. The Run Code task runs a single file, so the
generator must COPY the few functions a given transformation actually uses into the top of
the generated `.py` (tree-shake -- never paste the whole module). Each function is written
to be self-contained (only stdlib `math`/`re`, imported where used) so it can be lifted
verbatim.

Only reach for a helper when the mapping reference (jst-method-map.md) flags a method as
HELPER. Methods flagged CLEAN map straight to a Python builtin/operator and need nothing
from here.
"""
import math
import re


# --------------------------------------------------------------------------- #
# Truthiness & equality (JS coercion differs from Python)                      #
# --------------------------------------------------------------------------- #
def js_truthy(v):
    """JS truthiness. Falsy: None (null/undefined), False, 0, 0.0, "", NaN.

    Everything else is truthy -- including [] and {} and "0" and "false", which
    are all FALSY in Python. Use this wherever a JST relied on JS truthiness
    (Logical and/or/not, Conditional if/ternary, Array.filter predicates that
    return a value rather than a bool).
    """
    if v is None or v is False:
        return False
    if isinstance(v, float) and math.isnan(v):
        return False
    if isinstance(v, (int, float)) and v == 0:
        return False
    if isinstance(v, str) and v == "":
        return False
    return True


def js_strict_eq(a, b):
    """JS `===` / identity. Type-aware: bool is NOT a number, 1 !== true.

    Python treats True == 1 and False == 0; this keeps them distinct like JS.
    """
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, bool) and isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def js_loose_eq(a, b):
    """JS `==` with the common coercions (null==undefined, number<->string, bool->number).

    Covers the cases that actually appear in transformations; it is NOT the full
    abstract-equality spec. If a comparison looks exotic, review it by hand.
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, bool):
        a = int(a)
    if isinstance(b, bool):
        b = int(b)
    if isinstance(a, (int, float)) and isinstance(b, str):
        try:
            return a == float(b)
        except ValueError:
            return False
    if isinstance(b, (int, float)) and isinstance(a, str):
        try:
            return float(a) == b
        except ValueError:
            return False
    return js_strict_eq(a, b)


def deep_equals(a, b):
    """Structural deep equality that keeps bool distinct from number (JS semantics)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(deep_equals(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(deep_equals(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def js_typeof(v):
    """The JS `typeof` string for a JSON value (Json.typeof).

    Note: typeof null === "object" and typeof [] === "object" in JS, so None,
    dict and list all return "object" here. There is no "undefined" in JSON.
    """
    if v is None:
        return "object"          # JS: typeof null === "object"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    return "object"              # dict, list


# --------------------------------------------------------------------------- #
# Number formatting (Number.toFixed / toPrecision / toExponential)            #
# --------------------------------------------------------------------------- #
def to_fixed(n, digits=0):
    """Number.prototype.toFixed -> string with fixed decimals.

    Python's round() is banker's rounding; JS rounds half away from zero, so for
    exact .5 ties the last digit can differ. Good enough for display formatting.
    """
    return f"{float(n):.{int(digits)}f}"


def to_precision(n, precision):
    """Number.prototype.toPrecision -> string with `precision` significant digits."""
    if precision is None:
        return str(n)
    return f"{float(n):.{int(precision)}g}"


def to_exponential(n, digits=None):
    """Number.prototype.toExponential -> exponential-notation string.

    JS uses a single-digit exponent minimum (e.g. "1e+1"); Python emits "1e+01".
    Normalise the exponent padding to match JS.
    """
    s = f"{float(n):.{int(digits)}e}" if digits is not None else f"{float(n):e}"
    return re.sub(r"e([+-])0*(\d)", r"e\1\2", s)


# --------------------------------------------------------------------------- #
# Math.remainder -> JS `%` (sign follows the dividend, unlike Python `%`)     #
# --------------------------------------------------------------------------- #
def js_remainder(a, b):
    """JS `%`: result takes the sign of the dividend. (-5 % 3 === -2 in JS.)"""
    return math.fmod(a, b)


# --------------------------------------------------------------------------- #
# WorkflowEngine custom `query` -- a small JSONPath subset                     #
# --------------------------------------------------------------------------- #
def query(obj, path):
    """Evaluate a JSONPath `path` against `obj`, returning a LIST of matches.

    Supported subset (covers what JST transformations use in practice):
        $                      the root
        $.a.b      / a.b       child by key (leading $ optional)
        $.a[0]                 array index
        $.a[*]     / $.a.*     wildcard over array items or object values
        $..b                   recursive descent to every key `b`

    NOT supported: filter expressions `[?(...)]`, slices `[1:3]`, unions `[0,1]`,
    functions. If a JST uses one of those, translate that query by hand instead of
    relying on this helper. Returns [] when nothing matches.
    """
    path = path.strip()
    if path in ("$", ""):
        return [obj]
    if path.startswith("$"):
        path = path[1:]

    # tokenize into steps: .key  ..key  [idx]  [*]  .*
    tokens = re.findall(r"\.\.(\w+)|\.(\w+)|\[(\d+)\]|\[\*\]|\.\*", path)
    results = [obj]
    for recurse, key, idx in tokens:
        nxt = []
        if recurse:                                   # ..key  recursive descent
            for node in results:
                nxt.extend(_descend(node, recurse))
        elif key:                                     # .key
            for node in results:
                if isinstance(node, dict) and key in node:
                    nxt.append(node[key])
        elif idx:                                     # [idx]
            i = int(idx)
            for node in results:
                if isinstance(node, list) and -len(node) <= i < len(node):
                    nxt.append(node[i])
        else:                                         # [*] or .*
            for node in results:
                if isinstance(node, list):
                    nxt.extend(node)
                elif isinstance(node, dict):
                    nxt.extend(node.values())
        results = nxt
    return results


def _descend(node, key):
    """Collect every value under `key` anywhere beneath `node` (for `..key`)."""
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                found.append(v)
            found.extend(_descend(v, key))
    elif isinstance(node, list):
        for item in node:
            found.extend(_descend(item, key))
    return found
