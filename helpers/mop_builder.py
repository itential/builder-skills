#!/usr/bin/env python3
"""
MopTemplateBuilder: a construction-time API for building MOP command
template documents (POST /mop/createTemplate body's "mop" object).

Same rationale as workflow_builder.py, applied to a different document
type: MOP command templates have their own confirmed-live footguns that
are cheap to make structurally impossible instead of documenting as prose
an agent has to recall correctly:

  - `eval` type strings are case-sensitive ("RegEx", not "regex" or
    "REGEX") and silently do nothing useful if wrong. Named methods here
    (regex(), not_regex(), contains(), ...) mean the raw string is never
    hand-typed, so it can't be misspelled or miscased.
  - `case: true` means case-INSENSITIVE -- the field name is backwards
    from what it reads as. The builder's own parameter is named
    `case_insensitive` so the caller's code says what it means.
  - A command with zero rules always passes -- silently, not an error.
    finish() refuses to complete if any command has no rules, since this
    is almost never what's actually intended.
  - Rules referencing a `<!var!>` placeholder that isn't supplied at
    RunCommandTemplate invocation time are silently SKIPPED and counted
    as passing, not failing -- this is a runtime fact this builder can't
    prevent (it doesn't know what variables will be passed), but
    find_referenced_variables() surfaces every placeholder used so it can
    be checked against the variables a caller intends to pass.

`validate_mop_template.py`-equivalent checks are folded into this module
as a `validate()` function usable against hand-authored MOP JSON too --
see the bottom of this file.
"""
import json
import re
import sys


class MopBuilderError(Exception):
    """Raised when an operation would construct a MOP template the real
    platform is known to silently mishandle (not error on, just do the
    wrong thing)."""


_COMPARISON_EVALUATORS = {'=', '!=', '<', '>', '<=', '>=', '%'}

VAR_PLACEHOLDER_RE = re.compile(r'<!([^!]+)!>')


class MopTemplateBuilder:
    def __init__(self, name, description='', os='', pass_rule=True, ignore_warnings=False):
        self.name = name
        self.description = description
        self.os = os
        self.pass_rule = pass_rule
        self.ignore_warnings = ignore_warnings
        self.commands = []

    def add_command(self, command, pass_rule=True):
        """Add a command to run. Returns a handle for add_rule()-family calls.
        `pass_rule=True` means ALL rules on this command must pass (AND);
        `False` means only one needs to (OR) -- same semantics as the
        template-level passRule, just scoped to this command."""
        self.commands.append({'command': command, 'passRule': pass_rule, 'rules': []})
        return len(self.commands) - 1

    def contains(self, cmd, text, severity='error'):
        self._add_rule(cmd, {'rule': text, 'eval': 'contains', 'severity': severity})

    def not_contains(self, cmd, text, severity='error'):
        self._add_rule(cmd, {'rule': text, 'eval': '!contains', 'severity': severity})

    def contains_once(self, cmd, text, severity='error'):
        """Real eval type "contains1" -- the string must appear exactly once."""
        self._add_rule(cmd, {'rule': text, 'eval': 'contains1', 'severity': severity})

    def regex(self, cmd, pattern, severity='error', case_insensitive=False, multiline=False, global_match=False):
        rule = {'rule': pattern, 'eval': 'RegEx', 'severity': severity}
        self._apply_flags(rule, case_insensitive, multiline, global_match)
        self._add_rule(cmd, rule)

    def not_regex(self, cmd, pattern, severity='error', case_insensitive=False, multiline=False, global_match=False):
        rule = {'rule': pattern, 'eval': '!RegEx', 'severity': severity}
        self._apply_flags(rule, case_insensitive, multiline, global_match)
        self._add_rule(cmd, rule)

    def comparison(self, cmd, rule, rule_b, evaluator, severity='error'):
        """Extract two values with regex (`rule`/`ruleB`, each should have a
        capture group) and compare them numerically. `evaluator` is one of
        =, !=, <, >, <=, >=, % (percentage)."""
        if evaluator not in _COMPARISON_EVALUATORS:
            raise MopBuilderError(
                f"comparison evaluator {evaluator!r} is not one of the real set "
                f"{sorted(_COMPARISON_EVALUATORS)}."
            )
        self._add_rule(cmd, {
            'rule': rule, 'ruleB': rule_b, 'eval': '#comparison',
            'evaluator': evaluator, 'severity': severity,
        })

    def _apply_flags(self, rule, case_insensitive, multiline, global_match):
        if case_insensitive:
            rule['case'] = True
        if multiline:
            rule['multiline'] = True
        if global_match:
            rule['global'] = True

    def _add_rule(self, cmd, rule):
        if not (0 <= cmd < len(self.commands)):
            raise MopBuilderError(f"{cmd!r} is not a command handle from add_command().")
        self.commands[cmd]['rules'].append(rule)

    def find_referenced_variables(self):
        """Every <!var!> placeholder used across all commands and rules --
        including the pre-built command/rule strings. Missing one of these
        at RunCommandTemplate invocation time doesn't fail the run: the
        rule referencing it is silently SKIPPED and counted as a pass. This
        builder can't prevent that (it doesn't control what's passed at
        invocation time) -- use this to check against the variables a
        caller actually intends to supply before running the template."""
        found = set()
        for cmd in self.commands:
            found.update(VAR_PLACEHOLDER_RE.findall(cmd['command']))
            for rule in cmd['rules']:
                found.update(VAR_PLACEHOLDER_RE.findall(str(rule.get('rule', ''))))
                found.update(VAR_PLACEHOLDER_RE.findall(str(rule.get('ruleB', ''))))
        return found

    def finish(self):
        """A command with zero rules always passes -- silently, not an
        error. This is the one MOP footgun structurally worth blocking
        rather than just warning about, since it's almost never what's
        actually intended (an unvalidated check that always reports
        success)."""
        for i, cmd in enumerate(self.commands):
            if not cmd['rules']:
                raise MopBuilderError(
                    f"Command {i} ({cmd['command']!r}) has zero rules -- on the real "
                    f"platform this makes the command silently always pass, which is "
                    f"almost never intended. Add at least one rule."
                )
        return self

    def to_document(self):
        return {
            'name': self.name,
            'description': self.description,
            'os': self.os,
            'passRule': self.pass_rule,
            'ignoreWarnings': self.ignore_warnings,
            'commands': self.commands,
        }


_VALID_EVAL_TYPES = {'contains', '!contains', 'contains1', 'RegEx', '!RegEx', '#comparison'}


def validate(mop):
    """Backstop for hand-authored MOP template JSON (the {"name": ..., "commands": [...]}
    body, not wrapped in {"mop": ...}). Returns a list of violation strings."""
    violations = []
    for i, cmd in enumerate(mop.get('commands', [])):
        rules = cmd.get('rules', [])
        if not rules:
            violations.append(
                f"[command {i}] {cmd.get('command')!r} has zero rules -- this makes the "
                f"command silently always pass, not an error."
            )
        for j, rule in enumerate(rules):
            eval_type = rule.get('eval')
            if eval_type not in _VALID_EVAL_TYPES:
                violations.append(
                    f"[command {i}, rule {j}] eval {eval_type!r} is not a real eval type "
                    f"{sorted(_VALID_EVAL_TYPES)} -- these are case-sensitive (\"RegEx\", "
                    f"not \"regex\"/\"REGEX\")."
                )
            if eval_type == '#comparison' and rule.get('evaluator') not in _COMPARISON_EVALUATORS:
                violations.append(
                    f"[command {i}, rule {j}] #comparison evaluator {rule.get('evaluator')!r} "
                    f"is not one of the real set {sorted(_COMPARISON_EVALUATORS)}."
                )
    return violations


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    src = sys.stdin if sys.argv[1] == '-' else open(sys.argv[1])
    with src:
        doc = json.load(src)
    mop = doc.get('mop', doc)
    violations = validate(mop)
    if violations:
        print(f"{len(violations)} violation(s) found:\n")
        for v in violations:
            print(f"  - {v}\n")
        sys.exit(1)
    print("No violations found.")
    sys.exit(0)


if __name__ == '__main__':
    main()
