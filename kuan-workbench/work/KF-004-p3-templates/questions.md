---
work: KF-004-p3-templates
status: answered (Gate P3, 2026-10-13)
---
# Questions raised in P3

## Q-32 Re-review leftovers R1–R4 (all low/info, review.md)
R1 hostile-value test lacks U+FFFE/U+FFFF/lone surrogate; R2 literal non-ASCII checked only for `project.name`;
R3 `project.name`/`project.stack` adjacent (edit one while upstream changes the other → conflict);
R4 invisible/bidi characters (Unicode Cf, e.g. U+202E) written raw into `config.yaml`.
- A. Small fix round 2 at the start of P4 (tests for R1/R2, blank line for R3, escape Cf for R4).
- B. Accept as is.
- **Recommend A** (cheap; R4 avoids a command that looks different from what runs).

## Q-33 Decisions beyond the docs (D-P3-1..5, plan.md)
1. `lint_cmd` defaults: maven `./mvnw -q spotless:check`, gradle `./gradlew spotlessCheck`, others `make lint`;
   node/python keep the PKG `make` defaults (the P4 detector passes real commands).
2. One `gitignore` block body with `artifacts_commit` conditions (not `gitignore-*` files).
3. `kuanflow_version` filled by `engine.render()` from `VERSION`; `VERSION` ships in the wheel.
4. Scripts get mode 0755 in the synthetic repo (closes D-P2-6).
5. Knowledge repo uses the same engine and `.kuanflow/cache/template-repo`, and ships a `.gitignore`.
6. Config schema: top level closed except `x-*` keys; `project`, `commands`, `debug`, `knowledge`,
   `integrations` open; other sections closed.
- **Recommend:** accept all.

## Q-34 ADR-0002 TODO(verify) items still open
Relative `_src_path` from a sub-directory (P4: CLI chdirs to root), upstream-deleted files, and `exclude=` to stop
re-creating a deleted `docs/adr/0000-template.md` are not exercised in P3 (no `upgrade` yet).
- **Recommend:** carry to P4 (root handling) and P6 (upgrade tests), as listed in plan.md "Carried to P4/P6".

## Gate P3 answers (2026-10-13)
Human decision: **"apply all recommendations"** ("áp dụng tất cả đề xuất").
- Q-32 → **A** (fix round 2 for R1–R4 at the start of P4: tests for R1/R2, blank line for R3, escape Unicode Cf
  for R4).
- Q-33 → **accepted** (all six decisions).
- Q-34 → **carried** to P4 (root handling) and P6 (upgrade tests).
