# Phase 4: Eval Harness - Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 18
**Analogs found:** 16 / 18

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `cores/eval-harness/pyproject.toml` | config | — | `cores/subagent-runtime/pyproject.toml` | exact |
| `cores/eval-harness/src/eval_harness/__init__.py` | config | — | `cores/subagent-runtime/src/subagent_runtime/__init__.py` | role-match |
| `cores/eval-harness/src/eval_harness/baseline.py` | service | request-response (subprocess) | `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/runner_headless.py` | exact (port source) |
| `cores/eval-harness/src/eval_harness/isolation.py` | utility | file-I/O | `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/isolation.py` | exact (port source, simplify) |
| `cores/eval-harness/src/eval_harness/sweep.py` | service | batch | `cores/subagent-runtime/src/subagent_runtime/pool.py` | role-match |
| `cores/eval-harness/src/eval_harness/judge.py` | service | request-response | `RESEARCH.md` Pattern 1 (deepeval GEval + AmazonBedrockModel) | no analog in codebase |
| `cores/eval-harness/src/eval_harness/structural.py` | utility | transform | `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` `apply_guardrails()` | partial-match |
| `cores/eval-harness/src/eval_harness/pricing.py` | utility | transform | `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/pricing.py` | exact (port source, extend) |
| `cores/eval-harness/src/eval_harness/report.py` | utility | transform | `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/report.py` | role-match |
| `cores/eval-harness/tests/conftest.py` | test | — | `agents/code-wiki-agent/tests/conftest.py` | exact |
| `cores/eval-harness/tests/test_structural.py` | test | — | `cores/vault-io/tests/conftest.py` + query.py pattern | role-match |
| `cores/eval-harness/tests/test_sweep.py` | test | — | `cores/subagent-runtime/tests/conftest.py` | role-match |
| `cores/eval-harness/tests/test_baseline.py` | test | — | lattice-evals runner_headless + agents conftest | role-match |
| `cores/eval-harness/tests/test_report.py` | test | — | lattice-evals report.py structure | role-match |
| `cores/eval-harness/tests/test_pricing.py` | test | — | lattice-evals pricing.py | role-match |
| `eval/cases/query_cases.json` | config | — | no analog | none |
| `cores/model-adapter/src/model_adapter/models.toml` (modify) | config | — | `cores/model-adapter/src/model_adapter/models.toml` | self |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` (modify) | service | request-response | self | self |
| `cores/subagent-runtime/src/subagent_runtime/pool.py` (modify) | service | batch | self | self |

---

## Pattern Assignments

### `cores/eval-harness/pyproject.toml` (config)

**Analog:** `cores/subagent-runtime/pyproject.toml`

**Full pyproject.toml pattern** (lines 1-23):
```toml
[project]
name = "subagent-runtime"
version = "0.1.0"
description = "Async fan-out primitive for code-wiki-agent subagent dispatch"
requires-python = ">=3.11"
dependencies = [
    "langchain-aws>=1.4.6",
    "langchain-core>=1.4.0",
    "model-adapter",
]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.uv.sources]
model-adapter = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
asyncio_mode = "auto"
markers = ["integration: requires real Bedrock (skipped by default)"]
```

**Adaptation for eval-harness:** Name = `"eval-harness"`. Dependencies must include:
- `deepeval>=4.0.0` (judge panel)
- `pytest-evals>=0.3.4` (EVAL-10 two-phase integration)
- `code-wiki-agent` (sweep calls `run_query()`)
- `subagent-runtime` (sweep reads trace JSONL, adds cost accounting to pool.py)

Workspace source entries needed for all workspace deps. Add `markers` for both `integration` and `eval` marks. Note: `model-adapter` provides `models.toml` via `[tool.uv.build.include]` pattern (see `cores/model-adapter/pyproject.toml` lines 15-17).

---

### `cores/eval-harness/src/eval_harness/baseline.py` (service, subprocess)

**Port source:** `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/runner_headless.py`

**EVAL_SYSTEM_PROMPT_QA constant** (lines 43-50) — copy verbatim:
```python
EVAL_SYSTEM_PROMPT_QA = (
    "EVAL MODE (Q&A): This session runs inside an automated headless evaluation of a "
    "question-and-answer task. Answer the user's question directly using only read-only "
    "tools (Read, Glob, Grep, Bash for read-only commands). Do NOT call Edit or Write, "
    "and do NOT use Bash to modify files, install packages, run builds, or run tests — "
    "the prompt is asking for an answer, not an implementation. Do NOT pause to ask "
    "clarifying questions or present designs for approval. End your final reply with "
    "<DONE> on its own line once the answer is complete."
)
```

**RunResult dataclass** (lines 63-71) — copy verbatim, drop `simulator_*` fields (no user simulator in eval-harness):
```python
@dataclass
class RunResult:
    final_status: str
    budget_exceeded: bool
    wall_seconds: float
    turns: int
```

**_build_cmd() function** (lines 74-102) — copy and simplify: drop `auto_user` multi-turn path (baseline recorder is one-shot only). Keep `--output-format stream-json --verbose --add-dir --append-system-prompt --plugin-dir` flags. Drop `--input-format stream-json --replay-user-messages`:
```python
def _build_cmd(
    *,
    prompt: str,
    worktree_path: Path,
    system_prompt: str,
    plugin_dirs: list[Path] | None,
    model_override: str | None,
) -> list[str]:
    cmd = [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--add-dir", str(worktree_path),
        "--append-system-prompt", system_prompt,
    ]
    for pdir in plugin_dirs or []:
        cmd += ["--plugin-dir", str(pdir)]
    if model_override:
        cmd += ["--model", model_override]
    cmd.append(prompt)   # one-shot: prompt is always final positional arg
    return cmd
```

**_spawn() function** (lines 105-115) — copy verbatim (stdin=subprocess.DEVNULL for one-shot).

**run_headless() main loop** (lines 187-329) — copy the one-shot variant: drop `auto_user` branching, stdin management, `_select_reply()`. Keep: event loop over stdout, `ev["type"] == "assistant"` token accumulation, `ev["type"] == "result"` break. Keep budget checks (max_wall_seconds).

**BaselineRecorder wrapper** (new, not in lattice-evals): a class that loads `eval/cases/query_cases.json`, calls `run_headless()` per case, and snapshots to `eval/baselines/<case_id>.json`. Baseline JSON schema per D-specifics: `{query, case_id, answer, model_arn, prompt_hash, vault_content_hash, timestamp_utc}`.

---

### `cores/eval-harness/src/eval_harness/isolation.py` (utility, file-I/O)

**Port source:** `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/isolation.py`

**What to keep** from the original:
- `__aenter__`/`__aexit__` lifecycle pattern (lines 40-68 of original)
- `shutil.rmtree` cleanup in `__aexit__`
- `tempfile.mkdtemp` with prefix

**What to drop** (lattice-wiki-specific, lines 70-208 of original):
- `_validate_credentials()` — no OAuth needed (headless uses `--plugin-dir`)
- `_add_worktree()` — replace with `shutil.copytree` (fixture vault is not a git repo HEAD)
- `_remove_wiki()` — no `llm-wiki/` in code-wiki-agent
- `_build_cfg_dir()` / `_write_plugin_registry()` — no CLAUDE_CONFIG_DIR management

**Recommended EvalWorktree implementation** (from RESEARCH.md Pattern 3):
```python
import shutil
import tempfile
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

Note: `.code-wiki/` is included in the copy (pre-built BM25 + SQLite indexes travel with the vault). The `traces/` subdir inside the copy receives new JSONL during each sweep run.

---

### `cores/eval-harness/src/eval_harness/sweep.py` (service, batch)

**Analog:** `cores/subagent-runtime/src/subagent_runtime/pool.py`

**Partial-failure tolerance pattern** (pool.py lines 148-160) — copy `asyncio.gather(return_exceptions=True)` + `PerItemError` pattern:
```python
raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)

fan_result = FanOutResult()
for r in raw:
    if isinstance(r, PerItemError):
        fan_result.errors.append(r)
    elif isinstance(r, BaseException):
        logger.error("Unexpected gather exception: %s", r)
    else:
        fan_result.successes.append(r)
```

**Trace write pattern** (pool.py lines 162-210) — sweep accumulates per-run token counts. Read `tokens_in`/`tokens_out` from trace JSONL written by pool.py:
```python
# After run_query() completes, read the trace JSONL from wt.path / ".code-wiki" / "traces/"
# for this run's token counts. Each record has: "tokens_in", "tokens_out", "role", "model_id"
```

**Model override injection point** — sweep.py calls `run_query(query, vault_path=wt.path, top_k=5, librarian_model_override=model_id)`. This requires the `librarian_model_override` parameter added to query.py (see modifications section below).

**SweepResult dataclass** (new):
```python
@dataclass
class SweepResult:
    model_id: str
    query: str
    answer: str
    citations: list[str]
    pages_drilled: int
    tokens_in: int | None
    tokens_out: int | None
    cost_usd: float | None
    wall_seconds: float
    structural: dict         # output of check_structural()
    judge_scores: dict | None = None  # populated after judge panel runs
```

---

### `cores/eval-harness/src/eval_harness/judge.py` (service, request-response)

**No codebase analog.** Use RESEARCH.md Pattern 1 and Code Example (lines 619-664 of RESEARCH.md).

**Key patterns from research** (RESEARCH.md lines 621-664):
```python
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
```

**Critical: Always pass `model=` explicitly to every GEval instance** — deepeval defaults to OpenAI GPT if omitted (Pitfall 1 in RESEARCH.md).

**Position-bias check pattern** (RESEARCH.md Pitfall 5): run `panel_score(q, answer_a, answer_b)` then `panel_score(q, answer_b, answer_a)`; assert `abs(score1 - score2) < 0.05`.

**GEval instance per measure() call** — do not reuse `GEval` instances across parametrized test cases (RESEARCH.md anti-pattern).

---

### `cores/eval-harness/src/eval_harness/structural.py` (utility, transform)

**Analog:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` `apply_guardrails()` (lines 281-337)

**Citation resolution pattern** (query.py lines 311-327) — copy the G1 guard logic for wikilink resolution:
```python
unresolved: list[str] = []
for link in result.citations:
    link_path = link if link.endswith(".md") else f"{link}.md"
    candidate = vault_path / link_path
    if not candidate.exists():
        base = link.removesuffix(".md")
        matches = list(vault_path.glob(f"**/{base}.md"))
        if not matches:
            unresolved.append(link)
```

**_extract_wikilinks helper** (query.py line 271-273) — reuse or re-import:
```python
def _extract_wikilinks(text: str) -> list[str]:
    return re.findall(r"\[\[([^\]]+)\]\]", text)
```

**check_structural() return structure** (from RESEARCH.md lines 670-698):
```python
def check_structural(result: QueryResult, vault_path: Path) -> dict:
    """EVAL-06: wikilinks resolve, citations present, pages_drilled > 0."""
    return {
        "has_citation": len(result.citations) > 0,
        "citations_resolve": ...,   # bool
        "unresolved_citations": [], # list[str]
        "pages_drilled_positive": result.pages_drilled > 0,
    }
```

---

### `cores/eval-harness/src/eval_harness/pricing.py` (utility, transform)

**Port source:** `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/pricing.py`

**Full port** (lines 1-44) — copy module docstring, `UnknownModelError`, `PRICES` dict, and `cost_for_usage()` function verbatim, then extend `PRICES` with Bedrock models:

```python
# Extension from lattice-evals pricing.py — copy original 3 Claude entries, then add:
PRICES: dict[str, dict[str, float]] = {
    # Claude models (from lattice-evals pricing.py)
    "claude-opus-4-7":   {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "claude-sonnet-4-6": {"input": 3.0,  "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-haiku-4-5":  {"input": 1.0,  "output": 5.0,  "cache_read": 0.10, "cache_write": 1.25},
    # Bedrock on-demand prices verified 2026-05-14 (no cache_read/cache_write for Nova/Kimi)
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 1.0,  "output": 5.0},
    "us.anthropic.claude-sonnet-4-6":              {"input": 3.0,  "output": 15.0},
    "us.amazon.nova-pro-v1:0":                     {"input": 0.80, "output": 3.20},
    "us.amazon.nova-lite-v1:0":                    {"input": 0.30, "output": 1.20},
    "moonshotai.kimi-k2.5":                        {"input": 0.60, "output": 3.00},
}
```

`cost_for_usage()` (lattice-evals pricing.py lines 36-44) — copy verbatim. Takes `model: str` and `usage: dict[str, int]` (keys: `input`, `output`; no `cache_*` for Bedrock non-Claude models).

---

### `cores/eval-harness/src/eval_harness/report.py` (utility, transform)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/report.py`

**Report structure pattern** (lattice-evals report.py lines 71-151) — different domain but same general pattern: read sweep result JSONs, build a table, write output. Key differences: no Jinja2 templates needed (planner decision: plain string table or JSON output is simpler); no `metrics.json`/`meta.json` file pairs — sweep results come from `SweepResult` dataclasses.

**cost_frontier_table() function** — new, takes list of `SweepResult`, returns a dict (or rendered string) of `{model_id: {quality_score, cost_usd, pages_drilled, ...}}` sorted by quality descending.

**regression_check() function** — new, takes composite score and threshold; raises `AssertionError` with structured message if below threshold. Pattern mirrors the `_callouts()` function (report.py lines 46-68): iterate results, find outliers, emit structured message.

**Output formats:** per CONTEXT.md specifics — a pytest-captured JSON or printed table. Planner picks simplest. Recommend: `report.py` returns a dict; test captures it; `print_frontier()` formats it as a table for CLI use.

---

### `cores/eval-harness/tests/conftest.py` (test)

**Analog:** `agents/code-wiki-agent/tests/conftest.py`

**INTEGRATION_GATE pattern** (code-wiki-agent conftest.py lines 19-22) — mirror exactly, renamed to EVAL_GATE with `CODE_WIKI_RUN_EVAL`:
```python
import os
import pytest
from pathlib import Path

EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_EVAL"),
    reason="Set CODE_WIKI_RUN_EVAL=1 to run real eval suite",
)
```

**fixture_vault_path fixture** (code-wiki-agent conftest.py lines 25-50) — copy verbatim; the path computation via `Path(__file__).parent.parent.parent.parent / "cores" / "vault-io" / "tests" / "fixtures" / "round-trip-vault"` is the same since eval-harness is also under `cores/`:
```python
@pytest.fixture
def fixture_vault_path() -> Path:
    vault = (
        Path(__file__).parent.parent.parent.parent
        / "cores"
        / "vault-io"
        / "tests"
        / "fixtures"
        / "round-trip-vault"
    )
    if not vault.exists():
        pytest.skip(f"round-trip-vault fixture not found at {vault}")
    return vault
```

---

### `cores/eval-harness/tests/test_structural.py` (test, unit)

**Analog:** vault-io tests pattern + query.py `apply_guardrails()` structure.

**QueryResult fixture pattern** — construct a synthetic `QueryResult` with known citations to test `check_structural()`:
```python
from code_wiki_agent.commands.query import QueryResult

@pytest.fixture
def good_result():
    return QueryResult(
        answer="See [[packages/lattice-wiki-core]].",
        citations=["packages/lattice-wiki-core"],
        pages_drilled=3,
        search_scores={},
    )
```

**Test EVAL-06 known-good case:** assert `check_structural(good_result, fixture_vault_path)["citations_resolve"]` is True (the citation target must exist in the round-trip-vault).

**Test EVAL-02 fixture vault has pages:** assert `len(list(fixture_vault_path.rglob("*.md"))) > 3`.

---

### `cores/eval-harness/tests/test_sweep.py` (test, unit)

**Analog:** `cores/subagent-runtime/tests/conftest.py` mock pattern.

**Mock run_query pattern** (subagent-runtime conftest.py lines 24-31):
```python
@pytest.fixture
def make_task(fake_llm_response):
    def _make(*, raise_for=frozenset()):
        async def task(item):
            if item in raise_for:
                raise ValueError(f"Intentional failure for item: {item}")
            return fake_llm_response
        return task
    return _make
```

**For sweep tests:** mock `run_query` to return a synthetic `QueryResult`, verify that sweep runner collects N results for N model_ids. Test partial-failure tolerance: one model raises, others succeed.

---

### `cores/eval-harness/tests/test_baseline.py` (test, unit)

**Test _build_cmd():** call `_build_cmd(prompt="test", worktree_path=tmp_path, system_prompt="...", plugin_dirs=None, model_override=None)` and assert it contains `["claude", "-p", "--output-format", "stream-json", ..., "test"]`. No subprocess spawned.

**Test baseline JSON schema (EVAL-08):** call `BaselineRecorder.record()` with a mocked `run_headless()` that returns a canned RunResult; assert the written JSON includes `query`, `model_arn`, `prompt_hash`, `vault_content_hash`, `timestamp_utc`.

---

### `cores/eval-harness/tests/test_report.py` (test, unit)

**Test regression_check() raises (EVAL-09):**
```python
from eval_harness.report import regression_check

def test_regression_check_fails():
    with pytest.raises(AssertionError, match="below threshold"):
        regression_check(score=0.3, threshold=0.5)

def test_regression_check_passes():
    regression_check(score=0.7, threshold=0.5)  # no raise
```

**Test cost_frontier_table():** build synthetic `SweepResult` list with known costs; assert table keys match model_ids and cost values are correct.

---

### `cores/eval-harness/tests/test_pricing.py` (test, unit)

**Analog:** lattice-evals pricing.py structure.

**Test cost_for_usage():**
```python
from eval_harness.pricing import cost_for_usage

def test_nova_pro_cost():
    # 1M input + 1M output tokens at Nova Pro rates
    cost = cost_for_usage("us.amazon.nova-pro-v1:0", {"input": 1_000_000, "output": 1_000_000})
    assert abs(cost - (0.80 + 3.20)) < 0.001

def test_unknown_model_raises():
    with pytest.raises(KeyError):
        cost_for_usage("unknown-model", {"input": 1000, "output": 1000})
```

---

### `eval/cases/query_cases.json` (config)

**No analog.** Planner designs schema per D-03 suggestion: `{query, expected_answer, tags?}`.

**Minimum 3 cases** exercising different vault aspects per CONTEXT.md specifics:
- Package-lookup query (e.g. "What does lattice-wiki-core do?")
- Concept query (e.g. "How does the BM25 search index work?")
- Cross-reference query (e.g. "Which packages depend on lattice-source-parser?")

---

## Modifications to Existing Files

### `cores/model-adapter/src/model_adapter/models.toml` (modify)

**Change:** Update `[roles.judge_b]` `model_id` from `"us.anthropic.claude-sonnet-4-6"` to `"us.amazon.nova-pro-v1:0"` per D-07.

**Current lines 49-54:**
```toml
[roles.judge_b]
model_id        = "us.anthropic.claude-sonnet-4-6"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 2
```

**Updated:**
```toml
[roles.judge_b]
model_id        = "us.amazon.nova-pro-v1:0"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 2
```

---

### `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` (modify)

**Change:** Add `librarian_model_override: str | None = None` parameter to `run_query()` per RESEARCH.md Pattern 2 and Pitfall 4. When provided, construct `ChatBedrockConverse` directly with the given model_id instead of calling `make_llm("librarian")`.

**Current signature** (query.py line 460-464):
```python
async def run_query(
    query: str,
    vault_path: Path | None = None,
    top_k: int = 5,
) -> QueryResult:
```

**New signature:**
```python
async def run_query(
    query: str,
    vault_path: Path | None = None,
    top_k: int = 5,
    librarian_model_override: str | None = None,
) -> QueryResult:
```

**Injection point** (query.py lines 528-529):
```python
# Current:
lib_cfg = load_role_config("librarian")
librarian_llm = make_llm("librarian")

# Modified (surgical addition):
lib_cfg = load_role_config("librarian")
if librarian_model_override is not None:
    from langchain_aws import ChatBedrockConverse
    librarian_llm = ChatBedrockConverse(
        model_id=librarian_model_override,
        region_name=lib_cfg["region"],
        max_tokens=lib_cfg["max_tokens"],
    )
else:
    librarian_llm = make_llm("librarian")
```

---

### `cores/subagent-runtime/src/subagent_runtime/pool.py` (modify)

**Change:** Finish cost accounting in `_write_trace()`. The `cost_usd: None` field (line 200) and comment `# Phase 4 adds cost accounting` (line 200) mark this as a Phase 4 task.

**Current line 200:**
```python
"cost_usd": None,  # Phase 4 adds cost accounting
```

**Updated pattern** — compute cost from `tokens_in`/`tokens_out` using `eval_harness.pricing`:
```python
# After tokens_in/tokens_out are set:
cost_usd: float | None = None
if tokens_in is not None and tokens_out is not None:
    try:
        from eval_harness.pricing import cost_for_usage, UnknownModelError
        cost_usd = cost_for_usage(model_id, {"input": tokens_in, "output": tokens_out})
    except (UnknownModelError, ImportError):
        pass  # unknown model or eval-harness not installed — cost stays None
```

Note: The `eval_harness` import is intentionally lazy (inside the function) to avoid a hard dependency from `subagent-runtime` on `eval-harness`. The planner should verify whether a direct dep or lazy import is preferable given workspace topology.

---

## Shared Patterns

### `from __future__ import annotations`
**Source:** Every existing source file in the codebase (pool.py line 1, query.py line 1, etc.)
**Apply to:** All new `eval_harness/` module files.
```python
from __future__ import annotations
```

### EVAL_GATE skip marker
**Source:** `agents/code-wiki-agent/tests/conftest.py` lines 19-22 (INTEGRATION_GATE pattern)
**Apply to:** `cores/eval-harness/tests/conftest.py` and any test that calls real Bedrock
```python
EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_EVAL"),
    reason="Set CODE_WIKI_RUN_EVAL=1 to run real eval suite",
)
```

### Async context manager lifecycle (EvalWorktree)
**Source:** `isolation.py` `IsolationContext.__enter__`/`__exit__` pattern (lines 40-68)
**Apply to:** `eval_harness/isolation.py` `EvalWorktree.__aenter__`/`__aexit__`
Pattern: `tempfile.mkdtemp` on enter, `shutil.rmtree(ignore_errors=True)` on exit.

### Partial-failure fan-out
**Source:** `cores/subagent-runtime/src/subagent_runtime/pool.py` lines 148-160
**Apply to:** `eval_harness/sweep.py` model sweep loop
Pattern: `asyncio.gather(return_exceptions=True)` + per-item error isolation.

### pytest asyncio_mode = "auto"
**Source:** `cores/subagent-runtime/pyproject.toml` line 22
**Apply to:** `cores/eval-harness/pyproject.toml` `[tool.pytest.ini_options]`
```toml
asyncio_mode = "auto"
```

### UnknownModelError + PRICES dict
**Source:** `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/pricing.py` lines 8-44
**Apply to:** `eval_harness/pricing.py` — direct port, extend with Bedrock entries.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `cores/eval-harness/src/eval_harness/judge.py` | service | request-response | No deepeval GEval or AmazonBedrockModel usage exists in the codebase; use RESEARCH.md Pattern 1 + Code Example directly |
| `eval/cases/query_cases.json` | config | — | No existing eval case JSON files; planner designs schema per D-03 |

---

## Metadata

**Analog search scope:** `cores/`, `agents/`, `/Users/pat/Personal/lattice/packages/lattice-evals/src/lattice_evals/`
**Files scanned:** 15 source files + 3 pyproject.toml files
**Pattern extraction date:** 2026-05-14
