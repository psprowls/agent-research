"""URI -> slug derivation (Phase 39/40 shared invariant).

The graph is the source of truth for the canonical slug of an entity-backed
wiki page. Both the scanner (Phase 39, future refactor) and the ingestor
(Phase 40, now) consult the graph and derive the slug by taking the URI's
last segment.

The page-type routing prefix (`apps/`, `domains/<d>/packages/`, `packages/`)
is chosen elsewhere — `commands/ingest._route_target_path` for the ingestor;
`wiki_io.scan_monorepo._wiki_relative_path_for` for the scanner. This module
returns only the slug.
"""
from __future__ import annotations


def slug_from_uri(uri: str) -> str:
    """Return the last URI segment as the canonical slug.

    Examples:
      pkg:org/repo/graph-io        -> "graph-io"
      pkg:org/repo/sub/graph-io    -> "graph-io"
      cls:graph_io.store.Foo       -> "graph_io.store.Foo"  (scheme-only stripped)

    The returned slug is returned verbatim; callers that need filename
    sanitization should pass it through `wiki_io.ingest_source.slugify`
    afterward. Today's URIs from `packages.refresh` are already filename-safe.

    Raises:
      ValueError: empty input or derived tail is empty.
    """
    if not uri:
        raise ValueError("uri must be non-empty")
    tail = uri.rsplit("/", 1)[-1]
    tail = tail.rsplit(":", 1)[-1]
    if not tail:
        raise ValueError(f"could not derive slug from uri: {uri!r}")
    return tail
