# Postmortems

One file per incident: `postmortems/<year>/<id>-<slug>.md`, for example
`postmortems/2026/INC-0042-order-retry-duplicate.md`. Start from `templates/postmortem.md`.

Required frontmatter (checked by `scripts/check-frontmatter.py` in CI):

| Key | Rule |
|---|---|
| `id` | Non-empty string, for example `INC-0042` |
| `services` | Non-empty list of service names |
| `category` | One category from `taxonomy.md` |
| `signatures` | Non-empty list of exact error strings, so the incident can be found with grep |
| `status` | `draft` or `approved` |

An agent may draft a postmortem; a person approves it. After approval the file is immutable except
for its action items. Write it blameless and without personal data.
