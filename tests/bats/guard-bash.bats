#!/usr/bin/env bats
# Contract C12/C13: plugins/kuanflow/scripts/guard-bash.sh

load helpers/common

setup() {
  common_setup
}

assert_blocked() {
  [ "$status" -eq 2 ] || { echo "expected exit 2, got $status (stderr: $stderr)"; return 1; }
  [[ "$stderr" == "Blocked by kuanflow guard:"* ]] || { echo "bad stderr: $stderr"; return 1; }
}

assert_allowed() {
  [ "$status" -eq 0 ] || { echo "expected exit 0, got $status (stderr: $stderr)"; return 1; }
}

@test "script is executable" {
  [ -x "$SCRIPTS/guard-bash.sh" ]
}

# --- B1 force push to protected branch ---------------------------------------------------------

@test "B1 blocks force push to main" {
  run_bash_guard "git push --force origin main"
  assert_blocked
}

@test "B1 blocks -f push to release branch" {
  run_bash_guard "git push -f origin release/1.2"
  assert_blocked
}

@test "B1 allows force push to a feature branch" {
  run_bash_guard "git push --force origin feature/x"
  assert_allowed
}

# --- B2 direct push to main/master -------------------------------------------------------------

@test "B2 blocks direct push to main" {
  run_bash_guard "git push origin main"
  assert_blocked
}

@test "B2 blocks push of HEAD:master" {
  run_bash_guard "git push origin HEAD:master"
  assert_blocked
}

@test "B2 blocks push to refs/heads/main" {
  run_bash_guard "git push origin refs/heads/main"
  assert_blocked
}

@test "B2 allows branch whose name contains main" {
  run_bash_guard "git push origin feature/main-menu"
  assert_allowed
}

@test "B2 allows branch with a main path segment prefix" {
  run_bash_guard "git push origin fix/main-x"
  assert_allowed
}

@test "B2 allows push to a feature branch" {
  run_bash_guard "git push -u origin feature/ORD-1-thing"
  assert_allowed
}

# --- B3 production cluster ---------------------------------------------------------------------

@test "B3 blocks kubectl with prod context" {
  run_bash_guard "kubectl --context prod-eu get pods"
  assert_blocked
}

@test "B3 blocks helm with production namespace" {
  run_bash_guard "helm upgrade orders ./chart -n production"
  assert_blocked
}

@test "B3 allows kubectl with staging context" {
  run_bash_guard "kubectl --context staging get pods"
  assert_allowed
}

# --- B4 production datastore -------------------------------------------------------------------

@test "B4 blocks psql to a prod host" {
  run_bash_guard "psql -h db.prod.internal -U app"
  assert_blocked
}

@test "B4 blocks redis-cli to production" {
  run_bash_guard "redis-cli -h cache-production.internal"
  assert_blocked
}

@test "B4 allows psql to localhost" {
  run_bash_guard "psql -h localhost -U app"
  assert_allowed
}

# --- B5 destructive rm -------------------------------------------------------------------------

@test "B5 blocks rm -rf /" {
  run_bash_guard "rm -rf /"
  assert_blocked
}

@test "B5 blocks rm -fr ~" {
  run_bash_guard "rm -fr ~"
  assert_blocked
}

@test "B5 blocks rm -rf \$HOME" {
  run_bash_guard 'rm -rf $HOME'
  assert_blocked
}

@test "B5 blocks rm -rf ." {
  run_bash_guard "rm -rf ."
  assert_blocked
}

@test "B5 blocks rm -rf .. followed by another command" {
  run_bash_guard "rm -rf .. && ls"
  assert_blocked
}

@test "B5 blocks rm -r -f /*" {
  run_bash_guard "rm -r -f /*"
  assert_blocked
}

@test "B5 allows rm -rf ./build" {
  run_bash_guard "rm -rf ./build"
  assert_allowed
}

@test "B5 allows rm -rf target" {
  run_bash_guard "rm -rf target"
  assert_allowed
}

# --- B6 destructive SQL ------------------------------------------------------------------------

@test "B6 blocks DROP TABLE in any case" {
  run_bash_guard 'psql -c "DROP TABLE orders"'
  assert_blocked
}

@test "B6 blocks drop database" {
  run_bash_guard 'mysql -e "drop database app"'
  assert_blocked
}

@test "B6 allows a word starting with drop" {
  run_bash_guard "grep -r drop_log ."
  assert_allowed
}

# --- B7 reading .env ---------------------------------------------------------------------------

@test "B7 blocks cat .env" {
  run_bash_guard "cat .env"
  assert_blocked
}

@test "B7 blocks cp .env.production" {
  run_bash_guard "cp .env.production /tmp/x"
  assert_blocked
}

@test "B7 blocks tail of a nested .env" {
  run_bash_guard "tail -n 5 service/.env"
  assert_blocked
}

@test "B7 allows cat README.md" {
  run_bash_guard "cat README.md"
  assert_allowed
}

@test "B7 allows cat .envrc" {
  run_bash_guard "cat .envrc"
  assert_allowed
}

# --- B8 project patterns -----------------------------------------------------------------------

@test "B8 blocks a project pattern from config.yaml" {
  write_config $'guard:\n  extra_block_patterns:\n    - "terraform apply"'
  run_bash_guard "terraform apply -auto-approve"
  assert_blocked
}

@test "B8 blocks a project pattern from config.local.yaml" {
  write_config "schema_version: 1"
  write_local $'guard:\n  extra_block_patterns:\n    - "^make deploy"'
  run_bash_guard "make deploy"
  assert_blocked
}

@test "B8 allows a command not matching project patterns" {
  write_config $'guard:\n  extra_block_patterns:\n    - "terraform apply"'
  run_bash_guard "terraform plan"
  assert_allowed
}

@test "B8 ignores an invalid regex" {
  write_config $'guard:\n  extra_block_patterns:\n    - "(unclosed"\n    - "terraform apply"'
  run_bash_guard "terraform apply"
  assert_blocked
  run_bash_guard "ls"
  assert_allowed
}

@test "B8 finds config from a subdirectory of the project" {
  write_config $'guard:\n  extra_block_patterns:\n    - "terraform apply"'
  mkdir -p "$PROJECT/svc/sub"
  cd "$PROJECT/svc/sub"
  run_bash_guard "terraform apply"
  assert_blocked
}

@test "B8 without PyYAML project patterns are skipped and built-ins still work" {
  write_config $'guard:\n  extra_block_patterns:\n    - "terraform apply"'
  PYTHONPATH="$(no_yaml_env)"
  export PYTHONPATH
  run_bash_guard "terraform apply"
  assert_allowed
  run_bash_guard "git push --force origin main"
  assert_blocked
}

# --- C12 robustness ----------------------------------------------------------------------------

@test "allows normal build command" {
  run_bash_guard "./mvnw -q test"
  assert_allowed
}

@test "allows git status" {
  run_bash_guard "git status"
  assert_allowed
}

@test "invalid JSON is allowed" {
  run --separate-stderr bash -c 'printf "not json" | "$1"' _ "$SCRIPTS/guard-bash.sh"
  assert_allowed
}

@test "empty stdin is allowed" {
  run --separate-stderr bash -c '"$1" < /dev/null' _ "$SCRIPTS/guard-bash.sh"
  assert_allowed
}

@test "missing command field is allowed" {
  run --separate-stderr bash -c 'printf "{\"tool_input\":{}}" | "$1"' _ "$SCRIPTS/guard-bash.sh"
  assert_allowed
}

@test "without python3 the guard fails open" {
  local p
  p="$(path_without_python3)"
  run --separate-stderr env PATH="$p" bash -c \
    'printf "{\"tool_input\":{\"command\":\"git push --force origin main\"}}" | "$1"' _ "$SCRIPTS/guard-bash.sh"
  assert_allowed
}
