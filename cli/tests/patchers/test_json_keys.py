"""Contract tests C44: kuanflow_cli.patchers.json_keys."""

from __future__ import annotations

import hashlib
import importlib
import json
import random
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def jk() -> ModuleType:
    return importlib.import_module("kuanflow_cli.patchers.json_keys")


@pytest.fixture
def errors() -> ModuleType:
    return importlib.import_module("kuanflow_cli.errors")


def dump(obj: Any, indent: int | str = 2) -> str:
    return json.dumps(obj, indent=indent, ensure_ascii=False) + "\n"


def canon_sha(value: Any) -> str:
    canon = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --- merge --------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", [None, ""])
def test_c44_merge_into_no_file(jk: ModuleType, text: str | None) -> None:
    assert jk.merge(text, {"a": 1, "b": "é"}) == dump({"a": 1, "b": "é"})
    assert jk.merge(text, {}) == "{}\n"


def test_c44_merge_into_existing(jk: ModuleType) -> None:
    text = dump({"x": 1})
    assert jk.merge(text, {"y": [1, 2]}) == dump({"x": 1, "y": [1, 2]})


def test_c44_dotted_key_creates_parents(jk: ModuleType) -> None:
    out = jk.merge(None, {"permissions.deny": ["Bash(rm:*)"], "a.b.c": True})
    assert out == dump({"permissions": {"deny": ["Bash(rm:*)"]}, "a": {"b": {"c": True}}})


def test_c44_dotted_key_into_existing_parent(jk: ModuleType) -> None:
    text = dump({"permissions": {"allow": ["Read"], "ask": []}, "z": 0})
    out = jk.merge(text, {"permissions.deny": ["Write"]})
    assert out == dump({"permissions": {"allow": ["Read"], "ask": [], "deny": ["Write"]}, "z": 0})


@pytest.mark.parametrize(
    ("doc", "key"),
    [
        ({"a": 1}, "a.b"),
        ({"a": [1]}, "a.b"),
        ({"a": "s"}, "a.b.c"),
        ({"a": {"b": None}}, "a.b.c"),
    ],
)
def test_c44_non_object_intermediate_is_error(
    jk: ModuleType, errors: ModuleType, doc: dict[str, Any], key: str
) -> None:
    with pytest.raises(errors.KeysError):
        jk.merge(dump(doc), {key: 1})


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "not json",
        '{"a": 1,}',
        '{\n  // comment\n  "a": 1\n}\n',
        '{\n  /* block */ "a": 1\n}\n',
        "[1, 2]\n",
        "null\n",
        '"string"\n',
        "3\n",
    ],
    ids=[
        "truncated",
        "garbage",
        "trailing-comma",
        "jsonc-line",
        "jsonc-block",
        "array",
        "null",
        "str",
        "num",
    ],
)
def test_c44_invalid_or_non_object_is_error(jk: ModuleType, errors: ModuleType, text: str) -> None:
    with pytest.raises(errors.KeysError):
        jk.merge(text, {"a": 1})


def test_c44_key_order_preserved_new_keys_appended(jk: ModuleType) -> None:
    text = '{\n  "z": 1,\n  "a": 2,\n  "m": {"q": 1, "b": 2}\n}\n'
    out = jk.merge(text, {"new": 3, "a": 9, "m.c": 4, "m.q": 0})
    assert out == dump({"z": 1, "a": 9, "m": {"q": 0, "b": 2, "c": 4}, "new": 3})
    assert list(json.loads(out)) == ["z", "a", "m", "new"]


@pytest.mark.parametrize(
    ("text", "indent"),
    [
        (dump({"a": {"b": 1}}, 2), 2),
        (dump({"a": {"b": 1}}, 4), 4),
        (dump({"a": {"b": 1}}, 3), 3),
        (dump({"a": {"b": 1}}, "\t"), "\t"),
        ('{"a": {"b": 1}}', 2),
        ('{"a": {"b": 1}}\n', 2),
        ("{}", 2),
    ],
    ids=["two", "four", "three", "tab", "minified", "minified-nl", "empty"],
)
def test_c44_indent_detection(jk: ModuleType, text: str, indent: int | str) -> None:
    out = jk.merge(text, {"k": [1]})
    expected = json.loads(text)
    expected["k"] = [1]
    assert out == dump(expected, indent)


def test_c44_values_replaced_whole(jk: ModuleType) -> None:
    text = dump({"list": [1, 2, 3], "obj": {"keep": 1}})
    out = jk.merge(text, {"list": [9], "obj": {"new": 2}})
    assert out == dump({"list": [9], "obj": {"new": 2}})


def test_c44_non_ascii_written_literally(jk: ModuleType) -> None:
    out = jk.merge(None, {"name": "Quân — ✓"})
    assert "Quân — ✓" in out
    assert "\\u" not in out


# --- remove -------------------------------------------------------------------------------------


def test_c44_remove_keys_and_empty_parents(jk: ModuleType) -> None:
    text = dump({"keep": 1, "permissions": {"deny": ["x"]}, "a": {"b": {"c": 1}}})
    out = jk.remove(text, ["permissions.deny", "a.b.c"])
    assert out == dump({"keep": 1})


def test_c44_remove_keeps_nonempty_parent(jk: ModuleType) -> None:
    text = dump({"permissions": {"allow": ["Read"], "deny": ["x"]}})
    assert jk.remove(text, ["permissions.deny"]) == dump({"permissions": {"allow": ["Read"]}})


def test_c44_remove_does_not_touch_preexisting_empty_objects(jk: ModuleType) -> None:
    text = dump({"e": {}, "a": {"b": 1}, "f": {"g": {}}})
    assert jk.remove(text, ["a.b"]) == dump({"e": {}, "f": {"g": {}}})


def test_c44_remove_missing_keys_ignored(jk: ModuleType) -> None:
    text = dump({"a": {"b": 1}}, 4)
    assert jk.remove(text, ["nope", "a.nope", "x.y.z"]) == text


def test_c44_remove_accepts_dict_keys_and_keeps_indent(jk: ModuleType) -> None:
    text = dump({"a": 1, "b": 2}, "\t")
    assert jk.remove(text, {"b": 0}.keys()) == dump({"a": 1}, "\t")


def test_c44_remove_invalid_json_is_error(jk: ModuleType, errors: ModuleType) -> None:
    with pytest.raises(errors.KeysError):
        jk.remove("{ // c\n}", ["a"])


# --- values_sha ---------------------------------------------------------------------------------


def test_c44_values_sha(jk: ModuleType) -> None:
    value = {"b": [1, "é"], "a": {"z": None, "y": 1.5}}
    text = dump({"hooks": value, "permissions": {"deny": ["x"]}, "flag": False})
    got = jk.values_sha(text, ["hooks", "permissions.deny", "flag", "missing", "permissions.no"])
    assert got == {
        "hooks": canon_sha(value),
        "permissions.deny": canon_sha(["x"]),
        "flag": canon_sha(False),
        "missing": None,
        "permissions.no": None,
    }


def test_c44_values_sha_is_key_order_independent(jk: ModuleType) -> None:
    a = jk.values_sha(dump({"k": {"a": 1, "b": 2}}), ["k"])
    b = jk.values_sha(dump({"k": {"b": 2, "a": 1}}, 4), ["k"])
    assert a == b
    expected = hashlib.sha256(b'{"a":1,"b":2}').hexdigest()
    assert a == {"k": expected}


# --- round trip ---------------------------------------------------------------------------------

SETTINGS = {
    "$schema": "https://json.schemastore.org/claude-code-settings.json",
    "permissions": {
        "allow": ["Bash(npm run test:*)", "Read(~/.zshrc)"],
        "ask": ["Bash(git push:*)"],
    },
    "env": {"PROJECT_FLAG": "1"},
    "model": "opus",
}

MANAGED = {
    "hooks": {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "kuanflow-guard"}]}
        ]
    },
    "permissions.deny": ["Read(./.env)", "Bash(rm -rf:*)"],
    "env.KUANFLOW_ROOT": ".kuanflow",
    "kuanflow.meta.version": "0.4.0",
}


@pytest.mark.parametrize("indent", [2, 4, "\t"])
def test_c44_round_trip_settings_like(jk: ModuleType, indent: int | str) -> None:
    text = dump(SETTINGS, indent)
    merged = jk.merge(text, MANAGED)
    assert json.loads(merged)["permissions"]["deny"] == MANAGED["permissions.deny"]
    assert json.loads(merged)["kuanflow"] == {"meta": {"version": "0.4.0"}}
    assert jk.remove(merged, MANAGED.keys()) == text


def random_value(rng: random.Random, depth: int) -> Any:
    kind = rng.randrange(6 if depth < 2 else 4)
    if kind == 0:
        return rng.randint(-5, 5)
    if kind == 1:
        return rng.choice(["s", "é", "", "a.b", "x y"])
    if kind == 2:
        return rng.choice([True, False, None])
    if kind == 3:
        return [rng.randint(0, 3) for _ in range(rng.randint(0, 3))]
    if kind == 4:
        return {f"k{i}": random_value(rng, depth + 1) for i in range(rng.randint(0, 3))}
    return [random_value(rng, depth + 1) for _ in range(rng.randint(0, 2))]


def test_c44_round_trip_property(jk: ModuleType) -> None:
    rng = random.Random(4404)
    for _ in range(200):
        obj = {f"p{i}": random_value(rng, 0) for i in range(rng.randint(0, 4))}
        indent = rng.choice([1, 2, 4, "\t"])
        text = dump(obj, indent)
        managed: dict[str, Any] = {}
        for j in range(rng.randint(1, 3)):
            parent = rng.choice([f"p{i}" for i in range(len(obj))] + ["new"])
            if parent in obj and not (isinstance(obj[parent], dict) and obj[parent]):
                parent = "new"  # only non-empty existing objects (an emptied one would be pruned)
            key = f"{parent}.m{j}" if rng.random() < 0.7 else f"top{j}"
            if rng.random() < 0.3:
                key = f"fresh{j}.deep.leaf"
            managed[key] = random_value(rng, 1)
        merged = jk.merge(text, managed)
        assert jk.remove(merged, managed.keys()) == text, (text, managed)
