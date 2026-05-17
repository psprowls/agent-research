---
title: model-adapter
category: package
summary: AWS Bedrock model loader — resolves ChatBedrockConverse instances from a TOML model registry
status: active
package_path: packages/model-adapter
package_type: library
domain:
language: python
depends_on: []
tags: [bedrock, models, langchain-aws]
sources: 0
updated: 2026-05-14
tokens: 0
last_sync_commit:
last_sync_at:
---

# model-adapter

## Purpose

Thin loader that reads a TOML model registry (e.g. `models-qwen.toml`) and returns configured `ChatBedrockConverse` instances. Centralises all model-ID and region wiring so the rest of the codebase can request a model by role (`orchestrator`, `librarian`, `synthesizer`) without knowing Bedrock ARNs.

## Public API

- `loader.load(role, config_path)` — `src/model_adapter/loader.py` — returns a `ChatBedrockConverse` for the given role name
- `exceptions.ModelNotFoundError` — `src/model_adapter/exceptions.py` — raised when a role key is missing from the registry

## File map - model-adapter

- `models.toml` — bundled default model registry (shipped via `pyproject.toml [tool.uv.build.include]`)
- `pyproject.toml` — package manifest; no workspace deps

### model-adapter/src/

#### model-adapter/src/model_adapter/

- `__init__.py` — re-exports `load`, `ModelNotFoundError`
- `loader.py` — TOML parsing and `ChatBedrockConverse` construction; reads `models.toml` then overlays caller-supplied config
- `exceptions.py` — `ModelNotFoundError`
- `models.toml` — default role → model-ID mapping (Qwen3 variants on Bedrock Marketplace)

### model-adapter/tests/

- `__init__.py` — package init
- `test_loader.py` — unit tests for TOML loading and role resolution

## Key patterns

- `ChatBedrockConverse` is the only LLM class used — never `ChatBedrock` (legacy)
- Model IDs are read from TOML, never hardcoded in agent code
- The bundled `models.toml` is overridden by the project-level `models-qwen.toml` at runtime

## Used by
- [[agents/code-wiki-agent/code-wiki-agent]]
- [[packages/subagent-runtime/subagent-runtime]]
- [[packages/eval-harness/eval-harness]]

## Dependencies (external)
- [[dependencies/langchain-aws]]
- [[dependencies/boto3]]
