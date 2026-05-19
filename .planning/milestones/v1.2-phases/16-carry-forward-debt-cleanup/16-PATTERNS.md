# Phase 16: Carry-Forward Debt Cleanup — Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 13 (7 new, 6 modified)
**Analogs found:** 12 / 13 (1 has no direct analog — `docs/testing.md` reuses `docs/cancellation.md` shape)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| **NEW** `packages/subagent-runtime/src/subagent_runtime/trace_io.py` | utility (helper) | file-I/O (JSONL append) | `packages/subagent-runtime/src/subagent_runtime/pool.py` §`_write_trace` (186–231) | exact (this IS the extraction source) |
| **NEW** `packages/eval-harness/src/eval_harness/divergence/code_reader.py` | utility (rule module) | transform (text→Verdict) | `packages/eval-harness/src/eval_harness/divergence/librarian.py` | exact (same role family) |
| **NEW** `packages/eval-harness/src/eval_harness/divergence/synthesizer.py` | utility (rule module) | transform (text→Verdict) | `packages/eval-harness/src/eval_harness/divergence/librarian.py` | exact (same role family) |
| **NEW** `packages/eval-harness/src/eval_harness/divergence/rubrics/code_reader.md` | config (judge rubric) | document | `packages/eval-harness/src/eval_harness/divergence/rubrics/librarian.md` | exact |
| **NEW** `packages/eval-harness/src/eval_harness/divergence/rubrics/synthesizer.md` | config (judge rubric) | document | `packages/eval-harness/src/eval_harness/divergence/rubrics/librarian.md` | exact |
| **NEW** `eval/cases/code_reader_cases.json` (extended) | config (test data) | document | existing 3 cases in the same file + `eval/cases/query_cases.json` shape | exact (additive — preserve baseline) |
| **NEW** `packages/eval-harness/tests/fixtures/<vault>/...` | test fixture | file-I/O (vault read) | `packages/vault-io/tests/fixtures/round-trip-vault/` (used by `agents/code-wiki-agent/tests/conftest.py` and `test_query_e2e.py`) | role-match |
| **NEW** `agents/code-wiki-agent/tests/integration/test_trace_coverage.py` (or similar) | test (gated integration) | request-response (subprocess + filesystem assert) | `agents/code-wiki-agent/tests/integration/test_query_e2e.py` | exact |
| **NEW** `docs/testing.md` | config (documentation) | document | `docs/cancellation.md` (sibling; 5-section structure) | role-match |
| **NEW** `scripts/check-integration-gate.sh` OR `tests/test_integration_gate.py` | utility (CI gate) | transform (grep → exit code) | `scripts/check-brand.sh` (script form); existing pytest meta-tests like `test_models_toml_sweep_candidates.py` (test form) | exact |
| **MOD** `packages/subagent-runtime/src/subagent_runtime/pool.py` | service (fan-out) | event-driven | self (refactor `_write_trace` → thin delegate to `trace_io.write_record`) | n/a — touch surgical |
| **MOD** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:438` | controller (CLI command) | request-response | `pool.py` `_write_trace` call sites in `_run_one` (137–151) | role-match (call shape) |
| **MOD** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:977` | controller (CLI command) | request-response | `pool.py` `_write_trace` usage_metadata extraction (203–209) | exact (graft same logic onto `query_summary` record) |
| **MOD** `packages/eval-harness/src/eval_harness/two_gate.py:36` | service (scoring) | transform | self (extend frozenset) | n/a — one-line change |
| **MOD** `packages/model-adapter/tests/test_loader.py:125-130` | test | request-response | `test_load_role_config_librarian_values` (`test_loader.py:116-122`) | exact (same shape, extend with `model_id` assertion) |
| **MOD** `docs/cancellation.md` §4–§5 | config (documentation) | document | self (edit-in-place if spike gate fails) | n/a |

---

## Pattern Assignments

### NEW `packages/subagent-runtime/src/subagent_runtime/trace_io.py` (utility, file-I/O)

**Analog:** `packages/subagent-runtime/src/subagent_runtime/pool.py` §`_write_trace` (lines 182–231) — this IS the canonical source. D-04 calls for pure extraction with no behavior change.

**Module-level imports pattern** (model on `pool.py:27-39`):
```python
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
```

**Core record-construction + JSONL append pattern** (extract verbatim from `pool.py:194-231`):
```python
def write_trace_record(
    path: Path,
    role: str,
    model_id: str,
    item: Any,
    status: str,
    latency_ms: int,
    response: Any,
    *,
    error: str | None = None,
) -> None:
    """Write one JSONL record to the trace file.

    Never raises — OSError is caught and logged as WARNING so that trace
    failures never mask successful task results (AI-SPEC Failure Mode #2).

    Token fields come from ChatBedrockConverse usage_metadata dict:
    {"input_tokens": N, "output_tokens": N, "total_tokens": N}.
    usage_metadata is None on error responses — guarded explicitly.
    """
    tokens_in: int | None = None
    tokens_out: int | None = None
    if response is not None and hasattr(response, "usage_metadata"):
        meta = response.usage_metadata  # None on ThrottlingException / content filter
        if meta is not None:
            tokens_in = meta.get("input_tokens")
            tokens_out = meta.get("output_tokens")

    record: dict[str, Any] = {
        "schema_version": 1,  # Phase 9 OBS-04 D-01/D-02 — every record self-describing
        "role": role,
        "model_id": model_id,
        "prompt_hash": None,  # caller may set; None until computed upstream
        "item_id": getattr(item, "id", None) or str(item),
        "status": status,
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": _compute_cost_usd(model_id, tokens_in, tokens_out),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if error:
        record["error"] = error

    try:
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("Trace write failed (data loss): %s", exc)
```

**Critical invariants to preserve (from `pool.py:65-77` docstring):**
- `usage_metadata is None` on Bedrock error responses — guard before `.get()`
- OSError on write is logged + swallowed; never raises
- `schema_version: 1` on every record (Phase 9 OBS-04 D-01/D-02)
- `_compute_cost_usd(model_id, tokens_in, tokens_out)` stays in the helper (defined elsewhere in `pool.py`)

**Where `_compute_cost_usd` lives:** Confirm location during scout — likely move alongside the helper or import from existing location. Do not duplicate the cost-pricing logic.

---

### MOD `packages/subagent-runtime/src/subagent_runtime/pool.py` (refactor `_write_trace` to delegate)

**Pattern:** `_write_trace` becomes a thin method wrapping the module-level helper. The three call sites in `_run_one` (`pool.py:137-151`) stay identical:

```python
# pool.py:137-151 — these call sites stay unchanged
self._write_trace(
    trace_file, role, model_id, item, "success", latency_ms, result
)
# ... "cancelled" ...
self._write_trace(
    trace_file, role, model_id, item, "error", latency_ms, None, error=str(exc)
)
```

The body of `_write_trace` shrinks to:
```python
def _write_trace(self, path, role, model_id, item, status, latency_ms, response, *, error=None):
    from subagent_runtime.trace_io import write_trace_record
    write_trace_record(path, role, model_id, item, status, latency_ms, response, error=error)
```

(Or remove the method entirely and have call sites import the helper — scout's call. The locked decision per D-04 is "helper IS the writer," so the wrapper-method form is fine if it keeps the diff smaller.)

---

### MOD `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:438` (controller, request-response)

**Current code (no trace at all):**
```python
# ingest.py:428-439
ingestor_cfg = load_role_config("ingestor")
if model_override is not None:
    llm = ChatBedrockConverse(
        model_id=model_override,
        region_name=ingestor_cfg["region"],
        max_tokens=ingestor_cfg["max_tokens"],
    )
else:
    llm = make_llm("ingestor")
resp = await llm.ainvoke([SystemMessage(...), HumanMessage(prompt)])
llm_output: str = resp.content
```

**Pattern to apply (model on `pool.py:121-140` shape):**
- Wrap the `ainvoke` in `time.monotonic()` start/stop
- Call `write_trace_record(trace_dir / f"{int(time.time())}_{uuid8}.jsonl", role="ingestor", model_id=resolved_model_id, item=source_path, status="success", latency_ms=..., response=resp)`
- On exception path, write `status="error"` with `error=str(exc)`
- Resolve trace dir from `wiki / ".code-wiki" / "traces"` (same as `query.py:977`)

**Reference for trace-dir derivation** (`query.py:977-979`):
```python
trace_dir = wiki / ".code-wiki" / "traces"
trace_dir.mkdir(parents=True, exist_ok=True)
```

---

### MOD `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:977` (controller, backfill usage fields)

**Current `query_summary` record** (`query.py:980-994`):
```python
summary_record = {
    "schema_version": 1,
    "kind": "query_summary",
    "query_id": query_id,
    "query": query,
    "top_k": top_k,
    "pages_retrieved": len(top_pages),
    "pages_drilled": query_result.pages_drilled,
    "code_fallback": code_fallback_used,
    "started_at": started_at,
    "ended_at": ended_at,
}
```

**Pattern to apply:** This is NOT a per-item subagent record — it's a `kind: query_summary` discriminator record (see `docs/trace-schema.md` §2). The shared helper writes per-item records; the summary record stays in `query.py` but must aggregate `tokens_in` / `tokens_out` from upstream calls.

**Two viable shapes (executor's call during scout):**
1. Add aggregate `tokens_in_total` / `tokens_out_total` fields populated from the synthesizer call + librarian fan-out totals.
2. Add `tokens_in` / `tokens_out` fields specifically for the synthesizer LLM call that produces the final answer (analogous to per-item records).

**Source for usage_metadata extraction** (lift exactly from `pool.py:203-209`):
```python
tokens_in: int | None = None
tokens_out: int | None = None
if response is not None and hasattr(response, "usage_metadata"):
    meta = response.usage_metadata
    if meta is not None:
        tokens_in = meta.get("input_tokens")
        tokens_out = meta.get("output_tokens")
```

**OSError-swallow already in place** (`query.py:995-996`) — preserve.

---

### NEW `packages/eval-harness/src/eval_harness/divergence/code_reader.py` & `synthesizer.py` (utility, transform)

**Analog:** `packages/eval-harness/src/eval_harness/divergence/librarian.py` (4 hard/soft checks) and `scanner.py` (4 hard checks).

**Module structure pattern** (model on `librarian.py:1-21`):
```python
"""Programmatic divergence checks for the {role} role ({PREFIX}-001..{PREFIX}-NNN).

Security (T-06-15): All check callables use regex and string operations only.
No eval/exec of LLM-generated text.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck, Verdict
```

**Check callable pattern** (`librarian.py:33-41`):
```python
def _check_<rule_name>(output: AgentOutputProxy, vault: Path) -> Verdict:
    """<RULE-ID>: <one-line description>."""
    # ... regex/string ops only — no eval/exec ...
    if <violation>:
        return Verdict(passed=False, excerpt=f"<short evidence ≤200 chars>")
    return Verdict(passed=True, excerpt="")
```

**Module-level exports pattern** (`librarian.py:72-97`):
```python
CODE_READER_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(
        id="CR-001-<slug>",
        source_anchor="packages/prompt-sources/agents/code_reader.md#<section>",
        severity="hard",   # or "soft" for non-gating rules
        check=_check_<rule_name>,
    ),
    # ... more rules ...
]
```

**Rule-ID prefix convention** (per `metric.py:40-45` `_ROLE_JUDGE_ID` mapping):
- `code_reader` → rule prefix `CR-`, judge id `CR-JUDGE`
- `synthesizer` → rule prefix `SYN-`, judge id `SYN-JUDGE`
- Executor must extend `_ROLE_JUDGE_ID` in `metric.py:40-45` to add these mappings.

**Severity rigor target (D-06):** Phase-6 rigor — not minimal-viable. Match `librarian.py` (3 hard + 1 soft) and `scanner.py` (4 hard) shapes. 3–4 rules per role, anchored to canonical source files in `packages/prompt-sources/agents/`.

**Register in `__init__.py`** (`divergence/__init__.py:26-45`):
```python
from eval_harness.divergence.code_reader import CODE_READER_CHECKS
from eval_harness.divergence.synthesizer import SYNTHESIZER_CHECKS

ROLE_CHECKS: dict[str, list[DivergenceCheck]] = {
    "librarian": LIBRARIAN_CHECKS,
    "ingestor": INGESTOR_CHECKS,
    "linter": LINTER_CHECKS,
    "scanner": SCANNER_CHECKS,
    "code_reader": CODE_READER_CHECKS,    # NEW
    "synthesizer": SYNTHESIZER_CHECKS,    # NEW
}

ROLE_RUBRICS: dict[str, Path] = {
    # ... existing 4 ...
    "code_reader": _RUBRICS_DIR / "code_reader.md",    # NEW
    "synthesizer": _RUBRICS_DIR / "synthesizer.md",    # NEW
}
```

---

### NEW Rubric files `rubrics/code_reader.md` & `rubrics/synthesizer.md` (config, document)

**Analog:** `packages/eval-harness/src/eval_harness/divergence/rubrics/librarian.md` (verbatim shape below).

**Required header pattern** (`librarian.md:1-3`):
```markdown
<!-- Source: packages/prompt-sources/agents/<role>.md -->
<!-- Anchor: ## Rules + ## Red flags -->
<!-- Source-commit: <git-sha-of-source-at-port-time> -->
```

**Body structure** (`librarian.md:5-36`):
- `# Divergence Rubric — <Role>` heading
- Intro paragraph naming the canonical spec
- `## Scoring Criteria` section listing 2+ judge-only rule IDs (`<PREFIX>-005-...`, `<PREFIX>-006-...`) numbered after the programmatic rule IDs
- Each criterion: bold ID + 1-paragraph description + `(pass/fail)` suffix
- `## Scoring` section explaining 0.0–1.0 fraction-of-criteria-passed mapping

**Judge-only IDs that don't appear in the programmatic checks list:** these encode subjective rules (e.g. `LIB-005-refusal-pattern`, `LIB-006-no-invention`). For `code_reader` and `synthesizer`, executor authors 2–3 judge-only rules per the D-06 "Phase-6 rigor" target.

---

### MOD `packages/eval-harness/src/eval_harness/two_gate.py:36` (service, scoring)

**Current code** (`two_gate.py:35-38`):
```python
# D-07: roles that have Phase-6 divergence rubrics and run Gate 1.
ROLES_WITH_DIVERGENCE: frozenset[str] = frozenset(
    {"librarian", "ingestor", "linter", "scanner"}
)
```

**Pattern to apply (one-line extension):**
```python
# D-07 + D-06 (Phase 16): all 6 in-scope roles run Gate 1.
ROLES_WITH_DIVERGENCE: frozenset[str] = frozenset(
    {"librarian", "ingestor", "linter", "scanner", "code_reader", "synthesizer"}
)
```

**Downstream effect:** Code path in `two_gate.py:103-126` (Gate 1 branch) now triggers for the 2 new roles. The `divergence_metric_or_none is None` guard (line 104) means a caller that omits the metric for these roles now produces `gate1_passed=False` — executor must verify callers in `sweep.py` pass the new metrics.

**Comment update for line 11-12 module docstring:** `D-08 (synthesizer, code_reader): Gate 2 only` — flip to "All 6 in-scope roles run both gates" after the change.

---

### NEW `eval/cases/code_reader_cases.json` (extended; config, test data)

**Analog:** Existing 3 cases in the same file (lines 1–20) + `eval/cases/query_cases.json` shape.

**Existing case shape** (`code_reader_cases.json:2-7`):
```json
{
  "case_id": "code-reader-01",
  "query": "How is _StdoutGuard implemented in the MCP server?",
  "expected_answer": "cannot be answered from vault pages alone; requires reading mcp_server.py source",
  "tags": ["code-reader", "vault-thin"]
}
```

**Expansion pattern (D-07):** Keep the existing 3 cases unmodified for baseline comparability. Append 2–3 new cases reflecting the post-rebrand surface:
- Target candidates: `workspace-io`, `graph-wiki` plugin entry points, `vault-io.lint_wiki`, `vault-io.wiki_search`
- New `case_id` values continue the `code-reader-04`, `code-reader-05` numbering
- `tags` must include `"code-reader"`; `"vault-thin"` stays (cases force the code-fallback path per <specifics>)
- `expected_answer` follows the existing "cannot be answered from vault pages alone; requires reading <file>" prose pattern

**Count constraint to watch:** `packages/eval-harness/tests/test_models_toml_sweep_candidates.py:22-51` documents `code_reader_cases.json` count/path constraints — executor must check whether any hard-coded count assertion needs bumping.

---

### NEW Synthetic fixture vault (test fixture, file-I/O)

**Analog:** `packages/vault-io/tests/fixtures/round-trip-vault/` — referenced by `agents/code-wiki-agent/tests/conftest.py:25-50` (`fixture_vault_path`) and `agents/code-wiki-agent/tests/integration/test_query_e2e.py:27-34` (`FIXTURE_VAULT`).

**Location decision (per "Claude's Discretion"):** Prefer `packages/eval-harness/tests/fixtures/<vault-name>/` (eval-harness-local), per CONTEXT.md.

**Path-resolution pattern to copy** (`test_query_e2e.py:27-34`):
```python
# Precomputed at import time so downstream code can reference as default arg
FIXTURE_VAULT: Path = (
    Path(__file__).parent.parent / "fixtures" / "<vault-name>"
)
```

**Vault contents pattern:** Package pages with current names (`workspace-io`, `prompt-sources`, `vault-io`, etc.). Mirror the structure of `~/Personal/wiki/deep-agents` but smaller — enough for the scanner regression sweep to produce non-trivial output.

---

### NEW Gated integration test `test_trace_coverage.py` (test, gated)

**Analog:** `agents/code-wiki-agent/tests/integration/test_query_e2e.py` (subprocess + JSON-parse + assertions).

**Module preamble pattern** (`test_query_e2e.py:1-42`):
```python
from __future__ import annotations

"""End-to-end TRACE-FU-01 regression: real fan-out asserts every JSONL
record has non-None input_tokens / output_tokens (SC#1 D-05).

Gated by CODE_WIKI_RUN_INTEGRATION=1.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

FIXTURE_VAULT: Path = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages" / "vault-io" / "tests" / "fixtures" / "round-trip-vault"
)
_PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent.parent

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)
```

**Test-body pattern** (`test_query_e2e.py:45-80`):
```python
@pytest.mark.integration
@INTEGRATION_GATE
def test_<name>(tmp_path: Path) -> None:
    """Runs scan + ingest + query against tmp_path vault; parses every
    JSONL file under .code-wiki/traces/; asserts non-None tokens on
    every non-error record."""
    # subprocess.run(["uv", "run", "--package", "code-wiki-agent",
    #                "code-wiki-agent", "<subcmd>", ...], cwd=_PROJECT_ROOT, ...)
    # then: for jsonl in (tmp_path / ".code-wiki" / "traces").glob("*.jsonl"):
    #         for line in jsonl.read_text().splitlines():
    #             rec = json.loads(line)
    #             if rec.get("status") == "error" or rec.get("event"):
    #                 continue
    #             assert rec["tokens_in"] is not None, rec
    #             assert rec["tokens_out"] is not None, rec
```

**Critical exclusions (per D-05):**
- Records with `status == "error"` — `usage_metadata` legitimately None on Bedrock error responses (pool.py:205-209 guard).
- Records with `event` key — batch terminal records have no token fields.
- Records with `kind == "query_summary"` — separate shape, but executor decides whether to extend it with token fields per D-03.

---

### NEW `docs/testing.md` (config, document)

**Analog:** `docs/cancellation.md` (sibling file, 5-section structure).

**Section structure to mirror** (`docs/cancellation.md`):
- `## 1. <Topic intro / spec basis>`
- `## 2. <Internal pattern / chain>`
- `## 3. <Concrete shapes / canonical example>`
- `## 4. <Known limitations / inventory>`
- `## 5. <Future / re-eval triggers>`

**Header pattern** (`docs/cancellation.md:1-12`):
```markdown
# <Topic> in code-wiki-agent

This document describes <one-paragraph scope statement>. It covers the
<list of major sections>.

**v1.2 scope:** <what's locked in v1.2 vs. deferred>.

---
```

**Canonical skip-decorator block to document** (verbatim from `agents/code-wiki-agent/tests/conftest.py:19-22`):
```python
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)
```

**Inventory of currently-gated files (to list in `docs/testing.md`):**
- `agents/code-wiki-agent/tests/conftest.py:19-22` — canonical home
- `agents/code-wiki-agent/tests/integration/test_mcp_e2e.py:20-23` — copy of the decorator (matches canonical shape)
- `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py:142-143`
- `agents/code-wiki-agent/tests/integration/test_query_e2e.py:39-42`
- `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py:33-35` — **DIVERGES**: uses inline `pytest.skip(...)` inside test body, not a module-level decorator. Either bring this into the canonical shape or allowlist it explicitly.
- `packages/subagent-runtime/tests/integration/test_pool_bedrock.py:29-30`

---

### NEW Grep gate (`scripts/check-integration-gate.sh` OR `tests/test_integration_gate.py`)

**Two patterns to choose from (Claude's Discretion per CONTEXT.md):**

**(a) Bash-script form — analog:** `scripts/check-brand.sh`:
```bash
#!/usr/bin/env bash
# scripts/check-integration-gate.sh — MCP-CAN-02 grep gate.

set -euo pipefail
ALLOWLIST=".integration-gate-allow"   # optional

# Pattern: every test file under */tests/integration/ must contain the canonical
# skip-decorator OR be allowlisted.
HITS=$(...)  # locate gated test files that DON'T match the canonical pattern
if [ -n "$HITS" ]; then
  echo "$HITS"
  echo "MCP-CAN-02 FAIL: <N> divergent integration-gate patterns" >&2
  exit 1
fi
echo "MCP-CAN-02 OK"
```

**(b) Pytest meta-test form — analog:** `packages/eval-harness/tests/test_models_toml_sweep_candidates.py` (asserts repo invariants in pytest).
```python
"""MCP-CAN-02 grep gate (test form).

Walks every */tests/integration/*.py file and asserts each contains the
canonical CODE_WIKI_RUN_INTEGRATION skip-decorator pattern (or is explicitly
allowlisted via comment marker).
"""
from pathlib import Path
import re

_CANONICAL_PATTERN = re.compile(
    r'pytest\.mark\.skipif\(\s*\n?\s*not os\.environ\.get\("CODE_WIKI_RUN_INTEGRATION"\)'
)

def test_every_gated_test_uses_canonical_pattern() -> None:
    repo_root = Path(__file__).parent.parent.parent.parent
    for path in repo_root.glob("**/tests/integration/test_*.py"):
        text = path.read_text()
        assert _CANONICAL_PATTERN.search(text), f"{path}: non-canonical gate"
```

**Recommendation per CONTEXT.md "test-based form gets free CI hookup":** prefer the pytest form.

---

### MOD `packages/model-adapter/tests/test_loader.py:125-130` (test, extend)

**Current code** (`test_loader.py:125-130`):
```python
def test_load_role_config_synthesizer_limits():
    from model_adapter.loader import load_role_config

    cfg = load_role_config("synthesizer")
    assert cfg["max_tokens"] == 4096
    assert cfg["max_concurrency"] == 3
```

**Pattern to apply (model on `test_load_role_config_librarian_values`, lines 116-122):**
```python
def test_load_role_config_librarian_values():
    from model_adapter.loader import load_role_config

    cfg = load_role_config("librarian")
    assert cfg["model_id"] == HAIKU_ARN     # ← THIS is the shape to copy
    assert cfg["max_tokens"] == 2048
    assert cfg["max_concurrency"] == 5
```

**Locked value per D-13:** `cfg["model_id"] == "qwen.qwen3-32b-v1:0"` (sourced from `packages/model-adapter/src/model_adapter/models.toml:121`).

**Extended test (the one-line addition):**
```python
def test_load_role_config_synthesizer_limits():
    from model_adapter.loader import load_role_config

    cfg = load_role_config("synthesizer")
    assert cfg["model_id"] == "qwen.qwen3-32b-v1:0"   # NEW — locks D-13 default
    assert cfg["max_tokens"] == 4096
    assert cfg["max_concurrency"] == 3
```

(Optionally hoist `"qwen.qwen3-32b-v1:0"` into a module-level constant `QWEN_SYNTHESIZER_ARN` matching the `HAIKU_ARN` pattern on line 28 of `test_bedrock_iam.py`.)

---

### MOD `docs/cancellation.md` §4–§5 (conditional, if spike gate fails)

**Pattern:** Edit-in-place. Current §4 ("Known Limitations (v1.1)") and §5 ("Future Work (v1.2+)") at lines 155 and 195. Refresh with:
- Current blocker status (langchain-aws#663 + aioboto3 milestones)
- **Event-driven** re-eval trigger (D-09): "Re-evaluate when `langchain-aws` cuts a release with #663 merged, OR when `aioboto3` reaches GA / 1.0." Not a calendar date.

---

## Shared Patterns

### Schema-version + OSError-swallow on trace write
**Source:** `pool.py:211-231`
**Apply to:** Every JSONL write site (`trace_io.py`, `query.py:977-996`, any new writer)
```python
record["schema_version"] = 1  # always
try:
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
except OSError as exc:
    logger.warning("Trace write failed (data loss): %s", exc)
# Never raises. Trace failures must not mask successful task results.
```

### usage_metadata None-guard
**Source:** `pool.py:203-209`
**Apply to:** Every site that extracts tokens from a `ChatBedrockConverse` response
```python
tokens_in: int | None = None
tokens_out: int | None = None
if response is not None and hasattr(response, "usage_metadata"):
    meta = response.usage_metadata  # None on ThrottlingException / content filter
    if meta is not None:
        tokens_in = meta.get("input_tokens")
        tokens_out = meta.get("output_tokens")
```

### Canonical CODE_WIKI_RUN_INTEGRATION skip-decorator
**Source:** `agents/code-wiki-agent/tests/conftest.py:19-22`
**Apply to:** Every new gated integration test
```python
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)
```
**Use as decorator:** `@INTEGRATION_GATE` at function level, not inline `pytest.skip(...)` inside the body (the `test_bedrock_iam.py:33-35` anti-pattern).

### Divergence-check module shape
**Source:** `librarian.py:1-97`, `scanner.py:1-88`
**Apply to:** New `code_reader.py` and `synthesizer.py` rule modules
- `from __future__ import annotations`
- Security comment block (T-06-15)
- Private `_check_<name>(output: AgentOutputProxy, vault: Path) -> Verdict` callables — regex + string ops only
- Module-level `<ROLE>_CHECKS: list[DivergenceCheck]` export
- Each `DivergenceCheck` has `id` (`<PREFIX>-NNN-<slug>`), `source_anchor` (path#section in `packages/prompt-sources/`), `severity` (`"hard"` or `"soft"`), `check` (callable)

### Divergence rubric .md shape
**Source:** `rubrics/librarian.md:1-36`
**Apply to:** New `rubrics/code_reader.md` and `rubrics/synthesizer.md`
- 3 HTML comments at top (Source: / Anchor: / Source-commit:)
- `# Divergence Rubric — <Role>` heading
- `## Scoring Criteria` — numbered judge-only rules (`<PREFIX>-005`, `<PREFIX>-006`, ...) each with `(pass/fail)` suffix
- `## Scoring` — 0.0 to 1.0 fraction-of-criteria-passed mapping

### Per-VERIFICATION.md transcript pattern
**Source:** Phase 14 SC#4, Phase 15 D-09
**Apply to:** `16-VERIFICATION.md` (live scanner re-sweep + cancel spike write-up)
- Each SC gets its own `## SC#N: <name>` section
- Live runs captured as fenced markdown blocks
- Spike write-up cites diff against `docs/cancellation.md` if it landed

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `docs/testing.md` (deep content) | config (documentation) | document | `docs/cancellation.md` provides the structural shape (5-section layout) but the *content* about test gates is brand-new. The skill is to mirror the docs/ tone + structure, not to copy text. |

---

## Metadata

**Analog search scope:**
- `packages/subagent-runtime/src/subagent_runtime/` (pool.py is the source-of-truth for trace shape)
- `packages/eval-harness/src/eval_harness/divergence/` (all 4 existing rule modules + 4 rubric .md files)
- `packages/eval-harness/src/eval_harness/two_gate.py` (frozenset extension target)
- `packages/eval-harness/tests/` (meta-test pattern for grep gate option b)
- `agents/code-wiki-agent/tests/integration/` (5 existing gated tests — inventory for testing.md)
- `agents/code-wiki-agent/tests/conftest.py` (canonical INTEGRATION_GATE shape)
- `agents/code-wiki-agent/src/code_wiki_agent/commands/{ingest,query}.py` (refactor targets)
- `packages/model-adapter/tests/test_loader.py` (test extension shape)
- `docs/cancellation.md` + `docs/trace-schema.md` (docs/ sibling shape)
- `scripts/check-brand.sh` (script-form grep gate analog)
- `eval/cases/code_reader_cases.json` + `eval/cases/query_cases.json` (case JSON shape)

**Files scanned:** ~20
**Pattern extraction date:** 2026-05-19
