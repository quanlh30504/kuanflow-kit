# Review — KF-003 P2 Content source — `6f82127..358713f`

Reviewer: Coordinator (inline, adversarial). Mutations replayed each in a fresh clone under the scratchpad
(`review-p2/mutate.py`); oracle = `pytest` + `bats tests/bats` + `check_skills.py`. Nothing in the repo changed
except this file.

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Full verify suite | PASS | `make verify` exit 0: ruff clean, `775 passed`, bats `1..105` all ok, both checkers silent. |
| 2 | RED before GREEN | PASS | e94863a: pytest `195 failed, 21 passed, 1 skipped, 7 errors`; bats `102 not ok, 3 ok`. |
| 3 | Tests changed after RED | PASS (recorded) | 6f1556c fixes two test defects (bats stderr temp file; C17e weak check made stricter). Neither loosens a contract. |
| 4 | Contract → test mapping (mutation) | **FAIL** | 22 mutations, 17 killed. Survivors: M2/M17 drop the `sys.path` scrub (guard-bash, guard-protected-paths); M13 drop `more` from B7; M16 `+main` refspec no longer counts as force; M22 `rm -r` without `-f` treated like `-rf`. |
| 5 | Guard bypass probes | **FAIL** | `bash -c "git push --force origin main"`, `sh -c 'rm -rf /'`, `eval "git push origin main"` → exit 0. The PKG §18.4 sample (grep on the whole string) blocks the first and third. `$(…)`, `sudo`, `&&`, `git -C`, `+main`, `xargs cat < list .env` → blocked. `rm -r ~` → allowed. |
| 6 | Module hijack (repo ships `json.py`) | PASS (untested) | `json.py` that writes a marker in the project dir: no marker after running all four scripts; guard still blocks. Not covered by any test (row 4). |
| 7 | Verbatim content vs docs | PASS | Tests read PB §8.4–8.7 and PKG §5.4 from `docs/` and check frontmatter + ordered body lines; M10 killed. Additions read: only config/key/output lines; no doc rule dropped or weakened. |
| 8 | Derived content vs PB | PASS | Read each derived skill/agent/command against PB W0–W10, §6.4, §7.4, §7.5, §13. Gates, anti-patterns and outputs match; translations keep structure. Additions beyond PB: `state.json` `{"work": …}` format, fintech-review "skip when `risk.fintech` false and no money", w6 test map in `plan.md` — recorded as D-P2-4. |
| 9 | Hard-coded commands / paths / keys | PASS | check_skills S4 clean; C20 tests: no `kuan-workbench/`, `docs/adr`, `docs/runbooks`; every used key in PKG §7.1 + Q-11 and in the README table. |
| 10 | Security / hygiene | PASS | No network in scripts (bats grep + S5); no secrets; masking verified on e-mail/phone/account/id/long digits; collector refuses `paths.scratch` outside `.kuanflow/` and ids with `/`. |

## Findings

- **F1 — high — `guard-bash.sh`: wrapped commands bypass the token rules (row 5).** `bash -c "…"`, `sh -c '…'`,
  `eval "…"` hide a whole command in one quoted word. Fix: also scan every word that contains whitespace as a
  command line of its own (bounded depth). Add bats cases for `bash -c`, `sh -c`, `eval`.
- **F2 — med — module-hijack protection untested (M2, M17).** Add a bats case per script: a project-local
  `json.py`/`yaml.py` that writes a marker must not run.
- **F3 — low — B1 `+refspec` force and B7 `more` untested (M13, M16).** Add bats cases.
- **F4 — low — B5 needs `-f` (M22, row 5).** `rm -r ~` on a write-protected tree still destroys it. Proposal:
  block a recursive `rm` of the dangerous targets with or without `-f` (stricter than PKG; C13 B5 amended).

## "What would make me reject this phase even though verify is green?"
1. A guard that a one-word wrapper defeats, when the doc sample did not have that hole → yes, F1.
2. A security property (no imports from the repo) with no test → F2.
3. Content that contradicts PB → checked, none found (rows 7, 8).

## Verdict: FAIL — fix F1–F4, then re-review.

---

# Re-review — fix round 1 — `dd111d1..HEAD`

Reviewer: Coordinator (inline; fresh clone per mutation, same oracle).

| Finding | Status | Evidence |
|---|---|---|
| F1 wrapped commands | **fixed** (C13a) | `bash -c "git push --force origin main"`, `sh -c 'rm -rf /'`, `eval "git push origin main"`, doubly wrapped `cat .env` → exit 2. New mutation M23 (disable the nested scan) → killed by bats. |
| F2 module hijack untested | **fixed** (C12a) | One bats case per script plants `json.py`/`yaml.py`; M2, M17 → killed. (The first RED run also exposed the test helper importing the planted module; helper now uses `python3 -I`.) |
| F3 `+main`, `more` | **fixed** (C13c) | M13, M16 → killed. |
| F4 `rm -r` without `-f` | **fixed** (C13b) | `rm -r ~` → exit 2, `rm -r ./build` → exit 0; reverse mutation (require `-f` again) → killed. |
| Verify suite | PASS | `make verify` exit 0; bats `1..118` all ok. |

Known limitation (recorded as Q-29, not a defect against the contract): quoted text is scanned too, so
`git commit -m "docs: explain git push origin main"` is blocked. The PKG §18.4 grep sample has the same
false positive.

## Verdict: PASS
