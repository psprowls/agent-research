"""Phase 23 SC#2 mechanical smoke — Pydantic schema rejects the legacy MCP field.

Each Wiki*Input class in graph_wiki_mcp.server sets
``model_config = ConfigDict(extra='forbid')`` (WSMCP-01 Task 1). This file
asserts that a payload carrying the legacy ``vault_path`` key now raises
``pydantic.ValidationError`` rather than being silently dropped (Pydantic v2
default is ``extra='ignore'``). Runs in the default ``uv run pytest`` pass —
no Bedrock / no subprocess / no integration gate.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_legacy_vault_path_field_rejected_by_schema() -> None:
    """WSMCP-01 + ROADMAP SC#2: legacy field name on WikiScanInput raises ValidationError."""
    from graph_wiki_mcp.server import WikiScanInput

    with pytest.raises(ValidationError):
        WikiScanInput(**{"vault_path": "/tmp/x"})


def test_workspace_path_field_accepted() -> None:
    """Positive control: the new field name on WikiScanInput is accepted without error."""
    from graph_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput(workspace_path="/tmp/x")
    assert inp.workspace_path == "/tmp/x"
