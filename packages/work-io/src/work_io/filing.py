"""Write primitive for filing a structured work item page into the vault.

Owns parse / validate / slug / path / write for work-item pages, delegating all
YAML to work_io.frontmatter (no bespoke serializer). The side-effects that
filing a work item triggers (sidecar regen, index.md, log.md) deliberately live
in graph-wiki-core — keeping work-io free of any ingest-work-item dependency.

Replaces the legacy slugify / parse_frontmatter / validate / emit_yaml /
file_work_item helpers from the old ingest module.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from workspace_io.paths import work_dir

from work_io import frontmatter

REQUIRED_FIELDS = ("title", "category", "kind", "status", "summary", "opened", "affects")
_ALLOWED_CATEGORY = "work"
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_WORDS_CLEAN = 4
_MAX_WORDS_HARD_CAP = 6


def slugify(title: str) -> str:
    """Lowercase, replace non-alphanumeric runs with '-', strip edges."""
    return _SLUG_RE.sub("-", title.lower()).strip("-") or "untitled"


def compose_slug(kind: str, words: str, *, epic_child: bool = False) -> tuple[str, list[str]]:
    """Compose a `<prefix>-<w1>-<w2>-...` slug from filer-supplied words.

    `prefix` is `kind`, or `epic-<kind>` when `epic_child` is True. `words` is
    slugified (reusing `slugify`, so the same `_SLUG_RE` rules apply) and split
    into tokens: 1-4 tokens pass through clean, 5-6 are kept with a warning,
    7+ are truncated to 6 with a warning. Empty/whitespace `words` degrades
    silently to a single `untitled` token (via `slugify`'s own empty-input
    fallback) — no warning, since there's nothing to warn about.

    Returns (slug, warnings).
    """
    prefix = f"epic-{kind}" if epic_child else kind
    tokens = slugify(words).split("-")
    warnings: list[str] = []
    if len(tokens) > _MAX_WORDS_HARD_CAP:
        warnings.append(
            f"--slug-words: {len(tokens)} words truncated to {_MAX_WORDS_HARD_CAP} "
            f"({'-'.join(tokens[:_MAX_WORDS_HARD_CAP])})"
        )
        tokens = tokens[:_MAX_WORDS_HARD_CAP]
    elif len(tokens) > _MAX_WORDS_CLEAN:
        warnings.append(f"--slug-words: {len(tokens)} words kept (recommended 1-4)")
    return f"{prefix}-{'-'.join(tokens)}", warnings


def parse_fields(yaml_text: str) -> dict:
    """Parse a fence-less work-item frontmatter blob to a dict (full YAML).

    Replaces ingest_work_item._parse_frontmatter (a hand-rolled scalar/list
    line parser). Uses yaml.safe_load, so it handles quoted reserved-indicator
    values (e.g. '["@psprowls"]'), typed scalars, and nested structures the old
    parser silently mangled. Raises ValueError on malformed YAML or a non-mapping
    top level.
    """
    try:
        fm = yaml.safe_load(yaml_text) if yaml_text.strip() else {}
    except yaml.YAMLError as e:
        raise ValueError(f"malformed frontmatter YAML: {e}") from e
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter must be a YAML mapping, got {type(fm).__name__}")
    return fm


def validate(fm: dict) -> list[str]:
    """Return human-readable schema issues; an empty list means valid.

    Replaces ingest_work_item._validate: every REQUIRED_FIELDS key must be
    present, and category (when present) must be 'work'.
    """
    issues: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in fm:
            issues.append(f"missing required field: {field}")
    if fm.get("category") not in (None, _ALLOWED_CATEGORY):
        issues.append(f"category must be 'work' (got {fm.get('category')!r})")
    return issues


def write_work_item(
    wiki: Path,
    fm: dict,
    body: str,
    *,
    slug: str | None = None,
    epic_child: bool = False,
    force: bool = False,
) -> dict:
    """Write a work-item page to <workspace>/wiki/work/<opened>-<slug>.md.

    Serializes frontmatter via work_io.frontmatter.emit (no bespoke YAML).
    Performs NO sidecar / index.md / log.md side-effects — those live in
    graph-wiki-core's _apply_work_item_side_effects.

    Args:
        wiki:  the wiki directory (<workspace>/wiki). work_dir(wiki.parent)
               yields <workspace>/wiki/work.
        fm:    frontmatter dict (must carry 'title' and 'opened'; validate first).
        body:  markdown body text.
        slug:  page slug. When omitted, composed via compose_slug() from
               fm['kind'] + the first 4 words of the slugified title
               (epic-<kind> prefix when epic_child is True — the caller
               resolves the parent's kind; this function no longer infers it
               from fm['parent']); falls back to the legacy slugify(title)
               when fm has no 'kind'.
        epic_child: whether the composed default slug gets the epic-<kind>
               prefix. Ignored when slug is given explicitly.
        force: overwrite an existing page when True; else raise FileExistsError.

    Returns:
        {"status": "ok", "page_path": <abs str>, "slug": str, "title": str}.

    Raises:
        FileExistsError: the page already exists and force is False.
    """
    title = str(fm["title"])
    opened = str(fm["opened"])
    if slug is None:
        kind = fm.get("kind")
        if kind:
            first_four = "-".join(slugify(title).split("-")[:4])
            slug, _warnings = compose_slug(str(kind), first_four, epic_child=epic_child)
        else:
            slug = slugify(title)

    work_root = work_dir(wiki.parent)
    work_root.mkdir(parents=True, exist_ok=True)
    page_path = work_root / f"{opened}-{slug}.md"
    if page_path.exists() and not force:
        raise FileExistsError(f"page already exists: {page_path}")

    body = body if body.endswith("\n") else body + "\n"
    content = frontmatter.emit(fm) + "\n\n" + body
    page_path.write_text(content, encoding="utf-8")

    return {"status": "ok", "page_path": str(page_path), "slug": page_path.stem, "title": title}
