from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml
from graph_io.schema import SCHEMA_VERSION
from graph_wiki_core.commands.guidance_scan import run_guidance_scan
from guidance_io.index_store import load_index


def _seed_graph(db_path: Path, files: list[str]) -> None:
    """Minimal nodes table with file rows the scan enumerates."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE nodes (id INTEGER PRIMARY KEY, kind TEXT, name TEXT, "
        "path TEXT, line INTEGER, attrs_json TEXT, uri TEXT)"
    )
    conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    for i, rel in enumerate(files, start=1):
        conn.execute(
            "INSERT INTO nodes (id, kind, name, path, uri) VALUES (?,?,?,?,?)",
            (i, "file", Path(rel).name, rel, None),
        )
    conn.commit()
    conn.close()


def _write_topic(ws: Path, topic: str) -> None:
    (ws / "wiki" / "guidance" / topic).mkdir(parents=True, exist_ok=True)


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage_metadata = None


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def ainvoke(self, messages):  # noqa: ANN001
        return _FakeResp(self._reply)


class _FakePool:
    """Runs each task inline; mirrors SubagentPool.run_all's FanOutResult shape."""

    def __init__(self, trace_dir: Path) -> None:
        self.trace_dir = trace_dir

    async def run_all(self, items, task, role, *, model_id, max_concurrency, recursion_limit=None):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        for item in items:
            out = await task(item)
            value = getattr(out, "value", out)
            result.successes.append((item, value))
        return result


class _FakeTaskResult:
    def __init__(self, value, response=None) -> None:
        self.value = value
        self.response = response


def _fake_load_role_config(role: str) -> dict:
    return {"model_id": "fake", "region": "us-east-1", "max_tokens": 256, "max_concurrency": 4}


async def test_seed_tags_writes_allowlist_and_returns_early(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    gdir = ws / "wiki" / "guidance" / "python"
    gdir.mkdir(parents=True)
    fm = {"title": "T", "tags": ["retry", "io"]}
    (gdir / "a.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n## Guidance\nx\n", encoding="utf-8"
    )
    result = await run_guidance_scan(workspace_path=ws, repo_path=tmp_path / "repo", seed_tags=True)
    assert sorted(result.seeded_tags) == ["io", "retry"]
    assert (ws / "wiki" / "guidance" / "tags.yaml").exists()
    assert result.total == 0  # no classification happened


async def test_scan_classifies_and_writes_index(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    repo = tmp_path / "repo"
    _write_topic(ws, "python")
    (ws / "wiki" / "guidance" / "tags.yaml").write_text(yaml.safe_dump(["retry"]), encoding="utf-8")
    rel = "pkg/a.py"
    (repo / "pkg").mkdir(parents=True)
    (repo / rel).write_text("def f():\n    return 1\n", encoding="utf-8")
    _seed_graph(ws / ".graph-wiki" / "code.db", [rel])

    result = await run_guidance_scan(
        workspace_path=ws,
        repo_path=repo,
        stamp="2026-06-22",
        make_llm_fn=lambda role, **kw: _FakeLLM("topics: [python]\ntags: [retry]\n"),
        load_role_config_fn=_fake_load_role_config,
        subagent_pool_type=_FakePool,
        task_result_type=_FakeTaskResult,
    )
    assert rel in result.scanned
    idx = load_index(ws)
    assert idx.files[rel].topics == ["python"]
    assert idx.files[rel].tags == ["retry"]
    assert idx.vocab_hash  # stamped


async def test_scan_skips_unchanged(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    repo = tmp_path / "repo"
    _write_topic(ws, "python")
    (ws / "wiki" / "guidance" / "tags.yaml").write_text(yaml.safe_dump(["retry"]), encoding="utf-8")
    rel = "pkg/a.py"
    (repo / "pkg").mkdir(parents=True)
    (repo / rel).write_text("def f():\n    return 1\n", encoding="utf-8")
    _seed_graph(ws / ".graph-wiki" / "code.db", [rel])

    seams = dict(
        make_llm_fn=lambda role, **kw: _FakeLLM("topics: [python]\ntags: [retry]\n"),
        load_role_config_fn=_fake_load_role_config,
        subagent_pool_type=_FakePool,
        task_result_type=_FakeTaskResult,
    )
    await run_guidance_scan(workspace_path=ws, repo_path=repo, stamp="2026-06-22", **seams)
    second = await run_guidance_scan(workspace_path=ws, repo_path=repo, stamp="2026-06-22", **seams)
    assert rel in second.skipped
    assert rel not in second.scanned
