"""Unit-test guards for graph-wiki-core.

Token stamping reaches Bedrock through `wiki_io.update_tokens.count_tokens`
(direct boto3, not the model_adapter the narrator fan-out stubs). The narrated
scan path now stamps tokens, so any unit test running `run_scan(narrate=True)`
would otherwise make live CountTokens calls. Stub it offline by default with a
deterministic word count — the same stub `test_round_trip` uses. Real
CountTokens behavior stays covered by wiki-io's gated integration tests.

Workspace isolation: `graph_wiki_core.roles._workspace_role_override` consults
`workspace_io.resolve()` which in a dev environment finds the real workspace.
The autouse fixture below stubs it to return None so role tests read packaged
defaults deterministically. Tests that exercise the workspace-override path opt
in by patching `_workspace_role_override` directly via monkeypatch.
"""

from __future__ import annotations

import pytest
from graph_wiki_core import roles as _roles


@pytest.fixture(autouse=True)
def _offline_count_tokens(monkeypatch):
    from wiki_io import update_tokens

    monkeypatch.setattr(
        update_tokens,
        "count_tokens",
        lambda text, model_id=None, region=None: len(text.split()),
    )


@pytest.fixture(autouse=True)
def _isolate_roles_from_workspace(monkeypatch):
    """Default isolation: stub _workspace_role_override to return None so
    make_llm() reads packaged defaults deterministically.
    """
    monkeypatch.setattr(_roles, "_workspace_role_override", lambda role: None)
