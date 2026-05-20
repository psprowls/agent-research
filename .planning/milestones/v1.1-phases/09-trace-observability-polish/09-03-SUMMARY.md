---
phase: 09-trace-observability-polish
plan: 03
subsystem: observability
tags: [trace, renderer, cost-rollup, cli, obs-05]

# Dependency graph
requires:
  - phase: 09-trace-observability-polish
    plan: 01
    provides: schema_version-stamped per-item trace records with cost_usd populated by Phase 4 pricing
  - phase: 04-eval-harness
    provides: cost_usd field populated by SubagentPool._compute_cost_usd at write time
provides:
  - per-(role, model_id) cost rollup section in `graph-wiki-agent trace <file>` Summary block
  - by_role_model breakdown structure on _aggregate_trace return value (dict keyed by "<role>|<model_id>")
  - test_aggregate_trace_by_role_model_groups_and_costs locks the aggregator shape
  - test_cost_rollup_format_six_decimals locks D-09 numerics and D-15 ordering in default-mode rendering
  - test_cost_rollup_snapshot (skipif-guarded on `--expand` support) ready to record once plan 09-04 ships
affects: [09-04, 09-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-(role, model_id) rollup keyed by 'role|model_id' string in _aggregate_trace return dict (simple-shape choice for JSON-serializability and rendering)"
    - "Renderer reads cost_usd as-written (D-10): no eval_harness import, even lazily"
    - "Snapshot tests guarded by skipif on subprocess `trace --help` probe so cross-plan flag dependencies self-skip cleanly"

key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
    - agents/graph-wiki-agent/tests/unit/test_trace_viewer.py

key-decisions:
  - "by_role_model shape: dict keyed by 'role|model_id' string with inner {role, model_id, count, tokens_in, tokens_out, cost_usd_sum, unknown_cost_count}. Chose the pipe-delimited string key (over tuple key or list-of-dicts) for trivial JSON serializability + straightforward iteration in the renderer."
  - "Test ordering assertion anchored on '$n/a' substring (unique to the librarian rollup line) rather than 'librarian' substring (which also appears in the Per-role breakdown section), preventing false matches."
  - "test_cost_rollup_snapshot intentionally NOT recorded in this plan — the `.ambr` file is expected to land with 09-04 when `--expand` ships. Test self-skips until then via subprocess `trace --help` probe."

patterns-established:
  - "Cost rollup pattern: separate 'known' vs 'fully-null' groups, sort known by descending cost (+role/model_id tie-break), sort unknown by role/model_id, concatenate with unknown last (D-15)."

requirements-completed: [OBS-05]

# Metrics
duration: ~12 min
completed: 2026-05-17
---

# Phase 9 Plan 3: Per-subagent cost rollup in trace Summary block

**Extended `_aggregate_trace` with a `(role, model_id)` cost breakdown and replaced the `Cost USD: (Phase 4)` placeholder with a real rollup section formatted per D-09 ($0.000000 with `(+K unknown)` / `$n/a` accounting) and sorted per D-15 (descending cost, alphabetical tie-break, fully-null groups last).**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-05-17
- **Tasks:** 2 (both TDD: RED → GREEN per task; no REFACTOR needed)
- **Files modified:** 2

## Accomplishments

- `_aggregate_trace` now returns `by_role_model`: `{"<role>|<model_id>": {role, model_id, count, tokens_in, tokens_out, cost_usd_sum, unknown_cost_count}}` alongside the existing `by_role` / totals (backward-compatible additive shape).
- Per-item discriminator (D-11) applied: records with an `event` or `kind` key are excluded from the rollup but continue to count toward the existing `by_role`/totals so the Summary block's "Total records" line stays byte-identical for non-rollup callers.
- `trace` command's Summary block now ends with a `Cost rollup (per role/model):` section. Lines render as `<role> / <model_short>: <count> items, <tin>->>tout> tokens, $<cost>` where `model_short` reuses the existing `model_id[-30:]` convention from `_render_trace_record`.
- `$0.000000` six-decimal format (D-09) via `f"${value:.6f}"`. Partial-null groups append ` (+K unknown)`; fully-null groups render `$n/a (K unknown)` and sort last (D-15).
- Sort policy (D-15) split into two passes — `known` (count > unknown_cost_count) sorted by `(-cost_usd_sum, role, model_id)`, then `unknown` (fully-null) sorted by `(role, model_id)`, concatenated `known + unknown`.
- `Cost USD: (Phase 4)` placeholder fully removed from `cli.py`.
- Dropped the `'Phase 4'` half of the legacy OR-assertion in `test_trace_command_prints_summary_block`. Verified `grep -r "Phase 4" agents/graph-wiki-agent/tests/` returns zero matches.
- Renderer has zero `eval_harness` imports — verified via `grep -E "from eval_harness|import eval_harness" agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (D-10).
- Per-item record lines emitted earlier in the timeline are byte-identical to the pre-Phase-9 output — `_render_trace_record` was not touched (D-08).

## Task Commits

Each task committed atomically with RED + GREEN split:

1. **Task 1 RED — failing test for by_role_model rollup** — `8c0f7d4` (test)
2. **Task 1 GREEN — extend _aggregate_trace with by_role_model + cost rollup** — `559a77a` (feat)
3. **Task 2 RED — failing tests for cost rollup formatting + 09-04 snapshot** — `d4ff585` (test)
4. **Task 2 GREEN — emit per-(role, model_id) cost rollup in trace Summary** — `13e106b` (feat)

## Files Created/Modified

- **`agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`** (modified)
  - `_aggregate_trace` extended: new `by_role_model: defaultdict` accumulator; D-11 discriminator skips records with `event` or `kind` keys; numeric guard via `float(cost)` on the non-null branch (T-09-06 — raises loudly on non-numeric inputs rather than silently mis-summing).
  - `trace` command: removed `typer.echo("Cost USD: (Phase 4)")` placeholder; appended `Cost rollup (per role/model):` section with sort-then-emit loop.
- **`agents/graph-wiki-agent/tests/unit/test_trace_viewer.py`** (modified)
  - Added `from syrupy.assertion import SnapshotAssertion` and `from functools import lru_cache` to imports.
  - Added `_HAIKU_MODEL` / `_SONNET_MODEL` / `_QWEN_MODEL` module constants for fixture readability.
  - Added `_write_cost_rollup_fixture(tmp_path)` mixed-(role, model_id) JSONL writer.
  - Added `test_aggregate_trace_by_role_model_groups_and_costs` (Task 1).
  - Added `test_cost_rollup_format_six_decimals` (Task 2, default-mode substring + ordering assertions).
  - Added `_trace_supports_expand_flag()` `lru_cache`-memoized subprocess probe + `test_cost_rollup_snapshot` skipif-guarded snapshot test (Task 2; self-skips until 09-04 ships `--expand`).
  - Dropped `'Phase 4'` half of the OR-assertion in `test_trace_command_prints_summary_block` — now asserts only `"cost" in stdout.lower()`.

## Decisions Made

- **`by_role_model` shape — pipe-delimited string key:** chosen for trivially-JSON-serializable shape (the test exercises tuple, pipe-string, and list-of-dicts shapes via a canonicalizer so future changes are not forced into one representation). The renderer iterates `.values()` directly so the key shape is opaque to the printer.
- **Numeric guard via `float(cost)`:** per T-09-06 in the plan's threat register, malformed records with non-numeric `cost_usd` will raise `TypeError` (or `ValueError`) at aggregation time rather than silently producing wrong sums. Production writers always emit `float` or `None`, so this is a noisy-fail-on-bad-input policy.
- **Snapshot `.ambr` deferred until 09-04:** the snapshot test would need a recorded `.ambr` file, but `--expand` does not yet exist as a flag (lands in plan 09-04). The skipif-guarded test stays in the suite and will start recording / asserting automatically once `--expand` ships. No `.ambr` file is created in this plan.
- **Test ordering assertion anchored on `$n/a`:** an earlier draft anchored on the bare `"librarian"` substring, which falsely matched the librarian's appearance in the Per-role breakdown section (printed BEFORE the rollup). Switched to `$n/a` which uniquely identifies the librarian's rollup line in this fixture.

## Deviations from Plan

None. The plan executed as written. Two micro-adjustments captured under Decisions:
1. The ordering assertion's substring anchor (`$n/a` vs `librarian`) — discovered during GREEN verification of Task 2; corrected before committing.
2. Used `functools.lru_cache(maxsize=1)` to memoize the subprocess `trace --help` probe so the skipif evaluation cost is paid at most once per test session.

## Issues Encountered

- **Subprocess probe imports `subprocess` already** — confirmed at the top of the test file (Path/json/subprocess all already imported).
- **`pytest.approx` for cost equality** — used in the Task-1 test because float sums (`0.0005 + 0.0010 = 0.0015`) can have tiny IEEE-754 drift; the existing test file did not need it before.

## User Setup Required

None — purely additive renderer extension. No env vars, no migrations, no schema changes (the `cost_usd` field has been populated by `SubagentPool._compute_cost_usd` since Phase 4).

## Next Phase Readiness

- **Plan 09-04 (consecutive-same-role collapsing + `--expand`):** the snapshot test in this plan is already in place and skipif-guarded. Once 09-04 lands `--expand`, running `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_trace_viewer.py::test_cost_rollup_snapshot --snapshot-update` will record the `.ambr` file. The chosen `--expand`-mode capture means the timeline is invariant to 09-04's default-collapse behavior.
- **Plan 09-05 (v0 backward-compat + schema_version-too-new warnings):** OBS-05 is now closed by this plan; OBS-04's renderer half remains for 09-05. The renderer's `record.get(..., "-")` / `record.get(...) or 0` defensive idiom is preserved, so unversioned fixtures continue to render through the rollup pass without raising.
- **ROADMAP success criterion 2 ("`graph-wiki-agent trace <file>` displays per-subagent cost ... for each fan-out call")** is satisfied — per-`(role, model_id)` cost is now rolled up from per-record `cost_usd`.

## Self-Check

**Files modified (verified):**

- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — FOUND (modified, status M before commits; staged + committed in 559a77a and 13e106b)
- `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` — FOUND (modified, status M before commits; staged + committed in 8c0f7d4, d4ff585, 13e106b)

**Commits (verified by hash in `git log --oneline`):**

- `8c0f7d4` — test(09-03): add failing test for by_role_model rollup in _aggregate_trace — FOUND
- `559a77a` — feat(09-03): extend _aggregate_trace with by_role_model + cost rollup — FOUND
- `d4ff585` — test(09-03): add failing tests for cost rollup formatting + 09-04 snapshot — FOUND
- `13e106b` — feat(09-03): emit per-(role, model_id) cost rollup in trace Summary — FOUND

**Plan-level verify-block invariants (all 5 checks):**

- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` — 7 passed, 1 skipped (test_cost_rollup_snapshot self-skipped per 09-04 dependency) — PASS
- `grep "Cost USD: (Phase 4)" agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — 0 hits — PASS
- `grep -r "Phase 4" agents/graph-wiki-agent/tests/` — 0 hits — PASS
- `grep -E "from eval_harness|import eval_harness" agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — 0 hits — PASS
- Full `agents/graph-wiki-agent/tests/unit/` suite: 144 passed, 1 skipped — PASS (no regressions)

## Self-Check: PASSED

---
*Phase: 09-trace-observability-polish*
*Completed: 2026-05-17*
