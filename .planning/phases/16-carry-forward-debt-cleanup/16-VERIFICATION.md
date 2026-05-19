---
phase: 16-carry-forward-debt-cleanup
verified: 2026-05-19T00:00:00Z
status: passed
score: 5/5 must-haves verified — G-01 CLOSED via Plan 16-02 (Bedrock-verified); all 4 HUMAN-UAT items acknowledged by Pat on 2026-05-19 (SC#1 fan-out test passing, SC#2 scanner substitution accepted, SC#3 event-driven trigger accepted, SC#2 code_reader case structure accepted)
overrides_applied: 0
gaps:
  - id: G-01
    sc: 1
    status: CLOSED
    closed: 2026-05-19
    closed_by: "Plan 16-02"
    summary: "Librarian fan-out trace records emitted tokens_in=None, tokens_out=None despite status=success. SubagentPool.run_all wrote the trace via write_trace_record but the drill_page callback in query.py:903-914 returned only resp.content, dropping usage_metadata before the pool could read it. Phase 16 D-03/D-05 wired the synthesizer + ingest call sites; the librarian path (the dominant token consumer) was never re-plumbed until Plan 16-02."
    closure_evidence: "Plan 16-02 extended SubagentPool with an opt-in TaskResult(value=..., response=...) contract (commit e97ae7f) and migrated all 4 production fan-out callsites — scanner, linter, librarian, code_reader (commit 629f077). Plan 16-02 also self-isolated the gated test from stale fixture-vault traces (commit 4df6ace). Re-run on 2026-05-19: `CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v` → `1 passed in 14.02s`. Sample librarian success records now carry: tokens_in=2804/2536/3597, tokens_out=119/118/307, cost_usd=$0.0034/$0.0031/$0.0051 (3 different vault items, all on us.anthropic.claude-haiku-4-5-20251001-v1:0)."
    files_touched_by_fix: ["packages/subagent-runtime/src/subagent_runtime/pool.py", "packages/subagent-runtime/src/subagent_runtime/__init__.py", "packages/subagent-runtime/tests/test_pool.py", "agents/code-wiki-agent/src/code_wiki_agent/commands/query.py", "agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py", "agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py", "agents/code-wiki-agent/tests/integration/test_trace_coverage.py"]
    notes: "Original 2026-05-19 failure was partially a test fixture bug (stale committed traces being read by the integration test's glob walk); Phase 16-02 added test self-isolation via shutil.rmtree of the copied traces dir after copytree. NOTE: fixture-side deletion + .gitignore was attempted but reverted — those committed JSONLs are load-bearing for agents/code-wiki-agent/tests/unit/test_trace_viewer.py::test_v0_real_fixture_renders_and_warns_once (D-04 v0-unversioned-record fixture). Pool-side fix in 16-02 still necessary regardless — the librarian callback was dropping usage_metadata before reaching the pool's trace writer."
human_verification:
  - test: "Run the gated TRACE-FU-01 regression test against real Bedrock"
    expected: "`CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v` exits 0 and the assertion `tokens_in/tokens_out is not None` holds for every non-error / non-event JSONL record produced by a real fan-out against the round-trip fixture vault."
    why_human: "SC#1 explicitly requires the regression test 'runs a real fan-out and asserts the field is populated.' The test file exists, is correctly wired, and the 5 fast unit tests verifying the code paths all pass — but the gated regression test was NOT executed against real Bedrock during Phase 16 execution. Only a human with AWS credentials + opt-in to incur Bedrock cost can satisfy the SC#1 literal contract."
  - test: "Confirm acceptance of judgment-driven substitution for SC#2 live model-sweep"
    expected: "Pat confirms (or rejects) that the deterministic SCANNER_CHECKS pass-rate of 65% on the live vault (`~/Personal/wiki/deep-agents`) — with 7 SCN-002/SCN-003 failures attributed to a known structural mismatch (rules target raw LLM stub output; on-disk pages contain pipeline-appended `## File map`) — counts as 'no regression vs. v1.1 baseline' without running an actual `run_role_sweep` invocation against the live vault."
    why_human: "SC#2 says 'scanner re-sweep against a fresh-package vault completes without regression vs. v1.1 baseline'. Phase 16 operationalized this as a two-baseline split: forward-CI (synthetic fixture, 8/8 pass) + v1.1-equivalent (deterministic SCANNER_CHECKS against live vault, 13/20 pass with documented structural-mismatch justification). The actual live model-sweep was explicitly NOT executed per D-12 (judgment-driven, no hard cost cap was budgeted). Whether the v1.1-equivalent substitution meets the SC's intent is a judgment call only Pat can make."
  - test: "Confirm that the 'fresh re-evaluation date' phrasing in SC#3 is satisfied by the event-driven re-eval trigger in docs/cancellation.md §5"
    expected: "Pat confirms that the event-driven trigger ('Re-evaluate when langchain-aws cuts a release with #663 merged, OR when aioboto3 reaches a named milestone (GA / 1.0)') is acceptable in place of a calendar-date re-evaluation. Per D-09 the calendar phrasing was deliberately removed because v1.1->v1.2 calendar re-checks generated noise without changing the gate outcome."
    why_human: "SC#3 literal text says 'a fresh re-evaluation date'. Phase 16 chose an event-driven trigger instead (D-09 decision). The SC's intent — that the deferral be re-anchored to a checkable signal — is arguably satisfied, but the literal SC wording is not. This is a deliberate-but-undocumented (in the SC) deviation that needs explicit human acceptance."
  - test: "Confirm SC#2 'code_reader cases produce non-trivial scores' is acceptable as 'cases load and tag-validate cleanly + are structured to force code-fallback'"
    expected: "Pat confirms that cases 04-06 of `eval/cases/code_reader_cases.json` (each phrased to force the code-fallback path against post-rebrand surfaces) constitute acceptable evidence in the absence of a real sweep producing actual numeric scores."
    why_human: "SC#2 requires code_reader cases to 'produce non-trivial scores against the current fixture corpus' — producing scores requires a real model invocation. Phase 16 documented (in SUMMARY 'Scoped-down items') that the actual scoring run was not executed. Whether the case-structural evidence is sufficient is a judgment call."
---

# Phase 16 Verification

**Date:** 2026-05-19
**Plan:** 16-01 (carry-forward debt cleanup)
**Phase goal (from ROADMAP):** The v1.1 close-out debt items (trace pipeline gap, sweep matrix gaps, MCP cancel closure, model-config test drift) are resolved or explicitly re-deferred with documented justification.
**Status:** human_needed (G-01 CLOSED 2026-05-19; 3 judgment-call HUMAN-UAT items remain pending)
**Verifier:** gsd-verifier (audited the executor's pre-populated VERIFICATION.md against the actual codebase) + orchestrator post-hoc gate (ran the SC#1 gated test and recorded G-01)

---

## Goal Achievement — Observable Truths (ROADMAP Success Criteria)

| # | Truth (Success Criterion) | Status | Evidence |
|---|---------------------------|--------|----------|
| 1 | SC#1 — Every production trace JSONL from `commands/{scan,lint,ingest,query}` includes `usage_metadata` with input/output token counts (verified by a regression test that runs a real fan-out). | ✓ VERIFIED (G-01 CLOSED) | Plan 16-02 extended SubagentPool with an opt-in `TaskResult(value=..., response=...)` contract and migrated all 4 production fan-out callsites (scanner, linter, librarian, code_reader) to surface `usage_metadata` back to `write_trace_record`. Gated regression re-run on 2026-05-19: `CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v` → `1 passed in 14.02s`. Sample librarian success records carry non-None tokens — `concepts/code-wiki-pattern.md` tokens_in=2804/tokens_out=119, `packages/lattice-curator-core/context.md` tokens_in=2536/tokens_out=118, `concepts/lattice-vault-terminology.md` tokens_in=3597/tokens_out=307. See gap G-01 in frontmatter (`status: CLOSED`) and the `## G-01 Closure (Phase 16-02)` section at the end of this file. |
| 2 | SC#2 — sweep matrix runs DivergenceMetric across all in-scope roles + writes per-role scores; code_reader cases produce non-trivial scores; scanner re-sweep without regression vs. v1.1. | ⚠ VERIFIED (with caveats) | `two_gate.py:35-37` `ROLES_WITH_DIVERGENCE = frozenset({librarian, ingestor, linter, scanner, code_reader, synthesizer})` — 6 roles. `divergence/__init__.py` ROLE_CHECKS / ROLE_RUBRICS keyed on all 6. New rubrics + rule modules exist on disk for code_reader + synthesizer (4 hard + 1 soft each, anchored to `prompt-sources/agents/{code_reader,synthesizer}.md`). `code_reader_cases.json` expanded 3 → 6 (verified via `test_code_reader_cases_json_loads` PASS). Scanner fixture vault present (6 packages, no `lattice*` symbols); `test_scanner_regression.py` 8/8 PASS. BUT: actual model-sweep producing scores NOT executed; live-vault re-sweep substituted with deterministic SCANNER_CHECKS pass-rate (65%). Items 2 + 4 in human verification cover these substitutions. |
| 3 | SC#3 — Either real wire-level cancel verified end-to-end OR deferral re-documented in docs/cancellation.md with current blocker + fresh re-evaluation date. | ⚠ VERIFIED (with caveat) | `docs/cancellation.md` §4 cites both upstream blockers verbatim with PyPI / GitHub URLs (langchain-aws#663 unmerged; aioboto3 not at GA). §5 documents event-driven re-eval trigger (D-09). Deferral IS re-documented; blocker IS named. BUT the SC literally says "re-evaluation **date**" — the chosen event-driven trigger is a deliberate deviation. Item 3 in human verification covers explicit acceptance. |
| 4 | SC#4 — `CODE_WIKI_RUN_INTEGRATION` opt-in gate semantics consistent across all gated tests (single rule documented centrally; no test diverges silently). | ✓ VERIFIED | `docs/testing.md` is the canonical 5-section spec (basis / pattern / canonical block / inventory / future). `tests/test_integration_gate.py` grep-gate meta-test walks every `**/tests/integration/test_*.py` and asserts canonical regex OR `# integration-gate-allow` marker. `test_bedrock_iam.py:32,39` uses canonical INTEGRATION_GATE decorator. `test_mcp_cancel.py:3` has the allowlist marker. Meta-test PASS. Post-merge fix a530ddb correctly excludes `.claude/worktrees/` from discovery (verified in current code at `tests/test_integration_gate.py:43-44`). |
| 5 | SC#5 — `test_load_role_config_synthesizer_uses_sonnet` renamed/rewritten to assert current Qwen synthesizer default; `uv run pytest` is green. | ✓ VERIFIED | `packages/model-adapter/tests/test_loader.py:129-138` `test_load_role_config_synthesizer_limits` asserts `cfg["model_id"] == "qwen.qwen3-32b-v1:0"` AND `cfg["model_id"] == QWEN_SYNTHESIZER_ARN` (literal + constant pinned together). Test PASSES. Full non-integration suite: **549 passed, 22 skipped in 34.55s** (re-verified by gsd-verifier). |

**Score:** 5/5 must-haves verified — 3 fully verified, 2 verified with documented substitutions that require human acknowledgment (HUMAN-UAT items 2/3/4 remain pending; G-01 from prior verification CLOSED via 16-02 plan).

---

## Required Artifacts Verification (Level 1 — Exists, Level 2 — Substantive, Level 3 — Wired)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/subagent-runtime/src/subagent_runtime/trace_io.py` | Shared trace-record writer + cost helper | ✓ VERIFIED | 114 LOC, `write_trace_record` (lines 29-88) + `_compute_cost_usd` (lines 91-113). Imports `from typing import Any` (used), `json`, `logging`, `time`, `Path`. Defensive `isinstance(meta, dict)` guard at line 64. Lazy eval-harness pricing import at line 109. Imported and called by pool.py:39, ingest.py:33, query.py:47. WIRED. |
| `packages/subagent-runtime/src/subagent_runtime/pool.py` | `_write_trace` delegates to trace_io | ✓ VERIFIED | Line 39 imports `write_trace_record`. `_write_trace` (lines 184-199) is the thin delegate. Pool's batch terminal writer remains inline (lines 201-233). |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py` | Per-call trace records on success + error | ✓ VERIFIED | Line 33 imports `write_trace_record`. Two call sites at lines 452 (success path) + 464 (error path). |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` | Synth trace at both call sites + tokens threaded into summary | ✓ VERIFIED | Line 47 imports `write_trace_record`. `_extract_usage_tokens` helper (line 279) with isinstance(dict) guard (mirrors trace_io). Synth trace writes at lines 536 (code-fallback path) + 972 (regular path). Summary record at line 1054 threads `tokens_in` field. Filename convention: `synth_{query_id}.jsonl` (matches D-04 decision). |
| `agents/code-wiki-agent/tests/integration/test_trace_coverage.py` | Gated TRACE-FU-01 regression | ✓ EXISTS, ⚠ NOT EXECUTED | 106 LOC. Canonical INTEGRATION_GATE (lines 26-29). Asserts `tokens_in/tokens_out is not None` on every non-error / non-event record. SKIPPED in current test run. Real-Bedrock execution required for SC#1 literal contract. |
| `agents/code-wiki-agent/tests/test_ingest_trace_unit.py` | Fast unit (no Bedrock) | ✓ VERIFIED | 2 tests PASS in 0.31s (with sibling query trace unit tests). |
| `agents/code-wiki-agent/tests/test_query_trace_unit.py` | Fast unit (no Bedrock) | ✓ VERIFIED | 3 tests PASS. |
| `packages/subagent-runtime/tests/test_trace_io.py` | 3 unit tests for shared helper | ✓ VERIFIED | 3 tests PASS. |
| `packages/prompt-sources/agents/code_reader.md` | Canonical code_reader spec | ✓ VERIFIED | 4931 bytes (May 19 10:32). Anchors CR-001..CR-004 source_anchor URIs. |
| `packages/prompt-sources/agents/synthesizer.md` | Canonical synthesizer spec | ✓ VERIFIED | 5409 bytes. Anchors SYN-001..SYN-004 source_anchor URIs. |
| `packages/eval-harness/src/eval_harness/divergence/code_reader.py` | CR-001..CR-004 checks | ✓ VERIFIED | 129 LOC. 3 hard + 1 soft DivergenceCheck instances. Imported in `divergence/__init__.py:26`. Exported via `CODE_READER_CHECKS` keyed under `ROLE_CHECKS["code_reader"]`. WIRED. |
| `packages/eval-harness/src/eval_harness/divergence/synthesizer.py` | SYN-001..SYN-004 checks | ✓ VERIFIED | 134 LOC. Same structure. WIRED via `ROLE_CHECKS["synthesizer"]`. (See WR-01 / WR-02 / WR-03 in 16-REVIEW.md for narrow regex tightness gaps in CR-001 / CR-003 / SYN-002 — flagged but not blockers for SC#2.) |
| `packages/eval-harness/src/eval_harness/divergence/rubrics/code_reader.md` | Judge rubric | ✓ VERIFIED | 1883 bytes. Registered in `ROLE_RUBRICS["code_reader"]`. |
| `packages/eval-harness/src/eval_harness/divergence/rubrics/synthesizer.md` | Judge rubric | ✓ VERIFIED | 1881 bytes. Registered in `ROLE_RUBRICS["synthesizer"]`. |
| `packages/eval-harness/src/eval_harness/two_gate.py` (modified) | ROLES_WITH_DIVERGENCE expanded to 6 | ✓ VERIFIED | Line 35-37: `frozenset({"librarian", "ingestor", "linter", "scanner", "code_reader", "synthesizer"})`. Comment block on line 33-34 documents D-08 supersession. |
| `eval/cases/code_reader_cases.json` (modified) | 3 → 6 cases | ✓ VERIFIED | 6 cases on disk (verified by reading file). Cases 01-03 byte-identical to baseline; 04-06 target workspace-io.config, vault_io.wiki_search, vault_io.lint_wiki. |
| `packages/eval-harness/tests/test_models_toml_sweep_candidates.py` (modified) | Relaxed `5 <= len <= 6` + superset assertion | ✓ VERIFIED | Line 167: `assert 5 <= len(cases) <= 6`. Line 180: `assert case_ids >= {"code-reader-01", "code-reader-02", "code-reader-03"}`. (Note: IN-07 in 16-REVIEW.md — module docstring line 10 still says "3 vault-thin cases" — INFO not blocking.) |
| `packages/eval-harness/tests/fixtures/post-rebrand-vault/` | 6 post-rebrand package pages, no lattice symbols | ✓ VERIFIED | 6 package directories present (eval-harness, model-adapter, prompt-sources, subagent-runtime, vault-io, workspace-io). `test_fixture_vault_contains_no_lattice_symbols` PASS. |
| `packages/eval-harness/tests/test_scanner_regression.py` | Forward-CI scanner regression | ✓ VERIFIED | 83 LOC. 8/8 tests PASS (2 structural + 6 parametrized hard-rule). |
| `docs/cancellation.md` (modified) | §4–§5 refreshed with event-driven trigger | ✓ VERIFIED | §4 cites langchain-aws#663 + aioboto3 URLs verbatim with re-confirmed-2026-05-19 date. §5 has the verbatim event-driven trigger paragraph (lines 211-213). Calendar phrasing "v1.2+" removed (replaced with event-driven). |
| `docs/testing.md` | Canonical INTEGRATION_GATE doc | ✓ VERIFIED | 105 LOC. 5 sections: spec basis / pattern / canonical block / inventory / future. Inventory table at §4 includes the `test_mcp_cancel` allowlist row with rationale. |
| `tests/test_integration_gate.py` | Grep-gate meta-test | ✓ VERIFIED | 72 LOC. Post-merge fix a530ddb verified in current code (lines 43-44 exclude `.claude/worktrees/`). Meta-test PASS. |
| `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` | Canonical INTEGRATION_GATE decorator | ✓ VERIFIED | Line 32 defines INTEGRATION_GATE; line 39 applies `@INTEGRATION_GATE`. |
| `agents/code-wiki-agent/tests/integration/test_mcp_cancel.py` | `# integration-gate-allow` marker | ✓ VERIFIED | Line 3 carries the marker with rationale. |
| `packages/model-adapter/tests/test_loader.py` (modified) | synthesizer model_id assertion + QWEN_SYNTHESIZER_ARN constant | ✓ VERIFIED | Line 17 declares `QWEN_SYNTHESIZER_ARN = "qwen.qwen3-32b-v1:0"`. Lines 135-136 assert literal AND constant. Test PASS. |

All 17 created files exist; all 13 modified files match the planned changes.

---

## Key Link Verification (Wiring)

| From | To | Via | Status | Detail |
|------|----|----|--------|--------|
| `pool.py:_write_trace` | `trace_io.write_trace_record` | import line 39 + delegate at line 197 | ✓ WIRED | Single canonical call site; cost computation co-located in trace_io. |
| `ingest.py` per-call trace | `trace_io.write_trace_record` | import line 33 + calls at 452/464 | ✓ WIRED | Success + error paths both write records. |
| `query.py` synth trace | `trace_io.write_trace_record` | import line 47 + calls at 536/972 | ✓ WIRED | Code-fallback + regular synth paths both write records. |
| `query.py` summary record | `_extract_usage_tokens` → `summary_record["tokens_in"]` | helper at line 279 → record build at line 1054 | ✓ WIRED | Synth tokens flow into the top-level query_summary record. |
| `two_gate.score_two_gate` | code_reader + synthesizer divergence | `ROLES_WITH_DIVERGENCE` frozenset includes both; metric loaded via `divergence_metric_or_none` | ✓ WIRED | Both roles now go through Gate 1; superseded D-08 skip. |
| `ROLE_CHECKS` registry | `CODE_READER_CHECKS` / `SYNTHESIZER_CHECKS` | `divergence/__init__.py:26-31,35-42` | ✓ WIRED | Both lists registered; rubrics path registered alongside. |
| `tests/test_integration_gate.py` grep gate | every `**/tests/integration/test_*.py` | rglob walk at line 39 with worktrees exclusion at line 43-44 | ✓ WIRED | Post-merge fix a530ddb confirmed in current source. |
| `test_loader.py::test_load_role_config_synthesizer_limits` | `load_role_config("synthesizer")` from `model_adapter.loader` | direct import line 130 + literal assertion line 135 | ✓ WIRED | Drift trips the test loudly. |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Critical phase-16 tests pass | `uv run pytest tests/test_integration_gate.py packages/model-adapter/tests/test_loader.py::test_load_role_config_synthesizer_limits packages/eval-harness/tests/test_scanner_regression.py packages/eval-harness/tests/test_models_toml_sweep_candidates.py::test_code_reader_cases_json_loads packages/subagent-runtime/tests/test_trace_io.py agents/code-wiki-agent/tests/test_ingest_trace_unit.py agents/code-wiki-agent/tests/test_query_trace_unit.py -v` | 19 passed in 0.66s | ✓ PASS |
| Full non-integration suite green | `uv run pytest -x -q --ignore=agents/code-wiki-agent/tests/integration --ignore=packages/subagent-runtime/tests/integration` | 549 passed, 22 skipped in 34.55s | ✓ PASS |
| `ROLES_WITH_DIVERGENCE` covers all 6 | `python -c "from eval_harness.two_gate import ROLES_WITH_DIVERGENCE; assert len(ROLES_WITH_DIVERGENCE) == 6"` (verified by reading source) | frozenset of 6 in two_gate.py:35-37 | ✓ PASS |
| Gated TRACE-FU-01 regression runs against real Bedrock | `CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v` | `1 passed in 14.02s` (2026-05-19, after 16-02 pool contract fix + test self-isolation) | ✓ PASS (re-run 2026-05-19 after 16-02 pool contract fix) |
| Live model-sweep produces actual code_reader scores | `uv run --package eval-harness python -m eval_harness.sweep --role code_reader ...` | NOT executed (judgment call per D-12) | ? SKIP — routed to human verification items 2 + 4 |

---

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| TRACE-FU-01 | Production trace pipeline emits `usage_metadata` on every JSONL record | ✓ SATISFIED (code) / ? NEEDS HUMAN (real-Bedrock regression) | trace_io.py + pool/ingest/query call sites + 8 unit tests PASS. SC#1 literal real-fan-out test deferred to human. |
| SWEEP-FU-02 | DivergenceMetric wired through full sweep matrix (all in-scope roles) | ✓ SATISFIED | ROLES_WITH_DIVERGENCE = 6 roles; ROLE_CHECKS / ROLE_RUBRICS keyed on all 6. |
| SWEEP-FU-03 | code_reader cases re-tuned against current fixture corpus | ✓ SATISFIED (structural) / ? NEEDS HUMAN (non-trivial scores) | 6 cases on disk; tags + structure validated. Score-producing run not executed. |
| SWEEP-FU-04 | Scanner re-swept against fresh-package vault (regression test post-port) | ✓ SATISFIED (structural) / ? NEEDS HUMAN (live model-sweep) | Synthetic fixture 8/8 PASS; live-vault SCANNER_CHECKS substitution documented. |
| MCP-CAN-01 | Real DA-CLI wire-level cancel verified OR deferral re-documented | ✓ SATISFIED (RE-DEFERRED) / ? NEEDS HUMAN (event-driven trigger acceptance) | docs/cancellation.md §4-§5 refreshed; event-driven trigger replaces calendar date. |
| MCP-CAN-02 | Opt-in gate consistency reviewed across MCP tools | ✓ SATISFIED | docs/testing.md + grep-gate meta-test + canonical refactors. |
| MODEL-FU-01 | `test_load_role_config_synthesizer_uses_sonnet` fixed to match Qwen reality | ✓ SATISFIED | test_load_role_config_synthesizer_limits asserts qwen.qwen3-32b-v1:0; full suite green. |

No orphaned requirements — all 7 IDs declared in PLAN frontmatter and all 7 mapped to Phase 16 in REQUIREMENTS.md.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `divergence/synthesizer.py` | 19, 50-60 | SYN-002 slug-only regex matches PascalCase only — `[[bedrock]]` / `[[subagent-pool]]` slip past | ⚠ Warning (per 16-REVIEW.md WR-01) | Narrower than the prompt rule it enforces. Does not block SC#2 — the check is registered and called; the regex is just narrower than ideal. |
| `divergence/code_reader.py` | 21-23, 31, 71-82 | CR-003 lookbehind permits `vault/.code-wiki/foo`; CR-001 path:line requires `/` separator | ⚠ Warning (per 16-REVIEW.md WR-02/WR-03) | False-negative on bare-filename `pool.py:115` path:line annotations. Not a blocker — checks exist + run. |
| `integration/test_trace_coverage.py` | 88-95 | Asserts `tokens_in/tokens_out is not None` on all `query_summary` records — but code-fallback empty/empty legitimately writes None | ⚠ Warning (per 16-REVIEW.md WR-04) | Could trigger a spurious failure on a thin-vault run. Cited in 16-REVIEW.md; not corrected in Phase 16. |
| `commands/query.py` | 283-286 | Stale docstring points to `pool._write_trace:203-209` after D-04 extraction | ℹ Info (per IN-01) | Documentation drift only. |
| `divergence/metric.py` | 31 | Unused `from typing import Union` import | ℹ Info (per IN-03) | Dead import. |
| `test_models_toml_sweep_candidates.py` | 10 | Module docstring still says "3 vault-thin fixture cases" but file has 6 + assertion is `5 <= len <= 6` | ℹ Info (per IN-07) | Documentation drift only. |
| `docs/cancellation.md` | 103-115, 121-131 | Example JSON blocks omit `schema_version: 1` field | ℹ Info (per IN-08) | Doc example incompleteness; production code writes the field correctly. |

**Debt markers scan:** no `TBD` / `FIXME` / `XXX` markers in any phase-16 created/modified file (verified by inspection — none appear in the listed files).

No blocker-tier anti-patterns. The warning-tier findings are scope-acknowledged in 16-REVIEW.md and do not invalidate the phase's must-haves.

---

## Human Verification Required

See `human_verification` block in frontmatter for full details. Summary:

### 1. Run the gated TRACE-FU-01 regression against real Bedrock

**Test:** `CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v`
**Expected:** Exit 0; every non-error / non-event JSONL record from the round-trip fixture vault has `tokens_in != None` and `tokens_out != None`.
**Why human:** SC#1 literal wording requires "a regression test that runs a real fan-out". The test exists + is correctly wired; only a human can opt in to incur Bedrock cost.

### 2. Accept judgment-driven substitution for SC#2 live model-sweep

**Test:** Confirm or reject the documented two-baseline split (forward-CI synthetic fixture + deterministic SCANNER_CHECKS on live vault) as sufficient evidence for "no regression vs. v1.1 baseline" without running `run_role_sweep` against `~/Personal/wiki/deep-agents`.
**Expected:** Pat's explicit ack that the 7 SCN-002/SCN-003 failures (structural mismatch — rules target raw LLM stub output, on-disk pages contain pipeline-appended `## File map`) are NOT a v1.1→v1.2 regression.
**Why human:** Documented as a scope-down decision in SUMMARY ("Scoped-down items"); requires explicit operator acceptance.

### 3. Accept event-driven re-eval trigger in place of calendar date (SC#3)

**Test:** Confirm `docs/cancellation.md` §5 paragraph ("Re-evaluate when langchain-aws cuts a release with #663 merged, OR when aioboto3 reaches a named milestone (GA / 1.0)") is acceptable in place of SC#3's literal "fresh re-evaluation **date**".
**Expected:** Pat's explicit ack of the D-09 calendar-vs-event choice.
**Why human:** Deliberate deviation from SC literal wording; D-09 rationale (calendar re-checks generated noise) makes this an editorial judgment call.

### 4. Accept structural evidence in place of code_reader non-trivial scores (SC#2 sub-clause)

**Test:** Confirm cases 04-06 of `eval/cases/code_reader_cases.json` (each phrased to force code-fallback path against post-rebrand surfaces) constitute acceptable evidence in lieu of running an actual sweep producing numeric scores.
**Expected:** Pat's explicit ack.
**Why human:** SUMMARY documents the scope-down; operator judgment on sufficiency required.

---

## Audit of Pre-Populated 16-VERIFICATION.md

The executor wrote a 16-VERIFICATION.md (as commit `c217cc2`) during plan 16-01 step D-12. Audit findings:

- **Accurate factually:** Every artifact path, line number, commit hash, and test transcript in the prior VERIFICATION.md was independently verified against current source. The 5-test fast-unit transcript was reproduced (along with sibling tests — 19 total PASS).
- **Missing frontmatter:** Prior version lacked the required YAML frontmatter (`phase`, `verified`, `status`, `score`, `human_verification`). This rewrite adds it.
- **Status discrepancy:** Prior version was implicit "PASS" (no explicit status field). True status is `human_needed` because SC#1 explicitly requires a real-fan-out regression test that was NOT executed, and SC#2 + SC#3 each contain deliberate judgment-driven substitutions that require operator acknowledgment per verifier policy (Step 9 decision tree: any human verification items → `human_needed`, not `passed`).
- **Post-merge fix verified:** Commit a530ddb (`tests/test_integration_gate.py:43-44` excludes `.claude/worktrees/`) confirmed in current code; meta-test runs green against the live working tree.

---

## Gaps Summary

No FAILED truths and no missing/stub artifacts. All 5 ROADMAP success criteria have substantive code evidence. The phase-goal narrative ("debt items resolved OR explicitly re-deferred with documented justification") is achieved on every REQ-ID — six COMPLETE with code + tests, one RE-DEFERRED (MCP-CAN-01) with documented blocker + event-driven trigger.

The phase status is `human_needed` (not `passed`) because three SCs contain literal-text clauses that were satisfied with judgment-driven substitutions (real-Bedrock regression run skipped; live model-sweep substituted with deterministic checks; calendar-date replaced with event-driven trigger). Per the verifier decision tree, human verification items take priority over `passed` even when all truths are VERIFIED.

---

_Verified: 2026-05-19_
_Verifier: Claude (gsd-verifier)_

---

## G-01 Closure (Phase 16-02)

Plan 16-02 closed gap G-01 (librarian fan-out trace records emitting None tokens) via a two-layer fix:

- **Pool contract extension:** `SubagentPool.run_all` now recognizes an opt-in `TaskResult(value=..., response=...)` return shape from task callbacks. When detected via `isinstance`, the pool unwraps `result.value` into `FanOutResult.successes` (preserving the existing scalar contract for downstream consumers) AND passes `result.response` to `write_trace_record` (so `response.usage_metadata` flows into the JSONL trace). Scalar returns continue to work unchanged. Commit `e97ae7f` (`feat(16-02): extend SubagentPool task contract with TaskResult ...`).
- **Callsite migration:** All 4 production fan-out callbacks now return `TaskResult` — `query.drill_page`, `query.code_drill` (both terminal paths), `scan.generate_stub`, `lint.run_linter_group` (both terminal paths). Commit `629f077` (`fix(16-02): wrap fan-out callbacks in TaskResult ...`).
- **Test self-isolation:** `agents/code-wiki-agent/tests/integration/test_trace_coverage.py` now `shutil.rmtree`s the copied `.code-wiki/traces` directory immediately after `copytree`, so the assertion only walks records produced by the current run. (Fixture-side deletion of the v0 trace JSONLs was attempted but reverted — they are load-bearing for `test_trace_viewer.py::test_v0_real_fixture_renders_and_warns_once` D-04 fixture.) Commit `4df6ace` (`fix(16-02): self-isolate TRACE-FU-01 test from stale fixture traces ...`).
- **Bedrock re-run:** `CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v` → `1 passed in 14.02s` on 2026-05-19. Librarian success records emit non-None `tokens_in` / `tokens_out` / `cost_usd`; G-01 fully closed.
- **Plan reference:** See `.planning/phases/16-carry-forward-debt-cleanup/16-02-PLAN.md` and `16-02-SUMMARY.md` for the full rationale + commit chain.
