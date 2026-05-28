"""Dependency layer: validate `category: dependency` pages — kind discriminator,
per-kind required fields, stub detection.

Filesystem-only at this point; graph-aware variants (e.g. checking that a
member is actually imported anywhere in the codebase) are deferred to the
follow-on plan once the graph-aware extension ships.

Phase 51 PKGFAM-03 (RESEARCH.md Pitfall 3 Option A): the family-grouping
kind discriminator was retired alongside the graph-io kind retraction.
Future "dependency-family / dependency clustering" work is deferred per
REQUIREMENTS.md "Future Requirements" and will be modeled on
domain-clustering primitives rather than a separate kind.
"""

from __future__ import annotations

GROUP = "dependency_layer"

VALID_KINDS = {"package", "service"}


def _is_dependency(page: dict) -> bool:
    return page["fm"].get("category") == "dependency"


def check(pages: dict, *, workspaces: list[dict] | None = None) -> list[str]:
    """Run dependency_layer rules. Returns one finding string per issue."""
    findings: list[str] = []

    for key, page in pages.items():
        if not _is_dependency(page):
            continue
        fm = page["fm"]
        kind = (fm.get("kind") or "").strip()
        if not kind or kind not in VALID_KINDS:
            findings.append(f"{key}: dep-kind-not-in-enum: kind='{kind}' not in {{package | service}}")
            # Skip per-kind checks when kind is invalid — they wouldn't be meaningful.
            continue

        if kind == "package":
            if not (fm.get("ecosystem") or "").strip():
                findings.append(f"{key}: dep-package-without-ecosystem: ecosystem: missing")
        elif kind == "service":
            if not (fm.get("provider") or "").strip():
                findings.append(f"{key}: dep-service-without-provider: provider: missing")

        # dep-detail-without-load-bearing: package detail pages must declare load_bearing.
        # Only applies to kind == "package" — service pages are not individual
        # dependency detail pages in the same semantic sense.
        if kind == "package":
            load_bearing = (fm.get("load_bearing") or "").strip().lower()
            if load_bearing not in ("true", "yes", "1"):
                findings.append(f"{key}: dep-detail-without-load-bearing: detail page exists but load_bearing != true")

        # dep-stub-detail-page: body <15 lines beyond frontmatter
        body_lines = _body_line_count(page["text"])
        if body_lines < 15:
            findings.append(
                f"{key}: dep-stub-detail-page: only {body_lines} body lines beyond frontmatter "
                f"(<15 — flesh out or delete and rely on dependencies/index.md)"
            )

    return findings


def _body_line_count(text: str) -> int:
    """Count non-empty body lines after the YAML frontmatter block."""
    body = text
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4 :]
    return sum(1 for ln in body.splitlines() if ln.strip())
