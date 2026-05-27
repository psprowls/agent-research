"""Phase 45 D-07: unit tests for wiki_io.entity_writer.inject_narrative."""

from __future__ import annotations

import logging
from pathlib import Path

import frontmatter
import pytest

from wiki_io.entity_writer import inject_narrative


def _canonical_page(uri: str = "pkg:agent-research/foo") -> str:
    return (
        "---\n"
        f"uri: {uri}\n"
        "kind: package\n"
        "---\n"
        "\n"
        "## Overview\n"
        "\n"
        "body1\n"
        "\n"
        "## Narrative\n"
        "\n"
        "OLD\n"
        "\n"
        "## See also\n"
        "\n"
        "seealso\n"
    )


def test_inject_narrative_replaces_body(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_canonical_page(), encoding="utf-8")

    inject_narrative(p, "NEW")

    expected = (
        "---\n"
        "uri: pkg:agent-research/foo\n"
        "kind: package\n"
        "---\n"
        "\n"
        "## Overview\n"
        "\n"
        "body1\n"
        "\n"
        "## Narrative\n"
        "\n"
        "NEW\n"
        "\n"
        "## See also\n"
        "\n"
        "seealso\n"
    )
    assert p.read_text(encoding="utf-8") == expected


def test_inject_narrative_idempotent(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_canonical_page(), encoding="utf-8")

    inject_narrative(p, "NEW")
    after_first = p.read_bytes()
    inject_narrative(p, "NEW")
    after_second = p.read_bytes()

    assert after_first == after_second


def test_inject_narrative_atomic_no_tmp_remains(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_canonical_page(), encoding="utf-8")

    inject_narrative(p, "NEW")

    leftover_tmp = list(tmp_path.glob("*.tmp"))
    assert leftover_tmp == [], f"Stray temp files: {leftover_tmp}"


def test_inject_narrative_preserves_frontmatter(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_canonical_page(), encoding="utf-8")
    before = frontmatter.load(p).metadata

    inject_narrative(p, "NEW")
    after = frontmatter.load(p).metadata

    assert dict(after) == dict(before)


def test_inject_narrative_preserves_other_h2_sections(tmp_path: Path):
    page = (
        "---\nuri: pkg:x\nkind: package\n---\n"
        "\n## Overview\n\nover\n"
        "\n## Narrative\n\nOLD\n"
        "\n## See also\n\nsee\n"
        "\n## References\n\nrefs\n"
    )
    p = tmp_path / "page.md"
    p.write_text(page, encoding="utf-8")

    inject_narrative(p, "NEW")

    text = p.read_text(encoding="utf-8")
    assert "## Overview" in text
    assert "## Narrative" in text
    assert "## See also" in text
    assert "## References" in text
    # Non-narrative bodies are byte-stable.
    assert "over\n" in text
    assert "see\n" in text
    assert "refs\n" in text


def test_inject_narrative_last_h2_replaces_through_eof(tmp_path: Path):
    page = (
        "---\nuri: pkg:x\nkind: package\n---\n"
        "\n## Overview\n\nover\n"
        "\n## Narrative\n\nOLD\n"
    )
    p = tmp_path / "page.md"
    p.write_text(page, encoding="utf-8")

    inject_narrative(p, "NEW")

    text = p.read_text(encoding="utf-8")
    assert text.endswith("NEW\n\n"), f"Unexpected tail: {text!r}"


def test_inject_narrative_missing_heading_logs_warning_no_write(tmp_path: Path, caplog):
    page = (
        "---\nuri: pkg:x\nkind: package\n---\n"
        "\n## Overview\n\nover\n"
        "\n## See also\n\nsee\n"
    )
    p = tmp_path / "page.md"
    p.write_text(page, encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="wiki_io.entity_writer"):
        inject_narrative(p, "X")

    assert p.read_text(encoding="utf-8") == page  # untouched
    assert any(
        "Narrative" in record.getMessage() and record.levelno == logging.WARNING
        for record in caplog.records
    ), f"No WARNING about Narrative; saw: {[r.getMessage() for r in caplog.records]}"


def test_inject_narrative_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        inject_narrative(tmp_path / "nope.md", "X")


def test_inject_narrative_empty_prose(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_canonical_page(), encoding="utf-8")

    inject_narrative(p, "")

    text = p.read_text(encoding="utf-8")
    # Section structure preserved; body region is empty.
    assert "## Narrative" in text
    assert "## See also" in text
    # No exception, no leftover OLD content.
    assert "OLD" not in text


def test_inject_narrative_strips_prose_whitespace(tmp_path: Path):
    p = tmp_path / "page.md"
    p.write_text(_canonical_page(), encoding="utf-8")

    inject_narrative(p, "\n\n  hello\n\n")

    text = p.read_text(encoding="utf-8")
    # The body region between heading and next H2 contains the stripped prose
    # with exactly one blank line before and after.
    assert "\n\n  hello\n\n## See also" in text or "\n\nhello\n\n## See also" in text
