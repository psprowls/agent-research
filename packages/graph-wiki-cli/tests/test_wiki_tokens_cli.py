"""gw tokens surface — restores the token-stamping delivery surface deleted
in 73b470ab, which left `tokens` frontmatter `0`/absent on every page (bug:
token-count-field-never-populated)."""

from __future__ import annotations

import json
from pathlib import Path

import frontmatter
from graph_wiki_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _seed_wiki(tmp_path: Path) -> Path:
    """A wiki holding one concept page seeded with the template default `tokens: 0`."""
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "foo.md").write_text(
        "---\ntitle: Foo\ncategory: concept\ntokens: 0\n---\n\nHello world body.\n",
        encoding="utf-8",
    )
    return wiki


def _patch_count_tokens(monkeypatch, value):
    # util_cli/main.py's `tokens` command now delegates to
    # graph_wiki_core.commands.tokens.run_tokens_update, which is where
    # count_tokens/resolve_wiki_and_repo are actually bound and called —
    # see 2026-07-05-thin-the-delivery-surfaces-route-graph-wiki-cli-and-subagent-cli-through-graph-wiki-core.
    monkeypatch.setattr("graph_wiki_core.commands.tokens.count_tokens", lambda text: value)


def test_tokens_command_stamps_real_count(tmp_path, monkeypatch):
    """`gw tokens` overwrites the template `tokens: 0` with the counted value."""
    wiki = _seed_wiki(tmp_path)
    page = wiki / "concepts" / "foo.md"
    _patch_count_tokens(monkeypatch, 7)
    monkeypatch.setattr("graph_wiki_core.commands.tokens.resolve_wiki_and_repo", lambda wp=None: (wiki, None))

    result = runner.invoke(app, ["util", "tokens"])

    assert result.exit_code == 0, result.stdout
    assert frontmatter.load(str(page)).metadata["tokens"] == 7


def test_tokens_command_json_reports_updated(tmp_path, monkeypatch):
    """`--json` emits the {updated, unchanged, skipped} buckets from update_vault."""
    wiki = _seed_wiki(tmp_path)
    _patch_count_tokens(monkeypatch, 7)
    monkeypatch.setattr("graph_wiki_core.commands.tokens.resolve_wiki_and_repo", lambda wp=None: (wiki, None))

    result = runner.invoke(app, ["util", "tokens", "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert any("foo.md" in p for p in payload["updated"])


def test_tokens_command_dry_run_does_not_write(tmp_path, monkeypatch):
    """`--dry-run` reports counts but leaves page bytes untouched."""
    wiki = _seed_wiki(tmp_path)
    page = wiki / "concepts" / "foo.md"
    original = page.read_text(encoding="utf-8")
    _patch_count_tokens(monkeypatch, 7)
    monkeypatch.setattr("graph_wiki_core.commands.tokens.resolve_wiki_and_repo", lambda wp=None: (wiki, None))

    result = runner.invoke(app, ["util", "tokens", "--dry-run"])

    assert result.exit_code == 0, result.stdout
    assert page.read_text(encoding="utf-8") == original


def test_run_tokens_update_uses_graph_io_count_tokens() -> None:
    """graph_wiki_core.commands.tokens's `count_tokens` binding (used internally
    by run_tokens_update, which util_cli/main.py's `tokens` command now calls)
    is the real graph-io offline tiktoken counter, not a stand-in — every test
    above monkeypatches it before running, so import-time identity is the only
    thing left enforcing this."""
    import graph_wiki_core.commands.tokens as core_tokens
    from graph_io.tokens import count_tokens

    assert core_tokens.count_tokens is count_tokens
