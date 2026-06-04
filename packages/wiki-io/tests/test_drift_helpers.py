"""Living Wiki M2e: unit tests for the structured frontmatter setter and the
pure drift helpers (wiki_io.drift)."""

from __future__ import annotations

import frontmatter as _fm
import pytest
from wiki_io.entity_writer import update_frontmatter


def _write(tmp_path, fm: str, body: str = "# T\n\n## Purpose\nx\n"):
    p = tmp_path / "page.md"
    p.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")
    return p


def test_update_frontmatter_sets_structured_value(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\n")
    update_frontmatter(
        page,
        {
            "drift_checked_commit": "abc123",
            "drift_review": [
                {"section": "Purpose", "detected_commit": "abc123",
                 "hash": "9f2c", "reason": "stale"}
            ],
        },
    )
    meta = _fm.load(page).metadata
    assert meta["drift_checked_commit"] == "abc123"
    assert meta["drift_review"] == [
        {"section": "Purpose", "detected_commit": "abc123",
         "hash": "9f2c", "reason": "stale"}
    ]


def test_update_frontmatter_deletes_key(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\ndrift_review:\n- {section: Purpose}\n")
    update_frontmatter(page, {"drift_checked_commit": "x"}, delete=["drift_review"])
    meta = _fm.load(page).metadata
    assert "drift_review" not in meta
    assert meta["drift_checked_commit"] == "x"


def test_update_frontmatter_preserves_body_and_other_keys(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\nsummary: keep me\n")
    update_frontmatter(page, {"drift_checked_commit": "x"})
    post = _fm.load(page)
    assert post.metadata["summary"] == "keep me"
    assert post.metadata["uri"] == "pkg:a"
    assert "## Purpose" in post.content


def test_update_frontmatter_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        update_frontmatter(tmp_path / "nope.md", {"x": "y"})


# ---------------------------------------------------------------------------
# Task 2: pure drift helpers (wiki_io.drift)
# ---------------------------------------------------------------------------

from wiki_io.drift import (
    clear_resolved_flags,
    extract_file_map,
    iter_human_sections,
    section_hash,
)

_BODY = (
    "# pkg:a\n\n"
    "## Narrative\nThe package does async fan-out.\n\n"
    "## Purpose\nProcesses items synchronously.\n\n"
    "## Public API\n`run()`\n\n"
    "## File map - a\n\n| Path | Kind | Description |\n|---|---|---|\n"
    "| `x.py` | file | core |\n\n"
    "## Referenced in wiki\n- [[entities/foo]]\n"
)


def test_iter_human_sections_excludes_scanner_sections():
    secs = iter_human_sections(_BODY)
    headings = [h for h, _ in secs]
    assert headings == ["## Purpose", "## Public API"]
    # chunk includes the heading line
    assert secs[0][1].startswith("## Purpose")
    assert "synchronously" in secs[0][1]


def test_section_hash_is_stable_and_edit_sensitive():
    chunk = "## Purpose\nProcesses items synchronously.\n"
    assert section_hash(chunk) == section_hash(chunk + "\n\n")  # trailing ws ignored
    assert section_hash(chunk) != section_hash("## Purpose\nProcesses items async.\n")


def test_extract_file_map_returns_section_or_none():
    assert "| `x.py` |" in extract_file_map(_BODY)
    no_fm = "# t\n\n## Narrative\nn\n\n## Purpose\np\n"
    assert extract_file_map(no_fm) is None


def test_clear_resolved_flags_drops_edited_and_missing():
    purpose_chunk = "## Purpose\nProcesses items synchronously.\n\n"
    entries = [
        {"section": "Purpose", "detected_commit": "c1",
         "hash": section_hash(purpose_chunk), "reason": "r1"},
        {"section": "Public API", "detected_commit": "c1",
         "hash": "STALEHASH", "reason": "r2"},      # hash mismatch -> edited -> drop
        {"section": "Gone", "detected_commit": "c1",
         "hash": "whatever", "reason": "r3"},        # section absent -> drop
    ]
    survivors = clear_resolved_flags(entries, _BODY)
    assert [e["section"] for e in survivors] == ["Purpose"]


def test_clear_resolved_flags_keeps_all_when_unchanged():
    entries = [
        {"section": h.removeprefix("## "), "detected_commit": "c1",
         "hash": section_hash(chunk), "reason": "r"}
        for h, chunk in iter_human_sections(_BODY)
    ]
    assert clear_resolved_flags(entries, _BODY) == entries


def test_drift_keys_are_not_scanner_owned():
    """Guards §5.7: drift_checked_commit / drift_review must be PRESERVED across
    re-scan, so they must never be added to SCANNER_OWNED_KEYS (which merge wipes
    to template values)."""
    from wiki_io.entity_writer import SCANNER_OWNED_KEYS

    assert "drift_checked_commit" not in SCANNER_OWNED_KEYS
    assert "drift_review" not in SCANNER_OWNED_KEYS


def test_merge_frontmatter_preserves_drift_keys():
    """A scanner re-render keeps unknown preserved keys (like last_updated_commit,
    drift_checked_commit, drift_review)."""
    from wiki_io.entity_writer import merge_frontmatter

    existing = {
        "uri": "pkg:a", "kind": "package",
        "drift_checked_commit": "abc",
        "drift_review": [{"section": "Purpose", "hash": "h", "detected_commit": "abc", "reason": "r"}],
    }
    scanner = {"uri": "pkg:a", "kind": "package"}
    merged = merge_frontmatter(existing, scanner)
    assert merged["drift_checked_commit"] == "abc"
    assert merged["drift_review"] == existing["drift_review"]
