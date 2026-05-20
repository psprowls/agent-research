---
phase: 8
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - cores/subagent-runtime/src/subagent_runtime/pool.py
  - agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py
autonomous: true
requirements:
  - MCP-10
  - MCP-11
must_haves:
  truths:
    - "When the asyncio task running SubagentPool.run_all is cancelled mid-fan-out, each in-flight _run_one writes a per-item trace record with status: cancelled before re-raising CancelledError."
    - "After CancelledError propagates out of asyncio.gather, run_all writes exactly one terminal trace record with event: batch_cancelled, then re-raises CancelledError so FastMCP's anyio CancelScope sees it."
    - "_write_trace and _write_batch_terminal never raise; OSError on write is logged at WARNING and swallowed (existing AI-SPEC Failure Mode #2 contract is preserved)."
    - "The cancel test runs unconditionally (no GRAPH_WIKI_RUN_INTEGRATION=1 gate) and consumes zero Bedrock cost — model_adapter.loader.make_llm is monkeypatched to a slow stub."
  artifacts:
    - path: "cores/subagent-runtime/src/subagent_runtime/pool.py"
      provides: "_run_one CancelledError branch + run_all outer-cancel handler + _write_batch_terminal helper"
      contains: "async def _write_batch_terminal"
    - path: "agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py"
      provides: "Direct-asyncio cancel-mid-fan-out test asserting per-item cancelled + batch_cancelled records"
      contains: "async def test_cancel_mid_fan_out"
  key_links:
    - from: "_run_one (pool.py)"
      to: "_write_trace (pool.py)"
      via: "status='cancelled' branch"
      pattern: "self\\._write_trace\\([^)]*\"cancelled\""
    - from: "run_all (pool.py)"
      to: "_write_batch_terminal (pool.py)"
      via: "except asyncio.CancelledError around gather"
      pattern: "_write_batch_terminal"
    - from: "test_mcp_cancel.py"
      to: "model_adapter.loader.make_llm"
      via: "monkeypatch.setattr"
      pattern: "model_adapter\\.loader\\.make_llm"
---

<objective>
Wire MCP cancellation through `SubagentPool` so in-flight subagent tasks unwind cleanly with structured trace records, then prove it with a deterministic in-process asyncio cancel test that uses a stubbed LLM (zero Bedrock cost).

Purpose: closes MCP-10 (in-flight pool invocations terminate cleanly, traces close with a `cancelled` terminal event) and MCP-11 (automated cancel test at the MCP transport boundary, gate-consistent with v1.0). This is the precondition for Plan 02 (which shares `pool.py`) and Plan 03 (which documents the exact trace shapes emitted here).

Output: modified `cores/subagent-runtime/src/subagent_runtime/pool.py` with a `CancelledError` branch in `_run_one`, a wrapped `asyncio.gather` in `run_all`, and a new `_write_batch_terminal` helper; plus a new `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py` that drives the cancel chain end-to-end without subprocess overhead.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/08-host-reliability/08-CONTEXT.md
@.planning/phases/08-host-reliability/08-RESEARCH.md
@.planning/phases/08-host-reliability/08-PATTERNS.md
@.planning/phases/08-host-reliability/08-VALIDATION.md
@cores/subagent-runtime/src/subagent_runtime/pool.py
@agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py

<interfaces>
<!-- Contracts the executor needs. All extracted from codebase; executor should use these directly. -->

From cores/subagent-runtime/src/subagent_runtime/pool.py (current state — see PATTERNS.md lines 315-392 for exact line refs):

- `_run_one(item)` currently has shape: `try: ... result = await task(item); self._write_trace(..., "success", ...); return (item, result) except Exception as exc: self._write_trace(..., "error", ...); return PerItemError(item=item, exception=exc)` at lines 141-146. NEW `except asyncio.CancelledError` branch goes BEFORE the existing `except Exception` block (Pitfall 1: CancelledError inherits from BaseException, not Exception).
- `run_all(...)` currently calls `raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)` at line 149. Wrap this single call in `try / except asyncio.CancelledError`.
- `_write_trace` at lines 162-210 — DO NOT MODIFY. Its existing `None`-guard on lines 185-189 and `_compute_cost_usd(None)` at 224-225 already handle `response=None` correctly for the cancelled status.
- `_write_trace` never-raises skeleton at lines 206-210 is the template for `_write_batch_terminal`:
  ```
  try:
      with path.open("a") as f:
          f.write(json.dumps(record) + "\n")
  except OSError as exc:
      logger.warning("...: %s", exc)
  ```

From agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py:
- Module-level docstring style (lines 2-12): `"""<description>. Requirements covered: <ids>."""`
- `from __future__ import annotations` header is mandatory.
- `asyncio_mode = "auto"` is set in `agents/graph-wiki-agent/pyproject.toml` → async test functions take NO `@pytest.mark.asyncio` decorator.
- The cancel test should sit alongside this file but use direct-asyncio (no subprocess) — see RESEARCH.md §"Open Questions" #4 and §"Test File Layout Recommendation".

From agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:
- `run_query(query: str, vault_path: Path | str, top_k: int) -> ...` is the fan-out entry point that the cancel test will interrupt (RESEARCH.md Q5).

From model_adapter package:
- The correct monkeypatch target is `model_adapter.loader.make_llm` (NOT `model_adapter.factory.make_chat_model` — D-09 has a stale path; RESEARCH.md confirms `model_adapter.loader.make_llm` is the actual function).

Trace record shapes to emit (from CONTEXT.md D-06; these are the assertion targets in the test):

Per-item cancelled record (written by `_run_one` via existing `_write_trace`):
```
{"role": "...", "model_id": "...", "item_id": "...", "status": "cancelled",
 "latency_ms": <t0_to_cancel_receipt>, "tokens_in": null, "tokens_out": null,
 "cost_usd": null, "timestamp": "..."}
```

Batch terminal summary (written by NEW `_write_batch_terminal`):
```
{"role": "...", "model_id": "...", "event": "batch_cancelled",
 "items_total": N, "items_completed": K, "items_cancelled": M,
 "wall_clock_ms": <t0_to_cancel_complete>, "timestamp": "..."}
```

Per D-07, `event` is the discriminator — per-item records have no `event` key.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add CancelledError branches and _write_batch_terminal to pool.py</name>
  <files>cores/subagent-runtime/src/subagent_runtime/pool.py</files>
  <behavior>
    - When the asyncio task running `run_all` is cancelled mid-`gather`, every `_run_one` that was awaiting a slow `task(item)` MUST hit a new `except asyncio.CancelledError` branch placed BEFORE the existing `except Exception` block, call `self._write_trace(trace_file, role, model_id, item, "cancelled", latency_ms, None)`, then re-raise `CancelledError`.
    - `run_all` MUST wrap the single `asyncio.gather(...)` call (current line 149) in `try: ... except asyncio.CancelledError:` that calls `self._write_batch_terminal(...)` with `items_total=len(items)`, `items_completed=0`, `items_cancelled=len(items)` (conservative upper bound per RESEARCH.md Q6 counting note), `wall_clock_ms=int((time.monotonic()-batch_t0)*1000)`, then re-raises CancelledError.
    - `_write_batch_terminal` MUST emit a single JSONL line whose fields exactly match the `event: batch_cancelled` shape in `<interfaces>`, with `timestamp` formatted via `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())` (matches existing `_write_trace` timestamp format).
    - `_write_batch_terminal` MUST NEVER raise — wrap the file write in `try / except OSError as exc: logger.warning("Batch terminal trace write failed: %s", exc)` (verbatim contract from `_write_trace` lines 206-210).
    - Existing `_write_trace` is NOT modified — its `None` guard already handles `response=None` for cancelled (RESEARCH.md Q7).
    - Success path and existing `except Exception` error path remain byte-identical (Karpathy surgical-change rule).
  </behavior>
  <action>
Modify `cores/subagent-runtime/src/subagent_runtime/pool.py` exactly as specified in PATTERNS.md §"cores/subagent-runtime/src/subagent_runtime/pool.py" (lines 315-392). Three discrete edits:

(1) In `_run_one`, INSERT a new `except asyncio.CancelledError:` block immediately BEFORE the existing `except Exception as exc:` block at lines 141-146. The new block computes `latency_ms = int((time.monotonic() - t0) * 1000)`, calls `self._write_trace(trace_file, role, model_id, item, "cancelled", latency_ms, None)` (no `error=` kwarg — that's only for the error branch), then `raise` (bare re-raise). Per Pitfall 1 in RESEARCH.md, ordering is critical: `CancelledError` inherits from `BaseException` and would NOT be caught by `except Exception`, but explicit ordering documents intent and survives any future widening of the Exception handler.

(2) In `run_all`, REPLACE the bare `raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)` at line 149 with a try-wrapped form per PATTERNS.md lines 339-357: record `batch_t0 = time.monotonic()` immediately before the try, then `try: raw = await asyncio.gather(...)` exactly as before, then `except asyncio.CancelledError: wall_ms = int((time.monotonic() - batch_t0) * 1000); self._write_batch_terminal(trace_file, role, model_id, items_total=len(items), items_completed=0, items_cancelled=len(items), wall_clock_ms=wall_ms); raise`. The bare `raise` is mandatory — FastMCP's anyio CancelScope expects to see the CancelledError propagate (Pitfall 3, Invariant 3).

(3) ADD a new method `_write_batch_terminal` on `SubagentPool`, copying the never-raises skeleton from `_write_trace` lines 206-210. Signature per PATTERNS.md lines 362-390: `def _write_batch_terminal(self, path: Path, role: str, model_id: str, *, items_total: int, items_completed: int, items_cancelled: int, wall_clock_ms: int) -> None`. Body builds the record dict with keys exactly matching `<interfaces>` (role, model_id, event="batch_cancelled", items_total, items_completed, items_cancelled, wall_clock_ms, timestamp), then writes a single JSON line in a `try / except OSError as exc: logger.warning("Batch terminal trace write failed: %s", exc)` wrapper.

Do not touch `_write_trace`, the success branch, the existing error branch, or any imports beyond what's already in pool.py (asyncio, time, json, logging are all already imported — verify before adding any new import; do not import what is already present).

Do NOT add `print()` anywhere — `_StdoutGuard` in `server.py` raises on stray stdout writes (Pitfall 6). All logging stays on the existing module `logger`.
  </action>
  <verify>
    <automated>uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -x -k "not e2e and not integration"</automated>
    Then (after Task 2 is also complete): `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py -x` passes.
    Quick syntactic check: `uv run python -c "from subagent_runtime.pool import SubagentPool; p = SubagentPool.__dict__; assert '_write_batch_terminal' in p, 'helper missing'"`.
  </verify>
  <done>
    `_run_one` has an `except asyncio.CancelledError` branch BEFORE `except Exception`, writes `status: "cancelled"` via `_write_trace`, re-raises.
    `run_all` wraps `asyncio.gather` in `try / except asyncio.CancelledError`, writes the terminal summary via `_write_batch_terminal`, re-raises.
    `_write_batch_terminal` exists, emits a JSONL record with `event: batch_cancelled`, never raises (OSError logged at WARNING).
    Existing tests still pass (`uv run --package graph-wiki-agent pytest -x -k "not e2e and not integration"`).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Direct-asyncio cancel-mid-fan-out test (test_mcp_cancel.py)</name>
  <files>agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py</files>
  <behavior>
    - `test_cancel_mid_fan_out(tmp_path, monkeypatch)` is an async test function (no `@pytest.mark.asyncio` decorator — `asyncio_mode = "auto"` per CLAUDE.md / PATTERNS.md §"pytest asyncio test functions").
    - Test MUST run unconditionally — NO `INTEGRATION_GATE` skip-marker, NO `GRAPH_WIKI_RUN_INTEGRATION` check (D-10).
    - Monkeypatch `model_adapter.loader.make_llm` (the actual function — D-09's `make_chat_model` path is stale; RESEARCH.md Q4 confirms `loader.make_llm`) to return a stub whose `ainvoke` does `await asyncio.sleep(N)` where N≈2-3s, then returns an `AIMessage`-shaped object with `.usage_metadata = None` so the existing `_write_trace` guards do not blow up on the success path.
    - Test sequence (RESEARCH.md "Simpler alternative" + PATTERNS.md cancel core pattern):
      (1) Patch `model_adapter.loader.make_llm` before any graph-wiki-agent import that resolves it.
      (2) Seed a minimal vault under `tmp_path` (init via `run_wiki_init` or write the `.graph-wiki/` skeleton + 3 pages inline — whichever is shorter; do not call the MCP layer).
      (3) `task = asyncio.ensure_future(run_query(query="What is alpha?", vault_path=tmp_path, top_k=3))`.
      (4) `await asyncio.sleep(0)` to yield once and let `asyncio.gather` start (race control per RESEARCH.md Pattern 5 — direct-asyncio variant; `report_progress` is not observable in this mode).
      (5) `task.cancel()`.
      (6) `with pytest.raises(asyncio.CancelledError): await task` (the outer cancel MUST propagate — Invariant 3).
    - Assertions on the trace file under `tmp_path / ".code-wiki" / "traces"` (or wherever `SubagentPool` writes by default — read pool.py to confirm path; if traces land elsewhere given the test fixture, point the test at the actual path):
      (a) At least one trace line has `"status": "cancelled"` (per-item record exists).
      (b) Exactly one trace line has `"event": "batch_cancelled"` (terminal record exists, written once).
      (c) The `event: batch_cancelled` line is the LAST line in the file (Invariant 5).
      (d) Cancelled lines do NOT contain an `event` key (D-07 discriminator).
  </behavior>
  <action>
Create `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py` following PATTERNS.md §"agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py" lines 24-89.

Header structure:
- `from __future__ import annotations` (mandatory; PATTERNS.md §"Shared Patterns")
- Module docstring: `"""Cancel-mid-fan-out test (direct asyncio; no subprocess). Requirements covered: MCP-10, MCP-11."""`
- Imports: `asyncio`, `json`, `pathlib.Path`, `unittest.mock.AsyncMock`, `pytest`. Then `from graph_wiki_agent.commands.query import run_query` (or the correct import path — verify against the actual file location).

Stub model construction:
- Define an async function `_slow_ainvoke(*args, **kwargs)` that does `await asyncio.sleep(3)` then returns an object with `.usage_metadata = None` and `.content = "stub"` (look at how `_write_trace` reads `response` to confirm the minimum shape — pool.py lines 185-189 guard on `response is not None and hasattr(response, "usage_metadata")`, so a `MagicMock(usage_metadata=None, content="stub")` is sufficient).
- Build the fake llm: `fake_llm = MagicMock(); fake_llm.ainvoke = AsyncMock(side_effect=_slow_ainvoke)`.
- Apply: `monkeypatch.setattr("model_adapter.loader.make_llm", lambda *a, **kw: fake_llm)`.

Vault seeding (Claude's Discretion per CONTEXT.md):
- Use the smallest fixture that gets `run_query` into the fan-out: typically `.graph-wiki/config.toml` (or whatever `run_query` resolves) plus 3 placeholder pages under `tmp_path/wiki/`. If `run_query` requires a built bm25 index, call the appropriate index-build helper inline (look at the existing `tests/integration/test_query.py` or unit tests for the pattern — do not invent a new harness).
- If seeding is more than ~20 lines, extract to a `_seed_minimal_vault(tmp_path)` helper at module scope.

Cancel logic verbatim shape from PATTERNS.md lines 56-86 — substitute the actual `run_query` signature and the actual trace-file path you confirmed from `pool.py`.

Trace assertions:
- Locate the trace file: `trace_files = list((tmp_path / ".code-wiki" / "traces").glob("*.jsonl"))` (verify path against pool.py — if `SubagentPool` accepts an explicit `trace_file` arg, pass `tmp_path / "trace.jsonl"` and read it directly; simpler).
- Parse: `lines = [json.loads(l) for l in trace_files[0].read_text().splitlines() if l.strip()]`.
- Assert per-item: `cancelled = [l for l in lines if l.get("status") == "cancelled"]; assert cancelled, "no per-item cancelled records"`.
- Assert batch: `batch = [l for l in lines if l.get("event") == "batch_cancelled"]; assert len(batch) == 1, f"expected exactly one batch_cancelled record, got {len(batch)}"`.
- Assert ordering (Invariant 5): `assert lines[-1].get("event") == "batch_cancelled"`.
- Assert discriminator (D-07): `assert all("event" not in l for l in cancelled)`.

Do NOT add an `INTEGRATION_GATE` decorator (D-10 — runs unconditionally).
Do NOT use `subprocess` (subprocess monkeypatching does not work — Pitfall 2).
Do NOT add `@pytest.mark.asyncio` (asyncio_mode = "auto").
  </action>
  <verify>
    <automated>uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py -x -v</automated>
  </verify>
  <done>
    `test_mcp_cancel.py` exists at the specified path with one async test function `test_cancel_mid_fan_out`.
    Test runs in <10s (per VALIDATION.md sampling-rate target) and passes without `GRAPH_WIKI_RUN_INTEGRATION=1`.
    Test asserts: (a) ≥1 per-item `status: cancelled` record, (b) exactly one `event: batch_cancelled` record, (c) terminal record is last line, (d) per-item records have no `event` key.
    Zero Bedrock calls during the test (verifiable by absence of AWS API activity / by the stub being the only LLM path).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

This phase introduces no new trust boundaries. The MCP transport boundary, the FastMCP→anyio→asyncio chain, and the SubagentPool fan-out path are all pre-existing; this plan only widens an existing `except` clause and adds one new internal helper. The cancel test is in-process and exercises no external surface.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-01-N1 | (none) | pool.py cancel branch | accept | No new vector — additive trace writes use the same never-raises OSError contract as `_write_trace` (RESEARCH.md §"Security Domain"). Phase 1–5 ASVS L1 coverage on the MCP transport surface is unchanged. |

Per RESEARCH.md §"Security Domain": "This phase adds no new user-facing input surfaces, no new credentials handling, and no new network endpoints. The subprocess harness is test-only. No ASVS categories apply beyond what Phase 1–5 already covered. Security enforcement: pass-through (no new vectors introduced)."

No package installs in this plan — Package Legitimacy Audit (N/A; RESEARCH.md §"Package Legitimacy Audit" explicitly confirms no new deps).
</threat_model>

<verification>
After both tasks land:

```bash
# Cancel test (fast, no Bedrock; required green for per-commit sampling per VALIDATION.md)
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py -x -v

# Full non-integration suite (no regressions in existing _write_trace / _run_one / run_all paths)
uv run --package graph-wiki-agent pytest -x -k "not e2e"

# subagent-runtime own tests (regression on the modified pool.py)
uv run --package subagent-runtime pytest -x
```

All three commands must exit 0.
</verification>

<success_criteria>
- `pool.py` modifications complete: `_run_one` has explicit `except asyncio.CancelledError` branch BEFORE `except Exception`; `run_all` wraps gather; `_write_batch_terminal` exists and follows never-raises contract.
- `test_mcp_cancel.py` exists, passes in <10s, runs without `GRAPH_WIKI_RUN_INTEGRATION=1`, asserts both record shapes (per-item `status: cancelled` and terminal `event: batch_cancelled`) and the ordering invariant.
- Zero regressions in existing subagent-runtime and graph-wiki-agent non-integration test suites.
- MCP-10 and MCP-11 requirement IDs satisfied (see VALIDATION.md row 8-01-01 through 8-01-04).
- Plan 02 (which also touches `pool.py` indirectly via shared `files_modified`) and Plan 03 (which documents the trace shapes emitted here) are now unblocked.
</success_criteria>

<output>
Create `.planning/phases/08-host-reliability/08-01-SUMMARY.md` capturing: exact diff summary of pool.py (line ranges before/after), the final test file path, the cancel-test wall-clock time observed locally, any deviations from the planned trace-file path (because pool.py wrote traces elsewhere than the assumed `.graph-wiki/traces/` path), and confirmation that `_write_batch_terminal` was used by no other call site (i.e., it is reachable ONLY from the new `run_all` except branch).
</output>
