#!/usr/bin/env python3
"""Fail if a tracked file breaks one of the repo's security rules.

The skills are instructions an AI follows with customer credentials and customer platforms,
so most of what matters lives in Markdown, not code. Each rule below came from a real
finding; when a new one turns up, add a rule here so it can't come back.

A line that explains a rule ("never use ?token=") is allowed: it has to contain one of the
words in EXPLAINS. To allow a specific line anyway, put `security-rules: allow <rule-id>`
on it (in a Markdown comment if needed) and say why in the PR.

Scans tracked files only. Skips skills/*/assets/ (generated copies of the library, which is
scanned itself) and CHANGELOG.md (history describes old behavior on purpose).

Usage: check-security-rules.py [--list]      exit 1 when anything is found
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = (".md", ".py", ".sh", ".json", ".yml", ".yaml", ".txt", ".env", ".j2", ".html")
SKIP = re.compile(r"^(skills/[^/]+/assets/|CHANGELOG\.md$)")
EXPLAINS = re.compile(r"(?i)\bnever\b|\bdon'?t\b|\bnot\b|\binstead\b|\bavoid\b")

REMEDIATION = ("runAutoRemediation|advancedAutoRemediation|convertChangesToConfig|patchDeviceConfiguration|"
               "advancedPatchDeviceConfiguration|patchCMDeviceConfiguration|ManualRemediation|ManualRemediationResults")

# (id, files it applies to, pattern, explaining lines allowed?, message)
RULES = [
    ("token-in-url", (".md", ".py", ".sh", ".j2", ".html"), re.compile(r"[?&]token="), True,
     "token in a URL query parameter: it ends up in server logs, shell history and proxies. "
     "Send it in a header (Authorization: Bearer, or the token cookie for local /login)."),
    ("agent-reads-env", (".md",), re.compile(
        r"\b(cat|source|less|more|head|tail)\s+[^\s|;&`]*\.env\b"
        r"|(?i:\bread\s+(credentials|[`'\"]?[\w{}./<>-]*\.env\b))"
        r"|\bset -a\b[^\n]*\.env\b"), True,
     "instructions that have the agent read .env put the secret in the model's context. "
     "Run helpers/auth.py instead (AGENTS.md -> Auth Reuse)."),
    ("secret-cli-arg", (".py",), re.compile(
        r"add_argument\(\s*[\"']-{0,2}[\w-]*(secret|password|passwd|token)(?![\w-]*(file|path|env|var|prefix|name))[\w-]*[\"']"
        r"(?![^\n]*SUPPRESS)", re.I), False,
     "a secret taken as a command-line argument shows up in shell history and the process list. "
     "Read it from an environment variable, an --env-file, or a hidden prompt (getpass)."),
    ("secret-inline-command", (".md", ".sh"), re.compile(
        r"\b\w*(PASSWORD|SECRET)=\S+\s+(\w+=\S+\s+)*(python3?|bash|sh|node|\./)\b"), True,
     "a secret typed in front of a command lands in shell history. Use an --env-file or a prompt."),
    ("remote-shell-exec", (".md", ".sh", ".py"), re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b"), True,
     "piping a download straight into a shell runs unreviewed code."),
    ("autoyes-package-exec", (".md", ".sh"), re.compile(r"\bnpx\s+(-y|--yes)\b"), True,
     "npx -y installs and runs a package without asking."),
    ("remediation-task", (".json",), re.compile(r"\"name\"\s*:\s*\"(" + REMEDIATION + r")\""), False,
     "Configuration Manager remediation tasks are banned in workflows (AGENTS.md rule 25)."),
]


def tracked_files():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f.endswith(TEXT) and not SKIP.search(f)]


def main():
    if "--list" in sys.argv:
        for rule_id, exts, _, _, message in RULES:
            print(f"{rule_id:24} {' '.join(exts):28} {message}")
        return
    findings = []
    for rel in tracked_files():
        try:
            lines = (ROOT / rel).read_text(errors="replace").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for rule_id, exts, pattern, explained_ok, message in RULES:
                if not rel.endswith(exts) or not pattern.search(line):
                    continue
                if f"security-rules: allow {rule_id}" in line or (explained_ok and EXPLAINS.search(line)):
                    continue
                findings.append((rel, n, rule_id, message, line.strip()))
    in_actions = bool(__import__("os").environ.get("GITHUB_ACTIONS"))
    for rel, n, rule_id, message, text in findings:
        if in_actions:
            print(f"::error file={rel},line={n},title={rule_id}::{message}")
        print(f"{rel}:{n}: [{rule_id}] {text[:160]}")
    if findings:
        print(f"\n{len(findings)} security rule finding(s). See scripts/check-security-rules.py for each rule.", file=sys.stderr)
        sys.exit(1)
    print(f"Security rules: {len(tracked_files())} files checked, no findings.")


if __name__ == "__main__":
    main()
