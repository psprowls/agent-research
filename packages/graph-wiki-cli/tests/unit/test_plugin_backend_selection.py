"""Unit tests for the plugin shims' `_config.backend_for` resolution.

`backend_for` must resolve the workspace the same way every other surface does
— via `workspace_io.resolve()` (the `GRAPH_WIKI_WORKSPACE` override, else
discovery; the repo-side `.graph-wiki.local.yaml` pointer is dead) — and read the
`plugin:` block from `<workspace>/.graph-wiki.yaml`, NOT from cwd.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SCRIPT_DIR = Path(__file__).resolve().parents[4] / "plugins" / "graph-wiki" / "skills" / "graph-wiki" / "scripts"


@pytest.fixture
def backend_for(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(_SCRIPT_DIR))
    sys.modules.pop("_config", None)  # drop any stub left by sibling shim tests
    return importlib.import_module("_config").backend_for


def _write_workspace(
    tmp_path: Path,
    *,
    overrides: dict[str, str] | None = None,
    default: str | None = None,
    write_manifest: bool = True,
) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    if not write_manifest:
        return ws
    lines = ["version: 2", "initialized_at: '2026-06-06'", "topic: T", "plugins: []"]
    if overrides is not None or default is not None:
        lines.append("plugin:")
        if default is not None:
            lines.append(f"  backend_default: {default}")
        if overrides is not None:
            lines.append("  backend_overrides:")
            lines += [f"    {k}: {v}" for k, v in overrides.items()]
    (ws / ".graph-wiki.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ws


def test_reads_override_from_resolved_workspace(tmp_path, monkeypatch, backend_for):
    """A per-command override in the resolved workspace manifest is honored."""
    ws = _write_workspace(tmp_path, overrides={"scan": "bedrock", "ingest": "claude"})
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(ws))
    assert backend_for("scan") == "bedrock"
    assert backend_for("ingest") == "claude"


def test_falls_back_to_backend_default(tmp_path, monkeypatch, backend_for):
    """A command absent from overrides falls back to backend_default."""
    ws = _write_workspace(tmp_path, overrides={"scan": "bedrock"}, default="claude")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(ws))
    assert backend_for("query") == "claude"


def test_missing_workspace_manifest_returns_claude(tmp_path, monkeypatch, backend_for):
    """No reachable workspace manifest -> safe 'claude' fallback, never raises."""
    ws = _write_workspace(tmp_path, write_manifest=False)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(ws))
    assert backend_for("scan") == "claude"
