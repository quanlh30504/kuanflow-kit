#!/usr/bin/env bash
# Kuanflow SessionStart hook: prints the effective project config into the agent context.
# Silent when the repo does not use Kuanflow. Never fails the session (always exits 0).
set -uo pipefail

d="$PWD"
while [ "$d" != / ] && [ ! -d "$d/.kuanflow" ]; do d="$(dirname "$d")"; done
if [ -d "$d/.kuanflow" ]; then
  ROOT="$d"
else
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
CFG="$ROOT/.kuanflow/config.yaml"
LOCAL="$ROOT/.kuanflow/config.local.yaml"

[ -f "$CFG" ] || [ -f "$LOCAL" ] || exit 0

HAVE_PY=0
command -v python3 >/dev/null 2>&1 && HAVE_PY=1

# Installed version: manifest (CLI install) -> plugin.json (plugin channel) -> unknown.
read -r -d '' VERSION_PY <<'PY'
import sys
sys.path[:] = [p for p in sys.path if p not in ("", ".")]
import json, os
root = sys.argv[1]
candidates = [(os.path.join(root, ".kuanflow", "manifest.json"), "kuanflow_version")]
plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
if plugin_root:
    candidates.append((os.path.join(plugin_root, ".claude-plugin", "plugin.json"), "version"))
for path, key in candidates:
    try:
        with open(path, encoding="utf-8") as fh:
            value = json.load(fh).get(key)
    except Exception:
        continue
    if isinstance(value, str) and value.strip():
        print(value.strip())
        break
PY

# Prints a WARNING line when kuanflow.min_version (local overrides project) is newer than argv[2].
read -r -d '' MIN_PY <<'PY'
import sys
sys.path[:] = [p for p in sys.path if p not in ("", ".")]
import os, re

SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+\S*)?$")


def key(v):
    m = SEMVER.match(str(v).strip())
    if not m:
        return None
    return (int(m[1]), int(m[2]), int(m[3]), 0 if m[4] else 1)


def min_version(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    try:
        import yaml
        cfg = yaml.safe_load(text) or {}
        value = (cfg.get("kuanflow") or {}).get("min_version")
        return None if value is None else str(value)
    except ImportError:
        pass
    except Exception:
        return None
    # Fallback without PyYAML: an indented `min_version:` inside the top-level `kuanflow:` block.
    inside = False
    for line in text.splitlines():
        if re.match(r"^kuanflow:\s*(#.*)?$", line):
            inside = True
            continue
        if inside and line and not line[0].isspace() and not line.lstrip().startswith("#"):
            inside = False
        if inside:
            m = re.match(r"^\s+min_version:\s*['\"]?([^'\"#\s]+)", line)
            if m:
                return m[1]
    return None


root, installed = sys.argv[1], sys.argv[2]
required = None
for name in ("config.local.yaml", "config.yaml"):
    required = min_version(os.path.join(root, ".kuanflow", name))
    if required is not None:
        break
have, need = key(installed), key(required) if required else None
if have and need and have < need:
    print(f"WARNING: Kuanflow v{installed} is older than v{required} required by this project. "
          "Run: kuanflow upgrade")
PY

VER=""
[ "$HAVE_PY" -eq 1 ] && VER="$(python3 -c "$VERSION_PY" "$ROOT" 2>/dev/null)"
[ -n "$VER" ] || VER="unknown"

echo "## kuanflow v${VER}"
echo "Effective config (later file overrides earlier):"
for f in "$CFG" "$LOCAL"; do
  if [ -f "$f" ]; then
    echo "### ${f#"$ROOT"/}"
    echo '```yaml'
    cat "$f" 2>/dev/null
    echo '```'
  fi
done

if [ "$HAVE_PY" -eq 1 ] && [ "$VER" != "unknown" ]; then
  python3 -c "$MIN_PY" "$ROOT" "$VER" 2>/dev/null
fi

echo "Rules: use commands.* from config; never edit protected_paths; never claim done without running commands.verify."
exit 0
