#!/usr/bin/env bats
# Contract C12/C15: plugins/kuanflow/scripts/load-config.sh

load helpers/common

setup() {
  common_setup
  unset CLAUDE_PLUGIN_ROOT
}

run_load() {
  run --separate-stderr "$SCRIPTS/load-config.sh"
}

write_manifest() {
  printf '{"kuanflow_version": "%s"}\n' "$1" > "$PROJECT/.kuanflow/manifest.json"
}

@test "script is executable" {
  [ -x "$SCRIPTS/load-config.sh" ]
}

@test "silent without config" {
  run_load
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "silent outside any kuanflow project" {
  rmdir "$PROJECT/.kuanflow"
  run_load
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "prints version from manifest and both layers in order" {
  write_manifest "0.2.0"
  write_config $'schema_version: 1\ncommands:\n  verify: make verify'
  write_local $'commands:\n  verify: make verify-local'
  run_load
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "## kuanflow v0.2.0" ]
  [[ "$output" == *"Effective config (later file overrides earlier):"* ]]
  [[ "$output" == *"### .kuanflow/config.yaml"* ]]
  [[ "$output" == *"### .kuanflow/config.local.yaml"* ]]
  [[ "$output" == *'```yaml'* ]]
  [[ "$output" == *"verify: make verify-local"* ]]
  # project layer printed before local layer
  local before="${output%%### .kuanflow/config.local.yaml*}"
  [[ "$before" == *"### .kuanflow/config.yaml"* ]]
  [[ "${lines[${#lines[@]}-1]}" == Rules:* ]]
  [ -z "$stderr" ]
}

@test "only local layer present" {
  write_local $'commands:\n  test: make t'
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" == *"### .kuanflow/config.local.yaml"* ]]
  [[ "$output" != *"### .kuanflow/config.yaml"* ]]
}

@test "version from plugin.json when no manifest" {
  write_config "schema_version: 1"
  mkdir -p "$BATS_TEST_TMPDIR/plugin/.claude-plugin"
  printf '{"name": "kuanflow", "version": "0.3.0"}\n' > "$BATS_TEST_TMPDIR/plugin/.claude-plugin/plugin.json"
  CLAUDE_PLUGIN_ROOT="$BATS_TEST_TMPDIR/plugin" run --separate-stderr "$SCRIPTS/load-config.sh"
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "## kuanflow v0.3.0" ]
}

@test "version unknown without manifest or plugin" {
  write_config "schema_version: 1"
  run_load
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "## kuanflow vunknown" ]
}

@test "warns when installed version is older than min_version" {
  write_manifest "0.1.0"
  write_config $'kuanflow:\n  min_version: "0.2.0"'
  run_load
  [ "$status" -eq 0 ]
  local warn
  warn="$(printf '%s\n' "$output" | grep '^WARNING:')"
  [[ "$warn" == *"0.1.0"* ]]
  [[ "$warn" == *"0.2.0"* ]]
  [[ "$warn" == *"kuanflow upgrade"* ]]
}

@test "no warning when installed version satisfies min_version" {
  write_manifest "0.10.0"
  write_config $'kuanflow:\n  min_version: "0.9.0"'
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" != *"WARNING:"* ]]
}

@test "prerelease is older than the same release" {
  write_manifest "0.2.0-dev"
  write_config $'kuanflow:\n  min_version: "0.2.0"'
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" == *"WARNING:"* ]]
}

@test "prerelease of a newer core satisfies min_version" {
  write_manifest "0.3.0-dev"
  write_config $'kuanflow:\n  min_version: "0.2.0"'
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" != *"WARNING:"* ]]
}

@test "min_version not directly after kuanflow: is still read" {
  write_manifest "1.0.0"
  write_config $'kuanflow:\n  # required by this project\n  channel: stable\n  min_version: "1.4.0"'
  run_load
  [[ "$output" == *"WARNING:"* ]]
}

@test "local min_version overrides project" {
  write_manifest "1.0.0"
  write_config $'kuanflow:\n  min_version: "2.0.0"'
  write_local $'kuanflow:\n  min_version: "0.5.0"'
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" != *"WARNING:"* ]]
}

@test "no warning when version is unknown" {
  write_config $'kuanflow:\n  min_version: "9.0.0"'
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" != *"WARNING:"* ]]
}

@test "garbage min_version does not fail" {
  write_manifest "1.0.0"
  write_config $'kuanflow:\n  min_version: "banana"'
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" != *"WARNING:"* ]]
}

@test "malformed manifest falls back to unknown" {
  printf '{not json' > "$PROJECT/.kuanflow/manifest.json"
  write_config "schema_version: 1"
  run_load
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "## kuanflow vunknown" ]
}

@test "malformed config still prints and exits 0" {
  write_manifest "1.0.0"
  printf 'kuanflow: [unclosed\n' > "$PROJECT/.kuanflow/config.yaml"
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" == *"### .kuanflow/config.yaml"* ]]
}

@test "works without PyYAML" {
  write_manifest "1.0.0"
  write_config $'kuanflow:\n  min_version: "1.4.0"'
  PYTHONPATH="$(no_yaml_env)"
  export PYTHONPATH
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" == *"WARNING:"* ]]
}

@test "works without python3" {
  write_config "schema_version: 1"
  local p
  p="$(path_without_python3)"
  run --separate-stderr env PATH="$p" "$SCRIPTS/load-config.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"### .kuanflow/config.yaml"* ]]
}

@test "found from a subdirectory" {
  write_config "schema_version: 1"
  mkdir -p "$PROJECT/a/b"
  cd "$PROJECT/a/b"
  run_load
  [ "$status" -eq 0 ]
  [[ "$output" == *"### .kuanflow/config.yaml"* ]]
}
