"""Tests for wiki_io.update_tokens — offline token counting via tiktoken.

Token counts come from graph_io.tokens.count_tokens (tiktoken o200k_base), so
counting is local, deterministic, and needs no Bedrock/network call. There is no
"unsupported model" / `tokens: null` path anymore.
"""

from __future__ import annotations

from pathlib import Path


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


def test_count_tokens_is_graph_io_offline_counter() -> None:
    """update_tokens reuses graph_io's offline tiktoken counter rather than its
    own Bedrock call — same encoder the code-graph nodes are counted with."""
    from graph_io.tokens import count_tokens as graph_count
    from wiki_io.update_tokens import count_tokens

    assert count_tokens is graph_count


def test_update_page_stamps_positive_int_offline(tmp_path: Path) -> None:
    """A page is stamped with a real positive int count with no network call
    (no boto3/Bedrock mocking needed — counting is local)."""
    import frontmatter
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)

    status, count = update_page(page, dry_run=False)

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

    update_page(page, dry_run=False)
    stamped = page.read_text(encoding="utf-8")

    status, _ = update_page(page, dry_run=False)

    assert status == "unchanged"
    assert page.read_text(encoding="utf-8") == stamped


def test_tokens_null_remigrated_to_int(tmp_path: Path) -> None:
    """A page left at the old `tokens: null` sentinel is re-stamped with a real
    integer count — the null path is gone."""
    import frontmatter
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value="null")

    status, count = update_page(page, dry_run=False)

    assert status == "updated"
    assert isinstance(count, int) and count > 0
    assert frontmatter.load(str(page)).metadata["tokens"] == count


def test_update_page_delegates_to_module_count_tokens(tmp_path: Path, monkeypatch) -> None:
    """update_page stamps whatever the module-level count_tokens returns — proving
    it routes through the (now offline) counter, not a hardcoded path."""
    import frontmatter
    from wiki_io import update_tokens

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)
    monkeypatch.setattr(update_tokens, "count_tokens", lambda text: 4242)

    status, count = update_tokens.update_page(page, dry_run=False)

    assert status == "updated"
    assert count == 4242
    assert frontmatter.load(str(page)).metadata["tokens"] == 4242


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    """--dry-run counts but leaves the page bytes untouched."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)
    original = page.read_text(encoding="utf-8")

    status, count = update_page(page, dry_run=True)

    assert status == "updated"
    assert isinstance(count, int) and count > 0
    assert page.read_text(encoding="utf-8") == original


def test_file_without_frontmatter_skipped(tmp_path: Path) -> None:
    """A file with no leading `---` is skipped and never mutated."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "plain.md"
    page.write_text("No frontmatter here.\n", encoding="utf-8")
    original = page.read_text(encoding="utf-8")

    status, count = update_page(page, dry_run=False)

    assert status == "skipped"
    assert count == 0
    assert page.read_text(encoding="utf-8") == original


def test_truncated_frontmatter_skipped(tmp_path: Path) -> None:
    """Frontmatter with no closing fence is skipped (not mutated)."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "truncated.md"
    page.write_text("---\ntitle: T\nno closing fence\n", encoding="utf-8")
    original = page.read_text(encoding="utf-8")

    status, count = update_page(page, dry_run=False)

    assert status == "skipped"
    assert count == 0
    assert page.read_text(encoding="utf-8") == original
