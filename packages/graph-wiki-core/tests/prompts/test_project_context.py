"""Unit tests for prompts/project_context.py::render_project_context.

Covers the four LOCKED behavioral cases from 10-CONTEXT.md §Project-context renderer:
  1. Missing file → empty string (never None, never crash).
  2. CLAUDE.md present with style + log → rendered, snapshot-stable.
  3. CLAUDE.md absent but AGENTS.md present → AGENTS.md is used.
  4. Two consecutive calls return byte-identical output (determinism invariant).

Each test imports the module lazily inside the test body so collection succeeds
even before the implementation lands (test_prompt_snapshots.py pattern).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

# Module-level fixture: a minimal but realistic CLAUDE.md / AGENTS.md body.
# Contains:
#   - A ## Style section.
#   - A ## Log format section with the canonical fenced code block.
FIXTURE_CLAUDE_MD = """\
# Project schema

Some preamble text the renderer should ignore.

## Style

- Be concise.
- Cite aggressively.
- Prefer wikilinks over prose where possible.

## Log format

```
## [YYYY-MM-DD] <op> | <title>
```

Valid ops: scan, ingest, query, lint, create, update, delete, note.
"""


def test_render_project_context_missing_file(tmp_path: Path) -> None:
    """When neither CLAUDE.md nor AGENTS.md exists, return ''.

    Covers both: (a) wiki_path exists but is empty, and (b) wiki_path is a
    nonexistent subdirectory. Both must return the empty string — never None,
    never raise.
    """
    try:
        from graph_wiki_core.prompts.project_context import render_project_context
    except ImportError:
        pytest.skip("project_context module not yet implemented")

    # Case (a): empty existing directory.
    assert render_project_context(tmp_path) == ""

    # Case (b): nonexistent subdirectory.
    assert render_project_context(tmp_path / "does-not-exist") == ""


def test_render_project_context_with_claude_md(
    tmp_path: Path, snapshot: SnapshotAssertion
) -> None:
    """CLAUDE.md present → rendered block contains style/log."""
    try:
        from graph_wiki_core.prompts.project_context import render_project_context
    except ImportError:
        pytest.skip("project_context module not yet implemented")

    (tmp_path / "CLAUDE.md").write_text(FIXTURE_CLAUDE_MD, encoding="utf-8")

    rendered = render_project_context(tmp_path)

    assert rendered, "rendered block must be non-empty when CLAUDE.md exists"
    # Style section was extracted.
    assert "Style" in rendered or "style" in rendered
    # Log format section was extracted.
    assert "Log format" in rendered or "log format" in rendered
    # Snapshot stability.
    assert rendered == snapshot


def test_render_project_context_agents_md_fallback(tmp_path: Path) -> None:
    """No CLAUDE.md but AGENTS.md present → AGENTS.md is read instead."""
    try:
        from graph_wiki_core.prompts.project_context import render_project_context
    except ImportError:
        pytest.skip("project_context module not yet implemented")

    (tmp_path / "AGENTS.md").write_text(FIXTURE_CLAUDE_MD, encoding="utf-8")

    rendered = render_project_context(tmp_path)

    assert rendered, "rendered block must be non-empty when AGENTS.md exists"
    assert "Style" in rendered or "style" in rendered
    assert "Log format" in rendered or "log format" in rendered
    # The rendered output should reference AGENTS.md as the source filename.
    assert "AGENTS.md" in rendered


def test_render_project_context_deterministic(tmp_path: Path) -> None:
    """Two calls on the same fixture return byte-identical strings."""
    try:
        from graph_wiki_core.prompts.project_context import render_project_context
    except ImportError:
        pytest.skip("project_context module not yet implemented")

    (tmp_path / "CLAUDE.md").write_text(FIXTURE_CLAUDE_MD, encoding="utf-8")

    first = render_project_context(tmp_path)
    second = render_project_context(tmp_path)

    assert first == second
    assert len(first) > 0
