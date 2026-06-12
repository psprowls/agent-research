"""Unit-test guards for graph-wiki-core.

Token stamping reaches Bedrock through `wiki_io.update_tokens.count_tokens`
(direct boto3, not the model_adapter the narrator fan-out stubs). The narrated
scan path now stamps tokens, so any unit test running `run_scan(narrate=True)`
would otherwise make live CountTokens calls. Stub it offline by default with a
deterministic word count — the same stub `test_round_trip` uses. Real
CountTokens behavior stays covered by wiki-io's gated integration tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _offline_count_tokens(monkeypatch):
    from wiki_io import update_tokens

    monkeypatch.setattr(
        update_tokens,
        "count_tokens",
        lambda text, model_id=None, region=None: len(text.split()),
    )
