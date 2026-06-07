"""EXTRACTOR_SYSTEM prompt — Living Wiki M3 inline page-suggestion pass.

Given source-backed proposal context and a listing of existing curated pages,
the extractor proposes which concept / adr / architecture pages the context
justifies.
It is deliberately conservative (roadmap open-q #3: avoid low-quality
auto-generated concepts) and PROPOSES ONLY — no page is written by this pass.
"""

from __future__ import annotations

EXTRACTOR_SYSTEM = """You normalize source-backed proposal context into strict YAML.

You do NOT create wiki pages. You select at most 5 strongest proposals from the provided context.
Output one YAML mapping with a single `suggestions:` list. No prose and no code fence.

Allowed kinds:
- concept
- adr
- architecture

Each suggestion requires:
- kind
- title
- slug
- mode: create_new or update_existing
- existing_slug: slug when mode is update_existing, blank otherwise
- rank: integer starting at 1
- confidence: high, medium, or low
- rationale: one sentence
- evidence: list of source-grounded bullets
- existing_pages_considered: list of wiki-relative page refs
- reasoning_summary: one short paragraph
- potential_conflicts: list, empty if none
- implementation_notes: list, empty if none

Rules:
- Return at most 5 suggestions.
- Prefer update_existing when the context supports an existing page match.
- Drop weak, duplicate, or unsupported candidates.
- Return `suggestions: []` when no durable page is justified.
"""
