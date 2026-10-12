---
description: W0 — Plan the day - top 3, blockers and early questions in the personal journal
argument-hint: "[YYYY-MM-DD]"
---
Run the daily-plan skill for $ARGUMENTS (today if empty).

If `w0` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `workflows.enabled`, `paths.work` and
   `integrations.jira_project_key`. Outside a Kuanflow project, continue with personal sources only.
2. Execute every step of daily-plan. The top 3 is a proposal until I confirm it.
3. Write `~/.kuanflow/journal/YYYY/MM/YYYY-MM-DD.md`. End with the proposed top 3 and the questions to send early.
