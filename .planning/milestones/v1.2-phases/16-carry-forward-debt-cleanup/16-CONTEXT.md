# Phase 16: Carry-Forward Debt Cleanup - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Close out the four v1.1 carry-forward debt themes so v1.2 ships clean: production trace `usage_metadata` coverage (TRACE-FU-01), DivergenceMetric + cases + scanner re-sweep across the full matrix (SWEEP-FU-02/03/04), MCP wire-level cancel closure or re-deferral (MCP-CAN-01) plus a single documented `CODE_WIKI_RUN_INTEGRATION` gate rule (MCP-CAN-02), and a model-id assertion fix on the synthesizer config test (MODEL-FU-01). The phase is mechanical/maintenance — every requirement either resolves with code + tests or with explicitly-documented re-deferral evidence.

**In scope:**
- **TRACE-FU-01** — Extract the JSONL trace-record writer from `SubagentPool._write_trace` into a shared helper (in `packages/subagent-runtime/` per D-04). Refactor `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:438` (currently calls `llm.ainvoke` directly, writes no trace) and `commands/query.py:977` (`query_summary` record missing `tokens_in`/`tokens_out`) to use the helper. All production LLM call sites (scan, lint, query fan-out, query synthesizer, query code-fallback, ingest, any future direct invokes) write a JSONL record with `input_tokens` + `output_tokens` from `usage_metadata` (None allowed only on Bedrock error responses, per existing pool guard).
- **TRACE-FU-01 regression test** — Real-fan-out integration test (gated by `CODE_WIKI_RUN_INTEGRATION=1`) runs scan + ingest + query against a tmp_path fixture vault, parses every JSONL file under `.code-wiki/traces/`, asserts every non-error record has non-None `input_tokens` and `output_tokens`. Lives alongside existing `agents/code-wiki-agent/tests/integration/` tests.
- **SWEEP-FU-02** — Add programmatic divergence rubrics for `code_reader` and `synthesizer`; extend `ROLES_WITH_DIVERGENCE` in `packages/eval-harness/src/eval_harness/two_gate.py:36` from the current 4-role frozenset (`librarian, ingestor, linter, scanner`) to all 6 in-scope roles. Rubric depth: match Phase-6 EVAL-11..13 rigor (not minimal-viable).
- **SWEEP-FU-03** — Expand `eval/cases/code_reader_cases.json` from 3 vault-thin cases to 5–6, adding cases that reflect the post-rebrand surface (`workspace-io`, `graph-wiki` plugin, the `vault-io.lint_wiki` / `vault-io.wiki_search` port targets). Retune so every case produces a non-trivial score against the current corpus.
- **SWEEP-FU-04** — Both: (a) build a synthetic post-rebrand fixture vault under `packages/eval-harness/tests/` (or `tests/fixtures/`) for the CI-runnable scanner regression sweep, asserting no regression vs. v1.1 baseline; (b) one manual live-vault re-sweep against `~/Personal/wiki/deep-agents` recorded into `16-VERIFICATION.md` as milestone evidence (mirrors Phase 15 D-08/D-09 transcript pattern).
- **MCP-CAN-01** — Time-bound spike to evaluate aioboto3 / `langchain-aws#663` status. Spike gate (D-08): pursue if a working integration path exists (either a released `langchain-aws` version with native `aioboto3`, OR an `aioboto3` + thin adapter we'd own). If gate fails, refresh `docs/cancellation.md §4–§5` with the current blocker and an **upstream-signal** re-evaluation trigger (D-09): "Re-evaluate when langchain-aws cuts a release with #663 merged, OR when aioboto3 reaches a milestone we can name."
- **MCP-CAN-02** — Author `docs/testing.md` as the single home for the `CODE_WIKI_RUN_INTEGRATION` opt-in gate rule (D-10). Document the canonical skip-decorator pattern, list every gated file, include a grep gate (script or test) that fails the build if a future test diverges from the pattern.
- **MODEL-FU-01** — Extend `packages/model-adapter/tests/test_loader.py::test_load_role_config_synthesizer_limits` (current name; was already renamed from `_uses_sonnet` during prior work) to also assert `cfg["model_id"] == "qwen.qwen3-32b-v1:0"`. Locks the current Qwen synthesizer default so future drift fails loudly.
- **`16-VERIFICATION.md`** — Single doc with per-SC sections (#1–#5), citing trace JSONL output, sweep result tables, the cancel spike decision, the `docs/testing.md` grep-gate output, and the synthesizer model_id assertion.

**Out of scope:**
- New trace fields beyond `input_tokens` / `output_tokens` / existing schema (`prompt_hash`, multi-turn aggregation, cache-hit telemetry). Schema stays at `schema_version: 1` unless the helper extraction surfaces an actually-required field change.
- Reshaping the trace JSONL schema or path layout (`.code-wiki/traces/`); helper extraction is pure refactor.
- Routing all LLM calls through `SubagentPool` (rejected option B on the writer-shape question — pool stays for fan-out; single-call paths use the shared helper directly).
- Real `aioboto3` integration if the spike gate fails — defer per D-08/D-09.
- SIGINT / stdin-close fallback cancel paths (`docs/cancellation.md §5` v1.2+ list); orphan-thread monitoring; per-tool granular E2E cancel tests beyond the existing `wiki_query` one.
- Sweep cost cap / preflight abort. D-12 lets Pat judge per-run against the dry-run estimate.
- Authoring richer divergence rubrics for the existing 4 roles; only `code_reader` + `synthesizer` are new.
- Replacing `code_reader_cases.json` wholesale (rejected option C); preserve the existing 3 cases for baseline comparability.
- Promoting any sweep-discovered model swap as the new default. SWEEP-FU-04's job is regression check + evidence capture, not profile change.
- A separate per-role model_id parameterized test (rejected option B on MODEL-FU-01); single targeted assertion is the locked answer.
- Any work-layer or `archive_work` revival; any UI surface; any new ROADMAP requirement.

</domain>

<decisions>
## Implementation Decisions

### MCP cancel direction (SC#3 / MCP-CAN-01)

- **D-08 (Spike then decide, gated on integration path):** Half-to-one-day spike to assess `langchain-aws#663` and aioboto3 / aiobotocore feasibility. **Pursue real wire-level cancel only if a working integration path exists** — either a released `langchain-aws` with native aioboto3 support, OR aioboto3 plus a thin adapter we'd own and maintain in this repo. If neither exists at spike close, re-document per D-09. Rationale: a closed cancel story is real value, but the Phase 8 SC#1 history shows the blocker is upstream pace, not our willingness; tying the decision to a concrete integration path keeps the spike from sliding into open-ended research.
- **D-09 (Upstream-signal re-eval trigger):** If the spike says re-document, refresh `docs/cancellation.md §4–§5` with the current blocker status and an **event-driven re-evaluation trigger** (not a calendar date, not a milestone-tied date): "Re-evaluate when `langchain-aws` cuts a release with #663 merged, OR when `aioboto3` reaches a named milestone (GA / 1.0)." Pat tracks upstream; whichever lands first re-opens the cancel work.

### Gate consistency rule home (SC#4 / MCP-CAN-02)

- **D-10 (`docs/testing.md` is the single source of truth):** New file `docs/testing.md`, sibling to `docs/cancellation.md`. Documents the `CODE_WIKI_RUN_INTEGRATION=1` opt-in gate: canonical skip-decorator (`pytest.mark.skipif(not os.environ.get("CODE_WIKI_RUN_INTEGRATION"), reason="…")`), the standard reason text, every gated test file path, and a static grep gate (one of: a Bash script under `scripts/`, or a pytest meta-test) that fails CI if a gated file diverges from the canonical pattern. No mention in `CLAUDE.md` — `docs/testing.md` is discoverable and `docs/` is already the established location for cross-cutting conventions (`cancellation.md`, `trace-schema.md`).

### Trace coverage scope (SC#1 / TRACE-FU-01)

- **D-03 (All LLM call sites covered):** Every Bedrock invocation in production code must result in a JSONL trace record carrying `input_tokens` + `output_tokens`. Today's gap inventory:
  - `SubagentPool._write_trace` (`pool.py:186-231`) — already correct.
  - `query.py:977` `query_summary` record — missing usage fields; backfill.
  - `ingest.py:438` direct `llm.ainvoke` — no trace at all; route through the new helper.
  - Any future call site found during scout (executor verifies).
  None allowed on `usage_metadata` only when Bedrock returned an error response (existing pool guard semantics).
- **D-04 (Extract pool writer into shared helper):** Pull `_write_trace`'s record-construction + JSONL append logic out of `SubagentPool` into a `trace_io` helper (location: `packages/subagent-runtime/src/subagent_runtime/trace_io.py` — keeps it next to the pool; alternative locations like a new `core-trace` package are out unless executor finds a stronger reason during scout). Pool continues to call the helper; non-pool sites (ingest, query summary) call it directly. Single source of truth for record schema; eliminates the drift surface that produced this debt in the first place. Schema stays at `schema_version: 1` unless the extraction reveals a forced field change.
- **D-05 (Real-fan-out regression test):** Gated by `CODE_WIKI_RUN_INTEGRATION=1`. Runs scan + ingest + query against a tmp_path fixture vault, parses every JSONL file under `.code-wiki/traces/`, asserts every non-error record has non-None `input_tokens` AND `output_tokens`. SC#1's literal wording requires "a regression test that runs a real fan-out and asserts the field is populated." Belt + braces (static grep gate for ChatBedrockConverse outside the helper) was considered and rejected for now — the helper extraction makes the gap visible in code review without extra tooling.

### Sweep matrix expansion (SC#2 / SWEEP-FU-02/03/04)

- **D-06 (All 6 in-scope roles get divergence rubrics):** Extend `ROLES_WITH_DIVERGENCE` in `two_gate.py:36` from `{librarian, ingestor, linter, scanner}` to all 6 roles in `IN_SCOPE_ROLES`. Author new rubrics for `code_reader` and `synthesizer` at Phase-6 EVAL-11..13 rigor (not minimal-viable — Pat wants real signal, not a tick-box). If the executor's scout reveals an inherent reason one of the two can't take a programmatic rubric, that's a deviation that surfaces in the plan, not a quiet downgrade.
- **D-07 (`code_reader` cases — expand to 5–6):** Keep the existing 3 vault-thin cases in `eval/cases/code_reader_cases.json` for baseline comparability. Add 2–3 new cases reflecting the post-rebrand surface (target candidates during planning: `workspace-io`, `graph-wiki` plugin entry points, the new `vault-io.lint_wiki` / `vault-io.wiki_search` ports). Retune so every case produces a non-trivial score against the current corpus.
- **D-11 (SWEEP-FU-04: both fixture and live):** (a) Build a synthetic post-rebrand fixture vault for the CI-runnable scanner regression sweep — package pages reflecting current names (`workspace-io`, `prompt-sources`, `vault-io`, etc.), gated test asserting no regression vs. v1.1 baseline. (b) One manual live-vault re-sweep against `~/Personal/wiki/deep-agents` (the post-Phase-15 vault), output transcript / scores pasted into `16-VERIFICATION.md`. Mirrors Phase 15's D-08/D-09 pattern: fixture for reproducibility + live run for milestone-grade evidence.
- **D-12 (No hard cost cap — judgement-driven):** Sweep runs are bounded by Pat's review of the `pricing.py` preflight dry-run before each run, not by a hard abort threshold. Trust the existing preflight estimator output. Aligns with the cost-optimization mindset memory (`[[user_cost_optimization]]`) but acknowledges that v1.2 close-out evidence is worth measured spend.

### Test fix (SC#5 / MODEL-FU-01)

- **D-13 (Add model_id assertion to current test):** The named test `test_load_role_config_synthesizer_uses_sonnet` no longer exists — it was already renamed to `test_load_role_config_synthesizer_limits` (asserts only `max_tokens=4096`, `max_concurrency=3`). Extend the existing test to also assert `cfg["model_id"] == "qwen.qwen3-32b-v1:0"` — the current bundled default in `packages/model-adapter/src/model_adapter/models.toml:121`. Locks the current Qwen synthesizer default so any future silent swap fails the test. Per-role parameterized model_id coverage (rejected option B) is deferred to v1.3 if it becomes a real need.

### Plan structure

- **D-14 (1 bundled atomic plan):** All Phase 16 work lands in one `16-01-PLAN.md`, matching Phase 14 Plan 3 and Phase 15 D-10. Per-step commits inside the plan family: (1) trace helper extraction, (2) ingest + query-summary refactor + regression test, (3) `code_reader`/`synthesizer` divergence rubrics, (4) `code_reader_cases.json` expansion + retune, (5) synthetic fixture vault + scanner regression test, (6) cancel spike + decision artefact, (7) `docs/testing.md` + grep gate, (8) synthesizer model_id assertion, (9) live-vault scanner re-sweep transcript + `16-VERIFICATION.md`. Rationale: all items are mechanical/maintenance-grade, individually small, and the SC mapping is one-to-one with requirements — splitting into 4 themed plans adds overhead without buying anything. Matches Pat's stated preference for fewer larger plans on close-out work.

### Claude's Discretion

- Exact filename and home for the trace helper (`trace_io.py` vs. extending `pool.py` with module-level functions vs. a tiny new package) — executor's call during scout; preference is `subagent-runtime/trace_io.py` per D-04 unless a stronger reason emerges.
- Exact form of the `CODE_WIKI_RUN_INTEGRATION` grep gate (Bash script under `scripts/` vs. a `tests/test_integration_gate.py` meta-test) — executor's call; the test-based form gets free CI hookup.
- Exact divergence-rubric content for `code_reader` and `synthesizer` (rule count, rule shape) — author them to match the rigor of existing rubrics; executor reads existing Phase-6 rubrics during scout and patterns the new ones on them.
- Exact case text and case_ids for the 2–3 new `code_reader` cases — author against the post-rebrand surface (`workspace-io`, `graph-wiki` plugin, ported `vault-io` modules); follow the existing case JSON shape.
- Whether the synthetic fixture vault lives under `packages/eval-harness/tests/fixtures/` or a repo-level `tests/fixtures/` — executor's call; prefer the eval-harness-local location for proximity to the sweep code.
- Exact form of the cancel spike write-up (inline in `16-VERIFICATION.md` vs. a separate spike artifact) — if the spike says re-document, `docs/cancellation.md` is the canonical home; `16-VERIFICATION.md` cites the diff.
- Whether the live-vault re-sweep happens as part of the bundled plan or as a final post-plan step — executor's call; Phase 15 pattern was a final spot-check, which works here too.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirement traceability
- `.planning/ROADMAP.md` §Phase 16 — Goal, depends-on (Phase 12), SC#1..SC#5, 7-requirement mapping (TRACE-FU-01, SWEEP-FU-02, SWEEP-FU-03, SWEEP-FU-04, MCP-CAN-01, MCP-CAN-02, MODEL-FU-01).
- `.planning/REQUIREMENTS.md` lines 43–55 — Full requirement text for each of the 7 carry-forward items.
- `.planning/PROJECT.md` — Core Value (Bedrock-only `code-wiki-agent`); v1.1 deferrals carrying into v1.2 (lines 41, 113, 185).
- `.planning/RETROSPECTIVE.md` line 72 — Phase 8 host-reliability summary; documents the v1.1 cancel deferral path.

### Trace pipeline (TRACE-FU-01)
- `packages/subagent-runtime/src/subagent_runtime/pool.py` §`_write_trace` (lines 186–231) — Current canonical trace record shape; source for D-04 helper extraction. Includes the `usage_metadata` guard pattern (lines 205–209).
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:977` — `query_summary` JSONL record currently missing `tokens_in`/`tokens_out`; backfill target.
- `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:438` — Direct `llm.ainvoke` call site writing no trace; refactor target through the new helper.
- `docs/trace-schema.md` — Existing trace schema documentation (executor reads to confirm `schema_version: 1` field set).
- `agents/code-wiki-agent/tests/integration/` — Existing gated integration tests directory; home for the new TRACE-FU-01 regression test.

### Sweep matrix (SWEEP-FU-02/03/04)
- `packages/eval-harness/src/eval_harness/two_gate.py:36` — `ROLES_WITH_DIVERGENCE` frozenset; expansion target from 4 → 6 roles.
- `packages/eval-harness/src/eval_harness/sweep.py` — Sweep runner; integrates `ROLES_WITH_DIVERGENCE` via `two_gate.score_two_gate`.
- `packages/eval-harness/src/eval_harness/divergence/` — Existing divergence-rubric module; pattern source for new `code_reader` + `synthesizer` rubrics.
- `packages/eval-harness/tests/test_two_gate_scorer.py:173-227` — Documents that synthesizer currently skips Gate 1 (D-06 expansion will change this).
- `eval/cases/code_reader_cases.json` — Current 3 vault-thin cases; expansion + retune target per D-07.
- `eval/cases/query_cases.json` — Reference for case JSON shape.
- `packages/eval-harness/tests/test_models_toml_sweep_candidates.py:22-51` — `IN_SCOPE_ROLES` definition and `code_reader_cases.json` count/path constraints.
- `packages/eval-harness/src/eval_harness/preflight.py`, `pricing.py` — Cost estimation tools used per D-12 (judgement-driven cost gating).
- `.planning/phases/<phase-6>/` — Phase 6 EVAL-11..13 rubric rigor target (executor finds the exact phase dir; not directly referenced from current ROADMAP but RETROSPECTIVE points to it).

### MCP cancellation (MCP-CAN-01) + gate consistency (MCP-CAN-02)
- `docs/cancellation.md` — Current cancel documentation (lines 155–210 cover v1.1 limitations + v1.2+ future-work list); refresh target if D-08 spike says re-document.
- `.planning/research/STACK.md` lines 239, 649 — Documents `langchain-aws#663` as the upstream signal (filed Sep 2025).
- `.planning/milestones/v1.1-MILESTONE-AUDIT.md` lines 37, 191 — Phase 8 SC#1 deferral history.
- `agents/code-wiki-agent/tests/conftest.py:17-21` — Canonical `CODE_WIKI_RUN_INTEGRATION` skip-decorator shape (one of three current homes).
- `agents/code-wiki-agent/tests/integration/test_mcp_e2e.py:21-22`, `test_mcp_stdio.py:142-143`, `test_query_e2e.py:40-41`, `test_bedrock_iam.py:33-35` — All gated test files; inventory target for `docs/testing.md`.
- `packages/subagent-runtime/tests/integration/test_pool_bedrock.py:29-30` — Cross-package gated test; same inventory.

### Model config drift (MODEL-FU-01)
- `packages/model-adapter/tests/test_loader.py:125-130` — Current `test_load_role_config_synthesizer_limits` (extend per D-13).
- `packages/model-adapter/src/model_adapter/models.toml:113-130` — Bundled default; `synthesizer.model_id = "qwen.qwen3-32b-v1:0"` is the locked value.
- `packages/model-adapter/src/model_adapter/loader.py:27-41` — `set_models_path` override mechanism (read-only context).

### Prior phase patterns
- `.planning/phases/15-wiki-self-update/15-CONTEXT.md` — D-08/D-09 (single-page spot-check + transcript-in-VERIFICATION) pattern for SWEEP-FU-04 live re-sweep.
- `.planning/phases/14-plugin-port-m3b/14-CONTEXT.md` — D-01 bundled-plan pattern reference for D-14.
- `.planning/phases/11-workspace-io-port-m1/11-CONTEXT.md` — D-14 strict-raises philosophy cross-reference.

### Memory / project-level constraints
- `[[user_cost_optimization]]` — Eval-driven model selection; informs D-12 (no hard cap, preflight + judgement).
- `[[project_wiki_setup]]` — Qwen profile is the wiki default; informs D-11 live-vault sweep context.
- `[[project_plugin_port_model]]` — Plugin uses Claude Code; `code-wiki-agent` is the Bedrock path. Phase 16 work touches the Bedrock path only.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`SubagentPool._write_trace`** (`pool.py:186-231`) — Production-tested trace writer with proper `usage_metadata` handling, OSError swallowing (AI-SPEC Failure Mode #2), and `schema_version: 1` discriminator. Source for the D-04 helper extraction; minimal behavioral change required.
- **`ROLES_WITH_DIVERGENCE` frozenset + `score_two_gate`** (`two_gate.py:36, 103`) — Existing 2-gate scoring infrastructure; adding `code_reader` + `synthesizer` is a frozenset extension + 2 new rubric files, not a redesign.
- **`code_reader_cases.json` JSON shape** (`eval/cases/code_reader_cases.json`) — `{case_id, query, expected_answer, tags}` schema, 3 existing cases tagged `vault-thin`. New cases follow the same shape.
- **Preflight estimator** (`packages/eval-harness/src/eval_harness/preflight.py`, `pricing.py`) — Existing dry-run cost surface used by D-12 to keep sweep cost judgement-driven without a hard abort.
- **Canonical skip-decorator pattern** (`agents/code-wiki-agent/tests/conftest.py:17-21`) — Already-consistent shape across 5 known gated test files; `docs/testing.md` formalizes it as the rule rather than introducing a new shape.

### Established Patterns
- **`schema_version: 1` field on every trace record** (Phase 9 OBS-04 D-01/D-02) — Required for self-describing JSONL; D-04 helper preserves.
- **None-on-Bedrock-error guard** (`pool.py:205-209`) — `usage_metadata is None on ThrottlingException / content filter`; the helper preserves this exact semantics. Regression test (D-05) only asserts non-None on non-error records.
- **OSError-swallow on trace write** (`pool.py:227-231`) — Trace failures never mask successful task results; helper preserves.
- **Per-VERIFICATION.md transcript pattern** (Phase 14 SC#4, Phase 15 D-09) — Live runs captured as fenced markdown blocks inside `${padded_phase}-VERIFICATION.md`. Phase 16's live scanner re-sweep (D-11) and cancel spike write-up follow the same shape.
- **Per-step commits inside a bundled atomic plan** (Phase 14 Plan 3, Phase 15 D-10) — D-14's 9-step commit sequence mirrors this directly.
- **Strict-raises validation philosophy** (Phase 11 D-14, Phase 14 D-02) — If the trace-helper extraction needs to add a manifest-shape key, it raises on unknown keys.

### Integration Points
- **No MCP boundary change** — Phase 16 mutates internal helpers + tests + docs. The MCP tool surface (`wiki_bootstrap/scan/ingest/query/lint/log`) signatures stay identical.
- **No plugin touch** — `plugins/graph-wiki/` is out (it runs on Claude Code per `[[project_plugin_port_model]]`; trace pipeline + sweep matrix are Bedrock-side concerns).
- **No vault schema touch** — `~/Personal/wiki/deep-agents/` is only read (D-11 live re-sweep) — no page rewrites, no log mutation.
- **`models-qwen.toml` + `models-claude.toml` at repo root** — D-13 locks the bundled `models.toml` default (`qwen.qwen3-32b-v1:0`) but does NOT touch the project-root override profiles.
- **`docs/cancellation.md` is the cancel canon** — D-08/D-09 refresh extends what's there; no new doc unless cancel work pursues real implementation.

</code_context>

<specifics>
## Specific Ideas

- **The trace gap is real but narrow** — Pool fan-out already carries tokens; gaps are at `ingest.py:438` (no trace at all) and `query.py:977` (summary record schema). The helper-extraction approach (D-04) is the cleanest fix because it eliminates the *type* of gap (drift between writers), not just the current instances.
- **The named test in MODEL-FU-01 doesn't exist** — `test_load_role_config_synthesizer_uses_sonnet` was already renamed during prior v1.1 work to `_limits`. The locked decision (D-13) extends the existing test rather than closing the requirement as "already satisfied" — the model_id assertion is the real value the requirement was reaching for.
- **`ROLES_WITH_DIVERGENCE` expansion is 4→6, not 0→6** — The matrix is already half-wired; D-06 just finishes it. Two rubrics to author, not six.
- **`code_reader` cases are intentionally vault-thin** — They're designed to force the code-fallback path. Post-rebrand expansion stays on-theme: target newly-added modules (`workspace-io`, `graph-wiki` plugin entry, ported `vault-io.lint_wiki` / `vault-io.wiki_search`) so the cases continue to exercise the fallback rather than being answerable from vault pages.
- **D-08's spike gate is "working integration path exists," not "upstream merged"** — Subtle but important: if aioboto3 ships GA but `langchain-aws` hasn't merged #663, an adapter we own would still qualify. The gate measures feasibility-with-acceptable-maintenance, not waiting for someone else to do all the work.
- **D-09's re-eval is event-driven, not date-driven** — Calendar deferrals decay; upstream-signal deferrals re-open exactly when the blocker dissolves. Matches the way the Phase 8 SC#1 deferral was originally framed.
- **`docs/testing.md` is small but load-bearing** — It exists to make the gate rule grep-able and to surface drift in code review. The grep gate (D-10) is the enforcement mechanism; the doc text is the rationale + canonical pattern.
- **No hard cost cap (D-12) is consistent with the cost-optimization memory** — `[[user_cost_optimization]]` is "measure it, don't default to the best model" — not "spend nothing." The preflight estimator + Pat's per-run dry-run review is the measurement loop.

</specifics>

<deferred>
## Deferred Ideas

- **Real `aioboto3` integration (if spike gate fails)** — Deferred per D-08/D-09 with an upstream-signal re-eval trigger. Lives in `docs/cancellation.md §5` v1.2+ list.
- **SIGINT / stdin-close fallback cancel paths** — Already on the `docs/cancellation.md §5` list; stays there.
- **Orphan-thread monitoring / cleanup hooks** — On the `docs/cancellation.md §5` list; out of Phase 16 scope.
- **Per-tool granular E2E cancel tests** — Out unless a behavioral nuance surfaces during the D-08 spike.
- **Hard cost cap for sweep runs** — Rejected by D-12; could land in v1.3 if a real overrun ever happens.
- **Wholesale rewrite of `code_reader_cases.json`** — Rejected by D-07 in favor of incremental expansion; baseline comparability matters more than a clean-slate set.
- **Documenting why `ROLES_WITH_DIVERGENCE` could stay at 4** — Rejected by D-06; the answer is "expand," not "document the limitation."
- **Per-role model_id parameterized assertion test** — Considered for MODEL-FU-01 (option B), rejected by D-13 in favor of the single targeted synthesizer assertion. Could land in v1.3 if drift becomes a real pattern.
- **Inline writer pattern (same schema, multiple writers)** — Considered for the trace gap (option B on the writer-shape question), rejected by D-04 in favor of helper extraction.
- **Routing all LLM calls through `SubagentPool`** — Considered for trace coverage (option C on the writer-shape question), rejected by D-04 as a bigger refactor than the gap justifies.
- **Promoting any sweep-discovered model swap as a new default** — Out of Phase 16 scope per `[[user_cost_optimization]]` "measure it before defaulting"; D-11 captures evidence, doesn't act on it.
- **Cross-surface (Bedrock vs Claude Code) cancel behavior comparison** — Out; Phase 16 cancel work is Bedrock-only (the plugin runs on Claude Code per `[[project_plugin_port_model]]`).
- **Adding cache-hit telemetry / multi-turn aggregation to the trace schema** — Out; `schema_version: 1` stays unless the helper extraction surfaces a forced field change.

</deferred>

---

*Phase: 16-carry-forward-debt-cleanup*
*Context gathered: 2026-05-19*
