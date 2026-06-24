"""model_adapter — Bedrock + Vercel AI Gateway model loader for graph-wiki-agent.

Public API:
    make_llm(role)           → guarded chat model (Bedrock default, or Vercel
                               AI Gateway when the role sets backend = "vercel")
    load_role_config(role)   → dict with model_id, region, max_tokens, max_concurrency
    BedrockAccessDenied      → raised when Bedrock rejects with AccessDenied
    GatewayAccessDenied      → raised when the Vercel AI Gateway rejects on auth
"""

from __future__ import annotations

from model_adapter.exceptions import BedrockAccessDenied, GatewayAccessDenied
from model_adapter.loader import load_role_config, make_llm

__all__ = ["BedrockAccessDenied", "GatewayAccessDenied", "load_role_config", "make_llm"]
