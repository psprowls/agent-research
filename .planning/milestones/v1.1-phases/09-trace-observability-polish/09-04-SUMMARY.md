---
phase: 09-trace-observability-polish
plan: 04
subsystem: observability
tags: [trace, renderer, collapse, expand, cli, obs-06]

# Dependency graph
requires:
  - phase: 09-trace-observability-polish
    plan: 03
    provides: per-(role, model_id) cost rollup section + skipif-guarded test_cost_rollup_snapshot ready to record once --expand ships
provides:
  - --expand boolean flag on `graph-wiki-agent trace` (Typer Option)
  - consecutive-same-role group collapsing in default mode (D-11/D-12/D-13)
  - _render_collapsed_group helper function for dense one-line summaries
  - _is_groupable predicate excluding records with event/kind keys
  - five new snapshot/regression tests in test_trace_viewer.py (collapsed_default, expand, mixed_status, query_summary_interleaved, isolated_record)
  - recorded .ambr baselines for collapsed_default, expand, mixed_status, query_summary_interleaved, AND the previously-skipif'd cost_rollup snapshot
affects: [09-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Renderer two-mode emission: parse JSON records once, then walk twice (parse-then-emit) so default-mode group detection can look ahead a single record without re-reading the file"
    - "Sliding-window group accumulator with explicit _flush helper — emits one collapsed line per run of >=2 same-role groupable records; flushes on role change or non-groupable record; falls back to _render_trace_record for runs of length 1"
    - "Collapsed-line cost formatting follows D-13 / D-09: $0.000000 six-decimal sum, (+K unknown) suffix when some null, $n/a (N unknown) when ALL null"
    - "Status breakdown emits only nonzero categories in canonical order success → error → cancelled (zero categories silently omitted, never '0 cancelled')"

key-files:
  created:
    - agents/graph-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
    - agents/graph-wiki-agent/tests/unit/test_trace_viewer.py

key-decisions:
  - "Implemented as a top-level helper `_render_collapsed_group(records)` plus a one-line predicate `_is_groupable(record)`, NOT as an inline branch — the helper is reused conceptually by the `_flush` closure inside `trace` and reads as a single-responsibility unit; PATTERNS.md gave explicit permission for either choice."
  - "Two pre-existing tests updated to pass `--expand` (test_trace_command_renders_per_record_lines, test_trace_command_skips_malformed_lines) because their fixtures are 2 consecutive same-role records which now collapse by default. Updating those tests preserves their original per-item assertion semantics under the new default behavior — Rule 3 fix (blocking issue caused by current task's changes)."
  - "Recorded the 09-03 `test_cost_rollup_snapshot` baseline at the same time as the four new Task-2 snapshots — that test was waiting on `--expand` to ship and self-skipped until then; once Task 1 added the flag the test unskipped automatically and needed a baseline."

patterns-established:
  - "Default-mode timeline emission pattern: parse all records into a list, then walk once with a sliding window; flush emits collapsed-or-fallback; non-groupable records flush + render full-line"
  - "Snapshot tests for CLI subprocess output: use `assert result.stdout == snapshot` with syrupy SnapshotAssertion; `.ambr` files auto-land in tests/unit/__snapshots__/"

requirements-completed: [OBS-06]

# Metrics
duration: ~20 min
completed: 2026-05-17
---

# Phase 9 Plan 4: --expand flag + consecutive-same-role group collapsing

**Added the `--expand` Typer flag and default-mode consecutive-same-role group collapsing to `graph-wiki-agent trace`. A run of ≥2 groupable per-item records now renders as one dense summary line `[ts_first .. ts_last] <role> x<N>: <breakdown>, <tin>-><tout> tokens, $<cost>`; `--expand` reverts to one full line per record. Records with `event` or `kind` keys always render full-line and break runs (D-11). Five new snapshot tests + four recorded `.ambr` baselines lock the four key shapes; the 09-03 skipif-guarded cost-rollup snapshot was unskipped and recorded.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-05-17
- **Tasks:** 2 (both TDD: RED → GREEN per task; no REFACTOR needed)
- **Files modified:** 2 source/test files + 1 new snapshot file

## Accomplishments

### `--expand` flag wired (Task 1)

- `trace` command gains `expand: bool = typer.Option(False, "--expand", help="Disable consecutive-same-role collapsing; render every record full-line.")` as the second parameter.
- `graph-wiki-agent trace --help` now lists `--expand` (verified by `test_trace_command_has_expand_flag`).
- `--expand` is a single boolean flag with no per-role / per-threshold variants — matches D-14.

### Group detection + collapsed-line emission (Task 1)

- New helper `_render_collapsed_group(records: list[dict]) -> str` produces the D-13 line shape:
  - `ts_first / ts_last` = literal `timestamp` field of the first / last record (ISO-8601 as written).
  - Status breakdown = comma-separated, canonical order (success → error → cancelled), zero categories OMITTED (never `0 cancelled`).
  - Token sums use `or 0` defensive defaults (None-safe).
  - Cost: `$<sum:.6f>` six-decimal; `(+<K> unknown)` suffix when some records have null `cost_usd`; `$n/a (<N> unknown)` when ALL records are null.
- New predicate `_is_groupable(record)` returns False if the record carries an `event` or `kind` key (D-11).
- Per-record emission moved OUT of the JSON-parsing loop. After parsing into `records: list[dict]`, the renderer walks the list once with a sliding-window accumulator `current_run`, calling `_flush()` on role change, non-groupable record, or end-of-stream. `_flush` emits the collapsed-group line when `len(current_run) >= 2`, else falls back to `_render_trace_record(current_run[0])`.
- `_render_trace_record` itself is untouched (D-08 invariant preserved).
- Cost rollup Summary block from plan 09-03 prints unchanged in BOTH `--expand` and default mode (Claude's Discretion parity choice from 09-CONTEXT.md).
- Renderer still has zero `eval_harness` imports — verified by `grep -E "from eval_harness|import eval_harness" agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` returning 0 (D-10 invariant).

### Five new tests + four recorded snapshots (Task 2)

Snapshot tests (all use syrupy `SnapshotAssertion`, `.ambr` keys recorded):

| Test | `.ambr` key | What it locks |
|------|-------------|---------------|
| `test_collapsed_default_snapshot` | `test_collapsed_default_snapshot` | Default-mode 4-record same-role fan-out → ONE `scanner x4: 4 success, 40->20 tokens, $0.000400` line + Summary block. No per-item lines. |
| `test_expand_snapshot` | `test_expand_snapshot` | Same 4-record fixture with `--expand` → FOUR per-item full lines + Summary block. No `x4:` collapse marker. |
| `test_mixed_status_in_run_snapshot` | `test_mixed_status_in_run_snapshot` | 4 same-role records with statuses (success, success, error, cancelled) → `scanner x4: 2 success / 1 error / 1 cancelled, 27->11 tokens, $0.000400 (+1 unknown)`. Cancelled record's null cost drives the `(+1 unknown)` suffix. |
| `test_query_summary_interleaved_breaks_group_snapshot` | `test_query_summary_interleaved_breaks_group_snapshot` | 3 scanner → `kind: query_summary` → 2 scanner → `event: batch_cancelled` → `scanner x3:` collapsed, query_summary full-line (via `_render_trace_record` fallback), `scanner x2:` collapsed, batch_cancelled full-line. Both `kind` and `event` break runs (D-11). |

Non-snapshot regression test:

- `test_isolated_record_renders_full_line` — two records of different roles each form a run of length 1; both render full-line, no `x1:` marker appears anywhere. Locks D-12's "isolated single records still render full-line by default."

Recorded as a bonus side effect:

- `test_cost_rollup_snapshot` (the 09-03 test that self-skipped on `_trace_supports_expand_flag()`) unskipped the moment Task 1 shipped `--expand`. Its `.ambr` baseline was recorded alongside the four new Task-2 snapshots and demonstrates D-15 ordering: sonnet ($0.002000) before haiku ($0.001500 +1 unknown) before librarian ($n/a, last).

### Implementation choice — `_render_collapsed_group` helper, not inline

The renderer uses a top-level `_render_collapsed_group(records: list[dict]) -> str` function (single-responsibility, returns the formatted string) called from the `_flush` closure inside `trace`. PATTERNS.md explicitly permitted either an inline branch or a helper; the helper option produces the smaller per-call diff at the call site and a clean unit-testable name. The plan called this out under `<output>` — confirming the choice.

## Task Commits

Each task committed atomically with RED + GREEN split:

1. **Task 1 RED — failing tests for --expand + collapse** — `e45ac6d` (test)
2. **Task 1 GREEN — wire --expand + group collapsing + update 2 pre-existing tests** — `24e68a4` (feat)
3. **Task 2 RED — snapshot tests + interleaved/mixed-status/isolated fixtures** — `077f3e9` (test)
4. **Task 2 GREEN — record .ambr baselines** — `066321f` (test)

## Files Created/Modified

- **`agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`** (modified)
  - Added `_render_collapsed_group(records)` helper for the D-13 collapsed-line shape.
  - Added `_is_groupable(record)` predicate (returns False for records with `event` or `kind` keys per D-11).
  - `trace` command signature: added `expand: bool = typer.Option(False, "--expand", ...)`.
  - Refactored emission loop: parse all records first, then walk records once with sliding-window group detection (default mode) OR one full line per record (`--expand` mode). `_flush` closure emits the collapsed line or falls back to `_render_trace_record`.
  - Summary block + cost rollup still print in BOTH modes.

- **`agents/graph-wiki-agent/tests/unit/test_trace_viewer.py`** (modified)
  - Updated two pre-existing tests to pass `--expand`: `test_trace_command_renders_per_record_lines`, `test_trace_command_skips_malformed_lines` (their 2-record fixtures now collapse by default, so per-item assertions require the expand mode).
  - Added Task 1 tests: `test_trace_command_has_expand_flag`, `test_default_mode_collapses_consecutive_same_role`, `test_expand_mode_renders_every_record_full_line`, plus `_write_fan_out_fixture` helper.
  - Added Task 2 fixtures: `_write_mixed_status_fixture`, `_write_interleaved_fixture`, `_write_two_roles_fixture`.
  - Added Task 2 tests: `test_collapsed_default_snapshot`, `test_expand_snapshot`, `test_mixed_status_in_run_snapshot`, `test_query_summary_interleaved_breaks_group_snapshot`, `test_isolated_record_renders_full_line`.

- **`agents/graph-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr`** (created)
  - Five recorded snapshots: `test_collapsed_default_snapshot`, `test_cost_rollup_snapshot` (unskipped from 09-03), `test_expand_snapshot`, `test_mixed_status_in_run_snapshot`, `test_query_summary_interleaved_breaks_group_snapshot`.

## Decisions Made

- **Helper vs inline:** chose `_render_collapsed_group` top-level helper over an inline branch — the helper is single-responsibility, easily unit-testable, and the call site stays short. PATTERNS.md gave explicit permission.
- **Updating pre-existing tests instead of adding parallel ones:** two pre-09-04 tests (`test_trace_command_renders_per_record_lines`, `test_trace_command_skips_malformed_lines`) assert on per-item substrings (`scanner` per line, `page-good-a`/`page-good-b` in stdout). Their fixtures use 2 consecutive same-role records, which now collapse to one line in default mode. Rather than fork into expand+default variants, I added `--expand` to the existing test invocations — their original intent (verify per-item rendering + verify error handling continues mid-stream) is preserved under expand mode. The new collapse-mode coverage is fully provided by the four Task-2 snapshot tests.
- **Snapshot for the interleaved fixture honestly captures `_render_trace_record`'s generic fallback** for the query_summary and batch_cancelled records: those records render as e.g. `[-] - - - - -ms -->-` (most fields missing per `record.get(..., "-")`) and `[2026-05-17T10:00:07Z] scanner claude-haiku-4-5-20251001-v1:0 - - -ms -->-`. D-08 prohibits touching `_render_trace_record` in this plan; the snapshot locks the current behavior. If a future plan wants prettier non-groupable rendering, it can extend `_render_trace_record` and re-record this snapshot. 09-CONTEXT.md's "Claude's Discretion" list specifically called this out as a planner choice; this plan did NOT add a custom renderer (kept the diff minimal).

## Deviations from Plan

None substantive. The plan executed as written. Two micro-adjustments captured under Decisions:

1. **Helper vs inline** — chose helper (planner gave both options).
2. **Two pre-existing tests updated to use `--expand`** — Rule 3 auto-fix: my changes caused them to break (their fixtures now collapse by default); the smallest correct fix preserves their original per-item assertion semantics by passing `--expand`.

## Issues Encountered

- **`test_cost_rollup_snapshot` unskipped immediately** when `--expand` shipped — expected and documented in plan 09-03's SUMMARY. Recorded its baseline alongside the four new Task-2 snapshots in the same `pytest --snapshot-update` run.
- **`grep "scanner x4:"` count = 2** — confirms the collapsed_default snapshot has it, and the expand snapshot doesn't (as expected). The second match comes from the fact that the test_trace_viewer.ambr also keeps the `x4` token in non-collapse contexts; the plan's verify-block check `awk '{exit ($1>=2)?0:1}'` passes (2 >= 2).

## User Setup Required

None — purely additive renderer extension. No env vars, no migrations, no schema changes. Existing `graph-wiki-agent trace <file>` invocations get the new collapsed output by default; users who want the pre-Phase-9 behavior pass `--expand`.

## Next Phase Readiness

- **Plan 09-05 (v0 backward-compat + schema_version-too-new warnings):** OBS-06 is now closed by this plan; OBS-04's renderer half remains for 09-05. The renderer's `record.get(..., "-")` / `record.get(...) or 0` defensive idiom is preserved through both the new group-detection pass AND `_render_collapsed_group`, so unversioned fixtures (no `schema_version` field) continue to render through collapse/expand without raising.
- **ROADMAP success criterion 3** ("`graph-wiki-agent trace <file>` collapses repeated subagent-role groups into a summary line by default; `--expand` drills into the full event stream") is satisfied:
  - Default mode collapses runs of ≥2 same-role groupable records (D-12 threshold).
  - `--expand` reverts to the pre-Phase-9 one-line-per-record behavior.
  - `kind: query_summary` and `event: batch_cancelled` always render full-line (D-11) and break runs.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The plan's `<threat_model>` covered T-09-09/10/11 (renderer-side DoS / control-chars / `--expand` exposure); all dispositions held without code changes — implementation is O(N) with sliding window, `role` originates from internal config, and `--expand` exposes no new error surface beyond today's renderer.

## Self-Check

**Files verified:**

- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — FOUND (modified, staged + committed in `24e68a4`)
- `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` — FOUND (modified, staged + committed in `e45ac6d`, `24e68a4`, `077f3e9`)
- `agents/graph-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr` — FOUND (created in `24e68a4`, snapshots recorded in `066321f`)

**Commits verified by `git log --oneline -5`:**

- `e45ac6d` — test(09-04): add failing tests for --expand flag + consecutive-same-role collapse — FOUND
- `24e68a4` — feat(09-04): add --expand flag + consecutive-same-role group collapsing to trace renderer — FOUND
- `077f3e9` — test(09-04): add snapshot tests + fixtures for collapse, expand, mixed-status, interleave, isolated — FOUND
- `066321f` — test(09-04): record snapshot baselines for collapse, expand, mixed-status, interleave — FOUND

**Plan-level verify-block invariants (all 4 checks for Task 1 + 4 checks for Task 2):**

- Task 1: `graph-wiki-agent trace --help` lists `--expand` — PASS
- Task 1: `--expand` substring present in `cli.py` — PASS
- Task 1: zero `eval_harness` imports in `cli.py` — PASS
- Task 1: `pytest agents/graph-wiki-agent/tests/unit/test_trace_viewer.py -x` — PASS (11 → 16 passed, 0 failed)
- Task 2: keyword-filtered new tests pass — PASS (5 passed: collapsed_default, expand, mixed_status, interleaved, isolated)
- Task 2: `grep -c "scanner x4:" .ambr | awk '$1>=2'` — PASS (count = 2)
- Task 2: `grep "2 success / 1 error / 1 cancelled" .ambr` — PASS
- Task 2: `grep "scanner x3:"` AND `grep "scanner x2:"` both present — PASS

**Full unit suite (regression):** 153 passed, 0 failed, 0 skipped — PASS.

## Self-Check: PASSED

---
*Phase: 09-trace-observability-polish*
*Completed: 2026-05-17*
