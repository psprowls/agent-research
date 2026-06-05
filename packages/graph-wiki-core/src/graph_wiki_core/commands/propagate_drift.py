"""Living Wiki M4: scan-time drift producer — propose curated-page updates.

For every entity whose narrative was refreshed since M4 last propagated it, find
the curated pages (concepts/adrs/architecture) that backlink it and judge whether
their claims have gone stale relative to the entity's current state. Stale
findings are recorded as `source: drift` notes in the shared proposal ledger
(``wiki_io.proposals.upsert_proposal``) — propose only, never auto-edit.

M4 owns the per-entity anchor ``drift_propagated_commit`` (the analog of M2e's
``drift_checked_commit``): an entity is a candidate when
``drift_propagated_commit != last_updated_commit``, and the anchor is stamped to
``last_updated_commit`` after processing so repeat runs are idempotent on both
execution surfaces. Pure orchestration: the backlink map, ledger calls, and
judge prompt live in their own modules; this module composes them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter
from graph_io import queries as _queries
from langchain_core.messages import HumanMessage, SystemMessage
from wiki_io.backlink_index import build_entity_backlink_map
from wiki_io.drift import extract_narrative, section_hash
from wiki_io.entity_writer import LAST_UPDATED_COMMIT_KEY, update_frontmatter
from wiki_io.git_state import changed_files_since
from wiki_io.proposals import HUMAN_DECIDED, list_proposals, upsert_proposal
from workspace_io.paths import graph_dir

from graph_wiki_core.prompts.drift_propagator import (
    build_drift_propagator_prompt,
    parse_drift_propagator_verdict,
)

# Bedrock fan-out stack — imported only for the judged path (mirrors scan.py).
try:
    from model_adapter.loader import load_role_config, make_llm
    from subagent_runtime.pool import SubagentPool, TaskResult
except ImportError:  # pragma: no cover — exercised when the Bedrock stack is absent
    load_role_config = make_llm = None  # type: ignore[assignment]
    SubagentPool = TaskResult = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# M4's per-entity provenance anchor (new key; preserved across re-scan; NOT in
# SCANNER_OWNED_KEYS — see .claude/rules/backward-compatibility.md, Task 10).
DRIFT_PROPAGATED_COMMIT_KEY = "drift_propagated_commit"

# Curated categories M4 proposes against, folder -> ledger kind. `sources`
# (M3-refreshed) and `work` (transient) are deliberately excluded (§3.2).
_CATEGORY_TO_KIND = {"concepts": "concept", "adrs": "adr", "architecture": "architecture"}

# Candidate kinds carry a node_path -> git change signal; mirrors
# scan._commit_dirty_changes / DRIFT_TARGET_KINDS.
_CANDIDATE_KINDS = ("package", "app", "test_suite", "agent_plugin")


@dataclass
class PropagationCandidate:
    uri: str
    page_path: Path
    stem: str
    narrative: str
    last_updated_commit: str
    drift_propagated_commit: str | None
    changed_files: list[str]


@dataclass
class PropagateDriftResult:
    pages_judged: int
    entities_considered: int
    notes_written: int          # target notes created or refreshed this run
    pages_stale: int
    pages_skipped_settled: int   # dropped by the ledger pre-filter
    dry_run: bool
    proposals: list[dict] = field(default_factory=list)  # report rows for --json


def _entity_paths_by_uri(conn: Any) -> dict[str, str]:
    """uri -> repo-relative node path for the candidate kinds (from the graph).

    ``list_packages`` / ``list_apps`` / ``list_test_suites`` / ``list_agent_plugins``
    all use ``_list_by_kind``, which selects 6 columns including ``uri`` and folds
    it back into ``node.attrs["uri"]`` via ``_row_to_node``. So ``attrs.get("uri")``
    is the correct read surface here.
    """
    list_fns = {
        "package": _queries.list_packages,
        "app": _queries.list_apps,
        "test_suite": _queries.list_test_suites,
        "agent_plugin": _queries.list_agent_plugins,
    }
    out: dict[str, str] = {}
    for kind in _CANDIDATE_KINDS:
        for node in list_fns[kind](conn):
            attrs = node.attrs if isinstance(node.attrs, dict) else {}
            uri = attrs.get("uri")
            if uri and node.path:
                out[uri] = node.path
    return out


def propagation_candidates(wiki: Path, repo: Path, conn: Any) -> list[PropagationCandidate]:
    """Entity pages where ``drift_propagated_commit != last_updated_commit``.

    Each candidate carries its current narrative and the git-derived files that
    moved since its ``drift_propagated_commit`` (an absent anchor yields no
    specific files — empty ``since_sha`` -> ``changed_files_since`` returns None).
    A kind without a graph ``node.path`` (repository/domain/dependency) is not a
    candidate — it has no change signal.
    """
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return []
    uri_to_path = _entity_paths_by_uri(conn)
    out: list[PropagationCandidate] = []
    for page_path in sorted(entities_dir.glob("*.md")):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — a malformed page must not abort the pass
            continue
        meta = post.metadata
        uri = meta.get("uri")
        anchor = meta.get(LAST_UPDATED_COMMIT_KEY)
        if not uri or not anchor:
            continue
        propagated = meta.get(DRIFT_PROPAGATED_COMMIT_KEY)
        if propagated == anchor:
            continue  # already propagated at this narrative revision
        node_path = uri_to_path.get(uri)
        if not node_path:
            continue  # kind without a git change signal
        narrative = extract_narrative(post.content)
        if not narrative:
            continue  # no ground truth to judge against
        changed = changed_files_since(repo, str(propagated) if propagated else "", node_path) or []
        out.append(
            PropagationCandidate(
                uri=str(uri),
                page_path=page_path,
                stem=page_path.stem,
                narrative=narrative,
                last_updated_commit=str(anchor),
                drift_propagated_commit=(str(propagated) if propagated else None),
                changed_files=list(changed),
            )
        )
    return out
