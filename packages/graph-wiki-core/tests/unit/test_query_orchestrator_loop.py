"""Orchestration-loop tests for query orchestrator safe degradation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _final_payload(**overrides: object) -> str:
    payload: dict[str, object] = {
        "answer_markdown": "The scanner owns entity page writes.",
        "citations": ["entities/scanner.md"],
        "evidence": [
            {
                "id": "ev1",
                "source_type": "wiki",
                "path": "entities/scanner.md",
                "freshness": "fresh",
                "staleness_reason": None,
                "excerpt": "Scanner owns entity page writes.",
                "line_refs": ["entities/scanner.md:12"],
            }
        ],
        "answer_evidence_map": [{"claim": "The scanner owns entity page writes.", "evidence_ids": ["ev1"]}],
        "worker_plan": [],
        "worker_results": [],
        "gaps": [],
        "confidence": "high",
    }
    payload.update(overrides)
    return json.dumps(payload)


@pytest.mark.asyncio
async def test_run_query_orchestrator_accepts_final_json_without_workers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.agent_loop import ToolLoopResult
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import run_query_orchestrator

    llm = SimpleNamespace()
    calls: list[tuple[str, str | None]] = []

    def fake_make_llm(role: str, *, model_override: str | None = None) -> object:
        calls.append((role, model_override))
        return llm

    async def fake_run_tool_loop(**kwargs: Any) -> ToolLoopResult:
        assert kwargs["llm"] is llm
        assert kwargs["tools"]
        assert kwargs["max_iterations"] > 0
        return ToolLoopResult(status="ok", final_text=_final_payload())

    async def fail_worker_batch(*args: Any, **kwargs: Any) -> tuple[()]:
        raise AssertionError("worker batch should not run")

    monkeypatch.setattr(mod, "make_llm", fake_make_llm)
    monkeypatch.setattr(mod, "run_tool_loop", fake_run_tool_loop)
    monkeypatch.setattr(mod, "run_worker_batch", fail_worker_batch)

    result = await run_query_orchestrator(
        query="Who owns entity page writes?",
        wiki_root=tmp_path,
        repo_root=tmp_path,
        initial_candidates=[],
        graph_tools=[],
        trace_dir=tmp_path / "traces",
        role_model_overrides={"query_orchestrator": "override-orch"},
    )

    assert calls == [("query_orchestrator", "override-orch")]
    assert result.output.answer_markdown == "The scanner owns entity page writes."
    assert result.trace_metadata["status"] == "ok"
    assert result.trace_metadata["worker_batches"] == 0


@pytest.mark.asyncio
async def test_run_query_orchestrator_runs_worker_batches_until_final_answer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.agent_loop import ToolLoopResult
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import run_query_orchestrator

    first_payload = _final_payload(
        answer_markdown="Need worker evidence.",
        confidence="low",
        worker_plan=[
            {
                "worker": "librarian",
                "task_id": "lib-1",
                "page_path": "entities/scanner.md",
                "query_focus": "entity ownership",
                "expected_evidence": "who writes entity pages",
            }
        ],
        worker_results=[],
    )
    second_payload = _final_payload(worker_results=[{"task_id": "lib-1", "status": "complete"}])
    loop_outputs = [first_payload, second_payload]
    observed_messages: list[list[Any]] = []
    worker_calls: list[tuple[str, ...]] = []

    async def fake_run_tool_loop(**kwargs: Any) -> ToolLoopResult:
        observed_messages.append(kwargs["messages"])
        return ToolLoopResult(status="ok", final_text=loop_outputs.pop(0))

    async def fake_run_worker_batch(worker_tasks: Any, **kwargs: Any) -> tuple[dict[str, str], ...]:
        worker_calls.append(tuple(task.task_id for task in worker_tasks))
        assert kwargs["query"] == "Who owns entity page writes?"
        return ({"task_id": "lib-1", "worker": "librarian", "status": "complete", "result": "Scanner evidence."},)

    monkeypatch.setattr(mod, "make_llm", lambda role, *, model_override=None: SimpleNamespace())
    monkeypatch.setattr(mod, "run_tool_loop", fake_run_tool_loop)
    monkeypatch.setattr(mod, "run_worker_batch", fake_run_worker_batch)

    result = await run_query_orchestrator(
        query="Who owns entity page writes?",
        wiki_root=tmp_path,
        repo_root=tmp_path,
        initial_candidates=[],
        graph_tools=[],
        trace_dir=tmp_path / "traces",
    )

    assert worker_calls == [("lib-1",)]
    assert result.output.worker_results[0]["task_id"] == "lib-1"
    assert result.trace_metadata["status"] == "ok"
    assert result.trace_metadata["worker_batches"] == 1
    second_turn_text = "\n".join(
        str(message.content) for message in observed_messages[1] if hasattr(message, "content")
    )
    assert "Worker batch 1 results" in second_turn_text
    assert "Scanner evidence." in second_turn_text


@pytest.mark.asyncio
async def test_run_query_orchestrator_degrades_invalid_json_to_low_confidence_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.agent_loop import ToolLoopResult
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import run_query_orchestrator

    async def fake_run_tool_loop(**kwargs: Any) -> ToolLoopResult:
        return ToolLoopResult(status="ok", final_text="{not-json")

    monkeypatch.setattr(mod, "make_llm", lambda role, *, model_override=None: SimpleNamespace())
    monkeypatch.setattr(mod, "run_tool_loop", fake_run_tool_loop)

    result = await run_query_orchestrator(
        query="Who owns entity page writes?",
        wiki_root=tmp_path,
        repo_root=tmp_path,
        initial_candidates=[],
        graph_tools=[],
        trace_dir=tmp_path / "traces",
    )

    assert result.output.confidence == "low"
    assert result.output.answer_markdown.startswith("Insufficient evidence")
    assert result.output.gaps[0].question == "Who owns entity page writes?"
    assert result.trace_metadata["status"] == "invalid_json"
    assert "Invalid JSON" in str(result.trace_metadata["error"])


@pytest.mark.asyncio
async def test_run_query_orchestrator_caps_worker_batches_at_five(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.agent_loop import ToolLoopResult
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import run_query_orchestrator

    plan_payload = _final_payload(
        answer_markdown="Need more worker evidence.",
        confidence="low",
        worker_plan=[
            {
                "worker": "librarian",
                "task_id": "lib-repeat",
                "page_path": "entities/scanner.md",
                "query_focus": "entity ownership",
                "expected_evidence": "who writes entity pages",
            }
        ],
        worker_results=[],
    )
    worker_calls = 0

    async def fake_run_tool_loop(**kwargs: Any) -> ToolLoopResult:
        return ToolLoopResult(status="ok", final_text=plan_payload)

    async def fake_run_worker_batch(worker_tasks: Any, **kwargs: Any) -> tuple[dict[str, str], ...]:
        nonlocal worker_calls
        worker_calls += 1
        return ({"task_id": f"lib-{worker_calls}", "worker": "librarian", "status": "complete", "result": "More."},)

    monkeypatch.setattr(mod, "make_llm", lambda role, *, model_override=None: SimpleNamespace())
    monkeypatch.setattr(mod, "run_tool_loop", fake_run_tool_loop)
    monkeypatch.setattr(mod, "run_worker_batch", fake_run_worker_batch)

    result = await run_query_orchestrator(
        query="Who owns entity page writes?",
        wiki_root=tmp_path,
        repo_root=tmp_path,
        initial_candidates=[],
        graph_tools=[],
        trace_dir=tmp_path / "traces",
    )

    assert worker_calls == 5
    assert result.output.confidence == "low"
    assert result.trace_metadata["status"] == "capped"
    assert result.trace_metadata["worker_batches"] == 5
