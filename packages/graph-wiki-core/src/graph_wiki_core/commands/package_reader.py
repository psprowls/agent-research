"""Package-reader helpers for filling TODO-like human-owned package sections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from wiki_io.human_sections import is_todo_like_body

from graph_wiki_core.agent_loop import run_tool_loop
from graph_wiki_core.agent_tools import (
    filter_graph_tools,
    read_bounded_wiki_page,
    truncate_text,
)
from graph_wiki_core.prompts.package_reader import PACKAGE_READER_SYSTEM

MAX_PACKAGE_READER_ITERS = 20
MAX_REPO_FILE_CHARS = 40_000
MAX_WIKI_PAGE_CHARS = 40_000
MAX_TREE_ENTRIES = 200
_ALLOWED_GRAPH_TOOL_NAMES = {"cg_find", "cg_describe"}


@dataclass(frozen=True)
class PackageReaderItem:
    uri: str
    kind: str
    name: str
    graph_path: str
    language: str
    frontmatter: dict[str, str]
    page_content: str
    requested_sections: dict[str, str]
    narrative: str
    file_map: str
    graph_context: str
    entity_root: str


@dataclass(frozen=True)
class PackageReaderResult:
    status: str
    replacements: dict[str, str]
    error: str | None = None


@dataclass(frozen=True)
class _PackageReaderParseResult:
    replacements: dict[str, str]
    error: str | None = None


def parse_package_reader_output(raw: str, *, requested_headings: list[str]) -> dict[str, str]:
    return _parse_package_reader_output(raw, requested_headings=requested_headings).replacements


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _parse_package_reader_output(raw: str, *, requested_headings: list[str]) -> _PackageReaderParseResult:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError as exc:
        return _PackageReaderParseResult(replacements={}, error=f"package_reader returned invalid JSON: {exc.msg}")

    if not isinstance(payload, dict):
        return _PackageReaderParseResult(replacements={}, error="package_reader output must be a JSON object")

    sections = payload.get("sections")
    if not isinstance(sections, list):
        return _PackageReaderParseResult(replacements={}, error='package_reader output must contain a "sections" list')

    allowed = set(requested_headings)
    parsed: dict[str, str] = {}
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            return _PackageReaderParseResult(
                replacements={},
                error=f"package_reader section at index {index} must be an object",
            )
        if "heading" not in section or "replacement_markdown" not in section:
            return _PackageReaderParseResult(
                replacements={},
                error=f"package_reader section at index {index} must include heading and replacement_markdown",
            )
        heading = section["heading"]
        body = section["replacement_markdown"]
        if not isinstance(heading, str) or not isinstance(body, str):
            return _PackageReaderParseResult(
                replacements={},
                error=f"package_reader section at index {index} must use string heading and replacement_markdown",
            )
        normalized_heading = heading.strip()
        normalized_body = body.strip()
        if (
            not normalized_heading
            or normalized_heading not in allowed
            or normalized_heading in parsed
            or not normalized_body
            or is_todo_like_body(normalized_body)
        ):
            continue
        parsed[normalized_heading] = normalized_body
    return _PackageReaderParseResult(replacements=parsed, error=None)


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


def build_package_reader_tools(repo: Path, entity_root: str, wiki: Path, graph_tools: list[BaseTool]) -> list[BaseTool]:
    entity_root_path = repo / entity_root

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


def build_package_reader_prompt(item: PackageReaderItem) -> str:
    requested = "\n".join(f"- {heading}: {body}" for heading, body in item.requested_sections.items())
    frontmatter_json = json.dumps(item.frontmatter, sort_keys=True)
    return (
        f"Entity URI: {item.uri}\n"
        f"Kind: {item.kind}\n"
        f"Name: {item.name}\n"
        f"Graph path: {item.graph_path}\n"
        f"Language: {item.language}\n"
        f"Entity root: {item.entity_root}\n\n"
        "Frontmatter JSON:\n"
        f"{frontmatter_json}\n\n"
        "Requested H2 sections:\n"
        f"{requested or '(none)'}\n\n"
        "Scanner narrative:\n"
        f"{item.narrative or '(none)'}\n\n"
        "Scanner file map:\n"
        f"{item.file_map or '(none)'}\n\n"
        "Graph context:\n"
        f"{item.graph_context or '(none)'}\n\n"
        "Current page content:\n"
        f"{truncate_text(item.page_content, MAX_WIKI_PAGE_CHARS)}"
    )


async def run_package_reader(
    *,
    llm: object,
    item: PackageReaderItem,
    repo: Path,
    wiki: Path,
    graph_tools: list[BaseTool],
) -> PackageReaderResult:
    tools = build_package_reader_tools(repo=repo, entity_root=item.entity_root, wiki=wiki, graph_tools=graph_tools)
    loop_result = await run_tool_loop(
        llm=llm,
        tools=tools,
        messages=[
            SystemMessage(content=PACKAGE_READER_SYSTEM),
            HumanMessage(content=build_package_reader_prompt(item)),
        ],
        max_iterations=MAX_PACKAGE_READER_ITERS,
        cap_label="package_reader",
    )
    if loop_result.status != "ok":
        return PackageReaderResult(status=loop_result.status, replacements={}, error=loop_result.error)
    parse_result = _parse_package_reader_output(
        loop_result.final_text,
        requested_headings=list(item.requested_sections),
    )
    return PackageReaderResult(
        status=loop_result.status,
        replacements=parse_result.replacements,
        error=parse_result.error or loop_result.error,
    )
