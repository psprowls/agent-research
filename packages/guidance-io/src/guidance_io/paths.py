"""Pure path accessors for guidance pages: wiki/guidance/<topic>/<slug>.md.

Callers obtain the workspace from `workspace_io.config.resolve()` and pass
`.workspace` here. These functions do no business logic — they compose paths
and, for `list_pages`, glob a single directory.
"""

from __future__ import annotations

import re
from pathlib import Path

from workspace_io.paths import graph_dir, wiki_dir

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def guidance_dir(workspace: Path) -> Path:
    """The wiki/guidance/ root holding per-topic subfolders."""
    return wiki_dir(workspace) / "guidance"


def slugify(title: str) -> str:
    """Lowercase a title and collapse non-alphanumeric runs to '-'.

    Edge dashes are trimmed; an otherwise-empty result becomes 'untitled'.
    """
    s = _SLUG_RE.sub("-", title.lower()).strip("-")
    return s or "untitled"


def page_path(workspace: Path, topic: str, slug: str) -> Path:
    """Resolve wiki/guidance/<topic>/<slug>.md (no I/O)."""
    return guidance_dir(workspace) / topic / f"{slug}.md"


def list_pages(workspace: Path, topic: str) -> list[Path]:
    """Sorted .md pages under a topic folder (excluding the generated index.md);
    empty list if the folder is absent."""
    topic_dir = guidance_dir(workspace) / topic
    if not topic_dir.is_dir():
        return []
    return sorted(p for p in topic_dir.glob("*.md") if p.name != "index.md")


def list_all_pages(workspace: Path) -> list[Path]:
    """Sorted .md pages across every topic folder under wiki/guidance/
    (excluding generated index.md files); empty list if guidance/ is absent."""
    root = guidance_dir(workspace)
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*/*.md") if p.name != "index.md")


def tags_yaml_path(workspace: Path) -> Path:
    """The committed tag allowlist at wiki/guidance/tags.yaml (no I/O)."""
    return guidance_dir(workspace) / "tags.yaml"


def guidance_index_path(workspace: Path) -> Path:
    """The sidecar file→vocab index at .graph-wiki/guidance-index.json (no I/O)."""
    return graph_dir(workspace) / "guidance-index.json"
