"""Unit tests for vault_io.detect_containers — workspace exclusion and v1/v2 layout guard.

Requirements: WSRES-02, WSRES-03.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def v2_workspace(tmp_path: Path, monkeypatch):
    """v2-layout fixture: repo with graph-wiki/ workspace child and packages/."""
    repo = tmp_path / "repo"
    (repo / "graph-wiki" / "wiki").mkdir(parents=True)
    (repo / "graph-wiki" / ".graph-wiki.yaml").write_text("plugins: []\n", encoding="utf-8")
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text('[project]\nname="a"\n', encoding="utf-8")
    (repo / "packages" / "pkg-b").mkdir(parents=True)
    (repo / "packages" / "pkg-b" / "pyproject.toml").write_text('[project]\nname="b"\n', encoding="utf-8")
    (repo / ".git").mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(repo / "graph-wiki"))
    return {"repo": repo, "workspace": repo / "graph-wiki"}


def test_v2_layout_finds_repo_containers(v2_workspace) -> None:
    """detect() with v2 layout returns a record with source == 'packages'."""
    from vault_io.detect_containers import detect

    repo = v2_workspace["repo"]
    workspace = v2_workspace["workspace"]
    records = detect(repo, workspace_path=workspace)

    sources = {r["source"] for r in records}
    assert "packages" in sources, f"Expected 'packages' in results, got: {sources}"


def test_workspace_path_excluded(v2_workspace) -> None:
    """detect() with v2 layout excludes the workspace dir itself from results."""
    from vault_io.detect_containers import detect

    repo = v2_workspace["repo"]
    workspace = v2_workspace["workspace"]
    records = detect(repo, workspace_path=workspace)

    sources = {r["source"] for r in records}
    assert "graph-wiki" not in sources, (
        f"Workspace dir 'graph-wiki' must be excluded from results, got: {sources}"
    )


def test_v1_layout_guard(tmp_path: Path) -> None:
    """When workspace == repo root (v1 layout), exclusion guard prevents self-skip.

    The D-11 guard: if wp == repo_root, no exclusion fires — detect() returns
    its normal classification list.
    """
    from vault_io.detect_containers import detect

    repo = tmp_path / "repo"
    (repo / "wiki").mkdir(parents=True)
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text('[project]\nname="a"\n', encoding="utf-8")
    (repo / ".git").mkdir()

    # In v1 layout, workspace_path IS the repo root — guard must prevent self-exclusion
    records_with_workspace = detect(repo, workspace_path=repo)
    records_without_workspace = detect(repo)

    sources_with = {r["source"] for r in records_with_workspace}
    sources_without = {r["source"] for r in records_without_workspace}

    assert sources_with == sources_without, (
        f"v1 guard failed: passing workspace_path==repo should not change results.\n"
        f"  with workspace_path: {sources_with}\n"
        f"  without workspace_path: {sources_without}"
    )
    assert "packages" in sources_with, f"Expected 'packages' in results, got: {sources_with}"


def test_v2_synthetic_repo(v2_workspace) -> None:
    """End-to-end: v2 synthetic fixture returns packages found AND graph-wiki excluded."""
    from vault_io.detect_containers import detect

    repo = v2_workspace["repo"]
    workspace = v2_workspace["workspace"]
    records = detect(repo, workspace_path=workspace)

    sources = {r["source"] for r in records}

    # Positive: packages container is discovered
    assert "packages" in sources, f"Expected 'packages' in results, got: {sources}"

    # Negative: workspace dir is excluded
    assert "graph-wiki" not in sources, (
        f"Workspace 'graph-wiki' must not appear in results, got: {sources}"
    )

    # The packages record should be classified as 'package'
    packages_rec = next(r for r in records if r["source"] == "packages")
    assert packages_rec["classification"] == "package", (
        f"Expected 'packages' to be classified as 'package', got: {packages_rec['classification']}"
    )
