from __future__ import annotations

"""Tests for wiki_io.update_tokens — Bedrock CountTokens API shape.

Requirements: TOK-01, TOK-02 (mocked).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_count_tokens_request_shape() -> None:
    from wiki_io.update_tokens import count_tokens

    fake_client = MagicMock()
    fake_client.count_tokens.return_value = {"inputTokens": 42}

    with patch("wiki_io.update_tokens.boto3.client", return_value=fake_client) as mock_factory:
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
    from wiki_io.update_tokens import count_tokens

    fake_client = MagicMock()
    fake_client.count_tokens.return_value = {"inputTokens": 99}

    with patch("wiki_io.update_tokens.boto3.client", return_value=fake_client):
        result = count_tokens("test text", model_id="m1", region="us-east-1")

    assert result == 99


# F2 — tokens: null on unsupported model.

def _seed_page(path: Path, tokens_value: str | int | None = 5) -> None:
    """Write a minimal page with the given tokens frontmatter value.

    `tokens_value` may be an int (becomes `tokens: <int>`), the string "null"
    (becomes `tokens: null`), or None (omits the tokens line entirely).
    """
    fm_lines = [
        "---",
        "title: Test",
        "category: concept",
        "summary: t",
    ]
    if tokens_value == "null":
        fm_lines.append("tokens: null")
    elif tokens_value is not None:
        fm_lines.append(f"tokens: {tokens_value}")
    fm_lines.append("---")
    path.write_text("\n".join(fm_lines) + "\n\nBody.\n", encoding="utf-8")


def _validation_client_error(message: str = "Model does not support count tokens operation"):
    from botocore.exceptions import ClientError

    return ClientError(
        error_response={
            "Error": {
                "Code": "ValidationException",
                "Message": message,
            }
        },
        operation_name="CountTokens",
    )


def test_unsupported_model_detector_handles_modern_phrasing() -> None:
    """As of 2026-05 Bedrock returns 'The provided model doesn't support
    counting tokens.' for Claude 4.x models. The detector must recognise both
    that and the older 'count tokens operation' wording so the run gracefully
    stamps `tokens: null` instead of crashing the whole vault refresh.
    Regression for the 2026-05-23 lint finding (8 concept pages stuck without
    tokens because every CountTokens call surfaced as ('skipped', 0))."""
    from wiki_io.update_tokens import _is_unsupported_model_error

    legacy = _validation_client_error("Model does not support count tokens operation")
    modern = _validation_client_error("The provided model doesn't support counting tokens.")
    unrelated = _validation_client_error("Inference profile ARN is malformed")

    assert _is_unsupported_model_error(legacy) is True
    assert _is_unsupported_model_error(modern) is True
    assert _is_unsupported_model_error(unrelated) is False


def test_unsupported_model_writes_tokens_null(tmp_path: Path) -> None:
    """When CountTokens raises ValidationException with the unsupported-operation
    message, the page is rewritten with `tokens: null` and update_page returns
    ('updated', None)."""
    import frontmatter
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)

    fake_client = MagicMock()
    fake_client.count_tokens.side_effect = _validation_client_error()

    with patch("wiki_io.update_tokens.boto3.client", return_value=fake_client):
        status, count = update_page(page, dry_run=False, model_id="m1", region="us-east-1")

    assert status == "updated"
    assert count is None
    rewritten = page.read_text(encoding="utf-8")
    assert "tokens: null" in rewritten
    assert frontmatter.loads(rewritten).metadata["tokens"] is None


def test_legitimate_zero_writes_tokens_zero(tmp_path: Path) -> None:
    """count_tokens returning 0 must write `tokens: 0` (NOT `tokens: null`)."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)

    fake_client = MagicMock()
    fake_client.count_tokens.return_value = {"inputTokens": 0}

    with patch("wiki_io.update_tokens.boto3.client", return_value=fake_client):
        status, count = update_page(page, dry_run=False, model_id="m1", region="us-east-1")

    assert status == "updated"
    assert count == 0
    rewritten = page.read_text(encoding="utf-8")
    assert "tokens: 0" in rewritten
    assert "tokens: null" not in rewritten


def test_null_idempotent_on_rerun(tmp_path: Path) -> None:
    """A page already at `tokens: null` re-encountering an unsupported model
    stays at `tokens: null` and reports 'unchanged'."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value="null")
    original = page.read_text(encoding="utf-8")

    fake_client = MagicMock()
    fake_client.count_tokens.side_effect = _validation_client_error()

    with patch("wiki_io.update_tokens.boto3.client", return_value=fake_client):
        status, count = update_page(page, dry_run=False, model_id="m1", region="us-east-1")

    assert status == "unchanged"
    assert count is None
    # Bytes unchanged.
    assert page.read_text(encoding="utf-8") == original


def test_non_validation_errors_still_skip(tmp_path: Path) -> None:
    """Generic exceptions (network errors, etc.) preserve existing
    ('skipped', 0) behavior — the page is NOT mutated."""
    from wiki_io.update_tokens import update_page

    page = tmp_path / "page.md"
    _seed_page(page, tokens_value=5)
    original = page.read_text(encoding="utf-8")

    fake_client = MagicMock()
    fake_client.count_tokens.side_effect = RuntimeError("network down")

    with patch("wiki_io.update_tokens.boto3.client", return_value=fake_client):
        status, count = update_page(page, dry_run=False, model_id="m1", region="us-east-1")

    assert status == "skipped"
    assert count == 0
    # Page must not have been rewritten.
    assert page.read_text(encoding="utf-8") == original
