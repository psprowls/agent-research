from __future__ import annotations

"""Living Wiki M3 — inline page-suggestion pass for run_ingest_source.

After a Source page lands, propose which concept/adr/architecture pages the
document justifies and record them as `suggested_pages` frontmatter plus a
regenerated `## Suggested pages` body section. Propose only — nothing is written
under concepts/ / adrs/ / architecture/.

Public API:
    SUGGESTION_KINDS, HUMAN_DECIDED, EXTRACT_PREVIEW_CHARS
    parse_extractor_response(text) -> (list[dict], bool)
    build_curated_vault_index(wiki) -> list[dict]
    merge_suggested_pages(existing, proposals) -> list[dict]
    read_suggested_pages(text) -> list[dict]
    set_suggested_pages_in_frontmatter(text, entries) -> str
    render_suggested_pages_section(entries) -> str
    set_suggested_pages_section_in_body(text, section) -> str
    build_extract_suggestions_prompt(source_text, vault_index) -> str
    run_suggest_phase(...) -> (list[dict], bool)
"""

import logging
from pathlib import Path

import yaml
from wiki_io.ingest_source import slugify
from wiki_io.update_index import parse_frontmatter

logger = logging.getLogger(__name__)

SUGGESTION_KINDS = frozenset({"concept", "adr", "architecture"})
HUMAN_DECIDED = frozenset({"approved", "rejected", "created"})
EXTRACT_PREVIEW_CHARS = 4000

# Fixed key order so yaml.safe_dump(..., sort_keys=False) is deterministic.
_ENTRY_KEY_ORDER = ("kind", "title", "slug", "mode", "existing_slug", "rationale", "status")


def _ordered_entry(d: dict) -> dict:
    """Return a new dict with the canonical key order (omitting absent keys)."""
    return {k: d[k] for k in _ENTRY_KEY_ORDER if k in d}


def _validate_proposal(raw: object) -> dict | None:
    """Normalize one extractor proposal into a proposal dict, or None if invalid.

    Required: kind in SUGGESTION_KINDS, a non-empty title, a slug. mode defaults
    to create_new (and is forced to create_new when not update_existing).
    NOTE: no `status` key — merge_suggested_pages stamps that.
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
    rationale = str(raw.get("rationale", "")).strip()
    return _ordered_entry(
        {
            "kind": kind,
            "title": title,
            "slug": slug,
            "mode": mode,
            "existing_slug": existing_slug,
            "rationale": rationale,
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
    return proposals, True


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


def merge_suggested_pages(existing: list[dict], proposals: list[dict]) -> list[dict]:
    """Merge new proposals into the existing suggested_pages list (spec §3.4).

    - Human-decided entries (status in HUMAN_DECIDED) are preserved in place and
      never mutated.
    - A still-`proposed` entry whose (kind, slug) matches a new proposal is
      refreshed in place from that proposal (status stays `proposed`).
    - An orphaned `proposed` entry (no matching proposal) is preserved.
    - Genuinely new proposals (key not already present) are appended as
      `proposed`, in proposal order, deduped by key.
    - A proposal whose key matches ANY existing entry is not appended again.
    """
    prop_by_key: dict[tuple[str, str], dict] = {}
    for p in proposals:  # first occurrence wins (dedup)
        prop_by_key.setdefault((p["kind"], p["slug"]), p)

    existing_keys = {(e["kind"], e["slug"]) for e in existing}

    result: list[dict] = []
    for e in existing:
        key = (e["kind"], e["slug"])
        if e.get("status") in HUMAN_DECIDED:
            result.append(e)  # untouched
        elif key in prop_by_key:
            refreshed = dict(prop_by_key[key])
            refreshed["status"] = "proposed"
            result.append(_ordered_entry(refreshed))
        else:
            result.append(e)  # orphaned proposed: preserve

    for p in proposals:
        key = (p["kind"], p["slug"])
        if key in existing_keys:
            continue
        if any((r["kind"], r["slug"]) == key for r in result):
            continue  # already appended (duplicate proposal)
        appended = dict(p)
        appended["status"] = "proposed"
        result.append(_ordered_entry(appended))

    return result
