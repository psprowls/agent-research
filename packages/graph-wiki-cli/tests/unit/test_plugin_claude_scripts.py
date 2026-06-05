from __future__ import annotations

import json
import runpy
import sys
import types
from pathlib import Path

import pytest


_SCRIPT_DIR = (
    Path(__file__).resolve().parents[4]
    / "plugins"
    / "graph-wiki"
    / "skills"
    / "graph-wiki"
    / "scripts"
)


def _install_claude_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    config_module = types.ModuleType("_config")
    config_module.backend_for = lambda command, repo=None: "claude"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_config", config_module)
    monkeypatch.syspath_prepend(str(_SCRIPT_DIR))


def _install_fake_wiki_io(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path | None = None,
    repo: Path | None = None,
) -> None:
    package = types.ModuleType("wiki_io")
    package.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io", package)

    workspace_module = types.ModuleType("wiki_io._workspace")

    def fake_resolve_wiki_and_repo(*args, **kwargs):
        resolved_workspace = workspace or Path(kwargs.get("workspace") or args[0])
        resolved_repo = repo or resolved_workspace.parent / "repo"
        return resolved_workspace / "wiki", resolved_repo

    workspace_module.resolve_wiki_and_repo = fake_resolve_wiki_and_repo  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io._workspace", workspace_module)


def test_wiki_search_script_claude_branch_formats_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)
    module = types.ModuleType("wiki_io.wiki_search")

    def fake_load_docs(wiki_path):
        return [
            {
                "path": "concepts/auth.md",
                "title": "Auth",
                "category": "concept",
                "summary": "auth pipeline",
                "text": "Middleware pipeline details.",
            }
        ]

    module.load_docs = fake_load_docs  # type: ignore[attr-defined]
    module.tokenize = lambda text: ["middleware"]  # type: ignore[attr-defined]
    module.bm25_scores = lambda docs, query_tokens: [(0, 1.0)]  # type: ignore[attr-defined]
    module.snippet = lambda text, query_tokens: "Middleware pipeline details."  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io.wiki_search", module)

    wiki = workspace / "wiki"
    page_dir = wiki / "concepts"
    page_dir.mkdir(parents=True)
    (page_dir / "auth.md").write_text(
        "---\ntitle: Auth\ncategory: concept\nsummary: auth pipeline\n---\n\nMiddleware pipeline details.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(sys, "argv", ["wiki_search.py", "--query", "middleware", "--limit", "3", "--json"])

    runpy.run_path(str(_SCRIPT_DIR / "wiki_search.py"), run_name="__main__")

    data = json.loads(capsys.readouterr().out)
    assert data["query"] == "middleware"
    assert data["hits"][0]["path"] == "concepts/auth.md"


def test_lint_wiki_script_claude_branch_validates_unknown_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)
    module = types.ModuleType("wiki_io.lint_wiki")
    module.OPTIONAL_GROUPS = {"dependency_layer"}  # type: ignore[attr-defined]
    module.scan = lambda *args, **kwargs: []  # type: ignore[attr-defined]
    module.print_report = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io.lint_wiki", module)

    (workspace / "wiki").mkdir(parents=True)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(sys, "argv", ["lint_wiki.py", "--check", "missing"])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT_DIR / "lint_wiki.py"), run_name="__main__")

    assert excinfo.value.code == 2
    assert "unknown --check group 'missing'" in capsys.readouterr().err


def test_graph_analyzer_script_claude_branch_formats_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.syspath_prepend(str(_SCRIPT_DIR))
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)
    module = types.ModuleType("wiki_io.graph_analyzer")
    module.analyze = lambda *args, **kwargs: {  # type: ignore[attr-defined]
        "total_pages": 2,
        "total_edges": 1,
        "top_outbound_hubs": [],
        "top_inbound_hubs": [],
        "orphans": [],
        "sinks": [],
        "components": [],
        "component_count": 1,
    }
    monkeypatch.setitem(sys.modules, "wiki_io.graph_analyzer", module)

    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "a.md").write_text("---\ntitle: A\n---\n\n[[b]]\n", encoding="utf-8")
    (wiki / "b.md").write_text("---\ntitle: B\n---\n\nBody.\n", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(sys, "argv", ["graph_analyzer.py", "--json", "--top", "2"])

    runpy.run_path(str(_SCRIPT_DIR / "graph_analyzer.py"), run_name="__main__")

    data = json.loads(capsys.readouterr().out)
    assert data["total_pages"] == 2
    assert data["total_edges"] == 1


def test_ingest_source_script_claude_branch_emits_json_brief(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)
    module = types.ModuleType("wiki_io.ingest_source")

    def fake_build_ingest_brief(*args, **kwargs):
        return {
            "title": "Demo Source",
            "suggested_summary_path": "sources/demo-source.md",
            "entity_match": {"uri": None, "entity_filename": None},
        }

    module.build_ingest_brief = fake_build_ingest_brief  # type: ignore[attr-defined]
    module.build_folder_ingest_brief = lambda *args, **kwargs: {  # type: ignore[attr-defined]
        "is_folder": True,
        "file_count": 1,
        "state_gate": {},
    }
    monkeypatch.setitem(sys.modules, "wiki_io.ingest_source", module)

    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    source = workspace / "raw" / "notes" / "demo.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Demo Source\n\nUseful source text.", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest_source.py", str(source), "--workspace", str(workspace), "--json"],
    )

    runpy.run_path(str(_SCRIPT_DIR / "ingest_source.py"), run_name="__main__")

    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "Demo Source"
    assert data["suggested_summary_path"].startswith("sources/")
    assert data["entity_match"] == {"uri": None, "entity_filename": None}


def test_init_vault_script_claude_branch_calls_init_wiki(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    calls: list[dict[str, object]] = []
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)

    module = types.ModuleType("wiki_io.init_vault")
    module.TOOL_FILES = {"claude-code": [], "codex": [], "all": []}  # type: ignore[attr-defined]

    def fake_init_wiki(wiki_path, repo_path, topic, tool, force, as_json=False, non_interactive=False):
        calls.append(
            {
                "wiki_path": wiki_path,
                "repo_path": repo_path,
                "topic": topic,
                "tool": tool,
                "force": force,
                "as_json": as_json,
                "non_interactive": non_interactive,
            }
        )
        result = {"status": "ok", "wiki_path": str(wiki_path), "repo_path": str(repo_path), "topic": topic}
        if as_json:
            print(json.dumps(result, indent=2))
        return result

    module.init_wiki = fake_init_wiki  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io.init_vault", module)

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "init_vault.py",
            "--repo",
            str(repo),
            "--workspace",
            str(workspace),
            "--topic",
            "Demo",
            "--tool",
            "claude-code",
            "--force",
            "--json",
        ],
    )

    runpy.run_path(str(_SCRIPT_DIR / "init_vault.py"), run_name="__main__")

    assert calls == [
        {
            "wiki_path": workspace / "wiki",
            "repo_path": repo,
            "topic": "Demo",
            "tool": "claude-code",
            "force": True,
            "as_json": True,
            "non_interactive": True,
        }
    ]
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
