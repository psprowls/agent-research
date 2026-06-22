"""Unit tests for guidance_classifier and guidance_orchestrator roles.

Verifies that both roles are properly configured in models.toml with the
required keys (model_id, region, max_tokens, max_concurrency) and that
guidance_classifier has higher or equal concurrency than guidance_orchestrator.
"""

from __future__ import annotations

import pytest
from model_adapter.loader import load_role_config


@pytest.mark.parametrize("role", ["guidance_classifier", "guidance_orchestrator"])
def test_guidance_role_loads(role: str) -> None:
    """Both guidance roles load successfully with required config keys."""
    cfg = load_role_config(role)
    assert cfg["model_id"]
    assert cfg["region"]
    assert isinstance(cfg["max_tokens"], int)
    assert isinstance(cfg["max_concurrency"], int)


def test_classifier_is_higher_concurrency_than_orchestrator() -> None:
    """Guidance classifier concurrency >= orchestrator concurrency."""
    clf = load_role_config("guidance_classifier")
    orch = load_role_config("guidance_orchestrator")
    assert clf["max_concurrency"] >= orch["max_concurrency"]
