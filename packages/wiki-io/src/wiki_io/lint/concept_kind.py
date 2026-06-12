"""Concept-kind checks: invalid `kind:` on concepts/ pages and a residual
legacy `architecture/` directory (the fold's migration nudge)."""

from __future__ import annotations

from pathlib import Path

from wiki_io.concept_kinds import CONCEPT_KINDS

GROUP = "concept_kind"


def check(pages: dict, wiki: Path) -> list[str]:
    """Two warnings, never errors.

    1. Invalid kind — a concepts/ page whose `kind:` is not in CONCEPT_KINDS.
       A missing/blank kind is silent: defaulting to `concept` is by design.
    2. Legacy directory — wiki/architecture/ containing anything beyond an
       index.md stub. Existing vaults keep working; this is the migration
       nudge to fold pages into concepts/ with `kind: architecture`.
    """
    issues: list[str] = []
    for key, page in pages.items():
        if not key.startswith("concepts/"):
            continue
        raw = str(page["fm"].get("kind") or "").strip()
        if raw and raw not in CONCEPT_KINDS:
            issues.append(f"{key}: unknown `kind: {raw}` — expected one of {', '.join(CONCEPT_KINDS)}")
    legacy = wiki / "architecture"
    if legacy.is_dir():
        residual = [p for p in sorted(legacy.rglob("*.md")) if p.name != "index.md"]
        if residual:
            names = ", ".join(f"architecture/{p.relative_to(legacy)}" for p in residual)
            issues.append(
                f"legacy architecture/ directory: fold {names} into concepts/ "
                "with `kind: architecture` and delete the directory"
            )
    return issues
