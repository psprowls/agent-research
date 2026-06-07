"""Living Wiki M3 — inline page-suggestion pass for run_ingest_source.

After a Source page lands, propose which concept/adr/architecture pages the
document justifies and record each as a note in the proposal ledger
(`wiki/proposals/<kind>-<target_slug>.md`) via wiki_io.proposals.upsert_proposal.
Propose only — nothing is written under concepts/ / adrs/ / architecture/, and
the Source page is no longer mutated.

Public API:
    SUGGESTION_KINDS, EXTRACT_PREVIEW_CHARS
    parse_extractor_response(text) -> (list[dict], bool)
    build_curated_vault_index(wiki) -> list[dict]
    build_extract_suggestions_prompt(source_text, vault_index) -> str
    run_suggest_phase(*, wiki, page_path) -> (list[dict], bool)
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import make_llm
from wiki_io.ingest_source import slugify
from wiki_io.proposals import upsert_proposal
from wiki_io.update_index import parse_frontmatter

from graph_wiki_core.prompts.extractor import EXTRACTOR_SYSTEM

logger = logging.getLogger(__name__)

SUGGESTION_KINDS = frozenset({"concept", "adr", "architecture"})
EXTRACT_PREVIEW_CHARS = 4000

# Canonical key order for a validated proposal dict (cosmetic; the ledger owns serialization).
_ENTRY_KEY_ORDER = (
    "kind",
    "title",
    "slug",
    "mode",
    "existing_slug",
    "rank",
    "confidence",
    "rationale",
    "evidence",
    "existing_pages_considered",
    "reasoning_summary",
    "potential_conflicts",
    "implementation_notes",
    "status",
)


def _ordered_entry(d: dict) -> dict:
    """Return a new dict with the canonical key order (omitting absent keys)."""
    return {k: d[k] for k in _ENTRY_KEY_ORDER if k in d}


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _validate_proposal(raw: object) -> dict | None:
    """Normalize one extractor proposal into a proposal dict, or None if invalid.

    Required: kind in SUGGESTION_KINDS, a non-empty title, a slug. mode defaults
    to create_new (and is forced to create_new when not update_existing).
    NOTE: no `status` key — upsert_proposal stamps that.
    """
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind", "")).strip().lower()
    if kind not in SUGGESTION_KINDS:
        return None
    title = str(raw.get("title", "")).strip()
    slug_src = str(raw.get("slug", "")).strip()
    if not title or not slug_src:
        return None
    slug = slugify(slug_src)
    mode = str(raw.get("mode", "")).strip().lower()
    if mode != "update_existing":
        mode = "create_new"
    existing_raw = raw.get("existing_slug")
    existing_slug = slugify(str(existing_raw).strip()) if existing_raw else None
    try:
        rank = int(raw.get("rank", 999))
    except (OverflowError, TypeError, ValueError):
        rank = 999
    confidence = str(raw.get("confidence", "medium")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    rationale = str(raw.get("rationale", "")).strip()
    reasoning_summary = str(raw.get("reasoning_summary", "")).strip()
    return _ordered_entry(
        {
            "kind": kind,
            "title": title,
            "slug": slug,
            "mode": mode,
            "existing_slug": existing_slug,
            "rank": rank,
            "confidence": confidence,
            "rationale": rationale,
            "evidence": _string_list(raw.get("evidence")),
            "existing_pages_considered": _string_list(raw.get("existing_pages_considered")),
            "reasoning_summary": reasoning_summary,
            "potential_conflicts": _string_list(raw.get("potential_conflicts")),
            "implementation_notes": _string_list(raw.get("implementation_notes")),
        }
    )


def parse_extractor_response(text: str) -> tuple[list[dict], bool]:
    """Parse the extractor LLM output into (proposals, parsed).

    parsed is True whenever a well-formed list was recovered (including an empty
    one). It is False only on a YAML error or an unexpected top-level shape.
    """
    if text is None:
        return [], False
    stripped = text.strip()
    # Defensive: strip a leading ```yaml / ``` fence and a trailing ``` line.
    if stripped.startswith("```"):
        nl = stripped.find("\n")
        if nl == -1:
            return [], False
        stripped = stripped[nl + 1 :]
        last = stripped.rfind("```")
        if last != -1:
            stripped = stripped[:last]
        stripped = stripped.strip()

    try:
        loaded = yaml.safe_load(stripped)
    except yaml.YAMLError:
        return [], False

    if isinstance(loaded, dict) and isinstance(loaded.get("suggestions"), list):
        items = loaded["suggestions"]
    elif isinstance(loaded, list):
        items = loaded
    elif isinstance(loaded, dict) and "suggestions" in loaded and loaded["suggestions"] is None:
        # `suggestions:` with an empty/blank value -> zero proposals, still parsed.
        items = []
    else:
        return [], False

    proposals: list[dict] = []
    for item in items:
        norm = _validate_proposal(item)
        if norm is not None:
            proposals.append(norm)
    proposals.sort(key=lambda proposal: int(proposal.get("rank", 999)))
    return proposals[:5], True


# Directory name -> curated page kind.
_CURATED_DIRS = {"concepts": "concept", "adrs": "adr", "architecture": "architecture"}


def build_curated_vault_index(wiki: Path) -> list[dict]:
    """List existing curated pages as [{kind, slug, title, summary}].

    Cheap dedup substrate (spec §3.6): walks concepts/ / adrs/ / architecture/
    and reads title/summary from frontmatter only. No graph, no retrieval.
    """
    index: list[dict] = []
    for dirname, kind in _CURATED_DIRS.items():
        d = wiki / dirname
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            try:
                fm = parse_frontmatter(md.read_text(encoding="utf-8"))
            except OSError:
                continue
            index.append(
                {
                    "kind": kind,
                    "slug": md.stem,
                    "title": fm.get("title", md.stem),
                    "summary": fm.get("summary", ""),
                }
            )
    return index


def build_extract_suggestions_prompt(source_text: str, vault_index: list[dict]) -> str:
    """Human message for the extractor: source-backed proposal context + curated-vault index."""
    preview = source_text[:EXTRACT_PREVIEW_CHARS]
    if len(source_text) > EXTRACT_PREVIEW_CHARS:
        preview += "\n[TRUNCATED]"

    if vault_index:
        index_lines = "\n".join(
            f"  - {e['kind']}/{e['slug']} — {e.get('title', '')}" + (f" — {e['summary']}" if e.get("summary") else "")
            for e in vault_index
        )
    else:
        index_lines = "  (no curated pages yet)"

    return (
        "Existing curated pages (propose update_existing when your idea is "
        "already covered by one of these; otherwise create_new):\n"
        f"{index_lines}\n\n"
        "--- Source-backed proposal context ---\n"
        f"{preview}\n"
        "--- End source-backed proposal context ---\n\n"
        "Normalize this context into the concept/adr/architecture page proposals it justifies, as a "
        "YAML `suggestions:` list. Return `suggestions: []` if none are warranted."
    )


async def run_suggest_phase(
    *,
    wiki: Path,
    page_path: Path,
) -> tuple[list[dict], bool]:
    """Inline suggest phase: propose derived pages into the proposal ledger.

    For each validated extractor proposal, upsert a `proposals/` note keyed by
    `<kind>-<target_slug>` (the existing_slug when mode=update_existing, else the
    proposed slug), with an `ingest` origin pointing at this Source page. The
    ledger owns the per-note merge (human decisions survive re-ingest because a
    decided note is left untouched), so no prior-state capture is needed.

    Best-effort (spec §3.5): on an extractor error or parse miss, write ZERO
    notes and return ([], False). The suggest phase never fails an ingest.

    Returns (reports, parsed) where each report is a dict shaped
    {kind, title, slug, mode, status} (slug == target_slug) — the report shape
    the CLI/MCP already consume (spec §3.6).
    """
    page_text = page_path.read_text(encoding="utf-8")
    vault_index = build_curated_vault_index(wiki)
    prompt = build_extract_suggestions_prompt(page_text, vault_index)

    try:
        llm = make_llm("extractor")
        resp = await llm.ainvoke([SystemMessage(EXTRACTOR_SYSTEM), HumanMessage(prompt)])
    except Exception:
        logger.warning("extractor LLM call failed; skipping suggestions", exc_info=True)
        return [], False

    if not isinstance(resp.content, str):
        logger.warning("extractor LLM returned non-text content; skipping suggestions")
        return [], False

    proposals, parsed = parse_extractor_response(resp.content)
    if not parsed:
        return [], False

    source_ref = f"sources/{page_path.stem}"
    reports: list[dict] = []
    for p in proposals:
        if p["mode"] == "update_existing" and p.get("existing_slug"):
            target_slug = p["existing_slug"]
        else:
            target_slug = p["slug"]
        origin = {
            "ref": source_ref,
            "source": "ingest",
            "rationale": p.get("rationale", ""),
        }
        for key in (
            "evidence",
            "existing_pages_considered",
            "potential_conflicts",
            "implementation_notes",
        ):
            if p.get(key):
                origin[key] = p[key]
        if p.get("reasoning_summary"):
            origin["reasoning_summary"] = p["reasoning_summary"]
        record = upsert_proposal(
            wiki,
            {
                "kind": p["kind"],
                "mode": p["mode"],
                "target_slug": target_slug,
                "title": p["title"],
                "rank": p["rank"],
                "confidence": p["confidence"],
                "origin": origin,
            },
        )
        reports.append(
            {
                "kind": record["kind"],
                "title": record["title"],
                "slug": record["target_slug"],
                "mode": record["mode"],
                "rank": record.get("rank", p["rank"]),
                "confidence": record.get("confidence", p["confidence"]),
                "status": record["status"],
            }
        )
    return reports, True
