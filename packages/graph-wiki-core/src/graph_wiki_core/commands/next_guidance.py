"""`gw next` guidance flow — phase-filtered guidance for a work item.

Distinct from `gw guidance suggest`: receives the work item itself, derives the
recall inputs from it (message=summary, paths=affects, phase=current), filters
the guidance corpus to phase-relevant pages, then runs the shared recall→rank
core. Phase-value validation lives here — graph-wiki-core references both
guidance-io and work-io — and a `workflow` value outside VALID_PHASES excludes
the page from the phase filter and surfaces a warning (never an exception).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import graph_io
from graph_io.store import GraphNotInitializedError
from guidance_io.index_store import GuidanceIndex, load_index
from guidance_io.paths import guidance_index_path
from wiki_io._workspace import resolve_wiki_and_repo
from work_io import frontmatter as _frontmatter
from work_io.lifecycle_lint import TERMINAL_STATUSES, VALID_PHASES, VALID_ROLES

from graph_wiki_core.commands.guidance_recall import RankedGuidance, recall_and_rank
from graph_wiki_core.commands.guidance_signals import (
    GuidancePage,
    load_guidance_pages,
    resolve_path_contexts,
)
from graph_wiki_core.commands.work import WorkNextResult

# Statuses that never dispatch a stage and therefore never want guidance.
_NON_DISPATCHING_STATUSES = TERMINAL_STATUSES | {"mitigated"}
_PHASES_WITHOUT_GUIDANCE = {"finish", "done"}


@dataclass
class NextGuidanceResult:
    ranked: list[RankedGuidance] = field(default_factory=list)
    assembled: str | None = None
    warnings: list[str] = field(default_factory=list)


def derive_recall_inputs(fm: dict) -> tuple[str, list[str], str | None]:
    """From a work-item frontmatter dict: (message=summary, paths=affects, phase)."""
    message = str(fm.get("summary", ""))
    paths = [str(p) for p in (fm.get("affects") or [])]
    phase = str(fm["phase"]) if fm.get("phase") else None
    return message, paths, phase


def filter_by_phase(pages: list[GuidancePage], phase: str | None) -> tuple[list[GuidancePage], list[str]]:
    """Keep phase-agnostic + matching pages; drop non-matching; drop+warn invalid."""
    kept: list[GuidancePage] = []
    warnings: list[str] = []
    for page in pages:
        wf = page.workflow
        if not wf:
            kept.append(page)
            continue
        invalid = [v for v in wf if v not in VALID_PHASES]
        if invalid:
            warnings.append(
                f"guidance/{page.slug}: workflow has invalid phase value(s) {invalid}; excluded from the phase filter"
            )
            continue
        if phase is not None and phase in wf:
            kept.append(page)
    return kept, warnings


def filter_by_role(pages: list[GuidancePage], role: str | None) -> tuple[list[GuidancePage], list[str]]:
    """Keep role-agnostic + matching pages; drop non-matching; drop+warn invalid.

    role=None disables role filtering (keep all) — used at design/plan/finish, which
    have no implement-vs-review split.
    """
    if role is None:
        return pages, []
    kept: list[GuidancePage] = []
    warnings: list[str] = []
    for page in pages:
        rl = page.role
        if not rl:
            kept.append(page)  # dual-use
            continue
        invalid = [v for v in rl if v not in VALID_ROLES]
        if invalid:
            warnings.append(f"guidance/{page.slug}: role has invalid value(s) {invalid}; excluded from the role filter")
            continue
        if role in rl:
            kept.append(page)
    return kept, warnings


def guidance_eligible(wn: WorkNextResult) -> bool:
    """Whether a work-next result should carry guidance."""
    if wn.blockers:
        return False
    if wn.phase in _PHASES_WITHOUT_GUIDANCE:
        return False
    if (wn.status or "") in _NON_DISPATCHING_STATUSES:
        return False
    return True


async def run_next_guidance(
    slug: str,
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
    *,
    top: int = 5,
    candidates: int = 12,
    assemble: bool = False,
    budget: int | None = None,
    no_rank: bool = False,
    model_override: str | None = None,
    make_llm_fn: Any = None,
    # Caller (CLI) passes the phase resolved by run_work_next so freshly-filed items
    # (no frontmatter phase yet) still get phase-specific guidance on first dispatch.
    phase: str | None = None,
) -> NextGuidanceResult:
    """Load work item <slug>, phase-filter guidance, recall→rank. See module docstring."""
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    repo = repo_path.resolve() if repo_path else resolved_repo

    result = NextGuidanceResult()

    item_path = wiki / "work" / f"{slug}.md"
    if not item_path.exists():
        return result
    fm, _body = _frontmatter.parse(item_path.read_text(encoding="utf-8"))
    message, paths, frontmatter_phase = derive_recall_inputs(fm)
    # Prefer the caller-supplied resolved phase; fall back to frontmatter-derived one.
    effective_phase = phase if phase is not None else frontmatter_phase

    pages = load_guidance_pages(workspace)
    if not pages:
        return result

    # Option A: role tracks the stage's actor. Execute dispatches implement-flavored
    # stages (subagent-driven-development / test-driven-development); design/plan/finish
    # have no implement-vs-review split, so role filtering is OFF there (dual-use only).
    active_role = "implement" if effective_phase == "execute" else None
    kept, filter_warnings = filter_by_phase(pages, effective_phase)
    result.warnings.extend(filter_warnings)
    kept, role_warnings = filter_by_role(kept, active_role)
    result.warnings.extend(role_warnings)
    if not kept:
        return result

    index_present = guidance_index_path(workspace).is_file()
    index = load_index(workspace) if index_present else GuidanceIndex()
    if not index_present:
        result.warnings.append("no guidance index yet — run `gw guidance scan` to improve recall")

    reader = None
    if paths:
        try:
            reader = graph_io.open_reader(workspace)
        except GraphNotInitializedError:
            reader = None
    try:
        path_contexts = resolve_path_contexts(paths, reader, repo, index)
        ranked, assembled, core_warnings = await recall_and_rank(
            kept,
            message,
            path_contexts,
            top=top,
            candidates=candidates,
            assemble=assemble,
            budget=budget,
            model_override=model_override,
            make_llm_fn=make_llm_fn,
            force_recall_only=no_rank,
            recall_only_reason=(
                "ranking is deterministic (--no-rank)"
                if no_rank
                else "Bedrock stack unavailable; returning recall order without ranking"
            ),
            # Scope the all-low suppression to `gw next`; `guidance_suggest` keeps
            # the default drop_low=False so it can still surface low matches.
            drop_low=True,
        )
    finally:
        if reader is not None:
            reader.close()

    result.ranked = ranked
    result.assembled = assembled
    result.warnings.extend(core_warnings)
    return result
