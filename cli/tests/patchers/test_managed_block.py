"""Contract tests C42: kuanflow_cli.patchers.managed_block."""

from __future__ import annotations

import hashlib
import importlib
import random
from types import ModuleType

import pytest

BEGIN = {
    "html": "<!-- kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here) -->",
    "hash": "# kuanflow:begin (managed by Kuanflow — edit via Kuanflow, not here)",
}
END = {"html": "<!-- kuanflow:end -->", "hash": "# kuanflow:end"}
STYLES = ("html", "hash")
POSITIONS = ("top", "bottom")


@pytest.fixture
def mb() -> ModuleType:
    return importlib.import_module("kuanflow_cli.patchers.managed_block")


@pytest.fixture
def errors() -> ModuleType:
    return importlib.import_module("kuanflow_cli.errors")


def block(style: str, body: str) -> str:
    return f"{BEGIN[style]}\n{body}{END[style]}\n"


# --- markers / style_for / render_block ---------------------------------------------------------


@pytest.mark.parametrize("style", STYLES)
def test_c42_render_block_exact_markers(mb: ModuleType, style: str) -> None:
    assert mb.render_block("line one\nline two\n", style) == block(style, "line one\nline two\n")


@pytest.mark.parametrize(
    ("path", "style"),
    [
        ("AGENTS.md", "html"),
        ("docs/guide.md", "html"),
        (".gitignore", "hash"),
        ("info/exclude", "hash"),
        ("config.yaml", "hash"),
        ("README", "hash"),
        ("notes.markdown", "hash"),
    ],
)
def test_c42_style_for(mb: ModuleType, path: str, style: str) -> None:
    assert mb.style_for(path) == style


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize(
    ("body", "normalised"),
    [
        ("x", "x\n"),
        ("x\n", "x\n"),
        ("x\n\n\n", "x\n"),
        ("a\nb", "a\nb\n"),
        ("", ""),
    ],
)
def test_c42_render_block_normalises_body(
    mb: ModuleType, style: str, body: str, normalised: str
) -> None:
    assert mb.render_block(body, style) == block(style, normalised)


@pytest.mark.parametrize("style", STYLES)
def test_c42_render_block_empty_body_has_no_body_line(mb: ModuleType, style: str) -> None:
    assert mb.render_block("", style) == f"{BEGIN[style]}\n{END[style]}\n"


# --- find ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("style", STYLES)
def test_c42_find_none_without_markers(mb: ModuleType, style: str) -> None:
    assert mb.find("", style) is None
    assert mb.find("just text\n# comment\n<!-- c -->\n", style) is None


@pytest.mark.parametrize("style", STYLES)
def test_c42_find_offsets_and_body(mb: ModuleType, style: str) -> None:
    pre = "intro\n\n"
    blk = block(style, "b1\nb2\n")
    text = pre + blk + "after\n"
    found = mb.find(text, style)
    assert found is not None
    assert found.start == len(pre)
    assert found.end == len(pre) + len(blk)
    assert found.body == "b1\nb2\n"
    assert text[found.start : found.end] == blk


@pytest.mark.parametrize("style", STYLES)
def test_c42_find_end_at_eof_without_newline(mb: ModuleType, style: str) -> None:
    text = f"x\n{BEGIN[style]}\nbody\n{END[style]}"
    found = mb.find(text, style)
    assert found is not None
    assert found.start == 2
    assert found.end == len(text)
    assert found.body == "body\n"


@pytest.mark.parametrize("style", STYLES)
def test_c42_find_tolerates_trailing_whitespace_and_cr(mb: ModuleType, style: str) -> None:
    prefix = {"html": "<!-- kuanflow:begin", "hash": "# kuanflow:begin"}[style]
    begin = f"{prefix} some other wording -->  \r\n"
    end = f"{END[style]} \t\r\n"
    text = "top\r\n" + begin + "body\r\n" + end + "tail\r\n"
    found = mb.find(text, style)
    assert found is not None
    assert found.start == len("top\r\n")
    assert found.end == len(text) - len("tail\r\n")
    assert found.body == "body\r\n"


@pytest.mark.parametrize("style", STYLES)
def test_c42_find_empty_body(mb: ModuleType, style: str) -> None:
    found = mb.find(block(style, ""), style)
    assert found is not None
    assert found.body == ""


@pytest.mark.parametrize("style", STYLES)
def test_c42_find_requires_marker_at_line_start(mb: ModuleType, style: str) -> None:
    text = f"  {BEGIN[style]}\nbody\n  {END[style]}\n"
    assert mb.find(text, style) is None


def test_c42_find_ignores_other_style(mb: ModuleType) -> None:
    assert mb.find(block("html", "x\n"), "hash") is None
    assert mb.find(block("hash", "x\n"), "html") is None


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize(
    "shape",
    ["two-begins", "two-blocks", "begin-without-end", "end-without-begin", "end-before-begin"],
)
def test_c42_find_broken_markers(
    mb: ModuleType, errors: ModuleType, style: str, shape: str
) -> None:
    b, e = BEGIN[style], END[style]
    text = {
        "two-begins": f"{b}\nx\n{b}\ny\n{e}\n",
        "two-blocks": f"{b}\nx\n{e}\nmid\n{b}\ny\n{e}\n",
        "begin-without-end": f"pre\n{b}\nx\n",
        "end-without-begin": f"pre\nx\n{e}\n",
        "end-before-begin": f"{e}\nx\n{b}\n",
    }[shape]
    with pytest.raises(errors.BlockError):
        mb.find(text, style)
    with pytest.raises(errors.BlockError):
        mb.upsert(text, "new\n", style, "bottom")
    with pytest.raises(errors.BlockError):
        mb.remove(text, style)


# --- upsert -------------------------------------------------------------------------------------


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("position", POSITIONS)
@pytest.mark.parametrize("text", [None, ""])
def test_c42_upsert_no_file(mb: ModuleType, style: str, position: str, text: str | None) -> None:
    assert mb.upsert(text, "body", style, position) == block(style, "body\n")


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("position", POSITIONS)
def test_c42_upsert_replaces_existing_block_only(mb: ModuleType, style: str, position: str) -> None:
    prefix = {"html": "<!-- kuanflow:begin", "hash": "# kuanflow:begin"}[style]
    pre = "Line A  \r\n\n\tindented — ü\n"
    post = "\n\ntrailing   \nno newline at end"
    old = f"{prefix} legacy wording  \nold body\nmore\n{END[style]}  \n"
    out = mb.upsert(pre + old + post, "new body", style, position)
    assert out == pre + block(style, "new body\n") + post


@pytest.mark.parametrize("style", STYLES)
def test_c42_upsert_top(mb: ModuleType, style: str) -> None:
    assert mb.upsert("hello\n", "b", style, "top") == block(style, "b\n") + "\nhello\n"


@pytest.mark.parametrize("style", STYLES)
def test_c42_upsert_bottom_with_final_newline(mb: ModuleType, style: str) -> None:
    assert mb.upsert("hello\n", "b", style, "bottom") == "hello\n\n" + block(style, "b\n")


@pytest.mark.parametrize("style", STYLES)
def test_c42_upsert_bottom_without_final_newline(mb: ModuleType, style: str) -> None:
    assert mb.upsert("hello", "b", style, "bottom") == "hello\n\n" + block(style, "b\n")


@pytest.mark.parametrize("style", STYLES)
def test_c42_upsert_is_idempotent(mb: ModuleType, style: str) -> None:
    once = mb.upsert("x\n", "b\n", style, "bottom")
    assert mb.upsert(once, "b\n", style, "bottom") == once
    assert mb.upsert(once, "b\n", style, "top") == once


# --- remove -------------------------------------------------------------------------------------


@pytest.mark.parametrize("style", STYLES)
def test_c42_remove_without_block_unchanged(mb: ModuleType, style: str) -> None:
    for text in ("", "a\n", "no newline", "\n\n"):
        assert mb.remove(text, style) == text


@pytest.mark.parametrize("style", STYLES)
def test_c42_remove_block_only(mb: ModuleType, style: str) -> None:
    assert mb.remove(block(style, "x\n"), style) == ""


@pytest.mark.parametrize("style", STYLES)
def test_c42_remove_at_start_drops_one_following_newline(mb: ModuleType, style: str) -> None:
    assert mb.remove(block(style, "x\n") + "\n\nrest\n", style) == "\nrest\n"


@pytest.mark.parametrize("style", STYLES)
def test_c42_remove_preceded_by_blank_line_drops_one_newline(mb: ModuleType, style: str) -> None:
    assert mb.remove("a\n\n" + block(style, "x\n") + "b\n", style) == "a\nb\n"
    assert mb.remove("a\n\n\n" + block(style, "x\n"), style) == "a\n\n"


@pytest.mark.parametrize("style", STYLES)
def test_c42_remove_in_middle_without_blank_line(mb: ModuleType, style: str) -> None:
    assert mb.remove("a\n" + block(style, "x\n") + "b\n", style) == "a\nb\n"


@pytest.mark.parametrize("style", STYLES)
def test_c42_remove_at_start_not_followed_by_newline(mb: ModuleType, style: str) -> None:
    assert mb.remove(block(style, "x\n") + "rest\n", style) == "rest\n"


# --- round trip ---------------------------------------------------------------------------------

HANDWRITTEN = [
    "",
    "\n",
    "\n\n",
    "one line\n",
    "# Title\n\nparagraph\n",
    "trailing blank\n\n",
    "\n\nleading blanks\n",
    "crlf line\r\n",
    "mixed\r\nlines\n\n",
    "unicode — ü ✓\n",
    "   spaced   \n\t\ttabbed\n",
    "<!-- an html comment -->\n# a hash comment\n",
    "*.pyc\n.venv/\n",
]

LINE_POOL = [
    "",
    "text",
    "  indented",
    "\ttab",
    "# heading",
    "<!-- comment -->",
    "- item",
    "kuanflow mention",
    "café — ü",
    "trailing   ",
    "cr\r",
]

BODIES = ["", "x", "x\n", "multi\nline\n", "trail\n\n\n", "  spaced\n\tbody", "ü — ✓\n"]


def generated_texts(n: int, seed: int = 4242) -> list[str]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        lines = [rng.choice(LINE_POOL) for _ in range(rng.randint(0, 8))]
        out.append("".join(line + "\n" for line in lines))
    return out


ROUND_TRIP_TEXTS = HANDWRITTEN + generated_texts(150)


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("position", POSITIONS)
def test_c42_round_trip_property(mb: ModuleType, style: str, position: str) -> None:
    rng = random.Random(f"{style}-{position}")
    for text in ROUND_TRIP_TEXTS:
        assert text == "" or text.endswith("\n")
        body = rng.choice(BODIES)
        upserted = mb.upsert(text, body, style, position)
        found = mb.find(upserted, style)
        assert found is not None
        assert upserted[found.start : found.end] == mb.render_block(body, style)
        assert mb.remove(upserted, style) == text, (text, body)


@pytest.mark.parametrize("style", STYLES)
def test_c42_no_final_newline_comes_back_with_one(mb: ModuleType, style: str) -> None:
    for text in ("hello", "a\nb", "x\n\ny"):
        assert mb.remove(mb.upsert(text, "b", style, "bottom"), style) == text + "\n"


# --- body_sha256 --------------------------------------------------------------------------------


@pytest.mark.parametrize("style", STYLES)
def test_c42_body_sha256(mb: ModuleType, style: str) -> None:
    text = "pre\n" + block(style, "é body\nline\n") + "post\n"
    expected = hashlib.sha256("é body\nline\n".encode()).hexdigest()
    assert mb.body_sha256(text, style) == expected
    assert mb.body_sha256(mb.upsert("x\n", "b", style, "top"), style) == (
        hashlib.sha256(b"b\n").hexdigest()
    )


@pytest.mark.parametrize("style", STYLES)
def test_c42_body_sha256_none_without_block(mb: ModuleType, style: str) -> None:
    assert mb.body_sha256("plain\n", style) is None
    assert mb.body_sha256("", style) is None
