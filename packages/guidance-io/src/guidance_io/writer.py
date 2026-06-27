"""Mechanical writer for synthesized guidance pages.

Takes already-synthesized page text (produced by an LLM in graph-wiki-core),
validates it, stamps the real date, and writes it to its resolved path. No LLM,
no prompt construction — purely the deterministic scaffolding around a page.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from guidance_io.frontmatter import emit, normalize_language, parse, validate
from guidance_io.paths import page_path, slugify


@dataclass
class WriteResult:
    written_rel: str | None
    skip_reason: str | None


def write_page(
    workspace_root: Path,
    *,
    topic_raw: str,
    slug_raw: str,
    page_text: str,
    stamp: str,
    language: str | None = None,
) -> WriteResult:
    """Validate, date-stamp, and write one guidance page.

    Returns WriteResult: on success `written_rel` is the workspace-relative
    POSIX path and `skip_reason` is None; on parse/validation failure
    `written_rel` is None and `skip_reason` explains the skip (nothing written).

    The caller's language intent is authoritative in both directions. When
    ``language`` is provided it is normalized (lowercase+trim), stamped into the
    frontmatter, and appended as a ``-<language>`` suffix to the slug. When
    ``language=None`` the call is agnostic and authoritative: any ``language``
    already in the page text is dropped, so the page is always written agnostic
    (no stamp, no suffix). This prevents a stray LLM-supplied language from
    silently turning an intended-agnostic page into a language-specific one.
    """
    text = page_text.strip()
    try:
        fm, body = parse(text)
    except ValueError as exc:
        return WriteResult(None, f"frontmatter parse failed: {exc}")

    # Caller's language intent is authoritative in both directions.
    if language is not None:
        fm["language"] = language
        normalize_language(fm)
        suffix_language = fm.get("language")  # normalized, or None if caller value was empty/whitespace
    else:
        fm.pop("language", None)  # agnostic call is authoritative: never leave a stray language
        suffix_language = None

    errors = validate(fm)
    if errors:
        return WriteResult(None, "; ".join(errors))

    fm["updated"] = stamp  # never trust a model-supplied date
    page_text = f"{emit(fm)}\n{body}"

    topic = slugify(str(topic_raw))
    base_slug = slugify(str(slug_raw))
    # suffix_language is already lowercase+trimmed; exotic names (c++, c#) are
    # preserved verbatim rather than slugified away
    slug = f"{base_slug}-{suffix_language}" if suffix_language else base_slug
    page = page_path(workspace_root, topic, slug)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(page_text, encoding="utf-8")

    return WriteResult(page.relative_to(workspace_root).as_posix(), None)
