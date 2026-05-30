---
phase: quick-260529-pzd
plan: 01
subsystem: model-adapter
tags: [bedrock, content-normalization, async, access-denied, tdd]
requires: []
provides:
  - "_normalize_content boundary helper (list-content → str)"
  - "_GuardedChatBedrockConverse.ainvoke + _original_ainvoke"
  - "_wrap_client_error shared AccessDenied translation"
affects:
  - "downstream .content consumers (synthesizer, ingestor) — now always receive str"
tech-stack:
  added: []
  patterns:
    - "Normalize message content shape at the model-adapter boundary, not per-consumer"
    - "Detect multi-block content via isinstance(content, list), never a model-name check"
key-files:
  created: []
  modified:
    - packages/model-adapter/src/model_adapter/loader.py
    - packages/model-adapter/tests/test_loader.py
    - packages/model-adapter/pyproject.toml
decisions:
  - "Reasoning/thinking blocks preserved on additional_kwargs['reasoning'] (LOCKED — not dropped)"
  - "AccessDenied translation factored into _wrap_client_error and shared by sync invoke + async ainvoke"
metrics:
  duration: "~6 min"
  completed: "2026-05-29"
  tasks: 2
  files: 3
---

# Quick Task 260529-pzd: model-adapter content normalizer Summary

Added a content-shape normalizer at the model-adapter boundary so every consumer
receives a plain `str` on `response.content`, and extended the AccessDenied guard
to the async path — both `invoke` and `ainvoke` now normalize content and
translate `AccessDeniedException` → `BedrockAccessDenied`.

## What Was Built

- **`_normalize_content(response)`** (module helper): returns the response
  unchanged when `getattr(response, "content", None)` is not a list (covers
  bare `object()` and str-content messages). For list content, bare `str` items
  and `{"type": "text", ...}` dicts are joined onto `response.content`; every
  other block (reasoning/thinking) is preserved on
  `response.additional_kwargs["reasoning"]` (a fresh dict is created first if
  `additional_kwargs` is `None`).
- **`_wrap_client_error(self, e)`**: factored the AccessDenied translation out of
  `invoke`; returns a `BedrockAccessDenied` (built via the unchanged
  `_format_access_denied_message`) for `AccessDeniedException`, else `None`.
- **`_original_ainvoke` + async `ainvoke`**: async mirror of the sync path,
  using the same `_wrap_client_error` guard and `_normalize_content` on success.
- **Tests**: sync + async normalization (`content == "Hello world"`, reasoning
  block preserved), string-content pass-through (stays `str`, no `reasoning`
  key), and async AccessDenied (raises `BedrockAccessDenied` naming the ARN).

## Verification

- `uv run --package model-adapter pytest packages/model-adapter -q` → **29 passed**
  (27 pre-existing regression + 2 new async tests).
- Existing AccessDenied / success-path / workspace-override tests all remain green;
  the bare-`object()` success test still passes through unchanged (not a list).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Added `asyncio_mode = "auto"` to model-adapter pyproject**
- **Found during:** Task 2 (first full-suite run)
- **Issue:** The new `async def test_*` functions failed to collect with
  "async functions are not natively supported." `packages/model-adapter/pyproject.toml`
  carries its own `[tool.pytest.ini_options]` block, which becomes pytest's active
  config when rootdir resolves to the package — fully overriding the workspace-root
  config (which has `asyncio_mode = "auto"`, per CLAUDE.md §8). The package had no
  async tests before, so the gap never surfaced.
- **Fix:** Added `asyncio_mode = "auto"` to the package's `[tool.pytest.ini_options]`,
  mirroring the root convention, with a comment explaining the override.
- **Files modified:** packages/model-adapter/pyproject.toml
- **Commit:** 02ee3fe (bundled with the Task 2 test commit since it is required for those tests to run)

## Commits

- `b81c9b0` feat(quick-260529-pzd): normalize list-shaped content + async AccessDenied guard
- `02ee3fe` test(quick-260529-pzd): add sync+async content-normalization and async AccessDenied tests

## Self-Check: PASSED

- Files: loader.py, test_loader.py, pyproject.toml — all FOUND
- Commits: b81c9b0, 02ee3fe — all FOUND
- `_normalize_content`, `_original_ainvoke` present in loader.py; `ainvoke` present in tests
