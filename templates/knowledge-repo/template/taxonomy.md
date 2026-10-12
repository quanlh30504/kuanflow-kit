# Incident taxonomy

Every postmortem sets `category` to exactly one of the categories below. A shared category is what
lets us count repeat incidents and turn them into checklists. `scripts/check-frontmatter.py` reads
this list, so it is the single source of truth.

To add a category, open a pull request that changes this list and explains why no existing
category fits.

## Categories

- `idempotency`
- `concurrency/race`
- `timeout/retry-storm`
- `config`
- `deployment`
- `dependency-external`
- `data-quality`
- `schema/migration`
- `capacity`
- `precision/rounding`
- `time/timezone/calendar`
- `security/auth`
- `observability-gap`
