# Shared runbooks

Runbooks that apply to more than one service: one file per procedure, for example
`runbooks-shared/replay-settlement-events.md`. Runbooks for a single service live in that service's
repo under `docs/runbooks/`.

Give each runbook a title, either as frontmatter `title:` or as the first `# ` heading.
`scripts/build-index.py` uses it for the index. A person writes or approves every runbook, since
on-call engineers follow it step by step. Review runbooks periodically.
