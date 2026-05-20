# Phase 7: Cost-Frontier Sweep - Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 13 new/modified files
**Analogs found:** 12 / 13

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `cores/eval-harness/src/eval_harness/sweep.py` (extend) | service | batch | self (run_sweep) | exact — extend in place |
| `cores/eval-harness/src/eval_harness/report.py` (extend) | utility | transform | self (cost_frontier_table) | exact — extend in place |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (extend) | service | request-response | self (run_query) | exact — extend in place |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` (extend) | service | request-response | `commands/query.py` | role-match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` (extend) | service | request-response | `commands/query.py` | role-match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` (extend) | service | request-response | `commands/query.py` | role-match |
| `cores/model-adapter/src/model_adapter/models.toml` (extend) | config | — | self | exact |
| `eval/cases/query_cases.json` (extend) | config/fixture | — | self | exact |
| `cores/eval-harness/tests/test_role_sweep.py` (new) | test | — | `tests/test_sweep.py` | exact |
| `cores/eval-harness/tests/test_two_gate_scorer.py` (new) | test | — | `tests/test_divergence_metric.py` | role-match |
| `cores/eval-harness/tests/test_report_role_doc.py` (new) | test | — | `tests/test_report.py` | exact |
| `cores/eval-harness/tests/test_preflight_estimator.py` (new) | test | — | `tests/test_pricing.py` | role-match |
| `cores/eval-harness/tests/eval/test_sweep_dry_run.py` (new) | test | batch | `tests/eval/test_sweep_eval.py` | role-match |
| `.planning/sweep/` docs (new, hand-authored) | docs | — | none | no analog |

---

## Pattern Assignments

### `cores/eval-harness/src/eval_harness/sweep.py` (extend — add `run_role_sweep`)

**Analog:** self — extend existing `run_sweep()`.

**Imports pattern** (lines 14–30):
```python
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from graph_wiki_agent.commands.query import QueryResult, run_query

from eval_harness.isolation import EvalWorktree
from eval_harness.pricing import UnknownModelError, cost_for_usage
from eval_harness.structural import check_structural
```

**New imports to add for `run_role_sweep`:**
```python
from graph_wiki_agent.commands.scan import run_scan
from graph_wiki_agent.commands.lint import run_lint
from graph_wiki_agent.commands.ingest import run_ingest_source
from model_adapter.loader import load_role_config
```

**Existing `run_sweep` core pattern** (lines 155–267) — single `_run_one` inner async function wrapped with `asyncio.gather(return_exceptions=True)`. The new `run_role_sweep` follows the same shape:

```python
async def run_role_sweep(
    role: str,
    candidate_model_id: str,
    cases_path: Path,
    vault_path: Path,
    repeats: int = 3,
    semaphore: asyncio.Semaphore | None = None,
) -> list[SweepResult]:
    """Single-role-swap sweep: role-under-test uses candidate_model_id;
    all other roles stay at their models.toml defaults."""
    ...
    sem = semaphore or asyncio.Semaphore(8)  # Pitfall 4: rate-limit guard
    cases = _load_and_validate_cases(cases_path)
    # Build (case, repeat_idx) pairs
    coros = [
        _run_role_one(role, candidate_model_id, case, vault_path, sem)
        for case in cases
        for _ in range(repeats)
    ]
    raw = await asyncio.gather(*coros, return_exceptions=True)
    ...
```

**Role dispatch map pattern** (new constant — place above `run_role_sweep`):
```python
# Maps role name -> which command function to call in a sweep cell
ROLE_COMMAND_MAP = {
    "librarian":   "_sweep_query_role",   # run_query(role_model_overrides={"librarian": candidate})
    "synthesizer": "_sweep_query_role",   # run_query(role_model_overrides={"synthesizer": candidate})
    "code_reader": "_sweep_query_role",   # run_query(role_model_overrides={"code_reader": candidate})
    "scanner":     "_sweep_scan_role",    # run_scan(model_override=candidate)
    "linter":      "_sweep_lint_role",    # run_lint(model_override=candidate)
    "ingestor":    "_sweep_ingest_role",  # run_ingest_source(source_path, model_override=candidate)
}
```

**Partial-failure isolation pattern** (lines 253–267 of existing sweep.py — copy verbatim):
```python
raw = await asyncio.gather(*coros, return_exceptions=True)

results: list[SweepResult] = []
for item in raw:
    if isinstance(item, SweepResult):
        results.append(item)
    elif isinstance(item, BaseException):
        logger.error("Unexpected gather exception: %s", item)

return results
```

**`sweep_candidates` TOML read pattern** (new, reads from same `load_role_config` the production code uses):
```python
from model_adapter.loader import load_role_config

role_cfg = load_role_config(role)
candidates = role_cfg.get("sweep_candidates", [])
```

**Pre-flight estimator pattern** (new `estimate_sweep_cost()` function):
```python
# Conservative per-tier token constants (from RESEARCH.md §Tension 6)
_TIER_TOKENS: dict[str, tuple[int, int]] = {
    "cheap-fast": (3_000, 500),    # scanner, code_reader
    "mid":        (5_000, 1_000),  # linter, ingestor
    "quality":    (8_000, 2_000),  # librarian, synthesizer
}

_ROLE_TIER: dict[str, str] = {
    "scanner": "cheap-fast", "code_reader": "cheap-fast",
    "linter": "mid",         "ingestor": "mid",
    "librarian": "quality",  "synthesizer": "quality",
}

def estimate_sweep_cost(
    role_candidates: dict[str, list[str]],  # {role: [model_id, ...]}
    n_cases: int,
    repeats: int,
) -> float:
    """Pre-flight cost estimate using conservative per-tier token constants.
    No Bedrock calls. Reads PRICES from pricing.cost_for_usage."""
    total = 0.0
    for role, candidates in role_candidates.items():
        tier = _ROLE_TIER[role]
        tokens_in, tokens_out = _TIER_TOKENS[tier]
        for model_id in candidates:
            try:
                cell_cost = cost_for_usage(
                    model_id, {"input": tokens_in * n_cases * repeats,
                               "output": tokens_out * n_cases * repeats}
                )
                total += cell_cost
            except UnknownModelError:
                pass  # unknown model — skip from estimate
    return total
```

**BED-01 pre-flight pattern** (new — in sweep runner pre-flight block, before matrix):
```python
from model_adapter.loader import make_llm

try:
    make_llm("haiku").invoke("ping")
    print("[BED-01] Bedrock connectivity confirmed.")
except Exception as e:
    raise SystemExit(f"BED-01 FAILED — check AWS credentials/region: {e}")
```

**`_sanitize_model_id` reuse** (line 73–82 of sweep.py — apply to all new per-role filenames):
```python
def _sanitize_model_id(model_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", model_id)
```

---

### `cores/eval-harness/src/eval_harness/report.py` (extend — add `render_role_doc`, `pareto_frontier`)

**Analog:** self — extend existing `cost_frontier_table()` and `print_frontier()`.

**Existing quality-score extraction pattern** (lines 41–46 of report.py — reuse in `render_role_doc`):
```python
if result.judge_scores is not None:
    quality_score = float(result.judge_scores["mean"])
else:
    # Structural fallback: has_citation indicator
    quality_score = 1.0 if result.structural.get("has_citation") else 0.0
```

**New `pareto_frontier()` pattern** (add to report.py — trivial non-dominated-set filter):
```python
def pareto_frontier(table: dict[str, dict]) -> dict[str, dict]:
    """Return the non-dominated subset of table by (quality_score, cost_usd).

    A point is dominated if another point has >= quality AND <= cost.
    cost_usd=None entries are never dominated (cost unknown).
    """
    rows = list(table.items())
    dominated = set()
    for i, (mid_i, row_i) in enumerate(rows):
        for j, (mid_j, row_j) in enumerate(rows):
            if i == j:
                continue
            q_i, c_i = row_i["quality_score"], row_i["cost_usd"]
            q_j, c_j = row_j["quality_score"], row_j["cost_usd"]
            if c_i is None or c_j is None:
                continue
            if q_j >= q_i and c_j <= c_i and (q_j > q_i or c_j < c_i):
                dominated.add(mid_i)
    return {k: v for k, v in table.items() if k not in dominated}
```

**New `render_role_doc()` signature** (add to report.py):
```python
def render_role_doc(
    role: str,
    tier: str,
    candidates: list[str],
    sweep_results: list[SweepResult],
    divergence_results: dict | None,   # None for synthesizer/code_reader
    run_date: str,
    commit_sha: str,
    total_cost_usd: float,
) -> str:
    """Render per-role markdown doc per D-12 skeleton.

    Sections: role + tier + candidates, raw scores table, Pareto frontier
    callout, recommendation comment block text, run metadata.
    """
```

**Recommendation comment block emission** (the text to paste into models.toml per D-11):
```python
def render_recommendation_block(
    role: str,
    run_date: str,
    frontier: dict[str, dict],
    current_default: str,
) -> str:
    """Emit the TOML comment block for manual paste into models.toml."""
    lines = [f"# Sweep candidates (run {run_date}): pareto-frontier members"]
    for model_id, row in frontier.items():
        q = row["quality_score"]
        c = row["cost_usd"]
        cost_str = f"${c:.4f}" if c is not None else "N/A"
        lines.append(f"#   - {model_id:<50} (cost={cost_str}, quality={q:.2f})")
    lines.append(f"# Previous default: {current_default}")
    return "\n".join(lines)
```

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (extend)

**Analog:** self — add `role_model_overrides` parameter to existing `run_query()`.

**Existing signature** (line 752–757 of query.py):
```python
async def run_query(
    query: str,
    vault_path: Path | None = None,
    top_k: int = 5,
    librarian_model_override: str | None = None,
) -> QueryResult:
```

**New signature** (keep `librarian_model_override` for backward compat):
```python
async def run_query(
    query: str,
    vault_path: Path | None = None,
    top_k: int = 5,
    librarian_model_override: str | None = None,  # deprecated; prefer role_model_overrides
    role_model_overrides: dict[str, str] | None = None,
) -> QueryResult:
```

**Existing librarian override pattern** (lines 824–832 of query.py — copy this shape for other roles):
```python
lib_cfg = load_role_config("librarian")
if librarian_model_override is not None:
    librarian_llm = ChatBedrockConverse(
        model_id=librarian_model_override,
        region_name=lib_cfg["region"],
        max_tokens=lib_cfg["max_tokens"],
    )
else:
    librarian_llm = make_llm("librarian")
```

**New synthesizer override pattern** (replace line 879 `make_llm("synthesizer")`):
```python
synth_override = (role_model_overrides or {}).get("synthesizer")
if synth_override is not None:
    synth_cfg = load_role_config("synthesizer")
    synth_llm = ChatBedrockConverse(
        model_id=synth_override,
        region_name=synth_cfg["region"],
        max_tokens=synth_cfg["max_tokens"],
    )
else:
    synth_llm = make_llm("synthesizer")
```

**`_run_code_fallback` override threading** (replace lines 373–374 in `_run_code_fallback`):
```python
# _run_code_fallback needs to accept code_reader_override parameter
code_cfg = load_role_config("code_reader")
if code_reader_override is not None:
    code_llm_raw = ChatBedrockConverse(
        model_id=code_reader_override,
        region_name=code_cfg["region"],
        max_tokens=code_cfg["max_tokens"],
    )
else:
    code_llm_raw = make_llm("code_reader")
```

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` (extend)

**Analog:** `commands/query.py` (librarian override pattern).

**Existing `run_scan` signature** (line 221–226 of scan.py):
```python
async def run_scan(
    vault_path: Path | None = None,
    no_file_map: bool = False,
    max_depth: int = 3,
    repo_path: Path | None = None,
) -> ScanResult:
```

**New parameter to add:**
```python
async def run_scan(
    vault_path: Path | None = None,
    no_file_map: bool = False,
    max_depth: int = 3,
    repo_path: Path | None = None,
    model_override: str | None = None,   # sweep only — replaces make_llm("scanner")
) -> ScanResult:
```

**Existing make_llm call to patch** (line 325 of scan.py):
```python
# current:
scanner_llm = make_llm("scanner")

# new — copy from query.py librarian override pattern:
cfg = load_role_config("scanner")
if model_override is not None:
    scanner_llm = ChatBedrockConverse(
        model_id=model_override,
        region_name=cfg["region"],
        max_tokens=cfg["max_tokens"],
    )
else:
    scanner_llm = make_llm("scanner")
```

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` (extend)

**Analog:** `commands/query.py` (librarian override pattern).

**Existing `run_lint` signature** (line 469–473 of lint.py):
```python
async def run_lint(
    vault_path: Path | None = None,
    stale_days: int = 90,
    log_gap_days: int = 14,
) -> LintResult:
```

**New parameter:**
```python
async def run_lint(
    vault_path: Path | None = None,
    stale_days: int = 90,
    log_gap_days: int = 14,
    model_override: str | None = None,   # sweep only
) -> LintResult:
```

**Existing make_llm call in `run_linter_group`** (line 430 of lint.py — the closure captures `model_override` from the enclosing `run_lint` scope):
```python
# current (inside run_linter_group closure):
linter_llm = make_llm("linter")

# new:
cfg = load_role_config("linter")
if model_override is not None:
    linter_llm = ChatBedrockConverse(
        model_id=model_override,
        region_name=cfg["region"],
        max_tokens=cfg["max_tokens"],
    )
else:
    linter_llm = make_llm("linter")
```

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` (extend)

**Analog:** `commands/query.py` (librarian override pattern).

**Existing `run_ingest_source` signature** (line 348–351 of ingest.py):
```python
async def run_ingest_source(
    source_path: Path,
    vault_path: Path | None = None,
) -> IngestResult:
```

**New parameter:**
```python
async def run_ingest_source(
    source_path: Path,
    vault_path: Path | None = None,
    model_override: str | None = None,   # sweep only
) -> IngestResult:
```

**Existing make_llm call** (line 408 of ingest.py):
```python
# current:
llm = make_llm("ingestor")

# new:
cfg = load_role_config("ingestor")
if model_override is not None:
    from langchain_aws import ChatBedrockConverse
    llm = ChatBedrockConverse(
        model_id=model_override,
        region_name=cfg["region"],
        max_tokens=cfg["max_tokens"],
    )
else:
    llm = make_llm("ingestor")
```

---

### `cores/model-adapter/src/model_adapter/models.toml` (extend)

**Analog:** self.

**Existing role block structure** (lines 13–17 of models.toml):
```toml
[roles.librarian]
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 5
```

**New structure with `sweep_candidates` (D-05, D-11 shape):**
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
# Sweep candidates (run YYYY-MM-DD): pareto-frontier members
#   - <model-id>  (cost=$X.XX, quality=0.XX)
# Previous default: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

**TOML loader tolerance:** Verified — `load_role_config(role)` returns the full dict including `sweep_candidates`. `make_llm()` reads only `model_id`, `region`, `max_tokens` — ignores the new key. No loader changes required.

**Tier-to-role candidate sets** (D-03):
- `scanner`, `code_reader` (cheap-fast): haiku-4-5, nova-micro, nova-lite, qwen3-32b
- `linter`, `ingestor` (mid): haiku-4-5, nova-pro, nova-lite, qwen3-32b
- `librarian`, `synthesizer` (quality): sonnet-4-6, haiku-4-5, nova-pro, qwen3-32b

---

### `eval/cases/query_cases.json` (extend — add vault-thin cases for `code_reader`)

**Analog:** self — existing 4-case structure (lines 1–26).

**Existing case shape:**
```json
{
  "case_id": "pkg-lookup-01",
  "query": "What does lattice-wiki-core do?",
  "expected_answer": "lattice-wiki-core provides the core wiki maintenance logic",
  "tags": ["package-lookup"]
}
```

**New vault-thin cases to append** (D-09 — forces `_run_code_fallback` to fire):
```json
{
  "case_id": "code-reader-01",
  "query": "How is _StdoutGuard implemented in the MCP server?",
  "expected_answer": "cannot be answered from vault pages alone",
  "tags": ["code-reader", "vault-thin"]
},
{
  "case_id": "code-reader-02",
  "query": "What does SubagentPool._write_trace write to the trace JSONL file?",
  "expected_answer": "tokens_in, tokens_out, role, and other trace fields",
  "tags": ["code-reader", "vault-thin"]
},
{
  "case_id": "code-reader-03",
  "query": "What are the exact parameters to _read_file_bounded?",
  "expected_answer": "repo_root and path parameters with size limit",
  "tags": ["code-reader", "vault-thin"]
}
```

Note: vault-thin cases must be filtered out of non-`code_reader` sweeps to avoid inflating case counts. Add a `"roles": ["code_reader"]` tag or use a separate `eval/cases/code_reader_cases.json` — planner decides.

---

### `cores/eval-harness/tests/test_role_sweep.py` (new)

**Analog:** `cores/eval-harness/tests/test_sweep.py` — copy its structure exactly.

**File header + imports pattern** (from test_sweep.py lines 1–17):
```python
"""Unit tests for run_role_sweep(): single-role-swap protocol, dispatch map,
sweep_candidates TOML read, and pre-flight estimator.

All tests use AsyncMock/patch to avoid Bedrock calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from eval_harness.sweep import SweepResult, run_role_sweep, estimate_sweep_cost
```

**Mock helper pattern** (from test_sweep.py lines 24–46):
```python
def _make_query_result(answer: str = "test answer [[wiki-page]]") -> QueryResult:
    return QueryResult(
        answer=answer,
        citations=["wiki-page"],
        pages_drilled=2,
        search_scores={"page.md": {"bm25": 0.5, "embed": 0.4, "rrf": 0.9}},
    )

def _make_cases_file(tmp_path: Path, cases: list[dict] | None = None) -> Path:
    if cases is None:
        cases = [{"case_id": "test-01", "query": "What?", "expected_answer": "something", "tags": []}]
    cases_path = tmp_path / "query_cases.json"
    cases_path.write_text(json.dumps(cases))
    return cases_path
```

**Single-role-swap assertion pattern** (copy `patch` style from test_sweep.py line 90):
```python
async def test_single_role_swap_librarian(tmp_path, fixture_vault_path):
    """Sweeping librarian role passes role_model_overrides={"librarian": candidate}
    to run_query; all other roles use defaults."""
    cases_path = _make_cases_file(tmp_path)
    captured_kwargs = {}

    async def _mock_run_query(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return _make_query_result()

    with patch("eval_harness.sweep.run_query", new=AsyncMock(side_effect=_mock_run_query)):
        await run_role_sweep("librarian", "us.amazon.nova-pro-v1:0", cases_path, fixture_vault_path, repeats=1)

    overrides = captured_kwargs.get("role_model_overrides", {})
    assert overrides.get("librarian") == "us.amazon.nova-pro-v1:0"
    assert "synthesizer" not in overrides
```

---

### `cores/eval-harness/tests/test_two_gate_scorer.py` (new)

**Analog:** `cores/eval-harness/tests/test_divergence_metric.py` — copy its construction + `run_programmatic` patterns.

**Key pattern** (from test_divergence_metric.py lines 66–77):
```python
from eval_harness.divergence.metric import DivergenceMetric
from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
from eval_harness.divergence.check import AgentOutputProxy

m = DivergenceMetric(
    role="librarian",
    checks=ROLE_CHECKS["librarian"],
    rubric_path=ROLE_RUBRICS["librarian"],
    vault=fixture_vault_path,
)
outputs = [("fix1", AgentOutputProxy(answer="See [[packages/lattice-wiki-core]]."))]
results = m.run_programmatic(outputs)
```

**check_regression pattern** (from metric.py lines 254–291):
```python
from eval_harness.divergence.metric import check_regression, load_baseline

baseline = load_baseline("librarian", baselines_dir)
# Raises AssertionError if hard rule failures > baseline
check_regression("librarian", current_results, baseline)
```

---

### `cores/eval-harness/tests/test_report_role_doc.py` (new)

**Analog:** `cores/eval-harness/tests/test_report.py`.

**Test structure pattern** — call `render_role_doc()` with a minimal `SweepResult` list and assert sections present in returned string:
```python
from eval_harness.report import render_role_doc, pareto_frontier

def test_render_role_doc_contains_required_sections(tmp_path):
    results = [...]  # minimal SweepResult list
    doc = render_role_doc(
        role="librarian", tier="quality", candidates=[...],
        sweep_results=results, divergence_results=None,
        run_date="2026-05-16", commit_sha="abc1234", total_cost_usd=0.42,
    )
    assert "Pareto frontier" in doc
    assert "Previous default" in doc
    assert "librarian" in doc
```

---

### `cores/eval-harness/tests/test_preflight_estimator.py` (new)

**Analog:** `cores/eval-harness/tests/test_pricing.py` — same import style, same pure-function test style (no Bedrock calls).

**Pattern:**
```python
from eval_harness.sweep import estimate_sweep_cost

def test_estimate_24_cell_sweep_within_cap():
    role_candidates = {
        "librarian":   ["us.anthropic.claude-sonnet-4-6", "us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        "synthesizer": ["us.anthropic.claude-sonnet-4-6", "us.anthropic.claude-haiku-4-5-20251001-v1:0"],
        # ... all 6 roles
    }
    estimated = estimate_sweep_cost(role_candidates, n_cases=4, repeats=3)
    assert estimated < 25.0  # hard cap from D-13
```

---

### `cores/eval-harness/tests/eval/test_sweep_dry_run.py` (new)

**Analog:** `cores/eval-harness/tests/eval/test_sweep_eval.py` — copy its two-phase `@pytest.mark.eval` + `eval_bag` structure but run under `--dry-run` with mock LLM.

**Path resolution pattern** (from test_sweep_eval.py lines 38–48):
```python
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
# adjust parent count for tests/eval/ subdirectory depth

CASES_PATH = _WORKSPACE_ROOT / "eval" / "cases" / "query_cases.json"
FIXTURE_VAULT = (
    _WORKSPACE_ROOT / "cores" / "vault-io" / "tests" / "fixtures" / "round-trip-vault"
)
```

**Module-level skip guard pattern** (from test_sweep_eval.py lines 100–109):
```python
if not CASES_PATH.exists():
    pytest.skip("query_cases.json not found; skipping dry-run sweep", allow_module_level=True)
if not FIXTURE_VAULT.exists():
    pytest.skip("round-trip-vault not found; skipping dry-run sweep", allow_module_level=True)
```

**Dry-run assertion pattern** (output files must exist after mock sweep):
```python
def test_dry_run_writes_all_role_docs(tmp_path):
    sweep_dir = tmp_path / ".planning" / "sweep"
    # run dry-run sweep with mock LLM writing to tmp_path
    for role in ["librarian", "ingestor", "linter", "scanner", "synthesizer", "code_reader"]:
        doc_path = sweep_dir / f"{role}.md"
        assert doc_path.exists(), f"Missing role doc: {doc_path}"
        assert "Pareto frontier" in doc_path.read_text()
    assert (sweep_dir / "INDEX.md").exists()
```

---

## Shared Patterns

### LLM Construction with Override (applies to all 4 command files)

**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (lines 824–832)

**Pattern — copy for each role override (scanner, linter, ingestor, synthesizer, code_reader):**
```python
cfg = load_role_config("ROLE_NAME")
if model_override is not None:
    role_llm = ChatBedrockConverse(
        model_id=model_override,
        region_name=cfg["region"],
        max_tokens=cfg["max_tokens"],
    )
else:
    role_llm = make_llm("ROLE_NAME")
```

**Apply to:** `scan.py` (scanner), `lint.py` (linter), `ingest.py` (ingestor), `query.py` (synthesizer, code_reader in addition to existing librarian).

### Model ID Sanitization (applies to all filename construction)

**Source:** `cores/eval-harness/src/eval_harness/sweep.py` (lines 73–82)

**Apply to:** All new per-role result filenames, per-role doc names, trace dir components. Always sanitize before using a model_id in a path.

```python
safe_model_id = re.sub(r"[^a-zA-Z0-9._-]", "_", model_id)
```

### Eval Double Gate (applies to all new eval and integration tests)

**Source:** `cores/eval-harness/tests/conftest.py` (lines 22–29) + `tests/eval/test_sweep_eval.py` (line 58)

**Apply to:** `test_sweep_dry_run.py` (integration gate) and any new `@pytest.mark.eval` tests.

```python
# Module-level mark — skips without --run-eval
pytestmark = [pytest.mark.eval]

# Test-level gate — skips without GRAPH_WIKI_RUN_EVAL=1
from conftest import EVAL_GATE  # or from eval_helpers import EVAL_GATE
EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_EVAL"),
    reason="Set GRAPH_WIKI_RUN_EVAL=1 to run eval sweep tests",
)
```

### Divergence Baseline Load + Regression Check (two-gate scorer)

**Source:** `cores/eval-harness/src/eval_harness/divergence/metric.py` (lines 215–291)

**Apply to:** Two-gate scoring in `run_role_sweep` for librarian, ingestor, linter, scanner.

```python
from eval_harness.divergence.metric import load_baseline, check_regression, DivergenceMetric
from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS

# Gate 1: divergence check
baseline = load_baseline(role, baselines_dir)
current = divergence_metric.run_programmatic(outputs)
check_regression(role, current, baseline)  # raises AssertionError on regression

# Gate 2: end-to-end judge score
# compare panel_score() mean against current default's score × threshold
```

### Cost Calculation (pre-flight + per-cell result)

**Source:** `cores/eval-harness/src/eval_harness/pricing.py` (lines 66–78)

**Apply to:** Pre-flight estimator, per-cell cost in SweepResult.

```python
from eval_harness.pricing import cost_for_usage, UnknownModelError

try:
    cost_usd = cost_for_usage(model_id, {"input": tokens_in, "output": tokens_out})
except UnknownModelError:
    cost_usd = None
```

### Partial-Failure Isolation (asyncio.gather pattern)

**Source:** `cores/eval-harness/src/eval_harness/sweep.py` (lines 253–267)

**Apply to:** `run_role_sweep` outer gather loop. Never let one cell abort the entire matrix.

```python
raw = await asyncio.gather(*coros, return_exceptions=True)
results = [item for item in raw if isinstance(item, SweepResult)]
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.planning/sweep/{role}.md` (6 files) | docs | — | No per-role sweep result docs exist yet; D-12 skeleton defined in CONTEXT.md is the spec |
| `.planning/sweep/INDEX.md` | docs | — | No analog; render from 6 role doc paths |
| `.planning/sweep/STORY.md` | docs | — | Hand-authored post-sweep; no programmatic analog |

---

## Metadata

**Analog search scope:** `cores/eval-harness/`, `agents/graph-wiki-agent/src/`, `eval/cases/`, `cores/model-adapter/`
**Files read:** 15 (sweep.py, pricing.py, metric.py, report.py, test_sweep_eval.py, conftest.py, test_sweep.py, test_divergence_metric.py, query.py, scan.py, lint.py, ingest.py, models.toml, query_cases.json, divergence-librarian.json)
**Pattern extraction date:** 2026-05-16
