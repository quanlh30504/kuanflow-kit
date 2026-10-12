#!/usr/bin/env bash
# Kuanflow guard for shell commands (PreToolUse Bash hook; also used by git hooks).
# Reads hook JSON on stdin ({"tool_input": {"command": "..."}}).
# Exit 2 = block (reason on stderr), exit 0 = allow. Fails open when python3 is missing
# or the input cannot be parsed. A regex guard is a safety net, not a security boundary.
set -uo pipefail

command -v python3 >/dev/null 2>&1 || exit 0

read -r -d '' PROG <<'PY'
import sys

# Never import modules from the project directory (a repo could ship its own json.py/yaml.py).
sys.path[:] = [p for p in sys.path if p not in ("", ".")]

import json
import os
import re
import shlex
import subprocess

PROTECTED = re.compile(r"^(main|master)$")
RELEASE = re.compile(r"^release([/._-].*)?$")
SEPARATORS = {";", "&", "&&", "|", "||", "(", ")", ";;", "|&"}
RM_TARGETS = {
    "/", "/*", "~", "~/", "~/*", "$HOME", "$HOME/", "$HOME/*", "${HOME}", "${HOME}/",
    "${HOME}/*", ".", "./", "./*", "..", "../", "../*",
}
ENV_READERS = {"cat", "less", "more", "head", "tail", "cp", "scp"}
MAX_DEPTH = 3


def block(reason):
    sys.stderr.write(
        f"Blocked by kuanflow guard: {reason}. Ask the human to run this manually if truly needed.\n"
    )
    sys.exit(2)


def find_root():
    d = os.getcwd()
    while True:
        if os.path.isdir(os.path.join(d, ".kuanflow")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return os.getcwd()


def segments(cmd, depth=0):
    """Split a command line into simple commands (lists of words), respecting quotes.

    A word containing whitespace (the argument of `bash -c`, `eval`, `ssh host "..."`) is
    also split as a command line of its own, up to MAX_DEPTH levels.
    """
    result = []
    for line in cmd.splitlines():
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            words = list(lex)
        except ValueError:
            words = line.split()
        current = []
        for w in words:
            if w in SEPARATORS:
                if current:
                    result.append(current)
                current = []
            else:
                current.append(w)
        if current:
            result.append(current)
    if depth < MAX_DEPTH:
        for words in list(result):
            for w in words:
                if any(c.isspace() for c in w):
                    result += segments(w, depth + 1)
    return result


def base(word):
    return word.rsplit("/", 1)[-1]


def check_git_push(words):
    try:
        i = next(k for k, w in enumerate(words) if base(w) == "git")
    except StopIteration:
        return
    rest = words[i + 1 :]
    # skip git global options (-C <dir>, -c <k=v>, --git-dir=...)
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
    if not rest or rest[0] != "push":
        return
    force = False
    positional = []
    args = rest[1:]
    k = 0
    while k < len(args):
        a = args[k]
        if a in ("-o", "--push-option", "--repo", "--receive-pack", "--exec"):
            k += 2
            continue
        if a.startswith("--force") or a == "--mirror":
            force = True
        elif re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", a):
            force = True
        elif not a.startswith("-"):
            positional.append(a)
        k += 1
    for spec in positional[1:]:  # positional[0] is the remote
        if spec.startswith("+"):
            force = True
            spec = spec[1:]
        dst = spec.split(":", 1)[1] if ":" in spec else spec
        if dst.startswith("refs/heads/"):
            dst = dst[len("refs/heads/") :]
        if force and (PROTECTED.match(dst) or RELEASE.match(dst)):
            block("force push to protected branch")
        if PROTECTED.match(dst):
            block("direct push to main")


def check_rm(words):
    for i, w in enumerate(words):
        if base(w) != "rm":
            continue
        flags, targets = set(), []
        for a in words[i + 1 :]:
            if a == "--recursive":
                flags.add("r")
            elif a == "--force":
                flags.add("f")
            elif a.startswith("-") and not a.startswith("--"):
                flags.update(a[1:].lower())
            else:
                targets.append(a)
        # Recursive is enough: -f only skips prompts on write-protected files (C13b).
        if "r" in flags and any(t in RM_TARGETS for t in targets):
            block("destructive rm")


def check_env_read(words):
    for i, w in enumerate(words):
        if base(w) not in ENV_READERS:
            continue
        for a in words[i + 1 :]:
            name = base(a.split(":", 1)[-1])
            if name == ".env" or name.startswith(".env."):
                block("reading .env secrets")


def project_patterns(root):
    try:
        import yaml
    except Exception:
        return []
    patterns = []
    for name in ("config.yaml", "config.local.yaml"):
        f = os.path.join(root, ".kuanflow", name)
        if not os.path.isfile(f):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            items = (cfg.get("guard") or {}).get("extra_block_patterns") or []
        except Exception:
            continue
        if isinstance(items, list):
            patterns += [p for p in items if isinstance(p, str)]
    return patterns


def main():
    try:
        data = json.load(sys.stdin)
        cmd = (data.get("tool_input") or {}).get("command") or ""
    except Exception:
        return
    if not isinstance(cmd, str) or not cmd.strip():
        return

    for words in segments(cmd):
        check_git_push(words)
        check_rm(words)
        check_env_read(words)

    if re.search(
        r"\b(kubectl|helm)\b.*(--context|--kube-context|--namespace|-n)(\s+|=)[\w.-]*prod", cmd, re.I
    ):
        block("command targeting production cluster")
    if re.search(
        r"\b(psql|mysql|mongosh|mongo|redis-cli)\b.*(?<![a-z])prod(uction)?(?![a-z])", cmd, re.I
    ):
        block("direct connection to production datastore")
    if re.search(r"\bdrop\s+(database|schema|table)\b", cmd, re.I):
        block("destructive SQL")

    for p in project_patterns(find_root()):
        try:
            if re.search(p, cmd):
                block("matches project guard pattern")
        except re.error:
            continue


try:
    main()
except SystemExit:
    raise
except Exception:
    pass
sys.exit(0)
PY

python3 -c "$PROG"
code=$?
[ "$code" -eq 2 ] && exit 2
exit 0
