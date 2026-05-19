---
title: subagent-runtime
category: package
summary: Async fan-out pool (SubagentPool) with per-call JSONL trace records (schema_version 1) and the shared write_trace_record helper used across commands.
status: active
package_path: packages/subagent-runtime
package_type: library
domain:
language: Python
depends_on: []
tags: [python, async, fan-out, tracing]
sources: 0
updated: 2026-05-19
---

# subagent-runtime

## Overview

`subagent-runtime` is the async fan-out primitive of the post-rebrand `deep-agents` monorepo. `SubagentPool.run_all` dispatches N items in parallel through a caller-supplied async task, enforces a per-role semaphore, isolates per-item failures, and writes a JSONL trace record per invocation (success / cancelled / error). The trace-writing logic was extracted in Phase 16 D-04 into the `trace_io.write_trace_record` helper so command-level callers (ingest, query) can emit identically-shaped records without duplicating the construction logic.

## API

- `SubagentPool(trace_dir: Path, *, default_recursion_limit: int = 100)`
- `await pool.run_all(items, task, role, *, model_id, max_concurrency, recursion_limit=None) -> FanOutResult`
- `trace_io.write_trace_record(path, role, model_id, item, status, latency_ms, response, *, error=None) -> None`

## Cross-refs

- Consumed by [[wiki/agents/code-wiki-agent/code-wiki-agent]] commands.query for librarian + code-reader fan-outs
