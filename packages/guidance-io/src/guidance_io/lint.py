"""Mechanical lint rules for guidance pages.

Wraps guidance_io.frontmatter.validate over every page under wiki/guidance/,
plus an on-disk placement coherence check. No LLM, no network — the LLM-driven
guidance synthesis lives in graph-wiki-core.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from guidance_io.frontmatter import parse, validate
from guidance_io.paths import guidance_dir, list_all_pages, slugify


@dataclass
class LintFinding:
    rule_id: str
    severity: Literal["error", "warn", "info"]
    slug: str
    message: str


def run_lint(workspace: Path) -> list[LintFinding]:
    """Lint every guidance page; return findings (empty == clean)."""
    findings: list[LintFinding] = []
    root = guidance_dir(workspace)

    for page in list_all_pages(workspace):
        rel = page.relative_to(root)
        slug = f"{rel.parent.as_posix()}/{page.stem}"
        topic_dir = rel.parts[0]

        text = page.read_text(encoding="utf-8", errors="replace")
        try:
            fm, _body = parse(text)
        except ValueError as exc:
            findings.append(LintFinding("guidance-parse-error", "error", slug, f"frontmatter parse failed: {exc}"))
            continue

        for msg in validate(fm):
            findings.append(LintFinding("guidance-invalid-frontmatter", "error", slug, msg))

        topic = fm.get("topic")
        if isinstance(topic, str) and topic.strip() and slugify(topic) != topic_dir:
            findings.append(
                LintFinding(
                    "guidance-topic-placement",
                    "warn",
                    slug,
                    f"topic {topic!r} slugifies to {slugify(topic)!r} but page is filed under {topic_dir!r}",
                )
            )

    return findings
