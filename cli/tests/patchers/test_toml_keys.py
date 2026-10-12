"""Contract tests C45: kuanflow_cli.patchers.toml_keys (tomlkit)."""

from __future__ import annotations

import hashlib
import importlib
import json
import tomllib
from types import ModuleType
from typing import Any

import pytest

ODD_DOC = """\
# Top comment — keep me
title   =   "odd"    # trailing comment
numbers = [ 1,2 ,
    3, # inside array
]

[server]
  host = 'localhost'
  port=8080

# comment between tables


[server.tls]   # table comment
enabled = false
inline = { a = 1, b = "two" }

[[plugins]]
name = "first"

[[plugins]]
name = "second"
"""


@pytest.fixture
def tk() -> ModuleType:
    return importlib.import_module("kuanflow_cli.patchers.toml_keys")


@pytest.fixture
def jk() -> ModuleType:
    return importlib.import_module("kuanflow_cli.patchers.json_keys")


@pytest.fixture
def errors() -> ModuleType:
    return importlib.import_module("kuanflow_cli.errors")


def canon_sha(value: Any) -> str:
    canon = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --- merge --------------------------------------------------------------------------------------


def test_c45_merge_empty_is_byte_identical(tk: ModuleType) -> None:
    assert tk.merge(ODD_DOC, {}) == ODD_DOC
    no_nl = "a = 1 # c"
    assert tk.merge(no_nl, {}) == no_nl


@pytest.mark.parametrize("text", [None, ""])
def test_c45_merge_into_no_file(tk: ModuleType, text: str | None) -> None:
    out = tk.merge(text, {"a.b": 1, "a.c": ["x", "é"], "top": "v"})
    assert tomllib.loads(out) == {"a": {"b": 1, "c": ["x", "é"]}, "top": "v"}


def test_c45_dotted_key_is_key_in_table(tk: ModuleType) -> None:
    out = tk.merge("", {"tool.kuanflow.enabled": True})
    assert tomllib.loads(out) == {"tool": {"kuanflow": {"enabled": True}}}


def test_c45_merge_preserves_untouched_parts(tk: ModuleType) -> None:
    out = tk.merge(ODD_DOC, {"server.tls.enabled": True, "kuanflow.hooks": ["guard"]})
    data = tomllib.loads(out)
    assert data["server"]["tls"]["enabled"] is True
    assert data["server"]["tls"]["inline"] == {"a": 1, "b": "two"}
    assert data["kuanflow"] == {"hooks": ["guard"]}
    assert data["title"] == "odd"
    assert [p["name"] for p in data["plugins"]] == ["first", "second"]
    head = ODD_DOC[: ODD_DOC.index("[server.tls]")]
    assert out.startswith(head)  # comments, spacing and order before the touched table unchanged
    assert "[server.tls]   # table comment\n" in out
    assert 'inline = { a = 1, b = "two" }\n' in out
    assert out.index("[server]") < out.index("[server.tls]") < out.index("[[plugins]]")


def test_c45_merge_replaces_value_whole(tk: ModuleType) -> None:
    text = "[t]\nlist = [1, 2, 3]\nsub = { keep = 1 }\nother = 'x' # keep\n"
    out = tk.merge(text, {"t.list": [9], "t.sub": {"new": 2}})
    assert tomllib.loads(out) == {"t": {"list": [9], "sub": {"new": 2}, "other": "x"}}
    assert "other = 'x' # keep\n" in out


@pytest.mark.parametrize(
    ("text", "key"),
    [("a = 1\n", "a.b"), ("a = [1]\n", "a.b"), ("[a]\nb = 's'\n", "a.b.c")],
)
def test_c45_non_table_intermediate_is_error(
    tk: ModuleType, errors: ModuleType, text: str, key: str
) -> None:
    with pytest.raises(errors.KeysError):
        tk.merge(text, {key: 1})


@pytest.mark.parametrize("text", ["a = = 1\n", "[x\n", "a = 1\na = 2\n", "= 3\n"])
def test_c45_parse_error_is_keys_error(tk: ModuleType, errors: ModuleType, text: str) -> None:
    with pytest.raises(errors.KeysError):
        tk.merge(text, {"k": 1})
    with pytest.raises(errors.KeysError):
        tk.remove(text, ["k"])


# --- remove -------------------------------------------------------------------------------------


def test_c45_remove_keys_and_empty_tables(tk: ModuleType) -> None:
    text = "# head\nkeep = 1\n\n[kf]\nx = 1\n\n[other]\ny = 2 # note\n"
    out = tk.remove(text, ["kf.x"])
    data = tomllib.loads(out)
    assert data == {"keep": 1, "other": {"y": 2}}
    assert out.startswith("# head\nkeep = 1\n")
    assert "y = 2 # note\n" in out


def test_c45_remove_missing_keys_ignored(tk: ModuleType) -> None:
    assert tk.remove(ODD_DOC, ["nope", "server.nope", "x.y.z"]) == ODD_DOC


# --- round trip ---------------------------------------------------------------------------------

PYPROJECT_LIKE = """\
[project]
name = "demo"   # the name
version = "0.1.0"
dependencies = [
  "requests>=2",
]

# Lint settings
[tool.ruff]
line-length = 100
"""

ROUND_TRIP_DOCS = [
    "",
    "a = 1\n",
    "# only a comment\n",
    ODD_DOC,
    PYPROJECT_LIKE,
]

MANAGED_SETS: list[dict[str, Any]] = [
    {"kuanflow.enabled": True},
    {"kuanflow.hooks": ["a", "b"], "kuanflow.level": 3},
    {"kuanflow.meta.version": "0.4.0", "kuanflow.meta.name": "é"},
    {"mcp_servers.kuanflow.command": "kuanflow", "mcp_servers.kuanflow.args": ["serve"]},
]


@pytest.mark.parametrize("doc", ROUND_TRIP_DOCS, ids=["empty", "scalar", "comment", "odd", "py"])
@pytest.mark.parametrize("managed", MANAGED_SETS, ids=["one", "two", "nested", "codex-like"])
def test_c45_round_trip(tk: ModuleType, doc: str, managed: dict[str, Any]) -> None:
    merged = tk.merge(doc, managed)
    data = tomllib.loads(merged)
    for key, value in managed.items():
        node: Any = data
        for seg in key.split("."):
            node = node[seg]
        assert node == value
    assert tk.remove(merged, managed.keys()) == doc


# --- values_sha ---------------------------------------------------------------------------------


def test_c45_values_sha_matches_json_canonical_form(tk: ModuleType, jk: ModuleType) -> None:
    toml_text = (
        "[p]\n"
        "deny = ['a', 'b']\n"
        "n = 1\n"
        "flag = true\n"
        "t = { y = 'é', x = [1, 2] }\n"
        "[p.sub]\n"
        "z = 'last'\n"
        "a = 0.5\n"
    )
    plain = {
        "p": {
            "deny": ["a", "b"],
            "n": 1,
            "flag": True,
            "t": {"y": "é", "x": [1, 2]},
            "sub": {"z": "last", "a": 0.5},
        }
    }
    keys = ["p.deny", "p.n", "p.flag", "p.t", "p.sub", "p.missing", "nope.x"]
    got = tk.values_sha(toml_text, keys)
    assert got == jk.values_sha(json.dumps(plain), keys)
    assert got["p.t"] == canon_sha({"x": [1, 2], "y": "é"})
    assert got["p.sub"] == canon_sha({"a": 0.5, "z": "last"})
    assert got["p.missing"] is None
    assert got["nope.x"] is None
