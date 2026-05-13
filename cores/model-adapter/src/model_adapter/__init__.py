"""model_adapter — Bedrock model loader for code-wiki-agent.

Public API:
    make_llm(role)          → ChatBedrockConverse with actionable IAM errors
    BedrockAccessDenied     → raised when Bedrock rejects with AccessDenied
"""

from __future__ import annotations

from model_adapter.exceptions import BedrockAccessDenied
from model_adapter.loader import make_llm

__all__ = ["BedrockAccessDenied", "make_llm"]
