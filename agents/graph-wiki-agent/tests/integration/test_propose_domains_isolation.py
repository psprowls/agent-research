"""Phase 48 Plan 03 — PROPOSE-05 isolation acceptance tests.

These tests prove that placing a `domains.proposed.yaml` file next to the
authoritative `domains.yaml` in a workspace has ZERO effect on the graph.
This is the structural guarantee from CONTEXT D-17:
`graph_io.domains._load_domains_yaml` reads `domains.yaml` by literal
filename and never looks at `domains.proposed.yaml`.

These tests do NOT mock anything in graph_io — they exercise the real
`cg update` code path. That is the integrity guarantee being verified.

Tests:
  - test_proposed_yaml_produces_zero_graph_edges        — D-18 case 1
  - test_proposed_yaml_with_fake_package_never_appears   — D-18 case 2 (belt-and-suspenders)
  - test_proposed_yaml_does_not_break_normal_domain_loading — D-18 case 3
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from graph_io import update
from graph_io.store import read_only_connect
from workspace_io.paths import graph_dir

_FIXTURE_SRC = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages"
    / "graph-io"
    / "tests"
    / "fixtures"
    / "sample_monorepo"
)

_FAKE_PACKAGE_NAME = "__FAKE_PROPOSED_PACKAGE_48__"


# --------------------------------------------------------------------------- #
# Shared fixture
# --------------------------------------------------------------------------- #


def _git_init_and_commit(repo_root: Path, *, message: str = "seed") -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=repo_root, check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message], cwd=repo_root, check=True,
    )


@pytest.fixture
def isolation_workspace(tmp_path):
    """Build a minimal workspace + run `cg update` to get a baseline graph.

    Uses the sample_monorepo fixture (5 packages + a flat domains.yaml).
    The flat `domains.yaml` is REWRITTEN to be deterministic for these
    tests: exactly one domain `core` containing only `mypkg`.

    Returns (repo_root, workspace).
    """
    repo_root = tmp_path / "repo"
    shutil.copytree(_FIXTURE_SRC, repo_root)

    # Rewrite domains.yaml to the deterministic flat shape this test expects.
    # This matches the shape `graph_io.domains.emit` reads natively (flat:
    # top-level keys ARE domain names).
    (repo_root / "domains.yaml").write_text(
        yaml.safe_dump(
            {
                "core": {"packages": ["mypkg"], "parent": None},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    _git_init_and_commit(repo_root)
    update.run(repo_root, full=True)

    workspace = (repo_root / "graph-wiki").resolve()
    return repo_root, workspace


def _open_db(workspace: Path):
    """Open a read-only connection over the workspace's code.db."""
    db_path = graph_dir(workspace) / "code.db"
    return read_only_connect(db_path)


def _domain_edges(conn) -> list[tuple]:
    """Return all `belongs_to_domain` edges as (src_kind, src_name, dst_kind, dst_name)."""
    return list(
        conn.execute(
            """
            SELECT s.kind, s.name, d.kind, d.name
            FROM edges e
            JOIN nodes s ON e.src = s.id
            JOIN nodes d ON e.dst = d.id
            WHERE e.kind = 'belongs_to_domain'
            ORDER BY s.name, d.name
            """
        ).fetchall()
    )


def _all_node_names(conn) -> list[str]:
    return [
        row[0]
        for row in conn.execute("SELECT name FROM nodes ORDER BY name").fetchall()
    ]


def _domain_node_names(conn) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM nodes WHERE kind='domain' ORDER BY name"
        ).fetchall()
    ]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_proposed_yaml_produces_zero_graph_edges(isolation_workspace):
    """D-18 case 1: writing `domains.proposed.yaml` containing a 'data'
    domain claiming `bar` and `baz` produces ZERO `belongs_to_domain` edges
    for those packages after re-running `cg update`. Only `mypkg -> core`
    (from `domains.yaml`) is present."""
    repo_root, workspace = isolation_workspace

    # Baseline: only `mypkg -> core` should exist.
    conn = _open_db(workspace)
    try:
        baseline = _domain_edges(conn)
    finally:
        conn.close()
    assert len(baseline) == 1
    assert baseline[0][1] == "mypkg"  # src.name
    assert baseline[0][3] == "core"  # dst.name

    # Write domains.proposed.yaml using the proposed_domains+metadata schema
    # (the same shape `propose_domains_cmd` writes; matches D-14).
    (repo_root / "domains.proposed.yaml").write_text(
        yaml.safe_dump(
            {
                "proposed_domains": {
                    "data": {
                        "packages": ["jspkg", "webutil"],
                        "parent": None,
                        "description": "x",
                        "confidence": 0.5,
                        "llm_origin": "fan_out",
                    }
                },
                "metadata": {
                    "generated_at": "2026-05-27T00:00:00Z",
                    "cluster_command": "cg domain-clusters",
                    "model": "test",
                    "total_cost_usd": 0.0,
                    "stripped_unknown_packages": [],
                    "stripped_cycle_edges": [],
                    "llm_failures": [],
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    # Need a fresh git commit so cg update picks up the new file. Even though
    # the test relies on _load_domains_yaml NOT reading the file at all, we
    # commit it to make the test realistic: in real usage the user might
    # check in domains.proposed.yaml accidentally and we still must not
    # ingest it.
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "add domains.proposed.yaml"],
        cwd=repo_root, check=True,
    )

    # Re-run cg update.
    update.run(repo_root, full=True)

    # Re-check the graph: must still be exactly `mypkg -> core`.
    conn = _open_db(workspace)
    try:
        edges = _domain_edges(conn)
        domain_names = _domain_node_names(conn)
    finally:
        conn.close()

    assert len(edges) == 1, (
        f"expected exactly 1 belongs_to_domain edge after writing "
        f"domains.proposed.yaml; got {len(edges)}: {edges}"
    )
    assert edges[0][1] == "mypkg"
    assert edges[0][3] == "core"
    # Domain nodes: only `core` should exist. `data` must NOT be a domain.
    assert "data" not in domain_names, (
        f"`data` from domains.proposed.yaml must not be promoted to a Domain "
        f"node; got {domain_names}"
    )


def test_proposed_yaml_with_fake_package_never_appears(isolation_workspace):
    """D-18 case 2 (belt-and-suspenders): a UNIQUE fake package name in
    `domains.proposed.yaml` never appears anywhere in the graph after
    re-running `cg update`. Catches any future change that might introduce
    glob-based domain-file discovery."""
    repo_root, workspace = isolation_workspace

    (repo_root / "domains.proposed.yaml").write_text(
        yaml.safe_dump(
            {
                "proposed_domains": {
                    "ghost-domain": {
                        "packages": [_FAKE_PACKAGE_NAME],
                        "parent": None,
                        "description": "ghost",
                        "confidence": 0.1,
                        "llm_origin": "fan_out",
                    }
                },
                "metadata": {
                    "generated_at": "2026-05-27T00:00:00Z",
                    "cluster_command": "cg domain-clusters",
                    "model": "test",
                    "total_cost_usd": 0.0,
                    "stripped_unknown_packages": [],
                    "stripped_cycle_edges": [],
                    "llm_failures": [],
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "add ghost domains.proposed.yaml"],
        cwd=repo_root, check=True,
    )

    update.run(repo_root, full=True)

    conn = _open_db(workspace)
    try:
        node_names = _all_node_names(conn)
        # Also check all edges' src/dst names.
        edge_endpoints = list(
            conn.execute(
                """
                SELECT s.name FROM edges e JOIN nodes s ON e.src = s.id
                UNION
                SELECT d.name FROM edges e JOIN nodes d ON e.dst = d.id
                """
            ).fetchall()
        )
    finally:
        conn.close()

    endpoint_names = {row[0] for row in edge_endpoints}
    assert _FAKE_PACKAGE_NAME not in node_names, (
        f"{_FAKE_PACKAGE_NAME} from domains.proposed.yaml leaked into nodes"
    )
    assert _FAKE_PACKAGE_NAME not in endpoint_names, (
        f"{_FAKE_PACKAGE_NAME} from domains.proposed.yaml leaked into edges"
    )
    assert "ghost-domain" not in node_names, (
        "ghost-domain from domains.proposed.yaml must not become a Domain node"
    )


def test_proposed_yaml_does_not_break_normal_domain_loading(isolation_workspace):
    """D-18 case 3: with `domains.proposed.yaml` present, the listed domains
    are exactly what `domains.yaml` declares (`core`). `data` must NOT
    appear."""
    repo_root, workspace = isolation_workspace

    (repo_root / "domains.proposed.yaml").write_text(
        yaml.safe_dump(
            {
                "proposed_domains": {
                    "data": {
                        "packages": ["jspkg", "webutil"],
                        "parent": None,
                        "description": "x",
                        "confidence": 0.5,
                        "llm_origin": "fan_out",
                    }
                },
                "metadata": {
                    "generated_at": "2026-05-27T00:00:00Z",
                    "cluster_command": "cg domain-clusters",
                    "model": "test",
                    "total_cost_usd": 0.0,
                    "stripped_unknown_packages": [],
                    "stripped_cycle_edges": [],
                    "llm_failures": [],
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "smoke-test commit"],
        cwd=repo_root, check=True,
    )

    update.run(repo_root, full=True)

    # Mirror the q_list_domains read path: open read-only, list Domain nodes.
    from graph_io.queries import list_domains

    conn = _open_db(workspace)
    try:
        domains = list_domains(conn)
    finally:
        conn.close()

    names = [d.name for d in domains]
    assert names == ["core"], (
        f"expected exactly ['core'] from domains.yaml; got {names}"
    )
    assert "data" not in names, "domains.proposed.yaml `data` must not list"


# --------------------------------------------------------------------------- #
# Structural sanity-check: graph-io must not reference the proposed filename
# --------------------------------------------------------------------------- #


def test_graph_io_does_not_reference_proposed_yaml():
    """Belt-and-suspenders: ensure no module in `packages/graph-io/src/graph_io/`
    references `domains.proposed.yaml` or any `.proposed.yaml` suffix. This
    is the structural invariant that backs PROPOSE-05 — a regression here
    would be the first signal that someone added glob-based domain discovery."""
    graph_io_src = (
        Path(__file__).parent.parent.parent.parent.parent
        / "packages" / "graph-io" / "src" / "graph_io"
    )
    assert graph_io_src.is_dir(), f"graph_io src not found at {graph_io_src}"

    bad_hits: list[str] = []
    for py_file in graph_io_src.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "domains.proposed" in text or ".proposed.yaml" in text or "proposed_domains" in text:
            bad_hits.append(str(py_file.relative_to(graph_io_src)))

    assert not bad_hits, (
        f"graph_io must not reference domains.proposed.yaml; offenders: {bad_hits}"
    )
