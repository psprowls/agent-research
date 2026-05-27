"""Entity writer scaffold — locks the Phase 42 design contracts (D-10).

This module is the single source of truth for THREE contracts that every
downstream entity-writing phase (43-46) depends on:

1. **URI-to-filename slug encoding (D-01..D-05).**
   `encode_slug` maps a graph URI to a vault filename stem by replacing
   both `:` and `/` with `__` (double-underscore). The kind segment uses
   single-underscore (`test_suite`, `entry_point`, `package_family`) so it
   cannot collide with the separator. Injectivity holds because no admitted
   URI prefix contains `__`. Round-trip via `decode_slug` requires splitting
   on `__` and asserting the first segment is an admitted URI prefix
   (e.g. `pkg`, `repo`, `domain`). Note that URI prefixes are short aliases
   of the admitted kind names (`pkg` <-> `package`, `repo` <-> `repository`).
   See `_URI_PREFIX_BY_KIND` below for the full mapping.

   Worked examples (from `agent-research` itself):

     pkg:agent-research/graph-io           -> pkg__agent-research__graph-io
     domain:agent-research/billing         -> domain__agent-research__billing
     test_suite:agent-research/eval/unit   -> test_suite__agent-research__eval__unit
     package_family:aws                    -> package_family__aws
     plugin:graph-wiki                     -> plugin__graph-wiki
     dependency:pypi/boto3                 -> dependency__pypi__boto3
     repo:agent-research/agent-research    -> repo__agent-research__agent-research

2. **Scanner-owned frontmatter whitelist (D-06..D-09).**
   `SCANNER_OWNED_KEYS` is a flat frozenset enumerating every frontmatter
   key the scanner is allowed to overwrite on the next scan. Everything
   outside this set is human-territory and preserved as-is when the
   scanner re-renders an entity page (Phase 43 `merge_frontmatter`).

   Human-only keys are NOT enumerated as a constant (D-09); the explicit
   examples documented for readers are: `status`, `last_reviewed`, `owner`,
   `notes`. A unit test asserts disjointness from these four.

3. **Narrative region marker (D-16).**
   Per-kind templates carry a `## Narrative` H2 section that the LLM
   scanner targets and overwrites; everything outside that H2 (including
   other human-authored H2 sections) is preserved. Phase 42 does NOT
   implement the narrative-write path; it locks the contract. The H2
   string is a hard convention — humans must not rename the heading.

The Phase 42 scaffold is intentionally narrow: only the four exports below
plus this module docstring. Phase 43 expands the module with
`EntityWriteResult`, `merge_frontmatter`, `write_entities`, and hard-delete
logic; do NOT add those here.
"""

from __future__ import annotations

# v1.8 admitted entity kinds — the 7 graph-derived kinds the wiki materializes
# as standalone pages under `wiki/entities/`. Underscore-form per D-02 matches
# `graph_io.queries._VALID_KINDS` casing. Phase 43+ imports this constant when
# routing graph rows to the correct template / URI builder.
ADMITTED_KINDS: frozenset[str] = frozenset(
    {
        "repository",
        "domain",
        "package",
        "package_family",
        "plugin",
        "dependency",
        "test_suite",
    }
)

# Map admitted kind names to their URI prefix as produced by `graph_io.uri`
# builders. Two prefixes are shortened aliases of the kind name (`repository`
# -> `repo`, `package` -> `pkg`); the remaining five are identical. This is
# the surface `decode_slug` validates against, since slugs start with the
# URI-prefix, not the kind name.
_URI_PREFIX_BY_KIND: dict[str, str] = {
    "repository": "repo",
    "domain": "domain",
    "package": "pkg",
    "package_family": "package_family",
    "plugin": "plugin",
    "dependency": "dependency",
    "test_suite": "test_suite",
}
_ADMITTED_URI_PREFIXES: frozenset[str] = frozenset(_URI_PREFIX_BY_KIND.values())

# Frontmatter keys the scanner owns and may overwrite on every scan.
# Anything outside this set is human-authored and MUST be preserved by
# `merge_frontmatter` in Phase 43.
#
# Documented human-only keys (NOT in this whitelist; do not add):
#   - status          (e.g. `deprecated`, `active`, `experimental`)
#   - last_reviewed   (ISO date, human-recorded review checkpoint)
#   - owner           (free-form owner annotation)
#   - notes           (free-form human notes)
SCANNER_OWNED_KEYS: frozenset[str] = frozenset(
    {
        # Universal
        "uri",
        "kind",
        "graph_name",
        "last_scan_at",
        # Edge-derived (package)
        "domains",
        "depends_on",
        "test_suites",
        "entry_points",
        # Node-attr-derived (package)
        "language",
        "version",
        # Edge-derived (domain)
        "parent_domain",
        "sub_domains",
        "packages",
        # Edge-derived (test_suite)
        "tested_packages",
        "suite_kind",
        "file_count",
        # Edge-derived (dependency)
        "ecosystem",
        "used_by",
        "versions_in_use",
        # Edge-derived (package_family)
        "members",
        # Edge-derived (repository)
        "package_count",
    }
)


def encode_slug(uri: str) -> str:
    """Encode a graph URI as a vault filename stem (D-01).

    Replaces `:` and `/` with `__`. Injective and round-trip-stable across
    all 7 admitted kinds for fragments that DO NOT contain `__` AND DO NOT
    start or end with `_`. Real-world org / repo / package / suite names
    follow these constraints (PEP-8 / npm / cargo naming conventions prefer
    dashes to leading-underscore identifiers in distribution names).
    """
    return uri.replace(":", "__").replace("/", "__")


def decode_slug(slug: str) -> str:
    """Decode a vault filename stem back to its graph URI (D-03).

    Splits on `__`, asserts the first segment is in `ADMITTED_KINDS`, and
    reconstructs the URI as `<kind>:<remaining_segments_joined_by_/>`.

    Raises:
        ValueError: if `slug` has fewer than 2 `__`-separated segments,
            or if the first segment is not a recognized admitted kind.
    """
    segments = slug.split("__")
    if len(segments) < 2:
        raise ValueError(
            f"decode_slug: malformed slug {slug!r}: expected at least 2 "
            f"`__`-separated segments (kind + path), got {len(segments)}"
        )
    prefix, *path_segments = segments
    if prefix not in _ADMITTED_URI_PREFIXES:
        raise ValueError(
            f"decode_slug: unknown URI prefix {prefix!r} in slug {slug!r}: "
            f"expected one of {sorted(_ADMITTED_URI_PREFIXES)}"
        )
    return f"{prefix}:{'/'.join(path_segments)}"
