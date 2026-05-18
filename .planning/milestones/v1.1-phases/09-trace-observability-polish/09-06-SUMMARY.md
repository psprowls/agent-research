---
phase: 09-trace-observability-polish
plan: 06
subsystem: trace-renderer
tags:
  - gap-closure
  - renderer
  - trace
  - cli
requires:
  - 09-05
provides:
  - "CR-01 fix — timeline collapse keys by (role, model_id) with model surfaced in header"
  - "WR-02 fix — by_role aggregator excludes event/kind discriminator records"
  - "WR-03 fix — collapsed-group breakdown surfaces non-canonical statuses under `other` bucket; `0 success` fallback removed"
affects:
  - agents/code-wiki-agent/src/code_wiki_agent/cli.py
  - agents/code-wiki-agent/tests/unit/test_trace_viewer.py
  - agents/code-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr
tech-stack:
  added: []
  patterns:
    - "Single forward-declared filter `_is_groupable(record)` reused in both the by_role pass and the collapse-loop guard, unifying event/kind exclusion (D-11)."
    - "Tuple-key collapse extend-or-flush mirrors cost-rollup grouping at cli.py:329-345, preserving model attribution end-to-end (CR-01)."
    - "Closed-set + `other` bucket pattern for additive-shape resilience (docs/trace-schema.md §4) — new producer statuses surface loudly rather than silently dropping."
key-files:
  created: []
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py
    - agents/code-wiki-agent/tests/unit/test_trace_viewer.py
    - agents/code-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr
decisions:
  - "Header format: `[ts_first .. ts_last] {role} / {model_short} x{N}: {breakdown}, {tin}->{tout} tokens, {cost}` — mirrors the cost-rollup `/` separator at cli.py:362 for visual consistency."
  - "model_short = model_id[-30:] (same 30-char suffix as the cost rollup) — bounds header length and re-uses an already-proven convention from Phase 9 plan 09-03."
  - "by_role pass uses an early `if not _is_groupable(record): continue` after total-tokens accumulation, so event/kind records are excluded from BOTH by_role AND by_role_model under one filter; total_records and total_tokens_in/out preserve the file-level invariant of counting every parsed record."
  - "WR-03 breakdown fallback `f\"{n} unknown\"` is unreachable in practice once the `other` bucket exists — kept as a defensive guard against malformed N=0 input rather than removed."
metrics:
  duration: "~25 minutes"
  completed: 2026-05-17
  tasks: 3
  commits: 3
  files_modified: 3
---

# Phase 9 Plan 6: Gap closure for CR-01 + WR-02 + WR-03 Summary

Tightened the trace renderer on three advisory gaps surfaced by `09-VERIFICATION.md` (status: gaps_found): collapsed-group lines now preserve model attribution end-to-end, the per-role breakdown no longer synthesizes a phantom `unknown` bucket from `kind: query_summary` records, and the collapsed-group status breakdown handles future producer-added statuses correctly instead of silently mis-reporting `0 success` for an N-record group.

## Tasks Completed

| # | Task | Commit | Files |
| - | ---- | ------ | ----- |
| 1 | CR-01 — collapse by (role, model_id), surface model in collapsed-group header | `07f3b27` | `cli.py`, `test_trace_viewer.py` |
| 2 | WR-02 + WR-03 — gate by_role via `_is_groupable`; add `other` bucket; replace `0 success` fallback | `fbbd343` | `cli.py`, `test_trace_viewer.py` |
| 3 | Single-pass snapshot regeneration; full-suite green check | `a5f4a5b` | `__snapshots__/test_trace_viewer.ambr`, `test_trace_viewer.py` |

## Chosen Collapsed-Group Header Format

Verbatim from `cli.py:233-235`:

```python
return (
    f"[{ts_first} .. {ts_last}] {role} / {model_short} x{n}: {breakdown}, "
    f"{sum_tin}->{sum_tout} tokens, {cost_str}"
)
```

`model_short = model_id[-30:]` when `model_id` is set, else `"-"` (mirrors the cost-rollup convention at `cli.py:362`).

Concrete example from the re-recorded `test_collapsed_default_snapshot`:

```
[2026-05-17T10:00:00Z .. 2026-05-17T10:00:03Z] scanner / claude-haiku-4-5-20251001-v1:0 x4: 4 success, 40->20 tokens, $0.000400
```

## Exact Line Locations of the Three Fixes

| Gap | Where the fix lives | Mechanism |
| --- | ------------------- | --------- |
| CR-01 (collapse key) | `cli.py:328-334` (collapse extend-or-flush guard) | Tuple comparison `current_run[-1].get("role") == record.get("role") and current_run[-1].get("model_id") == record.get("model_id")` |
| CR-01 (header) | `cli.py:182-184` (model_id read), `cli.py:233-235` (return f-string) | `model_id = records[0].get("model_id", "-")`; `model_short = model_id[-30:] if model_id and model_id != "-" else "-"`; header includes `/ {model_short}` |
| WR-02 (by_role filter) | `cli.py:124-138` (`_aggregate_trace` early-continue) | `if not _is_groupable(record): continue` immediately after total-token accumulation, before both by_role and by_role_model writes |
| WR-03 (other bucket) | `cli.py:191-212` (counts dict + breakdown) | Closed-set match on `("success", "error", "cancelled")` with `else: counts["other"] += 1`; canonical iteration order `("success", "error", "cancelled", "other")`; fallback `f"{n} unknown"` replaces literal `"0 success"` |

## Regression Tests Added

| Test | Pins | Assertion strategy |
| ---- | ---- | ------------------ |
| `test_mixed_model_same_role_breaks_collapse` | CR-01 | Two consecutive `role: scanner` records with `model_id: HAIKU` and `model_id: SONNET` respectively. Splits stdout at `=== Summary ===` to isolate the timeline; asserts `"haiku-4-5" in timeline`, `"sonnet-4-5" in timeline`, AND `haiku_lines != sonnet_lines` (substring match on each model id lands on DISTINCT timeline lines). |
| `test_aggregate_excludes_event_kind_from_by_role` | WR-02 | Two records: one per-item `scanner` record + one `kind: query_summary` record. Slices `stdout.split("Per-role breakdown:")[1].split("Cost rollup")[0]` to isolate the per-role section; asserts `"scanner:" in per_role_section` (legitimate bucket present) and `"unknown:" not in per_role_section` (phantom bucket gone). |
| `test_collapsed_group_surfaces_unknown_status_in_other_bucket` | WR-03 | Three same-(role, model_id) records all carrying `status: "timeout"`. Splits at `=== Summary ===` to isolate the timeline; asserts `"x3" in timeline` (collapse occurred), `"3 other" in timeline` (other-bucket surfaced), and `"0 success" not in timeline` (misleading fallback gone). |

## Snapshots Regenerated

Single `pytest --snapshot-update` pass against `agents/code-wiki-agent/tests/unit/test_trace_viewer.py`. `git diff` showed:

| Snapshot | Change | Why |
| -------- | ------ | --- |
| `test_collapsed_default_snapshot` | Header gained `/ claude-haiku-4-5-20251001-v1:0` | CR-01 model_short insertion |
| `test_mixed_status_in_run_snapshot` | Header gained `/ claude-haiku-4-5-20251001-v1:0` | CR-01 model_short insertion |
| `test_query_summary_interleaved_breaks_group_snapshot` | Both collapsed-group headers gained `/ claude-haiku-4-5-20251001-v1:0` AND the phantom `unknown: count=1 tokens_in=0 tokens_out=0` line is removed from Per-role breakdown AND `scanner: count=6` → `scanner: count=5` (because the `event: batch_cancelled` record — which carries `role: scanner` — is now excluded from by_role under the unified `_is_groupable` filter) | CR-01 + WR-02 fixes |

Confirmed via `grep -c "unknown: count=1 tokens_in=0 tokens_out=0" test_trace_viewer.ambr` → `0`.

Unchanged snapshots (verified via `git diff --stat`): `test_cost_rollup_snapshot` and `test_expand_snapshot`. No numeric drift in any snapshot's token sums, cost sums, counts, or Summary totals.

## Inline-Assertion Adjustments

Two inline-asserted tests had substring anchors that the new `/ <model_short>` segment split:

- `test_default_mode_collapses_consecutive_same_role`: `assert "scanner x4:" in stdout` → reworked to match `scanner` AND `x4:` on the same timeline line (filters timeline lines by both substrings).
- `test_expand_mode_renders_every_record_full_line`: `assert "scanner x4:" not in stdout` → tightened to `assert "x4:" not in stdout` (the `xN:` token is unique to collapsed-group headers and never appears in `--expand` per-record lines).

Both adjustments preserve the original test intent.

## Scope Discipline

Per the planning_context "out of scope" list:

- WR-01 (bool-as-int coercion) — UNTOUCHED
- WR-04 (missing-timestamp dash fallback) — UNTOUCHED
- IN-01 (bare ValueError on float(cost) for bad input) — UNTOUCHED
- IN-04 (docs/cancellation.md schema_version in inline examples) — UNTOUCHED

Confirmed via `git diff 0ffb900..HEAD --stat`: only `agents/code-wiki-agent/{src/code_wiki_agent/cli.py, tests/unit/test_trace_viewer.py, tests/unit/__snapshots__/test_trace_viewer.ambr}` changed. No producer code (`cores/subagent-runtime/src/subagent_runtime/pool.py`, `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`) was touched, no schema docs (`docs/trace-schema.md`, `docs/cancellation.md`) modified, and the cost rollup section of `cli.py` (lines 366-401) is byte-identical to before this plan.

## Deviations from Plan

None — plan executed exactly as written. The one micro-deviation worth noting: the original Task 2 comment in `cli.py:200-205` originally contained the literal substring `0 success` while describing the behavior change. The plan's verify-step `grep -c "0 success" cli.py | awk '{exit ($1==0)?0:1}'` would have failed on that comment line, so the comment was reworded to use "zero-success fallback" instead — preserves meaning, satisfies the literal-absence verification. Same commit (`fbbd343`); no scope expansion.

## Verification Summary

All plan-level `<verify>` and `<verification>` checks pass:

- `grep -n "model_id" cli.py | grep -E "_render_collapsed_group|model_short"` — 4 hits (function body, docstring, return statement, `model_short` assignment).
- `grep -q 'current_run\[-1\].get("model_id") == record.get("model_id")' cli.py` — passes.
- `grep -q 'counts\["other"\]' cli.py` — passes.
- `grep -q "n} unknown" cli.py` — passes.
- `grep -c "0 success" cli.py` — `0`.
- `grep -c "unknown: count=1 tokens_in=0 tokens_out=0" test_trace_viewer.ambr` — `0`.
- `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/test_trace_viewer.py` — 23 passed, 5 snapshots passed, exit 0 (WITHOUT `--snapshot-update`).
- `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit` — 160 passed, exit 0 (no upstream regression).
- D-10 invariant (renderer free of `eval_harness` imports) preserved — no new imports added.

## Self-Check: PASSED

- All three commits exist in `git log`: `07f3b27`, `fbbd343`, `a5f4a5b` — VERIFIED via `git log --oneline -5`.
- All three modified files exist on disk: `cli.py`, `test_trace_viewer.py`, `test_trace_viewer.ambr` — VERIFIED via `git status --short` (clean) and `git ls-files`.
- Phantom `unknown: count=1` line absence VERIFIED via `grep -c`.
- Full unit-test suite green VERIFIED via final `pytest agents/code-wiki-agent/tests/unit` run (160 passed).
