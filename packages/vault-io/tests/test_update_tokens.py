from __future__ import annotations

"""Tests for vault_io.update_tokens — Bedrock CountTokens API shape.

Requirements: TOK-01, TOK-02 (mocked).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_count_tokens_request_shape() -> None:
    from vault_io.update_tokens import count_tokens

    fake_client = MagicMock()
    fake_client.count_tokens.return_value = {"inputTokens": 42}

    with patch("vault_io.update_tokens.boto3.client", return_value=fake_client) as mock_factory:
        result = count_tokens("hello world", model_id="m1", region="us-east-1")

    mock_factory.assert_called_once_with("bedrock-runtime", region_name="us-east-1")
    fake_client.count_tokens.assert_called_once_with(
        modelId="m1",
        input={
            "converse": {
                "messages": [
                    {"role": "user", "content": [{"text": "hello world"}]}
                ]
            }
        },
    )
    assert result == 42


def test_count_tokens_returns_input_tokens() -> None:
    from vault_io.update_tokens import count_tokens

    fake_client = MagicMock()
    fake_client.count_tokens.return_value = {"inputTokens": 99}

    with patch("vault_io.update_tokens.boto3.client", return_value=fake_client):
        result = count_tokens("test text", model_id="m1", region="us-east-1")

    assert result == 99
