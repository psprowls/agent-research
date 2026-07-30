"""Unified prose-refresh agent: one tool-using task updates all prose on a stale entity page."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from wiki_io.entity_writer import DETERMINISTIC_SECTIONS
from wiki_io.human_sections import is_todo_like_body

from graph_wiki_core.agent_loop import run_tool_loop
from graph_wiki_core.agent_tools import (
    filter_graph_tools,
    read_bounded_wiki_page,
    truncate_text,
)
from graph_wiki_core.commands.scan_contract import ProseRefreshResult, ProseRefreshTask
from graph_wiki_core.prompts.prose_refresher import PROSE_REFRESHER_SYSTEM

MAX_PROSE_REFRESH_ITERS = 50
MAX_REPO_FILE_CHARS = 40_000
MAX_WIKI_PAGE_CHARS = 40_000
MAX_TREE_ENTRIES = 200
_ALLOWED_GRAPH_TOOL_NAMES = {"cg_find", "cg_describe"}


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


def build_prose_refresh_prompt(task: ProseRefreshTask) -> str:
    if task.trigger == "first_fill":
        diff_block = "(first fill — no diff; write fresh prose for placeholder sections)"
    elif task.diff is None:
        diff_block = (
            "(history rewritten — the recorded anchor commit is unknown to this repo; "
            "re-verify all prose against current source)"
        )
    else:
        diff_block = task.diff
    sections_block = "\n\n".join(f"{heading}\n{body or '(empty)'}" for heading, body in task.prose_sections.items())
    changed = "\n".join(f"- {p}" for p in task.changed_files)
    return (
        f"Entity URI: {task.uri}\n"
        f"Kind: {task.kind}\n"
        f"Name: {task.name}\n"
        f"Graph path: {task.graph_path}\n"
        f"Language: {task.language}\n"
        f"Entity root: {task.entity_root}\n"
        f"Trigger: {task.trigger}\n\n"
        "Source diff since the prose was last updated:\n"
        f"{diff_block}\n\n"
        "Changed files:\n"
        f"{changed or '(none)'}\n\n"
        "Current prose sections (heading + body; these are the ONLY headings you may return):\n"
        f"{sections_block or '(none)'}\n\n"
        "Current File-map rows:\n"
        f"{task.file_map_rows or '(none)'}\n\n"
        "Graph context:\n"
        f"{task.graph_context or '(none)'}\n\n"
        "Current page content:\n"
        f"{truncate_text(task.page_content, MAX_WIKI_PAGE_CHARS)}"
    )


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _normalize_heading(raw: str) -> str:
    stripped = raw.strip()
    return stripped if stripped.startswith("## ") else f"## {stripped.removeprefix('##').strip()}"


def _str_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, val in value.items():
        if not (isinstance(key, str) and isinstance(val, str) and val.strip()):
            continue
        cleaned = " ".join(val.split()).strip()
        if cleaned and not is_todo_like_body(cleaned):
            out[key] = cleaned
    return out


def parse_prose_refresher_output(raw: str, *, allowed_headings: list[str]) -> ProseRefreshResult:
    """Parse the agent's final JSON into a ProseRefreshResult (uri filled by caller).

    Structural failures return an empty result with ``error`` set. Per-section
    filtering (deterministic/unknown headings, TODO-like or empty bodies) drops
    silently.
    """
    try:
        payload = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError as exc:
        return ProseRefreshResult(uri="", error=f"prose_refresher returned invalid JSON: {exc.msg}")
    if not isinstance(payload, dict):
        return ProseRefreshResult(uri="", error="prose_refresher output must be a JSON object")

    allowed = set(allowed_headings)
    sections: dict[str, str] = {}
    raw_sections = payload.get("sections")
    if raw_sections is not None and not isinstance(raw_sections, list):
        return ProseRefreshResult(uri="", error='prose_refresher "sections" must be a list')
    for section in raw_sections or []:
        if not isinstance(section, dict):
            continue
        heading = section.get("heading")
        body = section.get("replacement_markdown")
        if not isinstance(heading, str) or not isinstance(body, str):
            continue
        normalized = _normalize_heading(heading)
        cleaned = body.strip()
        if (
            normalized not in allowed
            or normalized in DETERMINISTIC_SECTIONS
            or normalized in sections
            or not cleaned
            or is_todo_like_body(cleaned)
        ):
            continue
        sections[normalized] = cleaned

    overview_raw = payload.get("overview")
    overview = overview_raw.strip() if isinstance(overview_raw, str) and overview_raw.strip() else None
    if overview is not None and is_todo_like_body(overview):
        overview = None
    return ProseRefreshResult(
        uri="",
        sections=sections,
        file_map_descriptions=_str_dict(payload.get("file_map_descriptions")),
        dir_descriptions=_str_dict(payload.get("dir_descriptions")),
        overview=overview,
        error=None,
    )


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
