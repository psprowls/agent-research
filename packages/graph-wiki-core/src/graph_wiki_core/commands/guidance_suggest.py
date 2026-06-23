"""`gw guidance suggest` — hybrid recall→rank over the guidance corpus.

Stage 1: deterministic recall (guidance_signals), no LLM. Stage 2: one
structured ranking call (guidance_orchestrator). Optional --assemble emits the
concatenated top-N ## Guidance bodies within a token budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from graph_io.store import GraphNotInitializedError, read_only_connect
from guidance_io.index_store import GuidanceIndex, load_index
from guidance_io.paths import guidance_index_path
from wiki_io._workspace import resolve_wiki_and_repo
from workspace_io.paths import graph_dir

from graph_wiki_core.commands.guidance_recall import (
    RankedGuidance,
    recall_and_rank,
)
from graph_wiki_core.commands.guidance_signals import (
    load_guidance_pages,
    resolve_path_contexts,
)


@dataclass
class GuidanceSuggestResult:
    ranked: list[RankedGuidance] = field(default_factory=list)
    assembled: str | None = None
    index_present: bool = False
    warnings: list[str] = field(default_factory=list)


async def run_guidance_suggest(
    message: str,
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
    *,
    paths: list[str] | None = None,
    top: int = 5,
    candidates: int = 12,
    assemble: bool = False,
    budget: int | None = None,
    model_override: str | None = None,
    make_llm_fn: Any = None,
) -> GuidanceSuggestResult:
    """Rank guidance for a coding task. See module docstring."""
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    repo = repo_path.resolve() if repo_path else resolved_repo

    result = GuidanceSuggestResult()
    pages = load_guidance_pages(workspace)
    if not pages:
        return result

    index_present = guidance_index_path(workspace).is_file()
    result.index_present = index_present
    index = load_index(workspace) if index_present else GuidanceIndex()
    if not index_present:
        result.warnings.append("no guidance index yet — run `gw guidance scan` to improve recall")

    conn = None
    if paths:
        try:
            conn = read_only_connect(graph_dir(workspace) / "code.db")
        except GraphNotInitializedError:
            conn = None
    try:
        path_contexts = resolve_path_contexts(paths or [], conn, repo, index)
        ranked, assembled, recall_warnings = await recall_and_rank(
            pages,
            message,
            path_contexts,
            top=top,
            candidates=candidates,
            assemble=assemble,
            budget=budget,
            model_override=model_override,
            make_llm_fn=make_llm_fn,
        )
    finally:
        if conn is not None:
            conn.close()

    result.ranked = ranked
    result.assembled = assembled
    result.warnings.extend(recall_warnings)

    return result
