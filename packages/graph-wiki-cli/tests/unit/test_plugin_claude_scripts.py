from __future__ import annotations

import json
import runpy
import sys
import types
from pathlib import Path

import pytest
from graph_wiki_core.page_kind_templates import kind_template_dirs

_SCRIPT_DIR = Path(__file__).resolve().parents[4] / "plugins" / "graph-wiki" / "skills" / "graph-wiki" / "scripts"


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

    def fake_resolve_wiki_and_repo(workspace_path=None, repo_path=None):
        resolved_workspace = workspace or workspace_path
        if resolved_workspace is None:
            resolved_workspace = Path.cwd() / "workspace"
        resolved_repo = repo_path or repo or resolved_workspace.parent / "repo"
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

    module.build_batch_ingest_brief = lambda *args, **kwargs: None  # type: ignore[attr-defined]  # not a batch → fall through
    module.build_ingest_brief = fake_build_ingest_brief  # type: ignore[attr-defined]
    module.build_folder_ingest_brief = lambda *args, **kwargs: {  # type: ignore[attr-defined]
        "is_folder": True,
        "file_count": 1,
        "state_gate": {},
    }
    module.build_skill_ingest_brief = lambda *args, **kwargs: {}  # type: ignore[attr-defined]  # not reached in this test
    module.resolve_skill_anchor = lambda path: None  # type: ignore[attr-defined]
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


def test_ingest_source_script_claude_branch_emits_skill_brief(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)
    module = types.ModuleType("wiki_io.ingest_source")

    module.build_batch_ingest_brief = lambda *args, **kwargs: None  # type: ignore[attr-defined]  # not a batch → fall through
    module.resolve_skill_anchor = lambda path: path  # type: ignore[attr-defined]  # non-None → skill branch
    module.build_skill_ingest_brief = lambda *args, **kwargs: {  # type: ignore[attr-defined]
        "is_skill": True,
        "source_type": "skill",
        "title": "My Skill",
        "slug": "my-skill",
        "suggested_summary_path": "sources/2026-06-my-skill.md",
        "guidance_dir": "guidance/",
        "included_files": ["SKILL.md", "references/advanced.md"],
        "excluded_files": ["scripts/helper.py"],
        "scripts_dominant": True,
        "warnings": ["scripts_dominant"],
        "entity_match": {"uri": None, "entity_filename": None},
        "state_gate": {},
    }
    module.build_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # must not be reached
    module.build_folder_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # must not be reached
    monkeypatch.setitem(sys.modules, "wiki_io.ingest_source", module)

    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    skill_dir = workspace / "raw" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# My Skill\n\nDoes things.\n", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest_source.py", str(skill_dir), "--workspace", str(workspace), "--json"],
    )

    runpy.run_path(str(_SCRIPT_DIR / "ingest_source.py"), run_name="__main__")

    data = json.loads(capsys.readouterr().out)
    assert data["is_skill"] is True
    assert data["source_type"] == "skill"
    assert data["included_files"][0] == "SKILL.md"

    # Human-readable branch (no --json) prints the skill summary.
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest_source.py", str(skill_dir), "--workspace", str(workspace)],
    )
    runpy.run_path(str(_SCRIPT_DIR / "ingest_source.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "Source type: skill" in out
    assert "Target guidance dir: guidance/" in out


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

    def fake_init_wiki(
        wiki_path, repo_path, topic, tool, force, as_json=False, non_interactive=False, extra_template_dirs=()
    ):
        calls.append(
            {
                "wiki_path": wiki_path,
                "repo_path": repo_path,
                "topic": topic,
                "tool": tool,
                "force": force,
                "as_json": as_json,
                "non_interactive": non_interactive,
                "extra_template_dirs": extra_template_dirs,
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
            "--non-interactive",
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
            "extra_template_dirs": kind_template_dirs(),
        }
    ]
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_init_vault_script_claude_branch_lands_kind_templates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The plugin shim's Claude branch must land the work.md + guidance.md
    page-kind templates in <wiki>/.templates/, just like the Bedrock path.

    Runs the REAL wiki_io.init_wiki (not stubbed) end-to-end through the shim,
    so it would fail if the shim forgot to forward the kind-template dirs. This
    mirrors core's test_bootstrap_copies_all_16_templates but exercises the
    Claude path. Regression guard for the plugin bootstrap dropping them.
    """
    _install_claude_backend(monkeypatch)

    workspace = tmp_path / "ws"
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
        ],
    )

    runpy.run_path(str(_SCRIPT_DIR / "init_vault.py"), run_name="__main__")

    templates = workspace / "wiki" / ".templates"
    assert (templates / "work.md").is_file(), "work.md kind template missing from plugin .templates/"
    assert (templates / "guidance.md").is_file(), "guidance.md kind template missing from plugin .templates/"


@pytest.mark.parametrize(
    "extra_argv, expected_limit",
    [
        ([], 10),
        (["--limit", "25"], 25),
        (["--all"], None),
        (["--all", "--limit", "5"], None),
    ],
)
def test_ingest_source_script_batch_limit_resolution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra_argv: list[str],
    expected_limit: int | None,
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)
    module = types.ModuleType("wiki_io.ingest_source")

    captured: dict[str, object] = {}

    # The fake always returns limited=True, so every parametrized case asserts the truncated form.
    def fake_batch(*args, **kwargs):
        captured["limit"] = kwargs.get("limit", "MISSING")
        return {
            "is_batch": True,
            "kind_folder": "specs",
            "root": str(kwargs.get("source_path", "")),
            "unit_count": 2,
            "total_count": 5,
            "limited": True,
            "units": [
                {"rel": "a.md", "unit_type": "file"},
                {"rel": "b.md", "unit_type": "file"},
            ],
            "state_gate": {},
        }

    module.build_batch_ingest_brief = fake_batch  # type: ignore[attr-defined]
    module.build_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached (batch)
    module.build_folder_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached
    module.build_skill_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached
    module.resolve_skill_anchor = lambda path: None  # type: ignore[attr-defined]  # not reached
    monkeypatch.setitem(sys.modules, "wiki_io.ingest_source", module)

    (workspace / "wiki").mkdir(parents=True)
    root = workspace / "raw" / "specs"
    root.mkdir(parents=True)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest_source.py", str(root), "--workspace", str(workspace), *extra_argv],
    )

    runpy.run_path(str(_SCRIPT_DIR / "ingest_source.py"), run_name="__main__")

    assert captured["limit"] == expected_limit
    out = capsys.readouterr().out
    assert "Batch: raw/specs (2 of 5 units, --all for everything)" in out


def test_ingest_source_script_batch_non_limited_print(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)
    module = types.ModuleType("wiki_io.ingest_source")

    def fake_batch(*args, **kwargs):
        return {
            "is_batch": True,
            "kind_folder": "specs",
            "root": str(kwargs.get("source_path", "")),
            "unit_count": 2,
            "total_count": 2,
            "limited": False,
            "units": [
                {"rel": "a.md", "unit_type": "file"},
                {"rel": "b.md", "unit_type": "file"},
            ],
            "state_gate": {},
        }

    module.build_batch_ingest_brief = fake_batch  # type: ignore[attr-defined]
    module.build_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached (batch)
    module.build_folder_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached
    module.build_skill_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached
    module.resolve_skill_anchor = lambda path: None  # type: ignore[attr-defined]  # not reached
    monkeypatch.setitem(sys.modules, "wiki_io.ingest_source", module)

    (workspace / "wiki").mkdir(parents=True)
    root = workspace / "raw" / "specs"
    root.mkdir(parents=True)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest_source.py", str(root), "--workspace", str(workspace)],
    )

    runpy.run_path(str(_SCRIPT_DIR / "ingest_source.py"), run_name="__main__")

    out = capsys.readouterr().out
    assert "Batch: raw/specs (2 units)" in out
    assert "of" not in out
    assert "--all for everything" not in out


def test_init_vault_script_claude_branch_forwards_repo_without_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_claude_backend(monkeypatch)
    calls: list[dict[str, object]] = []
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)

    module = types.ModuleType("wiki_io.init_vault")
    module.TOOL_FILES = {"claude-code": [], "codex": [], "all": []}  # type: ignore[attr-defined]

    def fake_init_wiki(
        wiki_path, repo_path, topic, tool, force, as_json=False, non_interactive=False, extra_template_dirs=()
    ):
        calls.append(
            {
                "wiki_path": wiki_path,
                "repo_path": repo_path,
                "topic": topic,
                "tool": tool,
                "force": force,
                "as_json": as_json,
                "non_interactive": non_interactive,
                "extra_template_dirs": extra_template_dirs,
            }
        )
        return {"status": "ok"}

    module.init_wiki = fake_init_wiki  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io.init_vault", module)

    repo = tmp_path / "repo-only"
    repo.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "init_vault.py",
            "--repo",
            str(repo),
            "--topic",
            "Demo",
        ],
    )

    runpy.run_path(str(_SCRIPT_DIR / "init_vault.py"), run_name="__main__")

    assert calls == [
        {
            "wiki_path": workspace / "wiki",
            "repo_path": repo,
            "topic": "Demo",
            "tool": "all",
            "force": False,
            "as_json": False,
            "non_interactive": False,
            "extra_template_dirs": kind_template_dirs(),
        }
    ]


def test_reconcile_doc_pointers_shim_reconciles_directly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The shim no longer delegates to wiki_io.reconcile_doc_pointers (deleted) —
    it calls work_io.doc_pointers.sweep and wiki_io._workspace.resolve_wiki_and_repo
    directly, inlined from the old wiki-io module."""
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)

    work_io_pkg = types.ModuleType("work_io")
    work_io_pkg.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "work_io", work_io_pkg)
    doc_pointers_module = types.ModuleType("work_io.doc_pointers")

    class _Report:
        rewrote = ["work/foo.md"]
        ok = ["work/bar.md"]
        unfixable: list[str] = []

    calls: list[tuple[Path, bool]] = []

    def fake_sweep(wiki_parent, dry_run=False):
        calls.append((wiki_parent, dry_run))
        return _Report()

    doc_pointers_module.sweep = fake_sweep  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "work_io.doc_pointers", doc_pointers_module)

    monkeypatch.setattr(sys, "argv", ["reconcile_doc_pointers.py"])

    runpy.run_path(str(_SCRIPT_DIR / "reconcile_doc_pointers.py"), run_name="__main__")

    assert calls == [(workspace, False)]
    out = capsys.readouterr().out
    assert "repointed: work/foo.md" in out
    assert "reconcile: 1 repointed, 1 ok, 0 unfixable" in out
