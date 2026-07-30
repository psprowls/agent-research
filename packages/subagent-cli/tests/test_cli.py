import json

from subagent_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_list_resolves_models():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    for name in ("guidance_classifier", "prose_refresher", "librarian", "synthesizer", "guidance_orchestrator"):
        assert name in result.stdout


def test_list_json():
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert {r["name"] for r in rows} >= {"librarian", "synthesizer"}
    assert all(r["model_id"] for r in rows)


def test_unknown_adapter_exits_1():
    result = runner.invoke(app, ["run", "nope", "--query", "x"])
    assert result.exit_code == 1
    assert "librarian" in result.stdout  # lists valid names


def test_all_on_query_adapter_exits_1(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    # workspace resolution will fail first (no manifest) → still non-zero, message present
    result = runner.invoke(app, ["run", "librarian", "--query", "x", "--all"])
    assert result.exit_code == 1


def test_list_shows_loop_kind():
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    by_name = {r["name"]: r for r in rows}
    assert by_name["query_orchestrator"]["kind"] == "tool-loop"
    assert by_name["librarian"]["kind"] == "single-shot"


def test_loop_unknown_name_exits_1():
    result = runner.invoke(app, ["loop", "nope", "--query", "x"])
    assert result.exit_code == 1
    assert "query_orchestrator" in result.stdout  # lists valid loop names


def test_loop_missing_query_exits_1(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    result = runner.invoke(app, ["loop", "query_orchestrator"])
    assert result.exit_code == 1
    assert "--query" in result.stdout


def test_loop_renders_and_json(tmp_path, monkeypatch):
    import subagent_cli.cli as cli_mod
    from subagent_cli.adapters.base import LoopOutcome

    class _FakeCtx:
        workspace = tmp_path
        repo_root = tmp_path

        def close(self):
            pass

    async def fake_run_loop(adapter, ctx, item):
        return LoopOutcome(
            item_id=item[:80],
            role="query_orchestrator",
            model_id="vendor.model-1:0",
            region="us-east-1",
            answer="## Answer\nFoo.",
            structured={"confidence": "high", "citations": [], "gaps": []},
            trace_metadata={"status": "ok", "worker_batches": 1},
            latency_s=1.0,
            trace_path="/ws/.graph-wiki/traces/x.jsonl",
            note="n",
        )

    monkeypatch.setattr(cli_mod, "run_loop", fake_run_loop)
    monkeypatch.setattr(cli_mod, "_build_context", lambda ws, repo: _FakeCtx())
    monkeypatch.setattr(
        cli_mod,
        "resolve",
        lambda cwd: type("C", (), {"workspace": tmp_path, "repo_root": tmp_path})(),
    )

    result = runner.invoke(app, ["loop", "query_orchestrator", "--query", "what does foo do?"])
    assert result.exit_code == 0
    assert "Foo." in result.stdout and "ok" in result.stdout

    result_json = runner.invoke(app, ["loop", "query_orchestrator", "--query", "q", "--json"])
    assert result_json.exit_code == 0
    rec = json.loads(result_json.stdout)
    assert rec["answer"] == "## Answer\nFoo." and rec["trace_metadata"]["status"] == "ok"


def test_loop_bedrock_access_denied_exits_2(tmp_path, monkeypatch):
    import subagent_cli.cli as cli_mod
    from model_adapter import BedrockAccessDenied

    class _FakeCtx:
        workspace = tmp_path
        repo_root = tmp_path

        def close(self):
            pass

    async def fake_run_loop(adapter, ctx, item):
        raise BedrockAccessDenied("denied")

    monkeypatch.setattr(cli_mod, "run_loop", fake_run_loop)
    monkeypatch.setattr(cli_mod, "_build_context", lambda ws, repo: _FakeCtx())
    monkeypatch.setattr(
        cli_mod,
        "resolve",
        lambda cwd: type("C", (), {"workspace": tmp_path, "repo_root": tmp_path})(),
    )

    result = runner.invoke(app, ["loop", "query_orchestrator", "--query", "q"])
    assert result.exit_code == 2


def test_loop_runtime_error_exits_1(tmp_path, monkeypatch):
    import subagent_cli.cli as cli_mod

    class _FakeCtx:
        workspace = tmp_path
        repo_root = tmp_path

        def close(self):
            pass

    async def fake_run_loop(adapter, ctx, item):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_mod, "run_loop", fake_run_loop)
    monkeypatch.setattr(cli_mod, "_build_context", lambda ws, repo: _FakeCtx())
    monkeypatch.setattr(
        cli_mod,
        "resolve",
        lambda cwd: type("C", (), {"workspace": tmp_path, "repo_root": tmp_path})(),
    )

    result = runner.invoke(app, ["loop", "query_orchestrator", "--query", "q"])
    assert result.exit_code == 1
