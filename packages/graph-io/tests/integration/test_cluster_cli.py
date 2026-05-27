"""Integration tests for `cg domain-clusters` against the agent-research repo.

These tests subprocess-invoke `cg domain-clusters` against the actual
agent-research code.db. Help-text tests always run; graph-dependent tests
skip cleanly when `code.db` is missing so CI is safe before `cg update`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Walk up from this file to find the agent-research repo root."""
    p = Path(__file__).resolve()
    for ancestor in p.parents:
        if (ancestor / "pyproject.toml").exists() and (ancestor / "packages").exists():
            return ancestor
    pytest.skip("Cannot locate agent-research repo root from test file location")


def _cg_cmd() -> list[str]:
    return [sys.executable, "-m", "graph_io.cli.main"]


def _agent_research_graph_available() -> bool:
    """True if the workspace has a code.db that read_only_connect would accept."""
    from workspace_io.config import resolve
    from workspace_io.paths import graph_dir

    try:
        ws = resolve(_repo_root(), require_manifest=False).workspace
        db = graph_dir(ws) / "code.db"
        return db.exists()
    except Exception:
        return False


@pytest.mark.integration
def test_cg_help_lists_command() -> None:
    """CLUSTER-04: `cg --help` lists domain-clusters."""
    result = subprocess.run(
        [*_cg_cmd(), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "domain-clusters" in result.stdout


@pytest.mark.integration
def test_subcommand_help_exit_zero() -> None:
    """CLUSTER-04: `cg domain-clusters --help` exits 0 and shows --hub-threshold."""
    result = subprocess.run(
        [*_cg_cmd(), "domain-clusters", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--hub-threshold" in result.stdout


@pytest.mark.integration
def test_run_against_agent_research_graph() -> None:
    """CLUSTER-04: command runs against the actual agent-research graph."""
    if not _agent_research_graph_available():
        pytest.skip(
            "agent-research code.db not initialised; run `cg update` from repo root"
        )
    repo = _repo_root()
    result = subprocess.run(
        [*_cg_cmd(), "--repo", str(repo), "--fmt", "json", "domain-clusters"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    payload = json.loads(result.stdout)
    # Must contain either at least one cluster OR a degenerate_warning explaining why.
    assert (
        len(payload["clusters"]) >= 1
        or payload["degenerate_warning"] is not None
    ), f"Expected clusters or a warning; got {payload}"
    # JSON shape locked by D-20.
    assert list(payload.keys()) == [
        "hub_threshold",
        "n_packages_total",
        "degenerate_warning",
        "clusters",
        "cross_cutting",
    ]


@pytest.mark.integration
def test_byte_identical_repeated_invocation() -> None:
    """CLUSTER-05: two invocations produce byte-identical stdout."""
    if not _agent_research_graph_available():
        pytest.skip(
            "agent-research code.db not initialised; run `cg update` from repo root"
        )
    repo = _repo_root()
    cmd = [*_cg_cmd(), "--repo", str(repo), "--fmt", "json", "domain-clusters"]
    out1 = subprocess.check_output(cmd)
    out2 = subprocess.check_output(cmd)
    assert out1 == out2, "Successive `cg domain-clusters` invocations produced different stdout"
