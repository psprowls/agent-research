"""Staleness classification tests for query orchestrator wiki evidence."""

from __future__ import annotations

from pathlib import Path

import pytest
from graph_wiki_core.commands.query_orchestrator import classify_wiki_freshness


def _write_page(tmp_path: Path, frontmatter: str, body: str | None = None) -> Path:
    page = tmp_path / "entities" / "scanner.md"
    page.parent.mkdir()
    body_text = (
        body
        if body is not None
        else "# Scanner\n\n## Narrative\nThe scanner refreshes wiki entity pages from code evidence.\n"
    )
    page.write_text(
        f"---\n{frontmatter}---\n{body_text}",
        encoding="utf-8",
    )
    return page


def test_drift_review_status_stale_marks_page_stale(tmp_path: Path) -> None:
    page = _write_page(tmp_path, "kind: package\ndrift_review: {status: stale}\n")

    result = classify_wiki_freshness(page, repo_head="head1")

    assert result.freshness == "stale"
    assert result.reason == "drift_review"


def test_multiline_drift_review_status_stale_marks_page_stale_even_when_commit_matches(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        "kind: package\n"
        "last_updated_commit: head1\n"
        "drift_review:\n"
        "  - section: Narrative\n"
        "    status: stale\n"
        "    reason: Source changed\n",
    )

    result = classify_wiki_freshness(page, repo_head="head1")

    assert result.freshness == "stale"
    assert result.reason == "drift_review"


@pytest.mark.parametrize(
    "drift_review",
    [
        "drift_review: []\n",
        "drift_review: {status: fresh}\n",
        "drift_review:\n  - section: Narrative\n    status: fresh\n    reason: Verified current\n",
        "drift_review: awaiting reviewer acknowledgement\n",
    ],
)
def test_benign_drift_review_metadata_does_not_mark_page_stale(tmp_path: Path, drift_review: str) -> None:
    page = _write_page(tmp_path, f"kind: package\nlast_updated_commit: head1\n{drift_review}")

    result = classify_wiki_freshness(page, repo_head="head1")

    assert result.freshness == "fresh"
    assert result.reason is None


def test_last_updated_commit_mismatch_marks_source_backed_entity_stale(tmp_path: Path) -> None:
    page = _write_page(tmp_path, "kind: package\nlast_updated_commit: oldhead\n")

    result = classify_wiki_freshness(page, repo_head="newhead")

    assert result.freshness == "stale"
    assert result.reason == "last_updated_commit mismatch"


def test_matching_last_updated_commit_marks_source_backed_entity_fresh(tmp_path: Path) -> None:
    page = _write_page(tmp_path, "kind: package\nlast_updated_commit: head1\n")

    result = classify_wiki_freshness(page, repo_head="head1")

    assert result.freshness == "fresh"
    assert result.reason is None


@pytest.mark.parametrize(
    "body",
    [
        "",
        "TODO",
        "# Scanner\n\n## Narrative\nNo narrative available.",
        "# Scanner\n\n## Narrative\nNeeds review.",
        "# Scanner\n\n## Narrative\nPlaceholder.",
    ],
)
def test_placeholder_todo_or_short_body_marks_page_stale(tmp_path: Path, body: str) -> None:
    page = _write_page(tmp_path, "kind: package\nlast_updated_commit: head1\n", body)

    result = classify_wiki_freshness(page, repo_head="head1")

    assert result.freshness == "stale"
    assert result.reason == "placeholder content"


@pytest.mark.parametrize("status_key", ["ingest_status", "proposal_status", "status"])
@pytest.mark.parametrize("status_value", ["degraded", "failed", "error", "blocked", "stale"])
def test_degraded_status_fields_mark_page_stale(tmp_path: Path, status_key: str, status_value: str) -> None:
    page = _write_page(tmp_path, f"kind: source\n{status_key}: {status_value}\n")

    result = classify_wiki_freshness(page, repo_head="head1")

    assert result.freshness == "stale"
    assert result.reason == "degraded status"


def test_missing_page_returns_unknown(tmp_path: Path) -> None:
    result = classify_wiki_freshness(tmp_path / "entities" / "missing.md", repo_head="head1")

    assert result.freshness == "unknown"
    assert result.reason == "wiki page not found"
