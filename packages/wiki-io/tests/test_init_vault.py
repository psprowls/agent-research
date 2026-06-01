"""Unit tests for wiki_io.init_vault._resolve_pinned_containers — workspace exclusion plumb-through.

Requirements: WSRES-02.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _build_v2_repo(tmp_path: Path) -> dict:
    """Build a synthetic v2-layout repo under tmp_path.

    Layout:
        repo/
          graph-wiki/wiki/
          graph-wiki/.graph-wiki.yaml
          packages/pkg-a/pyproject.toml
          packages/pkg-b/pyproject.toml
          .git/
    """
    repo = tmp_path / "repo"
    (repo / "graph-wiki" / "wiki").mkdir(parents=True)
    (repo / "graph-wiki" / ".graph-wiki.yaml").write_text("plugins: []\n", encoding="utf-8")
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text(
        '[project]\nname="pkg-a"\nversion="0.0.1"\n', encoding="utf-8"
    )
    (repo / "packages" / "pkg-b").mkdir(parents=True)
    (repo / "packages" / "pkg-b" / "pyproject.toml").write_text(
        '[project]\nname="pkg-b"\nversion="0.0.1"\n', encoding="utf-8"
    )
    (repo / ".git").mkdir()
    return {"repo": repo, "workspace": repo / "graph-wiki"}


def test_resolve_pinned_containers_v2_excludes_workspace(tmp_path: Path) -> None:
    """_resolve_pinned_containers with workspace_path excludes graph-wiki from results."""
    from wiki_io.init_vault import _resolve_pinned_containers

    fixture = _build_v2_repo(tmp_path)
    repo = fixture["repo"]
    workspace = fixture["workspace"]

    records = _resolve_pinned_containers(repo, non_interactive=True, workspace_path=workspace)
    sources = {r["source"] for r in records}

    # The packages container must be found
    assert "packages" in sources, f"Expected 'packages' in sources, got: {sources}"

    # The workspace dir must NOT appear as a container
    assert "graph-wiki" not in sources, (
        f"Workspace dir 'graph-wiki' must be excluded when workspace_path is passed, got: {sources}"
    )


def test_resolve_pinned_containers_v1_guard(tmp_path: Path) -> None:
    """When workspace_path == repo (v1 layout), no over-exclusion occurs.

    D-11 guard: if workspace_path is the repo root itself, detect() skips the
    exclusion and returns the full classification list.
    """
    from wiki_io.init_vault import _resolve_pinned_containers

    repo = tmp_path / "repo"
    (repo / "wiki").mkdir(parents=True)
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text(
        '[project]\nname="pkg-a"\nversion="0.0.1"\n', encoding="utf-8"
    )
    (repo / ".git").mkdir()

    # v1 layout: workspace IS the repo root
    records_v1 = _resolve_pinned_containers(repo, non_interactive=True, workspace_path=repo)
    records_none = _resolve_pinned_containers(repo, non_interactive=True, workspace_path=None)

    sources_v1 = {r["source"] for r in records_v1}
    sources_none = {r["source"] for r in records_none}

    assert sources_v1 == sources_none, (
        f"v1 guard failed: passing workspace_path==repo must not change results.\n"
        f"  with workspace_path=repo: {sources_v1}\n"
        f"  with workspace_path=None: {sources_none}"
    )
    assert "packages" in sources_v1, f"Expected 'packages' in results, got: {sources_v1}"


def test_resolve_pinned_containers_default_workspace_path_none(tmp_path: Path) -> None:
    """Without workspace_path, graph-wiki IS included — proving the new param is additive.

    This documents the contract that callers MUST opt in by passing workspace_path.
    Pre-fix behavior is the default.
    """
    from wiki_io.init_vault import _resolve_pinned_containers

    fixture = _build_v2_repo(tmp_path)
    repo = fixture["repo"]

    # No workspace_path arg — old behavior
    records = _resolve_pinned_containers(repo, non_interactive=True)
    sources = {r["source"] for r in records}

    # Both containers are discoverable when workspace_path is not passed
    assert "packages" in sources, f"Expected 'packages' in sources, got: {sources}"
    assert "graph-wiki" in sources, (
        f"Without workspace_path, 'graph-wiki' must appear (additive default). Got: {sources}"
    )


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
    monkeypatch.setattr(
        init_vault, "_resolve_pinned_containers", lambda *a, **k: []
    )

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
    """IQP: init_wiki must NOT materialize legacy container folders (apps/packages/domains/dependencies)
    even when _resolve_pinned_containers returns non-empty vault_dir entries for them.
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

    pinned_stub = [
        {"source": "apps", "vault_dir": "apps", "classification": "app", "children_count": 3},
        {"source": "packages", "vault_dir": "packages", "classification": "package", "children_count": 5},
        {"source": "domains", "vault_dir": "domains", "classification": "package", "children_count": 2},
    ]

    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)
    monkeypatch.setattr(
        init_vault, "_resolve_pinned_containers", lambda *a, **k: pinned_stub
    )

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
    stub out _workspace_init and _resolve_pinned_containers so the test exercises
    only the directory-creation + placeholder-write path.
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
    monkeypatch.setattr(init_vault, "_resolve_pinned_containers", lambda *a, **k: [])

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
