# Shared helpers for the guard-script bats suites (contracts C12–C15, C21).

bats_require_minimum_version 1.5.0

common_setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPTS="$REPO_ROOT/plugins/kuanflow/scripts"
  PROJECT="$BATS_TEST_TMPDIR/project"
  mkdir -p "$PROJECT/.kuanflow"
  cd "$PROJECT" || return 1
}

# write_config <yaml text> — writes .kuanflow/config.yaml
write_config() {
  printf '%s\n' "$1" > "$PROJECT/.kuanflow/config.yaml"
}

# write_local <yaml text> — writes .kuanflow/config.local.yaml
write_local() {
  printf '%s\n' "$1" > "$PROJECT/.kuanflow/config.local.yaml"
}

# json_field <key> <value> — prints {"tool_input":{"<key>":"<value>"}} with proper escaping
json_field() {
  python3 -I -c 'import json,sys; print(json.dumps({"tool_input": {sys.argv[1]: sys.argv[2]}}))' "$1" "$2"
}

# run_bash_guard <command string> — runs guard-bash.sh with that command as tool input
run_bash_guard() {
  local payload
  payload="$(json_field command "$1")"
  run --separate-stderr bash -c 'printf "%s" "$1" | "$2"' _ "$payload" "$SCRIPTS/guard-bash.sh"
}

# run_path_guard <file_path> — runs guard-protected-paths.sh with that path as tool input
run_path_guard() {
  local payload
  payload="$(json_field file_path "$1")"
  run --separate-stderr bash -c 'printf "%s" "$1" | "$2"' _ "$payload" "$SCRIPTS/guard-protected-paths.sh"
}

# no_yaml_env — prints a PYTHONPATH dir whose yaml module fails to import (simulates missing PyYAML)
no_yaml_env() {
  local d="$BATS_TEST_TMPDIR/noyaml"
  mkdir -p "$d"
  printf 'raise ImportError("PyYAML disabled for this test")\n' > "$d/yaml.py"
  printf '%s' "$d"
}

# path_without_python3 — prints a PATH with the basic tools but no python3
path_without_python3() {
  local d="$BATS_TEST_TMPDIR/nopy-bin" tool src
  mkdir -p "$d"
  for tool in bash sh cat dirname basename git grep sed tr printf env head tail mkdir rm pwd; do
    src="$(command -v "$tool" 2>/dev/null)" || continue
    [ -x "$src" ] && ln -sf "$src" "$d/$tool"
  done
  printf '%s' "$d"
}

# plant_modules — puts json.py and yaml.py in $PROJECT that write $PROJECT/PWNED when imported (C12a)
plant_modules() {
  local m
  for m in json yaml; do
    printf 'open(%q, "w").write("x")\n' "$PROJECT/PWNED" > "$PROJECT/$m.py"
  done
}
