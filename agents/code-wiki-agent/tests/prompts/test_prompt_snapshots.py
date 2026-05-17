from __future__ import annotations

"""Snapshot tests for every *_SYSTEM prompt constant exported from code_wiki_agent.prompts.

Each test imports its target lazily (inside the function body) so the file
collects cleanly even when the prompts module has not landed yet. A
pytest.skip() on ImportError converts a missing module into a clean skip,
not a collection error.

Once the prompts module is implemented (06-04..06-07), these tests serve as
the snapshot gate: running `pytest --snapshot-update` records baseline
snapshots, and subsequent runs assert byte equality.

Plan 10-07 extension: project-context-aware snapshot tests covering the
with-project-context path for each builder (scanner, ingestor, three linter
groups) plus a missing-CLAUDE.md degradation test that enforces the
"empty string + non-empty prompt" contract (CTX-04 LOCKED).
"""

from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion


# Module-level fixture: a minimal but realistic CLAUDE.md body.
# Mirrors FIXTURE_CLAUDE_MD in test_project_context.py — duplication is
# acceptable per CONTEXT.md §Claude's Discretion (keep each test module
# self-contained so snapshot drift is isolated).
FIXTURE_CLAUDE_MD_FOR_SNAPSHOTS = """\
# Project schema

Some preamble text the renderer should ignore.

<!-- lattice-wiki:layout:start -->
```yaml
version: 1
detected_at: 2026-04-29
repo_root: ..
containers:
  - source: apps
    vault_dir: apps
    classification: app
    children_count: 1
  - source: cores
    vault_dir: cores
    classification: package
    children_count: 4
```
<!-- lattice-wiki:layout:end -->

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


def _render_ctx_from_tmp(tmp_path: Path) -> str:
    """Materialize a wiki dir with FIXTURE_CLAUDE_MD_FOR_SNAPSHOTS and render it.

    Keeps the per-test setup short so each with-context test stays a one-liner.
    """
    from code_wiki_agent.prompts.project_context import render_project_context

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(FIXTURE_CLAUDE_MD_FOR_SNAPSHOTS, encoding="utf-8")
    return render_project_context(wiki)


def test_librarian_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """LIBRARIAN_SYSTEM matches recorded snapshot."""
    try:
        from code_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert LIBRARIAN_SYSTEM == snapshot


def test_ingestor_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """INGESTOR_SYSTEM matches recorded snapshot."""
    try:
        from code_wiki_agent.prompts.ingestor import INGESTOR_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert INGESTOR_SYSTEM == snapshot


def test_linter_page_quality_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """LINTER_PAGE_QUALITY_SYSTEM matches recorded snapshot."""
    try:
        from code_wiki_agent.prompts.linter import LINTER_PAGE_QUALITY_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert LINTER_PAGE_QUALITY_SYSTEM == snapshot


def test_linter_adr_chain_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """LINTER_ADR_CHAIN_SYSTEM matches recorded snapshot."""
    try:
        from code_wiki_agent.prompts.linter import LINTER_ADR_CHAIN_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert LINTER_ADR_CHAIN_SYSTEM == snapshot


def test_linter_stale_claims_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """LINTER_STALE_CLAIMS_SYSTEM matches recorded snapshot."""
    try:
        from code_wiki_agent.prompts.linter import LINTER_STALE_CLAIMS_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert LINTER_STALE_CLAIMS_SYSTEM == snapshot


def test_scanner_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """SCANNER_SYSTEM matches recorded snapshot."""
    try:
        from code_wiki_agent.prompts.scanner import SCANNER_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert SCANNER_SYSTEM == snapshot


def test_synthesizer_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """SYNTHESIZER_SYSTEM matches recorded snapshot."""
    try:
        from code_wiki_agent.prompts.synthesizer import SYNTHESIZER_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert SYNTHESIZER_SYSTEM == snapshot


def test_code_reader_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """CODE_READER_SYSTEM matches recorded snapshot."""
    try:
        from code_wiki_agent.prompts.code_reader import CODE_READER_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert CODE_READER_SYSTEM == snapshot


# ---------------------------------------------------------------------------
# Plan 10-07: with-project-context snapshots (CTX-04 §Snapshot coverage)
#
# These guard the wiring contract: a future refactor that strips the
# project_context kwarg or fails to insert the block would be caught here.
# ---------------------------------------------------------------------------


def test_scanner_system_with_project_context(
    snapshot: SnapshotAssertion, tmp_path: Path
) -> None:
    """build_scanner_system with rendered project-context matches snapshot."""
    try:
        from code_wiki_agent.prompts.scanner import build_scanner_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert build_scanner_system(project_context=_render_ctx_from_tmp(tmp_path)) == snapshot


def test_ingestor_system_with_project_context(
    snapshot: SnapshotAssertion, tmp_path: Path
) -> None:
    """build_ingestor_system with rendered project-context matches snapshot."""
    try:
        from code_wiki_agent.prompts.ingestor import build_ingestor_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert build_ingestor_system(project_context=_render_ctx_from_tmp(tmp_path)) == snapshot


def test_linter_page_quality_system_with_project_context(
    snapshot: SnapshotAssertion, tmp_path: Path
) -> None:
    """build_linter_page_quality_system with project-context matches snapshot."""
    try:
        from code_wiki_agent.prompts.linter import build_linter_page_quality_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert (
        build_linter_page_quality_system(project_context=_render_ctx_from_tmp(tmp_path))
        == snapshot
    )


def test_linter_adr_chain_system_with_project_context(
    snapshot: SnapshotAssertion, tmp_path: Path
) -> None:
    """build_linter_adr_chain_system with project-context matches snapshot."""
    try:
        from code_wiki_agent.prompts.linter import build_linter_adr_chain_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert (
        build_linter_adr_chain_system(project_context=_render_ctx_from_tmp(tmp_path))
        == snapshot
    )


def test_linter_stale_claims_system_with_project_context(
    snapshot: SnapshotAssertion, tmp_path: Path
) -> None:
    """build_linter_stale_claims_system with project-context matches snapshot."""
    try:
        from code_wiki_agent.prompts.linter import build_linter_stale_claims_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert (
        build_linter_stale_claims_system(project_context=_render_ctx_from_tmp(tmp_path))
        == snapshot
    )


def test_all_builders_degrade_without_project_context(tmp_path: Path) -> None:
    """Missing-CLAUDE.md degradation contract (CTX-04 LOCKED).

    On a vault with no CLAUDE.md / AGENTS.md, render_project_context must
    return the empty string. Every builder must still produce a non-empty
    prompt when called with `project_context=""`. The combination guarantees
    the project-context wiring is purely additive — a vault lacking the
    schema file still gets a working role-shaped prompt.
    """
    try:
        from code_wiki_agent.prompts.ingestor import build_ingestor_system
        from code_wiki_agent.prompts.librarian import build_librarian_system
        from code_wiki_agent.prompts.linter import (
            build_linter_adr_chain_system,
            build_linter_page_quality_system,
            build_linter_stale_claims_system,
        )
        from code_wiki_agent.prompts.project_context import render_project_context
        from code_wiki_agent.prompts.scanner import build_scanner_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")

    # Empty-string contract: no schema file → "".
    rendered = render_project_context(tmp_path / "nonexistent")
    assert rendered == "", "render_project_context must return '' when no schema file exists"

    # Each builder still emits a non-empty prompt on the empty-context path.
    assert build_scanner_system(project_context="").strip(), "scanner empty prompt"
    assert build_ingestor_system(project_context="").strip(), "ingestor empty prompt"
    assert build_linter_page_quality_system(project_context="").strip(), "linter PQ empty"
    assert build_linter_adr_chain_system(project_context="").strip(), "linter ADR empty"
    assert build_linter_stale_claims_system(project_context="").strip(), "linter SC empty"
    # Librarian has no project_context kwarg (CONTEXT.md §Wiring).
    assert build_librarian_system().strip(), "librarian empty prompt"
