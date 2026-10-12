"""Contract tests C51: `kuanflow promote` (CMD-20, Q-18)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import (
    assert_error,
    assert_ok,
    build,
    describe,
    invoke,
    snapshot,
    write,
)

WORK = "kuan-workbench/work/KF-1-outbox"
DRAFTS = f"{WORK}/drafts"
DATE = "2026-11-03"  # conftest.NOW
BODY = "\n## Context\nOrders emit events.\n\n## Decision\nUse an outbox table.\n"


def split(text: str) -> tuple[dict[str, Any] | None, str]:
    """(frontmatter mapping or None, body after the closing `---` line)."""
    if not text.startswith("---\n"):
        return None, text
    end = text.index("\n---\n", 3)
    data = yaml.safe_load(text[4 : end + 1])
    assert isinstance(data, dict)
    return data, text[end + 5 :]


@pytest.fixture
def project(tmp_path: Path, env: pytest.MonkeyPatch) -> Path:
    root = build("empty", tmp_path / "proj")
    assert_ok(invoke(["init", "--yes"], cwd=root))
    return root


def promote(root: Path, *args: str, cwd: Path | None = None) -> Any:
    return invoke(["promote", *args], cwd=cwd or root)


def test_promote_adr_vietnamese_title(project: Path) -> None:
    draft = f"{DRAFTS}/adr-outbox.md"
    fm = "---\nkind: adr\ntitle: Dùng outbox cho sự kiện đơn hàng\nowner: team-order\n---\n"
    write(project, draft, fm + BODY)
    result = promote(project, draft)
    assert_ok(result)
    target = "docs/adr/0001-dung-outbox-cho-su-kien-don-hang.md"
    assert f"promoted {draft} -> {target}" in result.stdout.splitlines()
    text = (project / target).read_text(encoding="utf-8")
    data, body = split(text)
    assert data is not None
    assert body == BODY
    assert data["id"] == "0001"
    assert data["title"] == "Dùng outbox cho sự kiện đơn hàng"
    assert data["status"] == "accepted"
    assert str(data["date"]) == DATE
    assert data["owner"] == "team-order"
    assert "kind" not in data
    assert list(data).index("title") < list(data).index("owner")  # existing order kept
    assert "Dùng outbox" in text  # allow_unicode
    assert not (project / draft).exists()
    assert not (project / DRAFTS).exists()  # empty drafts/ removed
    assert (project / WORK).is_dir()
    assert (project / "docs/adr/0000-template.md").is_file()


def test_promote_adr_numbering_after_existing(project: Path) -> None:
    write(project, "docs/adr/0007-old-decision.md", "# old\n")
    write(project, "docs/adr/0003-older.md", "# older\n")
    write(project, "docs/adr/12-not-numbered.md", "# x\n")
    write(project, "docs/adr/9999-notes.txt", "x\n")
    write(project, "docs/adr/notes.md", "# notes\n")
    write(project, f"{DRAFTS}/adr-next.md", "# Next decision\n\nText.\n")
    result = promote(project, f"{DRAFTS}/adr-next.md")
    assert_ok(result)
    assert (project / "docs/adr/0008-next-decision.md").is_file(), describe(result)


def test_promote_adr_without_frontmatter(project: Path) -> None:
    original = "# Use Kafka for events\n\nWe pick Kafka.\n"
    write(project, f"{DRAFTS}/adr-kafka.md", original)
    write(project, f"{DRAFTS}/other.md", "keep me\n")
    result = promote(project, f"{DRAFTS}/adr-kafka.md")
    assert_ok(result)
    target = project / "docs/adr/0001-use-kafka-for-events.md"
    data, body = split(target.read_text(encoding="utf-8"))
    assert data is not None
    assert body == original
    assert data["id"] == "0001"
    assert data["title"] == "Use Kafka for events"
    assert data["status"] == "accepted"
    assert str(data["date"]) == DATE
    assert (project / DRAFTS / "other.md").is_file()  # drafts/ not empty: kept


def test_promote_title_from_stem(project: Path) -> None:
    write(project, f"{DRAFTS}/adr-pick-a-db.md", "No heading here.\n")
    assert_ok(promote(project, f"{DRAFTS}/adr-pick-a-db.md"))
    assert (project / "docs/adr/0001-pick-a-db.md").is_file()


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("  Hello, World!!  ", "hello-world"),
        ("Đường đi của ĐƠN hàng", "duong-di-cua-don-hang"),
        ("Ünïcödé — test_case 42", "unicode-test-case-42"),
        ("日本語", "untitled"),
        ("---", "untitled"),
        (" ".join(["word"] * 20), "-".join(["word"] * 12)),
        ("a" * 80, "a" * 60),
    ],
    ids=["punct", "vietnamese-d", "accents", "non-latin", "dashes", "long-words", "long-one"],
)
def test_promote_slug_rules(project: Path, title: str, slug: str) -> None:
    write(
        project,
        f"{DRAFTS}/x.md",
        f"---\nkind: adr\ntitle: {json.dumps(title, ensure_ascii=False)}\n---\nB\n",
    )
    result = promote(project, f"{DRAFTS}/x.md")
    assert_ok(result)
    assert (project / f"docs/adr/0001-{slug}.md").is_file(), describe(result)
    assert len(slug) <= 60


def test_promote_runbook_with_frontmatter(project: Path) -> None:
    draft = f"{DRAFTS}/restart.md"
    write(project, draft, "---\nkind: runbook\ntitle: Restart order-svc\nowner: ops\n---\n" + BODY)
    result = promote(project, draft)
    assert_ok(result)
    target = "docs/runbooks/restart-order-svc.md"
    assert f"promoted {draft} -> {target}" in result.stdout.splitlines()
    data, body = split((project / target).read_text(encoding="utf-8"))
    assert data == {"title": "Restart order-svc", "owner": "ops"}
    assert body == BODY


def test_promote_runbook_without_frontmatter_byte_identical(project: Path) -> None:
    original = "# Restart the ledger\n\n1. Drain.\n2. Restart.\n"
    write(project, f"{DRAFTS}/runbook-ledger.md", original)
    assert_ok(promote(project, f"{DRAFTS}/runbook-ledger.md"))
    assert (project / "docs/runbooks/restart-the-ledger.md").read_text() == original


def test_promote_postmortem_refused(project: Path) -> None:
    write(project, f"{DRAFTS}/postmortem-2026-outage.md", "# Outage\n")
    write(project, f"{DRAFTS}/pm.md", "---\nkind: postmortem\n---\n# Outage\n")
    for name in ("postmortem-2026-outage.md", "pm.md"):
        result = promote(project, f"{DRAFTS}/{name}")
        assert_error(result, "postmortems go to the knowledge repo by pull request")
        assert (project / DRAFTS / name).is_file()


def test_promote_unknown_kind(project: Path) -> None:
    write(project, f"{DRAFTS}/notes.md", "# Some notes\n")
    before = snapshot(project)
    assert_error(promote(project, f"{DRAFTS}/notes.md"))
    assert snapshot(project) == before


def test_promote_target_exists(project: Path) -> None:
    write(project, "docs/runbooks/restart-x.md", "existing\n")
    write(project, f"{DRAFTS}/runbook-x.md", "# Restart X\n")
    before = snapshot(project)
    assert_error(promote(project, f"{DRAFTS}/runbook-x.md"))
    assert snapshot(project) == before


def test_promote_draft_outside_root(project: Path, tmp_path: Path) -> None:
    outside = tmp_path / "adr-outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    before = snapshot(project)
    assert_error(promote(project, str(outside)))
    assert snapshot(project) == before
    assert outside.is_file()


def test_promote_non_md_and_missing(project: Path) -> None:
    write(project, f"{DRAFTS}/adr-x.txt", "# X\n")
    before = snapshot(project)
    assert_error(promote(project, f"{DRAFTS}/adr-x.txt"))
    assert_error(promote(project, f"{DRAFTS}/adr-missing.md"))
    assert snapshot(project) == before


def test_promote_missing_config(project: Path) -> None:
    (project / ".kuanflow/config.yaml").unlink()
    write(project, f"{DRAFTS}/adr-x.md", "# X\n")
    before = snapshot(project)
    assert_error(promote(project, f"{DRAFTS}/adr-x.md"))
    assert snapshot(project) == before


def test_promote_uses_config_paths(project: Path) -> None:
    cfg = project / ".kuanflow/config.yaml"
    text = cfg.read_text(encoding="utf-8")
    cfg.write_text(text.replace("adr: docs/adr", "adr: docs/decisions"), encoding="utf-8")
    write(project, f"{DRAFTS}/adr-x.md", "# X marks\n")
    result = promote(project, f"{DRAFTS}/adr-x.md")
    assert_ok(result)
    assert (project / "docs/decisions/0001-x-marks.md").is_file()


def test_promote_dry_run(project: Path) -> None:
    draft = f"{DRAFTS}/adr-x.md"
    write(project, draft, "# X marks\n")
    before = snapshot(project)
    result = promote(project, draft, "--dry-run")
    assert_ok(result)
    assert f"would promote {draft} -> docs/adr/0001-x-marks.md" in result.stdout.splitlines()
    assert snapshot(project) == before


def test_promote_draft_relative_to_cwd(project: Path) -> None:
    write(project, f"{DRAFTS}/adr-x.md", "# X marks\n")
    result = promote(project, "drafts/adr-x.md", cwd=project / WORK)
    assert_ok(result)
    assert f"promoted {DRAFTS}/adr-x.md -> docs/adr/0001-x-marks.md" in result.stdout.splitlines()
    assert (project / "docs/adr/0001-x-marks.md").is_file()
