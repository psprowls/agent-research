"""Unit-test guards for graph-wiki-core.

Token stamping/counting reaches Bedrock through `graph_io.tokens.count_tokens`
(direct boto3, not the model_adapter the narrator fan-out stubs), imported
directly (module-level `from graph_io.tokens import count_tokens`) into both
`commands/scan.py` (passed into `update_tokens.update_vault`) and
`commands/query.py`. The narrated scan path stamps tokens and query counts
prompt/context tokens, so any unit test exercising those paths would otherwise
make live CountTokens calls. Stub both modules' bound names offline by default
with a deterministic word count — the same stub `test_round_trip` uses. Real
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

# Capture the real helper ONCE at conftest import time, BEFORE any test or
# autouse fixture has had a chance to stub it. Tests opt into the real
# workspace path by requesting the `real_workspace_role_override` fixture.
_REAL_WORKSPACE_ROLE_OVERRIDE = _roles._workspace_role_override


@pytest.fixture(autouse=True)
def _offline_count_tokens(monkeypatch):
    # Maintenance note: add a patch line here for every new direct importer of
    # `graph_io.tokens.count_tokens` (i.e. every module that does
    # `from graph_io.tokens import count_tokens`) — this fixture only stubs the
    # bindings named below, not the underlying `graph_io.tokens.count_tokens`.
    from graph_wiki_core.commands import query as query_module
    from graph_wiki_core.commands import scan as scan_module

    fake_count_tokens = lambda text, model_id=None, region=None: len(text.split())  # noqa: E731
    monkeypatch.setattr(scan_module, "count_tokens", fake_count_tokens)
    monkeypatch.setattr(query_module, "count_tokens", fake_count_tokens)


@pytest.fixture(autouse=True)
def _isolate_roles_from_workspace(monkeypatch):
    """Default isolation: stub _workspace_role_override to return None so
    make_llm() reads packaged defaults deterministically.
    """
    monkeypatch.setattr(_roles, "_workspace_role_override", lambda role: None)


@pytest.fixture
def real_workspace_role_override(monkeypatch):
    """Restore the real `_workspace_role_override` so the test exercises
    the production resolution path (`workspace_io.resolve` + `read_roles`).
    """
    monkeypatch.setattr(_roles, "_workspace_role_override", _REAL_WORKSPACE_ROLE_OVERRIDE)
    return _REAL_WORKSPACE_ROLE_OVERRIDE
