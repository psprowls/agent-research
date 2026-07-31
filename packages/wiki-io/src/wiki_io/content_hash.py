"""M4 content-hash primitives for drift detection on curated pages.

Relocated from the now-deleted ``drift.py`` (Living Wiki M2e teardown): after
M2e's intra-page drift judge was removed, these three symbols were the only
still-live survivors — the M4 content-hash baseline used by
``propagate_drift.py``.
"""

from __future__ import annotations

import hashlib

__all__ = [
    "CONTENT_HASH_KEY",
    "section_hash",
    "page_body_hash",
]

# Living Wiki M4 extension: frontmatter key for the content-hash detection
# baseline on curated (concept/ADR) pages. NOT in DATA_KEYS (that frozenset
# only governs entity-page re-render) — stamped by
# propagate_drift._stamp_curated_page_if_changed, preserved otherwise.
CONTENT_HASH_KEY = "content_hash"


def section_hash(chunk: str) -> str:
    """SHA-256 hex digest of a section ``chunk`` (heading + body), whitespace
    stripped so trailing-newline churn never looks like an edit."""
    return hashlib.sha256(chunk.strip().encode("utf-8")).hexdigest()


def page_body_hash(body: str) -> str:
    """SHA-256 hex digest of a curated (concept/ADR) page body, frontmatter
    already stripped by the caller. Mirrors ``section_hash``'s approach but
    over the whole body rather than one H2 section — the M4 content-hash
    detection pass (``propagate_drift.py``) uses it to notice hand-edits."""
    return section_hash(body)
