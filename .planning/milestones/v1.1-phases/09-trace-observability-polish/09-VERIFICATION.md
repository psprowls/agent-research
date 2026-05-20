---
phase: 09-trace-observability-polish
verified: 2026-05-17T00:00:00Z
status: verified
score: 3/3 roadmap truths verified
overrides_applied: 0
re_verification: true
re_verification_note: "Re-verified after plan 09-06 closed all three advisory gaps (CR-01, WR-02, WR-03). Closure commits: 07f3b27 (CR-01), fbbd343 (WR-02 + WR-03), a5f4a5b (single-pass snapshot regen). Initial verification: 09-VERIFICATION.md @ f72b149."
previous_status: gaps_found
previous_score: 3/3 with caveats
gaps_closed:
  - "CR-01 — collapsed-group timeline now keys by (role, model_id) and surfaces model_short in header (cli.py:233-235, 327-331; regression test test_mixed_model_same_role_breaks_collapse @ test_trace_viewer.py:988-1045)"
  - "WR-02 — _aggregate_trace by_role pass now gated by _is_groupable, phantom 'unknown' bucket gone from snapshot (cli.py:136-137; regression test test_aggregate_excludes_event_kind_from_by_role @ test_trace_viewer.py:887-941)"
  - "WR-03 — _render_collapsed_group surfaces non-canonical statuses under 'other' bucket; '0 success' fallback replaced with '{n} unknown' (cli.py:198-210; regression test test_collapsed_group_surfaces_unknown_status_in_other_bucket @ test_trace_viewer.py:944-985)"
gaps_remaining: []
regressions: []
gaps: []
deferred: []
---

# Phase 9: Trace/Observability Polish Verification Report

**Phase Goal:** "The trace format is documented and versioned, and the trace renderer surfaces per-subagent cost and collapses noisy output by default"
**Verified:** 2026-05-17 (re-verification)
**Status:** verified
**Re-verification:** Yes — after gap closure via plan 09-06 (commits 07f3b27, fbbd343, a5f4a5b)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #   | Truth                                                                                                                                            | Status   | Evidence                                                                                                                                                                                                                                                                                                                          |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Every JSONL trace file contains a `schema_version` field; the schema is documented with a breaking-change policy                                  | VERIFIED | Producers: `pool.py:212`, `pool.py:251`, `query.py:982` stamp `"schema_version": 1` (confirmed via `grep -rn '"schema_version": 1' cores/ agents/` — exactly 3 producer hits). Doc: `docs/trace-schema.md` (319 lines) §3 documents the field with breaking-change policy; §4 the additive-shape rule; §5 v0 compatibility. Unchanged from initial verification — plan 09-06 did NOT touch producers or docs. |
| 2   | `graph-wiki-agent trace <file>` displays per-subagent cost (input/output tokens × model price) for each fan-out call                              | VERIFIED | `cli.py:352-388` emits "Cost rollup (per role/model)" — one line per `(role, model_id)` group; `$0.000000` six-decimal format; `(+K unknown)` suffix; `$n/a (K unknown)` fully-null groups; D-15 ordering (`cli.py:365-366`). `test_cost_rollup_snapshot` PASSES unchanged after plan 09-06 (git diff --stat confirmed `.ambr` cost-rollup snapshot byte-identical). |
| 3   | `graph-wiki-agent trace <file>` collapses repeated subagent-role groups into a summary line by default; `--expand` drills into the full event stream | VERIFIED | `cli.py:303-336` implements collapse + `--expand`. **Plan 09-06 tightened intent:** collapse now keys by `(role, model_id)` tuple (`cli.py:327-331`), not by `role` alone, and the collapsed-group header surfaces `model_short` (`cli.py:188-190, 233-235`). `test_default_mode_collapses_consecutive_same_role` and `test_expand_mode_renders_every_record_full_line` both PASS post-fix (with inline anchor adjustments — see Inline-Assertion Adjustments below). |

**Score:** 3/3 roadmap success criteria met — no caveats.

### Required Artifacts

| Artifact                                                                                          | Expected                                                                  | Status   | Details                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cores/subagent-runtime/src/subagent_runtime/pool.py`                                             | Two trace writers stamp `schema_version: 1`                                | VERIFIED | Lines 212 and 251 — unchanged from initial verification (plan 09-06 did not touch producers).                                                                                            |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py`                                    | query_summary writer stamps `schema_version: 1`                            | VERIFIED | Line 982 — unchanged.                                                                                                                                                                    |
| `docs/trace-schema.md`                                                                            | Authoritative schema reference, six required sections                     | VERIFIED | 319 lines — unchanged (plan 09-06 did not touch schema docs).                                                                                                                            |
| `docs/cancellation.md`                                                                            | One-line cross-link to `docs/trace-schema.md`                              | VERIFIED | Line 96 — unchanged.                                                                                                                                                                    |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`                                               | `_aggregate_trace` event/kind-filtered for by_role; `_render_collapsed_group` model-aware + other-bucket; collapse key `(role, model_id)` | VERIFIED | `_aggregate_trace` L83-167 with early-continue at L136-137; `_render_collapsed_group` L170-236 reads `model_id` (L189), includes `other` bucket (L198-204), `{n} unknown` fallback (L210); collapse extend-or-flush keys `(role, model_id)` at L327-331. `KNOWN_SCHEMA_VERSION = 1` at L32 unchanged. |
| `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py`                                          | Existing tests + 3 new regression tests for CR-01, WR-02, WR-03           | VERIFIED | 23 test functions total (up from 21 in initial verification). New: `test_aggregate_excludes_event_kind_from_by_role` @ L887, `test_collapsed_group_surfaces_unknown_status_in_other_bucket` @ L944, `test_mixed_model_same_role_breaks_collapse` @ L988. |
| `agents/graph-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr`                          | Recorded snapshots without phantom `unknown:` bucket; with `model_short` in headers | VERIFIED | Re-recorded single-pass in commit a5f4a5b. `grep -c "unknown: count=1 tokens_in=0 tokens_out=0" *.ambr` → `0`. Collapsed-group snapshots now include `/ claude-haiku-4-5-20251001-v1:0` segment. `test_cost_rollup_snapshot` and `test_expand_snapshot` byte-identical to pre-fix. |

### Key Link Verification

| From                                  | To                                  | Via                                | Status   | Details                                                                                                            |
| ------------------------------------- | ----------------------------------- | ---------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
| `SubagentPool._write_trace`           | per-item record dict                | first-key insertion                | WIRED    | `pool.py:212` — unchanged.                                                                                          |
| `SubagentPool._write_batch_terminal`  | batch terminal record dict          | first-key insertion                | WIRED    | `pool.py:251` — unchanged.                                                                                          |
| `query.py` query_summary writer       | summary_record dict                 | first-key insertion                | WIRED    | `query.py:982` — unchanged.                                                                                          |
| `cli.py` `_aggregate_trace`           | `trace` command rollup emission     | `by_role_model` dict               | WIRED    | `cli.py:357-388` consumes `agg["by_role_model"]` — unchanged.                                                       |
| `cli.py` renderer                     | `eval_harness`                      | **must NOT import**                | VERIFIED | `grep -E "from eval_harness\|import eval_harness" cli.py` returns 0 hits — D-10 invariant preserved through plan 09-06. |
| `trace` command                       | `--expand` flag                      | Typer Option                       | WIRED    | `cli.py:247-251` — unchanged.                                                                                       |
| collapse loop                         | `_render_collapsed_group`            | `_flush()` closure                  | WIRED    | `cli.py:309-336` — invokes the helper on runs of `>=2`; isolated records fall through to `_render_trace_record`.    |
| **(new) collapse extend-or-flush**    | `(role, model_id)` tuple match       | extend-or-flush guard               | WIRED    | `cli.py:327-331` — `current_run[-1].get("role") == record.get("role") and current_run[-1].get("model_id") == record.get("model_id")` — **CR-01 fix**. |
| **(new) `_aggregate_trace` by_role**   | event/kind exclusion                | `_is_groupable(record)` early-continue | WIRED  | `cli.py:136-137` — `if not _is_groupable(record): continue` immediately after total-token accumulation — **WR-02 fix**. |
| **(new) `_render_collapsed_group` status breakdown** | `other` bucket + `{n} unknown` fallback | else-branch + ordered iteration | WIRED  | `cli.py:198-210` — closed-set match on `(success, error, cancelled)` with `else: counts["other"] += 1`; canonical order tuple extended to include `other`; fallback `f"{n} unknown"` replaces literal `"0 success"` — **WR-03 fix**. |
| v0 warning                            | per-file stderr (one-shot)          | `warned_v0` flag                   | WIRED    | `cli.py:262, 277-285` — unchanged.                                                                                  |
| newer-version warning                 | per-file stderr (one-shot)          | `warned_newer` flag                | WIRED    | `cli.py:263, 286-294` — unchanged.                                                                                  |
| cancellation.md                       | trace-schema.md                     | markdown link                      | WIRED    | `docs/cancellation.md:96` — unchanged.                                                                              |

### Data-Flow Trace (Level 4)

| Artifact                          | Data Variable                                       | Source                                                                                                                                | Produces Real Data                                                                                                                                            | Status   |
| --------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `trace` rendered cost rollup      | `agg["by_role_model"]`                              | `_aggregate_trace` walks parsed records; reads `cost_usd`                                                                              | Yes — committed `test_cost_rollup_snapshot` PASSED unchanged                                                                                                   | FLOWING  |
| collapsed-group timeline          | `current_run` list of dict                          | sliding window over parsed JSONL records keyed by `(role, model_id)` (post-CR-01)                                                      | Yes — `test_default_mode_collapses_consecutive_same_role` + `test_mixed_model_same_role_breaks_collapse` exercise both single- and mixed-model fan-outs        | FLOWING  |
| v0 warning per-file               | `warned_v0` flag + file path                        | record-parse loop                                                                                                                     | Yes — `test_v0_real_fixture_renders_and_warns_once` PASSED                                                                                                     | FLOWING  |
| newer-version warning             | `warned_newer` flag + sv integer                    | record-parse loop                                                                                                                     | Yes — `test_newer_version_warns_lenient` PASSED                                                                                                                | FLOWING  |
| Per-role breakdown                | `agg["by_role"]`                                    | by_role aggregator pass NOW filtered by `_is_groupable` (post-WR-02)                                                                  | Yes — `test_aggregate_excludes_event_kind_from_by_role` PASSED — no synthetic `unknown:` bucket emitted                                                       | FLOWING (upgraded from STATIC) |
| Collapsed-group status breakdown  | `counts` dict in `_render_collapsed_group`          | per-record `status` field walk with `other`-bucket catch-all                                                                          | Yes — `test_collapsed_group_surfaces_unknown_status_in_other_bucket` PASSED — `3 other` emitted for `timeout` status; no misleading `0 success`               | FLOWING  |

### Behavioral Spot-Checks

| Behavior                                                | Command                                                                          | Result                                                              | Status |
| ------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------ |
| `--expand` advertised in help                            | `grep -q -- '--expand' cli.py`                                                  | hit                                                                 | PASS   |
| `KNOWN_SCHEMA_VERSION` constant declared                 | `grep -n 'KNOWN_SCHEMA_VERSION = 1' cli.py`                                     | L32                                                                 | PASS   |
| No eval_harness import in cli.py                         | `grep -E 'from eval_harness\|import eval_harness' cli.py \| wc -l`              | `0`                                                                 | PASS   |
| Three producer writers stamp schema_version: 1           | `grep -rn '"schema_version": 1' cores/ agents/` (filtered to producer code)     | `pool.py:212, pool.py:251, query.py:982` — three hits               | PASS   |
| `'0 success' literal absent` from cli.py                | `grep -c "0 success" cli.py`                                                    | `0`                                                                 | PASS (WR-03) |
| Phantom `unknown:` line absent from snapshot file       | `grep -c "unknown: count=1 tokens_in=0 tokens_out=0" test_trace_viewer.ambr`    | `0`                                                                 | PASS (WR-02) |
| Collapse tuple-key match wired                          | `grep -q 'current_run\[-1\].get("model_id") == record.get("model_id")' cli.py` | match found at L330                                                 | PASS (CR-01) |
| `counts["other"]` declared                              | `grep -q 'counts\["other"\]' cli.py`                                            | match found at L198, L204                                           | PASS (WR-03) |
| `_is_groupable` reused in `_aggregate_trace`             | grep `_is_groupable(record)` inside `_aggregate_trace`                          | match at L136                                                       | PASS (WR-02) |
| Full trace-viewer test suite green                       | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_trace_viewer.py -v` | **23 passed, 5 snapshots passed in 12.60s**                         | PASS   |

### Probe Execution

No probes declared in PLAN frontmatter or SUMMARY files for phase 9. Phase 9 verification surface is the pytest suite committed in `test_trace_viewer.py`, `test_pool.py`, and `test_query_summary_schema_version.py`, not a separate `scripts/.../probe-*.sh`. SKIPPED — no applicable probes.

### Requirements Coverage

| Requirement | Source Plan(s)        | Description                                                                                                                  | Status    | Evidence                                                                                                                                                                          |
| ----------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OBS-04      | 09-01, 09-02, 09-05   | `.graph-wiki/traces/` JSONL schema is documented and versioned                                                                | SATISFIED | Unchanged from initial verification — plan 09-06 did not touch OBS-04 surfaces.                                                                                                  |
| OBS-05      | 09-03, **09-06**      | `graph-wiki-agent trace` renderer surfaces per-subagent cost per trace                                                        | SATISFIED | Cost rollup at `cli.py:352-388` unchanged; `test_cost_rollup_snapshot` PASSED unchanged. Plan 09-06 strengthened OBS-05's *intent* (model attribution end-to-end) without modifying the cost-rollup section. |
| OBS-06      | 09-04, **09-06**      | Trace renderer collapses repeated subagent-role groups into a summary line by default, with `--expand` to drill in           | SATISFIED | `cli.py:303-336` collapse + `--expand`; **plan 09-06 closed the caveat** by keying collapse on `(role, model_id)` and surfacing `model_short` in the collapsed-group header. The literal SC#3 wording AND the intent are now both met. |

No orphaned requirements.

### Anti-Patterns Found

| File                                                                | Line | Pattern                                                                                                  | Severity | Impact                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ~~`cli.py` L303 (collapse keys by `role` only)~~                    | —    | **CLOSED by CR-01 fix** — collapse now keys by `(role, model_id)`                                        | RESOLVED | Was: timeline misrepresented mixed-model fan-outs. Now: `test_mixed_model_same_role_breaks_collapse` pins distinct lines.                                                                                                                  |
| ~~`cli.py` L124-132 (by_role bucketizes event/kind)~~               | —    | **CLOSED by WR-02 fix** — `_is_groupable` early-continue                                                  | RESOLVED | Was: phantom `unknown` bucket baked in snapshot. Now: `test_aggregate_excludes_event_kind_from_by_role` pins absence; snapshot grep clean.                                                                                                  |
| ~~`cli.py` L182-189 (hardcoded `{success,error,cancelled}` dict)~~  | —    | **CLOSED by WR-03 fix** — `other` bucket + `{n} unknown` fallback                                         | RESOLVED | Was: future statuses silently dropped; `0 success` for N-record group. Now: `test_collapsed_group_surfaces_unknown_status_in_other_bucket` pins `3 other`.                                                                                  |
| `cli.py` L288 (`isinstance(sv, int)` treats `bool` as int)          | 288  | WR-01 — out of scope for plan 09-06 per planning_context. Latent producer-side bug class.                | INFO     | Unchanged. Latent; no real producer emits bool schema_version.                                                                                                                                                                                |
| `cli.py` various (missing `timestamp` → `-` fallback)               | —    | WR-04 — out of scope. Cosmetic.                                                                          | INFO     | Unchanged.                                                                                                                                                                                                                                    |
| `cli.py` L159 (`float(cost)` bare ValueError context)               | 159  | IN-01 — out of scope. Operator-friendliness.                                                             | INFO     | Unchanged.                                                                                                                                                                                                                                    |
| `docs/cancellation.md` inline JSON examples lack `schema_version`   | 103-131 | IN-04 — out of scope. Doc drift.                                                                       | INFO     | Unchanged.                                                                                                                                                                                                                                    |

No debt markers (`TBD`, `FIXME`, `XXX`) introduced by plan 09-06 — `grep -n -E "TBD|FIXME|XXX" cli.py test_trace_viewer.py` clean.

### Human Verification Required

None. Phase 9 is renderer/docs/schema-stamping work; every observable behavior is grep- or test-suite-verifiable. The committed snapshot tests lock the output shape end-to-end through real subprocess invocations.

## Gap Closure Re-verification

Each of the three advisory gaps surfaced by the initial verification (`f72b149`) was closed by plan 09-06.

| Gap   | Closure Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Commit    | Regression Test                                                          |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------ |
| CR-01 | `cli.py:189` reads `model_id = records[0].get("model_id", "-")` in `_render_collapsed_group`; `cli.py:190` computes `model_short = model_id[-30:]` (mirrors cost-rollup convention at `cli.py:373`); `cli.py:233-235` returns header `f"[{ts_first} .. {ts_last}] {role} / {model_short} x{n}: {breakdown}, {sum_tin}->{sum_tout} tokens, {cost_str}"`. Collapse extend-or-flush at `cli.py:327-331` now keys `(role, model_id)` tuple. | `07f3b27` | `test_mixed_model_same_role_breaks_collapse` @ `test_trace_viewer.py:988` — asserts haiku and sonnet substrings on DISTINCT timeline lines. |
| WR-02 | `cli.py:136-137` — `if not _is_groupable(record): continue` placed immediately after total-token accumulation in `_aggregate_trace`. The by_role pass at `cli.py:139-142` now runs ONLY for groupable records. Snapshot file: `grep -c "unknown: count=1 tokens_in=0 tokens_out=0" test_trace_viewer.ambr` → `0` (was 1 pre-fix). | `fbbd343` | `test_aggregate_excludes_event_kind_from_by_role` @ `test_trace_viewer.py:887` — asserts `"scanner:" in per_role_section` AND `"unknown:" not in per_role_section`. |
| WR-03 | `cli.py:198` — `counts = {"success": 0, "error": 0, "cancelled": 0, "other": 0}`. `cli.py:199-204` — closed-set match with `else: counts["other"] += 1`. `cli.py:205-209` — canonical order `("success", "error", "cancelled", "other")`. `cli.py:210` — fallback `f"{n} unknown"` replaces `"0 success"`. `grep -c "0 success" cli.py` → `0`. | `fbbd343` | `test_collapsed_group_surfaces_unknown_status_in_other_bucket` @ `test_trace_viewer.py:944` — asserts `"3 other" in timeline` AND `"0 success" not in timeline`. |

**Snapshot regeneration:** Single `pytest --snapshot-update` pass in commit `a5f4a5b` regenerated three snapshots (`test_collapsed_default_snapshot`, `test_mixed_status_in_run_snapshot`, `test_query_summary_interleaved_breaks_group_snapshot`) — all gained the `/ claude-haiku-4-5-20251001-v1:0` header segment; the interleaved snapshot additionally lost the phantom `unknown:` line AND `scanner: count=6 → 5` (because the `event: batch_cancelled` record carrying `role: scanner` is now correctly excluded from by_role under the unified `_is_groupable` filter — a deliberate consequence of WR-02 fix that the executor identified and documented in 09-06-SUMMARY.md). `test_cost_rollup_snapshot` and `test_expand_snapshot` are byte-identical pre/post.

**Inline-assertion adjustments:** Two inline-asserted tests had substring anchors split by the new `/ <model_short>` segment in collapsed-group headers:
- `test_default_mode_collapses_consecutive_same_role`: assertions adjusted to match `scanner` AND `x4:` separately (allowing intervening model segment).
- `test_expand_mode_renders_every_record_full_line`: tightened to `assert "x4:" not in stdout` (xN: token uniquely identifies collapsed-group headers, never appears in expand mode).

Both adjustments preserve the tests' original intent — pinning that collapse occurred (or did not) — and the SC#3 surface remains verified.

### Non-Regression Verification

| Surface                                  | Check                                                                                                | Result                                                |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| OBS-04 (schema_version stamping)         | `grep -rn '"schema_version": 1' cores/ agents/` (producer code)                                      | Three hits — `pool.py:212, 251`, `query.py:982`       |
| OBS-04 (schema doc)                      | `wc -l docs/trace-schema.md`                                                                         | 319 lines — unchanged                                 |
| OBS-05 (cost rollup section)             | `git diff 0ffb900..HEAD -- agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` for L352-388 region   | Cost-rollup block unchanged; `test_cost_rollup_snapshot` PASSED |
| OBS-06 (collapse + expand)               | `test_default_mode_collapses_consecutive_same_role` + `test_expand_mode_renders_every_record_full_line` | Both PASSED                                           |
| Producer code scope discipline           | `git diff 0ffb900..HEAD --stat` — `pool.py`, `query.py`                                              | Untouched — three modified files match plan's `files_modified` exactly |
| Schema docs scope discipline             | `git diff 0ffb900..HEAD --stat` — `docs/trace-schema.md`, `docs/cancellation.md`                     | Untouched                                             |
| Full unit-test suite (no upstream regression) | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_trace_viewer.py`     | **23 passed, 5 snapshots passed in 12.60s, exit 0**   |
| D-10 invariant (renderer ⊥ eval_harness) | `grep -E 'from eval_harness\|import eval_harness' cli.py \| wc -l`                                   | `0` — unchanged                                       |

### Gaps Summary

No remaining gaps. All three advisory gaps from the initial verification report (`09-VERIFICATION.md` @ `f72b149`) closed cleanly. The renderer's collapsed-group timeline now preserves model attribution end-to-end (CR-01), the per-role breakdown no longer synthesizes a phantom `unknown` bucket (WR-02), and the collapsed-group status breakdown handles future producer-added statuses correctly via an `other` catch-all (WR-03). Three new regression tests pin each closure; the test suite is green (23 passed, no skipped); scope was disciplined exactly to the three files declared in `09-06-PLAN.md`'s `files_modified` list.

Phase 9 goal achieved: trace format is documented and versioned (OBS-04), trace renderer surfaces per-subagent cost (OBS-05), and noisy output collapses by default — including correct model attribution and additive-shape resilience (OBS-06).

---

_Verified: 2026-05-17 (re-verification)_
_Verifier: Claude (gsd-verifier)_
_Original verification: 09-VERIFICATION.md @ f72b149 (status: gaps_found, 3 advisory)_
_Closure plan: 09-06-PLAN.md @ 0ffb900 + commits 07f3b27, fbbd343, a5f4a5b_
