"""Shared post-mutation markdown regeneration bundle.

Extracted from scan's Step 12 block so any mutation that moves or removes a
linked page (scan, ``gw work archive``) can refresh the master index, the
per-folder sub-indexes, and entity backlinks with one call.
"""

from __future__ import annotations

import logging
from pathlib import Path

from graph_io import GraphNotInitializedError, open_reader
from wiki_io.backlink_index import regenerate_referenced_in_wiki
from wiki_io.index_generator import generate_index
from wiki_io.update_index import update_index
from workspace_io import manifest as _manifest
from workspace_io.paths import manifest_path

logger = logging.getLogger(__name__)


def regen_indexes_and_backlinks(wiki: Path) -> None:
    """Regenerate wiki/index.md + per-folder sub-indexes + entity backlinks.

    Opens its own read-only reader for ``generate_index`` (graph-driven) and
    closes it; ``update_index`` and the backlink regen are graph-independent
    and always run. Each step is best-effort — a failure is logged, not
    raised — so callers never fail a larger operation on a regen hiccup.
    """
    reader = None
    try:
        reader = open_reader(wiki.parent)
    except GraphNotInitializedError:
        reader = None
    try:
        if reader is not None:
            display_name = _manifest.read(manifest_path(wiki.parent)).get("topic")
            generate_index(reader, wiki, display_name)
        try:
            update_index(wiki)
        except Exception as exc:  # noqa: BLE001
            logger.warning("update_index failed (non-fatal): %s", exc)
        try:
            regenerate_referenced_in_wiki(wiki)
        except Exception as exc:  # noqa: BLE001
            logger.warning("regenerate_referenced_in_wiki failed (non-fatal): %s", exc)
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:  # noqa: BLE001
                pass
