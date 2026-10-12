#!/usr/bin/env bash
# Kuanflow guard for file edits (PreToolUse Edit|Write|MultiEdit hook; also used by git hooks).
# Reads hook JSON on stdin ({"tool_input": {"file_path": "..."}}) and blocks edits of EXISTING
# files that match `protected_paths` in .kuanflow/config.yaml or config.local.yaml.
# New files are allowed. Exit 2 = block (reason on stderr), exit 0 = allow.
# Fails open without python3 or PyYAML (kuanflow doctor reports that).
set -uo pipefail

command -v python3 >/dev/null 2>&1 || exit 0

read -r -d '' PROG <<'PY'
import sys

# Never import modules from the project directory (a repo could ship its own json.py/yaml.py).
sys.path[:] = [p for p in sys.path if p not in ("", ".")]

import fnmatch
import json
import os
import subprocess


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


def protected_globs(root):
    try:
        import yaml
    except Exception:
        return []
    globs = []
    for name in ("config.yaml", "config.local.yaml"):
        f = os.path.join(root, ".kuanflow", name)
        if not os.path.isfile(f):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                items = (yaml.safe_load(fh) or {}).get("protected_paths") or []
        except Exception:
            continue
        if isinstance(items, list):
            globs += [g for g in items if isinstance(g, str) and g]
    return globs


def matches(rel, glob):
    # fnmatch: '*' also matches '/'. A leading '**/' also matches zero directories.
    if fnmatch.fnmatchcase(rel, glob):
        return True
    return glob.startswith("**/") and fnmatch.fnmatchcase(rel, glob[3:])


def main():
    try:
        data = json.load(sys.stdin)
        path = (data.get("tool_input") or {}).get("file_path") or ""
    except Exception:
        return
    if not isinstance(path, str) or not path:
        return
    root = os.path.realpath(find_root())
    target = os.path.realpath(os.path.abspath(path))
    if not os.path.exists(target):
        return  # creating a new file is always allowed
    rel = os.path.relpath(target, root).replace(os.sep, "/")
    if rel == ".." or rel.startswith("../") or os.path.isabs(rel):
        return  # outside the project
    for glob in protected_globs(root):
        if matches(rel, glob):
            sys.stderr.write(
                f"Blocked by kuanflow guard: '{rel}' matches protected path '{glob}'. "
                "Create a new file instead, or ask the human.\n"
            )
            sys.exit(2)


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
