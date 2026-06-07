"""Fixture layout checks for eval-harness wiki corpora."""

from pathlib import Path


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
