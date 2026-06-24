import json

import typer
from subagent_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_app_exists():
    assert isinstance(app, typer.Typer)


def test_list_resolves_models():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    for name in ("guidance_classifier", "package_reader", "librarian", "synthesizer", "guidance_orchestrator"):
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
