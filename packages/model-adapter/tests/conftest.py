"""Test isolation fixtures for model-adapter (Phase 20 / WMC-02).

The model-adapter loader consults `workspace_io.resolve()` + `read_roles()`
to resolve per-role overrides from `<workspace>/.graph-wiki.yaml`. In an
interactive dev environment the `GRAPH_WIKI_WORKSPACE` env var, or a `.git`
walked up from cwd, would silently route resolution to a real workspace,
making pre-existing tests pass or fail based on inherited env state. The
autouse fixture below neutralizes both signals so the default test path is
deterministic (packaged `models.toml`).

Tests that exercise the workspace-override path opt in by requesting the
`real_workspace_role_override` fixture, which restores the production helper
AFTER the autouse stub has run.
"""
from __future__ import annotations

import pytest

# Capture the real helper ONCE at conftest import time, BEFORE any test or
# autouse fixture has had a chance to stub it. Tests opt into the real
# workspace path by requesting the `real_workspace_role_override` fixture.
from model_adapter import loader as _loader

_REAL_WORKSPACE_ROLE_OVERRIDE = _loader._workspace_role_override


@pytest.fixture(autouse=True)
def _isolate_model_adapter_from_workspace(monkeypatch):
    """Default isolation: drop GRAPH_WIKI_WORKSPACE; stub the helper to
    return None so `make_llm()` reads packaged defaults deterministically.
    """
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    monkeypatch.setattr(_loader, "_workspace_role_override", lambda role: None)
    yield


@pytest.fixture
def real_workspace_role_override(monkeypatch):
    """Restore the real `_workspace_role_override` so the test exercises
    the production resolution path (`workspace_io.resolve` + `read_roles`).
    """
    monkeypatch.setattr(_loader, "_workspace_role_override", _REAL_WORKSPACE_ROLE_OVERRIDE)
    return _REAL_WORKSPACE_ROLE_OVERRIDE
