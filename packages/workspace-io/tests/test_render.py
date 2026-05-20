"""Tests for workspace_io.render — workspace-level CLAUDE.md rendering."""
from __future__ import annotations

from pathlib import Path

import pytest

from workspace_io.render import (
    AUTO_END,
    AUTO_START,
    render_workspace_claude_md,
)


def _write_manifest(workspace: Path, plugins: list[str]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    body = "version: 2\ninitialized_at: 2026-05-09\nplugins:\n"
    for p in plugins:
        body += (
            f"  - name: {p}\n"
            f"    installed_version: null\n"
            f"    applied_version: null\n"
        )
    (workspace / ".graph-wiki.yaml").write_text(body, encoding="utf-8")


def test_creates_claude_md_on_first_call(tmp_path):
    _write_manifest(tmp_path, ["graph-wiki-agent"])
    render_workspace_claude_md(tmp_path)
    claude = tmp_path / "CLAUDE.md"
    assert claude.exists()
    text = claude.read_text(encoding="utf-8")
    assert AUTO_START in text
    assert AUTO_END in text
    assert "graph-wiki-agent" in text


def test_lists_each_installed_plugin(tmp_path):
    _write_manifest(tmp_path, ["graph-wiki-agent", "code-wiki-second"])
    render_workspace_claude_md(tmp_path)
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "graph-wiki-agent" in text
    assert "code-wiki-second" in text


def test_refresh_updates_plugin_block_only(tmp_path):
    _write_manifest(tmp_path, ["graph-wiki-agent"])
    render_workspace_claude_md(tmp_path)

    # User adds prose between renders. Two regions: above the auto block,
    # and below it.
    claude = tmp_path / "CLAUDE.md"
    text = claude.read_text(encoding="utf-8")
    text = "USER PROSE ABOVE\n" + text + "\nUSER PROSE BELOW\n"
    claude.write_text(text, encoding="utf-8")

    # New plugin registered → re-render. Auto block updates; user prose
    # is preserved.
    _write_manifest(tmp_path, ["graph-wiki-agent", "code-wiki-second"])
    render_workspace_claude_md(tmp_path)
    after = claude.read_text(encoding="utf-8")
    assert "USER PROSE ABOVE" in after
    assert "USER PROSE BELOW" in after
    assert "code-wiki-second" in after


def test_idempotent_same_plugin_set(tmp_path):
    _write_manifest(tmp_path, ["graph-wiki-agent"])
    render_workspace_claude_md(tmp_path)
    first = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    render_workspace_claude_md(tmp_path)
    second = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert first == second


def test_unknown_plugin_renders_generic_pointer(tmp_path):
    """An unknown plugin still appears in the list with no detail link."""
    _write_manifest(tmp_path, ["some-third-party-plugin"])
    render_workspace_claude_md(tmp_path)
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "some-third-party-plugin" in text


def test_no_manifest_no_render(tmp_path):
    """If the manifest is missing, render is a no-op (caller's job to ensure manifest)."""
    # No .graph-wiki.yaml written.
    render_workspace_claude_md(tmp_path)
    assert not (tmp_path / "CLAUDE.md").exists()
