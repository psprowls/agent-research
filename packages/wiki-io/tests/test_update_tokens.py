"""Tests for wiki_io.update_tokens — the `tokens` frontmatter stamper.

update_page/update_vault take a `count_tokens: Callable[[str], int]` (dependency
injection — Move 4 of the wiki-io/graph-io decoupling) instead of importing
graph_io.tokens directly. Real callers (gw scan, gw util tokens) pass
graph_io.tokens.count_tokens; these tests use a deterministic local fake so
wiki-io's own test suite never imports graph_io here.
"""

from __future__ import annotations

from pathlib import Path


def _fake_count_tokens(text: str) -> int:
    return len(text)


def _seed_page(path: Path, tokens_value: str | int | None = 5) -> None:
    """Write a minimal page with the given tokens frontmatter value.

    `tokens_value` may be an int (becomes `tokens: <int>`), the string "null"
    (becomes `tokens: null`), or None (omits the tokens line entirely).
    """
    fm_lines = [
        "---",
        "title: Test",
        "category: concept",
        "summary: t",
    ]
    if tokens_value == "null":
        fm_lines.append("tokens: null")
    elif tokens_value is not None:
        fm_lines.append(f"tokens: {tokens_value}")
    fm_lines.append("---")
    path.write_text("\n".join(fm_lines) + "\n\nBody.\n", encoding="utf-8")


def test_update_page_stamps_positive_int(tmp_path: Path) -> None:
    """A page is stamped with a real positive int count from the injected counter."""
    import frontmatter
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)

    status, count = update_page(page, _fake_count_tokens, dry_run=False)

    assert status == "updated"
    assert isinstance(count, int) and count > 0
    meta = frontmatter.load(str(page)).metadata
    assert meta["tokens"] == count
    assert "tokens: null" not in page.read_text(encoding="utf-8")


def test_update_page_idempotent_on_rerun(tmp_path: Path) -> None:
    """Re-running on an already-stamped page reports 'unchanged' and leaves the
    bytes identical (deterministic count)."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)

    update_page(page, _fake_count_tokens, dry_run=False)
    stamped = page.read_text(encoding="utf-8")

    status, _ = update_page(page, _fake_count_tokens, dry_run=False)

    assert status == "unchanged"
    assert page.read_text(encoding="utf-8") == stamped


def test_tokens_null_remigrated_to_int(tmp_path: Path) -> None:
    """A page left at the old `tokens: null` sentinel is re-stamped with a real
    integer count — the null path is gone."""
    import frontmatter
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value="null")

    status, count = update_page(page, _fake_count_tokens, dry_run=False)

    assert status == "updated"
    assert isinstance(count, int) and count > 0
    assert frontmatter.load(str(page)).metadata["tokens"] == count


def test_update_page_uses_injected_counter(tmp_path: Path) -> None:
    """update_page stamps whatever the injected count_tokens returns — proving
    it routes through the caller-supplied counter, not a hardcoded one."""
    import frontmatter
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)

    status, count = update_page(page, lambda text: 4242, dry_run=False)

    assert status == "updated"
    assert count == 4242
    assert frontmatter.load(str(page)).metadata["tokens"] == 4242


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    """--dry-run counts but leaves the page bytes untouched."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)
    original = page.read_text(encoding="utf-8")

    status, count = update_page(page, _fake_count_tokens, dry_run=True)

    assert status == "updated"
    assert isinstance(count, int) and count > 0
    assert page.read_text(encoding="utf-8") == original


def test_file_without_frontmatter_skipped(tmp_path: Path) -> None:
    """A file with no leading `---` is skipped and never mutated."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "plain.md"
    page.write_text("No frontmatter here.\n", encoding="utf-8")
    original = page.read_text(encoding="utf-8")

    status, count = update_page(page, _fake_count_tokens, dry_run=False)

    assert status == "skipped"
    assert count == 0
    assert page.read_text(encoding="utf-8") == original


def test_truncated_frontmatter_skipped(tmp_path: Path) -> None:
    """Frontmatter with no closing fence is skipped (not mutated)."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "truncated.md"
    page.write_text("---\ntitle: T\nno closing fence\n", encoding="utf-8")
    original = page.read_text(encoding="utf-8")

    status, count = update_page(page, _fake_count_tokens, dry_run=False)

    assert status == "skipped"
    assert count == 0
    assert page.read_text(encoding="utf-8") == original
