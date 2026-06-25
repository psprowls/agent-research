"""model_adapter — generic Bedrock + Vercel AI Gateway chat-model client.

Public API:
    make_bedrock_llm(model_id, ...) → guarded Bedrock Converse chat model
    make_gateway_llm(model_id, ...) → guarded Vercel AI Gateway chat model
    BedrockAccessDenied  → raised when Bedrock rejects with AccessDenied
    GatewayAccessDenied  → raised when the Vercel AI Gateway rejects on auth
"""

from __future__ import annotations

from model_adapter.exceptions import BedrockAccessDenied, GatewayAccessDenied
from model_adapter.loader import make_bedrock_llm, make_gateway_llm

__all__ = [
    "BedrockAccessDenied",
    "GatewayAccessDenied",
    "make_bedrock_llm",
    "make_gateway_llm",
]
