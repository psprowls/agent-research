from __future__ import annotations

"""Unit tests for eval_harness.baseline.

All tests are pure unit — no subprocess spawned, no Bedrock calls.
Tests cover:
- _build_cmd(): command list construction, flags, plugin_dirs, model_override
- _make_snapshot(): baseline JSON schema (all 8 EVAL-08 fields including seed=None)
- _wiki_content_hash(): determinism and non-empty hex output
- _prompt_hash(): determinism
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eval_harness.baseline import (
    EVAL_SYSTEM_PROMPT_QA,
    BaselineRecorder,
    RunResult,
    _build_cmd,
    _prompt_hash,
    _wiki_content_hash,
)


# ---------------------------------------------------------------------------
# _build_cmd() tests
# ---------------------------------------------------------------------------


def test_build_cmd_flags(tmp_path: Path) -> None:
    """_build_cmd returns list starting with required claude -p flags."""
    result = _build_cmd(
        prompt="What is X?",
        worktree_path=tmp_path,
        system_prompt="test-prompt",
        plugin_dirs=None,
        model_override=None,
    )
    assert isinstance(result, list)
    assert result[0] == "claude"
    assert result[1] == "-p"
    assert "--output-format" in result
    idx = result.index("--output-format")
    assert result[idx + 1] == "stream-json"


def test_build_cmd_plugin_dir(tmp_path: Path) -> None:
    """_build_cmd includes --plugin-dir flag when plugin_dirs is provided."""
    plugin = Path("/some/plugin")
    result = _build_cmd(
        prompt="What is X?",
        worktree_path=tmp_path,
        system_prompt="test-prompt",
        plugin_dirs=[plugin],
        model_override=None,
    )
    assert "--plugin-dir" in result
    idx = result.index("--plugin-dir")
    assert result[idx + 1] == "/some/plugin"


def test_build_cmd_model_override(tmp_path: Path) -> None:
    """_build_cmd includes --model flag when model_override is provided."""
    result = _build_cmd(
        prompt="What is X?",
        worktree_path=tmp_path,
        system_prompt="test-prompt",
        plugin_dirs=None,
        model_override="sonnet-4-6",
    )
    assert "--model" in result
    idx = result.index("--model")
    assert result[idx + 1] == "sonnet-4-6"


def test_build_cmd_no_shell(tmp_path: Path) -> None:
    """_build_cmd returns a list (not a string); shell=True must never appear."""
    result = _build_cmd(
        prompt="What is X?",
        worktree_path=tmp_path,
        system_prompt="test-prompt",
        plugin_dirs=None,
        model_override=None,
    )
    assert isinstance(result, list), "cmd must be a list, never a shell string"
    # No element should be a boolean True (defensive)
    assert True not in result


def test_build_cmd_prompt_is_last(tmp_path: Path) -> None:
    """Prompt is always the final positional argument in the command list."""
    result = _build_cmd(
        prompt="What is X?",
        worktree_path=tmp_path,
        system_prompt="test-prompt",
        plugin_dirs=None,
        model_override=None,
    )
    assert result[-1] == "What is X?"


# ---------------------------------------------------------------------------
# BaselineRecorder._make_snapshot() tests
# ---------------------------------------------------------------------------


def test_baseline_schema(tmp_path: Path, fixture_workspace_path: Path) -> None:
    """_make_snapshot returns dict with all 8 required EVAL-08 schema keys."""
    recorder = BaselineRecorder(
        cases_path=Path("/dev/null"),
        workspace_path=fixture_workspace_path,
        baselines_dir=tmp_path,
    )
    case = {"case_id": "test-case-01", "query": "What is X?"}
    run_result = RunResult(
        final_status="success",
        budget_exceeded=False,
        wall_seconds=1.5,
        turns=2,
    )
    snapshot = recorder._make_snapshot(case, run_result, answer="The answer.")
    required_keys = {
        "case_id",
        "query",
        "answer",
        "model_arn",
        "prompt_hash",
        "wiki_content_hash",
        "timestamp_utc",
        "seed",
    }
    assert required_keys <= snapshot.keys(), f"Missing keys: {required_keys - snapshot.keys()}"


def test_baseline_seed_is_none(tmp_path: Path, fixture_workspace_path: Path) -> None:
    """snapshot['seed'] is always None (claude CLI has no seed parameter)."""
    recorder = BaselineRecorder(
        cases_path=Path("/dev/null"),
        workspace_path=fixture_workspace_path,
        baselines_dir=tmp_path,
    )
    case = {"case_id": "test-case-02", "query": "What is Y?"}
    run_result = RunResult(
        final_status="success",
        budget_exceeded=False,
        wall_seconds=2.0,
        turns=1,
    )
    snapshot = recorder._make_snapshot(case, run_result, answer="Another answer.")
    assert snapshot["seed"] is None


# ---------------------------------------------------------------------------
# _prompt_hash() tests
# ---------------------------------------------------------------------------


def test_prompt_hash_deterministic() -> None:
    """Same (case_id, query, system_prompt) always produces same prompt_hash."""
    h1 = _prompt_hash("case-01", "What is X?", "system-prompt-text")
    h2 = _prompt_hash("case-01", "What is X?", "system-prompt-text")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest is 64 chars


def test_prompt_hash_differs_on_input() -> None:
    """Different inputs produce different hashes."""
    h1 = _prompt_hash("case-01", "What is X?", "system-prompt")
    h2 = _prompt_hash("case-02", "What is X?", "system-prompt")
    assert h1 != h2


# ---------------------------------------------------------------------------
# _wiki_content_hash() tests
# ---------------------------------------------------------------------------


def test_wiki_content_hash(fixture_wiki_path: Path) -> None:
    """_wiki_content_hash returns a non-empty hex string."""
    result = _wiki_content_hash(fixture_wiki_path)
    assert isinstance(result, str)
    assert len(result) > 0
    # Should be a valid hex string
    int(result, 16)


def test_wiki_content_hash_deterministic(fixture_wiki_path: Path) -> None:
    """Calling _wiki_content_hash twice with same path returns same value."""
    h1 = _wiki_content_hash(fixture_wiki_path)
    h2 = _wiki_content_hash(fixture_wiki_path)
    assert h1 == h2
