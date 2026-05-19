---
title: model-adapter
category: package
summary: ChatBedrockConverse role-config loader; reads models.toml and produces per-role LLM instances with the bundled defaults (Qwen synthesizer, Haiku librarian, etc).
status: active
package_path: packages/model-adapter
package_type: library
domain:
language: Python
depends_on: []
tags: [python, bedrock, config]
sources: 0
updated: 2026-05-19
---

# model-adapter

## Overview

`model-adapter` is the Bedrock model-config layer of the post-rebrand `deep-agents` monorepo. It reads `packages/model-adapter/src/model_adapter/models.toml` and exposes `load_role_config(role)` + `make_llm(role)` for every in-scope role. The bundled defaults are the Qwen-family synthesizer (`qwen.qwen3-32b-v1:0`), the Haiku librarian, and so on. Override at call time via `ChatBedrockConverse(model_id=..., region_name=..., max_tokens=...)`.

## API

- `load_role_config(role: str) -> dict` — returns `{"model_id", "region", "max_tokens", "max_concurrency"}`
- `make_llm(role: str) -> ChatBedrockConverse` — convenience constructor
- `set_models_path(path: Path)` — test override for `models.toml`

## Cross-refs

- Consumed everywhere: [[wiki/packages/subagent-runtime/subagent-runtime]], [[wiki/agents/code-wiki-agent/code-wiki-agent]]
