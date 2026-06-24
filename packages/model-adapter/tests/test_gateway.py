"""Unit tests for the Vercel AI Gateway path in model_adapter.loader.

No real gateway calls — all network paths are mocked via a stub
`_original_invoke`, mirroring tests/test_loader.py for the Bedrock path.
"""

from __future__ import annotations


def test_gateway_access_denied_is_exported_exception():
    from model_adapter import GatewayAccessDenied

    assert issubclass(GatewayAccessDenied, Exception)
