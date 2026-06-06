"""Proposal reasoner context helpers for ingest-time curated-page suggestions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from model_adapter.loader import make_llm
from wiki_io.proposals import list_proposals
from wiki_io.update_index import parse_frontmatter

from graph_wiki_core.prompts.proposal_reasoner import PROPOSAL_REASONER_SYSTEM

CURATED_DIRS = ("concepts", "adrs", "architecture", "sources")
FULL_SOURCE_MAX_CHARS = 120_000
SOURCE_CHUNK_CHARS = 20_000
EXCERPT_CHARS = 500
MAX_REASONER_ITERS = 5
MAX_WIKI_PAGE_CHARS = 40_000
_CATALOG_PROMPT_CHARS = 80_000
_ALLOWED_GRAPH_TOOL_NAMES = {"cg_find", "cg_describe"}


@dataclass(frozen=True)
class SourceChunks:
    full_text: str | None
    chunks: list[str]
    over_budget: bool


@dataclass(frozen=True)
class ProposalReasonerResult:
    status: str
    analysis: str
    error: str | None = None


def _body_without_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].strip()


def _frontmatter_entry(path: Path, wiki: Path, kind: str) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    metadata = parse_frontmatter(text)
    rel_path = path.relative_to(wiki).as_posix()
    body = _body_without_frontmatter(text)
    excerpt = " ".join(body.split())[:EXCERPT_CHARS]
    entry: dict[str, Any] = {
        "kind": kind,
        "slug": path.stem,
        "path": rel_path,
        "title": metadata.get("title", path.stem.replace("-", " ").replace("_", " ").title()),
        "summary": metadata.get("summary", ""),
        "uri": metadata.get("uri", ""),
        "entity_kind": metadata.get("kind", ""),
        "excerpt": excerpt,
    }
    return entry


def build_wiki_catalog(wiki: Path) -> dict[str, list[dict[str, Any]]]:
    catalog: dict[str, list[dict[str, Any]]] = {name: [] for name in CURATED_DIRS}
    catalog["entities"] = []
    catalog["proposals"] = list_proposals(wiki)

    for dirname in CURATED_DIRS:
        directory = wiki / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == "index.md":
                continue
            entry = _frontmatter_entry(path, wiki, dirname.rstrip("s"))
            if entry is not None:
                catalog[dirname].append(entry)

    entities = wiki / "entities"
    if entities.is_dir():
        for path in sorted(entities.rglob("*.md")):
            if path.name == "index.md":
                continue
            entry = _frontmatter_entry(path, wiki, "entity")
            if entry is not None:
                catalog["entities"].append(entry)

    return catalog


def build_source_chunks(
    source_text: str,
    *,
    max_chars: int = FULL_SOURCE_MAX_CHARS,
    chunk_chars: int = SOURCE_CHUNK_CHARS,
) -> SourceChunks:
    if len(source_text) <= max_chars:
        return SourceChunks(full_text=source_text, chunks=[], over_budget=False)
    chunks = [source_text[start : start + chunk_chars] for start in range(0, len(source_text), chunk_chars)]
    return SourceChunks(full_text=None, chunks=chunks, over_budget=True)


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[TRUNCATED after {max_chars} chars]"


def _read_bounded_wiki_page(wiki: Path, rel_path: str) -> str:
    try:
        wiki_root = wiki.resolve()
        page = (wiki_root / rel_path).resolve()
        page.relative_to(wiki_root)
    except ValueError:
        return "ERROR: path is outside wiki"
    except OSError as exc:
        return f"ERROR: {exc}"

    if page.suffix != ".md":
        return "ERROR: only markdown wiki pages may be read"
    if not page.is_file():
        return f"ERROR: wiki page not found: {rel_path}"

    try:
        text = page.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"ERROR: {exc}"

    metadata = parse_frontmatter(text)
    body = _body_without_frontmatter(text)
    title = str(metadata.get("title") or page.stem.replace("-", " ").replace("_", " ").title())
    content = f"# {title}\n\n{body}" if body else f"# {title}"
    return _truncate_text(content, MAX_WIKI_PAGE_CHARS)


def _flatten_catalog(catalog: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, entries in catalog.items():
        for entry in entries:
            if isinstance(entry, dict):
                row = dict(entry)
                row.setdefault("bucket", bucket)
                rows.append(row)
    return rows


def _catalog_bucket_matches(bucket: str, entry: dict[str, Any], kind: str | None) -> bool:
    if not kind:
        return True
    normalized = kind.lower().strip()
    if normalized == bucket or normalized == bucket.rstrip("s"):
        return True
    entry_kind = str(entry.get("kind", "")).lower()
    return normalized == entry_kind or normalized == f"{entry_kind}s"


def _search_catalog(catalog: dict[str, list[dict[str, Any]]], query: str, kind: str | None = None) -> str:
    query_lc = query.lower().strip()
    matches: list[dict[str, Any]] = []
    for row in _flatten_catalog(catalog):
        bucket = str(row.get("bucket", ""))
        if not _catalog_bucket_matches(bucket, row, kind):
            continue
        fields = [
            str(row.get("title", "")),
            str(row.get("summary", "")),
            str(row.get("slug", "")),
            str(row.get("target_slug", "")),
        ]
        haystack = " ".join(fields).lower()
        if not query_lc or query_lc in haystack:
            matches.append(row)
        if len(matches) >= 20:
            break
    return json.dumps(matches, indent=2, sort_keys=True)


def build_reasoner_tools(*, wiki: Path, chunks: list[str], graph_tools: list[BaseTool]) -> list[BaseTool]:
    catalog = build_wiki_catalog(wiki)

    @tool
    def read_wiki_page(path: str) -> str:
        """Read one markdown page under the wiki root, bounded to a safe size."""
        return _read_bounded_wiki_page(wiki, path)

    @tool
    def read_source_chunk(index: int) -> str:
        """Read one source chunk by zero-based index when the source exceeded the prompt budget."""
        if index < 0 or index >= len(chunks):
            return f"ERROR: source chunk index out of range: {index}"
        return chunks[index]

    @tool
    def search_wiki_catalog(query: str, kind: str | None = None) -> str:
        """Search the wiki catalog by title, summary, or slug and return up to 20 JSON rows."""
        return _search_catalog(catalog, query, kind)

    allowed_graph_tools = [graph_tool for graph_tool in graph_tools if graph_tool.name in _ALLOWED_GRAPH_TOOL_NAMES]
    return [read_wiki_page, read_source_chunk, search_wiki_catalog, *allowed_graph_tools]


def build_reasoner_prompt(
    *,
    wiki: Path,
    source_path: Path,
    source_text: str,
    source_page_path: Path,
    source_page_text: str,
    entity_uri: str | None,
    entity_stem: str | None,
) -> str:
    source_chunks = build_source_chunks(source_text)
    catalog_json = json.dumps(build_wiki_catalog(wiki), indent=2, sort_keys=True)

    if source_chunks.full_text is None:
        chunk_lines = "\n".join(
            f"- chunk {index}: {len(chunk)} chars" for index, chunk in enumerate(source_chunks.chunks)
        )
        raw_source_section = (
            "Raw source text exceeded prompt budget and was split into chunks. "
            "Use read_source_chunk(index) for targeted inspection.\n"
            f"{chunk_lines}"
        )
    else:
        raw_source_section = source_chunks.full_text

    return (
        f"Source path: {source_path}\n"
        f"Source wiki page: {source_page_path}\n"
        f"Entity URI: {entity_uri or '(none)'}\n"
        f"Entity stem: {entity_stem or '(none)'}\n\n"
        "Wiki catalog JSON (truncated if needed):\n"
        f"{_truncate_text(catalog_json, _CATALOG_PROMPT_CHARS)}\n\n"
        "Source page text (truncated if needed):\n"
        f"{_truncate_text(source_page_text, MAX_WIKI_PAGE_CHARS)}\n\n"
        "Raw source text or chunk manifest:\n"
        f"{raw_source_section}\n\n"
        "Produce up to 10 candidate analyses. For each candidate include: kind, mode, target page or new slug, "
        "title, source evidence, existing pages considered, reasoning summary, potential conflicts, implementation "
        "notes, confidence, and rank. Return no candidates if the source does not justify durable curated wiki changes."
    )


def _tool_call_parts(call: Any) -> tuple[str, dict[str, Any], str]:
    if not isinstance(call, dict):
        return "", {}, ""
    name = str(call.get("name", ""))
    args = call.get("args", {})
    if not isinstance(args, dict):
        args = {}
    call_id = str(call.get("id", ""))
    return name, args, call_id


async def run_proposal_reasoner(
    *,
    wiki: Path,
    source_path: Path,
    source_text: str,
    source_page_path: Path,
    source_page_text: str,
    entity_uri: str | None,
    entity_stem: str | None,
    graph_tools: list[BaseTool],
) -> ProposalReasonerResult:
    source_chunks = build_source_chunks(source_text)
    tools = build_reasoner_tools(wiki=wiki, chunks=source_chunks.chunks, graph_tools=graph_tools)
    tool_by_name = {reasoner_tool.name: reasoner_tool for reasoner_tool in tools}
    llm = make_llm("proposal_reasoner").bind_tools(tools)
    messages: list[Any] = [
        SystemMessage(content=PROPOSAL_REASONER_SYSTEM),
        HumanMessage(
            content=build_reasoner_prompt(
                wiki=wiki,
                source_path=source_path,
                source_text=source_text,
                source_page_path=source_page_path,
                source_page_text=source_page_text,
                entity_uri=entity_uri,
                entity_stem=entity_stem,
            )
        ),
    ]

    last_text = ""
    for _iteration in range(MAX_REASONER_ITERS):
        response = await llm.ainvoke(messages)
        text = getattr(response, "content", "") or ""
        if text:
            last_text = str(text)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return ProposalReasonerResult(status="ok", analysis=str(text))

        messages.append(response)
        for call in tool_calls:
            call_name, call_args, call_id = _tool_call_parts(call)
            reasoner_tool = tool_by_name.get(call_name)
            if reasoner_tool is None:
                tool_output = f"ERROR: unknown tool {call_name!r}"
            else:
                try:
                    tool_output = reasoner_tool.invoke(call_args)
                except Exception as exc:
                    tool_output = f"ERROR: {exc}"
            if not isinstance(tool_output, str):
                tool_output = str(tool_output)
            messages.append(ToolMessage(content=tool_output, tool_call_id=call_id))

    if last_text:
        return ProposalReasonerResult(
            status="ok",
            analysis=last_text,
            error=f"reasoner hit iteration cap ({MAX_REASONER_ITERS}) after producing text",
        )
    return ProposalReasonerResult(
        status="failed",
        analysis="",
        error=f"reasoner hit iteration cap ({MAX_REASONER_ITERS})",
    )
