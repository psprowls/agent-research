# Phase 19: Phase 16 Code Review Burndown - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Triage every Phase 16 code review finding (6 warnings + 9 info, 0 critical) on the trace pipeline + eval-harness refactor and land each as a code fix, a documented dismissal, or a follow-up todo. Outcome of triage is recorded in a phase-local 19-REVIEW-BURNDOWN.md disposition table so future code review can verify the debt is not re-accumulating.

**In scope:**
- 13 code/doc/test fixes locked at discuss-time (see Implementation Decisions)
- 2 no-action dispositions (IN-02, IN-05 — review self-corrected on re-scan; current code is correct)
- One phase-local disposition table at `.planning/phases/19-phase-16-code-review-burndown/19-REVIEW-BURNDOWN.md`
- Each fix proven against the existing test suite (no new regression tests authored for this phase)

**Out of scope:**
- New tests beyond what existing fixtures already exercise (fix-only test policy)
- Touching findings outside the original 16-REVIEW.md (no scope creep onto adjacent code)
- Editing the archived 16-REVIEW.md at `.planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/` (left as historical record; back-pointer not required)
- Re-litigating WR-06's "macOS/Linux only" debate — decision is locked: switch to `Path.is_relative_to` for codebase-idiom convergence

</domain>

<decisions>
## Implementation Decisions

### Triage Outcomes (all 15 findings disposed)

**Warnings (6 of 6 → Fix as proposed):**
- **D-01 (WR-01):** Replace `_SLUG_ONLY_RE` in `packages/eval-harness/src/eval_harness/divergence/synthesizer.py` with a "no `/` in target" check. Closes the lowercase/hyphenated slug gap (`[[bedrock]]`, `[[subagent-pool]]` currently pass).
- **D-02 (WR-02):** Update `_GRAPH_WIKI_PREFIX_RE` lookbehind in `packages/eval-harness/src/eval_harness/divergence/code_reader.py:31` to `(?<![A-Za-z0-9_-])\.graph-wiki/` so inline path references like `vault/.graph-wiki/...` are caught.
- **D-03 (WR-03):** Drop the `/` requirement from `_PATH_LINE_RE` in `code_reader.py:21-23` so bare-filename citations (`pool.py:115`) qualify as `path:line`. Align with synthesizer's permissive regex.
- **D-04 (WR-04):** Exempt the disclaimer/empty-fallback path in `agents/graph-wiki-agent/tests/integration/test_trace_coverage.py:88-95` — when `tokens_in is None and tokens_out is None`, count the record and continue (mirrors the existing error-record exemption).
- **D-05 (WR-05):** Hoist `inspect.signature(task)` out of `_run_one` in `packages/subagent-runtime/src/subagent_runtime/pool.py:133-137`; compute once with `try/except (ValueError, TypeError)` falling back to single-arg form.
- **D-06 (WR-06):** Switch `_route_target_path` in `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:101-106` to `Path.is_relative_to`. Not a runtime bug today (project is macOS/Linux only) but converges the codebase on the idiom already used by `query.py:356`.

**Info findings (7 of 9 → Fix; 2 → No-action):**
- **D-07 (IN-01):** Update stale docstring in `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:283-286` to point at `subagent_runtime.trace_io.write_trace_record:56-66` (the canonical home post-D-04 extraction).
- **D-08 (IN-02):** No-action. Review self-corrected on re-scan; `Any` is used in `trace_io.py`. Record as "dismissed — review self-corrected" in 19-REVIEW-BURNDOWN.md.
- **D-09 (IN-03):** Remove unused `from typing import Union` in `packages/eval-harness/src/eval_harness/divergence/metric.py:31` (module uses PEP-604 `A | B` syntax elsewhere).
- **D-10 (IN-04):** Add `caplog`-based assertion to `test_write_trace_record_swallows_oserror` in `packages/subagent-runtime/tests/test_trace_io.py` verifying the WARNING-level log the docstring promises. Drops nothing; strengthens the contract.
- **D-11 (IN-05):** No-action. Review self-corrected; `pytest` is legitimately used by `pytest.raises(BotoCoreError)`. Record as "dismissed — review self-corrected" in 19-REVIEW-BURNDOWN.md.
- **D-12 (IN-06):** Qualify synth trace filenames so the code-fallback and regular-path synth calls write to distinguishable files: `synth_librarian_{query_id}.jsonl` (regular path, `query.py:968`) and `synth_codefallback_{query_id}.jsonl` (`query.py:532`). Cheap insurance against future retry-after-fallback collisions.
- **D-13 (IN-07):** Update module docstring in `packages/eval-harness/tests/test_models_toml_sweep_candidates.py:10` from "3 vault-thin cases" to match the asserted 5–6 range.
- **D-14 (IN-08):** Add `"schema_version": 1,` to both example JSON blocks in `docs/cancellation.md:103-115,121-131` so doc readers building a trace consumer produce schema-complete writers.
- **D-15 (IN-09):** Refactor `apply_guardrails` in `query.py:663-670` to call `_compute_unresolved_wikilinks` (lines 551-570) instead of duplicating the G1 resolution algorithm inline. Drift bait removed.

### Plan Granularity
- **D-16:** Group the 13 fixes into ~4 plans by code area. The planner is expected to land on a split close to:
  1. **Divergence eval regex fixes** — D-01 (WR-01), D-02 (WR-02), D-03 (WR-03) — all in `packages/eval-harness/src/eval_harness/divergence/`.
  2. **Core runtime fixes** — D-05 (WR-05) in `packages/subagent-runtime/`, D-06 (WR-06) in `agents/graph-wiki-agent/.../commands/ingest.py`.
  3. **Test + integration fixes** — D-04 (WR-04), D-09 (IN-03), D-10 (IN-04), D-13 (IN-07). All test-suite or test-adjacent edits.
  4. **Query trace + docs cleanup** — D-07 (IN-01), D-12 (IN-06), D-14 (IN-08), D-15 (IN-09). Touch `query.py` and `docs/cancellation.md`.

  Planner may adjust if a different grouping yields cleaner per-plan commits, but should not split below ~3 plans (consolidation hurts blame) or above ~5 (over-fragmentation for a maintenance phase).

### Recording Surface
- **D-17:** Create `.planning/phases/19-phase-16-code-review-burndown/19-REVIEW-BURNDOWN.md` as the canonical disposition table. Columns: finding id (WR-01..06, IN-01..09), severity, file:line, disposition (fixed / dismissed / deferred / no-action), commit SHA (filled at execute time), notes. The archived `.planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/16-REVIEW.md` is **not** edited (stays as historical record). The phase SUMMARY.md links to 19-REVIEW-BURNDOWN.md so a future code-review pass on this surface area finds the table.

### Test Policy
- **D-18:** Fix-only. No new regression tests authored solely to demonstrate the fixed failure mode for WR-01..04. Rely on:
  - Existing divergence-eval test suite (`packages/eval-harness/tests/`) to catch regressions in the regex-changed paths.
  - WR-04's fix is itself a test edit (loosening a fragile assertion).
  - Per-commit gate: `uv sync && uv run pytest packages/eval-harness/tests/ packages/subagent-runtime/tests/ agents/graph-wiki-agent/tests/ -m "not integration"` must pass before each plan-final commit.

  Exception path the planner may invoke: if while implementing D-01/D-02/D-03 the planner finds no existing test covers the regex (i.e., a true silent-pass), add one targeted assertion to the existing test file. Do not stand up new test files.

### Claude's Discretion
- Plan-final commit messages, plan filenames, exact ordering within each plan, regression-gate scope per plan — planner decides per existing GSD conventions.
- 19-REVIEW-BURNDOWN.md table column order and markdown styling — executor decides.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Findings source (authoritative)
- `.planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/16-REVIEW.md` — full review report: every finding's file:line, issue narrative, and proposed fix. This is the source-of-truth for what's being burned down.

### Phase scope + success criteria
- `.planning/ROADMAP.md` §"Phase 19: Phase 16 Code Review Burndown" — phase goal + 3 success criteria.
- `.planning/REQUIREMENTS.md` §"Phase 16 Code Review Burndown (REVIEW)" — REVIEW-01 (6 warnings) + REVIEW-02 (9 info) traceability.

### Files touched by the fixes
- `packages/eval-harness/src/eval_harness/divergence/synthesizer.py` (D-01) — `_SLUG_ONLY_RE` definition + use at line 58.
- `packages/eval-harness/src/eval_harness/divergence/code_reader.py` (D-02, D-03) — `_PATH_LINE_RE` at line 21, `_GRAPH_WIKI_PREFIX_RE` at line 31.
- `packages/eval-harness/src/eval_harness/divergence/metric.py` (D-09) — dead `Union` import.
- `packages/subagent-runtime/src/subagent_runtime/pool.py` (D-05) — `_run_one` per-item `inspect.signature` call.
- `packages/subagent-runtime/src/subagent_runtime/trace_io.py` — canonical home of `write_trace_record` (referenced by D-07's docstring fix; not edited).
- `packages/subagent-runtime/tests/test_trace_io.py` (D-10) — `test_write_trace_record_swallows_oserror`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` (D-06) — `_route_target_path` containment check.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (D-07, D-12, D-15) — `_extract_usage_tokens` docstring, synth trace filenames at lines 532 and 968, `_compute_unresolved_wikilinks` vs `apply_guardrails` G1 dedup.
- `agents/graph-wiki-agent/tests/integration/test_trace_coverage.py` (D-04) — query-summary assertion at lines 88-95.
- `packages/eval-harness/tests/test_models_toml_sweep_candidates.py` (D-13) — module docstring at line 10.
- `docs/cancellation.md` (D-14) — trace JSON example blocks at lines 103-115 and 121-131.

### Conventions + gate
- `CLAUDE.md` — universal anti-patterns: no dead code, no unsupported imports, no backwards-compat shims; macOS/Linux-only deployment target (informs WR-06 disposition).
- `scripts/check-brand.sh` — repo grep-gate; not extended for this phase (no new brand surface introduced).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `subagent_runtime.trace_io.write_trace_record` (extracted in Phase 16 D-04) — canonical trace writer; D-07's docstring fix points downstream readers here.
- `Path.is_relative_to` — already used in `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:356`. D-06 reuses the same idiom in `ingest.py`.
- `_compute_unresolved_wikilinks` helper in `query.py:551-570` — D-15 has `apply_guardrails` call this instead of duplicating the algorithm.
- `caplog` pytest fixture pattern — D-10 follows the standard `with caplog.at_level("WARNING")` + `any(... in r.message for r in caplog.records)` shape.
- Existing error-record exemption logic in `test_trace_coverage.py` — D-04 mirrors its structure for the empty/empty disclaimer path.

### Established Patterns
- **Severity discipline:** 0 critical, 6 warning, 9 info — no fix here is load-bearing; per-commit gate scope is unit + non-integration pytest (no live-Bedrock calls).
- **Hard-cut philosophy** (from CLAUDE.md / Phase 21 precedent): no backwards-compat shims for dead imports / stale docstrings — delete or correct in place.
- **`# Source: / # Anchor:` provenance** (from Phase 10 PORT-XX): D-07's docstring fix should restore a correct line reference, not drop the reference entirely.

### Integration Points
- Per-plan commit gate runs against `packages/eval-harness/tests/`, `packages/subagent-runtime/tests/`, and `agents/graph-wiki-agent/tests/ -m "not integration"`. Integration + live-Bedrock paths gated behind existing env flags (`GRAPH_WIKI_RUN_INTEGRATION=1`, `GRAPH_WIKI_RUN_EVAL=1`); not required between plans.
- 19-REVIEW-BURNDOWN.md disposition table is referenced from the phase SUMMARY.md but stands alone — future `/gsd:code-review` passes on this surface can grep for it.

</code_context>

<specifics>
## Specific Ideas

- All 6 warning fixes follow the exact patch the reviewer proposed in 16-REVIEW.md. No re-derivation.
- WR-06 disposition is "Fix as proposed" even though current behavior is correct on macOS/Linux. Locked at discuss-time; do not re-litigate — rationale is "converge on `Path.is_relative_to` idiom already used in `query.py:356`."
- IN-06 disposition is "Fix as proposed" rather than the "dismiss with rationale" alternative because the cost of qualifying the filename is one literal change per call site, while the cost of debugging a future retry-after-fallback collision would be hours.
- IN-02 and IN-05 are explicitly **not** dismissed because of negligence — they're dismissed because the review's own author re-scanned and found the original concern was incorrect. 19-REVIEW-BURNDOWN.md should phrase the disposition that way: "no-action — review self-corrected on re-scan."

</specifics>

<deferred>
## Deferred Ideas

None — every finding from 16-REVIEW.md is dispositioned in this phase. Nothing rolled forward.

</deferred>

---

*Phase: 19-phase-16-code-review-burndown*
*Context gathered: 2026-05-20*
