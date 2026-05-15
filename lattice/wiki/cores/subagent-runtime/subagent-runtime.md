---
title: subagent-runtime
category: package
summary: Async fan-out primitive — dispatches concurrent LLM calls via a worker pool and collects results
status: active
package_path: cores/subagent-runtime
package_type: library
domain:
language: python
depends_on:
  - model-adapter
tags: [concurrency, bedrock, fan-out, langchain]
sources: 0
updated: 2026-05-14
tokens: 0
last_sync_commit:
last_sync_at:
---

# subagent-runtime

## Purpose

Provides the async worker pool used when `code-wiki-agent` needs to read or process multiple wiki pages in parallel. Wraps `ChatBedrockConverse` in a pool that accepts a list of prompts, dispatches them concurrently up to a configurable limit, and returns ordered results. Keeps the fan-out logic in one place so agent commands don't each re-implement `asyncio.gather`.

## Public API

- `pool.SubagentPool` — `src/subagent_runtime/pool.py` — async context manager; `await pool.run(prompts)` returns list of responses in submission order

## File map - subagent-runtime

- `pyproject.toml` — package manifest; workspace dep on `model-adapter`

### subagent-runtime/src/

#### subagent-runtime/src/subagent_runtime/

- `__init__.py` — re-exports `SubagentPool`
- `pool.py` — `SubagentPool`: semaphore-bounded `asyncio.gather` over `ChatBedrockConverse.ainvoke`; accepts a model instance from `model-adapter`

### subagent-runtime/tests/

- `__init__.py` — package init
- `conftest.py` — fake model fixture
- `test_pool.py` — unit tests with mock Bedrock responses (ordering, error handling, concurrency cap)

#### subagent-runtime/tests/integration/

Live Bedrock tests (marked `integration`, skipped by default).

- `__init__.py` — package init
- `test_pool_bedrock.py` — fires real concurrent requests against Bedrock to verify rate-limit handling

## Key patterns

- Concurrency cap is a constructor param (default: 5); tune for Bedrock TPS limits
- Uses `ChatBedrockConverse.ainvoke` which wraps sync boto3 — not true async but sufficient for I/O-bound wiki reads
- Results list preserves submission order regardless of completion order

## Used by
- [[agents/code-wiki-agent/code-wiki-agent]]
- [[cores/eval-harness/eval-harness]]

## Related concepts
- [[concepts/bedrock-async-pseudo-async]]

## Dependencies (external)
- [[dependencies/langchain-aws]]
- [[dependencies/langchain-core]]
