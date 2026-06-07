from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from graph_wiki_core.commands.package_reader import (
    MAX_PACKAGE_READER_ITERS,
    PackageReaderItem,
    build_package_reader_prompt,
    build_package_reader_tools,
    parse_package_reader_output,
    run_package_reader,
)
from langchain_core.tools import tool


def test_parse_package_reader_output_filters_invalid_entries() -> None:
    raw = json.dumps(
        {
            "sections": [
                {"heading": "Purpose", "replacement_markdown": "Owns scan orchestration."},
                {"heading": "Public API", "replacement_markdown": "TODO later"},
                {"heading": "Unknown", "replacement_markdown": "Must be ignored."},
                {"heading": "Purpose", "replacement_markdown": ""},
            ]
        }
    )

    parsed = parse_package_reader_output(raw, requested_headings=["Purpose", "Public API"])

    assert parsed == {"Purpose": "Owns scan orchestration."}


def test_parse_package_reader_output_accepts_fenced_json() -> None:
    raw = '```json\n{"sections":[{"heading":"Purpose","replacement_markdown":"Does real work."}]}\n```'

    parsed = parse_package_reader_output(raw, requested_headings=["Purpose"])

    assert parsed == {"Purpose": "Does real work."}


def test_build_package_reader_tools_rejects_reads_outside_entity_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    root = repo / "packages" / "pkg-a"
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'pkg-a'\n", encoding="utf-8")
    (repo / "secret.txt").write_text("secret", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    tools = {
        agent_tool.name: agent_tool
        for agent_tool in build_package_reader_tools(repo=repo, entity_root="packages/pkg-a", wiki=wiki, graph_tools=[])
    }

    assert "name = 'pkg-a'" in tools["read_repo_file"].invoke({"path": "pyproject.toml"})
    assert tools["read_repo_file"].invoke({"path": "../secret.txt"}).startswith("ERROR: path is outside entity root")
    assert tools["list_repo_tree"].invoke({"path": "."}).startswith("pyproject.toml")


def test_build_package_reader_tools_rejects_symlinked_entity_root_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    packages = repo / "packages"
    packages.mkdir(parents=True)
    external_root = tmp_path / "external-pkg"
    external_root.mkdir()
    (external_root / "secret.txt").write_text("external secret", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    symlink_root = packages / "pkg-a"
    try:
        symlink_root.symlink_to(external_root, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are unsupported: {exc}")

    tools = {
        agent_tool.name: agent_tool
        for agent_tool in build_package_reader_tools(repo=repo, entity_root="packages/pkg-a", wiki=wiki, graph_tools=[])
    }

    assert tools["read_repo_file"].invoke({"path": "secret.txt"}).startswith("ERROR: entity root is outside repo")
    assert tools["list_repo_tree"].invoke({"path": "."}).startswith("ERROR: entity root is outside repo")


def test_build_package_reader_tools_rejects_internal_symlink_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    root = repo / "packages" / "pkg-a"
    root.mkdir(parents=True)
    (repo / "secret.txt").write_text("repo secret", encoding="utf-8")
    external_dir = repo / "external-dir"
    external_dir.mkdir()
    (external_dir / "hidden.txt").write_text("hidden", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    file_link = root / "link.txt"
    dir_link = root / "external_dir_symlink"
    try:
        file_link.symlink_to(repo / "secret.txt")
        dir_link.symlink_to(external_dir, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are unsupported: {exc}")

    tools = {
        agent_tool.name: agent_tool
        for agent_tool in build_package_reader_tools(repo=repo, entity_root="packages/pkg-a", wiki=wiki, graph_tools=[])
    }

    assert tools["read_repo_file"].invoke({"path": "link.txt"}).startswith("ERROR: path is outside entity root")
    assert (
        tools["list_repo_tree"]
        .invoke({"path": "external_dir_symlink"})
        .startswith("ERROR: path is outside entity root")
    )


def test_build_package_reader_tools_includes_bounded_wiki_and_allowed_graph_tools(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "pkg-a.md").write_text("---\ntitle: pkg-a\n---\n\nBody", encoding="utf-8")

    @tool
    def cg_find(name: str) -> str:
        """Find a graph node."""
        return f"find:{name}"

    @tool
    def cg_callers(name: str) -> str:
        """Not allowed for package-reader."""
        return name

    tools = build_package_reader_tools(
        repo=repo,
        entity_root="packages/pkg-a",
        wiki=wiki,
        graph_tools=[cg_find, cg_callers],
    )
    names = [agent_tool.name for agent_tool in tools]

    assert names == ["read_repo_file", "list_repo_tree", "read_wiki_page", "cg_find"]


def test_build_package_reader_prompt_includes_requested_bodies_and_frontmatter() -> None:
    item = PackageReaderItem(
        uri="pkg:org/repo/pkg-a",
        kind="package",
        name="pkg-a",
        graph_path="packages/pkg-a",
        language="python",
        frontmatter={"uri": "pkg:org/repo/pkg-a", "kind": "package"},
        page_content="# pkg-a\n\n## Purpose\n> TODO: explain.\n",
        requested_sections={"Purpose": "> TODO: explain."},
        narrative="Scanner prose.",
        file_map="## File map - pkg-a\n...",
        graph_context="package pkg-a",
        entity_root="packages/pkg-a",
    )

    prompt = build_package_reader_prompt(item)

    assert "Purpose: > TODO: explain." in prompt
    assert '"kind": "package"' in prompt
    assert '"uri": "pkg:org/repo/pkg-a"' in prompt


@pytest.mark.asyncio
async def test_run_package_reader_uses_shared_tool_loop(monkeypatch, tmp_path: Path) -> None:
    item = PackageReaderItem(
        uri="pkg:org/repo/pkg-a",
        kind="package",
        name="pkg-a",
        graph_path="packages/pkg-a",
        language="python",
        frontmatter={"uri": "pkg:org/repo/pkg-a", "kind": "package"},
        page_content="# pkg-a\n\n## Purpose\n> TODO: explain.\n",
        requested_sections={"Purpose": "> TODO: explain."},
        narrative="Scanner prose.",
        file_map="## File map - pkg-a\n...",
        graph_context="package pkg-a",
        entity_root="packages/pkg-a",
    )
    fake_llm = MagicMock()

    async def fake_loop(**kwargs):
        assert kwargs["llm"] is fake_llm
        assert kwargs["max_iterations"] == MAX_PACKAGE_READER_ITERS
        assert kwargs["cap_label"] == "package_reader"
        return MagicMock(
            status="ok",
            final_text='{"sections":[{"heading":"Purpose","replacement_markdown":"Owns scan."}]}',
            error=None,
        )

    monkeypatch.setattr("graph_wiki_core.commands.package_reader.run_tool_loop", fake_loop)

    result = await run_package_reader(
        llm=fake_llm,
        item=item,
        repo=tmp_path / "repo",
        wiki=tmp_path / "wiki",
        graph_tools=[],
    )

    assert result.replacements == {"Purpose": "Owns scan."}
    assert result.error is None


@pytest.mark.asyncio
async def test_run_package_reader_reports_invalid_model_output(monkeypatch, tmp_path: Path) -> None:
    item = PackageReaderItem(
        uri="pkg:org/repo/pkg-a",
        kind="package",
        name="pkg-a",
        graph_path="packages/pkg-a",
        language="python",
        frontmatter={"uri": "pkg:org/repo/pkg-a", "kind": "package"},
        page_content="# pkg-a\n\n## Purpose\n> TODO: explain.\n",
        requested_sections={"Purpose": "> TODO: explain."},
        narrative="Scanner prose.",
        file_map="## File map - pkg-a\n...",
        graph_context="package pkg-a",
        entity_root="packages/pkg-a",
    )

    async def fake_loop(**_kwargs):
        return MagicMock(status="ok", final_text="not json", error=None)

    monkeypatch.setattr("graph_wiki_core.commands.package_reader.run_tool_loop", fake_loop)

    result = await run_package_reader(
        llm=MagicMock(),
        item=item,
        repo=tmp_path / "repo",
        wiki=tmp_path / "wiki",
        graph_tools=[],
    )

    assert result.replacements == {}
    assert result.error is not None


@pytest.mark.asyncio
async def test_run_package_reader_allows_valid_empty_sections(monkeypatch, tmp_path: Path) -> None:
    item = PackageReaderItem(
        uri="pkg:org/repo/pkg-a",
        kind="package",
        name="pkg-a",
        graph_path="packages/pkg-a",
        language="python",
        frontmatter={"uri": "pkg:org/repo/pkg-a", "kind": "package"},
        page_content="# pkg-a\n\n## Purpose\n> TODO: explain.\n",
        requested_sections={"Purpose": "> TODO: explain."},
        narrative="Scanner prose.",
        file_map="## File map - pkg-a\n...",
        graph_context="package pkg-a",
        entity_root="packages/pkg-a",
    )

    async def fake_loop(**_kwargs):
        return MagicMock(status="ok", final_text='{"sections":[]}', error=None)

    monkeypatch.setattr("graph_wiki_core.commands.package_reader.run_tool_loop", fake_loop)

    result = await run_package_reader(
        llm=MagicMock(),
        item=item,
        repo=tmp_path / "repo",
        wiki=tmp_path / "wiki",
        graph_tools=[],
    )

    assert result.replacements == {}
    assert result.error is None


@pytest.mark.asyncio
async def test_run_package_reader_rejects_malformed_section_schema(monkeypatch, tmp_path: Path) -> None:
    item = PackageReaderItem(
        uri="pkg:org/repo/pkg-a",
        kind="package",
        name="pkg-a",
        graph_path="packages/pkg-a",
        language="python",
        frontmatter={"uri": "pkg:org/repo/pkg-a", "kind": "package"},
        page_content="# pkg-a\n\n## Purpose\n> TODO: explain.\n",
        requested_sections={"Purpose": "> TODO: explain."},
        narrative="Scanner prose.",
        file_map="## File map - pkg-a\n...",
        graph_context="package pkg-a",
        entity_root="packages/pkg-a",
    )

    async def fake_loop(**_kwargs):
        return MagicMock(
            status="ok",
            final_text='{"sections":[{"heading":1,"replacement_markdown":"Owns scan."}]}',
            error=None,
        )

    monkeypatch.setattr("graph_wiki_core.commands.package_reader.run_tool_loop", fake_loop)

    result = await run_package_reader(
        llm=MagicMock(),
        item=item,
        repo=tmp_path / "repo",
        wiki=tmp_path / "wiki",
        graph_tools=[],
    )

    assert result.replacements == {}
    assert result.error is not None
