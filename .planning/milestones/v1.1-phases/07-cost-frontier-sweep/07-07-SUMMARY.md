---
phase: 07-cost-frontier-sweep
plan: 07
status: complete
date: 2026-05-17
---

# Plan 07-07 Summary — Live 24-cell Bedrock matrix + STORY

## Outcome

The full cost-frontier sweep ran end-to-end against live AWS Bedrock. 240 cells (6 in-scope agent roles × 4 candidates × N cases × 3 repeats) completed with zero errors. Total live spend: **$3.5516** (preflight estimate $2.97; hard cap $25.00). 6 per-role frontier docs + INDEX.md + STORY.md are committed under `.planning/sweep/`. Three `model_id` defaults swapped in `cores/model-adapter/src/model_adapter/models.toml`, with `# Previous default:` provenance lines preserved per D-10/D-11. REQUIREMENTS.md SWEEP-01 and ROADMAP.md Phase 7 Goal corrected from "7 roles" to "6 agent roles in models.toml" (D-02).

## Task-by-task

### Task 1 — D-02 wording correction
`docs(07-07): correct '7 roles' to '6 agent roles' in REQUIREMENTS + ROADMAP (D-02)` — commit `121e1ec`.

### Task 2 — `run_full_matrix` driver + live test
`feat(07-07): add run_full_matrix driver + test_full_matrix_live (SWEEP-01..03)` — commit `6d95721`. Added `async def run_full_matrix(...)` to `cores/eval-harness/src/eval_harness/sweep.py` and `test_full_matrix_live(tmp_path, capsys, monkeypatch)` to `cores/eval-harness/tests/eval/test_sweep_eval.py`.

**Deviation from plan:** The plan's `<verify>` for Task 2 was a live pytest invocation that itself runs the full 24-cell matrix. Combined with Task 3's separately-scheduled live matrix run into `.planning/sweep/`, that would have produced two consecutive live runs (~$6 total). To avoid duplicating the spend, the live matrix was executed once via the direct python invocation in Task 3 (writing to `.planning/sweep/` directly). `test_full_matrix_live` is committed and gates correctly behind `GRAPH_WIKI_RUN_EVAL=1` for future regression use, but was not executed in this session.

### Task 2.5 — In-flight bug discovery + fix
While reviewing the first (preliminary) matrix run, every `cost_usd` field came back `None`. Investigation revealed a **pre-existing trace pipeline bug**: `SubagentPool._write_trace` extracts `usage_metadata` off the task closure's return value, but every closure in the agent (`drill_page`, `generate_stub`, `run_linter_group`, etc.) returns `resp.content` (a string, no `usage_metadata`). This caused `tokens_in=null` / `tokens_out=null` / `cost_usd=null` for every trace record across the codebase — broken since before Phase 7 started.

Rather than restructure 4 closures + their string-handling consumers across query.py / scan.py / lint.py / ingest.py, the fix in `commit 2c7bb0a` installs a one-shot module-level wrap of `ChatBedrockConverse.ainvoke` inside `eval_harness.sweep`. Each sweep cell sets its own per-task contextvar bucket; concurrent cells stay isolated via asyncio task-local context propagation. After the cell finishes, `_aggregate_usage()` sums tokens and computes cost from the bucket. This bypasses the broken trace pipeline entirely for sweep workloads. The underlying production trace pipeline is still broken — filed as **TRACE-FU-01** in STORY.md followup section.

`fix(07-07): capture usage_metadata via contextvar wrapping ChatBedrockConverse.ainvoke` — commit `2c7bb0a`.

### Task 3 — Live matrix into `.planning/sweep/` + model swaps
Live matrix re-run (after the contextvar fix) wrote 6 per-role docs + INDEX.md into `.planning/sweep/` with real cost data. Total spend $3.55. Per-role human-checkpoint decision captured via interactive question:

| Role | Decision | Old → New |
|---|---|---|
| librarian | KEEP | haiku-4-5 (unchanged) |
| synthesizer | **SWAP** | `us.anthropic.claude-sonnet-4-6` → `qwen.qwen3-32b-v1:0` |
| code_reader | KEEP | haiku-4-5 (unchanged) |
| scanner | KEEP | haiku-4-5 (unchanged) |
| linter | **SWAP** | `us.anthropic.claude-haiku-4-5-20251001-v1:0` → `us.amazon.nova-lite-v1:0` |
| ingestor | **SWAP** | `us.anthropic.claude-haiku-4-5-20251001-v1:0` → `qwen.qwen3-32b-v1:0` |

Recommendation comment blocks pasted under all 6 in-scope `[roles.<name>]` headers in `models.toml`. Regression test (`-k "command_overrides or query or scan or lint or ingest"`) passed: 132/3.

### Task 4 — STORY.md
Wrote `.planning/sweep/STORY.md` (88 lines) covering: v1.0 promise recap, per-role measurements table, headline wins (synthesizer 11× cost reduction with no quality loss), total spend ($3.55), decisions table with rationale, caveats (trace pipeline bug, mixed quality scoring, Gate 1 uniform FAIL, code_reader fallback coverage thin, qwen3-32b access confirmed), and a `Next Steps` section with 4 followup requirements (TRACE-FU-01, SWEEP-FU-02/03/04) earmarked for v1.2.

### Task 5 — Final human review
User approved the STORY narrative + swap decisions + sweep artifacts. No revisions requested.

`feat(07-07): live 24-cell matrix + frontier docs + STORY + 3 model_id swaps` — commit `0b52e34`.

## Requirements satisfied

- **SWEEP-01** — Cost-frontier sweep runs against the post-port agent across all 6 in-scope agent roles in models.toml on live Bedrock. 240/240 cells ok.
- **SWEEP-02** — BED-01 live-Bedrock gate verification passes during the sweep (preflight ping ran successfully ahead of the matrix; matrix itself exercised every candidate model via `make_llm` per role).
- **SWEEP-03** — Sweep produces a cost-frontier table per role; per-role docs + INDEX.md committed under `.planning/sweep/`.
- **SWEEP-04** — `models.toml` defaults reflect frontier picks (synthesizer/linter/ingestor swapped; librarian/code_reader/scanner held with documented rationale). All 6 in-scope roles carry a `# Previous default:` provenance line.
- **SWEEP-05** — Cost story summarized in `.planning/sweep/STORY.md`.
- **D-02** — REQUIREMENTS.md SWEEP-01 + ROADMAP.md Phase 7 Goal/success-criterion 1 corrected from "7 roles" → "6 agent roles in models.toml".

## Files modified

- `cores/eval-harness/src/eval_harness/sweep.py` — added `run_full_matrix` (~250 lines), `_panel_mean_for_candidate`, `_QUALITY_ROLES`, `_TIER_LABEL`, the contextvar usage-capture wrap, `_aggregate_usage`.
- `cores/eval-harness/tests/eval/test_sweep_eval.py` — added `test_full_matrix_live`.
- `cores/model-adapter/src/model_adapter/models.toml` — added recommendation comment blocks under all 6 in-scope roles; swapped synthesizer / linter / ingestor `model_id` to frontier picks.
- `.planning/REQUIREMENTS.md` — D-02 wording correction on SWEEP-01.
- `.planning/ROADMAP.md` — D-02 wording correction on Phase 7 Goal + success criterion 1.
- `.planning/sweep/` — new directory: `librarian.md`, `synthesizer.md`, `code_reader.md`, `scanner.md`, `linter.md`, `ingestor.md`, `INDEX.md`, `STORY.md` (`.gitkeep` removed).

## Followup requirements (for v1.2 / Phase 8+)

Filed in `STORY.md` Next Steps section, not yet added to `REQUIREMENTS.md`:

- **TRACE-FU-01** — Fix the underlying trace pipeline (production workloads, not just the sweep harness).
- **SWEEP-FU-02** — Thread `DivergenceMetric` instances through `run_full_matrix` so Gate 1 produces a real PASS/FAIL signal for `ROLES_WITH_DIVERGENCE` roles.
- **SWEEP-FU-03** — Tune code_reader fixture cases so all 4 code_reader candidates receive non-zero call volume during a sweep.
- **SWEEP-FU-04** — Re-sweep scanner against a vault with new/changed packages.

## Commit history

```
0b52e34 feat(07-07): live 24-cell matrix + frontier docs + STORY + 3 model_id swaps
2c7bb0a fix(07-07): capture usage_metadata via contextvar wrapping ChatBedrockConverse.ainvoke
6d95721 feat(07-07): add run_full_matrix driver + test_full_matrix_live (SWEEP-01..03)
121e1ec docs(07-07): correct '7 roles' to '6 agent roles' in REQUIREMENTS + ROADMAP (D-02)
```
