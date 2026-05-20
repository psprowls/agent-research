---
phase: 09-trace-observability-polish
plan: 05
subsystem: observability
tags: [trace, renderer, schema-version, backward-compat, obs-04]

# Dependency graph
requires:
  - phase: 09-trace-observability-polish
    plan: 01
    provides: schema_version=1 stamped on every record by all three producers
  - phase: 09-trace-observability-polish
    plan: 03
    provides: cost rollup in trace renderer
  - phase: 09-trace-observability-polish
    plan: 04
    provides: consecutive-same-role collapse + --expand flag
provides:
  - "KNOWN_SCHEMA_VERSION = 1 constant in cli.py defining the renderer's known max"
  - "One-shot per-file stderr warning for unversioned records (D-04 v0-inference)"
  - "One-shot per-file stderr warning for schema_version > KNOWN (D-03 lenient consumer)"
  - "Four named tests locking the behavior, one of which exercises the real v0 fixtures"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-file one-shot warning flag (warned_v0, warned_newer) before record append"
    - "Per-line semantics for one-shot test assertion (set of stderr line indices carrying any marker; len == 1)"
    - "Lenient-consumer policy: warnings never escalate to non-zero exit"

key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
    - agents/graph-wiki-agent/tests/unit/test_trace_viewer.py

key-decisions:
  - "v0 warning string (Claude's Discretion per 09-CONTEXT.md): 'warning: trace file <path> contains unversioned records; treating as schema_version=0 (pre-Phase-9 shape); rendering best-effort' — single line, mentions file path, contains all three markers (unversioned / schema_version=0 / pre-Phase-9) on one line so the one-shot test's per-line semantics is the only correct measure"
  - "Newer-version warning string (D-03 locked verbatim): 'warning: trace schema_version <N> is newer than supported (1); rendering best-effort'"
  - "Non-integer schema_version values are silently rendered best-effort (T-09-15 mitigation via isinstance(sv, int) guard)"
  - "Order of operations: warning emission happens BEFORE records.append(record) so the warning attaches to the offending record's parse but does not gate its inclusion in the timeline"

patterns-established:
  - "Per-line semantics for one-shot warning tests: the canonical measure of 'emitted once per file' is the count of DISTINCT stderr line indices carrying any of the agreed markers (set comprehension + len==1), NOT a substring .count() across the whole stream — robust against warning strings that bundle multiple markers per line"

requirements-completed: [OBS-04]

# Metrics
duration: ~10 min
completed: 2026-05-17
---

# Phase 9 Plan 5: schema_version-aware Renderer Warnings Summary

**Closed OBS-04's consumer half: the trace renderer now detects unversioned records (one-shot per-file v0 warning per D-04) and records with `schema_version` greater than the renderer's known max (one-shot per-file lenient-consumer warning per D-03), continues rendering in both cases, and is locked by four focused tests including one that exercises the real unversioned fixtures under `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/`.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-05-17
- **Tasks:** 2 (single TDD cycle: RED → GREEN; both tasks landed together because Task 1's `<verify>` block depends on Task 2's tests)
- **Files modified:** 2 (1 production code + 1 test file)
- **Files created:** 0
- **Tests added:** 4 (all passing)
- **Total tests in test_trace_viewer.py:** 20 (all passing, no regression)

## Accomplishments

- `cli.py` carries a module-level `KNOWN_SCHEMA_VERSION = 1` constant (added at line 32)
- The `trace` command tracks two per-file booleans (`warned_v0`, `warned_newer`) initialized False per invocation
- The renderer emits the v0 warning exactly once per file when ANY record lacks `schema_version`; subsequent unversioned records in the same file do NOT re-emit
- The renderer emits the D-03 newer-version warning exactly once per file when ANY record has `schema_version > KNOWN_SCHEMA_VERSION`
- Both warnings go to stderr (`err=True`); stdout still receives the full timeline + Summary block
- Exit code stays 0 in both warning paths (lenient consumer)
- Non-integer `schema_version` values are silently rendered best-effort (T-09-15 mitigation)
- Renderer has zero `eval_harness` imports (D-10 invariant preserved)
- The real fixtures under `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/` render successfully with exactly one v0 warning each — fixtures themselves are NOT rewritten

## Plan-Required Artifacts

- **Chosen v0 warning string (verbatim):**
  ```
  warning: trace file <path> contains unversioned records; treating as schema_version=0 (pre-Phase-9 shape); rendering best-effort
  ```
  (Single line; mentions the file path per D-04; intentionally contains all three markers — `unversioned`, `schema_version=0`, `pre-Phase-9` — on the same line, which is why the one-shot test must use per-line semantics rather than substring count.)

- **Exact location of `KNOWN_SCHEMA_VERSION`:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` **line 32** (module-level, immediately after the `Typer` app construction so the constant lives alongside other top-level renderer state).

- **Test names added:**
  - `test_v0_real_fixture_renders_and_warns_once`
  - `test_newer_version_warns_lenient`
  - `test_versioned_clean_emits_no_version_warning`
  - `test_v0_warning_emitted_once_per_file`

- **Path of the real v0 fixture used in `test_v0_real_fixture_renders_and_warns_once`:** `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/1779049934_249e599f.jsonl` (the first entry of `sorted(_REAL_V0_FIXTURE_DIR.glob("*.jsonl"))` — the test resolves it dynamically so a new fixture landing earlier in lexicographic order would be picked up automatically; selection is deterministic for a given fixture set).

## Task Commits

Each task was committed atomically; the pair forms a single TDD cycle:

1. **Task 2 (RED): add failing schema_version warning tests** — `2c738ef` (test) — adds four new tests; three fail as expected (no warning emission yet), one passes trivially (clean v1 case)
2. **Task 1 (GREEN): emit schema_version-aware warnings in trace renderer** — `ca4083c` (feat) — adds `KNOWN_SCHEMA_VERSION = 1`, per-file warning emission with one-shot flags, both stderr warnings; all four tests now pass

## Files Modified

- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — added module-level `KNOWN_SCHEMA_VERSION = 1` at line 32; extended the `trace` command's parse-and-collect loop with `warned_v0` and `warned_newer` per-file booleans plus the two D-03/D-04 warning branches (lines 244-273). Total addition: 34 lines.
- `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` — added `_REAL_V0_FIXTURE_DIR` path helper resolving to the workspace's real v0 fixtures (via `Path(__file__).resolve().parents[4]`), two new inline fixture factories (`_write_newer_version_fixture`, `_write_unversioned_inline_fixture`), and four new tests. Total addition: 205 lines.

## Decisions Made

- **v0 warning wording (Claude's Discretion per 09-CONTEXT.md):** included all three markers (`unversioned`, `schema_version=0`, `pre-Phase-9`) on a single line so each marker stays meaningful to grep'ers approaching the file with different mental models (Phase 9 newcomers will look for `schema_version`; renderer maintainers will look for `pre-Phase-9`; lattice-wiki users will look for `unversioned`). This choice forces the one-shot test to use per-line semantics, which is the more robust assertion shape anyway (and explicitly called out in the plan as the required measure).
- **Task ordering vs. plan layout:** the plan splits Task 1 (impl) from Task 2 (tests), but Task 1's `<verify>` block runs `pytest test_trace_viewer.py -x` — which only succeeds after Task 2's tests exist AND Task 1's impl satisfies them. The cleanest TDD-compliant interpretation was tests-first (RED commit, matching Task 2's spec) → impl (GREEN commit, matching Task 1's spec). Both tasks' `<done>` criteria are satisfied by the pair.
- **Path resolution `parents[4]`:** matches the existing `_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent` pattern already in this test file (five parents). `parents[4]` is the same depth in the cleaner `resolve().parents[N]` form.

## Deviations from Plan

None. Plan executed exactly as written.

## Issues Encountered

- First attempt at `_REAL_V0_FIXTURE_DIR` used `parents[3]` and resolved into `agents/cores/...`. Caught immediately by the first test failure (`No real v0 fixtures found at ...`). Fixed to `parents[4]` before any test passed. This was a pre-impl path-resolution mistake in the RED commit, fixed in the same RED commit before staging — no follow-up commit needed because the RED test still failed for the intended reason (no warning emission) after the path was corrected.

## User Setup Required

None — purely additive in-process change. No environment variables, dashboards, or external services.

## Phase Readiness

- **OBS-04 fully closed.** Producer half landed in 09-01 (`schema_version: 1` stamping); consumer half landed in this plan (lenient-consumer warnings for unversioned and newer-than-known records).
- The "lenient consumer, strict producer" policy documented in `docs/trace-schema.md` (written in 09-02) is now backed by code on both halves.
- This is the final plan in Phase 9. Phase 9's three OBS requirements (OBS-04 schema versioning, OBS-05 cost rollup, OBS-06 group collapse) are all complete and locked by tests.

## Self-Check

**Files modified (verified):**
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — FOUND (`grep -q "KNOWN_SCHEMA_VERSION = 1"` succeeds; `grep -q "is newer than supported"` succeeds; `grep -q "rendering best-effort"` succeeds; zero `eval_harness` imports)
- `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` — FOUND (`grep -c "schema_version"` >= 1; four new test functions defined)

**Commits (verified by hash in `git log --oneline`):**
- `2c738ef` — test(09-05): add failing schema_version warning tests (RED) — FOUND
- `ca4083c` — feat(09-05): emit schema_version-aware warnings in trace renderer (GREEN) — FOUND

**Tests (verified by `pytest`):**
- `test_v0_real_fixture_renders_and_warns_once` — PASSED
- `test_newer_version_warns_lenient` — PASSED
- `test_versioned_clean_emits_no_version_warning` — PASSED
- `test_v0_warning_emitted_once_per_file` — PASSED
- Full `test_trace_viewer.py` suite: 20 / 20 PASSED (no regression in plans 09-03 / 09-04 tests)

## Self-Check: PASSED

---
*Phase: 09-trace-observability-polish*
*Plan: 05 (final plan)*
*Completed: 2026-05-17*
