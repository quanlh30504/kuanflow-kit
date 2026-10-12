#!/usr/bin/env bash
# stale-wiki-check.sh <repo-path>
#
# Reports generated wiki pages of a service repo whose sources changed since they were written.
# For each <repo>/kuan-workbench/wiki/*.md whose frontmatter has `generated: true`:
#   - no `source_commit`, no `source_paths`, or a commit unknown to the repo
#       -> stdout: UNKNOWN <relpath>: <reason>
#   - any change in `source_paths` between `source_commit` and HEAD
#       -> stdout: STALE <relpath>
# Pages without `generated: true` are ignored. Uncommitted changes are not compared.
# Read-only: never modifies files, the index or refs. No network.
#
# Exit: 0 nothing stale or unknown (also when there is no wiki directory),
#       1 any STALE or UNKNOWN line, 2 usage or environment error.
# Needs: bash, git, python3 with PyYAML.
set -euo pipefail

prog="stale-wiki-check.sh"

die() {
  printf '%s: %s\n' "$prog" "$1" >&2
  exit 2
}

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  printf 'usage: %s <repo-path>\n' "$prog" >&2
  exit 2
fi
repo="$1"

[ -d "$repo" ] || die "not a directory: $repo"
inside="$(git -C "$repo" rev-parse --is-inside-work-tree 2>/dev/null)" || inside=""
[ "$inside" = "true" ] || die "not a git work tree: $repo"
top="$(git -C "$repo" rev-parse --show-toplevel)" || die "cannot find the work tree root of $repo"
command -v python3 >/dev/null 2>&1 || die "python3 not found"

wiki="$repo/kuan-workbench/wiki"
[ -d "$wiki" ] || exit 0

# Parses the frontmatter of every wiki page. For each page with `generated: true` it prints
# NUL-terminated fields: either
#   <relpath> "ok" <commit> <n> <path 1> ... <path n>
# or
#   <relpath> "unknown" <reason>
# and finally the single field "end", so the caller can tell a complete run from a crash.
# All scalars are read as strings (BaseLoader), so a commit such as 0123456 keeps its digits.
parser="$(
  cat <<'PY'
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required (pip install pyyaml)")

TRUE = {"true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"}
HEX = re.compile(r"[0-9a-fA-F]{4,64}")
wiki = Path(sys.argv[1])
out = sys.stdout.buffer


def emit(*fields):
    for field in fields:
        out.write(str(field).encode("utf-8", "surrogateescape") + b"\0")


def frontmatter(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].rstrip() != "---":
        return {}
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            data = yaml.load("\n".join(lines[1:i]), Loader=yaml.BaseLoader)
            return data if isinstance(data, dict) else {}
    return {}


for page in sorted(p for p in wiki.glob("*.md") if p.is_file()):
    rel = "kuan-workbench/wiki/" + page.name
    try:
        fm = frontmatter(page)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        reason = " ".join(str(exc).split())
        print(f"warning: {rel}: cannot read frontmatter, page ignored: {reason}", file=sys.stderr)
        continue
    generated = fm.get("generated")
    if not isinstance(generated, str) or generated not in TRUE:
        continue
    commit = fm.get("source_commit")
    paths = fm.get("source_paths")
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(commit, str) or not commit.strip():
        emit(rel, "unknown", "no source_commit")
    elif not HEX.fullmatch(commit.strip()):
        emit(rel, "unknown", f"source_commit {commit.strip()!r} is not a commit id")
    elif (
        not isinstance(paths, list)
        or not paths
        or not all(isinstance(p, str) and p.strip() for p in paths)
    ):
        emit(rel, "unknown", "no source_paths")
    else:
        emit(rel, "ok", commit.strip(), len(paths), *(p.strip() for p in paths))
emit("end")
PY
)"

fields=()
while IFS= read -r -d '' field; do
  fields+=("$field")
done < <(python3 -I -c "$parser" "$wiki")

n="${#fields[@]}"
if [ "$n" -eq 0 ] || [ "${fields[n - 1]}" != "end" ]; then
  die "failed to parse wiki frontmatter in $wiki"
fi

found=0
i=0
while [ "$i" -lt $((n - 1)) ]; do
  rel="${fields[i]}"
  kind="${fields[i + 1]}"
  if [ "$kind" = "unknown" ]; then
    printf 'UNKNOWN %s: %s\n' "$rel" "${fields[i + 2]}"
    found=1
    i=$((i + 3))
    continue
  fi
  commit="${fields[i + 2]}"
  count="${fields[i + 3]}"
  paths=("${fields[@]:i+4:count}")
  i=$((i + 4 + count))

  if ! git -C "$top" rev-parse --verify --quiet "${commit}^{commit}" >/dev/null 2>&1; then
    printf 'UNKNOWN %s: source_commit %s is not a commit in this repo\n' "$rel" "$commit"
    found=1
    continue
  fi
  rc=0
  git -C "$top" diff --quiet --no-ext-diff --no-textconv "$commit" HEAD -- "${paths[@]}" \
    >/dev/null 2>&1 || rc=$?
  case "$rc" in
    0) ;;
    1)
      printf 'STALE %s\n' "$rel"
      found=1
      ;;
    *)
      printf 'UNKNOWN %s: git diff failed for source_commit %s\n' "$rel" "$commit"
      found=1
      ;;
  esac
done

exit "$found"
