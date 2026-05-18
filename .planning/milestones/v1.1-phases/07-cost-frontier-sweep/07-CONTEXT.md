# Phase 7: Cost-Frontier Sweep - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Execute the Phase 4 eval-harness cost-frontier sweep against the **post-Phase-6 agent** (after PORT requirements landed) across the six agent roles in `models.toml`, score each (role, model) cell using a tier-appropriate quality signal, publish a Pareto frontier per role under `.planning/sweep/`, and update `models.toml` defaults to cost-optimal picks via a manual edit guided by sweep-emitted recommendation comments. The BED-01 live-Bedrock gate verification folds into this run.

**In scope:**
- Define per-role `sweep_candidates = [...]` arrays in `models.toml` (role-tiered candidate sets)
- Add 3–5 "vault-thin" fixture queries to force `code_reader` to fire during the sweep
- Extend the sweep runner (`cores/eval-harness/src/eval_harness/sweep.py`) so the role-under-test rotates across all six roles, single-role-swap protocol (other roles held at current defaults)
- Two-gate quality scoring for the four roles with Phase-6 divergence rubrics (librarian, ingestor, linter, scanner): divergence-within-baseline AND end-to-end score within bounds
- End-to-end-only scoring for synthesizer and code_reader (no divergence rubrics)
- Pre-flight cost estimator + `--dry-run` mode (estimate cases × cells × tokens × per-model price; refuse if estimate exceeds hard cap)
- Per-role results docs at `.planning/sweep/{role}.md` + `.planning/sweep/INDEX.md`
- Sweep emits a `# Sweep candidates (run YYYY-MM-DD): ...` recommendation block per role in `models.toml`; user edits the default manually with `# was: <model-id>` provenance comment (satisfies SWEEP-04)
- A short cost-story doc (the v1.0 promise SWEEP-05 satisfies)
- BED-01 live-Bedrock gate verification confirmed in passing during the sweep run

**Out of scope (explicit):**
- Judge model sweeps (`judge_a`, `judge_b`) — swapping judges would invalidate Phase 6 divergence baselines and the position-bias-checked panel from Phase 4
- New Phase-6-style divergence rubrics for synthesizer or code_reader — quality signal stays end-to-end for those roles
- Automated in-place rewrite of `models.toml` — manual edit is the policy
- Adding new agent roles or changing the role taxonomy
- MCP cancellation polish, DeepAgents CLI integration test (Phase 8)
- Trace renderer / schema versioning (Phase 9)
- OSS release prep (deferred past v1.1)

</domain>

<decisions>
## Implementation Decisions

### Role coverage
- **D-01:** Sweep covers **six agent roles**: `librarian`, `code_reader`, `scanner`, `linter`, `ingestor`, `synthesizer`. Judges (`judge_a`, `judge_b`) are excluded; aliases `haiku`/`sonnet` in `models.toml` are not roles.
- **D-02:** SWEEP-01's "7 roles" wording is inaccurate against the current `models.toml`. Planner to either correct the requirement text or document the count discrepancy in the results doc (preference: correct REQUIREMENTS.md to "all 6 agent roles in models.toml" with a note).

### Candidate model matrix (role-tiered)
- **D-03:** Candidates are role-tiered, not uniform. Three tiers:
  - **Cheap-fast** (`scanner`, `code_reader`): `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.amazon.nova-micro-v1:0`, `us.amazon.nova-lite-v1:0`, `qwen.qwen3-32b-v1:0`
  - **Mid** (`linter`, `ingestor`): `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.amazon.nova-pro-v1:0`, `us.amazon.nova-lite-v1:0`, `qwen.qwen3-32b-v1:0`
  - **Quality** (`librarian`, `synthesizer`): `us.anthropic.claude-sonnet-4-6`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.amazon.nova-pro-v1:0`, `qwen.qwen3-32b-v1:0`
- **D-04:** Total sweep matrix is **24 (role, model) cells** (6 roles × 4 candidates).
- **D-05:** Candidate lists live in `models.toml` as `sweep_candidates = [...]` arrays inside each `[roles.{name}]` block. Single-file config; sweep runner reads the same TOML used for production defaults. Planner: verify the existing TOML loader tolerates the new key (or extend it).

### Quality signal
- **D-06:** **Single-role-swap protocol.** For every cell, the role-under-test runs with the candidate model while *all other roles stay at their current `models.toml` default*. Measures marginal impact of one model change at a time; matches how a swap would actually ship.
- **D-07:** **Two-gate scoring** for the four roles with Phase-6 divergence rubrics (`librarian`, `ingestor`, `linter`, `scanner`): a candidate qualifies only if BOTH (a) divergence stays within the role's `cores/eval-harness/baselines/divergence-{role}.json` baseline AND (b) end-to-end query score (judge panel mean) stays within bounds set in the Frontier-pick step. Either gate fails → candidate disqualified for that role.
- **D-08:** **End-to-end-only scoring** for `synthesizer` and `code_reader`: reuse the existing judge panel + structural score on the full query pipeline's final answer. No new divergence rubrics this phase.
- **D-09:** **`code_reader` fixture additions.** Add 3–5 "vault-thin" queries to `eval/cases/query_cases.json` (or a new `eval/cases/code_reader_cases.json`) whose answers cannot come from any vault page — they force the librarian fan-out to return empty and the `code_reader` fallback to fire. Without these, `code_reader` would record N/A across the sweep.

### Frontier pick + swap policy
- **D-10:** **Pareto frontier published, human picks.** The sweep emits the cost-vs-quality Pareto frontier (non-dominated set) per role; the user picks the default by editing `models.toml`. No auto-write, no threshold-driven auto-pick — defensive against bad auto-picks.
- **D-11:** **Sweep emits a recommendation comment block** in/next to each role in `models.toml`:
  ```toml
  # Sweep candidates (run 2026-MM-DD): pareto-frontier members
  #   - us.anthropic.claude-haiku-4-5-...  (cost=$X.XX, quality=0.XX)
  #   - us.amazon.nova-lite-v1:0           (cost=$X.XX, quality=0.XX)
  # Previous default: <model-id>
  ```
  User edits `model_id = ...` by hand. The `# Previous default:` line satisfies SWEEP-04's provenance requirement.
- **D-12:** **Per-role docs under `.planning/sweep/`.** One markdown file per role (`librarian.md`, `ingestor.md`, etc.) with its frontier table, recommendation, and raw scores; an `INDEX.md` ties them together. Easier to diff incrementally if a single role is re-swept later. The cost-story doc (SWEEP-05) is a separate top-level file in `.planning/sweep/STORY.md` (planner picks the exact name).
- **D-13:** **Pre-flight cost estimate + `--dry-run` mode.** Sweep runner computes `estimated_cost_usd = sum(cases × repeats × expected_tokens × pricing[model])` and prints `Estimated cost: $X.XX, proceed? [y/N]` before any Bedrock call. `--dry-run` flag executes the loop end-to-end with mock LLM responses to validate plumbing without spend. Hard cap: planner picks the threshold (suggestion: `$50` aborts pre-flight automatically). Saves Pat from accidentally kicking off a $200 run.

### Claude's Discretion
- Exact name and layout of the cost-story doc — `.planning/sweep/STORY.md` vs `docs/cost-frontier.md` vs another path. Planner decides based on whether v1.1 wants user-facing OSS docs yet.
- Whether the new `sweep_candidates` key lives in `models.toml` as a sibling of `model_id` or under a nested `[roles.{name}.sweep]` table. Planner picks based on what the existing loader tolerates without rewriting.
- The exact "within bounds" threshold for the end-to-end gate (D-07/D-08). Suggested starting points: "within 5% of the current default's mean score" for quality-tier roles, "within 10%" for mid/cheap-fast — but planner should propose a defensible number after running a baseline pass.
- Repeats-per-cell (3 is the default suggestion from the budget question; planner can tune based on cost estimate).
- Whether to add a `--role <name>` flag so a single role can be re-swept without re-running the whole matrix (likely worth doing; user didn't ask but it falls out of D-11/D-12 naturally).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project + milestone
- `.planning/PROJECT.md` — Core value (Bedrock cost story), milestone v1.1 framing, HARD CONSTRAINT that sweep measures *post-port* agent (not v1.0 baseline)
- `.planning/REQUIREMENTS.md` §SWEEP — The 5 requirements this phase delivers (SWEEP-01..05); note D-02 about the "7 roles" wording
- `.planning/ROADMAP.md` §"Phase 7: Cost-Frontier Sweep" (lines 70–79) — Goal + 4 success criteria locked at roadmap time
- `.planning/STATE.md` — Confirms Phase 6 complete; Phase 7 entry conditions met
- `.planning/phases/06-prompt-content-port-divergence-eval/06-CONTEXT.md` — Phase 6 divergence baselines exist for librarian/ingestor/linter/scanner; rubrics under `cores/eval-harness/src/eval_harness/divergence/rubrics/`; baselines under `cores/eval-harness/baselines/divergence-{role}.json`

### Existing eval-harness assets (the sweep runs on top of these)
- `cores/eval-harness/src/eval_harness/sweep.py` — `run_sweep()`, `SweepResult` dataclass, `_extract_tokens_from_traces()`. Currently parametrized only on `model_ids: list[str]` for the librarian; Phase 7 extends to per-role rotation.
- `cores/eval-harness/src/eval_harness/pricing.py` — `PRICES` dict + `cost_for_usage()`. Already covers all 6 candidate models. Pre-flight estimator (D-13) reads from here.
- `cores/eval-harness/src/eval_harness/structural.py` — `check_structural()` (cites code path / wikilinks resolve / valid frontmatter) — quality side of end-to-end score.
- `cores/eval-harness/src/eval_harness/judge.py` — `panel_score()` (heterogeneous claude-sonnet-4-6 + nova-pro-v1:0); `position_bias_check()` — the existing judge panel. Reused as-is.
- `cores/eval-harness/src/eval_harness/report.py` — `cost_frontier_table()`, `print_frontier()`, `regression_check()`. Per-role frontier docs render via these.
- `cores/eval-harness/src/eval_harness/divergence/` — Per-role check modules + `metric.py` + `rubrics/`. Two-gate scoring (D-07) reuses these directly.
- `cores/eval-harness/baselines/divergence-{librarian,ingestor,linter,scanner}.json` — Phase 6 baselines. Two-gate scoring loads these per role.
- `cores/eval-harness/tests/eval/test_sweep_eval.py` — Current pytest-evals two-phase integration (`@pytest.mark.eval` + `@pytest.mark.eval_analysis`). Phase 7 extends this file (or adds per-role siblings).
- `cores/eval-harness/tests/conftest.py` — `EVAL_GATE` skipif marker (`CODE_WIKI_RUN_EVAL=1` env-var gate); `CODE_WIKI_RUN_JUDGES=1` decouples sweep cost from judge cost. Both must remain honored.
- `eval/cases/query_cases.json` — Existing query corpus (parsed by `_load_cases()`). D-09 adds vault-thin cases here or in a sibling file.

### Production config + agent code (single-role-swap reads these)
- `cores/model-adapter/src/model_adapter/models.toml` — 10 entries: 2 aliases (`haiku`, `sonnet`) + 8 roles. Phase 7 adds `sweep_candidates` to the 6 in-scope roles.
- `cores/model-adapter/models.toml` — Top-level copy with only `haiku`/`sonnet`. Planner: verify which copy is the source of truth and whether the duplication is intentional.
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — `run_query()` is what the sweep invokes per cell; `librarian_model_override` parameter already exists. Other roles need a similar override surface (planner: extend or wrap).

### BED-01 gate
- See PROJECT.md ("BED-01 live-Bedrock gate is approved; verify in passing during the sweep") — confirmation that `make_llm("haiku").invoke("ping")` succeeds against real Bedrock is part of SWEEP-02; folds into the pre-flight pass before the matrix runs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Sweep runner is 80% there.** `run_sweep()` already does isolated per-run worktrees (`EvalWorktree`), token extraction from trace JSONL, cost computation via `pricing.cost_for_usage()`, structural checks, partial-failure isolation via `asyncio.gather(return_exceptions=True)`, and model-ID sanitization for filenames (T-4-02). Phase 7's lift is the rotation across roles + per-role candidate sets + two-gate scoring — not a rewrite.
- **Judge panel is paid for.** `panel_score()` (judge.py) is already heterogeneous and position-bias-checked from Phase 4. End-to-end scoring for the 6 roles reuses it unchanged.
- **Divergence harness is paid for.** Phase 6 shipped per-role `DivergenceCheck` modules, rubrics, baselines, and the `--accept-divergence-baseline` flow. Two-gate scoring (D-07) plugs into `metric.py` and reads `baselines/divergence-{role}.json`.
- **`code_reader` already has a `librarian_model_override`-style hook.** It's the opt-in vault-thin fallback; the planner can introduce `code_reader_model_override` symmetrically.
- **Trace JSONL captures `tokens_in` / `tokens_out`** per `SubagentPool._write_trace` — the pre-flight estimator (D-13) can sample-run a single case to calibrate expected-tokens-per-call per role, or use a conservative constant per pricing tier.

### Established Patterns
- **`CODE_WIKI_RUN_EVAL=1` + `--run-eval`** double gate is the established pattern for Bedrock-spend tests. Phase 7's runner inherits both. `CODE_WIKI_RUN_JUDGES=1` keeps judge-spend separately gated.
- **Per-role JSON files keep diffs reviewable.** Phase 6 chose one divergence baseline per role; Phase 7 mirrors this with one sweep result doc per role (D-12).
- **Provenance via inline comments.** Phase 6 uses `# Source:` / `# Anchor:` / `# Source-commit:` in prompt fragments. Phase 7's `models.toml` recommendation block (D-11) uses the same comment-as-provenance style.
- **`pytest-evals` two-phase pattern** (`@pytest.mark.eval` collects → `@pytest.mark.eval_analysis` aggregates) is the harness contract. Phase 7's per-role sweeps follow this — collection phase runs cells, analysis phase emits per-role frontier docs.

### Integration Points
- `cores/eval-harness/src/eval_harness/sweep.py` — `run_sweep()` signature widens to accept a role parameter (or the runner gains a `run_role_sweep(role, candidates)` companion). Single-role-swap override plumbed through `run_query()` per role.
- `cores/model-adapter/src/model_adapter/models.toml` — `sweep_candidates` keys added; loader must tolerate the new key (likely already does — TOML parsers ignore unknown keys, but verify in test).
- `eval/cases/` — vault-thin fixture additions for `code_reader`.
- `cores/eval-harness/baselines/divergence-{role}.json` — read-only for two-gate scoring (Phase 7 does not modify these).
- `.planning/sweep/` — new output directory for per-role frontier docs + INDEX + cost story.
- `cores/eval-harness/tests/eval/test_sweep_eval.py` (or per-role siblings) — extended/added to drive the 6-role × 4-model matrix under the existing `pytest-evals` gates.

</code_context>

<specifics>
## Specific Ideas

- **Tier-to-role map** (locked):
  - Cheap-fast: `scanner`, `code_reader`
  - Mid: `linter`, `ingestor`
  - Quality: `librarian`, `synthesizer`
- **Single-role-swap protocol example.** When sweeping `librarian` candidate `qwen.qwen3-32b-v1:0`, the run uses `qwen` for the librarian role and current defaults (today: `haiku` for code_reader/scanner/linter/ingestor and `sonnet` for synthesizer) for every other role. The judge panel runs unchanged. The end-to-end answer is what gets scored.
- **Recommendation comment block shape** (locked example):
  ```toml
  [roles.librarian]
  model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
  region          = "us-east-1"
  max_tokens      = 2048
  max_concurrency = 5
  sweep_candidates = [
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.amazon.nova-pro-v1:0",
    "qwen.qwen3-32b-v1:0",
  ]
  # Sweep candidates (run 2026-MM-DD): pareto-frontier members
  #   - us.anthropic.claude-haiku-4-5-... (cost=$0.XX, quality=0.XX)
  #   - us.amazon.nova-pro-v1:0           (cost=$0.XX, quality=0.XX)
  # Previous default: us.anthropic.claude-haiku-4-5-20251001-v1:0
  ```
- **Per-role results doc skeleton** (`.planning/sweep/librarian.md`): role name + tier + candidate list, raw scores table (model, quality_mean, quality_std, cost_per_run, n_cases, divergence_failures vs baseline), Pareto frontier callout, recommendation, run metadata (date, commit SHA, total cost).
- **Vault-thin fixture intent.** Queries like "How is `_StdoutGuard` implemented in the MCP server?" or "What does `SubagentPool._write_trace` write to the trace file?" — answers should require reading source, not the vault.

</specifics>

<deferred>
## Deferred Ideas

- **Judge model swaps.** Out of scope this phase (D-01 rationale). If a future cost squeeze warrants it, a dedicated "judge-swap" mini-phase would re-run Phase 6 baseline acceptance after the swap.
- **Divergence rubrics for synthesizer and code_reader.** Not authored in Phase 7 (D-08). If end-to-end scoring proves too noisy for these roles, a follow-up phase can add Phase-6-style rubrics + baselines.
- **Tier-relative auto-pick threshold (different X% per tier).** Considered as an alternative to Pareto-published-human-picks but declined in favor of human review. Reconsider if the cost-frontier becomes part of a regular re-sweep cadence.
- **In-place `models.toml` rewrite by the sweep tool.** Declined this phase (D-10). If repeated manual swaps prove tedious, add a `--apply` flag later that writes the lowest-cost-on-frontier in place.
- **Repeats-per-cell tuning / variance reporting.** Default suggestion is 3 repeats; if variance is too high to pick clean winners, a follow-up could raise repeats or add a confidence-interval column to the per-role docs.
- **Sample-run calibration for the pre-flight estimator.** Could measure actual tokens-per-call per role on a 1-case dry pass to calibrate the cost estimate rather than using a conservative constant. Planner can decide if worth the implementation cost in Phase 7 or defer.
- **`docs/cost-frontier.md` for OSS audiences.** PROJECT.md notes OSS release prep is deferred past v1.1; the cost-story doc lives under `.planning/sweep/` for now. Re-home to `docs/` when OSS release happens.

</deferred>

---

*Phase: 7-Cost-Frontier Sweep*
*Context gathered: 2026-05-16*
