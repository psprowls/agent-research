"""Living Wiki M2e: `gw wiki ack-drift <entity>` — clear a page's drift flags
without editing the prose (the "I reviewed it, prose is still correct" case).

Resolves the entity (by URI or page stem) to its entity page and removes the
`drift_review` key. No LLM. Because `drift_checked_commit` already equals
`last_updated_commit` after the judge ran, the page is not re-judged until its
narrative changes again."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import frontmatter
from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.entity_writer import update_frontmatter


@dataclass
class AckDriftResult:
    page_path: Path
    cleared: int


def _resolve_entity_page(wiki: Path, entity: str) -> Path:
    """Find the entity page whose `uri` == entity, else whose filename stem ==
    entity. Raises ValueError on no match or ambiguity."""
    entities_dir = wiki / "entities"
    by_uri: list[Path] = []
    by_stem: list[Path] = []
    if entities_dir.is_dir():
        for page_path in sorted(entities_dir.glob("*.md")):
            try:
                meta = frontmatter.load(page_path).metadata
            except Exception:  # noqa: BLE001
                continue
            if meta.get("uri") == entity:
                by_uri.append(page_path)
            if page_path.stem == entity:
                by_stem.append(page_path)
    matches = by_uri or by_stem
    if not matches:
        raise ValueError(f"no entity page found for {entity!r}")
    if len(matches) > 1:
        raise ValueError(f"ambiguous entity {entity!r}: {[str(m) for m in matches]}")
    return matches[0]


def run_ack_drift(entity: str, workspace_path: Path | None = None) -> AckDriftResult:
    """Clear all `drift_review` flags for `entity`. Returns the page + count cleared."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    page_path = _resolve_entity_page(wiki, entity)
    entries = frontmatter.load(page_path).metadata.get("drift_review") or []
    cleared = len(entries)
    if cleared:
        update_frontmatter(page_path, delete=["drift_review"])
    return AckDriftResult(page_path=page_path, cleared=cleared)
