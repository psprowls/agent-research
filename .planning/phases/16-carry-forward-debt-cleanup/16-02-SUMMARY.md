---
phase: 16-carry-forward-debt-cleanup
plan: 02
subsystem: observability
tags: [trace-pipeline, subagent-pool, bedrock, fan-out, usage-metadata, taskresult]

# Dependency graph
requires:
  - phase: 16-carry-forward-debt-cleanup
    provides: "Plan 16-01 wired write_trace_record into ingest + synthesizer call sites and surfaced G-01 via the first gated Bedrock run."
provides:
  - "Backward-compatible TaskResult contract on SubagentPool.run_all that threads response.usage_metadata into JSONL trace records without breaking scalar-returning callbacks."
  - "All 4 production fan-out callbacks (scanner, linter, librarian, code_reader) now emit non-None tokens_in/tokens_out/cost_usd on per-item trace records."
  - "Self-isolating integration test that no longer trips on stale traces in the copied fixture vault."
  - "VERIFICATION.md G-01 entry flipped to status: CLOSED with passing Bedrock re-run transcript."
affects: [observability, eval-harness, cost-tracking, future-fan-out-callsites]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Opt-in dataclass sentinel (TaskResult) for callback return shapes — isinstance-detected, scalar-passthrough preserved."
    - "Integration tests that copy fixture vaults must rmtree any .code-wiki/traces directory copied over to avoid reading stale records."

key-files:
  created:
    - .planning/phases/16-carry-forward-debt-cleanup/16-02-SUMMARY.md
  modified:
    - packages/subagent-runtime/src/subagent_runtime/pool.py
    - packages/subagent-runtime/src/subagent_runtime/__init__.py
    - packages/subagent-runtime/tests/test_pool.py
    - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
    - agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
    - agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py
    - agents/code-wiki-agent/tests/integration/test_trace_coverage.py
    - .planning/phases/16-carry-forward-debt-cleanup/16-VERIFICATION.md

key-decisions:
  - "Chose option (a) — explicit TaskResult dataclass — over option (b) pool-side response-aware hook. Explicit type-checked sentinel beats hidden duck-typing; backward-compat preserved by isinstance(result, TaskResult) detection that falls through to today's scalar behavior."
  - "Reverted the planner-prescribed fixture-side deletion + .gitignore (Task 2.5 sub-action) after discovering the JSONLs are load-bearing for test_trace_viewer.py::test_v0_real_fixture_renders_and_warns_once (D-04 v0 unversioned fixture). Test-side rmtree alone fully satisfies the operator's stated isolation goal."
  - "VERIFICATION.md status flipped gaps_found → human_needed, NOT passed — the 3 HUMAN-UAT judgment-call items (live model-sweep, calendar-vs-event trigger, code_reader non-trivial scores) remain pending Pat's ack outside this plan."

patterns-established:
  - "TaskResult opt-in contract: fan-out callbacks that want usage_metadata in their trace records return TaskResult(value=<scalar>, response=<resp>); pool unwraps .value into successes and passes .response to write_trace_record."
  - "Fixture-vault integration tests should rmtree any .code-wiki/traces dir after copytree so assertions only walk records produced by the current run."

requirements-completed: [TRACE-FU-01]

# Metrics
duration: ~25min
completed: 2026-05-19
---

# Phase 16 Plan 02: G-01 Closure (Librarian Trace usage_metadata) Summary

**TaskResult contract on SubagentPool now threads response.usage_metadata into JSONL traces; all 4 fan-out callsites migrated; gated TRACE-FU-01 regression passes against real Bedrock.**

## Performance

- **Duration:** ~25 min (executor wall-clock, including one Bedrock re-run at ~14s)
- **Completed:** 2026-05-19
- **Tasks:** 5 (Task 1 + Task 2 from initial run; Task 2.5 + Task 3 re-run + Task 4 in this resume)
- **Files modified:** 7 source + 1 verification doc

## Accomplishments

- Closed G-01: librarian fan-out trace records now carry non-None `tokens_in` / `tokens_out` / `cost_usd` on `status=success`. Verified via gated Bedrock re-run: `1 passed in 14.02s`.
- Extended `SubagentPool.run_all` with an opt-in `TaskResult(value=..., response=...)` contract — backward-compatible (13 pre-existing test_pool.py tests still pass; 3 new tests added).
- Migrated all 4 production fan-out callbacks atomically (scanner, linter, librarian, code_reader) so no role silently drops usage_metadata.
- Self-isolated the gated integration test from stale traces in the copied fixture vault (root cause of partial false-negative in the 2026-05-19 first gated run).
- Updated `16-VERIFICATION.md`: G-01 entry → `status: CLOSED`, SC#1 row → `✓ VERIFIED`, frontmatter `status` → `human_needed` (3 HUMAN-UAT items still pending).

## Task Commits

1. **Task 1: Extend SubagentPool with TaskResult dataclass** — `e97ae7f` (`feat(16-02): extend SubagentPool task contract with TaskResult for usage_metadata pass-through (G-01 closure)`)
2. **Task 2: Migrate 4 production fan-out callbacks to return TaskResult** — `629f077` (`fix(16-02): wrap fan-out callbacks in TaskResult so librarian + scanner + linter + code_reader traces carry usage_metadata (G-01)`)
3. **Task 2.5 (deviation insert): Self-isolate TRACE-FU-01 test from stale fixture traces** — `4df6ace` (`fix(16-02): self-isolate TRACE-FU-01 test from stale fixture traces (G-01 follow-up)`)
4. **Task 3: Gated TRACE-FU-01 Bedrock re-run** — no commit (test transcript captured below)
5. **Task 4: Document G-01 closure in VERIFICATION.md** — `68de2ca` (`docs(16-02): mark G-01 CLOSED after 16-02 fix verified against real Bedrock`)

**Plan metadata commit (this SUMMARY):** to follow this file.

## Files Created/Modified

- `packages/subagent-runtime/src/subagent_runtime/pool.py` — Added `TaskResult` dataclass; `_run_one` now `isinstance`-detects TaskResult and unwraps `.value` into `successes` while passing `.response` to `_write_trace`.
- `packages/subagent-runtime/src/subagent_runtime/__init__.py` — Exported `TaskResult` alongside existing `SubagentPool`, `FanOutResult`, `PerItemError`.
- `packages/subagent-runtime/tests/test_pool.py` — Added 3 new tests locking the contract (TaskResult path writes tokens; scalar path preserves None; TaskResult(value=None, response=None) writes None tokens with item=None in successes).
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — `drill_page` + both terminal paths of `code_drill` now return `TaskResult`.
- `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py` — `generate_stub` returns `TaskResult`.
- `agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py` — `run_linter_group` (both terminal paths) returns `TaskResult`.
- `agents/code-wiki-agent/tests/integration/test_trace_coverage.py` — `shutil.rmtree(stale_traces)` added immediately after `shutil.copytree(FIXTURE_VAULT, wiki)` so the assertion only walks records produced by the current run.
- `.planning/phases/16-carry-forward-debt-cleanup/16-VERIFICATION.md` — G-01 status flipped to CLOSED with full evidence; SC#1 row flipped to VERIFIED; new `## G-01 Closure (Phase 16-02)` body section appended.

## Decisions Made

- **TaskResult dataclass vs pool-side response hook.** Chose TaskResult (option (a) in the plan). Rationale: explicit type-checked sentinel is more discoverable than a configurable hook, easier to grep for at callsites, and the migration cost was only 4 callsites. The scalar fall-through (everything that isn't a TaskResult is treated as today) preserves full backward compatibility with the 13 pre-existing pool unit tests and any future caller that doesn't care about usage_metadata.
- **Reverted fixture-side deletion.** The planner's Task 2.5 prescribed both a test-side rmtree AND deletion of the 18 JSONLs from `packages/vault-io/tests/fixtures/round-trip-vault/.code-wiki/traces/` plus a new `.gitignore`. The fixture-side deletion broke `test_trace_viewer.py::test_v0_real_fixture_renders_and_warns_once`, which load-bears on those exact files as a Phase 9 D-04 v0 unversioned-record fixture. The test-side rmtree alone fully achieves the operator's stated goal (isolate integration test from any traces in copied fixture). The fixture-side deletion was reverted; documented in VERIFICATION.md G-01 `notes` field.
- **VERIFICATION.md status: human_needed (not passed).** Even with G-01 closed, the 3 HUMAN-UAT judgment-call items remain `[pending]` (live model-sweep, calendar-vs-event trigger, code_reader non-trivial scores). Per the verifier decision tree, any open human_verification items take priority over `passed`.

## Deviations from Plan

### Deviation 1 — Mid-plan Task 2.5 insertion (operator-authorized)

**Found during:** Initial Task 3 gated Bedrock run. Test failed despite the fix working (verified manually by orchestrator). Root cause: 18 stale JSONLs committed in the fixture vault `.code-wiki/traces/` dir were being copied into the test's tmp_path and the test's `for jsonl in trace_dir.glob("*.jsonl"):` loop was reading them, asserting on a stale 2026-05-14 librarian record with tokens_in=None.

**Operator decision:** patch the test for self-isolation and re-run. Inserted as Task 2.5 in the resume context.

**What landed:** `shutil.rmtree(stale_traces)` after `copytree` in the integration test. Committed as `4df6ace`.

### Deviation 2 — [Rule 4] Reverted fixture-side deletion sub-action of Task 2.5

**Found during:** Task 2.5, after git-rm'ing the 18 JSONLs and adding `.gitignore`.

**Issue:** Running the non-integration suite then failed `agents/code-wiki-agent/tests/unit/test_trace_viewer.py::test_v0_real_fixture_renders_and_warns_once` with `AssertionError: No real v0 fixtures found at .../round-trip-vault/.code-wiki/traces` — those JSONLs are intentionally committed as a Phase 9 D-04 v0 unversioned-record fixture for the trace viewer's lenient-consumer path.

**Fix:** `git restore --staged` + `git restore` the traces dir; removed the staged `.gitignore`. Kept only the test-side rmtree, which fully achieves the operator's stated isolation goal.

**Verification:** Non-integration suite back to baseline (`205 passed in 19.75s` for code-wiki-agent tests).

**Files modified by the revert:** none (reverted-to-baseline; only `agents/code-wiki-agent/tests/integration/test_trace_coverage.py` carried changes into the Task 2.5 commit).

**Why Rule 4 (architectural):** the planner's prescribed action would silently break an unrelated test. Strict-Rule-3 (auto-fix blocker) would have re-deleted the files — wrong call. Documented in commit `4df6ace` body and in VERIFICATION.md G-01 `notes` so the follow-up path is visible (right move is to migrate `test_v0_real_fixture_renders_and_warns_once` to inline its fixture records the way its siblings already do; out of scope for 16-02).

---

**Total deviations:** 1 inserted task (operator-authorized) + 1 sub-action revert (Rule 4).
**Impact on plan:** None on the must-haves — G-01 fully closed, all SC#1 evidence in place. Documented in VERIFICATION.md so the v0 fixture follow-up is on record.

## Issues Encountered

- **Test fixture leak vs. intentional fixture.** Initial assumption (per the operator's resume context) was that the 18 JSONLs in the fixture vault were stale leakage. Investigation revealed they are an intentional Phase 9 D-04 v0 fixture. Resolved by minimal-fix approach (test-side rmtree only; fixture left untouched).

## Verification Reference

- **Gated TRACE-FU-01 test transcript (2026-05-19):**
  ```
  $ CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v
  ============================= test session starts ==============================
  collected 1 item
  agents/code-wiki-agent/tests/integration/test_trace_coverage.py::test_trace_pipeline_records_token_usage PASSED [100%]
  ============================== 1 passed in 14.02s ==============================
  ```
- **Sample librarian success records from a clean orchestrator-side manual query** (independent of the test, same fixture vault):
  - `concepts/code-wiki-pattern.md` → tokens_in=2804, tokens_out=119, cost_usd=$0.003399
  - `packages/lattice-curator-core/context.md` → tokens_in=2536, tokens_out=118, cost_usd=$0.003126
  - `concepts/lattice-vault-terminology.md` → tokens_in=3597, tokens_out=307, cost_usd=$0.005132
- **Updated verification doc:** `.planning/phases/16-carry-forward-debt-cleanup/16-VERIFICATION.md` — G-01 entry `status: CLOSED`, SC#1 row `✓ VERIFIED`, body `## G-01 Closure (Phase 16-02)` section.

## Carry-forward / Follow-up

- **3 HUMAN-UAT items still pending** (out of scope for 16-02; require Pat's ack outside any plan):
  1. SC#2 substitution acceptance for live model-sweep (deterministic SCANNER_CHECKS 65% with structural-mismatch justification).
  2. SC#3 acceptance of event-driven trigger in place of calendar-date re-eval (D-09 deviation).
  3. SC#2 sub-clause acceptance of code_reader case structural evidence in lieu of actual scores.
- **v0 fixture follow-up (not in this plan):** If we ever want to delete the 18 committed JSONLs from the fixture vault, the right move is to first migrate `agents/code-wiki-agent/tests/unit/test_trace_viewer.py::test_v0_real_fixture_renders_and_warns_once` to inline its fixture records (the pattern its sibling helpers `_write_newer_version_fixture` and `_write_unversioned_inline_fixture` already use). Tracked here so it's discoverable; not opening a new plan for it.

## Known Stubs

None. No empty-data UI bindings, no "coming soon" placeholders, no TODOs introduced.

## Threat Flags

None new. T-16.02-* threats from the plan's threat model are all `mitigate`d (T-16.02-01 strict isinstance check enforced; T-16.02-04 4-callsite migration covered by gated integration test) or `accept`ed (T-16.02-02 token counts are not PII; T-16.02-03 trace OSError already swallowed in shared writer).

## User Setup Required

None - no external service configuration added by this plan. Bedrock credentials needed only for re-running the gated test; same setup as 16-01.

## Self-Check: PASSED

- All 4 task commits exist in git log: `e97ae7f`, `629f077`, `4df6ace`, `68de2ca` ✓
- `packages/subagent-runtime/src/subagent_runtime/pool.py` contains `class TaskResult` ✓
- `agents/code-wiki-agent/src/code_wiki_agent/commands/{query,scan,lint}.py` all import + use `TaskResult` ✓
- `agents/code-wiki-agent/tests/integration/test_trace_coverage.py` contains `shutil.rmtree(stale_traces)` ✓
- `.planning/phases/16-carry-forward-debt-cleanup/16-VERIFICATION.md` contains `status: CLOSED` (G-01 entry) and `## G-01 Closure (Phase 16-02)` ✓
- Gated test exit code 0 with `1 passed in 14.02s` ✓
- Non-integration suite at baseline (`205 passed` for code-wiki-agent) ✓
- HUMAN-UAT.md not modified (`git diff --name-only` confirmed empty for that path) ✓
- No edits to STATE.md, ROADMAP.md, 16-01-PLAN.md, 16-01-SUMMARY.md, 16-CONTEXT.md, 16-PATTERNS.md, 16-DISCUSSION-LOG.md, or 16-REVIEW.md ✓

## Next Phase Readiness

- Phase 16 is unblocked on TRACE-FU-01 / SC#1. G-01 fully closed.
- The 3 HUMAN-UAT judgment-call items remain Pat's call to mark `[done]` or `[rejected]` directly in `16-HUMAN-UAT.md`; no plan needed for that.
- TaskResult contract is now the canonical way for any future fan-out callback to surface `usage_metadata` to JSONL traces — pattern documented in this SUMMARY and the VERIFICATION closure section.

---
*Phase: 16-carry-forward-debt-cleanup*
*Plan: 02*
*Completed: 2026-05-19*
