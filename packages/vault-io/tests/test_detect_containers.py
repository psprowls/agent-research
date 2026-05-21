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


# --- Phase 25: permissive Rule 3 contract (D-09) ---------------------------------
# These tests pin the new heuristic: a directory with >=1 manifested child
# classifies as `package`, with `children_count` reporting the manifested-child
# count (not raw subdir count), and an honest `reason` string that names what
# was skipped. See .planning/phases/25-packages-dir-misclassification-fix/.


def test_mixed_manifest_dirs_classify_as_package(tmp_path: Path) -> None:
    """5/6 manifested children -> package (the bug-repro shape on this repo).

    D-01 / D-02: permissive `>=1 manifested child` wins; `children_count`
    reports manifested count; `reason` names what was skipped.
    """
    from vault_io.detect_containers import _classify_dir

    container = tmp_path / "packages"
    for name in ("core-bedrock", "eval-harness", "model-adapter", "subagent-runtime", "vault-io"):
        pkg = container / name
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text('[project]\nname="x"\n', encoding="utf-8")
    (container / "prompt_sources").mkdir()

    rec = _classify_dir(container)

    assert rec["classification"] == "package", (
        f"Expected 'package' for 5/6 mixed-manifest dir, got: {rec['classification']} "
        f"(reason: {rec['reason']})"
    )
    assert rec["children_count"] == 5, (
        f"Expected children_count=5 (manifested count, per D-02), got: {rec['children_count']}"
    )
    assert "skipped" in rec["reason"], (
        f"Expected honest reason mentioning 'skipped' (D-02), got: {rec['reason']!r}"
    )


def test_loose_md_file_at_container_root_does_not_block_package(tmp_path: Path) -> None:
    """Loose `.md` at container root no longer flips to ambiguous (D-03)."""
    from vault_io.detect_containers import _classify_dir

    container = tmp_path / "packages"
    for name in ("pkg-a", "pkg-b"):
        pkg = container / name
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
    (container / "README.md").write_text("# packages\n", encoding="utf-8")

    rec = _classify_dir(container)

    assert rec["classification"] == "package", (
        f"Expected 'package' even with loose .md (D-03), got: {rec['classification']} "
        f"(reason: {rec['reason']})"
    )
    assert rec["children_count"] == 2, (
        f"Expected children_count=2 (manifested count), got: {rec['children_count']}"
    )


def test_empty_dir_falls_back_to_ambiguous(tmp_path: Path) -> None:
    """Empty/unrecognized directory still falls back to ambiguous (D-04)."""
    from vault_io.detect_containers import _classify_dir

    container = tmp_path / "empty_container"
    container.mkdir()

    rec = _classify_dir(container)

    assert rec["classification"] == "ambiguous", (
        f"Expected 'ambiguous' fallback for empty dir, got: {rec['classification']}"
    )
    assert "empty" in rec["reason"], (
        f"Expected fallback reason mentioning 'empty', got: {rec['reason']!r}"
    )


def test_single_manifested_child_with_many_non_manifested_siblings_still_package(
    tmp_path: Path,
) -> None:
    """One manifested child + 5 non-manifested siblings -> package (D-01 `>=1` semantics)."""
    from vault_io.detect_containers import _classify_dir

    container = tmp_path / "packages"
    pkg = container / "only-real-pkg"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text('[project]\nname="x"\n', encoding="utf-8")
    for name in ("sib1", "sib2", "sib3", "sib4", "sib5"):
        (container / name).mkdir()

    rec = _classify_dir(container)

    assert rec["classification"] == "package", (
        f"Expected 'package' for 1/6 (>=1 wins per D-01), got: {rec['classification']}"
    )
    assert rec["children_count"] == 1, (
        f"Expected children_count=1 (manifested count), got: {rec['children_count']}"
    )


def test_no_manifest_kids_with_md_files_predominant_classifies_as_docs_not_ambiguous(
    tmp_path: Path,
) -> None:
    """Rule 1 (docs) still fires when Rule 3 doesn't apply (regression guard)."""
    from vault_io.detect_containers import _classify_dir

    container = tmp_path / "docs_container"
    container.mkdir()
    for i in range(8):
        (container / f"note_{i}.md").write_text(f"# note {i}\n", encoding="utf-8")

    rec = _classify_dir(container)

    assert rec["classification"] == "docs", (
        f"Expected 'docs' for predominantly-.md dir (Rule 1), got: {rec['classification']}"
    )
