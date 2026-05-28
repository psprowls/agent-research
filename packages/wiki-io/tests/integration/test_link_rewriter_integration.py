"""Phase 46 Plan 02: integration tests for rewrite_vault against a fixture vault."""

# integration-gate-allow — pure local fixture vault

import json
from pathlib import Path

import pytest

from wiki_io.link_rewriter import (
    CURATED_LANES_REL,
    RewriteResult,
    rewrite_vault,
)


def _make_fixture_vault(tmp_path: Path) -> Path:
    """Build a tiny vault exercising:

    - concepts file with prose + code-block wikilink (only prose rewritten)
    - adrs file with alias wikilink
    - architecture file with anchor wikilink
    - sources file with unresolvable wikilink
    - workspace-rooted ``work/`` file
    """
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "adrs").mkdir(parents=True)
    (wiki / "architecture").mkdir(parents=True)
    (wiki / "sources").mkdir(parents=True)
    (tmp_path / "work").mkdir()
    # concepts/per-repo-layout.md — prose + fenced code wikilink
    (wiki / "concepts" / "per-repo-layout.md").write_text(
        "Refers to [[packages/graph-io/index]].\n\n```\n[[packages/graph-io/index]]\n```\n",
        encoding="utf-8",
    )
    # adrs/001.md — alias preservation
    (wiki / "adrs" / "001.md").write_text(
        "[[packages/graph-io/index|graph-io]]\n",
        encoding="utf-8",
    )
    # architecture/overview.md — anchor preservation
    (wiki / "architecture" / "overview.md").write_text(
        "[[packages/graph-io/index#api]]\n",
        encoding="utf-8",
    )
    # sources/legacy.md — unresolvable target (table[t] = None)
    (wiki / "sources" / "legacy.md").write_text(
        "[[packages/old-removed/index]]\n",
        encoding="utf-8",
    )
    # work/notes.md — workspace-rooted lane
    (tmp_path / "work" / "notes.md").write_text(
        "Notes mention [[domain/billing/index]] for context.\n",
        encoding="utf-8",
    )
    return wiki


TABLE = {
    "packages/graph-io/index": "entities/pkg__agent-research__graph-io",
    "domain/billing/index": "entities/domain__agent-research__billing",
    "packages/old-removed/index": None,  # unresolvable
}


def test_integration_full_rewrite_vault(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    result = rewrite_vault(wiki, TABLE)
    assert isinstance(result, RewriteResult)
    # 5 files visited.
    assert result.files_scanned == 5
    # 4 modified (sources/legacy.md unresolvable — no modification).
    assert result.files_modified == 4
    # Total rewrites: 1 (concepts; fenced one skipped) + 1 (adrs) + 1 (architecture) + 1 (work).
    assert result.rewrites_total == 4
    # 1 unresolvable in sources/legacy.md.
    assert result.unresolved_total == 1


def test_integration_fenced_code_byte_preserved(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    rewrite_vault(wiki, TABLE)
    content = (wiki / "concepts" / "per-repo-layout.md").read_text(encoding="utf-8")
    # Fenced block content preserved byte-identical.
    assert "```\n[[packages/graph-io/index]]\n```" in content
    # Prose rewrite applied.
    assert "[[entities/pkg__agent-research__graph-io]]" in content


def test_integration_alias_preserved(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    rewrite_vault(wiki, TABLE)
    content = (wiki / "adrs" / "001.md").read_text(encoding="utf-8")
    assert content.strip() == "[[entities/pkg__agent-research__graph-io|graph-io]]"


def test_integration_anchor_preserved(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    rewrite_vault(wiki, TABLE)
    content = (wiki / "architecture" / "overview.md").read_text(encoding="utf-8")
    assert content.strip() == "[[entities/pkg__agent-research__graph-io#api]]"


def test_integration_unresolvable_left_alone(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    rewrite_vault(wiki, TABLE)
    content = (wiki / "sources" / "legacy.md").read_text(encoding="utf-8")
    assert content.strip() == "[[packages/old-removed/index]]"


def test_integration_workspace_rooted_work_lane(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    rewrite_vault(wiki, TABLE)
    content = (tmp_path / "work" / "notes.md").read_text(encoding="utf-8")
    assert "[[entities/domain__agent-research__billing]]" in content


def test_integration_returns_RewriteResult_with_per_file_counts(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    result = rewrite_vault(wiki, TABLE)
    assert "wiki/concepts/per-repo-layout.md" in result.per_file
    assert result.per_file["wiki/concepts/per-repo-layout.md"] == 1
    # Unresolvable-only files NOT in per_file (count was 0).
    assert "wiki/sources/legacy.md" not in result.per_file


def test_integration_logs_per_rewrite_to_migration_log(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    log_path = tmp_path / ".graph-wiki" / "migration.log"
    rewrite_vault(wiki, TABLE, log_path=log_path)
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    # All recorded records are "rewrite" phase (no unresolved here — that comes from build_rewrite_table).
    rewrite_records = [r for r in records if r["phase"] == "rewrite"]
    assert len(rewrite_records) == 4
    # Each has from + to fields.
    for r in rewrite_records:
        assert "from" in r and "to" in r and "file" in r and "timestamp" in r


def test_integration_wiki_root_files_not_rewritten(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    # Create wiki/index.md and wiki/log.md with rewritable wikilinks.
    (wiki / "index.md").write_text("[[packages/graph-io/index]]\n", encoding="utf-8")
    (wiki / "log.md").write_text("[[packages/graph-io/index]]\n", encoding="utf-8")
    rewrite_vault(wiki, TABLE)
    # Both root files untouched.
    assert (wiki / "index.md").read_text(encoding="utf-8") == "[[packages/graph-io/index]]\n"
    assert (wiki / "log.md").read_text(encoding="utf-8") == "[[packages/graph-io/index]]\n"


def test_integration_atomic_no_tmp_remains(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    rewrite_vault(wiki, TABLE)
    tmp_files = list(wiki.rglob("*.tmp"))
    assert tmp_files == []


def test_integration_lanes_override(tmp_path):
    wiki = _make_fixture_vault(tmp_path)
    # Only walk concepts/ — adrs/architecture/sources/work should be untouched.
    rewrite_vault(wiki, TABLE, lanes=[wiki / "concepts"])
    assert "[[entities/pkg__agent-research__graph-io]]" in (
        wiki / "concepts" / "per-repo-layout.md"
    ).read_text(encoding="utf-8")
    # adrs/001.md untouched — alias still has the OLD target.
    assert "packages/graph-io/index|graph-io" in (
        wiki / "adrs" / "001.md"
    ).read_text(encoding="utf-8")


def test_integration_curated_lanes_rel_constant():
    # Sanity check: the public constant lists exactly the 5 expected suffixes.
    assert CURATED_LANES_REL == (
        "wiki/concepts",
        "wiki/adrs",
        "wiki/architecture",
        "wiki/sources",
        "work",
    )
