"""Worker dispatch tests for query orchestrator batches."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


class _FakeLLM:
    def __init__(self, content: str, tool_responses: list[Any] | None = None) -> None:
        self.content = content
        self.tool_responses = tool_responses or []
        self.bound_tools = []
        self.messages = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages):
        self.messages.append(messages)
        if self.tool_responses:
            return self.tool_responses.pop(0)
        return SimpleNamespace(content=self.content, tool_calls=[])


def test_parse_worker_tasks_accepts_librarian_and_code_reader_rows() -> None:
    from graph_wiki_core.commands.query_orchestrator import WorkerTask, parse_worker_tasks

    tasks = parse_worker_tasks(
        [
            {
                "worker": "librarian",
                "task_id": "lib-1",
                "page_path": "entities/scanner.md",
                "query_focus": "entity ownership",
                "expected_evidence": "who writes entity pages",
            },
            {
                "worker": "code_reader",
                "task_id": "code-1",
                "target_paths_or_hints": ["packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py"],
                "query_focus": "entity ownership",
                "expected_evidence": "source writer",
            },
        ]
    )

    assert tasks == (
        WorkerTask(
            worker="librarian",
            task_id="lib-1",
            query_focus="entity ownership",
            expected_evidence="who writes entity pages",
            page_path="entities/scanner.md",
            target_paths_or_hints=(),
        ),
        WorkerTask(
            worker="code_reader",
            task_id="code-1",
            query_focus="entity ownership",
            expected_evidence="source writer",
            page_path=None,
            target_paths_or_hints=("packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py",),
        ),
    )


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"worker": "archivist", "task_id": "x", "query_focus": "focus", "expected_evidence": "evidence"}, "worker"),
        ({"worker": "librarian", "task_id": "x", "query_focus": "focus", "expected_evidence": "evidence"}, "page_path"),
        (
            {
                "worker": "code_reader",
                "task_id": "x",
                "query_focus": "focus",
                "expected_evidence": "evidence",
                "target_paths_or_hints": [],
            },
            "target_paths_or_hints",
        ),
    ],
)
def test_parse_worker_tasks_rejects_invalid_rows(row: dict[str, object], message: str) -> None:
    from graph_wiki_core.commands.query_orchestrator import OrchestratorValidationError, parse_worker_tasks

    with pytest.raises(OrchestratorValidationError, match=message):
        parse_worker_tasks([row])


@pytest.mark.asyncio
async def test_run_worker_batch_dispatches_each_role_with_config_and_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import WorkerTask, run_worker_batch

    wiki = tmp_path / "wiki"
    repo = tmp_path / "repo"
    (wiki / "entities").mkdir(parents=True)
    (repo / "packages").mkdir(parents=True)
    (wiki / "entities" / "scanner.md").write_text("# Scanner\n\nScanner owns page writes.", encoding="utf-8")

    calls = []
    llms = {
        "librarian": _FakeLLM("wiki excerpt"),
        "code_reader": _FakeLLM("code excerpt"),
    }

    def fake_load_role_config(role: str) -> dict[str, object]:
        return {"model_id": f"default-{role}", "max_concurrency": 7 if role == "librarian" else 3}

    def fake_make_llm(role: str, *, model_override: str | None = None):
        calls.append((role, model_override))
        return llms[role]

    monkeypatch.setattr(mod, "load_role_config", fake_load_role_config)
    monkeypatch.setattr(mod, "make_llm", fake_make_llm)

    results = await run_worker_batch(
        (
            WorkerTask(
                worker="librarian",
                task_id="lib-1",
                page_path="entities/scanner.md",
                query_focus="ownership",
                expected_evidence="wiki facts",
            ),
            WorkerTask(
                worker="code_reader",
                task_id="code-1",
                target_paths_or_hints=("packages/scanner.py",),
                query_focus="ownership",
                expected_evidence="code facts",
            ),
        ),
        query="Who owns scanner pages?",
        wiki_root=wiki,
        repo_root=repo,
        trace_dir=tmp_path / "traces",
        role_model_overrides={"librarian": "override-lib", "code_reader": "override-code"},
    )

    assert calls == [("librarian", "override-lib"), ("code_reader", "override-code")]
    assert [(row["task_id"], row["worker"], row["status"], row["result"]) for row in results] == [
        ("lib-1", "librarian", "complete", "wiki excerpt"),
        ("code-1", "code_reader", "complete", "code excerpt"),
    ]


@pytest.mark.asyncio
async def test_run_worker_batch_records_worker_failures_without_dropping_successes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import WorkerTask, run_worker_batch
    from subagent_runtime.pool import FanOutResult, PerItemError

    wiki = tmp_path / "wiki"
    repo = tmp_path / "repo"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "ok.md").write_text("# OK\n\nUseful wiki evidence.", encoding="utf-8")

    async def fake_run_all(self, *, items, task, role, model_id, max_concurrency):
        result = FanOutResult()
        result.successes.append((items[0], "useful result"))
        result.errors.append(PerItemError(item=items[1], exception=RuntimeError("bedrock unavailable")))
        return result

    monkeypatch.setattr(mod, "load_role_config", lambda role: {"model_id": f"model-{role}", "max_concurrency": 2})
    monkeypatch.setattr(mod, "make_llm", lambda role, *, model_override=None: _FakeLLM("unused"))
    monkeypatch.setattr(mod.SubagentPool, "run_all", fake_run_all)

    results = await run_worker_batch(
        (
            WorkerTask(
                worker="librarian",
                task_id="lib-ok",
                page_path="entities/ok.md",
                query_focus="focus",
                expected_evidence="evidence",
            ),
            WorkerTask(
                worker="librarian",
                task_id="lib-fail",
                page_path="entities/fail.md",
                query_focus="focus",
                expected_evidence="evidence",
            ),
        ),
        query="question",
        wiki_root=wiki,
        repo_root=repo,
        trace_dir=tmp_path / "traces",
    )

    assert [(row["task_id"], row["status"]) for row in results] == [("lib-ok", "complete"), ("lib-fail", "error")]
    assert results[1]["error"] == "bedrock unavailable"


@pytest.mark.asyncio
async def test_code_reader_tool_uses_existing_bounded_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import WorkerTask, run_worker_batch

    repo = tmp_path / "repo"
    wiki = tmp_path / "wiki"
    repo.mkdir()
    wiki.mkdir()
    reads = []
    first = SimpleNamespace(tool_calls=[{"id": "call-1", "args": {"path": "packages/example.py"}}], content="")
    llm = _FakeLLM("bounded excerpt", tool_responses=[first])

    def fake_read_file_bounded(repo_root: Path, path: str) -> str:
        reads.append((repo_root, path))
        return "def example():\n    return 1\n"

    monkeypatch.setattr(mod, "load_role_config", lambda role: {"model_id": f"model-{role}", "max_concurrency": 1})
    monkeypatch.setattr(mod, "make_llm", lambda role, *, model_override=None: llm)
    monkeypatch.setattr(mod, "_read_file_bounded", fake_read_file_bounded)

    results = await run_worker_batch(
        (
            WorkerTask(
                worker="code_reader",
                task_id="code-1",
                target_paths_or_hints=("packages/example.py",),
                query_focus="example",
                expected_evidence="example implementation",
            ),
        ),
        query="How does example work?",
        wiki_root=wiki,
        repo_root=repo,
        trace_dir=tmp_path / "traces",
    )

    assert reads == [(repo, "packages/example.py")]
    assert results[0]["status"] == "complete"
    assert results[0]["result"] == "bounded excerpt"


@pytest.mark.asyncio
async def test_code_reader_rejects_out_of_scope_tool_path_before_bounded_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import WorkerTask, run_worker_batch

    repo = tmp_path / "repo"
    wiki = tmp_path / "wiki"
    repo.mkdir()
    wiki.mkdir()
    reads = []
    first = SimpleNamespace(tool_calls=[{"id": "call-1", "args": {"path": "packages/secret.py"}}], content="")
    llm = _FakeLLM("NO_RELEVANT_CONTENT", tool_responses=[first])

    def fake_read_file_bounded(repo_root: Path, path: str) -> str:
        reads.append((repo_root, path))
        return "secret = True\n"

    monkeypatch.setattr(mod, "load_role_config", lambda role: {"model_id": f"model-{role}", "max_concurrency": 1})
    monkeypatch.setattr(mod, "make_llm", lambda role, *, model_override=None: llm)
    monkeypatch.setattr(mod, "_read_file_bounded", fake_read_file_bounded)

    await run_worker_batch(
        (
            WorkerTask(
                worker="code_reader",
                task_id="code-1",
                target_paths_or_hints=("packages/allowed.py",),
                query_focus="example",
                expected_evidence="example implementation",
            ),
        ),
        query="How does example work?",
        wiki_root=wiki,
        repo_root=repo,
        trace_dir=tmp_path / "traces",
    )

    assert reads == []


@pytest.mark.asyncio
async def test_code_reader_allows_directoryish_hint_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from graph_wiki_core.commands import query_orchestrator as mod
    from graph_wiki_core.commands.query_orchestrator import WorkerTask, run_worker_batch

    repo = tmp_path / "repo"
    wiki = tmp_path / "wiki"
    repo.mkdir()
    wiki.mkdir()
    reads = []
    first = SimpleNamespace(tool_calls=[{"id": "call-1", "args": {"path": "packages/allowed/example.py"}}], content="")
    llm = _FakeLLM("bounded excerpt", tool_responses=[first])

    def fake_read_file_bounded(repo_root: Path, path: str) -> str:
        reads.append((repo_root, path))
        return "def example():\n    return 1\n"

    monkeypatch.setattr(mod, "load_role_config", lambda role: {"model_id": f"model-{role}", "max_concurrency": 1})
    monkeypatch.setattr(mod, "make_llm", lambda role, *, model_override=None: llm)
    monkeypatch.setattr(mod, "_read_file_bounded", fake_read_file_bounded)

    results = await run_worker_batch(
        (
            WorkerTask(
                worker="code_reader",
                task_id="code-1",
                target_paths_or_hints=("packages/allowed",),
                query_focus="example",
                expected_evidence="example implementation",
            ),
        ),
        query="How does example work?",
        wiki_root=wiki,
        repo_root=repo,
        trace_dir=tmp_path / "traces",
    )

    assert reads == [(repo, "packages/allowed/example.py")]
    assert results[0]["status"] == "complete"
