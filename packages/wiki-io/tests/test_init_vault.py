"""Unit tests for wiki_io.init_vault.init_wiki — vault bootstrap behaviour.

The container-detection / layout-pinning path was removed (decontainerize
Task 1.3); init_wiki no longer detects containers or writes a graph-wiki:layout
block. Tests that exercised `_resolve_pinned_containers` were removed with it.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_init_wiki_titles_claude_md_with_topic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wiki CLAUDE.md title uses the human topic, not the 'wiki' dir name."""
    from wiki_io import init_vault

    repo = tmp_path / "repo"
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="solo"\nversion="0.0.1"\n', encoding="utf-8"
    )
    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)

    init_vault.init_wiki(
        wiki, repo, topic="Agent Research", tool="claude-code", force=False, non_interactive=True
    )

    claude = (wiki / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.splitlines()[0] == "# Agent Research — Code Wiki"
    # The bootstrapped index stub title is topic-based too.
    index = (wiki / "index.md").read_text(encoding="utf-8")
    assert "# Index — Agent Research" in index


def test_init_wiki_creates_section_index_stubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_wiki seeds stub index.md files in concepts/sources/adrs/architecture
    and preserves them across a re-init with force=True."""
    from wiki_io import init_vault

    repo = tmp_path / "repo"
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="solo"\nversion="0.0.1"\n', encoding="utf-8"
    )

    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)

    init_vault.init_wiki(
        wiki, repo, topic="test", tool="claude-code", force=False, non_interactive=True
    )

    expected = {
        "concepts": "Concept",
        "sources": "Source",
        "adrs": "ADR",
        "architecture": "Architecture",
    }
    for section, label in expected.items():
        stub = wiki / section / "index.md"
        assert stub.exists(), f"missing stub: {stub}"
        first = next(
            line for line in stub.read_text(encoding="utf-8").splitlines() if line.strip()
        )
        assert first == f"# {label}", f"unexpected heading in {stub}: {first!r}"

    sentinel = wiki / "concepts" / "index.md"
    sentinel.write_text("SENTINEL\n", encoding="utf-8")

    init_vault.init_wiki(
        wiki, repo, topic="test", tool="claude-code", force=True, non_interactive=True
    )

    assert sentinel.read_text(encoding="utf-8") == "SENTINEL\n", (
        "existing stub was overwritten by re-init"
    )


def test_init_writes_no_layout_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_wiki must NOT detect containers or pin a graph-wiki:layout block.

    Decontainerize Task 1.3: entity discovery is now purely graph-driven, so the
    vault schema files (CLAUDE.md / AGENTS.md) must no longer carry a pinned
    layout block describing detected containers/classification.
    """
    from wiki_io import init_vault

    repo = tmp_path / "repo"
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="solo"\nversion="0.0.1"\n', encoding="utf-8"
    )

    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)

    init_vault.init_wiki(
        wiki, repo, topic="x", tool="claude-code", force=True, non_interactive=True
    )

    claude = (wiki / "CLAUDE.md").read_text(encoding="utf-8")
    # No pinned layout block (start/end markers) and none of its content fields.
    assert "graph-wiki:layout" not in claude
    assert "graph-wiki:layout:start" not in claude
    assert "graph-wiki:layout:end" not in claude
    assert "detected_at:" not in claude
    assert "containers:" not in claude


def test_entities_in_fixed_vault_dirs() -> None:
    """URI-04 / D-14: 'entities' must be in FIXED_VAULT_DIRS for vault bootstrap."""
    from wiki_io.init_vault import FIXED_VAULT_DIRS

    assert "entities" in FIXED_VAULT_DIRS


def test_dependencies_not_in_fixed_vault_dirs() -> None:
    """IQP: 'dependencies' legacy container must NOT be in FIXED_VAULT_DIRS."""
    from wiki_io.init_vault import FIXED_VAULT_DIRS

    assert "dependencies" not in FIXED_VAULT_DIRS


def test_legacy_container_folders_not_created_by_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IQP: init_wiki must NOT materialize legacy container folders (apps/packages/domains/dependencies).
    Canonical FIXED_VAULT_DIRS (entities, concepts, architecture, adrs, sources, .templates)
    must still be created.
    """
    from wiki_io import init_vault

    repo = tmp_path / "repo"
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="solo"\nversion="0.0.1"\n', encoding="utf-8"
    )

    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)

    init_vault.init_wiki(
        wiki, repo, topic="test", tool="claude-code", force=False, non_interactive=True
    )

    # Legacy container folders must NOT exist
    assert not (wiki / "dependencies").exists(), "dependencies/ must not be created"
    assert not (wiki / "apps").exists(), "apps/ must not be created (container vault_dirs not materialized)"
    assert not (wiki / "packages").exists(), "packages/ must not be created (container vault_dirs not materialized)"
    assert not (wiki / "domains").exists(), "domains/ must not be created (container vault_dirs not materialized)"

    # Canonical dirs must still exist
    assert (wiki / "entities").is_dir(), "entities/ must be created"
    assert (wiki / "concepts").is_dir(), "concepts/ must be created"
    assert (wiki / "architecture").is_dir(), "architecture/ must be created"
    assert (wiki / "adrs").is_dir(), "adrs/ must be created"
    assert (wiki / "sources").is_dir(), "sources/ must be created"
    assert (wiki / ".templates").is_dir(), ".templates/ must be created"


def test_entities_dir_bootstrapped_with_gitkeep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_wiki creates wiki/entities/.gitkeep so the empty dir is committable.

    Uses the same monkeypatch pattern as test_init_wiki_creates_section_index_stubs:
    stub out _workspace_init so the test exercises only the directory-creation +
    placeholder-write path.
    """
    from wiki_io import init_vault

    repo = tmp_path / "repo"
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="solo"\nversion="0.0.1"\n', encoding="utf-8"
    )

    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)

    result = init_vault.init_wiki(
        wiki, repo, topic="test", tool="claude-code", force=False, non_interactive=True
    )

    entities_dir = wiki / "entities"
    gitkeep = entities_dir / ".gitkeep"
    assert entities_dir.is_dir(), f"entities/ dir not created: {entities_dir}"
    assert gitkeep.is_file(), f".gitkeep not created: {gitkeep}"
    assert gitkeep.read_text(encoding="utf-8") == "", (
        f".gitkeep must be empty, got: {gitkeep.read_text(encoding='utf-8')!r}"
    )
    assert not (entities_dir / "_index.md").exists(), (
        "_index.md must no longer be created"
    )
    assert "entities/.gitkeep" in result["installed_files"], (
        f"installed_files missing entities/.gitkeep: {result['installed_files']}"
    )
