#!/usr/bin/env bats
# Cheap smoke checks for the P1 skeleton.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "VERSION exists and is SemVer" {
  [ -f "$REPO_ROOT/VERSION" ]
  run head -n 1 "$REPO_ROOT/VERSION"
  [ "$status" -eq 0 ]
  [[ "$output" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$ ]]
}

@test "plugins/kuanflow/scripts directory exists" {
  [ -d "$REPO_ROOT/plugins/kuanflow/scripts" ]
}

@test "make verify wires bats" {
  run make -C "$REPO_ROOT" -n verify
  [ "$status" -eq 0 ]
  [[ "$output" == *"bats tests/bats"* ]]
}
