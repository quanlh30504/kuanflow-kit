"""Contract tests C40: kuanflow_cli.manifest.

Assumptions (the contract pins the JSON, not the constructor API):
- ``Manifest`` and ``FileEntry`` are dataclasses whose field names equal the JSON keys
  (``manifest_version``, ``kuanflow_version``, ``template``, ``installed_at``, ``updated_at``,
  ``mode``, ``agents``, ``source``, ``files`` / ``path``, ``owner``, ``sha256``, ``block``,
  ``keys``, ``created``, ``agent``); optional ones (``updated_at`` and the owner-specific entry
  fields) default to ``None``, and ``manifest_version`` defaults to 1.
- ``source`` defaults (when not passed to ``Manifest``) to ``KUANFLOW_SOURCE`` (else
  ``git+https://github.com/<org>/kuanflow.git``) + ``@v<kuanflow_version>``.
Most tests therefore go through ``read()`` / ``dumps()`` on JSON written here.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64

FILES: list[dict[str, Any]] = [
    {"path": ".copier-answers.yml", "owner": "template-managed", "sha256": SHA_A},
    {"path": ".gitignore", "owner": "managed-block", "block": "kuanflow", "sha256": SHA_B,
     "created": False},
    {"path": ".kuanflow/config.yaml", "owner": "merge-required", "sha256": SHA_C},
    {"path": "AGENTS.md", "owner": "managed-block", "block": "kuanflow", "sha256": SHA_D,
     "created": True},
    {"path": "docs/adr/0000-template.md", "owner": "local-owned", "sha256": SHA_A},
    {"path": "docs/ghi-chú.md", "owner": "local-owned", "sha256": SHA_B},
    {"path": "git:info/exclude", "owner": "managed-block", "block": "kuanflow", "sha256": SHA_C,
     "created": False},
    {"path": "z/.claude/settings.json", "owner": "managed-keys",
     "keys": {"permissions.deny": SHA_D, "hooks.PreToolUse": SHA_A}, "created": True,
     "agent": "claude"},
]  # fmt: skip

TOP: dict[str, Any] = {
    "manifest_version": 1,
    "kuanflow_version": "0.4.0-dev",
    "template": "project",
    "installed_at": "2026-11-03T09:00:00+07:00",
    "updated_at": "2026-11-04T10:00:00+07:00",
    "mode": "project",
    "agents": [],
    "source": "git+https://github.com/<org>/kuanflow.git@v0.4.0-dev",
}
TOP_ORDER = [*TOP, "files"]
ENTRY_ORDER = {
    "template-managed": ["path", "owner", "sha256"],
    "merge-required": ["path", "owner", "sha256"],
    "local-owned": ["path", "owner", "sha256"],
    "managed-block": ["path", "owner", "block", "sha256", "created"],
    "managed-keys": ["path", "owner", "keys", "created"],
}


def mod() -> ModuleType:
    return importlib.import_module("kuanflow_cli.manifest")


def manifest_error() -> type[Exception]:
    return importlib.import_module("kuanflow_cli.errors").ManifestError


def canonical(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def doc(**over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {**TOP, "files": [dict(f) for f in FILES]}
    for k, v in over.items():
        if v is _DROP:
            data.pop(k, None)
        else:
            data[k] = v
    return data


_DROP = object()


def put(root: Path, text: str) -> Path:
    p = root / ".kuanflow" / "manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return root


def load(root: Path, data: dict[str, Any] | str) -> Any:
    text = data if isinstance(data, str) else canonical(data)
    return mod().read(put(root, text))


# --- read / dumps ------------------------------------------------------------------------------


def test_canonical_round_trips_byte_identical(tmp_path: Path) -> None:
    text = canonical(doc())
    m = load(tmp_path, text)
    assert mod().dumps(m) == text


def test_dumps_format(tmp_path: Path) -> None:
    out = mod().dumps(load(tmp_path, doc()))
    assert out.endswith("}\n") and not out.endswith("\n\n")
    assert '\n  "manifest_version": 1,' in out  # indent 2
    assert "docs/ghi-chú.md" in out  # ensure_ascii=False
    assert "\\u" not in out


def test_top_level_key_order(tmp_path: Path) -> None:
    shuffled = dict(reversed(list(doc().items())))
    out = mod().dumps(load(tmp_path, shuffled))
    assert list(json.loads(out)) == TOP_ORDER
    assert out == canonical(doc())


def test_entry_field_order_per_owner(tmp_path: Path) -> None:
    files = [dict(reversed(list(f.items()))) for f in FILES]
    out = mod().dumps(load(tmp_path, doc(files=files)))
    for entry in json.loads(out)["files"]:
        order = ENTRY_ORDER[entry["owner"]]
        expected = [*order, "agent"] if "agent" in entry else order
        assert list(entry) == expected, entry
    assert out == canonical(doc())


def test_files_sorted_by_path(tmp_path: Path) -> None:
    out = mod().dumps(load(tmp_path, doc(files=list(reversed(FILES)))))
    paths = [f["path"] for f in json.loads(out)["files"]]
    assert paths == sorted(paths)
    assert out == canonical(doc())


def test_files_sorted_when_constructed() -> None:
    m = mod()
    entries = [
        m.FileEntry(path="b.txt", owner="template-managed", sha256=SHA_A),
        m.FileEntry(path="a.txt", owner="local-owned", sha256=SHA_B),
    ]
    man = m.Manifest(
        manifest_version=1,
        kuanflow_version="0.4.0-dev",
        template="project",
        installed_at="2026-11-03T09:00:00+07:00",
        mode="project",
        agents=[],
        source="s@v0.4.0-dev",
        files=entries,
    )
    data = json.loads(m.dumps(man))
    assert [f["path"] for f in data["files"]] == ["a.txt", "b.txt"]
    assert data["files"][0] == {"path": "a.txt", "owner": "local-owned", "sha256": SHA_B}


def test_updated_at_optional(tmp_path: Path) -> None:
    data = doc(updated_at=_DROP)
    m = load(tmp_path, data)
    assert m.updated_at is None
    out = mod().dumps(m)
    assert "updated_at" not in out
    assert out == canonical(data)
    assert list(json.loads(out)) == [k for k in TOP_ORDER if k != "updated_at"]


def test_agents_and_personal_mode(tmp_path: Path) -> None:
    data = doc(mode="personal", agents=["claude", "codex"])
    assert mod().dumps(load(tmp_path, data)) == canonical(data)


def test_knowledge_repo_template(tmp_path: Path) -> None:
    data = doc(template="knowledge-repo", files=[dict(FILES[0])])
    assert mod().dumps(load(tmp_path, data)) == canonical(data)


def test_dumps_deterministic(tmp_path: Path) -> None:
    m = load(tmp_path, doc())
    assert mod().dumps(m) == mod().dumps(m)


# --- read: absent / errors ---------------------------------------------------------------------


def test_read_absent(tmp_path: Path) -> None:
    assert mod().read(tmp_path) is None
    (tmp_path / ".kuanflow").mkdir()
    assert mod().read(tmp_path) is None


@pytest.mark.parametrize(
    "text",
    ["", "{", "not json\n", '{"manifest_version": 1,}\n'],
    ids=["empty", "truncated", "garbage", "trailing-comma"],
)
def test_invalid_json(tmp_path: Path, text: str) -> None:
    with pytest.raises(manifest_error()):
        load(tmp_path, text)


@pytest.mark.parametrize("text", ["[]\n", '"x"\n', "1\n", "null\n"])
def test_not_an_object(tmp_path: Path, text: str) -> None:
    with pytest.raises(manifest_error()):
        load(tmp_path, text)


@pytest.mark.parametrize("version", [0, 2, "1", None])
def test_manifest_version(tmp_path: Path, version: Any) -> None:
    with pytest.raises(manifest_error()):
        load(tmp_path, doc(manifest_version=version))


@pytest.mark.parametrize("key", [k for k in TOP_ORDER if k != "updated_at"])
def test_missing_field(tmp_path: Path, key: str) -> None:
    with pytest.raises(manifest_error()):
        load(tmp_path, doc(**{key: _DROP}))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("kuanflow_version", 4),
        ("template", None),
        ("installed_at", 20261103),
        ("updated_at", 1),
        ("mode", ["project"]),
        ("agents", "claude"),
        ("agents", [1]),
        ("source", {}),
        ("files", {}),
        ("files", ["a.txt"]),
    ],
)
def test_mistyped_field(tmp_path: Path, key: str, value: Any) -> None:
    with pytest.raises(manifest_error()):
        load(tmp_path, doc(**{key: value}))


@pytest.mark.parametrize(
    "entry",
    [
        {"owner": "template-managed", "sha256": SHA_A},
        {"path": "a", "sha256": SHA_A},
        {"path": "a", "owner": "template-managed"},
        {"path": 1, "owner": "template-managed", "sha256": SHA_A},
        {"path": "a", "owner": "template-managed", "sha256": 5},
        {"path": "a", "owner": "managed-block", "sha256": SHA_A, "created": True},
        {"path": "a", "owner": "managed-block", "block": "kuanflow", "sha256": SHA_A},
        {"path": "a", "owner": "managed-block", "block": "kuanflow", "sha256": SHA_A,
         "created": "yes"},
        {"path": "a", "owner": "managed-keys", "created": True},
        {"path": "a", "owner": "managed-keys", "keys": ["x"], "created": True},
    ],
    ids=[
        "no-path", "no-owner", "no-sha", "path-int", "sha-int", "block-no-block",
        "block-no-created", "block-created-str", "keys-no-keys", "keys-list",
    ],
)  # fmt: skip
def test_bad_entry(tmp_path: Path, entry: dict[str, Any]) -> None:
    with pytest.raises(manifest_error()):
        load(tmp_path, doc(files=[entry]))


@pytest.mark.parametrize("owner", ["foo", "Template-Managed", "", None])
def test_unknown_owner(tmp_path: Path, owner: Any) -> None:
    entry = {"path": "a", "owner": owner, "sha256": SHA_A}
    with pytest.raises(manifest_error()):
        load(tmp_path, doc(files=[entry]))


# --- write / round trip ------------------------------------------------------------------------


def test_write_bytes_and_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "src"
    m = load(src, doc())
    dst = tmp_path / "dst"
    (dst / ".kuanflow").mkdir(parents=True)
    mod().write(dst, m)
    raw = (dst / ".kuanflow" / "manifest.json").read_bytes()
    assert raw == mod().dumps(m).encode("utf-8")
    assert raw == canonical(doc()).encode("utf-8")
    again = mod().read(dst)
    assert again == m
    assert mod().dumps(again) == mod().dumps(m)


def test_write_constructed_round_trips(tmp_path: Path) -> None:
    m = mod()
    man = m.Manifest(
        manifest_version=1,
        kuanflow_version="0.4.0-dev",
        template="project",
        installed_at="2026-11-03T09:00:00+07:00",
        mode="project",
        agents=[],
        source="git+https://example/k.git@v0.4.0-dev",
        files=[
            m.FileEntry(path="AGENTS.md", owner="managed-block", block="kuanflow",
                        sha256=SHA_A, created=True),
            m.FileEntry(path=".kuanflow/config.yaml", owner="merge-required", sha256=SHA_B),
        ],
    )  # fmt: skip
    (tmp_path / ".kuanflow").mkdir()
    m.write(tmp_path, man)
    back = m.read(tmp_path)
    assert m.dumps(back) == m.dumps(man)
    data = json.loads((tmp_path / ".kuanflow" / "manifest.json").read_text(encoding="utf-8"))
    assert "updated_at" not in data
    assert data["files"] == [
        {"path": ".kuanflow/config.yaml", "owner": "merge-required", "sha256": SHA_B},
        {"path": "AGENTS.md", "owner": "managed-block", "block": "kuanflow", "sha256": SHA_A,
         "created": True},
    ]  # fmt: skip


# --- source ------------------------------------------------------------------------------------


def _bare(version: str) -> Any:
    m = mod()
    return m.Manifest(
        kuanflow_version=version,
        template="project",
        installed_at="2026-11-03T09:00:00+07:00",
        mode="project",
        agents=[],
        files=[],
    )


def test_source_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUANFLOW_SOURCE", "git+https://git.example.com/acme/kuanflow.git")
    data = json.loads(mod().dumps(_bare("0.4.0-dev")))
    assert data["source"] == "git+https://git.example.com/acme/kuanflow.git@v0.4.0-dev"
    assert data["manifest_version"] == 1


def test_source_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KUANFLOW_SOURCE", raising=False)
    data = json.loads(mod().dumps(_bare("1.2.3")))
    assert data["source"] == "git+https://github.com/<org>/kuanflow.git@v1.2.3"


def test_source_read_is_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUANFLOW_SOURCE", "git+https://elsewhere/k.git")
    m = load(tmp_path, doc())
    assert json.loads(mod().dumps(m))["source"] == TOP["source"]


# --- sha256_bytes / diff -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [b"", b"hello\n", "Dịch vụ\n".encode(), bytes(range(256))],
    ids=["empty", "ascii", "utf8", "all-bytes"],
)
def test_sha256_bytes(data: bytes) -> None:
    assert mod().sha256_bytes(data) == hashlib.sha256(data).hexdigest()


def test_diff(tmp_path: Path) -> None:
    old_files = [
        {"path": "keep.txt", "owner": "template-managed", "sha256": SHA_A},
        {"path": "gone-b.txt", "owner": "template-managed", "sha256": SHA_A},
        {"path": "gone-a.txt", "owner": "local-owned", "sha256": SHA_A},
        {"path": "sha.txt", "owner": "template-managed", "sha256": SHA_A},
        {"path": "owner.txt", "owner": "template-managed", "sha256": SHA_A},
        {"path": "AGENTS.md", "owner": "managed-block", "block": "kuanflow", "sha256": SHA_A,
         "created": True},
    ]  # fmt: skip
    new_files = [
        {"path": "keep.txt", "owner": "template-managed", "sha256": SHA_A},
        {"path": "new-z.txt", "owner": "template-managed", "sha256": SHA_B},
        {"path": "new-a.txt", "owner": "merge-required", "sha256": SHA_B},
        {"path": "sha.txt", "owner": "template-managed", "sha256": SHA_B},
        {"path": "owner.txt", "owner": "merge-required", "sha256": SHA_A},
        {"path": "AGENTS.md", "owner": "managed-block", "block": "kuanflow", "sha256": SHA_B,
         "created": True},
    ]  # fmt: skip
    old = load(tmp_path / "old", doc(files=old_files))
    new = load(tmp_path / "new", doc(files=new_files, updated_at="2026-11-05T00:00:00+07:00"))
    assert mod().diff(old, new) == {
        "added": ["new-a.txt", "new-z.txt"],
        "removed": ["gone-a.txt", "gone-b.txt"],
        "changed": ["AGENTS.md", "owner.txt", "sha.txt"],
    }


def test_diff_identical(tmp_path: Path) -> None:
    a = load(tmp_path / "a", doc())
    b = load(tmp_path / "b", doc())
    assert mod().diff(a, b) == {"added": [], "removed": [], "changed": []}
