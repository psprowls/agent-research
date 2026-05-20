---
phase: 10-subagent-context-completion
plan: 07
subsystem: testing
tags: [pytest, syrupy, snapshot, token-budget, divergence-eval, ctx-04, ctx-05]

# Dependency graph
requires:
  - phase: 10-subagent-context-completion
    provides: project_context renderer + builder fns w/ project_context kwarg (plans 10-04..10-06)
provides:
  - Snapshot tests covering with-context AND without-context paths for scanner/ingestor/linter-3-groups
  - Missing-CLAUDE.md degradation test enforcing empty-render + non-empty-prompt contract
  - +1500-tokens-per-role budget regression test with baselines pinned to a documented git SHA
affects: [future-prompt-fragments, future-context-block-additions, phase-10-merge-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Snapshot-test-per-context-shape: one snapshot per (builder × context-state) cell"
    - "Token-budget-as-test: regression caught at CI, no runtime cost"

key-files:
  created:
    - agents/graph-wiki-agent/tests/prompts/test_token_budget.py
  modified:
    - agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py
    - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr

key-decisions:
  - "PRE_PHASE_10_BASELINE pinned to git SHA e9cfd56 (parent of 1cc94f5) — fragments unchanged since, so baseline is reproducible"
  - "Duplicated FIXTURE_CLAUDE_MD into test_prompt_snapshots.py rather than importing — keeps snapshot test self-contained per CONTEXT.md §Claude's Discretion"
  - "Task 3 divergence-eval re-run DEFERRED — live Bedrock not reachable from parallel-executor worktree (no GRAPH_WIKI_RUN_EVAL, no AWS creds); checkpoint must be resolved by developer before merging Phase 10"

patterns-established:
  - "Pattern 1: With-context snapshot tests use a tmp_path helper (_render_ctx_from_tmp) to materialize a wiki/CLAUDE.md fixture deterministically"
  - "Pattern 2: Token-budget tests assert per-role using a shared _assert_within_budget helper with a diagnostic failure message naming role, measured, baseline, ceiling"

requirements-completed: [CTX-04]
requirements-deferred: [CTX-05]

# Metrics
duration: ~15min
completed: 2026-05-17
---

# Phase 10 Plan 07: Verification harness — snapshot + token-budget regression tests

**6 new snapshot tests (5 with-context + 1 degradation) and 6 token-budget tests pinned to git SHA e9cfd56 enforce CTX-04 in CI; CTX-05 divergence-eval second half deferred to developer because live Bedrock is unreachable from the parallel-executor worktree.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-17T20:13:00Z
- **Completed:** 2026-05-17T20:28:00Z
- **Tasks:** 2 of 3 (Task 3 is the human-verify checkpoint, returned to orchestrator)
- **Files modified:** 3 (1 new, 2 modified)

## Accomplishments

- 5 new with-context snapshot tests record the wiring contract for scanner/ingestor/linter-3-groups — a future refactor that drops the `project_context` kwarg or fails to insert the block is caught by snapshot diff.
- 1 degradation test asserts `render_project_context(missing)` returns `""` AND every builder still emits a non-empty prompt — the missing-CLAUDE.md contract is no longer implicit.
- New `test_token_budget.py` with 6 tests pins the +1500-tokens-per-role ceiling and documents the exact git SHA (e9cfd56) used to derive baselines, so any developer can rederive the same numbers.
- Confirmed all 6 current builders are within the +1500 budget — largest delta is ingestor at +751 tokens (baseline 1574 → current 2325, 749 of headroom remaining).

## Task Commits

1. **Task 1: Extend test_prompt_snapshots.py with project-context-aware tests** — `0df20f9` (test)
2. **Task 2: Create test_token_budget.py enforcing +1500 token ceiling** — `e2ae080` (test)
3. **Task 3: Re-run Phase 6 divergence eval** — DEFERRED (no commit; see "Deferred Work" below)

## Files Created/Modified

- `agents/graph-wiki-agent/tests/prompts/test_token_budget.py` *(new)* — Six per-role token-budget tests with documented baselines.
- `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py` *(modified)* — Six new tests (5 with-context + 1 degradation) plus `FIXTURE_CLAUDE_MD_FOR_SNAPSHOTS` constant and `_render_ctx_from_tmp` helper.
- `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` *(modified)* — 5 newly recorded snapshots for the with-context builds.

## PRE_PHASE_10_BASELINE Reference (for future phases)

Measured via `len(prompt) // 4` against git SHA `e9cfd56` (parent of 1cc94f5 — the wiring commit). Fragments are byte-identical between e9cfd56 and HEAD (`git diff e9cfd56 HEAD -- agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/` returns empty), so the baselines are reproducible.

| Role                  | Baseline tokens | Current tokens | Headroom (ceiling = baseline + 1500) |
| --------------------- | --------------- | -------------- | ------------------------------------ |
| scanner               | 837             | 1445           | 892 of 1500 remaining                |
| ingestor              | 1574            | 2325           | 749 of 1500 remaining                |
| linter_page_quality   | 617             | 741            | 1376 of 1500 remaining               |
| linter_adr_chain      | 514             | 638            | 1376 of 1500 remaining               |
| linter_stale_claims   | 529             | 653            | 1376 of 1500 remaining               |
| librarian             | 975             | 1054           | 1421 of 1500 remaining               |

The ingestor has the tightest budget because it receives the most fragments (ARCHITECTURE_OVERVIEW + PAGE_CATEGORIES + FRONTMATTER_RULES + CITATION_RULES + STYLE_RULES + CLAUDE_MD_DISAMBIGUATION + LOG_FORMAT + role-local prose).

## Decisions Made

- **Duplicate FIXTURE_CLAUDE_MD across test files** rather than importing it from `test_project_context.py`. Rationale: CONTEXT.md §Claude's Discretion encourages test-module self-containment so a snapshot drift in one file does not propagate via shared imports.
- **Pin baselines to a single SHA in a comment block** rather than recomputing at test time. Rationale: the baseline is a contract, not an observation. A baseline that drifts silently would defeat the regression-gate purpose.
- **Use `len // 4` as the tokenizer** per CONTEXT.md LOCKED. Rationale: tiktoken is OpenAI-specific (wrong for Bedrock/Claude), and pulling boto3 CountTokens into a unit test would add Bedrock dependence — both forbidden by the project constraints.

## Deviations from Plan

None — plan executed exactly as written. The Task 3 deferral is part of the plan's explicit fallback (see `<how-to-verify>` step 5: "If the divergence eval gate is itself broken or unavailable... this checkpoint may be deferred").

## Deferred Work — REQUIRES DEVELOPER ACTION BEFORE PHASE 10 MERGE

**Task 3 (CTX-05 second half): Phase 6 divergence-eval re-run.**

The `test_divergence_regression` test at `cores/eval-harness/tests/test_divergence.py` is gated behind `GRAPH_WIKI_RUN_EVAL=1` and requires live AWS Bedrock credentials. Neither is available in the parallel-executor worktree environment (verified: `GRAPH_WIKI_RUN_EVAL=""`, `AWS_ACCESS_KEY_ID` unset, `AWS_PROFILE=""`).

**Required developer follow-up** (must complete before Phase 10 is merged into a release):

1. Export AWS credentials for the Bedrock account.
2. Run:
   ```bash
   GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest cores/eval-harness/tests/test_divergence.py -x -v
   ```
3. Inspect the per-role report (printed under `-s`). Expected outcomes:
   - **PASS** → CTX-05 fully satisfied; mark complete.
   - **FAIL with small attributable delta** → review the divergence diff; if the new ARCHITECTURE_OVERVIEW or project-context block legitimately changed model behavior in a non-regressive way, re-run with `--accept-divergence-baseline` and commit the refreshed baselines under `cores/eval-harness/baselines/`.
   - **FAIL with large delta** → file a follow-up plan to investigate which Phase 10 fragment or wiring change caused the regression. Do NOT accept-baseline.

A corresponding CTX-05 entry in `.planning/REQUIREMENTS.md` must remain `[ ]` (unchecked) until the developer completes this step. The orchestrator is responsible for marking CTX-04 complete now and leaving CTX-05 deferred until the divergence eval result is recorded.

## Threat Flags

None — this plan only adds tests; no new network endpoints, auth paths, file-access patterns, or trust-boundary changes.

## Issues Encountered

None.

## User Setup Required

None for the test changes. The Task 3 deferral requires AWS Bedrock credentials to resolve — see "Deferred Work" above.

## Self-Check: PASSED

- `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py` exists (modified) — FOUND
- `agents/graph-wiki-agent/tests/prompts/test_token_budget.py` exists (new) — FOUND
- `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` exists (5 new snapshots) — FOUND
- Commit `0df20f9` (test 10-07 snapshot tests) — FOUND in git log
- Commit `e2ae080` (test 10-07 token budget) — FOUND in git log
- Full test run: `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/prompts/ -x` reports 26 passed.

## Next Phase Readiness

- CTX-04 is fully satisfied — snapshot + degradation tests are in CI and will catch any wiring-contract regression.
- CTX-05 first half (+1500 token ceiling) is satisfied and will catch any fragment-bloat regression.
- CTX-05 second half (divergence-eval re-run) is the human-verify checkpoint at Task 3 — developer must run the live-Bedrock eval before Phase 10 can be considered closed.
- All scope fences honored: no edits to `deepagents`, `pyproject.toml`, `pool.py`, or any prompt/command source file. `git diff --name-only` for `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/` and `commands/` reports 0 changes from this plan.

## Task 3: Divergence Eval Result (2026-05-17)

Ran live with `GRAPH_WIKI_RUN_EVAL=1` + AWS Bedrock (us-east-1) — **PASSED for all 4 roles (193s total)**.

| Role | Status | Notes |
|------|--------|-------|
| librarian | PASSED | 4 cases; LIB-001/004/JUDGE failures within baseline |
| ingestor | PASSED | 2 cases; ING-001/002 single-case failures within baseline |
| linter | PASSED | 3 cases; LNT-JUDGE 2 failures within baseline |
| scanner | PASSED | 1 case; SCN-003 single failure within baseline (pipeline-added File map section) |

No hard-severity regression vs. recorded baselines under `cores/eval-harness/baselines/` (left unchanged). CTX-05 fully satisfied.

---
*Phase: 10-subagent-context-completion*
*Completed: 2026-05-17 (all 3 tasks)*
