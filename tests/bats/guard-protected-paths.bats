#!/usr/bin/env bats
# Contract C12/C14: plugins/kuanflow/scripts/guard-protected-paths.sh

load helpers/common

setup() {
  common_setup
  write_config $'protected_paths:\n  - "src/main/resources/db/migration/**"\n  - "**/legacy/**"\n  - "docs/adr/**"'
  mkdir -p "$PROJECT/src/main/resources/db/migration"
  printf 'create table t (id int);\n' > "$PROJECT/src/main/resources/db/migration/V1__init.sql"
}

assert_blocked() {
  [ "$status" -eq 2 ] || { echo "expected exit 2, got $status (stderr: $stderr)"; return 1; }
  [[ "$stderr" == "Blocked by kuanflow guard:"* ]] || { echo "bad stderr: $stderr"; return 1; }
}

assert_allowed() {
  [ "$status" -eq 0 ] || { echo "expected exit 0, got $status (stderr: $stderr)"; return 1; }
}

@test "script is executable" {
  [ -x "$SCRIPTS/guard-protected-paths.sh" ]
}

@test "blocks edit of an existing protected file (absolute path)" {
  run_path_guard "$PROJECT/src/main/resources/db/migration/V1__init.sql"
  assert_blocked
  [[ "$stderr" == *"src/main/resources/db/migration/V1__init.sql"* ]]
  [[ "$stderr" == *"src/main/resources/db/migration/**"* ]]
}

@test "blocks edit of an existing protected file (relative path)" {
  run_path_guard "src/main/resources/db/migration/V1__init.sql"
  assert_blocked
}

@test "allows creating a new file under a protected path" {
  run_path_guard "$PROJECT/src/main/resources/db/migration/V2__add.sql"
  assert_allowed
}

@test "allows edit of an unprotected existing file" {
  mkdir -p "$PROJECT/src/main/java"
  printf 'class A {}\n' > "$PROJECT/src/main/java/A.java"
  run_path_guard "$PROJECT/src/main/java/A.java"
  assert_allowed
}

@test "leading **/ also matches zero directories" {
  mkdir -p "$PROJECT/legacy"
  printf 'x\n' > "$PROJECT/legacy/Old.java"
  run_path_guard "$PROJECT/legacy/Old.java"
  assert_blocked
}

@test "**/legacy/** matches a nested legacy dir" {
  mkdir -p "$PROJECT/src/main/java/com/acme/legacy"
  printf 'x\n' > "$PROJECT/src/main/java/com/acme/legacy/Old.java"
  run_path_guard "$PROJECT/src/main/java/com/acme/legacy/Old.java"
  assert_blocked
}

@test "protected path from config.local.yaml" {
  write_local $'protected_paths:\n  - "secrets-docs/**"'
  mkdir -p "$PROJECT/secrets-docs"
  printf 'x\n' > "$PROJECT/secrets-docs/a.md"
  run_path_guard "$PROJECT/secrets-docs/a.md"
  assert_blocked
  # project globs still apply when a local file exists
  run_path_guard "$PROJECT/src/main/resources/db/migration/V1__init.sql"
  assert_blocked
}

@test "only config.local.yaml present" {
  rm "$PROJECT/.kuanflow/config.yaml"
  write_local $'protected_paths:\n  - "x/**"'
  mkdir -p "$PROJECT/x"
  printf 'x\n' > "$PROJECT/x/a.txt"
  run_path_guard "$PROJECT/x/a.txt"
  assert_blocked
}

@test "path with spaces" {
  mkdir -p "$PROJECT/docs/adr"
  printf 'x\n' > "$PROJECT/docs/adr/0001 my decision.md"
  run_path_guard "$PROJECT/docs/adr/0001 my decision.md"
  assert_blocked
}

@test "path with unicode" {
  mkdir -p "$PROJECT/docs/adr"
  printf 'x\n' > "$PROJECT/docs/adr/0002-quyết-định.md"
  run_path_guard "$PROJECT/docs/adr/0002-quyết-định.md"
  assert_blocked
}

@test "path with square brackets" {
  mkdir -p "$PROJECT/docs/adr"
  printf 'x\n' > "$PROJECT/docs/adr/[draft] 0003.md"
  run_path_guard "$PROJECT/docs/adr/[draft] 0003.md"
  assert_blocked
}

@test "new file with special characters is allowed" {
  mkdir -p "$PROJECT/docs/adr"
  run_path_guard "$PROJECT/docs/adr/[new] ý tưởng.md"
  assert_allowed
}

@test "path outside the project root is allowed" {
  mkdir -p "$BATS_TEST_TMPDIR/elsewhere/legacy"
  printf 'x\n' > "$BATS_TEST_TMPDIR/elsewhere/legacy/a.java"
  run_path_guard "$BATS_TEST_TMPDIR/elsewhere/legacy/a.java"
  assert_allowed
}

@test "works from a subdirectory of the project" {
  mkdir -p "$PROJECT/src/main"
  cd "$PROJECT/src/main"
  run_path_guard "resources/db/migration/V1__init.sql"
  assert_blocked
}

@test "no config at all allows everything" {
  rm "$PROJECT/.kuanflow/config.yaml"
  run_path_guard "$PROJECT/src/main/resources/db/migration/V1__init.sql"
  assert_allowed
}

@test "malformed config is ignored" {
  printf 'protected_paths: [unclosed\n' > "$PROJECT/.kuanflow/config.yaml"
  run_path_guard "$PROJECT/src/main/resources/db/migration/V1__init.sql"
  assert_allowed
}

@test "without PyYAML the guard allows" {
  PYTHONPATH="$(no_yaml_env)"
  export PYTHONPATH
  run_path_guard "$PROJECT/src/main/resources/db/migration/V1__init.sql"
  assert_allowed
}

@test "without python3 the guard fails open" {
  local p payload
  p="$(path_without_python3)"
  payload="{\"tool_input\":{\"file_path\":\"$PROJECT/src/main/resources/db/migration/V1__init.sql\"}}"
  run --separate-stderr env PATH="$p" bash -c 'printf "%s" "$1" | "$2"' _ "$payload" \
    "$SCRIPTS/guard-protected-paths.sh"
  assert_allowed
}

@test "invalid JSON is allowed" {
  run --separate-stderr bash -c 'printf "{bad" | "$1"' _ "$SCRIPTS/guard-protected-paths.sh"
  assert_allowed
}

@test "missing file_path is allowed" {
  run --separate-stderr bash -c 'printf "{\"tool_input\":{}}" | "$1"' _ "$SCRIPTS/guard-protected-paths.sh"
  assert_allowed
}
