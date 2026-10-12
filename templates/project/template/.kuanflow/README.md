# .kuanflow/

This project uses Kuanflow: AI-assisted workflows that read their settings from this directory.
Work artifacts live in `kuan-workbench/`; approved docs live in `docs/`.

| Path | Owner | Notes |
|---|---|---|
| `config.yaml` | you | Project config (commands, paths, protected paths). Edit values freely; upgrades merge. |
| `config.local.yaml` | you | Personal overrides. Git-ignored. |
| `scripts/` | Kuanflow | Guard and config hooks shared by all agents and git hooks. Avoid local edits; propose changes to Kuanflow. |
| `templates/` | you | Optional overrides of the spec/plan/review templates. |
| `manifest.json` | CLI | Installed version, agents and files. Written by the CLI; do not edit. |
| `state.json`, `scratch/`, `cache/` | CLI | Local state, temporary data and caches. Git-ignored. |

`../.copier-answers.yml` stores the answers this project was rendered with. Do not edit it by hand:
change answers through the CLI instead.

## Commands

- `kuanflow upgrade` — update these files to a newer Kuanflow version (3-way merge; conflicts are left
  for you to resolve).
- `kuanflow doctor` — check that the install is complete and consistent.
