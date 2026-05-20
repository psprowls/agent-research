---
phase: 19-phase-16-code-review-burndown
plan: 04
subsystem: graph-wiki-agent/commands/query + docs/cancellation
tags: [code-review-burndown, query, trace, docs, refactor]
requires: []
provides:
  - "query.py with corrected _extract_usage_tokens docstring (points at subagent_runtime.trace_io.write_trace_record:56-66)"
  - "query.py with deduplicated G1 logic (apply_guardrails delegates to _compute_unresolved_wikilinks)"
  - "query.py with qualified synth trace filenames (synth_librarian_*, synth_codefallback_*)"
  - "docs/cancellation.md JSON examples with schema_version: 1"
affects:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
  - docs/cancellation.md
tech-stack:
  added: []
  patterns:
    - "Phase 10 # Source: provenance norm — restored a correct line reference instead of dropping it (D-07)"
    - "Shared-helper delegation — single resolution algorithm in _compute_unresolved_wikilinks (D-15)"
key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
    - docs/cancellation.md
decisions:
  - "D-07 docstring line range 56-66 verified against current trace_io.py — accurate as of this commit"
  - "D-15 dedup removed inline G1 block; _compute_unresolved_wikilinks signature unchanged"
  - "D-12 filenames written verbatim per CONTEXT.md (synth_librarian_, synth_codefallback_)"
metrics:
  duration: "~10 min"
  completed: 2026-05-20
---

# Phase 19 Plan 04: Query Trace + Docs Cleanup Summary

One-liner: Landed CONTEXT.md decisions D-07, D-12, D-14, and D-15 — query.py docstring repair + G1 dedup + synth-filename qualification + cancellation.md schema_version examples — closing four IN-level findings from the Phase 16 code review.

## Scope

Four surgical fixes from `16-REVIEW.md`:

| Finding  | Decision | File                                          | Lines       | Change |
|----------|----------|-----------------------------------------------|-------------|--------|
| IN-01    | D-07     | `agents/.../commands/query.py`                | 283-286     | Repoint stale docstring at `subagent_runtime.trace_io.write_trace_record:56-66` (canonical home post-Phase-16 D-04 extraction). |
| IN-06    | D-12     | `agents/.../commands/query.py`                | 534, 964    | Qualify synth trace filenames: regular path → `synth_librarian_{query_id}.jsonl`, code-fallback path → `synth_codefallback_{query_id}.jsonl`. |
| IN-08    | D-14     | `docs/cancellation.md`                        | 103-116, 121-132 | Add `"schema_version": 1,` to both inline JSON example blocks (per-item cancelled record + batch terminal summary). |
| IN-09    | D-15     | `agents/.../commands/query.py`                | 663-670     | Refactor `apply_guardrails` G1 branch to call `_compute_unresolved_wikilinks` instead of duplicating the resolution algorithm inline. |

No new dependencies, no new files, no test changes — fix-only per CONTEXT.md §D-18.

## Commits

| Task | Commit  | Message |
|------|---------|---------|
| 1    | `a907d1b` | `refactor(19-04): fix _extract_usage_tokens docstring + dedupe G1 (D-07, D-15)` |
| 2    | `7122996` | `fix(19-04): qualify synth trace filenames per call site (D-12)` |
| 3    | `a5f0760` | `docs(19-04): add schema_version: 1 to cancellation.md JSON examples (D-14)` |

## Verification

Plan-close gate (success criterion): `uv sync && uv run pytest packages/eval-harness/tests/ packages/subagent-runtime/tests/ agents/graph-wiki-agent/tests/ -m "not integration"` — **389 passed, 23 skipped, 9 deselected** (skipped tests are gated behind `GRAPH_WIKI_RUN_INTEGRATION=1` / `GRAPH_WIKI_RUN_EVAL=1` env flags; not in scope for unit-only gate).

Grep verifications (done-criteria):

- `grep -n "trace_io" agents/.../query.py` → docstring at line 284 names `subagent_runtime.trace_io.write_trace_record`.
- `grep -c "_compute_unresolved_wikilinks" agents/.../query.py` → 3 (one definition, two calls: `run_query` + new call from `apply_guardrails`).
- `grep -n "synth_librarian_\|synth_codefallback_" agents/.../query.py` → both prefixes present (lines 534 + 964). No surviving `synth_{query_id}` literal.
- `grep -c '"schema_version": 1' docs/cancellation.md` → 2.

## D-07 Line-Range Verification

The plan said `write_trace_record:56-66`. Confirmed against current `packages/subagent-runtime/src/subagent_runtime/trace_io.py`:

- `write_trace_record` signature begins at line 29.
- Lines 56-66 contain the `usage_metadata` extraction block (`tokens_in`/`tokens_out` with the `None`-guard + `isinstance(dict)` defensive check) — the exact code that `_extract_usage_tokens` mirrors verbatim.

No drift; the 56-66 range cited in the docstring is accurate as of `a907d1b`.

## D-15 Behavior Equivalence

`apply_guardrails`'s old inline G1 algorithm and `_compute_unresolved_wikilinks` are byte-equivalent in resolution rules:

1. Extract wikilinks via `_extract_wikilinks(text)`.
2. Append `.md` if not already suffixed.
3. Direct path lookup at `vault_path / link_path`.
4. Fallback glob `**/<base>.md` (where `base = link.removesuffix(".md")`).
5. Append `link` (original form, NOT `link_path`) to `unresolved` if neither lookup matches.

Both implementations produce identical output on every input. All 8 `apply_guardrails` test cases pass unchanged (`agents/graph-wiki-agent/tests/unit/test_query_result.py:109-228`).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` exists and contains all three changes.
- `docs/cancellation.md` exists and contains 2 occurrences of `"schema_version": 1`.
- All three commits (`a907d1b`, `7122996`, `a5f0760`) present in `git log`.
- Plan-close gate (389 tests) passes.

## Follow-up

- 19-REVIEW-BURNDOWN.md rows for IN-01, IN-06, IN-08, IN-09 will be populated by plan 05 (commit SHAs: `a907d1b`, `7122996`, `a5f0760`, `a907d1b`).
