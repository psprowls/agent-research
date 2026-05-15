from __future__ import annotations

"""Snapshot tests for every *_SYSTEM prompt constant exported from code_wiki_agent.prompts.

Each test imports its target lazily (inside the function body) so the file
collects cleanly even when the prompts module has not landed yet. A
pytest.skip() on ImportError converts a missing module into a clean skip,
not a collection error.

Once the prompts module is implemented (06-04..06-07), these tests serve as
the snapshot gate: running `pytest --snapshot-update` records baseline
snapshots, and subsequent runs assert byte equality.
"""

import pytest
from syrupy.assertion import SnapshotAssertion


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
