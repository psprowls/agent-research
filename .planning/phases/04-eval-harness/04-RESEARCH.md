# Phase 4: Eval Harness - Research

**Researched:** 2026-05-14
**Domain:** deepeval 4.0 + pytest-evals + Bedrock model sweep + git worktree isolation
**Confidence:** HIGH (all critical claims verified via tool calls or official sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Reuse `cores/vault-io/tests/fixtures/round-trip-vault/` as the query eval fixture. No new fixture repos needed for Phase 4.
- **D-02:** Eval artifacts live in a top-level `eval/` directory. Subdirs: `eval/cases/`, `eval/baselines/`, `eval/runs/`.
- **D-03:** Test cases defined as JSON files in `eval/cases/` with `(query, expected_answer)` pairs.
- **D-04:** Baseline recorder invokes `claude -p --output-format stream-json --plugin-dir <lattice-wiki>` as a headless subprocess, exactly the pattern in `lattice-evals/runner_headless.py`.
- **D-05:** Port the headless runner + IsolationContext architecture from lattice-evals into `cores/eval-harness` as independent code (no dep on `lattice-evals`).
- **D-06:** Git worktree isolation per run, even for read-only `query`.
- **D-07:** `judge_b` = Amazon Nova Pro (`us.amazon.nova-pro-v1:0`). Update `models.toml` `[roles.judge_b]`.
- **D-08:** Heterogeneous panel: `judge_a` (Claude Sonnet 4.6) + `judge_b` (Nova Pro). Both as `deepeval.AmazonBedrockModel`. Final score = mean. Position-bias check: swap answer, delta < 5%.
- **D-09:** Initial librarian sweep: Haiku 4.5 + Nova Lite + Qwen3 32B (`qwen.qwen3-32b-v1:0`, on-demand only, no cross-region prefix).
- **D-10:** Sweep config in `models.toml` extension or separate `eval/sweep.toml` (planner decides).

### Claude's Discretion

- `eval/cases/` JSON schema
- `eval/cases/` JSON schema
- `eval/baselines/` JSON structure
- `eval/runs/` gitignore status
- deepeval GEval metric prompt design
- Cost pricing extension for `pricing.py`
- IsolationContext adaptation for `.code-wiki/` state dir

### Deferred Ideas (OUT OF SCOPE)

- Eval for scan/lint/ingest/log commands (Phase 5)
- `pytest-evals` CI integration beyond `@pytest.mark.eval` skip gate
- A/B prompt regression suite (V2-EVAL-03)
- Confidence calibration (V2-EVAL-01)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EVAL-01 | `cores/eval-harness` is a separate package usable by future agents | Package scaffold in `cores/eval-harness/` per workspace glob `cores/*` |
| EVAL-02 | Fixture corpus: small test repos with pre-built wikis in `tests/fixtures/` | Round-trip-vault already has BM25 + SQLite indexes committed; usable as-is |
| EVAL-03 | Baseline recorder: headless `claude -p` subprocess snapshots lattice-wiki output | Port `runner_headless.py` + `_build_cmd()` directly; `EVAL_SYSTEM_PROMPT_QA` is the right prompt mode |
| EVAL-04 | Model sweep runner: N Bedrock models for a role with fixed prompts | Sweep calls `run_query()` directly with swapped `make_llm(role)` — no `claude` CLI needed |
| EVAL-05 | `deepeval` 4.0 with AmazonBedrockModel; heterogeneous judge panel | `GEval` + two `AmazonBedrockModel` instances; mean-score aggregation; position-bias swap test |
| EVAL-06 | Structural metrics: wikilink resolution, frontmatter valid, JSON schema match | Pure Python deterministic checks on `QueryResult`; no LLM calls |
| EVAL-07 | Cost-frontier report: quality vs $/run table | `pricing.py` module with verified token prices; sweep accumulates `tokens_in`/`tokens_out` from trace JSONL |
| EVAL-08 | Reproducibility: each run pins model ARN + prompt hash + timestamp + seed | Baseline JSON schema includes all four fields; vault content hash for fixture pinning |
| EVAL-09 | Regression check vs baseline; CI-friendly failure | Compare composite score against configurable threshold; raise `AssertionError` with structured message |
| EVAL-10 | pytest integration via `pytest-evals` | `pytest-evals` 0.3.4 is a real PyPI package; use `@pytest.mark.eval` + `eval_bag`; also add `@pytest.mark.eval` skip gate with `CODE_WIKI_RUN_EVAL=1` |
</phase_requirements>

---

## Summary

Phase 4 builds `cores/eval-harness` — the cost-frontier measurement infrastructure for the `query` command. There are four distinct components: a **baseline recorder** (headless `claude -p` subprocess via ported `runner_headless.py`), a **model sweep runner** (directly calls `run_query()` with swapped model configs, no `claude` CLI), a **heterogeneous judge panel** (two `deepeval.AmazonBedrockModel` instances running independent `GEval` metrics), and a **cost-frontier report** (pricing table × sweep token accumulation).

All critical research risks have been resolved: deepeval 4.0 AmazonBedrockModel and GEval APIs are verified. Nova Pro cross-region inference profile `us.amazon.nova-pro-v1:0` is ACTIVE on Pat's account. Kimi K2.5 exists as `moonshotai.kimi-k2.5` (on-demand only, no cross-region inference profile). Nova Lite is `us.amazon.nova-lite-v1:0`. `pytest-evals` 0.3.4 is a real PyPI package with `@pytest.mark.eval` + `eval_bag` + `@pytest.mark.eval_analysis` API. The lattice-evals IsolationContext is a direct port candidate but needs simplification for the code-wiki-agent use case (no OAuth token, no plugin registry, no `claude` config dir — those are only needed by the baseline recorder's subprocess path, not the sweep runner).

**Primary recommendation:** Build the sweep runner and judge panel first (lowest external dependencies), then the baseline recorder (requires `claude` CLI), then the cost-frontier report. Structure the package so sweep and baseline recorder share the `IsolationContext` worktree primitive but are otherwise independent.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Baseline recording | `cores/eval-harness` (subprocess) | External: `claude` CLI + lattice-wiki plugin | Baseline is driven by the eval harness; the actual AI work runs in a subprocess |
| Model sweep execution | `cores/eval-harness` (orchestrator) | `agents/code-wiki-agent` (run_query entry point) | Sweep calls `run_query()` in-process; eval-harness owns the loop |
| Judge scoring | `cores/eval-harness` (judge panel) | AWS Bedrock (via deepeval) | deepeval calls Bedrock directly; eval-harness configures the panel |
| Structural metrics | `cores/eval-harness` (deterministic) | — | Pure Python on `QueryResult`; no Bedrock calls |
| Cost accounting | `cores/eval-harness` (pricing.py) | `cores/subagent-runtime` (trace JSONL source) | Sweep reads trace JSONL for token counts; pricing.py converts to USD |
| Test orchestration | `cores/eval-harness` tests (pytest-evals) | `eval/` directory (cases, baselines, runs) | pytest-evals wraps the eval loop; `eval/` stores artifacts |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `deepeval` | 4.0.0 (latest: 4.0.2) | LLM judge + GEval metric | CLAUDE.md-mandated; AmazonBedrockModel works with GEval |
| `pytest` | >=8.3 | Test runner | CLAUDE.md-mandated |
| `pytest-asyncio` | 1.3.0 | Async test support | CLAUDE.md-mandated; sweep runner is async |
| `pytest-evals` | 0.3.4 | `@pytest.mark.eval` + `eval_bag` + analysis phase | Real PyPI package; provides the eval/analysis two-phase pattern required by EVAL-10 |
| `langchain-aws` | 1.4.6 | `ChatBedrockConverse` for sweep runner | CLAUDE.md-mandated |
| `syrupy` | 5.1.0 | Snapshot testing for baseline outputs | CLAUDE.md-mandated |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-frontmatter` | 1.1.0 | Parse vault page frontmatter in structural checker | Used in EVAL-06 frontmatter validation |
| `code-wiki-agent` (workspace dep) | — | `run_query()` entry point for sweep | Sweep runner imports this directly |

### Version Verification

All versions confirmed via `pip3 index versions` and `pip show` on 2026-05-14:
- `deepeval`: latest is 4.0.2 (CLAUDE.md pins 4.0.0; pin to `>=4.0.0,<5.0` for safety) [VERIFIED: pip registry]
- `pytest-evals`: 0.3.4 is current [VERIFIED: pip registry]

**Installation:**
```bash
uv add --package eval-harness deepeval>=4.0.0 pytest-evals>=0.3.4
uv add --package eval-harness --group dev pytest>=8.3 pytest-asyncio==1.3.0 syrupy==5.1.0
```

---

## Architecture Patterns

### System Architecture Diagram

```
eval/cases/*.json
      |
      v
[sweep_runner.py]  ←─────────────────────────────────────────────┐
      |                                                           |
      | for each model_id in sweep config                        |
      v                                                           |
[IsolationContext]  ──── git worktree copy ──→ [run_query()]      |
      |                  (fixture vault copy)       |             |
      |                                             v             |
      |                                     [QueryResult]         |
      |                                             |             |
      |                                    [structural_check()]   |
      |                                             |             |
      |                                    [judge_panel.score()]  |
      |                                        /          \       |
      |                               [GEval judge_a]  [GEval judge_b]
      |                               [Sonnet via       [Nova Pro via
      |                                Bedrock]          Bedrock]
      |                                     |             |
      |                                  mean_score ──────┘
      |
      v
[SweepResult JSON] → eval/runs/<timestamp>/
      |
      v
[cost_frontier.py]
  reads: trace JSONL (tokens_in/tokens_out) + pricing.py
  outputs: quality × cost table
      |
      v
pytest-evals @eval_analysis
  raises if quality < threshold (EVAL-09)
```

The baseline recorder is a separate entry point:
```
eval/cases/*.json
      |
      v
[baseline_recorder.py]
      |
      | for each case
      v
[IsolationContext]
      |
      v
[run_headless()] ──→ subprocess: claude -p --plugin-dir lattice-wiki
      |                          --append-system-prompt EVAL_SYSTEM_PROMPT_QA
      v
[baseline snapshot] → eval/baselines/<case_id>.json
```

### Recommended Project Structure

```
cores/eval-harness/
├── pyproject.toml
├── src/
│   └── eval_harness/
│       ├── __init__.py
│       ├── isolation.py        # IsolationContext (ported, simplified)
│       ├── runner_headless.py  # RunResult, _build_cmd, run_headless (ported)
│       ├── baseline.py         # BaselineRecorder: record(), load(), compare()
│       ├── sweep.py            # SweepRunner: run_sweep(), SweepResult
│       ├── judge.py            # JudgePanel: score(), two GEval instances
│       ├── structural.py       # Structural metrics: check_citations(), check_frontmatter()
│       ├── pricing.py          # PRICES dict: Bedrock model USD/M token table
│       └── report.py           # cost_frontier_table(), regression_check()
└── tests/
    ├── conftest.py
    ├── test_structural.py       # unit tests (no Bedrock)
    ├── test_pricing.py          # unit tests
    ├── test_isolation.py        # unit tests (tmp dir, no real git worktree)
    └── eval/
        └── test_sweep_eval.py   # @pytest.mark.eval tests (opt-in)

eval/                            # top-level, next to cores/ and agents/
├── cases/
│   └── query_cases.json
├── baselines/
│   └── <case_id>.json           # committed snapshots
└── runs/                        # sweep result JSONs (gitignored or committed)
```

### Pattern 1: AmazonBedrockModel + GEval for Query Scoring

**What:** Two independent GEval instances, each with its own AmazonBedrockModel judge. Scores averaged for position-bias resistance.

**When to use:** Any eval that needs LLM-as-judge with heterogeneous panel.

```python
# Source: Context7 /confident-ai/deepeval + deepeval.com/integrations/models/amazon-bedrock
from deepeval.metrics import GEval
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

judge_a = AmazonBedrockModel(
    model="us.anthropic.claude-sonnet-4-6",  # cross-region inference profile
    region="us-east-1",
    cost_per_input_token=3.0 / 1_000_000,
    cost_per_output_token=15.0 / 1_000_000,
    generation_kwargs={"temperature": 0},
)

judge_b = AmazonBedrockModel(
    model="us.amazon.nova-pro-v1:0",  # cross-region inference profile (VERIFIED ACTIVE)
    region="us-east-1",
    cost_per_input_token=0.80 / 1_000_000,
    cost_per_output_token=3.20 / 1_000_000,
    generation_kwargs={"temperature": 0},
)

def make_geval(name: str, model: AmazonBedrockModel) -> GEval:
    return GEval(
        name=name,
        criteria=(
            "Determine whether the actual output accurately answers the input query "
            "based on the expected answer. The actual output should cite relevant wiki "
            "pages using [[wikilink]] notation and include code path references when present."
        ),
        evaluation_steps=[
            "Check whether the actual output addresses the core of the user query",
            "Check whether at least one [[wikilink]] citation is present",
            "Check whether factual claims align with the expected answer",
            "Penalize responses that have no citations or include hallucinated package names",
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=model,
        threshold=0.5,
    )

def score_with_panel(
    query: str,
    actual: str,
    expected: str,
) -> dict:
    """Score with both judges; return mean score + individual scores."""
    tc = LLMTestCase(input=query, actual_output=actual, expected_output=expected)
    metric_a = make_geval("judge_a_score", judge_a)
    metric_b = make_geval("judge_b_score", judge_b)
    metric_a.measure(tc)
    metric_b.measure(tc)
    return {
        "judge_a": metric_a.score,
        "judge_b": metric_b.score,
        "mean": (metric_a.score + metric_b.score) / 2.0,
        "reason_a": metric_a.reason,
        "reason_b": metric_b.reason,
    }
```

### Pattern 2: Sweep Runner — Direct run_query() Invocation

**What:** The sweep calls `run_query()` directly (not `claude -p`), with a temporary override of the librarian model. This avoids subprocess overhead for the sweep path.

**When to use:** Model sweep for any command that exposes a Python async entry point.

```python
# Source: existing query.py analysis + CONTEXT.md D-specifics section
import asyncio
from pathlib import Path
from code_wiki_agent.commands.query import run_query, QueryResult
from model_adapter.loader import make_llm
from eval_harness.isolation import EvalWorktree

async def run_sweep_case(
    query: str,
    expected_answer: str,
    model_id: str,
    vault_path: Path,
) -> dict:
    """Run one case with one model. Returns sweep record."""
    # EvalWorktree is a simplified IsolationContext: copies vault to tmpdir,
    # does NOT need git worktree (query is read-only; tmpdir prevents index pollution)
    async with EvalWorktree(vault_path) as wt:
        result: QueryResult = await run_query(
            query=query,
            vault_path=wt.path,
            top_k=5,
        )
    return {
        "query": query,
        "model_id": model_id,
        "answer": result.answer,
        "citations": result.citations,
        "pages_drilled": result.pages_drilled,
    }
```

**Note:** The sweep runner needs to inject the model-under-test at `make_llm("librarian")` call time. Options:
1. Monkey-patch `models.toml` in the copied vault path (not clean)
2. Pass a `model_override` parameter to `run_query()` (requires a small modification to `run_query()`)
3. Use an env var to override the librarian model_id before each sweep invocation

Option 2 (add optional `librarian_model_override: str | None = None` to `run_query()`) is the cleanest and avoids environment state. The planner should add this parameter.

### Pattern 3: IsolationContext Simplification for Code-Wiki-Agent

**What:** The lattice-evals `IsolationContext` is built for the `claude -p` subprocess path with full OAuth token, plugin registry, and `CLAUDE_CONFIG_DIR` management. The eval-harness needs a simpler version.

**Lattice-evals `IsolationContext` full behavior:**
- Creates `git worktree add --detach <tmp>/<sha>` of the TARGET REPO (not the eval fixture)
- Builds a `CLAUDE_CONFIG_DIR` with plugin symlinks and `installed_plugins.json`
- Validates `CLAUDE_CODE_OAUTH_TOKEN`
- Optionally removes the wiki directory from the worktree

**What code-wiki-agent's eval actually needs (two cases):**

**Case A: Baseline Recorder (claude -p subprocess)**
- Needs the fixture vault as the working directory
- Does NOT need OAuth or plugin registry (uses `--plugin-dir` flag directly)
- Does NOT need a git worktree of the deep-agents repo itself
- DOES need isolation to prevent concurrent runs writing to the same `.code-wiki/` index
- Simplest approach: `shutil.copytree(fixture_vault, tmp_dir)` — a plain temp-dir copy

**Case B: Sweep Runner (in-process run_query)**
- `run_query()` builds/reads the `.code-wiki/` BM25 + SQLite index inside the vault path
- With fixture vault already having pre-built indexes, a read is safe
- Still want isolation so sweep runs don't write overlapping trace JSONL
- Simplest approach: `shutil.copytree(fixture_vault, tmp_dir)` with pre-built indexes included

**Recommended `EvalWorktree` implementation:**

```python
# Source: lattice-evals isolation.py (ported + simplified)
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

class EvalWorktree:
    """Isolated copy of a vault for one eval run.

    Uses shutil.copytree into a tempdir — not a git worktree.
    Sufficient for read-heavy query eval where git history is irrelevant.
    Cleans up on __aexit__.
    """
    def __init__(self, source_vault: Path) -> None:
        self._source = source_vault
        self.path: Path | None = None
        self._tmp: Path | None = None

    async def __aenter__(self) -> "EvalWorktree":
        self._tmp = Path(tempfile.mkdtemp(prefix="eval-wt-"))
        self.path = self._tmp / "vault"
        shutil.copytree(self._source, self.path, dirs_exist_ok=False)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._tmp and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
```

**Why not git worktree:** The fixture vault is not a git repository (it's inside the deep-agents repo as a tracked directory, not a submodule). `git worktree add` requires the target to be a git repo HEAD. `shutil.copytree` is correct.

### Pattern 4: pytest-evals Integration

**What:** `pytest-evals` 0.3.4 provides `@pytest.mark.eval`, `eval_bag`, and `@pytest.mark.eval_analysis`. Separate from `@pytest.mark.eval` skip gate (the skip gate uses `CODE_WIKI_RUN_EVAL=1`).

```python
# Source: AlmogBaku/pytest-evals README, verified against PyPI 0.3.4
import pytest
from eval_harness.sweep import run_sweep_case

CASES = [...]  # loaded from eval/cases/query_cases.json

@pytest.mark.eval(name="query_sweep")
@pytest.mark.parametrize("case", CASES)
async def test_query_sweep_case(case: dict, eval_bag):
    result = await run_sweep_case(
        query=case["query"],
        expected_answer=case["expected_answer"],
        model_id=case.get("model_id", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        vault_path=FIXTURE_VAULT,
    )
    eval_bag.answer = result["answer"]
    eval_bag.citations = result["citations"]
    eval_bag.score = result.get("composite_score", 0.0)

@pytest.mark.eval_analysis(name="query_sweep")
def test_query_sweep_analysis(eval_results):
    scores = [r.score for r in eval_results]
    mean = sum(scores) / len(scores) if scores else 0.0
    assert mean >= 0.5, f"Mean composite score {mean:.2f} below threshold 0.5"
```

**Run phases:**
```bash
# Eval phase (runs each case)
pytest --run-eval -k "query_sweep"
# Analysis phase (aggregate assertion)
pytest --run-eval-analysis -k "query_sweep"
```

**Existing project mark pattern (from conftest.py):**
```python
# In eval-harness conftest.py — mirrors CODE_WIKI_RUN_INTEGRATION pattern
EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_EVAL"),
    reason="Set CODE_WIKI_RUN_EVAL=1 to run real eval suite",
)
```

### Anti-Patterns to Avoid

- **Calling `claude -p` for the model sweep:** The sweep invokes `run_query()` in-process. `claude -p` is only for the baseline recorder (which measures the lattice-wiki plugin, not code-wiki-agent).
- **Using git worktree for the fixture vault copy:** The fixture vault is a directory inside the repo, not a detached HEAD. Use `shutil.copytree` to a tmpdir.
- **Global `AmazonBedrockModel` instances across tests:** deepeval metrics are not thread-safe if reused across parametrized test cases. Create fresh instances per test call or per sweep run.
- **Hardcoding OpenAI model names in GEval:** deepeval defaults to OpenAI GPT. Always pass `model=` explicitly with `AmazonBedrockModel` or the call silently routes to the Anthropic/OpenAI direct API.
- **Using `assert_test()` in pytest-evals context:** `assert_test()` calls deepeval's test runner which conflicts with pytest-evals' two-phase collection. Use `metric.measure(test_case)` directly, then store `metric.score` in `eval_bag`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM-as-judge scoring | Custom API calls to Bedrock for scoring | `deepeval.GEval` + `AmazonBedrockModel` | GEval handles chain-of-thought scoring, score normalization (0–1), threshold pass/fail, `reason` string |
| Test case parametrization + aggregate assertion | Custom fixture collection | `pytest-evals` `@pytest.mark.eval` + `eval_bag` + `eval_results` | Built-in two-phase separation; JSON/CSV export; xdist-compatible |
| Snapshot assertion | String diffing code | `syrupy` | Already in the stack; `.assert_match_snapshot()` handles whitespace-normalized comparison |
| Subprocess output parsing | Hand-rolled JSON line reader | `runner_headless.py` port (lattice-evals) | Already handles `stream-json` event parsing, budget limits, stdin/stdout management |

**Key insight:** deepeval 4.0 `GEval` with a custom `AmazonBedrockModel` judge is the prescribed heterogeneous panel pattern. No prior art needed — the `model=` parameter accepts any `DeepEvalBaseLLM` subclass.

---

## Verified Bedrock Model IDs

**Verified via `aws bedrock list-foundation-models --region us-east-1` and `aws bedrock list-inference-profiles --region us-east-1` on 2026-05-14:**

| Role | Model ID | Inference Type | Status |
|------|----------|---------------|--------|
| `judge_a` (current) | `us.anthropic.claude-sonnet-4-6` | Cross-region inference profile | ACTIVE |
| `judge_b` (D-07 update) | `us.amazon.nova-pro-v1:0` | Cross-region inference profile | ACTIVE |
| Sweep: baseline | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Cross-region inference profile | (existing in models.toml) |
| Sweep: alt 1 | `us.amazon.nova-lite-v1:0` | Cross-region inference profile | ACTIVE |
| Sweep: alt 2 | `qwen.qwen3-32b-v1:0` | **ON-DEMAND ONLY** — no cross-region inference profile | ACTIVE |

**Critical note on on-demand models (Qwen3):** `qwen.qwen3-32b-v1:0` has no `us.` cross-region inference profile — it only supports on-demand inference. This means:
1. Use model ID `qwen.qwen3-32b-v1:0` (no `us.` prefix) in the sweep config
2. `ChatBedrockConverse` works fine with on-demand model IDs [VERIFIED: pool.py uses `model_id` field directly]
3. `deepeval.AmazonBedrockModel` works fine with on-demand model IDs too

**Nova Lite:** `us.amazon.nova-lite-v1:0` (cross-region inference profile, ACTIVE)

---

## Pricing Table (for pricing.py extension)

**Verified via AWS Bedrock pricing page (https://aws.amazon.com/bedrock/pricing/) on 2026-05-14:**

```python
# USD per 1M tokens — extend lattice-evals pricing.py pattern
PRICES: dict[str, dict[str, float]] = {
    # Claude models (from lattice-evals pricing.py — already verified)
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    # Bedrock on-demand prices verified 2026-05-14
    "us.amazon.nova-pro-v1:0":   {"input": 0.80, "output": 3.20},
    "us.amazon.nova-lite-v1:0":  {"input": 0.30, "output": 1.20},
    "qwen.qwen3-32b-v1:0":       {"input": 0.40, "output": 1.60},  # Qwen3 32B on-demand
}
```

Bedrock models do not have prompt-caching surcharges (no `cache_read`/`cache_write` pricing for Nova/Qwen). Claude cross-region inference pricing on Bedrock matches direct Bedrock on-demand prices.

---

## How run_query() Works (Sweep Integration Points)

**Signature:**
```python
async def run_query(
    query: str,
    vault_path: Path | None = None,
    top_k: int = 5,
) -> QueryResult
```

**Returns:**
```python
@dataclass
class QueryResult:
    answer: str            # synthesized answer, may contain [[wikilink]] tokens
    citations: list[str]   # wikilink targets extracted from answer
    pages_drilled: int     # successful librarian fan-out count
    search_scores: dict    # {page_path: {"bm25": float, "embed": float, "rrf": float}}
```

**What the sweep needs to override:** `run_query()` internally calls `make_llm("librarian")` which reads `models.toml`. The sweep needs to inject a different model per sweep iteration. **Recommended approach: add `librarian_model_override: str | None = None` parameter to `run_query()`.** The planner must include a task to add this parameter in the code-wiki-agent package before the sweep can use it.

**Side effects the sweep must account for:**
1. `run_query()` auto-builds the index if missing — the fixture vault already has pre-built BM25 + SQLite indexes in `.code-wiki/`, so no first-time build in sweep (confirmed: `bm25/` and `search.db` present in fixture vault)
2. `run_query()` writes trace JSONL to `vault/.code-wiki/traces/` — per-run isolation via `EvalWorktree` prevents inter-run trace file conflicts
3. `run_query()` calls `resolve_wiki_and_repo()` — when `vault_path` is explicitly provided, this should short-circuit the env-var lookup (need to verify this in `vault_io._workspace`)

**Token counts from traces:** The trace JSONL written by `SubagentPool` has `"tokens_in"` and `"tokens_out"` fields (currently `null` — Phase 4 is meant to add cost accounting per the `# Phase 4 adds cost accounting` comment in `pool.py`). The sweep runner should:
1. Add cost accounting to `pool.py` as a Phase 4 task (the comment explicitly flags this)
2. Alternatively, capture token counts from `langchain_core` `usage_metadata` directly in the sweep runner

---

## pytest-evals vs. deepeval `assert_test` Integration Strategy

**`pytest-evals` (EVAL-10):**
- Real PyPI package, 0.3.4 [VERIFIED: pip registry]
- Provides two-phase eval/analysis separation
- `@pytest.mark.eval(name=...)` marks individual cases
- `eval_bag` fixture stores per-case metrics (arbitrary fields)
- `@pytest.mark.eval_analysis(name=...)` runs after all cases; receives `eval_results`
- CLI flags: `--run-eval`, `--run-eval-analysis`
- xdist-compatible (parallel case execution)

**deepeval `assert_test` / `evaluate()` (alternative):**
- Runs scoring inline per test
- Does NOT separate collection from aggregate assertion
- Works in standard pytest without `--run-eval`

**Recommendation:** Use **both** in complementary roles:
- `pytest-evals` for the sweep: case execution (store raw answer + score in eval_bag) → analysis (assert mean score >= threshold)
- `deepeval.metric.measure()` inside each case (NOT `assert_test`) to get the score
- `@pytest.mark.eval` skip gate + `CODE_WIKI_RUN_EVAL=1` env var mirrors `CODE_WIKI_RUN_INTEGRATION=1` pattern

---

## IsolationContext Port Analysis

**What to port (verbatim or near-verbatim):**
- `RunResult` dataclass from `runner_headless.py`
- `_build_cmd()` function (exact flags: `--output-format stream-json --verbose --add-dir --append-system-prompt --plugin-dir`)
- `run_headless()` function (event loop, budget checks, stdin management)
- `EVAL_SYSTEM_PROMPT_QA` constant (exact text — tested to work for Q&A tasks)
- `pricing.py` cost-per-million pattern (extend for Bedrock models above)

**What NOT to port (lattice-wiki-specific, drop):**
- `_validate_credentials()` / OAuth token check — baseline recorder uses `--plugin-dir`, not Claude Code's OAuth
- `_add_worktree()` — replace with `shutil.copytree` (fixture is not a git repo HEAD)
- `_remove_wiki()` / wiki directory removal — code-wiki-agent uses `.code-wiki/` state dir, not a top-level `llm-wiki/` folder
- `_build_cfg_dir()` / `_write_plugin_registry()` — CLAUDE_CONFIG_DIR management not needed (headless runner uses `--plugin-dir` flag)
- `_plugin_shas()`, `Config.includes_wiki`, `scenario.baseline_sha` — lattice-evals concepts with no equivalent

**What to add (code-wiki-agent-specific):**
- `.code-wiki/` state dir handling: the copied vault includes the pre-built BM25 and SQLite index (good — no rebuild needed), plus a `traces/` subdirectory that will receive new JSONL during sweep. The sweep runner should be able to read the copied trace files to extract token counts.

---

## Common Pitfalls

### Pitfall 1: deepeval Defaults to OpenAI
**What goes wrong:** `GEval()` without explicit `model=` parameter calls OpenAI GPT-4. This silently routes outside Bedrock and incurs OpenAI API costs.
**Why it happens:** deepeval's default judge is `gpt-4o` or `gpt-4-turbo` depending on version.
**How to avoid:** Always pass `model=AmazonBedrockModel(...)` explicitly to every `GEval` instance.
**Warning signs:** `openai.AuthenticationError` or unexpected OpenAI charges.

### Pitfall 2: Kimi K2.5 Has No Cross-Region Inference Profile
**What goes wrong:** Constructing `ChatBedrockConverse(model_id="us.moonshotai.kimi-k2.5")` fails with a model-not-found error.
**Why it happens:** `moonshotai.kimi-k2.5` is on-demand only; there is no `us.` prefixed profile.
**How to avoid:** Use `"moonshotai.kimi-k2.5"` directly as the model_id (no `us.` prefix).
**Warning signs:** `ValidationException: The provided model identifier is invalid`.

### Pitfall 3: fixture vault .code-wiki/ Index is Already Built
**What goes wrong:** Planning to build the index in Wave 0 when it already exists.
**Why it happens:** The fixture vault at `cores/vault-io/tests/fixtures/round-trip-vault/` already has `.code-wiki/bm25/` and `.code-wiki/search.db` committed (confirmed via ls).
**How to avoid:** The sweep runner's `EvalWorktree` copies the vault including the `.code-wiki/` dir — no rebuild needed. DO include `.code-wiki/` in the `shutil.copytree` (it is the working index).
**Warning signs:** Slow first-run or unexpected Bedrock embedding calls in unit tests.

### Pitfall 4: run_query() Uses Global models.toml for Librarian Role
**What goes wrong:** Sweep iterations all use the same librarian model because `make_llm("librarian")` reads the global `models.toml`.
**Why it happens:** `run_query()` has no model override parameter.
**How to avoid:** Add `librarian_model_override: str | None = None` to `run_query()` signature. The planner must include this as a code-wiki-agent task.
**Warning signs:** All sweep results have identical model_id in trace JSONL.

### Pitfall 5: Position Bias Test Requires Two Separate Scores
**What goes wrong:** Position bias check is done by comparing the judge score when the answer is in position A vs position B. With `GEval`, the `evaluation_params` includes `ACTUAL_OUTPUT` and `EXPECTED_OUTPUT` — swapping means running two separate `metric.measure()` calls with positions swapped.
**Why it happens:** GEval doesn't have a built-in position-swap mode.
**How to avoid:** The bias check function runs `score_with_panel(query, answer_a, answer_b)` then `score_with_panel(query, answer_b, answer_a)` and asserts `abs(score1 - score2) < 0.05`.
**Warning signs:** Consistently higher scores for whichever answer appears first.

### Pitfall 6: `resolve_wiki_and_repo()` with Explicit vault_path
**What goes wrong:** When the sweep passes an explicit `vault_path` to `run_query()`, `resolve_wiki_and_repo(vault_path)` may still look for a parent git repo.
**Why it happens:** The function signature is `resolve_wiki_and_repo(vault_path)` which returns `(wiki, repo)`. When `vault_path` points to the tmpdir copy, there is no parent git repo — `repo` may be `None` or raise.
**How to avoid:** Verify `resolve_wiki_and_repo()` behavior when called with a non-git-repo path before using it in sweep (add a unit test). If it raises, the sweep should call `run_query()` with a pre-resolved `vault_path` and patch out the `resolve_wiki_and_repo` call, or add a `skip_repo_resolve=True` flag.
**Warning signs:** `subprocess.CalledProcessError: git rev-parse --show-toplevel` in sweep tests.

---

## Code Examples

### Full Judge Panel Invocation

```python
# Source: Context7 /confident-ai/deepeval + deepeval.com/integrations/models/amazon-bedrock
from deepeval.metrics import GEval
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

def make_judge(model_id: str, input_price: float, output_price: float) -> AmazonBedrockModel:
    return AmazonBedrockModel(
        model=model_id,
        region="us-east-1",
        cost_per_input_token=input_price / 1_000_000,
        cost_per_output_token=output_price / 1_000_000,
        generation_kwargs={"temperature": 0},
    )

JUDGE_PANEL = [
    make_judge("us.anthropic.claude-sonnet-4-6", 3.0, 15.0),    # judge_a
    make_judge("us.amazon.nova-pro-v1:0", 0.80, 3.20),           # judge_b
]

EVAL_STEPS = [
    "Check whether the response directly addresses the query",
    "Check whether at least one [[wikilink]] citation is present and plausible",
    "Check whether the response avoids hallucinating package or file names",
    "Penalize responses with no citations or vague answers with no specifics",
]

def panel_score(query: str, actual: str, expected: str) -> dict:
    tc = LLMTestCase(input=query, actual_output=actual, expected_output=expected)
    results = []
    for judge in JUDGE_PANEL:
        metric = GEval(
            name="wiki_query_quality",
            criteria="Assess quality of a wiki query answer.",
            evaluation_steps=EVAL_STEPS,
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=judge,
        )
        metric.measure(tc)
        results.append({"score": metric.score, "reason": metric.reason})
    scores = [r["score"] for r in results]
    return {"mean": sum(scores) / len(scores), "individual": results}
```

### Structural Metrics (EVAL-06)

```python
# Pure Python, no Bedrock calls — runs on every sweep result
from pathlib import Path
from code_wiki_agent.commands.query import QueryResult, _extract_wikilinks
import frontmatter

def check_structural(result: QueryResult, vault_path: Path) -> dict:
    """EVAL-06: wikilinks resolve, citations present, frontmatter valid on sampled pages."""
    checks = {}

    # Check 1: at least one citation present
    checks["has_citation"] = len(result.citations) > 0

    # Check 2: all [[wikilink]] citations resolve to existing vault pages
    unresolved = []
    for link in result.citations:
        link_path = link if link.endswith(".md") else f"{link}.md"
        if not (vault_path / link_path).exists():
            # try glob fallback
            base = link.removesuffix(".md")
            if not list(vault_path.glob(f"**/{base}.md")):
                unresolved.append(link)
    checks["citations_resolve"] = len(unresolved) == 0
    checks["unresolved_citations"] = unresolved

    # Check 3: pages_drilled > 0
    checks["pages_drilled_positive"] = result.pages_drilled > 0

    return checks
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@pytest.mark.integration` only | `@pytest.mark.eval` + `pytest-evals` two-phase | pytest-evals 0.3.4 (AlmogBaku) | Eval aggregate assertions separate from per-case assertions |
| Single-model LLM judge | Heterogeneous panel (two independent judges) | deepeval AmazonBedrockModel allows per-judge model | Position-bias resistance; avoids Claude self-preferencing |
| deepeval OpenAI default | `AmazonBedrockModel` with explicit `model=` | deepeval 3.x+ | Bedrock-only stack compatible |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `resolve_wiki_and_repo(vault_path)` when `vault_path` is an explicit non-git tmpdir will not raise | Pattern 2 + Pitfall 6 | Sweep runner would need to patch or bypass the function; adds code to query.py |
| A2 | deepeval 4.0.2 `AmazonBedrockModel` `cost_per_input_token` param is per-token (not per-1K or per-1M) | Pricing section | Cost tracking would be off by 1000x or 1000000x; verify by checking deepeval source |
| A3 | Qwen3 32B supports text generation via Bedrock Converse API (needed by deepeval judge's text prompt) | Bedrock model IDs section | Qwen3 cannot be used as sweep candidate; use Nova Micro instead |
| A4 | Nova Lite pricing is $0.30/$1.20 per 1M tokens (input/output) | Pricing section | Cost-frontier report numbers wrong; re-verify before committing pricing.py |
| A5 | `shutil.copytree` of fixture vault preserves `.code-wiki/bm25/` numpy binary files intact | IsolationContext section | Index corruption in sweep; rebuild would be needed (slow) |

**Highest risk:** A1 (`resolve_wiki_and_repo` behavior with tmpdir) — should be validated with a unit test before the sweep runner builds on it. A3 (Qwen3 text generation support) is lower risk since deepeval sends plain text prompts, not tool calls.

**On A2:** Per deepeval docs, `cost_per_input_token` is **per token** (e.g., $3.00 per 1M tokens = `0.000003` per token). The examples above already use `price / 1_000_000` which is correct.

---

## Open Questions (RESOLVED)

1. **Does `resolve_wiki_and_repo(vault_path)` raise when vault_path is a tmpdir with no parent git repo?**
   - What we know: It calls `resolve_wiki_and_repo(vault_path)` and returns `(wiki, repo)` where `repo` may be `None`.
   - What's unclear: Whether the function tries `subprocess git rev-parse` on the tmpdir.
   - Recommendation: Add a unit test in Wave 0 with a tmpdir path. If it raises, add `vault_path` bypass to `run_query()`.
   - **RESOLVED:** Plans address this as Warning W2 — 04-01 Task 2 (which adds `librarian_model_override` to `run_query()`) also adds a `skip_repo_resolve: bool = False` guard check. A unit test in `test_sweep.py` verifies `run_query()` succeeds with a tmpdir `vault_path`. Fallback: if `resolve_wiki_and_repo` raises, the test documents accepted risk and the sweep runner passes `vault_path` as absolute path to bypass git detection. (Addressed in planner revision pass.)

2. **Does `token_in`/`token_out` in trace JSONL get populated by Phase 3 code?**
   - What we know: `pool.py` writes `"tokens_in": null, "tokens_out": null` with comment `# Phase 4 adds cost accounting`.
   - What's unclear: Whether Phase 3 execution actually populated these fields.
   - Recommendation: Check one trace file in the fixture vault `traces/` dir. The sampled trace showed `"tokens_in": null` — cost accounting work remains for Phase 4.
   - **RESOLVED:** Confirmed null — Phase 3 did NOT populate these fields. The `# Phase 4 adds cost accounting` comment in `pool.py` confirms this is intentionally deferred. Plan 04-01 Task 2 fixes this by injecting `cost_for_usage()` via lazy import in `_write_trace()`.

3. **Does the third sweep candidate support text generation via Bedrock Converse API?**
   - **RESOLVED (model swapped):** Kimi K2.5 replaced with `qwen.qwen3-32b-v1:0` (Qwen3 32B dense, on-demand, ACTIVE on Pat's account). deepeval's `AmazonBedrockModel.generate()` sends plain text prompts — tool_use support is not required. Fallback: `us.amazon.nova-micro-v1:0` if Qwen3 fails. Risk: LOW.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| AWS Bedrock (us-east-1) | Model sweep, judge panel | ✓ | Active | — |
| `us.amazon.nova-pro-v1:0` | judge_b | ✓ | ACTIVE | `us.meta.llama3-3-70b-instruct-v1:0` |
| `us.amazon.nova-lite-v1:0` | Sweep candidate | ✓ | ACTIVE | `us.amazon.nova-micro-v1:0` |
| `qwen.qwen3-32b-v1:0` | Sweep candidate | ✓ (on-demand only) | ACTIVE | `us.amazon.nova-micro-v1:0` |
| `claude` CLI | Baseline recorder subprocess | Unknown | — | Skip baseline recorder in CI |
| `lattice-wiki` plugin | Baseline recorder | Unknown | — | Baseline recording is a manual one-time step |
| `deepeval` | Judge panel | Not installed yet | 4.0.2 available | — |
| `pytest-evals` | EVAL-10 integration | Not installed yet | 0.3.4 available | — |

**Missing dependencies with no fallback:**
- `claude` CLI and `lattice-wiki` plugin are required only for the baseline recorder, which is described as a "one-time manual step" in CONTEXT.md. The sweep runner and judge panel have no dependency on these.

**Missing dependencies with fallback:**
- If Kimi K2.5 doesn't support Bedrock Converse tool_use for deepeval: `us.meta.llama3-3-70b-instruct-v1:0` (ACTIVE, cross-region) is a viable judge_b and sweep candidate alternative.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8.3 + pytest-asyncio 1.3.0 + pytest-evals 0.3.4 |
| Config file | `cores/eval-harness/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run --package eval-harness pytest cores/eval-harness/tests/ -m "not eval"` |
| Full suite command | `CODE_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest --run-eval --run-eval-analysis` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVAL-01 | Package importable as workspace member | unit | `uv run --package eval-harness python -c "import eval_harness"` | ❌ Wave 0 |
| EVAL-02 | Fixture vault has queryable content | unit | `pytest cores/eval-harness/tests/test_structural.py::test_fixture_vault_has_pages` | ❌ Wave 0 |
| EVAL-03 | `_build_cmd()` produces correct `claude -p` flags | unit | `pytest cores/eval-harness/tests/test_baseline.py::test_build_cmd` | ❌ Wave 0 |
| EVAL-04 | Sweep iterates N models, collects N results | unit (mock run_query) | `pytest cores/eval-harness/tests/test_sweep.py::test_sweep_collects_results` | ❌ Wave 0 |
| EVAL-05 | `panel_score()` returns mean of two judge scores | integration (Bedrock) | `CODE_WIKI_RUN_EVAL=1 pytest --run-eval -k judge_panel` | ❌ Wave 0 |
| EVAL-06 | `check_structural()` passes on known-good QueryResult | unit | `pytest cores/eval-harness/tests/test_structural.py::test_known_good` | ❌ Wave 0 |
| EVAL-07 | `cost_frontier_table()` produces correct USD values | unit | `pytest cores/eval-harness/tests/test_pricing.py` | ❌ Wave 0 |
| EVAL-08 | Baseline JSON includes model_id, prompt_hash, timestamp | unit | `pytest cores/eval-harness/tests/test_baseline.py::test_baseline_schema` | ❌ Wave 0 |
| EVAL-09 | Regression check raises on score below threshold | unit | `pytest cores/eval-harness/tests/test_report.py::test_regression_check_fails` | ❌ Wave 0 |
| EVAL-10 | `@pytest.mark.eval` cases skip without `CODE_WIKI_RUN_EVAL=1` | unit | `pytest cores/eval-harness/tests/ -v --co \| grep eval` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run --package eval-harness pytest cores/eval-harness/tests/ -m "not eval" -x`
- **Per wave merge:** Full unit suite clean; manually run eval suite with `CODE_WIKI_RUN_EVAL=1`
- **Phase gate:** All unit tests green; at least one full sweep run (3 models × 3 cases) completes before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `cores/eval-harness/src/eval_harness/__init__.py` — package init
- [ ] `cores/eval-harness/pyproject.toml` — package declaration with workspace deps
- [ ] `cores/eval-harness/tests/conftest.py` — `EVAL_GATE`, `fixture_vault_path` fixture
- [ ] `cores/eval-harness/tests/test_structural.py` — REQ EVAL-02, EVAL-06
- [ ] `cores/eval-harness/tests/test_pricing.py` — REQ EVAL-07
- [ ] `cores/eval-harness/tests/test_baseline.py` — REQ EVAL-03, EVAL-08
- [ ] `cores/eval-harness/tests/test_sweep.py` — REQ EVAL-04
- [ ] `cores/eval-harness/tests/test_report.py` — REQ EVAL-09
- [ ] `eval/cases/query_cases.json` — REQ EVAL-02 (3-5 cases from fixture vault)
- [ ] `deepeval>=4.0.0`, `pytest-evals>=0.3.4` deps added to eval-harness pyproject.toml

---

## Security Domain

> `security_enforcement` is absent from config.json — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in eval harness |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Local tool, no multi-user |
| V5 Input Validation | Yes | `eval/cases/*.json` schema validation before sweep; Pydantic or dataclass validation |
| V6 Cryptography | No | No cryptographic operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed eval/cases JSON injected as query string | Tampering | Load with `json.load()` + validate schema fields (query: str, expected_answer: str); reject unknown fields |
| Trace JSONL file path traversal from model_id string | Tampering | Sanitize model_id before using as filename component: `re.sub(r"[^a-zA-Z0-9._:-]", "_", model_id)` |
| Subprocess injection via prompt in baseline recorder | Tampering | Use `cmd` list form (already in `_build_cmd()`) — never shell=True; prompt is final positional arg, not interpolated into command string |

---

## Sources

### Primary (HIGH confidence)

- Context7 `/confident-ai/deepeval` — AmazonBedrockModel constructor API, GEval metric API with custom model, `evaluation_params`, `assert_test` pattern
- `aws bedrock list-foundation-models --region us-east-1` [VERIFIED: 2026-05-14] — All model IDs and availability
- `aws bedrock list-inference-profiles --region us-east-1` [VERIFIED: 2026-05-14] — Cross-region inference profile availability for Nova Pro, Nova Lite
- `pip3 index versions pytest-evals` [VERIFIED: 2026-05-14] — Package existence, version 0.3.4
- AWS Bedrock pricing page https://aws.amazon.com/bedrock/pricing/ [VERIFIED: WebFetch 2026-05-14] — Nova Pro, Nova Lite, Kimi K2.5 pricing
- `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/` [VERIFIED: read] — Complete source for IsolationContext, runner_headless, orchestrator, pricing

### Secondary (MEDIUM confidence)

- AlmogBaku/pytest-evals README via WebFetch [VERIFIED via PyPI + GitHub README] — `@pytest.mark.eval`, `eval_bag`, `@pytest.mark.eval_analysis`, CLI flags
- deepeval.com/integrations/models/amazon-bedrock via WebFetch — `AmazonBedrockModel` parameter list (7 params including `cost_per_input_token`)
- deepeval.com/docs/metrics-llm-evals via WebFetch — `GEval` `evaluation_steps` and `model=` override pattern

### Tertiary (LOW confidence, flagged in Assumptions Log)

- Kimi K2.5 tool calling support via Bedrock Converse API — not explicitly documented; assumed from model capabilities [A3 in Assumptions Log]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all package versions verified via pip registry and Context7
- Architecture: HIGH — based on verified code reads of query.py, pool.py, lattice-evals source
- Bedrock model IDs: HIGH — verified via AWS CLI on Pat's account
- Pricing: HIGH — verified via AWS pricing page
- Pitfalls: HIGH (most) / MEDIUM (Pitfall 6 on resolve_wiki_and_repo behavior)

**Research date:** 2026-05-14
**Valid until:** 2026-06-14 (model pricing may change; deepeval minor version updates are expected)
