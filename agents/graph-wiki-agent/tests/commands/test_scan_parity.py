from __future__ import annotations

"""Parity tests for the scan command (Plan 05-04).

These tests build a minimal in-process vault using tmp_path so they run
without a real Bedrock connection. The scanner LLM is mocked to return a
deterministic stub body.

Requirements: CMD-02
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixture: minimal vault with log.md + packages dir (self-contained)
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_vault(tmp_path: Path) -> Path:
    """Create a minimal vault directory suitable for run_scan()."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("# Log\n", encoding="utf-8")
    (wiki / "packages").mkdir()

    # Minimal CLAUDE.md with a layout block so discover_workspaces works
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers:\n  - source: .\n    vault_dir: packages\n    classification: single-package\n    children_count: 1\n```\n",
        encoding="utf-8",
    )

    # index.md so update_index doesn't fail
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    return wiki


# ---------------------------------------------------------------------------
# Helper: build a FanOutResult with no successes (discovery-only run)
# ---------------------------------------------------------------------------


def _empty_fan_result():
    from subagent_runtime.pool import FanOutResult

    return FanOutResult()


# ---------------------------------------------------------------------------
# Common patch context for run_scan tests (no Bedrock, no real git repo)
# ---------------------------------------------------------------------------


def _scan_patches(wiki: Path, repo: Path):
    """Return a context manager that patches all Bedrock-touching code.

    Also patches resolve_wiki_and_repo so the scan doesn't need a real git repo.
    """
    from contextlib import ExitStack
    from unittest.mock import patch

    fake_state_gate = {"allowed": True, "reason": "test-mode", "head_commit": "abc123"}

    stack = ExitStack()
    stack.enter_context(patch("graph_wiki_agent.commands.scan.resolve_wiki_and_repo", return_value=(wiki, repo)))
    stack.enter_context(patch("graph_wiki_agent.commands.scan.compute_state_gate", return_value=fake_state_gate))
    stack.enter_context(patch("graph_wiki_agent.commands.scan.make_llm"))
    pool_mock = AsyncMock()
    pool_mock.run_all = AsyncMock(return_value=_empty_fan_result())
    pool_patch = stack.enter_context(patch("graph_wiki_agent.commands.scan.SubagentPool"))
    pool_patch.return_value = pool_mock
    stack.enter_context(patch("graph_wiki_agent.commands.scan.regenerate_dependencies_index"))
    stack.enter_context(patch("graph_wiki_agent.commands.scan.update_index"))
    stack.enter_context(patch("graph_wiki_agent.commands.scan.append_log"))
    stack.enter_context(patch("graph_wiki_agent.commands.scan.attach_changed_files"))
    return stack


# ---------------------------------------------------------------------------
# Test 1: ScanResult.added is a list
# ---------------------------------------------------------------------------


async def test_scan_result_added_is_list(minimal_vault: Path) -> None:
    """run_scan returns ScanResult whose fields are all correct types."""
    from graph_wiki_agent.commands.scan import ScanResult, run_scan

    repo = minimal_vault.parent
    with _scan_patches(minimal_vault, repo):
        result = await run_scan(vault_path=minimal_vault)

    assert isinstance(result, ScanResult)
    assert isinstance(result.added, list)
    assert isinstance(result.updated, list)
    assert isinstance(result.deleted, list)
    assert isinstance(result.renamed, list)
    assert isinstance(result.errors, list)


# ---------------------------------------------------------------------------
# Test 2: state_gate has expected keys
# ---------------------------------------------------------------------------


async def test_scan_state_gate_has_required_keys(minimal_vault: Path) -> None:
    """ScanResult.state_gate dict has {allowed, reason, head_commit} keys."""
    from graph_wiki_agent.commands.scan import run_scan

    repo = minimal_vault.parent
    with _scan_patches(minimal_vault, repo):
        result = await run_scan(vault_path=minimal_vault)

    assert "allowed" in result.state_gate
    assert "reason" in result.state_gate
    assert "head_commit" in result.state_gate


# ---------------------------------------------------------------------------
# Test 3: JSON round-trip via dataclasses.asdict
# ---------------------------------------------------------------------------


async def test_scan_result_json_roundtrip(minimal_vault: Path) -> None:
    """ScanResult serializes cleanly via dataclasses.asdict + json.dumps/loads."""
    from graph_wiki_agent.commands.scan import run_scan

    repo = minimal_vault.parent
    with _scan_patches(minimal_vault, repo):
        result = await run_scan(vault_path=minimal_vault)

    as_dict = dataclasses.asdict(result)
    json_str = json.dumps(as_dict, indent=2)
    parsed = json.loads(json_str)

    assert "added" in parsed
    assert "updated" in parsed
    assert "deleted" in parsed
    assert "renamed" in parsed
    assert "errors" in parsed
    assert "state_gate" in parsed
