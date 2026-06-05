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


def _page_title(page_path: Path, fallback: str) -> str:
    try:
        return str(frontmatter.load(page_path).metadata.get("title") or fallback)
    except Exception:  # noqa: BLE001
        return fallback


def _build_targets(
    candidates: list[PropagationCandidate], backlink_map: dict
) -> dict[Path, dict]:
    """page_path -> {kind, target_slug, page_path, candidates[]} for curated
    pages backlinked by a candidate (sources/work filtered out)."""
    targets: dict[Path, dict] = {}
    for c in candidates:
        for category, slug, page_path in backlink_map.get(c.stem, []):
            kind = _CATEGORY_TO_KIND.get(category)
            if kind is None:
                continue  # sources / work are not drift targets
            entry = targets.setdefault(
                page_path,
                {"kind": kind, "target_slug": slug, "page_path": page_path, "candidates": []},
            )
            entry["candidates"].append(c)
    return targets


async def run_propagate_drift(
    *,
    wiki: Path,
    repo: Path,
    conn: Any,
    dry_run: bool = False,
    only: str | None = None,
    model_override: str | None = None,
) -> PropagateDriftResult:
    """Propose curated-page updates for changed entities (spec §3.6).

    candidates → curated backlink targets → kind-aware judge → upsert one origin
    per finding → stamp drift_propagated_commit per processed candidate. Both
    surfaces call this; it computes its own candidates off the on-disk anchors.
    """
    candidates = propagation_candidates(wiki, repo, conn)

    # The Bedrock stack is required to judge; absent it (plugin branch) we make
    # no proposals and stamp nothing (mirrors scan._drift_flag_pass early-out).
    if make_llm is None or SubagentPool is None:
        return PropagateDriftResult(0, len(candidates), 0, 0, 0, dry_run, [])

    # --only: an entity (uri/stem) narrows the candidate set; otherwise a target
    # (slug/page-stem) narrows the target set (§3.8, test 13).
    only_target: str | None = None
    if only is not None:
        entity_match = [c for c in candidates if c.uri == only or c.stem == only]
        if entity_match:
            candidates = entity_match
        else:
            only_target = only

    targets = _build_targets(candidates, build_entity_backlink_map(wiki))
    if only_target is not None:
        targets = {
            p: e
            for p, e in targets.items()
            if e["target_slug"] == only_target or p.stem == only_target
        }

    # Ledger pre-filter: drop targets the human already disposed of (§3.3).
    settled = {
        (rec["kind"], rec["target_slug"])
        for rec in list_proposals(wiki)
        if rec["status"] in HUMAN_DECIDED
    }
    pages_skipped_settled = 0
    judge_targets: list[dict] = []
    for entry in targets.values():
        if (entry["kind"], entry["target_slug"]) in settled:
            pages_skipped_settled += 1
            continue
        judge_targets.append(entry)

    # Processed candidates get the anchor stamp: every candidate in scope whose
    # backlinkers were considered — INCLUDING those whose targets were all
    # pre-filtered out (§3.5). In target-only mode, scope is just the candidates
    # backlinking the chosen page.
    if only_target is not None:
        seen_ids: set[int] = set()
        processed: list[PropagationCandidate] = []
        for entry in targets.values():
            for c in entry["candidates"]:
                if id(c) not in seen_ids:
                    seen_ids.add(id(c))
                    processed.append(c)
    else:
        processed = candidates

    items: list[tuple] = []
    for entry in judge_targets:
        body = entry["page_path"].read_text(encoding="utf-8")
        title = _page_title(entry["page_path"], entry["target_slug"])
        entity_tuples = [(c.stem, c.narrative, c.changed_files) for c in entry["candidates"]]
        items.append(
            (entry["kind"], entry["target_slug"], title, body, entity_tuples, entry)
        )

    verdicts: list[tuple] = []
    if items:
        cfg = load_role_config("drift_propagator")
        llm = make_llm("drift_propagator", model_override=model_override)
        pool = SubagentPool(trace_dir=graph_dir(wiki.parent) / "traces")

        async def judge(item: tuple) -> "TaskResult":
            kind, _slug, title, body, entity_tuples, _entry = item
            system_msg, human_msg = build_drift_propagator_prompt(kind, title, body, entity_tuples)
            resp = await llm.ainvoke(
                [SystemMessage(content=system_msg), HumanMessage(content=human_msg)]
            )
            return TaskResult(value=parse_drift_propagator_verdict(resp.content), response=resp)

        fan = await pool.run_all(
            items,
            judge,
            "drift_propagator",
            model_id=cfg["model_id"],
            max_concurrency=cfg["max_concurrency"],
        )
        verdicts = list(fan.successes)

    pages_stale = 0
    notes_written = 0
    report: list[dict] = []
    for item, verdict in verdicts:
        kind, slug, title, _body, _entity_tuples, entry = item
        if not (isinstance(verdict, dict) and verdict.get("stale")):
            continue
        findings = verdict.get("findings") or []
        by_stem = {c.stem: c for c in entry["candidates"]}
        origins_written: list[dict] = []
        for finding in findings:
            cand = by_stem.get(finding.get("entity_stem"))
            if cand is None:
                continue  # finding references an entity not in this page's batch
            origin = {
                "ref": f"entities/{cand.stem}",
                "source": "drift",
                "detected_commit": cand.last_updated_commit,
                "hash": section_hash(cand.narrative),
                "rationale": str(finding.get("rationale", "")),
            }
            if not dry_run:
                upsert_proposal(
                    wiki,
                    {
                        "kind": kind,
                        "mode": "update_existing",
                        "target_slug": slug,
                        "title": title,
                        "origin": origin,
                    },
                )
            origins_written.append(origin)
        if origins_written:
            pages_stale += 1
            if not dry_run:
                notes_written += 1  # nothing is written in a dry run
            report.append({"kind": kind, "target_slug": slug, "origins": origins_written})

    if not dry_run:
        for c in processed:
            try:
                update_frontmatter(c.page_path, {DRIFT_PROPAGATED_COMMIT_KEY: c.last_updated_commit})
            except Exception as exc:  # noqa: BLE001 — non-fatal stamp
                logger.warning("drift_propagated stamp failed for %s: %s", c.page_path, exc)

    return PropagateDriftResult(
        pages_judged=len(items),
        entities_considered=len(processed),
        notes_written=notes_written,
        pages_stale=pages_stale,
        pages_skipped_settled=pages_skipped_settled,
        dry_run=dry_run,
        proposals=report,
    )
