---
description: W9 — Draft a daily or weekly work report with evidence links
argument-hint: "[daily|weekly]"
---
Run the work-report skill for a $ARGUMENTS report (daily if empty).

If `w9` is not listed in `workflows.enabled`, say so and stop.

1. Read `.kuanflow/config.yaml` (and `.kuanflow/config.local.yaml`) for `workflows.enabled`, `paths.work` and
   `integrations.jira_project_key`. Outside a Kuanflow project, continue with personal sources only.
2. Execute every step of work-report. Every Done item needs an evidence link.
3. Write the report under `~/.kuanflow/reports/` and show it to me for a tone edit before anyone sees it.
