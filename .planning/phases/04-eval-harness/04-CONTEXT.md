# Phase 4: Eval Harness - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers `cores/eval-harness` — a standalone workspace package with four interconnected capabilities:

1. **Baseline recorder** — headless `claude -p` subprocess (same pattern as lattice-evals) runs the existing lattice-wiki `query` command against the fixture vault and snapshots outputs to `eval/baselines/`
2. **Model sweep runner** — for a given subagent role (initially `librarian`), runs N candidate Bedrock models holding prompts fixed; each run uses git worktree isolation
3. **Heterogeneous judge panel** — deepeval 4.0 `AmazonBedrockModel` with `judge_a` (Claude Sonnet) + `judge_b` (Amazon Nova Pro) scoring each sweep run
4. **Cost-frontier report** — per-role quality vs. $/run table; cost-optimal-still-passing model highlighted

First target: validate against the `query` command before any other command's baseline is committed.

**Out of scope this phase:** eval for scan/lint/ingest/log commands (those come in Phase 5), `pytest-evals` CI integration beyond the `@pytest.mark.eval` skip gate, any write-back to the vault.

</domain>

<decisions>
## Implementation Decisions

### Fixture Corpus (EVAL-02)

- **D-01:** Reuse the existing vault at `cores/vault-io/tests/fixtures/round-trip-vault/` as the query eval fixture. It has real wiki structure (packages, plugins, `index.md`, `log.md`) — sufficient for query eval in v1. No new fixture repos needed for Phase 4.
- **D-02:** Eval artifacts (baselines, sweep result JSONs, cost-frontier reports) live in a **top-level `eval/` directory** at the workspace root. Subdirectory layout:
  - `eval/cases/` — JSON test case files `(query, expected_answer)` pairs
  - `eval/baselines/` — committed snapshots of current lattice-wiki output (oracle)
  - `eval/runs/` — sweep result JSONs (gitignored or committed per preference; planner decides)
- **D-03:** Test cases are defined as a **JSON file in `eval/cases/`** with `(query, expected_answer)` pairs. Planner designs the exact schema (suggest: `query: str`, `expected_answer: str`, optional `tags: list[str]`). Cases are committed to the repo.

### Baseline Recorder (EVAL-03)

- **D-04:** The baseline recorder invokes `claude -p --output-format stream-json --plugin-dir <lattice-wiki>` as a headless subprocess — exactly the pattern used in `lattice-evals/runner_headless.py`. Each test case runs once against the current lattice-wiki plugin (Claude Sonnet via Claude Code). Output is snapshotted as a JSON file in `eval/baselines/`.
- **D-05:** **Port the headless runner + verifier + IsolationContext architecture from lattice-evals into `cores/eval-harness`** — as independent code (no dep on `lattice-evals` package). Reference files:
  - `runner_headless.py` — `_build_cmd()`, `run_headless()`, `RunResult` dataclass
  - `orchestrator.py` — `run_one()`, worktree lifecycle, metrics accumulation
  - `isolation.py` — `IsolationContext` git worktree management
  - `pricing.py` — cost-per-million-token table pattern (extend for Bedrock models)
- **D-06:** **Git worktree isolation per run** — even though `query` is read-only, adopt `IsolationContext` now. Reasons: (a) matches the ported pattern, (b) future commands (scan, lint) will need it, (c) isolation prevents runs from polluting each other's search index (`.code-wiki/` state).

### Judge Panel Configuration (EVAL-05)

- **D-07:** `judge_b` = **Amazon Nova Pro** (`us.amazon.nova-pro-v1:0` — researcher verifies the cross-region inference ARN for Pat's account). Update `models.toml` `[roles.judge_b]` accordingly.
- **D-08:** Heterogeneous panel: `judge_a` (Claude Sonnet 4.6) + `judge_b` (Amazon Nova Pro). Both instantiated as `deepeval.AmazonBedrockModel`; each scores independently; final score is the mean. Panel composition satisfies EVAL-05's "position-bias check" requirement — swap answer position, confirm score delta < 5%.

### Model Sweep Candidates (EVAL-04)

- **D-09:** Initial librarian sweep: **Haiku 4.5** (current default, baseline speed/cost reference) + **Nova Lite** (cheapest Amazon alternative) + **Qwen3 32B** (`qwen.qwen3-32b-v1:0` — dense 32B, on-demand, no cross-region prefix needed).
- **D-10:** Sweep configuration lives in `models.toml` or a separate `eval/sweep.toml` (planner decides); the sweep runner reads it to enumerate candidate models per role.

### Claude's Discretion

- **Exact Kimi K2.5 Bedrock ARN** — researcher verifies against Pat's account (check `aws bedrock list-foundation-models` or Bedrock console for `moonshot` or `kimi` model IDs)
- **`eval/cases/` JSON schema** — planner designs; suggest `{query, expected_answer, tags?}` per case
- **`eval/baselines/` JSON structure** — each file should include: query, lattice-wiki answer, pinned model ARN, timestamp, content hash of fixture vault (EVAL-08 reproducibility)
- **`eval/runs/` gitignore status** — planner decides if sweep results are committed or gitignored
- **deepeval GEval metric prompt** — what the judge is asked to score (relevance? citation accuracy? factual correctness vs. expected answer?); planner designs
- **Cost pricing extension** — add Nova Lite, Nova Pro, Kimi K2.5 pricing to a `pricing.py` module in `cores/eval-harness` (extend lattice-evals pattern: USD per million tokens)
- **`IsolationContext` implementation** — git worktree or temp-dir copy? Researcher checks lattice-evals `isolation.py` for the exact pattern; planner adapts for `code-wiki-agent`'s vault structure (`.code-wiki/` state dir needs to be in the worktree copy)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 4: Eval Harness" — phase goal, success criteria, requirements (EVAL-01..10)
- `.planning/REQUIREMENTS.md` §"Evaluation Harness (EVAL)" — full requirement text EVAL-01..10
- `.planning/STATE.md` §"Research Flags" — Phase 4 research risk: "deepeval 4.0 AmazonBedrockModel cost tracking fields need verification; heterogeneous judge panel with two GEval instances has no prior art in deepeval docs"
- `.planning/PROJECT.md` §"Key Decisions" — "Eval = cost-frontier per subagent role, baselined from current tool"

### Prior Phase CONTEXT (patterns this phase extends)
- `.planning/phases/03-query-vertical-slice-hybrid-search/03-CONTEXT.md` — D-06 (`QueryResult` dataclass that the eval sweep receives), D-07 (top-K=5 default), D-08 (state-gate always-passes for query)
- `.planning/phases/02-subagent-fan-out-runtime/02-CONTEXT.md` — D-04 (SubagentPool API), D-06 (FanOutResult), D-09 (tokens from usage_metadata), D-10 (trace writer)

### Existing Code — Deliverables from Phases 1-3
- `cores/vault-io/tests/fixtures/round-trip-vault/` — **THE EVAL FIXTURE VAULT** (real wiki structure: packages, plugins, index.md, log.md; queryable content)
- `cores/model-adapter/src/model_adapter/models.toml` — `judge_a` (Sonnet 4.6) and `judge_b` (needs update to Nova Pro per D-07); `librarian` role (current sweep baseline model)
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — `run_query()` is what the model sweep invokes; `QueryResult` dataclass is what the eval scores
- `cores/subagent-runtime/src/subagent_runtime/pool.py` — trace JSONL format (contains token counts that feed cost calculation)

### Reference Implementation — lattice-evals (PORT SOURCE, not a dependency)
- `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/runner_headless.py` — **MUST READ**: headless `claude -p` runner with `--output-format stream-json --plugin-dir`; `_build_cmd()`, `run_headless()`, `RunResult` dataclass
- `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/orchestrator.py` — `run_one()` orchestration: worktree lifecycle, verifier execution, metrics accumulation
- `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/isolation.py` — `IsolationContext` git worktree management (port this)
- `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/pricing.py` — cost-per-million-tokens table pattern (extend for Bedrock non-Claude models)
- `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/` — full module list for reference (judge.py, metrics.py, schemas.py, qualitative.py, transcript.py, verify/)

### External Documentation (researcher verifies)
- deepeval 4.0 `AmazonBedrockModel`: `https://deepeval.com/integrations/models/amazon-bedrock` — `AmazonBedrockModel` constructor, `cost_per_input_token` param, `GEval` usage with Bedrock
- Bedrock model catalog: `aws bedrock list-foundation-models --region us-east-1` — verify Kimi K2.5 and Nova Pro model IDs / cross-region inference ARNs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cores/model-adapter/src/model_adapter/models.toml` — `judge_a` and `judge_b` roles already defined with concurrency limits; Phase 4 updates `judge_b.model_id` to Nova Pro ARN
- `cores/vault-io/tests/fixtures/round-trip-vault/` — real vault with packages (lattice-wiki-core, lattice-source-parser, lattice-evals, lattice-curator-core), plugins, index.md — usable as eval fixture without modification
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — `run_query(vault_path, query, top_k)` is the sweep entry point; returns `QueryResult(answer, citations, pages_drilled, search_scores)`
- `cores/subagent-runtime/src/subagent_runtime/pool.py` — `FanOutResult` + trace JSONL pattern; sweep accumulates per-run token counts from traces for cost calculation

### Established Patterns
- **`@pytest.mark.integration` + env var skip** — Phase 2/3 pattern; eval tests use `@pytest.mark.eval` + `CODE_WIKI_RUN_EVAL=1` (same skip mechanism, different mark)
- **SubagentPool partial failure** — model sweep should tolerate one model failing without aborting the whole sweep
- **`make_llm(role)`** — resolver in `cores/model-adapter`; the sweep runner instantiates model-under-test via this or directly via `ChatBedrockConverse`

### Integration Points
- New workspace member: `cores/eval-harness/pyproject.toml` — `uv sync` picks it up automatically via `members = ["cores/*", ...]` glob
- `models.toml` — judge_b model_id update is a Phase 4 deliverable
- `eval/` top-level directory — new, parallel to `.planning/` and `cores/` at workspace root

</code_context>

<specifics>
## Specific Ideas

- The baseline recorder runs `claude -p --output-format stream-json --append-system-prompt "EVAL MODE (Q&A): ..." --plugin-dir /path/to/lattice-wiki` with `--add-dir <fixture_vault>` — same flags as lattice-evals `_build_cmd()`. The prompt is the test case query string. The recorded answer + wikilink citations are snapshotted.
- The model sweep invokes `run_query()` from `commands/query.py` with a temporary `models.toml` that swaps the `librarian` model_id to each candidate. This avoids running the full `claude` CLI for the sweep — the sweep calls the Python `run_query()` function directly with the model under test.
- `eval/cases/` should include at least 3–5 query cases that exercise different aspects of the vault: a package-lookup query, a concept query, and a cross-reference query.
- The cost-frontier report is a pytest-captured JSON or a printed table — either works; planner picks the simplest option that shows quality-score vs. cost-per-run per model.
- The `IsolationContext` worktree for query eval only needs to copy the fixture vault + the `.code-wiki/` index if pre-built; the search index rebuild can be part of the sweep setup.

</specifics>

<deferred>
## Deferred Ideas

- **Eval for scan/lint/ingest/log commands** — Phase 5 concern; these commands need their own baseline recording after they're built
- **`pytest-evals` package** — EVAL-10 mentions it; planner determines whether `deepeval` already provides this or if it's a separate PyPI package; if unavailable, the `@pytest.mark.eval` skip gate suffices for v1
- **Embedding dimension tuning for eval fixtures** — already deferred from Phase 3; not a Phase 4 concern
- **A/B prompt regression suite** — V2-EVAL-03; not v1 scope
- **Confidence calibration** — V2-EVAL-01; not v1 scope

</deferred>

---

*Phase: 4-Eval Harness*
*Context gathered: 2026-05-14*
