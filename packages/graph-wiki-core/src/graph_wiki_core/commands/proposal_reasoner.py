"""Proposal reasoner context helpers for ingest-time curated-page suggestions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool

from graph_wiki_core.agent_loop import run_tool_loop
from graph_wiki_core.agent_tools import (
    build_wiki_catalog,
    chunk_text,
    filter_graph_tools,
    read_bounded_wiki_page,
    truncate_text,
)
from graph_wiki_core.agent_tools import (
    search_wiki_catalog as search_catalog_rows,
)
from graph_wiki_core.prompts.proposal_reasoner import PROPOSAL_REASONER_SYSTEM
from graph_wiki_core.roles import make_llm

FULL_SOURCE_MAX_CHARS = 120_000
SOURCE_CHUNK_CHARS = 20_000
MAX_REASONER_ITERS = 5
MAX_WIKI_PAGE_CHARS = 40_000
_CATALOG_PROMPT_CHARS = 80_000
_ALLOWED_GRAPH_TOOL_NAMES = {"cg_find", "cg_describe"}


@dataclass(frozen=True)
class ProposalReasonerResult:
    status: str
    analysis: str
    error: str | None = None


def build_source_chunks(
    source_text: str,
    *,
    max_chars: int = FULL_SOURCE_MAX_CHARS,
    chunk_chars: int = SOURCE_CHUNK_CHARS,
):
    return chunk_text(source_text, max_chars=max_chars, chunk_chars=chunk_chars)


def build_reasoner_tools(*, wiki: Path, chunks: list[str], graph_tools: list[BaseTool]) -> list[BaseTool]:
    catalog = build_wiki_catalog(wiki)

    @tool
    def read_wiki_page(path: str) -> str:
        """Read one markdown page under the wiki root, bounded to a safe size."""
        return read_bounded_wiki_page(wiki, path, max_chars=MAX_WIKI_PAGE_CHARS)

    @tool
    def read_source_chunk(index: int) -> str:
        """Read one source chunk by zero-based index when the source exceeded the prompt budget."""
        if index < 0 or index >= len(chunks):
            return f"ERROR: source chunk index out of range: {index}"
        return chunks[index]

    @tool
    def search_wiki_catalog(query: str, kind: str | None = None) -> str:
        """Search the wiki catalog by title, summary, or slug and return up to 20 JSON rows."""
        rows = search_catalog_rows(catalog, query, kind=kind, limit=20)
        return json.dumps(rows, indent=2, sort_keys=True)

    allowed_graph_tools = filter_graph_tools(graph_tools, _ALLOWED_GRAPH_TOOL_NAMES)
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
        f"{truncate_text(catalog_json, _CATALOG_PROMPT_CHARS)}\n\n"
        "Source page text (truncated if needed):\n"
        f"{truncate_text(source_page_text, MAX_WIKI_PAGE_CHARS)}\n\n"
        "Raw source text or chunk manifest:\n"
        f"{raw_source_section}\n\n"
        "Produce up to 10 candidate analyses. For each candidate include: kind, mode, target page or new slug, "
        "title, source evidence, existing pages considered, reasoning summary, potential conflicts, implementation "
        "notes, confidence, and rank. Return no candidates if the source does not justify durable curated wiki changes."
    )


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
    messages = [
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
    loop_result = await run_tool_loop(
        llm=make_llm("proposal_reasoner"),
        tools=tools,
        messages=messages,
        max_iterations=MAX_REASONER_ITERS,
        cap_label="reasoner",
    )
    return ProposalReasonerResult(
        status=loop_result.status,
        analysis=loop_result.final_text,
        error=loop_result.error,
    )
