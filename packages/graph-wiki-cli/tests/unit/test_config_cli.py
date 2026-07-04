"""Smoke tests for the gw config Typer surface (logic is tested in core)."""

import json

from graph_wiki_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _seed(tmp_path):
    (tmp_path / ".graph-wiki.yaml").write_text(
        "version: 2\ninitialized_at: 2026-07-04\nplugins: []\n", encoding="utf-8"
    )


def test_set_get_roundtrip(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    r = runner.invoke(app, ["config", "set", "workflow.commit_strategy", "at-end"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["config", "get", "workflow.commit_strategy", "--json"])
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert (payload["value"], payload["origin"]) == ("at-end", "manifest")


def test_env_only_key_refused_with_exit_2(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    r = runner.invoke(app, ["config", "set", "GRAPH_WIKI_ROUTING_GUARD", "0"])
    assert r.exit_code == 2
    assert "env-only" in r.output


def test_list_json_masks_secret(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "sk-secret")
    r = runner.invoke(app, ["config", "list", "--json"])
    assert r.exit_code == 0
    rows = {row["key"]: row for row in json.loads(r.output)}
    assert rows["AI_GATEWAY_API_KEY"]["value"] == "••••"
    assert "sk-secret" not in r.output


def test_init_non_interactive(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)  # keep settings.local.json writes inside tmp
    r = runner.invoke(
        app,
        [
            "config",
            "init",
            "--model-routing",
            "guided",
            "--commit-strategy",
            "at-end",
            "--no-gates",
            "--no-transcript",
            "--no-write-env",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "workflow.model_routing" in r.output
