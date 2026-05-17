"""model_adapter — Bedrock model loader for code-wiki-agent.

Public API:
    make_llm(role)           → ChatBedrockConverse with actionable IAM errors
    load_role_config(role)   → dict with model_id, region, max_tokens, max_concurrency
    BedrockAccessDenied      → raised when Bedrock rejects with AccessDenied
"""

from __future__ import annotations

from model_adapter.exceptions import BedrockAccessDenied
from model_adapter.loader import load_role_config, make_llm, set_models_path

__all__ = ["BedrockAccessDenied", "load_role_config", "make_llm", "set_models_path"]
