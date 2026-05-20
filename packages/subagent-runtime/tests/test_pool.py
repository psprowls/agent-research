from __future__ import annotations

"""Unit tests for subagent_runtime.pool.SubagentPool.

Covers partial failure isolation, semaphore concurrency cap, JSONL trace
completeness (success and error paths), token metadata None guard, trace
writer OSError isolation, multi-run lineage, and RunnableConfig recursion
limit propagation.

No real Bedrock calls — all LLM paths are mocked via conftest fixtures.
"""

import asyncio
import json
import logging
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Test 1: FanOutResult dataclass returned on empty input
# ---------------------------------------------------------------------------


async def test_fanout_returns_fanout_result_dataclass(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    task = make_task()
    result = await pool.run_all(
        items=[],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )
    assert isinstance(result, FanOutResult)
    assert result.successes == []
    assert result.errors == []


# ---------------------------------------------------------------------------
# Test 2: Partial failure isolation — 1 of 4 fails
# ---------------------------------------------------------------------------


async def test_partial_failure_isolation(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError

    task = make_task(raise_for={"bad"})
    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=["a", "b", "bad", "c"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )
    assert len(result.successes) == 3
    assert len(result.errors) == 1
    assert result.errors[0].item == "bad"
    assert isinstance(result.errors[0].exception, ValueError)


# ---------------------------------------------------------------------------
# Test 3: First task failure does not cancel siblings
# ---------------------------------------------------------------------------


async def test_first_task_failure_does_not_cancel_siblings(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError

    task = make_task(raise_for={"bad"})
    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=["bad", "a", "b", "c"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )
    assert len(result.successes) == 3
    assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Test 4: All tasks fail
# ---------------------------------------------------------------------------


async def test_all_tasks_fail(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError

    task = make_task(raise_for={"a", "b", "c", "d"})
    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=["a", "b", "c", "d"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )
    assert len(result.successes) == 0
    assert len(result.errors) == 4


# ---------------------------------------------------------------------------
# Test 5: Semaphore caps concurrency
# ---------------------------------------------------------------------------


async def test_semaphore_caps_concurrency(tmp_path):
    from subagent_runtime.pool import SubagentPool

    peak = 0
    current = 0

    async def counting_task(item):
        nonlocal peak, current
        current += 1
        if current > peak:
            peak = current
        await asyncio.sleep(0.01)
        current -= 1
        return item

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=list(range(6)),
        task=counting_task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=2,
    )
    assert peak <= 2
    assert len(result.successes) == 6


# ---------------------------------------------------------------------------
# Test 6: max_concurrency=1 serializes tasks
# ---------------------------------------------------------------------------


async def test_max_concurrency_one_serializes_tasks(tmp_path):
    from subagent_runtime.pool import SubagentPool

    peak = 0
    current = 0

    async def counting_task(item):
        nonlocal peak, current
        current += 1
        if current > peak:
            peak = current
        await asyncio.sleep(0.01)
        current -= 1
        return item

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=list(range(3)),
        task=counting_task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=1,
    )
    assert peak == 1
    assert len(result.successes) == 3


# ---------------------------------------------------------------------------
# Test 7: Trace record completeness on success path
# ---------------------------------------------------------------------------


async def test_trace_record_completeness_success_path(tmp_path, fake_llm_response):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)

    async def task(item):
        return fake_llm_response

    result = await pool.run_all(
        items=["item-1"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    assert len(result.successes) == 1

    trace_files = list(traces_dir.glob("*.jsonl"))
    assert len(trace_files) == 1

    lines = trace_files[0].read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    required_keys = {
        "schema_version",
        "role", "model_id", "prompt_hash", "item_id",
        "status", "latency_ms", "tokens_in", "tokens_out",
        "cost_usd", "timestamp",
    }
    assert required_keys.issubset(record.keys())
    assert record["schema_version"] == 1
    assert record["status"] == "success"
    assert record["tokens_in"] == 10
    assert record["tokens_out"] == 5
    assert record["cost_usd"] is None


# ---------------------------------------------------------------------------
# Test 8: Trace record on error path
# ---------------------------------------------------------------------------


async def test_trace_record_error_path(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)
    task = make_task(raise_for={"bad"})

    result = await pool.run_all(
        items=["bad"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    assert len(result.errors) == 1

    trace_files = list(traces_dir.glob("*.jsonl"))
    assert len(trace_files) == 1

    lines = trace_files[0].read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["schema_version"] == 1
    assert record["status"] == "error"
    assert "error" in record
    assert record["error"]  # non-empty string
    assert record["tokens_in"] is None
    assert record["tokens_out"] is None


# ---------------------------------------------------------------------------
# Test 9: usage_metadata=None guard — no AttributeError
# ---------------------------------------------------------------------------


async def test_token_metadata_none_guard(tmp_path, fake_llm_response_error):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)

    async def task(item):
        return fake_llm_response_error  # usage_metadata is None

    # Must not raise; tokens_in and tokens_out must be null, not 0, not missing
    result = await pool.run_all(
        items=["x"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    assert len(result.successes) == 1

    trace_files = list(traces_dir.glob("*.jsonl"))
    lines = trace_files[0].read_text().strip().splitlines()
    record = json.loads(lines[0])

    assert record["tokens_in"] is None
    assert record["tokens_out"] is None


# ---------------------------------------------------------------------------
# Test 10: _write_trace OSError is logged as WARNING, does not mask success
# ---------------------------------------------------------------------------


async def test_write_trace_oserror_logged_not_raised(tmp_path, fake_llm_response, caplog, monkeypatch):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)  # mkdir happens here — dir exists

    # Monkeypatch Path.open to raise OSError on any open call
    original_open = Path.open

    def raising_open(self, *args, **kwargs):
        if str(self).endswith(".jsonl"):
            raise OSError("simulated write failure")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", raising_open)

    async def task(item):
        return fake_llm_response

    with caplog.at_level(logging.WARNING):
        result = await pool.run_all(
            items=["a"],
            task=task,
            role="scanner",
            model_id="test-model-id",
            max_concurrency=4,
        )

    # Success must NOT be converted to PerItemError due to trace failure
    assert len(result.successes) == 1
    assert len(result.errors) == 0

    # A WARNING must have been logged about the trace failure
    warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("simulated write failure" in msg or "Trace write failed" in msg for msg in warning_messages)


# ---------------------------------------------------------------------------
# Test 11: Two sequential run_all() calls produce two separate trace files
# ---------------------------------------------------------------------------


async def test_separate_trace_files_per_run_all(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)
    task = make_task()

    await pool.run_all(
        items=["a"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    # UUID suffix on trace filename guarantees uniqueness even within the same wall-clock second (CR-02 fix)

    await pool.run_all(
        items=["b"],
        task=task,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
    )

    trace_files = list(traces_dir.glob("*.jsonl"))
    assert len(trace_files) == 2
    # Both must be distinct paths
    assert trace_files[0] != trace_files[1]


# ---------------------------------------------------------------------------
# Test 12: RunnableConfig recursion_limit is propagated to every task call
# ---------------------------------------------------------------------------


async def test_recursion_limit_propagated_to_runnableconfig(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, call
    import subagent_runtime.pool as pool_module

    traces_dir = tmp_path / "traces"

    # --- Part A: explicit recursion_limit=42 ---
    mock_rc_a = MagicMock(side_effect=lambda **kwargs: kwargs)
    monkeypatch.setattr(pool_module, "RunnableConfig", mock_rc_a)

    pool_a = pool_module.SubagentPool(trace_dir=traces_dir)

    received_configs_a: list = []

    async def simple_task_a(item, config):
        received_configs_a.append(config)
        return MagicMock(usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})

    await pool_a.run_all(
        items=["a", "b"],
        task=simple_task_a,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
        recursion_limit=42,
    )

    # RunnableConfig must have been called twice (once per item)
    assert mock_rc_a.call_count == 2
    for c in mock_rc_a.call_args_list:
        assert c.kwargs.get("recursion_limit") == 42

    # Config must have been DELIVERED to the task callable (CR-01 fix)
    assert len(received_configs_a) == 2, f"Expected 2 configs delivered; got {len(received_configs_a)}"
    for cfg in received_configs_a:
        assert isinstance(cfg, dict), f"Expected dict (mocked RunnableConfig); got {type(cfg)}"
        assert cfg.get("recursion_limit") == 42, f"Expected recursion_limit=42; got {cfg}"

    # --- Part B: default_recursion_limit from __init__ ---
    mock_rc_b = MagicMock(side_effect=lambda **kwargs: kwargs)
    monkeypatch.setattr(pool_module, "RunnableConfig", mock_rc_b)

    pool_b = pool_module.SubagentPool(trace_dir=traces_dir, default_recursion_limit=99)

    received_configs_b: list = []

    async def simple_task_b(item, config):
        received_configs_b.append(config)
        return MagicMock(usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})

    await pool_b.run_all(
        items=["x"],
        task=simple_task_b,
        role="scanner",
        model_id="test-model-id",
        max_concurrency=4,
        # recursion_limit NOT passed — should use default_recursion_limit=99
    )

    assert mock_rc_b.call_count == 1
    assert mock_rc_b.call_args.kwargs.get("recursion_limit") == 99

    # Config must have been DELIVERED to the task callable (CR-01 fix)
    assert len(received_configs_b) == 1, f"Expected 1 config delivered; got {len(received_configs_b)}"
    assert received_configs_b[0].get("recursion_limit") == 99, f"Expected recursion_limit=99; got {received_configs_b[0]}"


# ---------------------------------------------------------------------------
# Test 13 (Phase 9 OBS-04): batch_cancelled terminal record stamps schema_version: 1
# ---------------------------------------------------------------------------


async def test_batch_terminal_includes_schema_version(tmp_path):
    """When a fan-out is cancelled mid-flight, the batch_cancelled terminal
    record written by _write_batch_terminal carries schema_version: 1
    (Phase 9 D-01 / D-02 — schema_version on every record, integer 1).
    """
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)

    async def slow_task(item):
        await asyncio.sleep(3)  # long enough that cancel always arrives in-flight
        return MagicMock(
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
        )

    task = asyncio.ensure_future(
        pool.run_all(
            items=["a", "b"],
            task=slow_task,
            role="scanner",
            model_id="test-model-id",
            max_concurrency=4,
        )
    )

    # Yield long enough for both _run_one coroutines to be in flight inside slow_task.
    # Same pattern as agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py.
    await asyncio.sleep(0.05)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    trace_files = list(traces_dir.glob("*.jsonl"))
    assert len(trace_files) == 1, f"Expected one trace file, got {len(trace_files)}"

    lines = [
        json.loads(line)
        for line in trace_files[0].read_text().splitlines()
        if line.strip()
    ]
    batch_records = [line for line in lines if line.get("event") == "batch_cancelled"]
    assert len(batch_records) == 1, (
        f"Expected exactly one batch_cancelled record, got {len(batch_records)}; "
        f"lines: {lines}"
    )
    assert batch_records[0]["schema_version"] == 1

    # Per-item cancelled records (if any) also carry schema_version: 1
    cancelled_records = [line for line in lines if line.get("status") == "cancelled"]
    for record in cancelled_records:
        assert record["schema_version"] == 1


# ---------------------------------------------------------------------------
# Phase 16-02 G-01 closure: TaskResult contract — opt-in usage_metadata pass-through
# ---------------------------------------------------------------------------


class _StubResponseWithUsage:
    """Plain stub with a real dict usage_metadata (NOT a MagicMock).

    MagicMock auto-resolves attributes and returns MagicMock objects for
    usage_metadata, which poisons the isinstance(meta, dict) guard in
    trace_io.write_trace_record. A bare class with a real dict matches the
    shape of a ChatBedrockConverse response without that hazard. See 16-01
    SUMMARY auto-fix #1.
    """

    def __init__(self, usage_metadata: dict | None) -> None:
        self.usage_metadata = usage_metadata
        self.content = "stub-content"


async def test_pool_writes_tokens_when_callback_returns_taskresult(tmp_path):
    """TaskResult(value=..., response=stub_with_usage_metadata) -> trace
    record carries tokens_in / tokens_out; successes carries only the value.
    """
    from subagent_runtime.pool import SubagentPool, TaskResult

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)
    stub = _StubResponseWithUsage(
        usage_metadata={"input_tokens": 5, "output_tokens": 7, "total_tokens": 12}
    )

    async def task(item):
        return TaskResult(value="hello", response=stub)

    result = await pool.run_all(
        items=["item-a"],
        task=task,
        role="librarian",
        model_id="test-model-id",
        max_concurrency=4,
    )

    # successes must carry the SCALAR value, NOT the TaskResult wrapper —
    # downstream consumers unchanged.
    assert result.successes == [("item-a", "hello")]
    assert result.errors == []

    trace_files = list(traces_dir.glob("*.jsonl"))
    assert len(trace_files) == 1
    lines = trace_files[0].read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["status"] == "success"
    assert record["tokens_in"] == 5
    assert record["tokens_out"] == 7


async def test_pool_preserves_scalar_callback_contract_backward_compat(tmp_path):
    """A callback that returns a bare scalar (today's contract) keeps
    working: successes carries the scalar verbatim; trace tokens are None
    because a string has no usage_metadata attribute.
    """
    from subagent_runtime.pool import SubagentPool

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)

    async def task(item):
        return "bare-scalar-string"

    result = await pool.run_all(
        items=["item-b"],
        task=task,
        role="librarian",
        model_id="test-model-id",
        max_concurrency=4,
    )

    assert result.successes == [("item-b", "bare-scalar-string")]

    trace_files = list(traces_dir.glob("*.jsonl"))
    lines = trace_files[0].read_text().strip().splitlines()
    record = json.loads(lines[0])
    assert record["tokens_in"] is None
    assert record["tokens_out"] is None


async def test_pool_taskresult_with_none_response_writes_null_tokens(tmp_path):
    """TaskResult(value=None, response=None) writes a success record with
    tokens_in/tokens_out as None; successes carries (item, None).
    """
    from subagent_runtime.pool import SubagentPool, TaskResult

    traces_dir = tmp_path / "traces"
    pool = SubagentPool(trace_dir=traces_dir)

    async def task(item):
        return TaskResult(value=None, response=None)

    result = await pool.run_all(
        items=["item-c"],
        task=task,
        role="linter",
        model_id="test-model-id",
        max_concurrency=4,
    )

    assert result.successes == [("item-c", None)]

    trace_files = list(traces_dir.glob("*.jsonl"))
    lines = trace_files[0].read_text().strip().splitlines()
    record = json.loads(lines[0])
    assert record["status"] == "success"
    assert record["tokens_in"] is None
    assert record["tokens_out"] is None
