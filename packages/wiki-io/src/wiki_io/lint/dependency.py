"""Dependency layer: validate `category: dependency` pages — kind discriminator,
per-kind required fields, family/member back-pointers, stub detection.

Filesystem-only at this point; graph-aware variants (e.g. checking that a
member is actually imported anywhere in the codebase) are deferred to the
follow-on plan once the graph-aware extension ships.
"""

from __future__ import annotations

from pathlib import Path

from wiki_io.lint.common import parse_inline_list

GROUP = "dependency_layer"

VALID_KINDS = {"package", "package-family", "service"}


def _is_dependency(page: dict) -> bool:
    return page["fm"].get("category") == "dependency"


def check(pages: dict, *, workspaces: list[dict] | None = None) -> list[str]:
    """Run dependency_layer rules. Returns one finding string per issue."""
    findings: list[str] = []

    # Per-page rules and an index of family pages keyed by family_name
    family_pages: dict[str, dict] = {}
    package_family_claims: dict[str, list[str]] = {}
    for key, page in pages.items():
        if not _is_dependency(page):
            continue
        fm = page["fm"]
        kind = (fm.get("kind") or "").strip()
        if not kind or kind not in VALID_KINDS:
            findings.append(f"{key}: dep-kind-not-in-enum: kind='{kind}' not in {{package | package-family | service}}")
            # Skip per-kind checks when kind is invalid — they wouldn't be meaningful.
            continue

        if kind == "package":
            if not (fm.get("ecosystem") or "").strip():
                findings.append(f"{key}: dep-package-without-ecosystem: ecosystem: missing")
            family = (fm.get("family") or "").strip()
            if family:
                package_family_claims.setdefault(key, []).append(family)
        elif kind == "service":
            if not (fm.get("provider") or "").strip():
                findings.append(f"{key}: dep-service-without-provider: provider: missing")
        elif kind == "package-family":
            members = parse_inline_list(fm.get("members", ""))
            if not members:
                findings.append(f"{key}: dep-family-without-members: members: empty or missing")
            family_name = (fm.get("family_name") or Path(key).name).strip()
            family_pages[family_name] = {"key": key, "fm": fm, "members": members}

        # dep-detail-without-load-bearing: package detail pages must declare load_bearing.
        # Only applies to kind == "package" — service and package-family pages are not
        # individual dependency detail pages in the same semantic sense.
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

    # Cross-page rules

    # dep-family-member-not-in-scan: each `members:` entry resolves to a scanned workspace dep
    if workspaces is not None:
        scanned_dep_names = _scanned_dependency_names(workspaces)
        for family_name, fp in family_pages.items():
            for member in fp["members"]:
                if member not in scanned_dep_names:
                    findings.append(
                        f"{fp['key']}: dep-family-member-not-in-scan: '{member}' not found in any scanned manifest"
                    )

    # dep-family-back-pointer-mismatch: package's family: matches a family page that lists it,
    # and family page's members: each have a package page (or no page) with matching family:
    pkg_pages_by_name: dict[str, dict] = {}
    for key, page in pages.items():
        if not _is_dependency(page):
            continue
        if (page["fm"].get("kind") or "").strip() != "package":
            continue
        name = (page["fm"].get("package_name") or Path(key).name).strip()
        pkg_pages_by_name[name] = {"key": key, "fm": page["fm"]}

    for pkg_name, pkg in pkg_pages_by_name.items():
        family = (pkg["fm"].get("family") or "").strip()
        if not family:
            continue
        fp = family_pages.get(family)
        if fp is None:
            findings.append(
                f"{pkg['key']}: dep-family-back-pointer-mismatch: family='{family}' but no family page for it"
            )
            continue
        if pkg_name not in fp["members"]:
            findings.append(
                f"{pkg['key']}: dep-family-back-pointer-mismatch: '{pkg_name}' "
                f"claims family '{family}' but the family page does not list it"
            )

    # dep-multiple-families: a package listed by two family pages
    membership_owners: dict[str, list[str]] = {}
    for family_name, fp in family_pages.items():
        for member in fp["members"]:
            membership_owners.setdefault(member, []).append(family_name)
    for member, families in membership_owners.items():
        if len(families) > 1:
            findings.append(f"dependencies/{member}: dep-multiple-families: claimed by {', '.join(sorted(families))}")

    return findings


def _body_line_count(text: str) -> int:
    """Count non-empty body lines after the YAML frontmatter block."""
    body = text
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4 :]
    return sum(1 for ln in body.splitlines() if ln.strip())


def _scanned_dependency_names(workspaces: list[dict]) -> set[str]:
    """Collect every dependency name (any field) referenced by scanned workspaces.

    Reads both raw-manifest field names (``dependencies``/``devDependencies``/
    ``peerDependencies``) and the scanner's derived fields (``depends_on`` for
    internal workspace references, ``external_deps`` for the merged external
    dependency map). Without ``external_deps`` the family-member check sees
    nothing for normal monorepos — the scanner doesn't emit raw-manifest
    fields, only the derived ones.
    """
    names: set[str] = set()
    for w in workspaces:
        for field in (
            "dependencies",
            "devDependencies",
            "peerDependencies",
            "depends_on",
            "external_deps",
        ):
            value = w.get(field)
            if isinstance(value, dict):
                names.update(value.keys())
            elif isinstance(value, list):
                names.update(value)
    return names
