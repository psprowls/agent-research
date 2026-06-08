---
title: model-adapter
uri: pkg:agent-research/model-adapter
kind: package
summary: Bedrock Converse role-config loader; reads models.toml and produces guarded per-role LLM instances with bundled defaults.
updated: 2026-05-19
---

# model-adapter

## Overview

`model-adapter` is the Bedrock model-config layer of the post-rebrand `agent-research` monorepo. It reads `packages/model-adapter/src/model_adapter/models.toml`, applies optional workspace overrides, and exposes `load_role_config(role)` plus `make_llm(role)` for every in-scope role. `make_llm` returns a guarded Bedrock Converse chat model so callers keep the shared `AccessDeniedException` to `BedrockAccessDenied` translation instead of constructing Bedrock clients directly.

## API

- `load_role_config(role: str) -> dict` — returns `{"model_id", "region", "max_tokens", "max_concurrency"}`
- `make_llm(role: str) -> _GuardedChatBedrockConverse` — shared Bedrock Converse constructor for role-scoped model access
- `set_models_path(path: Path)` — test override for `models.toml`
- `BedrockAccessDenied` — actionable exception for IAM or model-access failures

## Cross-refs

- Consumed by [[entities/pkg_subagent-runtime]] fan-out and [[entities/pkg_graph-wiki-core]] command orchestration
