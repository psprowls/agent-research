"""Workflow-hints check: workflow_hints entries pointing to missing sub-pages."""

from __future__ import annotations

from pathlib import Path

from vault_io.lint.common import FRONTMATTER_RE as _FRONTMATTER_RE
from vault_io.lint.common import parse_inline_list

GROUP = "workflow_hints"


def _parse_workflow_hints(text: str) -> dict[str, list[str]]:
    """Extract workflow_hints mapping from YAML frontmatter without pyyaml.

    Handles the multi-line block form:
        workflow_hints:
          brainstorming: [context.md]
          planning:      [api.md, patterns.md]
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    hints: dict[str, list[str]] = {}
    in_hints = False
    for line in m.group(1).splitlines():
        if line.rstrip() == "workflow_hints:":
            in_hints = True
            continue
        if in_hints:
            if line.startswith(" ") or line.startswith("\t"):
                stripped = line.strip()
                colon = stripped.find(":")
                if colon == -1:
                    continue
                phase = stripped[:colon].strip()
                rest = stripped[colon + 1:].strip()
                items = parse_inline_list(rest)
                if items:
                    hints[phase] = items
            else:
                in_hints = False
    return hints


def check(pages: dict, vault: Path) -> list[str]:
    """Flag workflow_hints entries pointing to sub-pages that do not exist on disk."""
    issues: list[str] = []
    for key, page in pages.items():
        hints = _parse_workflow_hints(page.get("text") or "")
        for phase, sub_pages in hints.items():
            for sp in sub_pages:
                sub_path = vault / Path(key).parent / sp
                if not sub_path.exists():
                    issues.append(
                        f"{key}: workflow_hints.{phase} references missing sub-page '{sp}'"
                    )
    return issues
