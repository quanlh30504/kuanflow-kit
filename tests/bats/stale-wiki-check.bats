#!/usr/bin/env bats
# Contract C34: templates/knowledge-repo/template/scripts/stale-wiki-check.sh

bats_require_minimum_version 1.5.0

setup() {
  ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$ROOT/templates/knowledge-repo/template/scripts/stale-wiki-check.sh"
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_CEILING_DIRECTORIES="$BATS_TEST_TMPDIR"
  REPO="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$REPO/src" "$REPO/docs"
  g init -q
  printf 'a\n' > "$REPO/src/a.txt"
  printf 'b\n' > "$REPO/src/b.txt"
  printf 'c\n' > "$REPO/docs/c.txt"
  commit "base"
  BASE="$(g rev-parse HEAD)"
  # run from somewhere that is not the repo
  cd "$BATS_TEST_TMPDIR" || return 1
}

g() {
  git -C "$REPO" -c user.name=t -c user.email=t@t -c commit.gpgsign=false "$@"
}

commit() {
  g add -A
  g commit -q -m "$1"
}

# page <name> <frontmatter body> — writes kuan-workbench/wiki/<name>.md (not committed)
page() {
  mkdir -p "$REPO/kuan-workbench/wiki"
  printf -- '---\n%s\n---\n## Summary\nText.\n' "$2" > "$REPO/kuan-workbench/wiki/$1.md"
}

# page_c — like page, then commits
page_c() {
  page "$@"
  commit "wiki $1"
}

change() {
  printf 'changed %s\n' "$RANDOM" >> "$REPO/$1"
  commit "change $1"
}

snapshot() {
  (cd "$REPO" && find . -path ./.git -prune -o -type f -print0 | sort -z | xargs -0 sha256sum)
}

run_check() {
  run --separate-stderr "$SCRIPT" "$@"
}

@test "script is executable" {
  [ -x "$SCRIPT" ]
}

@test "fresh page: exit 0, no output" {
  page_c flow "generated: true
source_commit: $BASE
source_paths: [src/a.txt]"
  change docs/c.txt
  run_check "$REPO"
  [ "$status" -eq 0 ] || { echo "status=$status out=$output err=$stderr"; return 1; }
  [ -z "$output" ]
}

@test "abbreviated source_commit is accepted" {
  page_c flow "generated: true
source_commit: ${BASE:0:7}
source_paths: [src/a.txt]"
  run_check "$REPO"
  [ "$status" -eq 0 ] || { echo "status=$status out=$output err=$stderr"; return 1; }
  [ -z "$output" ]
}

@test "stale page: STALE line, exit 1" {
  page_c flow "generated: true
source_commit: $BASE
source_paths: [src/a.txt]"
  change src/a.txt
  run_check "$REPO"
  [ "$status" -eq 1 ] || { echo "status=$status out=$output"; return 1; }
  [ "$output" = "STALE kuan-workbench/wiki/flow.md" ]
}

@test "directory in source_paths: change below it is stale" {
  page_c flow "generated: true
source_commit: $BASE
source_paths: [src/]"
  change src/b.txt
  run_check "$REPO"
  [ "$status" -eq 1 ]
  [ "$output" = "STALE kuan-workbench/wiki/flow.md" ]
}

@test "flow list source_paths: change in second path is stale" {
  page_c flow "generated: true
source_commit: $BASE
source_paths: [src/a.txt, src/b.txt]"
  change src/b.txt
  run_check "$REPO"
  [ "$status" -eq 1 ]
  [ "$output" = "STALE kuan-workbench/wiki/flow.md" ]
}

@test "block list source_paths: change in second path is stale" {
  page_c flow "generated: true
source_commit: $BASE
source_paths:
  - src/a.txt
  - src/b.txt"
  change src/b.txt
  run_check "$REPO"
  [ "$status" -eq 1 ]
  [ "$output" = "STALE kuan-workbench/wiki/flow.md" ]
}

@test "block list source_paths: unrelated change is fresh" {
  page_c flow "generated: true
source_commit: $BASE
source_paths:
  - src/a.txt
  - src/b.txt"
  change docs/c.txt
  run_check "$REPO"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "uncommitted change is not compared (source_commit vs HEAD only)" {
  page_c flow "generated: true
source_commit: $BASE
source_paths: [src/a.txt]"
  printf 'dirty\n' >> "$REPO/src/a.txt"
  run_check "$REPO"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "unknown commit: UNKNOWN line, exit 1" {
  page_c flow "generated: true
source_commit: 0123456789abcdef0123456789abcdef01234567
source_paths: [src/a.txt]"
  run_check "$REPO"
  [ "$status" -eq 1 ]
  [ "${#lines[@]}" -eq 1 ]
  [[ "${lines[0]}" == "UNKNOWN kuan-workbench/wiki/flow.md: "?* ]]
}

@test "missing source_commit: UNKNOWN" {
  page_c flow "generated: true
source_paths: [src/a.txt]"
  run_check "$REPO"
  [ "$status" -eq 1 ]
  [[ "$output" == "UNKNOWN kuan-workbench/wiki/flow.md: "?* ]]
}

@test "missing source_paths: UNKNOWN" {
  page_c flow "generated: true
source_commit: $BASE"
  run_check "$REPO"
  [ "$status" -eq 1 ]
  [[ "$output" == "UNKNOWN kuan-workbench/wiki/flow.md: "?* ]]
}

@test "pages without generated: true are ignored" {
  page manual "title: Hand written
source_commit: 0123456789abcdef0123456789abcdef01234567
source_paths: [src/a.txt]"
  page notgen "generated: false
source_commit: $BASE
source_paths: [src/a.txt]"
  mkdir -p "$REPO/kuan-workbench/wiki"
  printf '# No frontmatter\n' > "$REPO/kuan-workbench/wiki/plain.md"
  commit "pages"
  change src/a.txt
  run_check "$REPO"
  [ "$status" -eq 0 ] || { echo "status=$status out=$output err=$stderr"; return 1; }
  [ -z "$output" ]
}

@test "mixed pages: only the stale and unknown ones are reported" {
  page fresh "generated: true
source_commit: $BASE
source_paths: [docs/c.txt]"
  page stale "generated: true
source_commit: $BASE
source_paths: [src/a.txt]"
  page unknown "generated: true
source_paths: [src/a.txt]"
  commit "pages"
  change src/a.txt
  run_check "$REPO"
  [ "$status" -eq 1 ]
  [ "${#lines[@]}" -eq 2 ] || { echo "$output"; return 1; }
  printf '%s\n' "${lines[@]}" | grep -qx 'STALE kuan-workbench/wiki/stale.md'
  printf '%s\n' "${lines[@]}" | grep -q '^UNKNOWN kuan-workbench/wiki/unknown.md: .'
  ! printf '%s\n' "${lines[@]}" | grep -q 'fresh.md'
}

@test "files are never modified" {
  page stale "generated: true
stale: false
source_commit: $BASE
source_paths: [src/a.txt]"
  page unknown "generated: true
source_commit: 0123456789abcdef0123456789abcdef01234567
source_paths: [src/a.txt]"
  commit "pages"
  change src/a.txt
  before="$(snapshot)"
  head_before="$(g rev-parse HEAD)"
  run_check "$REPO"
  [ "$status" -eq 1 ]
  [ "$(snapshot)" = "$before" ]
  [ "$(g rev-parse HEAD)" = "$head_before" ]
  [ -z "$(g status --porcelain)" ]
}

@test "no wiki directory: exit 0" {
  run_check "$REPO"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "empty wiki directory: exit 0" {
  mkdir -p "$REPO/kuan-workbench/wiki"
  run_check "$REPO"
  [ "$status" -eq 0 ]
}

@test "no argument: exit 2" {
  run_check
  [ "$status" -eq 2 ]
}

@test "not a git work tree: exit 2" {
  mkdir -p "$BATS_TEST_TMPDIR/plain/kuan-workbench/wiki"
  run_check "$BATS_TEST_TMPDIR/plain"
  [ "$status" -eq 2 ]
}

@test "missing path: exit 2" {
  run_check "$BATS_TEST_TMPDIR/does-not-exist"
  [ "$status" -eq 2 ]
}

@test "C34a: modules are not imported from the working directory or PYTHONPATH" {
  page_c flow "generated: true
source_commit: $BASE
source_paths: [src/a.txt]"
  change src/a.txt
  plant="$BATS_TEST_TMPDIR/plant"
  mkdir -p "$plant"
  marker="$BATS_TEST_TMPDIR/planted-module-ran"
  for dir in "$BATS_TEST_TMPDIR" "$plant" "$REPO/kuan-workbench/wiki"; do
    printf 'open(%s, "w").close()\n' "'$marker'" > "$dir/yaml.py"
    printf 'open(%s, "w").close()\n' "'$marker'" > "$dir/re.py"
  done
  # cwd is $BATS_TEST_TMPDIR (setup); PYTHONPATH points at another planted dir
  PYTHONPATH="$plant" run --separate-stderr "$SCRIPT" "$REPO"
  [ ! -e "$marker" ] || { echo "planted module ran"; return 1; }
  [ "$status" -eq 1 ] || { echo "status=$status out=$output err=$stderr"; return 1; }
  [ "$output" = "STALE kuan-workbench/wiki/flow.md" ]
}
