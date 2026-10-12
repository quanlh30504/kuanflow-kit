---
name: write-postmortem
description: Use after a production incident has been fixed or mitigated, to draft a blameless postmortem with structured frontmatter (id, services, category, signatures) for the knowledge repo. Do not use while the incident is still being investigated (use debug-incident).
---
# Write postmortem (W10)

## Before you start
1. Read the effective config. It is printed at session start; if you do not see it, read
   `.kuanflow/config.yaml`, then `.kuanflow/config.local.yaml` (the local file overrides the project file).
2. Resolve the work item, in this order: env `KUANFLOW_WORK` (a path or incident id) → the ticket key in the
   branch name, matched with `work.ticket_pattern` → the `work` field of `.kuanflow/state.json` → ask the human.
   Incidents use `<paths.work>/<INCIDENT-ID>-<slug>/`.
3. Required keys: `paths.work`. Optional: `knowledge.repo`. If a required key is missing, stop and ask the human.
4. Template: use `.kuanflow/templates/postmortem.md` if the project has one; otherwise `templates/postmortem.md`
   in this skill's directory.

## Inputs
`incident-notes.md` of the incident folder, the fix PR, the regression test, timeline data, and the human's
notes on impact and mitigation. Ask for anything the notes do not contain; do not invent impact numbers.

## Steps
1. Fill the frontmatter:
   - `id`: the incident id. `severity`: as declared during the incident.
   - `services`: every affected service.
   - `category`: exactly one from the taxonomy below.
   - `signatures`: the exact error strings someone would search for (exception + key text).
   - `fix_pr`, `regression_test`, `related_adr` when they exist. `status: draft`.
2. Write the sections of the template. Times in Vietnam time (Asia/Ho_Chi_Minh), stated once.
3. Root cause with 5 whys, down to the system cause: why was it not detected earlier?
4. Blameless: describe systems and processes, never individual mistakes.
5. Remove personal data before saving: account numbers, id numbers, phone numbers, e-mails, customer names,
   tokens. Use masked values from `context.json` only.
6. Lessons: name the skill or checklist to update (for example a new fintech-review item). If this `category`
   has happened 2–3 times, propose a checklist item.

Taxonomy (`category`): `idempotency` · `concurrency/race` · `timeout/retry-storm` · `config` · `deployment` ·
`dependency-external` · `data-quality` · `schema/migration` · `capacity` · `precision/rounding` ·
`time/timezone/calendar` · `security/auth` · `observability-gap`

## Output
`<paths.work>/<INCIDENT-ID>-<slug>/drafts/postmortem.md`. Postmortems are not promoted into this repo: after
human review and PII cleaning, the human opens a PR to the knowledge repo (`knowledge.repo`).
