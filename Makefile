UV_RUN := uv run --locked --project cli

.PHONY: verify test lint fmt

# Full gate (contract C7); each step is its own recipe line so the first failure stops make.
verify:
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .
	$(UV_RUN) pytest -q
	bats tests/bats
	$(UV_RUN) python tests/check_skills.py plugins/kuanflow
	$(UV_RUN) python tests/check_versions.py

test:
	$(UV_RUN) pytest -q
	bats tests/bats

lint:
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .

fmt:
	$(UV_RUN) ruff check --fix .
	$(UV_RUN) ruff format .
