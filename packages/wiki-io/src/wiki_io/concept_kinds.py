"""concept_kinds.py — single source of truth for concept-page kinds.

Pages under `wiki/concepts/` carry an optional `kind:` frontmatter key with
values `concept` (default), `pattern`, or `architecture`, each backed by its
own page template. Lint validates kinds; rendering and routing must never
crash on a bad kind (tolerant-frontmatter posture).
"""

from __future__ import annotations

CONCEPT_KINDS: tuple[str, ...] = ("concept", "pattern", "architecture")
DEFAULT_CONCEPT_KIND = "concept"

# Template filenames under assets/page-templates/ (copied to wiki/.templates/
# at bootstrap). Consumed by agents as reference and by the proposal-scaffold
# action text — not selected by deterministic page-writing code.
KIND_TEMPLATES: dict[str, str] = {
    "concept": "concept.md",
    "pattern": "concept-pattern.md",
    "architecture": "concept-architecture.md",
}

# Index rendering: sub-group order and labels for the Concepts lane.
# Architecture first — syntheses keep the top prominence the old standalone
# Architecture lane had.
KIND_GROUP_ORDER: tuple[str, ...] = ("architecture", "pattern", "concept")
KIND_GROUP_LABELS: dict[str, str] = {
    "architecture": "Architecture",
    "pattern": "Patterns",
    "concept": "Concepts",
}


def effective_kind(frontmatter: dict) -> str:
    """Read `kind`, defaulting when absent or blank.

    Returns the raw value even if unknown — validation is lint's job;
    rendering and routing must never crash on a bad kind.
    """
    value = str(frontmatter.get("kind") or "").strip()
    return value or DEFAULT_CONCEPT_KIND


def kind_group(frontmatter: dict) -> str:
    """Grouping key for index rendering: the effective kind, with unknown
    values folded into the default group (pages are never dropped)."""
    kind = effective_kind(frontmatter)
    return kind if kind in CONCEPT_KINDS else DEFAULT_CONCEPT_KIND
