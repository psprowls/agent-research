"""Controlled vocabulary for guidance pages.

Topics are the folder names under wiki/guidance/ (one folder = one topic; a
new topic is a deliberate human act of making a folder). Tags are a committed
allowlist in wiki/guidance/tags.yaml, with optional `alias -> canonical`
remapping. The vocab_hash fingerprints the closed set the classifier chose
from; when it changes, the file index is fully rebuilt.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from guidance_io.frontmatter import parse
from guidance_io.paths import guidance_dir, list_all_pages, slugify, tags_yaml_path


@dataclass(frozen=True)
class Vocab:
    topics: frozenset[str]
    tags: frozenset[str]
    aliases: dict[str, str]
    vocab_hash: str


def _compute_vocab_hash(topics: frozenset[str], tags: frozenset[str]) -> str:
    payload = "\n".join(sorted(topics)) + "\x00" + "\n".join(sorted(tags))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _load_tags_yaml(workspace: Path) -> tuple[frozenset[str], dict[str, str]]:
    path = tags_yaml_path(workspace)
    if not path.is_file():
        return frozenset(), {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return frozenset(), {}
    if isinstance(raw, list):
        return frozenset(slugify(str(t)) for t in raw), {}
    if isinstance(raw, dict):
        tags = frozenset(slugify(str(t)) for t in (raw.get("tags") or []))
        aliases = {slugify(str(k)): slugify(str(v)) for k, v in (raw.get("aliases") or {}).items()}
        return tags, aliases
    return frozenset(), {}


def load_vocab(workspace: Path) -> Vocab:
    """Resolve the controlled vocabulary for a workspace."""
    root = guidance_dir(workspace)
    topics = frozenset(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else frozenset()
    tags, aliases = _load_tags_yaml(workspace)
    return Vocab(topics, tags, aliases, _compute_vocab_hash(topics, tags))


def canonical_tag(raw: str, vocab: Vocab) -> str | None:
    """Normalize a raw tag to its canonical allowlist form, or None if off-vocab."""
    norm = slugify(str(raw))
    norm = vocab.aliases.get(norm, norm)
    return norm if norm in vocab.tags else None


def seed_tags(workspace: Path) -> list[str]:
    """Sorted, kebab-normalized union of every page's `tags` (bootstrap allowlist)."""
    found: set[str] = set()
    for page in list_all_pages(workspace):
        try:
            fm, _ = parse(page.read_text(encoding="utf-8", errors="replace"))
        except ValueError:
            continue
        for tag in fm.get("tags") or []:
            found.add(slugify(str(tag)))
    return sorted(found)


def write_tags_yaml(workspace: Path, tags: list[str]) -> Path:
    """Write the {tags: [...]} allowlist file; return its path."""
    path = tags_yaml_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"tags": list(tags)}, sort_keys=False), encoding="utf-8")
    return path
