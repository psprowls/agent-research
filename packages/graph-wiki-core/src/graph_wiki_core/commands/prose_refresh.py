"""Unified prose-refresh agent: one tool-using task updates all prose on a stale entity page."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool

from graph_wiki_core.agent_loop import run_tool_loop
from graph_wiki_core.agent_tools import (
    filter_graph_tools,
    read_bounded_wiki_page,
    truncate_text,
)
from graph_wiki_core.commands.scan_contract import ProseRefreshResult, ProseRefreshTask
from graph_wiki_core.prompts.prose_refresher import (
    MAX_WIKI_PAGE_CHARS,
    PROSE_REFRESHER_SYSTEM,
    build_prose_refresh_prompt,
    parse_prose_refresher_output,
    sanitize_prose_result,
)

# parse_prose_refresher_output (and its _strip_json_fence helper) live in
# prompts/prose_refresher.py now — it is base-closure safe (json + the
# normalize/sanitize helpers already there, no Bedrock dependency) and the
# out-of-process results-dir loader needs the same parsing logic. Re-exported
# here so existing importers (this module's own run_prose_refresh, the
# subagent-cli adapter) are undisturbed.

MAX_PROSE_REFRESH_ITERS = 50
MAX_REPO_FILE_CHARS = 40_000
MAX_TREE_ENTRIES = 200
_ALLOWED_GRAPH_TOOL_NAMES = {"cg_find", "cg_describe"}

__all__ = [
    "MAX_PROSE_REFRESH_ITERS",
    "MAX_REPO_FILE_CHARS",
    "MAX_TREE_ENTRIES",
    "MAX_WIKI_PAGE_CHARS",
    "PROSE_REFRESHER_SYSTEM",
    "ProseRefreshResult",
    "ProseRefreshTask",
    "build_prose_refresh_prompt",
    "build_prose_refresh_tools",
    "parse_prose_refresher_output",
    "run_prose_refresh",
    "sanitize_prose_result",
]


def _resolve_under_entity_root(root: Path, rel_path: str) -> Path | None:
    try:
        resolved_root = root.resolve()
        resolved_path = (resolved_root / rel_path).resolve()
        resolved_path.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    return resolved_path


def _resolved_entity_root_within_repo(repo: Path, entity_root_path: Path) -> Path | None:
    try:
        resolved_repo = repo.resolve()
        resolved_entity_root = entity_root_path.resolve()
        resolved_entity_root.relative_to(resolved_repo)
    except (OSError, ValueError):
        return None
    return resolved_entity_root


def build_prose_refresh_tools(repo: Path, entity_root: str, wiki: Path, graph_tools: list[BaseTool]) -> list[BaseTool]:
    entity_root_path = repo / entity_root if entity_root else repo

    @tool
    def read_repo_file(path: str) -> str:
        """Read one repo file under the entity root, bounded to a safe size."""
        resolved_entity_root = _resolved_entity_root_within_repo(repo, entity_root_path)
        if resolved_entity_root is None:
            return "ERROR: entity root is outside repo"
        target = _resolve_under_entity_root(resolved_entity_root, path)
        if target is None:
            return "ERROR: path is outside entity root"
        if not target.is_file():
            return f"ERROR: repo file not found: {path}"
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"ERROR: {exc}"
        return truncate_text(text, MAX_REPO_FILE_CHARS)

    @tool
    def list_repo_tree(path: str = ".") -> str:
        """List shallow sorted children under the entity root, bounded to 200 entries."""
        resolved_entity_root = _resolved_entity_root_within_repo(repo, entity_root_path)
        if resolved_entity_root is None:
            return "ERROR: entity root is outside repo"
        target = _resolve_under_entity_root(resolved_entity_root, path)
        if target is None:
            return "ERROR: path is outside entity root"
        if not target.exists():
            return f"ERROR: repo path not found: {path}"
        if not target.is_dir():
            return f"ERROR: repo path is not a directory: {path}"
        try:
            children = sorted(target.iterdir(), key=lambda child: child.name)
        except OSError as exc:
            return f"ERROR: {exc}"
        rows = [f"{child.name}/" if child.is_dir() else child.name for child in children[:MAX_TREE_ENTRIES]]
        return "\n".join(rows) if rows else "(empty)"

    @tool
    def read_wiki_page(path: str) -> str:
        """Read one markdown page under the wiki root, bounded to a safe size."""
        return read_bounded_wiki_page(wiki, path, max_chars=MAX_WIKI_PAGE_CHARS)

    allowed_graph_tools = filter_graph_tools(graph_tools, _ALLOWED_GRAPH_TOOL_NAMES)
    return [read_repo_file, list_repo_tree, read_wiki_page, *allowed_graph_tools]


async def run_prose_refresh(
    *,
    llm: object,
    task: ProseRefreshTask,
    repo: Path,
    wiki: Path,
    graph_tools: list[BaseTool],
) -> ProseRefreshResult:
    tools = build_prose_refresh_tools(repo=repo, entity_root=task.entity_root, wiki=wiki, graph_tools=graph_tools)
    loop_result = await run_tool_loop(
        llm=llm,
        tools=tools,
        messages=[
            SystemMessage(content=PROSE_REFRESHER_SYSTEM),
            HumanMessage(content=build_prose_refresh_prompt(task)),
        ],
        max_iterations=MAX_PROSE_REFRESH_ITERS,
        cap_label="prose_refresher",
    )
    if loop_result.status != "ok":
        return ProseRefreshResult(uri=task.uri, error=loop_result.error)
    parsed = parse_prose_refresher_output(loop_result.final_text, allowed_headings=list(task.prose_sections))
    parsed.uri = task.uri
    parsed.error = parsed.error or loop_result.error
    return parsed
