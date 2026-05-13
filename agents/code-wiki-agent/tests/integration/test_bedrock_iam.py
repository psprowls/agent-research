"""Bedrock IAM gate tests for code-wiki-agent.

Two functions:

  - test_make_llm_haiku_invoke
      Live Bedrock test. Marked @pytest.mark.integration so it is skipped in CI
      by default. Gated additionally by CODE_WIKI_RUN_INTEGRATION=1 so even when
      `pytest -m integration` is requested, the test is a no-op unless the
      developer explicitly opts into real-network calls.

  - test_make_llm_raises_bedrock_access_denied_on_bad_creds
      Mock-only. NOT marked integration — it runs in CI as a regression gate
      for the actionable IAM error path. Patches `_original_invoke` to raise a
      simulated AccessDeniedException and asserts the wrapped error message
      contains the model ARN AND the `bedrock:InvokeModel` IAM action string.

Per-function marking (not module-level pytestmark) keeps the mock test out of
the integration set so the negative path runs by default.
"""

from __future__ import annotations

import os

import botocore.exceptions
import pytest

HAIKU_ARN = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


@pytest.mark.integration
def test_make_llm_haiku_invoke():
    """Calls real Bedrock when CODE_WIKI_RUN_INTEGRATION=1; otherwise skips."""
    if not os.environ.get("CODE_WIKI_RUN_INTEGRATION"):
        pytest.skip("Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations")
    from model_adapter.loader import make_llm

    llm = make_llm("haiku")
    result = llm.invoke("Reply with exactly: pong")
    assert result.content  # non-empty


def test_make_llm_raises_bedrock_access_denied_on_bad_creds(monkeypatch):
    """Mocked AccessDeniedException → BedrockAccessDenied with ARN + IAM action in message."""
    from model_adapter.exceptions import BedrockAccessDenied
    from model_adapter.loader import make_llm

    def raise_access_denied(*args, **kwargs):
        raise botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "InvokeModel",
        )

    llm = make_llm("haiku")
    monkeypatch.setattr(llm, "_original_invoke", raise_access_denied)

    with pytest.raises(BedrockAccessDenied) as exc_info:
        llm.invoke("ping")

    msg = str(exc_info.value)
    assert HAIKU_ARN in msg
    assert "bedrock:InvokeModel" in msg
