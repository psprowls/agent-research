"""Mechanical writer for synthesized guidance pages.

Takes already-synthesized page text (produced by an LLM in graph-wiki-core),
validates it, stamps the real date, and writes it to its resolved path. No LLM,
no prompt construction — purely the deterministic scaffolding around a page.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from guidance_io.frontmatter import emit, parse, validate
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
) -> WriteResult:
    """Validate, date-stamp, and write one guidance page.

    Returns WriteResult: on success `written_rel` is the workspace-relative
    POSIX path and `skip_reason` is None; on parse/validation failure
    `written_rel` is None and `skip_reason` explains the skip (nothing written).
    """
    text = page_text.lstrip()
    try:
        fm, body = parse(text)
    except ValueError as exc:
        return WriteResult(None, f"frontmatter parse failed: {exc}")

    errors = validate(fm)
    if errors:
        return WriteResult(None, "; ".join(errors))

    fm["updated"] = stamp  # never trust a model-supplied date
    page_text = f"{emit(fm)}\n{body}"

    topic = slugify(str(topic_raw))
    slug = slugify(str(slug_raw))
    page = page_path(workspace_root, topic, slug)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(page_text, encoding="utf-8")

    return WriteResult(page.relative_to(workspace_root).as_posix(), None)
