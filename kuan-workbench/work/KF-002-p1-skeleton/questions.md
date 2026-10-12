---
work: KF-002-p1-skeleton
status: open (Gate P1)
---
# Questions raised in P1

## Q-26 Rollback with `upgrade --to <older>` (PKG §10.5, UPG-04)
Spike S1 (ADR-0002 §h): Copier refuses downgrades (`Downgrades are not supported`).
PKG §10.5 lists two rollback paths: `git revert` of the upgrade PR, or `kuanflow upgrade --to <old>`.
- A. Support only `git revert`; `upgrade --to <older>` exits 1 with instructions. Deviates from PKG §10.5.
- B. The synthetic template repo is rebuilt for every operation, so its tags are internal. The CLI can always tag
  "currently installed content" as internal `0.0.1` and "target content" as `0.0.2`, even when the target is an
  older Kuanflow release. Copier then sees an upgrade and runs a normal 3-way merge. The real Kuanflow version is
  kept in the answers data and the manifest. Needs a P6 spike to confirm Copier accepts the `_commit` rewrite this
  implies.
- **Recommend B**, with A as fallback if the P6 spike fails. The P6 downgrade test stays in the plan.

## Q-27 `copier.yml` `_migrations` (PKG §6.3)
ADR-0002 confirms that `unsafe=True` is needed only when the template has `_tasks`, `_migrations` or
`_jinja_extensions`. Q-09 already chose CLI-only migrations, so the template will NOT contain the `_migrations`
example from PKG §6.3. This is recorded here because it is a visible deviation from the doc sample.
- **Recommend:** accept (no action).

## Q-28 CODEOWNERS rule for `plugins/kuanflow/scripts/` (D-P1-2, review F6)
PKG §14 has no rule for `plugins/kuanflow/scripts/`. P1 adds
`plugins/kuanflow/scripts/ @<org>/kuanflow-maintainers @<org>/security`, because the guard scripts that hooks call
are as security-sensitive as `hooks/` (PKG §15). Contract C8a allows this extra line.
- A. Keep the rule (deviation from PKG §14, recorded here).
- B. Remove it and follow PKG §14 exactly.
- **Recommend A.**
