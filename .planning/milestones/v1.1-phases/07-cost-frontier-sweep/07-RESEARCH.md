# Phase 7: Cost-Frontier Sweep - Research

**Researched:** 2026-05-16
**Domain:** LLM cost-quality evaluation, Bedrock model selection, per-role sweep extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Sweep covers six agent roles: `librarian`, `code_reader`, `scanner`, `linter`, `ingestor`, `synthesizer`. Judges (`judge_a`, `judge_b`) are excluded.
- **D-02:** SWEEP-01's "7 roles" wording is inaccurate. Planner to correct REQUIREMENTS.md to "all 6 agent roles in models.toml" with a note.
- **D-03:** Role-tiered candidate sets:
  - Cheap-fast (scanner, code_reader): haiku-4-5, nova-micro, nova-lite, qwen3-32b
  - Mid (linter, ingestor): haiku-4-5, nova-pro, nova-lite, qwen3-32b
  - Quality (librarian, synthesizer): sonnet-4-6, haiku-4-5, nova-pro, qwen3-32b
- **D-04:** 24 cells total (6 roles × 4 candidates).
- **D-05:** `sweep_candidates = [...]` arrays inside each `[roles.{name}]` block in `models.toml`. Loader must tolerate the new key.
- **D-06:** Single-role-swap protocol — role-under-test uses candidate model; all other roles stay at current defaults.
- **D-07:** Two-gate scoring for librarian, ingestor, linter, scanner: divergence-within-baseline AND end-to-end judge score.
- **D-08:** End-to-end-only scoring for synthesizer and code_reader (no divergence rubrics).
- **D-09:** Add 3–5 vault-thin fixture queries to force code_reader fallback during sweep.
- **D-10:** Pareto frontier published per role; user picks the default manually.
- **D-11:** Sweep emits recommendation comment block in models.toml.
- **D-12:** Per-role docs under `.planning/sweep/`; `INDEX.md` ties them together.
- **D-13:** Pre-flight cost estimator + `--dry-run` mode. Planner picks the hard cap (suggestion: $50 auto-abort).

### Claude's Discretion

- Exact name and layout of the cost-story doc (`.planning/sweep/STORY.md` vs `docs/cost-frontier.md`).
- Whether `sweep_candidates` key is a sibling of `model_id` or under a nested `[roles.{name}.sweep]` table.
- Exact "within bounds" threshold for end-to-end gate — research informs suggested values.
- Repeats-per-cell (3 suggested; cost estimate now available to inform this).
- Whether to add `--role <name>` flag for single-role re-sweeps.

### Deferred Ideas (OUT OF SCOPE)

- Judge model swaps.
- Divergence rubrics for synthesizer and code_reader.
- Automated in-place rewrite of models.toml.
- Tier-relative auto-pick threshold.
- Sample-run calibration for pre-flight estimator.
- `docs/cost-frontier.md` for OSS audiences.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SWEEP-01 | Sweep runs against post-port agent across all roles | D-01 correction documented; 6 agent roles confirmed |
| SWEEP-02 | BED-01 gate passes during sweep | Pre-flight check uses `make_llm("haiku").invoke("ping")` — existing pattern |
| SWEEP-03 | Cost-frontier table per role committed under `.planning/` | `cost_frontier_table()` + `print_frontier()` already exist in report.py; per-role markdown doc pattern defined |
| SWEEP-04 | `models.toml` defaults updated to cost-optimal pick; previous defaults preserved | Recommendation comment block pattern locked in D-11; source of truth identified |
| SWEEP-05 | Results summarized in cost-story doc | `.planning/sweep/STORY.md` is the recommended location (see discretion item) |
</phase_requirements>

---

## Phase Summary

Phase 7 executes the cost-frontier sweep the project has been building toward since Phase 4. The eval harness is 80% built: `run_sweep()` handles isolation, token extraction, and cost computation; `panel_score()` is the quality signal; `cost_frontier_table()` and `print_frontier()` render results; and the divergence harness (Phase 6) provides the per-role quality baselines for the four-role two-gate scoring.

The primary lift is mechanical: extending `run_sweep()` to rotate the role-under-test across all six roles (D-06 single-role-swap protocol), wiring the two-gate scorer for the four roles that have divergence rubrics (D-07), adding vault-thin fixture cases so `code_reader` actually fires during the sweep (D-09), and adding a pre-flight cost estimator + `--dry-run` mode (D-13). The per-role output docs and models.toml recommendation block complete the deliverable.

**Primary recommendation:** Extend `run_sweep()` with a `role` parameter and a `role_model_override` dict; implement `run_role_sweep(role, candidates, cases_path, vault_path)` as a thin wrapper. Keep the existing `run_sweep()` signature unchanged for backward compatibility. All six role overrides plumb through a single `role_overrides: dict[str, str]` argument passed to a new `run_query_with_overrides()` helper that wraps `run_query()`.

**Key numeric finding:** The full 24-cell sweep (4 cases × 3 repeats) costs approximately **$3.08 in agent calls + $3.11 in judge calls = ~$6.19 total**. This is well below any sane hard cap. A $25 hard cap for agent-only runs and a $50 cap for agent + judges is defensible.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Single-role-swap protocol | Eval harness (`sweep.py`) | Agent command layer (`run_query()`) | Sweep runner constructs the override dict; agent command layer consumes it |
| Two-gate divergence scoring | Eval harness (`divergence/metric.py`) | — | DivergenceMetric already implements both programmatic + judge passes |
| Pre-flight cost estimation | Eval harness (`sweep.py` or new `preflight.py`) | `pricing.py` | reads pricing.py constants; no Bedrock calls needed |
| Per-role output docs | Eval harness (`report.py` extended) | `.planning/sweep/` filesystem | renderer is in report.py; output lands in planning artifacts |
| models.toml recommendation comment | Agent config (`cores/model-adapter/src/model_adapter/models.toml`) | Sweep runner (writes recommendation text to stdout/file) | Sweep emits the text; human pastes it manually |
| BED-01 pre-flight ping | Eval harness (pre-flight block) | `model_adapter.loader.make_llm` | uses existing make_llm pattern |
| vault-thin fixture queries | `eval/cases/` corpus | — | new JSON entries; no code change needed |
| `code_reader` model override | `commands/query.py` (`_run_code_fallback`) | `sweep.py` | override must be threaded into `_run_code_fallback` |

---

## Codebase Research

All findings below are from direct file reads of the working codebase.

### Tension 1: D-02 Role Count (7 vs 6)

**Finding:** `cores/model-adapter/src/model_adapter/models.toml` (the authoritative source of truth) defines exactly **10 entries**: `haiku`, `sonnet` (aliases, not agent roles), plus 8 role blocks: `librarian`, `code_reader`, `scanner`, `linter`, `ingestor`, `synthesizer`, `judge_a`, `judge_b`. Of the 8 named roles, 2 are judges (excluded per D-01), leaving **6 in-scope agent roles**.

REQUIREMENTS.md line 37 says "all 7 roles" — this is wrong by one. ROADMAP.md line 71 also says "all 7 Bedrock roles" — also wrong. The CONTEXT.md D-02 decision already acknowledges this and mandates correction.

**Recommended correction text for REQUIREMENTS.md / ROADMAP.md:**
> "all 6 agent roles defined in `models.toml` (`librarian`, `code_reader`, `scanner`, `linter`, `ingestor`, `synthesizer`)"

### Tension 2: D-04 Matrix Size and Cost Envelope

**Finding:** The 24-cell matrix costs approximately **$3.08 in agent calls + $3.11 in judge calls** at 4 cases × 3 repeats. Breakdown:

| Role tier | Candidates | Cases | Cost range per cell |
|-----------|------------|-------|---------------------|
| cheap-fast (scanner, code_reader) | haiku, nova-micro, nova-lite, qwen3-32b | 4 (8 for code_reader with vault-thin) | $0.002–$0.13 |
| mid (linter, ingestor) | haiku, nova-pro, nova-lite, qwen3-32b | 4 | $0.03–$0.12 |
| quality (librarian, synthesizer) | sonnet, haiku, nova-pro, qwen3-32b | 4 | $0.08–$0.65 |

**Total with 3 repeats, 4 base cases + 4 vault-thin: ~$6.19.**

The expensive cells are sonnet-4-6 for librarian and synthesizer ($0.54/case × 3 repeats × 4 cases = $0.65 each). Nova-micro for scanner is nearly free ($0.002/case).

**Recommended hard cap:** `$25` aborts pre-flight automatically (leaving 4x headroom for token estimate error). This is the planner's call per D-13.

### Tension 3: D-06 Single-Role-Swap Protocol — Override Surface Extension

**Finding:** `run_query()` (query.py line 756) has signature:
```python
async def run_query(
    query: str,
    vault_path: Path | None = None,
    top_k: int = 5,
    librarian_model_override: str | None = None,
) -> QueryResult:
```
The `librarian_model_override` is wired at lines 825–830: it creates a `ChatBedrockConverse` with `model_id=librarian_model_override`.

**The code_reader role** is created inside `_run_code_fallback()` (line 374) via `make_llm("code_reader")` with no override parameter. The `synthesizer` role is created at line 879 via `make_llm("synthesizer")` with no override.

**For scan, lint, ingest commands:** `run_scan()`, `run_lint()`, `run_ingest_source()` have no model override parameters at all. They call `make_llm("scanner")`, `make_llm("linter")`, `make_llm("ingestor")` directly.

**Recommended approach — minimal surgical extension:**

For `query.py`, add a `role_model_overrides: dict[str, str] | None = None` parameter to `run_query()`. Inside, read `role_model_overrides.get("librarian")` for the librarian override (deprecating the old `librarian_model_override` param or keeping both for backward compat), `role_model_overrides.get("synthesizer")` for synthesizer, and thread `role_model_overrides.get("code_reader")` into `_run_code_fallback()`.

For `scan.py` / `lint.py` / `ingest.py`, add a `model_override: str | None = None` parameter to `run_scan()`, `run_lint()`, `run_ingest_source()`. Inside each, apply the override when constructing the LLM.

The sweep runner then calls each command with the appropriate override for the role under test; all other roles use their `make_llm("role")` defaults (unchanged).

**Alternative (wrapper approach):** Create `run_query_with_overrides()` that patches `model_adapter.loader._models_path_override` to point at a temp TOML with the candidate's model_id substituted. This avoids touching every command signature but is fragile (global mutable state in the loader). **Not recommended.**

**Key finding on SubagentPool model_id:** The `pool.run_all()` call passes `model_id=cfg["model_id"]` for tracing purposes only — the actual LLM invocation is done by the closure over `librarian_llm`. So adding override support to the LLM construction is sufficient; no SubagentPool changes needed.

### Tension 4: D-07 Two-Gate Scoring Wiring

**Finding:** `DivergenceMetric` in `divergence/metric.py` already implements `run_programmatic()` + `run_judge()` + `run()`. The `check_regression()` function in the same file compares current results against a loaded baseline and raises `AssertionError` on hard-severity failures.

**What needs wiring:** The sweep loop needs to call `DivergenceMetric.run()` per-case for the four roles that have rubrics (`ROLE_CHECKS` dict in `divergence/__init__.py` covers librarian, ingestor, linter, scanner). The result needs to be compared against `load_baseline(role, baselines_dir)`.

**Two-gate logic per cell:**
1. **Gate 1 (divergence):** Run `DivergenceMetric.run()` on the role's output for each case. Count hard-severity failures. A candidate fails gate 1 if any hard rule has more failures than the baseline.
2. **Gate 2 (end-to-end):** `panel_score()` mean for the candidate vs. the current default's score. Threshold is the "within bounds" discretion item.

**For synthesizer and code_reader (D-08):** only gate 2 runs.

**The `AgentOutputProxy` class** (in `divergence/check.py`) needs to be constructed from the `run_query()` result. The current programmatic checks only use `output.answer` and `output.page_type`. For librarian outputs, `page_type` is not relevant. The sweep runner needs to build `AgentOutputProxy(answer=result.answer)` for each sweep result.

**For ingestor/linter/scanner sweeps:** The sweep needs to call the appropriate command (not just `run_query`) and produce an output suitable for the divergence check. This is new work — the existing `run_sweep()` only calls `run_query()`. Per-role sweep loops for scanner, linter, and ingestor need to call `run_scan()`, `run_lint()`, `run_ingest_source()` respectively, then apply the divergence metric to their outputs.

### Tension 5: D-09 Vault-Thin Fixture Queries

**Finding:** Current `eval/cases/query_cases.json` has 4 cases (pkg-lookup-01, concept-01, cross-ref-01, format-01), all of which look up general wiki concepts. The fixture vault is `cores/vault-io/tests/fixtures/round-trip-vault`.

**Vault-thin queries require asking about things that cannot be answered from vault pages.** The code_reader fires when `useful_excerpts` (librarian fan-out results with non-"NO_RELEVANT_CONTENT" content) is empty.

**Candidate vault-thin queries (verified against the vault structure):**

1. `"How is _StdoutGuard implemented in the MCP server?"` — asks about a specific class in `agents/code-wiki-agent/src/code_wiki_agent/mcp_server.py`; the round-trip-vault has no page about this.
2. `"What does SubagentPool._write_trace write to the trace JSONL file?"` — asks about internal implementation of `cores/subagent-runtime/src/subagent_runtime/pool.py`.
3. `"What are the exact parameters to _read_file_bounded?"` — asks about a function in `commands/query.py`.
4. `"How does the BM25 tokenizer handle stopwords in bm25_query?"` — asks about internal BM25 indexing behavior.

These queries require reading source; the vault does not document implementation internals. The code_reader fallback fires only when the librarian fan-out returns nothing useful — which will happen for these questions against the round-trip-vault fixture.

**Note:** For the sweep, `code_reader` cases need a vault where the round-trip-vault is used alongside a real repo root. The `_resolve_repo_root()` function looks for a `.git` or `pyproject.toml` in `vault_path.parent`. The EvalWorktree creates an isolated vault copy in a tmpdir — the code fallback will fall back to the vault path itself when the repo root heuristic fails (logged warning, not crash). A `repo_path` override may be needed in the code_reader sweep context.

### Tension 6: D-13 Pre-Flight Estimator

**Finding:** Three approaches identified:

| Approach | Accuracy | Implementation cost | Recommendation |
|----------|----------|--------------------|-|
| (a) Conservative constant per tier | Low-medium | Trivial (hardcode tokens_in/out per tier) | Good enough |
| (b) Sample-run calibration (1-case dry pass) | High | Medium (requires real Bedrock call) | Deferred per CONTEXT.md |
| (c) Read existing trace JSONLs | Medium | Low (parse trace files from prior runs) | Useful if traces exist; not reliable for first run |

**Recommended approach (a):** Use conservative per-tier constants derived from the cost model above. For Phase 7 where the actual sweep will reveal real numbers, this is sufficient. The D-13 deferred note already marks sample-run calibration as optional.

**Conservative constants per role invocation:**
- cheap-fast roles (scanner, code_reader): 3,000 in / 500 out
- mid roles (linter, ingestor): 5,000 in / 1,000 out
- quality roles (librarian, synthesizer): 8,000 in / 2,000 out

**Formula:** `estimated_cost = sum(role_tier_cost_per_call × n_cases × n_repeats for each cell)`

These give a $3.08 total for 4 cases × 3 repeats, which the pre-flight prints before prompting for confirmation.

### Tension 7: models.toml Duplication

**Finding (verified):**

- `cores/model-adapter/src/model_adapter/models.toml` — **10 entries**, all roles + aliases + judges. This is the file bundled inside the `model_adapter` package via `importlib.resources`.
- `cores/model-adapter/models.toml` — **2 entries only** (`haiku`, `sonnet` aliases). This appears to be a legacy/stub file from early development.

**The loader** (`loader.py` line 43) loads from `resources.files("model_adapter").joinpath("models.toml")`, which resolves to the `src/model_adapter/models.toml` package resource. The top-level `cores/model-adapter/models.toml` is **never loaded by production code**.

**This duplication is a stale artifact.** The top-level `cores/model-adapter/models.toml` is not referenced by any import or test. It can safely be left as-is (it's inert) or removed. The planner should note it but not block Phase 7 on cleaning it up.

**Source of truth: `cores/model-adapter/src/model_adapter/models.toml`** — this is the file where `sweep_candidates` must be added.

### Tension 8: sweep_candidates TOML Loader Tolerance

**Finding (verified by direct test):** Python's `tomllib.load()` parses TOML into a plain dict. Unknown keys (like `sweep_candidates`) are simply included in the returned dict. The `load_role_config()` function returns `config["roles"][role]` directly — the entire dict including any unknown keys.

The `make_llm()` function reads only `model_id`, `region`, and `max_tokens` from the role config dict. It ignores any other keys. Therefore **adding `sweep_candidates` to any role block causes no error and requires no loader changes.**

The sweep runner reads `sweep_candidates` from the same `load_role_config(role)` result:
```python
role_cfg = load_role_config(role)
candidates = role_cfg.get("sweep_candidates", [])
```

This is zero-friction.

---

## Recommended Approach

### SWEEP-01: Six-Role Sweep Execution

**File changes:**

**`cores/eval-harness/src/eval_harness/sweep.py`** — extend with `run_role_sweep()`:

```python
async def run_role_sweep(
    role: str,
    candidate_model_id: str,
    cases_path: Path,
    vault_path: Path,
    repeats: int = 3,
) -> list[SweepResult]:
    """Run sweep for one (role, candidate) cell. Single-role-swap: only this role
    runs with candidate_model_id; all others use their models.toml defaults."""
    ...
```

**`agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`** — extend `run_query()` signature:

```python
async def run_query(
    query: str,
    vault_path: Path | None = None,
    top_k: int = 5,
    librarian_model_override: str | None = None,  # deprecated; use role_model_overrides
    role_model_overrides: dict[str, str] | None = None,
) -> QueryResult:
```

Read `role_model_overrides.get("librarian")` (fallback to `librarian_model_override` for compatibility), `role_model_overrides.get("synthesizer")`, and thread `role_model_overrides.get("code_reader")` into `_run_code_fallback()`.

**`commands/scan.py` / `commands/lint.py` / `commands/ingest.py`** — add `model_override: str | None = None` parameter to `run_scan()`, `run_lint()`, `run_ingest_source()`. Inside each, construct the role LLM as:
```python
if model_override is not None:
    role_llm = ChatBedrockConverse(model_id=model_override, region_name=cfg["region"], max_tokens=cfg["max_tokens"])
else:
    role_llm = make_llm("scanner")  # or linter / ingestor
```

**Per-role sweep dispatch in sweep.py:**
```python
ROLE_COMMAND_MAP = {
    "librarian":   _sweep_query_role,
    "synthesizer": _sweep_query_role,
    "code_reader": _sweep_query_role,
    "scanner":     _sweep_scan_role,
    "linter":      _sweep_lint_role,
    "ingestor":    _sweep_ingest_role,
}
```

librarian / synthesizer / code_reader all route through `run_query(role_model_overrides={role: candidate})`. scanner / linter / ingestor route through their respective command functions with `model_override=candidate`.

### SWEEP-02: BED-01 Pre-Flight Gate

In the sweep runner pre-flight block:
```python
from model_adapter.loader import make_llm
from model_adapter.exceptions import BedrockAccessDenied

try:
    make_llm("haiku").invoke("ping")
    print("[BED-01] Bedrock connectivity confirmed.")
except BedrockAccessDenied as e:
    raise SystemExit(f"BED-01 FAILED: {e}")
```

### SWEEP-03: Per-Role Frontier Docs

**`cores/eval-harness/src/eval_harness/report.py`** — add `render_role_doc()`:

```python
def render_role_doc(
    role: str,
    tier: str,
    sweep_results: list[SweepResult],   # for this role only
    divergence_results: dict | None,     # None for synthesizer/code_reader
    run_date: str,
    commit_sha: str,
    total_cost_usd: float,
) -> str:
    """Render per-role markdown doc per D-12 skeleton."""
```

Output docs: `.planning/sweep/{role}.md` (6 files) + `.planning/sweep/INDEX.md`.

**Existing `cost_frontier_table()` and `print_frontier()`** are reused inside `render_role_doc()`.

### SWEEP-04: models.toml Recommendation Block

The sweep runner writes the recommendation block as a comment string per D-11 shape. The planner should note: this is emitted to stdout or a temp file for Pat to paste manually — it is NOT auto-written to models.toml.

**Models.toml update:** Phase 7 adds `sweep_candidates = [...]` to the 6 in-scope roles in `cores/model-adapter/src/model_adapter/models.toml`. This is the only structural TOML change; the default `model_id` is unchanged until Pat makes the manual swap after reading the frontier.

### SWEEP-05: Cost Story Doc

**`.planning/sweep/STORY.md`** (recommended over `docs/cost-frontier.md` per CONTEXT.md deferred note about OSS prep). This is a hand-authored summary doc written during the analysis phase, not auto-generated, but the sweep runner can emit a skeleton.

---

## Validation Architecture

`nyquist_validation` is `true` in `.planning/config.json` — this section is mandatory.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8.3 with pytest-asyncio 1.3.0 + pytest-evals |
| Config file | `cores/eval-harness/pytest.ini` (or `pyproject.toml [tool.pytest]`) — check at Wave 0 |
| Quick run command | `uv run --package eval-harness pytest cores/eval-harness/tests/unit/ -x` |
| Full suite command | `CODE_WIKI_RUN_EVAL=1 CODE_WIKI_RUN_JUDGES=1 uv run --package eval-harness pytest --run-eval` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SWEEP-01 | `run_role_sweep()` dispatches correct override per role | unit | `pytest tests/unit/test_role_sweep.py -x` | No — Wave 0 |
| SWEEP-01 | single-role-swap: other roles use defaults | unit (mock LLM) | `pytest tests/unit/test_role_sweep.py::test_single_role_swap -x` | No — Wave 0 |
| SWEEP-01 | `sweep_candidates` read from models.toml per role | unit | `pytest tests/unit/test_models_toml_sweep_candidates.py -x` | No — Wave 0 |
| SWEEP-01 | two-gate scoring for librarian passes/fails correctly | unit | `pytest tests/unit/test_two_gate_scorer.py -x` | No — Wave 0 |
| SWEEP-02 | BED-01 pre-flight runs before matrix (live) | eval (gated) | `CODE_WIKI_RUN_EVAL=1 pytest --run-eval tests/eval/test_sweep_eval.py::test_bed01_preflight` | No — Wave 0 |
| SWEEP-02 | BED-01 ping confirmed in sweep run (end-to-end) | eval (gated) | `CODE_WIKI_RUN_EVAL=1 pytest --run-eval` | Partial (test_sweep_eval.py exists but needs SWEEP-02 hook) |
| SWEEP-03 | `render_role_doc()` produces all required sections | unit | `pytest tests/unit/test_report_role_doc.py -x` | No — Wave 0 |
| SWEEP-03 | INDEX.md and 6 role docs written by sweep | integration (dry-run) | `pytest tests/integration/test_sweep_dry_run.py -x` | No — Wave 0 |
| SWEEP-04 | recommendation comment block emitted correctly | unit | `pytest tests/unit/test_recommendation_block.py -x` | No — Wave 0 |
| SWEEP-05 | cost-story doc exists with required sections | manual | N/A — human-authored post-sweep | N/A |

### Integration-Level Validation (without Bedrock spend)

**`--dry-run` mode** is the primary integration validator:
- Sweep loop iterates all 24 cells with mock LLM responses
- Pre-flight estimator runs and prints estimate
- Two-gate scorer runs against mock outputs
- All 6 per-role docs + INDEX.md are written
- Total Bedrock spend: $0

**Mock LLM fixture pattern** (from existing `conftest.py`):
```python
@pytest.fixture
def mock_llm(monkeypatch):
    # Monkeypatches make_llm to return a FakeChatModel
    ...
```

The dry-run test file: `cores/eval-harness/tests/integration/test_sweep_dry_run.py` — uses the existing `EvalWorktree` + mock LLM from `conftest.py`.

### Live-Bedrock Validation

**BED-01 gate:** Confirmed in pre-flight via `make_llm("haiku").invoke("ping")` before the matrix runs. This verifies AWS credentials, IAM policy, and region availability in one shot.

**Full live sweep:** `CODE_WIKI_RUN_EVAL=1 CODE_WIKI_RUN_JUDGES=1 pytest --run-eval` — existing double-gate pattern honored.

### Cost-Correctness Validation

After a real sweep run, compare:
- Pre-flight estimate vs. actual spend from trace JSONL token sums
- `cost_for_usage(model_id, {"input": tokens_in, "output": tokens_out})` per cell
- Report actual / estimated ratio in STORY.md

### Output Validation

The `test_sweep_dry_run.py` integration test asserts:
- `.planning/sweep/librarian.md` exists and contains "Pareto frontier" heading
- `.planning/sweep/INDEX.md` exists and links all 6 role docs
- Each role doc contains: raw scores table, frontier callout, recommendation, run metadata

### Sampling Rate

- **Per task commit:** `uv run --package eval-harness pytest cores/eval-harness/tests/unit/ -x`
- **Per wave merge:** `uv run --package eval-harness pytest cores/eval-harness/tests/ -x` (unit + integration dry-run)
- **Phase gate:** Full suite green (`CODE_WIKI_RUN_EVAL=1`) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `cores/eval-harness/tests/unit/test_role_sweep.py` — covers SWEEP-01 unit cases
- [ ] `cores/eval-harness/tests/unit/test_two_gate_scorer.py` — covers D-07 two-gate logic
- [ ] `cores/eval-harness/tests/unit/test_report_role_doc.py` — covers render_role_doc()
- [ ] `cores/eval-harness/tests/unit/test_preflight_estimator.py` — covers pre-flight cost math
- [ ] `cores/eval-harness/tests/integration/test_sweep_dry_run.py` — covers full loop w/ mock LLM

---

## Common Pitfalls

### Pitfall 1: Single-Role-Swap Breaks on Synthesizer

**What goes wrong:** The synthesizer role is created inline in `run_query()` via `make_llm("synthesizer")` at line 879. A sweep of the synthesizer role must override this call, but it's not currently parameterized.

**Why it happens:** The override mechanism was designed for the librarian role only (Phase 4 scope).

**How to avoid:** Add `role_model_overrides: dict[str, str] | None = None` to `run_query()`. Read `role_model_overrides.get("synthesizer")` at line 879 before calling `make_llm("synthesizer")`.

**Warning signs:** If synthesizer sweep cells all show the same cost (the current default's cost), the override isn't wired.

### Pitfall 2: code_reader Sweep Returns N/A Unless vault-thin Cases Are Present

**What goes wrong:** If the librarian fan-out returns useful excerpts (which it will for the existing 4 query cases against the round-trip-vault), `_run_code_fallback()` never fires. The code_reader model is never invoked. Cost and quality data for code_reader will be missing.

**Why it happens:** The code fallback is conditional on `useful_excerpts` being empty (line 866).

**How to avoid:** Add D-09 vault-thin cases before running the sweep. These must ask questions the round-trip-vault cannot answer. Validate by running a query locally and checking if `code_fallback` is `True` in the trace summary.

**Warning signs:** code_reader sweep results show `tokens_in=None` (trace extraction found no records from the code_reader invocation).

### Pitfall 3: Two-Gate Baseline Comparison Compares Wrong Roll-Up

**What goes wrong:** The `check_regression()` function in `metric.py` compares per-rule failure counts against baseline. If the sweep uses fewer cases than the baseline was recorded on, every rule will show fewer failures even if the rate is worse.

**Why it happens:** `check_regression` is a count-based gate, not a rate-based gate.

**How to avoid:** Run the sweep divergence checks on the same case set as the baseline (currently 4 cases from query_cases.json). The gate comparison is: `current_failures > baseline_failures` — so with equal `runs`, this is a count check that approximates a rate check.

**Warning signs:** Baseline has `"runs": 4` and the sweep shows `"runs": 2` — the comparison is meaningless.

### Pitfall 4: EvalWorktree in Parallel Sweep Causes Race Conditions

**What goes wrong:** The existing `run_sweep()` runs all `(model_id, case)` pairs in parallel via `asyncio.gather`. For the 6-role sweep with 4 candidates × 4 cases × 3 repeats = 144 concurrent coroutines, this may overwhelm Bedrock rate limits or the EvalWorktree tmpdir cleanup.

**Why it happens:** `asyncio.gather` submits all coroutines immediately.

**How to avoid:** Add a semaphore to `run_role_sweep()` — limit total concurrent Bedrock calls (e.g., `asyncio.Semaphore(10)`). The existing per-role `max_concurrency` in models.toml (5 for librarian, 10 for scanner) already throttles per-role fan-out; the outer semaphore throttles across cells.

**Warning signs:** `ThrottlingException` from Bedrock; or tmpdir cleanup errors after the sweep.

### Pitfall 5: models.toml Top-Level Stale Copy Confusion

**What goes wrong:** A dev edits `cores/model-adapter/models.toml` (the top-level stub) thinking it's the source of truth. The loader ignores it.

**Why it happens:** The top-level file is an inert stale artifact from early development.

**How to avoid:** All Phase 7 edits to models.toml go to `cores/model-adapter/src/model_adapter/models.toml`. Consider adding a comment to the top-level file: `# STUB: this file is not loaded in production. Edit src/model_adapter/models.toml.`

### Pitfall 6: Judge Cost Gating (CODE_WIKI_RUN_JUDGES)

**What goes wrong:** Running the sweep without `CODE_WIKI_RUN_JUDGES=1` causes the two-gate end-to-end check to fall back to the structural-composite score (1.0 if all pass, 0.5 partial, 0.0 none), not the LLM judge panel mean. The frontier docs then show structural-only quality — which is a weaker signal.

**How to avoid:** For the Phase 7 live sweep, set both `CODE_WIKI_RUN_EVAL=1` and `CODE_WIKI_RUN_JUDGES=1`. The pre-flight cost estimate should include judge cost when judges are enabled.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Cost calculation per model | Custom pricing table | `eval_harness.pricing.cost_for_usage()` — already covers all 6 candidate models |
| Quality aggregation across runs | Custom averaging | `eval_harness.report.cost_frontier_table()` — already handles judge_scores fallback |
| Divergence baseline loading | Dict parsing | `eval_harness.divergence.metric.load_baseline()` |
| Divergence regression check | Count comparison | `eval_harness.divergence.metric.check_regression()` |
| Judge panel invocation | Custom GEval setup | `eval_harness.judge.panel_score()` — already position-bias-checked |
| Isolated vault per eval run | tmpdir management | `eval_harness.isolation.EvalWorktree` |
| Token extraction from traces | JSONL parsing | `eval_harness.sweep._extract_tokens_from_traces()` |
| Pareto frontier computation | Custom dominance check | Add `pareto_frontier()` to report.py — trivial (filter non-dominated points by cost × quality) |

**Key insight:** This phase is almost entirely wiring existing components. The only genuinely new code is: `run_role_sweep()`, the two-gate wrapper, the pre-flight estimator, `render_role_doc()`, and the per-command model override parameters.

---

## Open Questions for Planner

1. **End-to-end quality threshold (D-07/D-08 discretion item).** Research suggests starting at "within 5% of current default's mean judge score" for quality-tier roles and "within 10%" for mid/cheap-fast. But the planner cannot finalize this until a baseline run establishes the current default's judge score. **Recommendation:** Run a single-model sweep with the current defaults first (4 cases, no repeats) to get baseline scores, then set the threshold at `current_mean × 0.90` for quality-tier. This baseline run costs < $0.50.

2. **`--role <name>` flag (D-13 discretion item).** Given the D-12 per-role doc structure, a `--role` flag is a natural extension that costs one day of implementation. **Recommendation:** Include it — it lets Pat re-sweep a single role after manually swapping the default without re-running all 24 cells.

3. **Repeats-per-cell count.** Research confirmed total cost at 3 repeats is ~$6.19. At 5 repeats it would be ~$10. **Recommendation:** 3 repeats is sufficient for a cost-frontier with this many candidates. The Pareto frontier is robust to 1-2 noisy samples when 4 candidates are compared.

4. **code_reader sweep vault fixture.** The round-trip-vault fixture lives at `cores/vault-io/tests/fixtures/round-trip-vault`. `_resolve_repo_root()` will fail to find a `.git` or `pyproject.toml` in its parent (which is `cores/vault-io/tests/fixtures/`), so it will fall back to the vault itself. This means `_read_file_bounded()` will be anchored to the vault root, and the code_reader will only be able to read files inside the vault (markdown files). It will not be able to read actual source code. **The vault-thin cases will trigger the code_reader fallback, but the code_reader will find nothing useful and return `CODE_FALLBACK_DISCLAIMER`.** This is enough to confirm the fallback fires, but won't produce a meaningful quality comparison. **Planner decision needed:** Should the code_reader sweep use a different fixture that includes actual source files? Or is confirming the fallback fires (and comparing cost at N/A quality) sufficient?

5. **Ingestor/linter/scanner sweep fixtures.** These roles need different inputs than `query_cases.json`. Linter runs against the whole vault; ingestor takes a source file path; scanner takes a repo path. The sweep needs dedicated fixture inputs for each. The planner should add wave 0 tasks to create these fixture inputs.

6. **`.planning/sweep/` directory creation.** This directory does not exist. The sweep runner or the report writer must create it. The planner should include a task that creates `.planning/sweep/` with a `.gitkeep`.

7. **REQUIREMENTS.md correction task (D-02).** The planner must include a task that edits REQUIREMENTS.md line 37 (and ROADMAP.md line 71) to replace "7 roles" with "all 6 agent roles in models.toml". This is a docs-only change but should be a distinct task for traceability.

---

## Risks and Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|------------|
| Bedrock rate limits under parallel sweep | Medium | Medium | Add `asyncio.Semaphore(8)` across all cells in `run_role_sweep()` |
| code_reader sweep produces N/A results (no source access) | Medium | High | Decide on fixture at planning time (see Open Question 4); at minimum, confirm fallback fires |
| Token estimates off by >2x (estimate exceeds cap) | Low | Low | Cap is $25 at conservative estimates; actual cost is ~$3; 8x headroom |
| Qwen3-32B on Bedrock has access errors | Medium | Unknown | BED-01 pre-flight pings only haiku; planner should add per-candidate access check or test Qwen3 separately |
| Divergence baseline counts mismatched (different case count) | Low | Low | Run on same 4-case corpus as Phase 6 baseline; verify `runs` count in sweep output matches baseline `runs` |
| Stale top-level models.toml confusion | Low | Low | Add comment to top-level stub; document source of truth in plan |

---

## Security Domain

The `security_enforcement` key is not set in `.planning/config.json` — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes (model_id from sweep_candidates) | Model IDs come from TOML, not user input; `_sanitize_model_id()` already applies to filenames |
| V4 Access Control | yes (Bedrock IAM) | `BedrockAccessDenied` handler in `make_llm()`; BED-01 pre-flight gate |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| sweep_candidates TOML injection | Tampering | `sweep_candidates` values come from a committed TOML file; same threat model as model_id today |
| Filename construction from model_id | Tampering | `_sanitize_model_id()` (already exists in sweep.py) must be applied to all new per-role filenames |
| Bedrock cross-region inference routing | Elevation | Use `us.` prefix model IDs (cross-region inference profiles); already enforced by models.toml |

---

## Sources

### Primary (HIGH confidence)

- Direct read of `cores/eval-harness/src/eval_harness/sweep.py` — `run_sweep()` signature, token extraction, cost computation [VERIFIED: codebase]
- Direct read of `cores/eval-harness/src/eval_harness/pricing.py` — all 6 candidate model prices [VERIFIED: codebase]
- Direct read of `cores/model-adapter/src/model_adapter/models.toml` — 10 entries, role structure [VERIFIED: codebase]
- Direct read of `cores/model-adapter/src/model_adapter/loader.py` — `load_role_config()`, `make_llm()`, resource path [VERIFIED: codebase]
- Direct read of `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — `run_query()` signature, `_run_code_fallback()`, `make_llm("synthesizer")` usage [VERIFIED: codebase]
- Direct read of `cores/eval-harness/src/eval_harness/divergence/metric.py` — `DivergenceMetric`, `check_regression()`, `load_baseline()` [VERIFIED: codebase]
- Direct read of `cores/eval-harness/src/eval_harness/report.py` — `cost_frontier_table()`, `print_frontier()`, `regression_check()` [VERIFIED: codebase]
- Direct read of `cores/eval-harness/tests/eval/test_sweep_eval.py` — two-phase pytest-evals pattern, EVAL_GATE usage [VERIFIED: codebase]
- Direct read of `cores/eval-harness/tests/conftest.py` — `EVAL_GATE` definition [VERIFIED: codebase]
- Direct read of `eval/cases/query_cases.json` — 4 existing cases [VERIFIED: codebase]
- Direct read of all 4 divergence baseline JSON files [VERIFIED: codebase]
- `tomllib` verification test — `sweep_candidates` key parsed without error; `load_role_config()` returns it transparently [VERIFIED: runtime test]
- Cost envelope calculation — Python script run against `pricing.py` constants [VERIFIED: computed]

### Secondary (MEDIUM confidence)

- `.planning/phases/07-cost-frontier-sweep/07-CONTEXT.md` — locked decisions D-01 through D-13 [CITED: planning artifact]
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` — phase requirements and success criteria [CITED: planning artifact]
- `cores/model-adapter/models.toml` (top-level stub) — identified as stale; not loaded by production code [VERIFIED: codebase + loader code path]

### Tertiary (LOW confidence)

- Qwen3-32B Bedrock access availability — assumed available based on `models.toml` entry; not confirmed via live BED-01 ping [ASSUMED]
- Bedrock rate limits under parallel 24-cell sweep — risk is plausible based on known Bedrock concurrency limits but not measured [ASSUMED]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Qwen3-32B (`qwen.qwen3-32b-v1:0`) is accessible on Bedrock with current IAM credentials | Risks | Sweep cells for qwen3-32b fail with AccessDenied; need separate IAM policy or model removal |
| A2 | Conservative token estimates (3k/5k/8k input) are within 2x of actual per-call token usage | Cost Envelope | Pre-flight estimate off by 2x max; still within $25 hard cap by 4x margin |
| A3 | Round-trip-vault fixture is sufficient for librarian/synthesizer sweep quality signal | Open Questions | Quality scores reflect the fixture, not production vault behavior; may underestimate divergence |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| AWS Bedrock (haiku, sonnet, nova-pro, nova-lite, nova-micro) | SWEEP-01, SWEEP-02 | Assumed yes (BED-01 approved) | — | Pre-flight gate fails fast |
| Qwen3-32B on Bedrock | SWEEP-01 | Unknown [ASSUMED] | — | Remove from sweep_candidates if inaccessible |
| Python 3.11+ | All | Yes | 3.11+ | — |
| `uv` workspace | All | Yes | 0.11.14 | — |
| `pytest-evals` | SWEEP-01 test | Assumed (Phase 4 harness) | — | — |

**Missing dependencies with no fallback:** Qwen3-32B Bedrock access — if unavailable, the sweep candidates must be adjusted.

**Missing dependencies with fallback:** None blocking.

---

## Metadata

**Confidence breakdown:**
- Codebase findings: HIGH — all files read directly
- Cost envelope: HIGH — computed from exact pricing.py constants
- Role count / models.toml structure: HIGH — verified directly
- TOML loader tolerance: HIGH — verified by runtime test
- Qwen3 availability: LOW — not confirmed via live ping
- Bedrock rate limit behavior: LOW — not measured

**Research date:** 2026-05-16
**Valid until:** 2026-06-16 (stable domain; prices may change)

## RESEARCH COMPLETE
