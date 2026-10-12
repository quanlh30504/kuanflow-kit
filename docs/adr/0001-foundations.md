# ADR-0001: Foundations

- Status: Proposed
- Date: 2026-10-12
- Context: phase P1 (KF-002), spike S2; answers Q-02, Q-03, Q-06 in
  `kuan-workbench/work/KF-000-analysis/questions.md`.

## Context

`docs/packaging.md` (PKG) §4 puts the CLI in `cli/` with `cli/pyproject.toml`, while PKG §9.2 shows an install
command that assumes a root `pyproject.toml`. A wheel built from `cli/` does not naturally contain `plugins/` or
`templates/`. Plugin manifests need SemVer, Python packaging needs PEP 440. PKG §18.2 says `requires-python >=3.10`.

## Decisions

1. **Python >= 3.11** (Q-02). Overrides PKG §18.2 (`>=3.10`). Gives `tomllib`, modern typing, and matches the
   supported range of current Copier/Typer.
2. **One version source: repo-root `VERSION`, SemVer 2.0** (Q-03), e.g. `0.1.0-dev`. Python package metadata is
   derived at build time and mapped to PEP 440:

   | SemVer | PEP 440 |
   |---|---|
   | `X.Y.Z` | `X.Y.Z` |
   | `X.Y.Z-dev` / `-dev.N` | `X.Y.Z.dev0` / `X.Y.Z.devN` |
   | `X.Y.Z-alpha.N` (`-a.N`) / `-beta.N` (`-b.N`) / `-rc.N` | `X.Y.ZaN` / `X.Y.ZbN` / `X.Y.ZrcN` |

   No leading zeros in `X`, `Y`, `Z` or `N`. Build metadata (`+…`), bare `-rc`/`-alpha`/`-beta` and any other
   pre-release form are rejected. The table lives in exactly one place, `cli/semver_pep440.py` (stdlib only,
   contract C9); both the build and the release gate `tests/check_versions.py` load it by file path, so they
   cannot disagree. Implementation: a hatchling **metadata hook**
   (`cli/hatch_build.py`, `[tool.hatch.metadata.hooks.custom]`). At runtime `kuanflow_cli.__version__` =
   `importlib.metadata.version("kuanflow-cli")`, so `kuanflow --version` always reports the installed metadata.
   `[tool.uv] cache-keys` includes `../VERSION`, so `uv run` rebuilds the editable install after a bump.
3. **`pyproject.toml` stays in `cli/`; content is bundled into the wheel; install URL uses
   `#subdirectory=cli`** (Q-06, option A). A hatchling **build hook** (same file) force-includes:
   - wheel: `../plugins/kuanflow` -> `kuanflow_cli/_content/plugins/kuanflow`,
     `../templates` -> `kuanflow_cli/_content/templates`;
   - sdist: `../VERSION`, `../plugins/kuanflow`, `../templates` copied to the sdist root, so a wheel built from the
     sdist (what `uv build` does) is identical. The hooks look for `VERSION` in `<cli>` first (unpacked sdist), then `<cli>/..` (repo checkout), so a stray
     `VERSION` above an unpacked sdist is ignored.
   - editable wheel: nothing bundled (content is read from the checkout).

   Install command: `uvx --from "git+https://github.com/<org>/kuanflow.git@vX.Y.Z#subdirectory=cli" kuanflow`
   (or `uv tool install` with the same spec). README/PKG §9.2 must use this form.
4. **Runtime content lookup** (documented here, implemented later): first
   `importlib.resources.files("kuanflow_cli") / "_content"` (wheel / uvx / tool install); if absent, the repo
   checkout `Path(kuanflow_cli.__file__).parents[3]` (`src/kuanflow_cli` -> `cli/src` -> `cli` -> repo root), which
   holds `plugins/kuanflow` and `templates` (editable / `uv run --project cli`). A single locator function owns
   this; nothing else hard-codes paths.
5. **Old-version content for upgrades** (decided, implemented in P6): the 3-way merge base is fetched from
   `manifest.source` at the old tag into `.kuanflow/cache/sources/<ver>/` (git; `file://` in tests). The wheel
   only ever carries the *current* version's content.
6. **Root tool config**: `ruff.toml` (py311, line-length 100, rules E/F/I/UP/B; Markdown code blocks are not
   formatted) and `pytest.ini` (`testpaths = cli/tests tests`). Everything runs from the repo root via
   `uv run --project cli ...`.

## Evidence (S2)

Run on 2026-10-12 with an uncommitted `VERSION` = `0.1.0-dev` (owned by T1.3) and temporary
`MARKER.txt` files under `plugins/kuanflow/skills/` and `templates/project/` (not committed).

**Editable / dev mode**

```
$ cd cli && uv sync          # ... + typer==0.27.3 ...
$ uv run --project cli kuanflow --version
kuanflow 0.1.0.dev0
$ printf '0.1.0-rc.1\n' > VERSION && uv run --project cli kuanflow --version
   Built kuanflow-cli @ file:///.../cli          # cache-key on ../VERSION triggers rebuild
kuanflow 0.1.0rc1
$ uv run --project cli python -c "import kuanflow_cli; print(kuanflow_cli.__file__)"
.../cli/src/kuanflow_cli/__init__.py            # site-packages holds only _editable_impl_kuanflow_cli.pth
```

**`uv build` (sdist, then wheel from sdist)**

```
$ cd cli && uv build
Building source distribution...
Building wheel from source distribution...
Successfully built dist/kuanflow_cli-0.1.0.dev0.tar.gz
Successfully built dist/kuanflow_cli-0.1.0.dev0-py3-none-any.whl
$ python3 -m zipfile -l dist/kuanflow_cli-0.1.0.dev0-py3-none-any.whl
kuanflow_cli/__init__.py
kuanflow_cli/main.py
kuanflow_cli/{adapters,migrations,patchers}/__init__.py
kuanflow_cli/_content/templates/knowledge-repo/.gitkeep
kuanflow_cli/_content/templates/project/.gitkeep
kuanflow_cli/_content/templates/project/MARKER.txt
kuanflow_cli/_content/plugins/kuanflow/{.claude-plugin,agents,commands,hooks,scripts,skills}/.gitkeep
kuanflow_cli/_content/plugins/kuanflow/skills/MARKER.txt
kuanflow_cli-0.1.0.dev0.dist-info/{METADATA,WHEEL,entry_points.txt,RECORD}
$ tar tzf dist/kuanflow_cli-0.1.0.dev0.tar.gz   # VERSION, hatch_build.py, pyproject.toml, src/, plugins/, templates/
$ uvx --python 3.11 --from ./cli/dist/kuanflow_cli-0.1.0.dev0-py3-none-any.whl kuanflow --version
kuanflow 0.1.0.dev0
```

**Install from a git URL with `#subdirectory=cli`**

1. Branch commit `57c702d` (the P1 commit minus this ADR; no `VERSION` yet):

   ```
   $ uvx --from "git+file://<worktree>@57c702d#subdirectory=cli" kuanflow --version
     x The build backend returned an error
   (-v) FileNotFoundError: VERSION not found in ~/.cache/uv/git-v0/checkouts/<id>/57c702d or .../57c702d/cli
   ```

   Expected until T1.3 adds `VERSION`. It also proves that uv checks out the **whole repository** and builds in
   the `cli/` subdirectory, so `../VERSION`, `../plugins`, `../templates` are reachable.
2. Throw-away clone of the branch + one commit adding `VERSION` and a marker (`b2b05a8`, tagged `v0.1.0-dev`):

   ```
   $ uvx --from "git+file://<scratch>/s2proof@b2b05a8#subdirectory=cli" kuanflow --version
         Built kuanflow-cli @ git+file://<scratch>/s2proof@b2b05a8...#subdirectory=cli
   kuanflow 0.1.0.dev0
   $ uvx --from "git+file://<scratch>/s2proof@v0.1.0-dev#subdirectory=cli" kuanflow --version
   kuanflow 0.1.0.dev0
   $ uvx --python 3.11 --from "git+file://...@b2b05a8#subdirectory=cli" python -c \
       "...files('kuanflow_cli')/'_content'..."
   3.11.15 ['plugins', 'templates'] True        # _content present, marker bundled
   ```

   Network: PyPI only, for dependency resolution (served from the local uv cache after the first run).
   No alternative to `git+file` + `#subdirectory` was needed.

**Verdict: S2 passes.** Option A works for `uv sync`/`uv run`, `uv build`, wheel install, and git-URL install
(commit and tag refs) on Python 3.11 and 3.13.

## Tool versions (verified 2026-10-12)

| Tool | Version |
|---|---|
| Python (system / uv-managed venv / 3.11 check) | 3.12.3 / 3.13.5 / 3.11.15 |
| uv | 0.11.21 |
| hatchling | 1.32.4 |
| copier | 9.18.2 |
| typer | 0.27.3 |
| pyyaml / tomlkit / rich / jsonschema | 6.0.3 / 0.15.1 / 15.0.0 / 4.26.0 |
| pytest / pytest-cov / ruff | 9.1.1 / 7.1.0 / 0.17.0 |
| Claude Code (`claude --version`) | 2.1.296 |
| Codex (`codex --version`) | codex-cli 0.162.1 |
| OpenCode (`opencode --version`) | v2.0.19 |
| Kiro (`kiro-cli --version`) | 2.29.0 |
| Bats (`bats --version`) | 1.10.0 |

Lower bounds in `cli/pyproject.toml` follow the resolved versions (`copier>=9.18.2,<10` per ADR-0002, `typer>=0.27`, `pyyaml>=6.0`,
`tomlkit>=0.15`, `rich>=15.0`, `jsonschema>=4.26`); `cli/uv.lock` pins the exact set.

## Consequences

- Every build needs `VERSION` reachable (repo checkout or sdist). A tree without it fails loudly at build time.
- Docs and README must show `#subdirectory=cli` in install commands; PKG §9.2's root-level form is superseded.
- Wheels carry only the current content; upgrades fetch older content via `manifest.source` (P6), which needs
  git access to the source repo (or `file://` mirrors offline).
- Editable installs never contain `_content`; the runtime locator must support both modes (decision 4) and is
  tested in both when implemented.
- `kuanflow --version` reflects installed metadata: after a `VERSION` bump outside `uv run`, re-sync is required.
- `check_versions.py` (T1.3) imports the same converter (`cli/semver_pep440.py`), so a version the gate
  accepts is a version the package can build.
- TODO(verify): `build-system requires hatchling>=1.27` — only 1.30–1.32 were observed; the lower bound is untested.
