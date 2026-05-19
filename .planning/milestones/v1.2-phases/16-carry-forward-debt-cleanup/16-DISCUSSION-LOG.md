# Phase 16: Carry-Forward Debt Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 16-carry-forward-debt-cleanup
**Areas discussed:** MCP cancel direction (SC#3), Trace coverage scope (SC#1), Sweep matrix expansion (SC#2), Plan structure + MODEL-FU-01 + gate-consistency (SC#4/SC#5)

---

## MCP cancel direction (SC#3 / MCP-CAN-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Re-document deferral | Refresh `docs/cancellation.md §4–§5` with current blocker + re-evaluation date. No code change. | |
| Pursue real wire-level cancel | Add aioboto3/aiobotocore, swap ChatBedrockConverse internals, end-to-end cancel test. | |
| Spike then decide | Half-day spike to check aioboto3/langchain-aws#663 status and feasibility, then pursue or re-document inside this phase. | ✓ |

**User's choice:** Spike then decide.
**Notes:** Avoids prematurely closing the requirement before checking what's actually changed upstream since Phase 8.

### Spike decision criteria

| Option | Description | Selected |
|--------|-------------|----------|
| Upstream-merged only | Pursue only if langchain-aws#663 has landed in a released langchain-aws version. | |
| Working aioboto3 path exists | Pursue if a clean integration path exists (aioboto3 + adapter we own, OR a langchain-aws PR we can vendor). | ✓ |
| Time-box the spike (1 day max) | If wire-level cancel isn't demonstrably working at end of day, re-document. | |

**User's choice:** Working aioboto3 path exists.
**Notes:** Captured as D-08. The gate measures feasibility-with-acceptable-maintenance, not waiting for upstream to do all the work.

### If re-document: re-evaluation trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Calendar date — 2026-Q4 | Set next re-evaluation for 2026-10-01. | |
| Upstream signal | Re-evaluate when langchain-aws cuts a release with #663 merged, OR when aioboto3 hits a named milestone (GA/1.0). | ✓ |
| Next milestone (v1.3) | Tie re-evaluation to whenever v1.3 planning starts. | |

**User's choice:** Upstream signal.
**Notes:** Captured as D-09. Event-driven trigger re-opens cancel work exactly when the blocker dissolves.

### MCP-CAN-02 — gate rule home

| Option | Description | Selected |
|--------|-------------|----------|
| `docs/testing.md` (new) | Sibling to docs/cancellation.md as central rule + grep gate. | ✓ |
| Inline in CLAUDE.md | Top-level CLAUDE.md "Testing conventions" section. | |
| Both — CLAUDE.md links to docs/testing.md | Detail in docs/testing.md; CLAUDE.md carries a one-line pointer. | |

**User's choice:** docs/testing.md (new).
**Notes:** Captured as D-10. Matches existing docs/ shape (cancellation.md, trace-schema.md).

---

## Trace coverage scope (SC#1 / TRACE-FU-01)

| Option | Description | Selected |
|--------|-------------|----------|
| All LLM call sites | Every Bedrock invocation in production code writes a trace record with input/output tokens. | ✓ |
| Pool path only + audit | Refactor non-pool sites to go through SubagentPool. Single trace writer. | |
| Per-record fields, not surface | Define contract narrowly: every record currently written must have tokens_in/tokens_out. | |

**User's choice:** All LLM call sites.
**Notes:** Captured as D-03. Gap inventory: ingest.py:438 writes no trace; query.py:977 query_summary missing usage fields; pool fan-out already correct.

### Writer shape

| Option | Description | Selected |
|--------|-------------|----------|
| Extract pool writer into shared helper | Pull SubagentPool._write_record into trace_io helper; all sites call it. | ✓ |
| Inline writers, same schema | Each site writes own JSONL record with agreed schema. | |
| Route all LLM calls through pool | Refactor ingest.py to use SubagentPool even for single calls. | |

**User's choice:** Extract pool writer into shared helper.
**Notes:** Captured as D-04. Eliminates the drift surface (different writers diverging) rather than fixing only today's instances.

### Regression test shape

| Option | Description | Selected |
|--------|-------------|----------|
| Real fan-out + assert field | Run real scan/ingest/query (gated by CODE_WIKI_RUN_INTEGRATION) against tmp_path vault; parse JSONL; assert non-None tokens on every record. | ✓ |
| Stub LLM + assert writer called | Mock ChatBedrockConverse; drive command functions; parse trace files. Zero Bedrock cost. | |
| Static grep gate + integration test | (a) grep ChatBedrockConverse outside helper fails build; (b) one real-fan-out integration test. Belt + braces. | |

**User's choice:** Real fan-out + assert field.
**Notes:** Captured as D-05. Matches SC#1's literal wording: "a regression test that runs a real fan-out."

---

## Sweep matrix expansion (SC#2 / SWEEP-FU-02/03/04)

### SWEEP-FU-02 — DivergenceMetric across full matrix

| Option | Description | Selected |
|--------|-------------|----------|
| All 6 in-scope roles | Add divergence rubrics for code_reader + synthesizer (currently 4 roles). All 6 become Gate 1 participants. | ✓ |
| All 6 — but rubrics minimal | Add code_reader + synthesizer rubrics as minimum-viable, not Phase-6-rich. | |
| Document why 4 is correct | If synthesizer + code_reader inherently can't use programmatic divergence, document and lock at 4. | |

**User's choice:** All 6 in-scope roles.
**Notes:** Captured as D-06. Pat wants real signal at Phase-6 EVAL-11..13 rigor, not tick-box minimum rubrics.

### SWEEP-FU-03 — code_reader case retuning

| Option | Description | Selected |
|--------|-------------|----------|
| Verify current 3 still work | Run sweep against existing 3 cases; fix if they fail; no expansion. | |
| Expand to 5-6 cases + retune | Add 2-3 new vault-thin cases reflecting post-rebrand surface; retune all. | ✓ |
| Wholesale rewrite | Replace code_reader_cases.json with fresh set authored against today's codebase. | |

**User's choice:** Expand to 5-6 cases + retune.
**Notes:** Captured as D-07. Targets for new cases: workspace-io, graph-wiki plugin, ported vault-io.lint_wiki / vault-io.wiki_search.

### SWEEP-FU-04 — scanner re-sweep target

| Option | Description | Selected |
|--------|-------------|----------|
| Use ~/Personal/wiki/deep-agents (post-Phase 15) | Re-sweep against live wiki vault. Real-world signal. | |
| Build synthetic fixture vault | Author tmp_path fixture mirroring fresh post-rebrand shape. Reproducible, CI-runnable. | |
| Both — fixture for CI, live for milestone evidence | Synthetic fixture for pytest regression; manual live-vault re-sweep into 16-VERIFICATION.md. | ✓ |

**User's choice:** Both — fixture for CI, live for milestone evidence.
**Notes:** Captured as D-11. Mirrors Phase 15 D-08/D-09 pattern.

### Cost ceiling

| Option | Description | Selected |
|--------|-------------|----------|
| Hard cap — $5 total | Cheap fan-out only; preflight abort if exceeded. | |
| Hard cap — $25 total | Broader sweep coverage; preflight + abort at $25. | |
| No cap — budget by judgement | Trust preflight estimator + Pat's review of dry-run plan. No hard abort. | ✓ |

**User's choice:** No cap — budget by judgement.
**Notes:** Captured as D-12. Aligns with [[user_cost_optimization]] "measure it" mindset; v1.2 close-out evidence is worth measured spend.

---

## Plan structure + MODEL-FU-01 + gate-consistency (SC#4/SC#5)

### MODEL-FU-01 — what's actually missing?

Pre-question state captured: The named test `test_load_role_config_synthesizer_uses_sonnet` no longer exists — already renamed to `test_load_role_config_synthesizer_limits` during prior v1.1 work. Current bundled `models.toml` has `synthesizer.model_id = "qwen.qwen3-32b-v1:0"`.

| Option | Description | Selected |
|--------|-------------|----------|
| Add model_id assertion to current test | Extend `_limits` test with `cfg['model_id'] == 'qwen.qwen3-32b-v1:0'`. | ✓ |
| Add separate model_id test per role | Parameterized test asserting model_id for every role in models.toml. | |
| Close the requirement as already-satisfied | Mark MODEL-FU-01 done; document resolution in 16-VERIFICATION.md. | |

**User's choice:** Add model_id assertion to current test.
**Notes:** Captured as D-13. Locks current Qwen default so any future silent swap fails the test.

### Phase 16 plan structure

| Option | Description | Selected |
|--------|-------------|----------|
| 4 themed plans | One per theme (trace, sweep, cancel, model+verification). Each independent; parallelizable. | |
| 1 bundled atomic plan | Everything in one SUMMARY family with per-step commits. Matches Phase 14 Plan 3 / Phase 15 D-10. | ✓ |
| 2 plans — code + docs | All code in plan 1; all docs in plan 2. | |

**User's choice:** 1 bundled atomic plan.
**Notes:** Captured as D-14. All items mechanical/maintenance-grade and individually small; splitting adds overhead without benefit.

---

## Claude's Discretion

- Exact home for the trace helper (`subagent_runtime/trace_io.py` vs. module-level in `pool.py` vs. new tiny package).
- Exact form of `CODE_WIKI_RUN_INTEGRATION` grep gate (Bash script vs. pytest meta-test).
- Exact content of new `code_reader` + `synthesizer` divergence rubrics (rule count, rule shape).
- Exact case text and case_ids for the 2–3 new `code_reader` cases.
- Synthetic fixture vault location (`packages/eval-harness/tests/fixtures/` vs. repo-level `tests/fixtures/`).
- Cancel spike write-up form (inline in `16-VERIFICATION.md` vs. separate spike artifact).
- Whether the live-vault re-sweep happens inside the bundled plan or as a final post-plan step.

## Deferred Ideas

(See `16-CONTEXT.md` `<deferred>` section for the full list; key entries:)
- Real `aioboto3` integration (if spike gate fails) — re-evaluated on upstream signal per D-09.
- SIGINT / stdin-close fallback cancel paths — stays on `docs/cancellation.md §5` v1.2+ list.
- Hard cost cap for sweep runs — rejected by D-12; could land in v1.3 if overrun pattern emerges.
- Wholesale rewrite of `code_reader_cases.json` — rejected by D-07.
- Per-role model_id parameterized test — rejected by D-13 in favor of single targeted assertion.
- Trace schema extensions (cache-hit telemetry, multi-turn aggregation) — schema stays at v1.
- Cross-surface (Bedrock vs Claude Code) cancel behavior comparison — plugin runs on Claude Code; out of Bedrock-side Phase 16.
