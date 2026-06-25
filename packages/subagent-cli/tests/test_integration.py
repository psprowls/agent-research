import os

import pytest
from subagent_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.mark.integration
def test_run_guidance_classifier_live():
    ws = os.environ.get("GRAPH_WIKI_WORKSPACE")
    if not ws:
        pytest.skip("set GRAPH_WIKI_WORKSPACE to a real workspace for the live test")
    # pick a small real file from the indexed repo
    result = runner.invoke(
        app,
        ["run", "guidance_classifier", "--file", "packages/workspace-io/src/workspace_io/paths.py"],
    )
    assert result.exit_code == 0
    assert "tok" in result.stdout  # footer with token counts


@pytest.mark.integration
def test_loop_query_orchestrator_live():
    ws = os.environ.get("GRAPH_WIKI_WORKSPACE")
    if not ws:
        pytest.skip("set GRAPH_WIKI_WORKSPACE to a real workspace for the live loop test")
    result = runner.invoke(
        app,
        ["loop", "query_orchestrator", "--query", "What does the model-adapter package do?"],
    )
    assert result.exit_code == 0
    assert "ANSWER" in result.stdout  # answer section rendered
    assert "status" in result.stdout  # structured summary line present
