"""Fixture layout checks for eval-harness wiki corpora."""

import json
import re
from pathlib import Path

from graph_io import store
from workspace_io.paths import graph_dir

QUERY_CASES_PATH = Path(__file__).resolve().parents[3] / "eval" / "cases" / "query_cases.json"
WIKILINK_PATTERN = re.compile(r"\[\[([^|\]#]+)")


def test_fixture_wiki_uses_current_entity_layout(fixture_wiki_path: Path) -> None:
    """The eval wiki fixture must mirror current Graph Wiki page routing."""
    assert (fixture_wiki_path / "entities").is_dir()
    assert (fixture_wiki_path / "entities" / "pkg_eval-harness.md").is_file()
    assert not (fixture_wiki_path / "packages").exists()


def test_fixture_workspace_shapes_workspace_and_wiki_as_separate_roots(
    fixture_workspace_path: Path,
    fixture_wiki_path: Path,
) -> None:
    """Public eval helpers receive a workspace root, not the wiki root."""
    assert fixture_workspace_path != fixture_wiki_path
    assert (fixture_workspace_path / "wiki").resolve() == fixture_wiki_path.resolve()
    assert fixture_wiki_path.name == "wiki"


def test_committed_fixture_remains_markdown_source_only(
    fixture_workspace_path: Path,
    fixture_wiki_path: Path,
) -> None:
    """Direct fixture paths still point at the committed source fixture."""
    assert "packages/eval-harness/tests/fixtures/post-rebrand-workspace" in fixture_workspace_path.as_posix()
    assert fixture_wiki_path == fixture_workspace_path / "wiki"
    assert not (fixture_wiki_path / "log.md").exists()
    assert not (graph_dir(fixture_workspace_path) / "code.db").exists()


def test_runtime_fixture_bootstraps_log_and_schema_valid_graph_db(
    runtime_fixture_workspace_path: Path,
    runtime_fixture_wiki_path: Path,
) -> None:
    """Eval role producers receive a disposable workspace with runtime state."""
    assert runtime_fixture_wiki_path == runtime_fixture_workspace_path / "wiki"
    assert (runtime_fixture_wiki_path / "log.md").is_file()

    db_path = graph_dir(runtime_fixture_workspace_path) / "code.db"
    assert db_path.is_file()
    conn = store.connect(db_path)
    conn.close()


def test_runtime_fixture_is_isolated_from_committed_fixture(
    fixture_workspace_path: Path,
    fixture_wiki_path: Path,
    runtime_fixture_workspace_path: Path,
    runtime_fixture_wiki_path: Path,
) -> None:
    """Runtime writes never mutate the committed source fixture."""
    assert runtime_fixture_workspace_path != fixture_workspace_path
    assert runtime_fixture_wiki_path != fixture_wiki_path
    assert (graph_dir(runtime_fixture_workspace_path) / "bm25" / ".gitkeep").is_file()

    (runtime_fixture_wiki_path / "runtime-only.md").write_text("runtime copy\n", encoding="utf-8")
    assert not (fixture_wiki_path / "runtime-only.md").exists()


def test_librarian_query_cases_are_post_rebrand_and_cite_fixture_entities(fixture_wiki_path: Path) -> None:
    """Librarian eval cases must ask questions answerable from the committed fixture."""
    cases = json.loads(QUERY_CASES_PATH.read_text(encoding="utf-8"))
    serialized = json.dumps(cases).lower()

    assert "lattice" not in serialized

    for case in cases:
        citations = case.get("expected_citations")
        assert isinstance(citations, list), f"{case['case_id']} must declare expected_citations"
        assert citations, f"{case['case_id']} must cite at least one fixture entity"
        for citation in citations:
            assert isinstance(citation, str), f"{case['case_id']} has a non-string citation"
            assert (fixture_wiki_path / f"{citation}.md").is_file(), (
                f"{case['case_id']} cites missing fixture page {citation!r}"
            )


def test_fixture_entity_wikilinks_resolve_inside_fixture(fixture_wiki_path: Path) -> None:
    """Curated fixture markdown must not link to pages outside the committed corpus."""
    for page in (fixture_wiki_path / "entities").glob("*.md"):
        text = page.read_text(encoding="utf-8")
        for target in WIKILINK_PATTERN.findall(text):
            assert (fixture_wiki_path / f"{target}.md").is_file(), f"{page.name} links to missing {target!r}"
