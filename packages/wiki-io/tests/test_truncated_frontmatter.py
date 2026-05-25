"""VAULT-05: truncated-frontmatter guard in update_tokens.update_page.

A page whose frontmatter is missing the closing `---` fence must:
  - return ("skipped", 0)
  - leave the file bytes unchanged
  - emit a warning to stderr containing 'no closing frontmatter fence'
"""

from __future__ import annotations

from pathlib import Path


def test_update_page_skips_truncated_frontmatter(tmp_path: Path):
    from wiki_io.update_tokens import update_page

    page = tmp_path / "truncated.md"
    page.write_text(
        "---\ntitle: No closing fence\ncategory: concept\n",
        encoding="utf-8",
    )
    before = page.read_text(encoding="utf-8")

    status, count = update_page(page, dry_run=False)

    assert status == "skipped"
    assert count == 0
    assert page.read_text(encoding="utf-8") == before


def test_truncated_frontmatter_emits_stderr_warning(tmp_path: Path, capsys):
    from wiki_io.update_tokens import update_page

    page = tmp_path / "truncated.md"
    page.write_text(
        "---\ntitle: No closing fence\ncategory: concept\n",
        encoding="utf-8",
    )

    update_page(page, dry_run=False)

    err = capsys.readouterr().err
    assert "no closing frontmatter fence" in err
    assert page.name in err or str(page) in err
