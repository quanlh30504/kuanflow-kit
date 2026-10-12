#!/usr/bin/env bash
# Builds context.json for the debug-incident skill from LOCAL inputs only (no network).
# Masks personal data, keeps the output under 50 KB, and writes only to
# <root>/<paths.scratch>/<ID>/context.json (paths.scratch must stay inside .kuanflow/).
#
# Usage: collect_context.sh --id <ID> [--service S]... [--log FILE]... [--trace FILE]...
#          [--changes FILE] [--metrics FILE] [--symptom TEXT] [--severity SEVn]
#          [--source alert|ticket|report|manual] [--similar INC]... [--root DIR]
# Exit: 0 ok (prints the output path) · 1 error · 2 usage error.
#
# Org-specific sources (log platform, tracing, deploy history) are added by exporting them to
# files first and passing them in, or by extending this script — never by network calls here.
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "collect_context: python3 is required" >&2
  exit 1
fi

SCHEMA="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/schemas/context.schema.json"

read -r -d '' PROG <<'PY'
import sys

# Never import modules from the project directory.
sys.path[:] = [p for p in sys.path if p not in ("", ".")]

import argparse
import datetime
import json
import os
import re
import subprocess

MAX_BYTES = 51200
MAX_SIGNATURES = 20
MAX_LINE = 500
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MASKS = (
    ("account_no", re.compile(
        r"(?i)\b(account_no|account_number|accountNo|acct)(\s*[:=]\s*)(\"?)([^\s\",;&]+)"), r"\1\2\3<account_no>"),
    ("id_number", re.compile(
        r"(?i)\b(id_number|idNumber|national_id|cccd|cmnd|passport)(\s*[:=]\s*)(\"?)([^\s\",;&]+)"),
     r"\1\2\3<id_number>"),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<email>"),
    ("phone", re.compile(r"(?<![\w+])(?:\+84|0)\d{9,10}(?!\d)"), "<phone>"),
    ("number", re.compile(r"(?<![\w.:/-])\d{9,19}(?![\w.:/-])"), "<number>"),
)
COUNTS = {name: 0 for name, _, _ in MASKS}
ERROR_LINE = re.compile(r"\b(ERROR|FATAL)\b|Exception")
EXCEPTION = re.compile(r"[\w.$]*(Exception|Error)\b.*")
LEVEL = re.compile(r"\b(ERROR|FATAL|WARN|INFO|DEBUG)\b\s*(.*)")


class Fail(Exception):
    pass


def mask(value):
    if isinstance(value, str):
        for name, pattern, repl in MASKS:
            value, n = pattern.subn(repl, value)
            COUNTS[name] += n
        return value
    if isinstance(value, list):
        return [mask(v) for v in value]
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    return value


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


def load_config(root):
    try:
        import yaml
    except Exception:
        return {}
    merged = {}
    for name in ("config.yaml", "config.local.yaml"):
        f = os.path.join(root, ".kuanflow", name)
        if not os.path.isfile(f):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except Exception:
            continue
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key] = {**merged[key], **value}
                else:
                    merged[key] = value
    return merged


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        raise Fail(f"cannot read {path}: {exc.strerror}")


def read_json(path):
    try:
        return json.loads(read_text(path))
    except ValueError as exc:
        raise Fail(f"{path} is not valid JSON: {exc}")


def signature(line):
    m = EXCEPTION.search(line)
    if m:
        return m.group(0).strip()[:200]
    m = LEVEL.search(line)
    return (m.group(2) if m else line).strip()[:200]


def serialize(ctx):
    return json.dumps(ctx, indent=2, ensure_ascii=False) + "\n"


def fit(ctx, key):
    """Keep the longest prefix of ctx[key] that fits MAX_BYTES (binary search)."""
    items = ctx.get(key) or []
    lo, hi = 0, len(items)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        ctx[key] = items[:mid]
        if len(serialize(ctx).encode("utf-8")) <= MAX_BYTES:
            lo = mid
        else:
            hi = mid - 1
    ctx[key] = items[:lo]
    return lo < len(items)


def validate(ctx, schema_path):
    try:
        import jsonschema
    except Exception:
        jsonschema = None
    if jsonschema is not None:
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        try:
            jsonschema.validate(ctx, schema)
        except jsonschema.ValidationError as exc:
            raise Fail(f"output does not match the schema: {exc.message}")
        return
    # Minimal structural check when jsonschema is not installed.
    for key in ("incident_id", "services", "symptom", "redaction"):
        if key not in ctx:
            raise Fail(f"output is missing {key!r}")
    if not isinstance(ctx["symptom"].get("error_signatures"), list):
        raise Fail("output symptom.error_signatures is not a list")


def main(argv, schema_path):
    parser = argparse.ArgumentParser(prog="collect_context.sh")
    parser.add_argument("--id", required=True)
    parser.add_argument("--service", action="append", default=[])
    parser.add_argument("--log", action="append", default=[])
    parser.add_argument("--trace", action="append", default=[])
    parser.add_argument("--changes")
    parser.add_argument("--metrics")
    parser.add_argument("--symptom", default="")
    parser.add_argument("--severity", default="")
    parser.add_argument("--source", default="manual", choices=["alert", "ticket", "report", "manual"])
    parser.add_argument("--similar", action="append", default=[])
    parser.add_argument("--root")
    args = parser.parse_args(argv)
    if not ID_RE.match(args.id):
        parser.error(f"invalid --id {args.id!r} (allowed: letters, digits, '.', '_', '-')")

    root = os.path.realpath(args.root or find_root())
    cfg = load_config(root)
    scratch_rel = ((cfg.get("paths") or {}).get("scratch")) or ".kuanflow/scratch"
    engine = os.path.realpath(os.path.join(root, ".kuanflow"))
    scratch = os.path.realpath(os.path.join(root, str(scratch_rel)))
    if scratch != engine and not scratch.startswith(engine + os.sep):
        raise Fail(f"paths.scratch {scratch_rel!r} must stay inside .kuanflow/")
    out_dir = os.path.join(scratch, args.id)

    services = args.service or [s for s in ((cfg.get("debug") or {}).get("services") or []) if isinstance(s, str)]

    lines = []
    for path in args.log:
        lines += [ln for ln in read_text(path).splitlines() if ln.strip()]
    samples = []
    for path in args.trace:
        data = read_json(path)
        items = data if isinstance(data, list) else [data]
        if not all(isinstance(i, dict) for i in items):
            raise Fail(f"{path}: expected a JSON object or a list of objects")
        samples += items
    changes = read_json(args.changes) if args.changes else None
    metrics = read_json(args.metrics) if args.metrics else None
    for name, value in (("--changes", changes), ("--metrics", metrics)):
        if value is not None and not isinstance(value, dict):
            raise Fail(f"{name}: expected a JSON object")

    lines = [mask(ln)[:MAX_LINE] for ln in lines]
    signatures = []
    for ln in lines:
        if ERROR_LINE.search(ln):
            sig = signature(ln)
            if sig and sig not in signatures:
                signatures.append(sig)
        if len(signatures) >= MAX_SIGNATURES:
            break

    budget = {"max_bytes": MAX_BYTES, "truncated": False}
    max_turns = ((cfg.get("debug") or {}).get("budget") or {}).get("max_turns_total")
    if isinstance(max_turns, int):
        budget["max_turns_total"] = max_turns

    ctx = {
        "incident_id": args.id,
        "detected_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": args.source,
        "severity": mask(args.severity),
        "services": mask(services),
        "symptom": {"summary": mask(args.symptom), "error_signatures": signatures},
        "samples": mask(samples),
        "log_excerpts": lines,
        "metrics": mask(metrics) if metrics is not None else {},
        "changes_in_window": mask(changes) if changes is not None else {},
        "similar_incidents": mask(args.similar),
        "redaction": {
            "applied": True,
            "fields": ["account_no", "id_number", "phone", "email"],
            "counts": dict(COUNTS),
        },
        "budget": budget,
    }

    if len(serialize(ctx).encode("utf-8")) > MAX_BYTES:
        budget["truncated"] = True
        fit(ctx, "log_excerpts")
        if len(serialize(ctx).encode("utf-8")) > MAX_BYTES:
            fit(ctx, "samples")
    if len(serialize(ctx).encode("utf-8")) > MAX_BYTES:
        raise Fail(f"context exceeds {MAX_BYTES} bytes even without log excerpts and samples")

    validate(ctx, schema_path)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "context.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(serialize(ctx))
    print(out)


try:
    main(sys.argv[2:], sys.argv[1])
except Fail as exc:
    sys.stderr.write(f"collect_context: {exc}\n")
    sys.exit(1)
PY

python3 -c "$PROG" "$SCHEMA" "$@"
