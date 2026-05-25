---
phase: 8
plan: 02
type: execute
wave: 2
depends_on:
  - 08-01
files_modified:
  - agents/graph-wiki-agent/src/graph_wiki_mcp/server.py
  - agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py
  - agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py
autonomous: true
requirements:
  - DACLI-01
  - DACLI-02
  - DACLI-03
must_haves:
  truths:
    - "WikiScanInput accepts an explicit repo_path string; wiki_scan tool passes it through to run_scan so MCP-layer callers can scope the scan target (preventing the test from walking the live agent-research workspace)."
    - "A single end-to-end integration test launches graph-wiki-mcp as a stdio subprocess via uv run --package graph-wiki-agent graph-wiki-mcp and drives JSON-RPC over stdin/stdout (DACLI-01)."
    - "The test exercises all six shipped tools — wiki_init, wiki_scan, wiki_ingest, wiki_query, wiki_lint, wiki_log — sequentially against a fresh tmp_path vault and asserts non-error JSON-RPC responses for each (DACLI-02)."
    - "The test is gated by GRAPH_WIKI_RUN_INTEGRATION=1 because 4/6 tools call real Bedrock; the gate matches v1.0 integration-test conventions (DACLI-03)."
  artifacts:
    - path: "agents/graph-wiki-agent/src/graph_wiki_mcp/server.py"
      provides: "WikiScanInput.repo_path field + wiki_scan handler passthrough"
      contains: "repo_path: str = Field("
    - path: "agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py"
      provides: "Schema round-trip + default-value tests for WikiScanInput.repo_path"
      contains: "def test_wiki_scan_input_accepts_repo_path"
    - path: "agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py"
      provides: "INTEGRATION_GATE-gated subprocess JSON-RPC test exercising all 6 tools"
      contains: "def test_all_six_tools_end_to_end"
  key_links:
    - from: "WikiScanInput.repo_path"
      to: "run_scan(repo_path=...)"
      via: "wiki_scan handler argument plumbing"
      pattern: "repo_path=Path\\(input\\.repo_path\\)"
    - from: "test_mcp_e2e.py"
      to: "graph-wiki-mcp subprocess"
      via: "subprocess.Popen(['uv', 'run', '--package', 'graph-wiki-agent', 'graph-wiki-mcp'])"
      pattern: "graph-wiki-mcp"
    - from: "test_mcp_e2e.py wiki_scan call"
      to: "tmp_path"
      via: "repo_path arg in tools/call arguments.input"
      pattern: "\"repo_path\": str\\(tmp_path"
---

<objective>
Add the missing `repo_path` field to `WikiScanInput` (required precondition — without it the E2E test would scan the live agent-research workspace per RESEARCH.md Pitfall 4), then write a single sequential E2E integration test that launches `graph-wiki-mcp` as a stdio subprocess and exercises all six shipped MCP tools against a fresh `tmp_path` vault.

Purpose: closes DACLI-01 (subprocess launch from spec-conformant host), DACLI-02 (all 6 tools exercised with non-error outcomes), and DACLI-03 (`GRAPH_WIKI_RUN_INTEGRATION=1` opt-in gate). This is the v1.1 proof that every shipped tool round-trips correctly through the real FastMCP stdio transport — not just unit-tested in isolation.

Output: modified `server.py` (one new field + one handler line); new `tests/unit/test_wiki_scan_input.py` (schema unit test, ungated); new `tests/integration/test_mcp_e2e.py` (single sequential test function, `INTEGRATION_GATE`-gated). Depends on Plan 01 only because both plans modify files in the same package and the cancel infrastructure should land first so any regression surfaced by the E2E test points to a clean baseline.
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
@agents/graph-wiki-agent/src/graph_wiki_mcp/server.py
@agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py
@agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py
@agents/graph-wiki-agent/tests/conftest.py

<interfaces>
<!-- Contracts the executor needs. All extracted from codebase. -->

From agents/graph-wiki-agent/src/graph_wiki_mcp/server.py:
- `WikiScanInput` at lines 242-245 currently exposes only: `vault_path: str = Field("", ...)`, `no_file_map: bool = Field(False, ...)`, `max_depth: int = Field(3, ...)`. It has NO repo_path field — this is the gap (RESEARCH.md Pitfall 4 + Pattern Map self-analog).
- `wiki_scan` handler at lines 261-284 currently calls `run_scan(vault_path=vault, no_file_map=input.no_file_map, max_depth=input.max_depth)`.
- `run_scan` (from `graph_wiki_agent.commands.scan`) already accepts `repo_path: Path | None = None` (RESEARCH.md confirms — the override exists; only the MCP-layer plumbing is missing).
- `wiki_query` at line 125 uses the `Path(...) if X else None` pattern: `vault_path=Path(input.vault_path) if input.vault_path else None` — copy this idiom for repo_path.

From agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py (PATTERNS.md lines 99-204):
- `_run_server(payload_objs)` helper at lines 63-78: spawns subprocess via `["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-mcp"]`, feeds JSON-RPC over stdin, returns `(stdout, stderr)` decoded strings. 15s communicate timeout. Copy verbatim.
- `_send_initialize()` at lines 24-32 returns `{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "0.0.1"}}}`. Copy verbatim.
- `_send_initialized_notification()` at lines 35-41 returns `{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}`. Copy verbatim.
- `tools/call` payload shape at lines 44-60 — IMPORTANT: arguments are nested under the Python parameter name `"input"` (Pydantic-typed params; flat shorthand does NOT work — verified against mcp 1.27.1, PATTERNS.md line 163-164).
- Response extraction pattern at lines 123-135: parse stdout lines, `next((r for r in responses if r.get("id") == request_id), None)`, assert `"result" in tool_resp` and `tool_resp["result"].get("isError") is False`.

From agents/graph-wiki-agent/tests/conftest.py lines 19-23:
- `INTEGRATION_GATE = pytest.mark.skipif(not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"), reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations")` — canonical definition. Import via `from tests.conftest import INTEGRATION_GATE` OR redefine locally (PATTERNS.md notes either is fine).

From agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py (PATTERNS.md lines 234-263):
- Test function signature style: `def test_wiki_X_input_default_Y_is_Z() -> None:` with one-line docstring citing the requirement ID in parentheses.
- Import-inside-test pattern (lines 31-37): `from graph_wiki_mcp.server import WikiScanInput; inp = WikiScanInput(); assert inp.X == expected`.

Six tool input shapes (from server.py + RESEARCH.md Q9; Claude's Discretion per CONTEXT.md — concrete values are the planner's call):

1. `wiki_init`: `{"topic": "test repo", "tool": "claude-code", "vault_path": str(tmp_path / "wiki")}`
2. `wiki_scan`: `{"vault_path": str(tmp_path / "wiki"), "repo_path": str(tmp_path), "max_depth": 2}` ← uses the NEW field
3. `wiki_ingest`: e.g. `{"op": "source", "path": str(tmp_path / "sample.py"), "vault_path": str(tmp_path / "wiki")}` — verify WikiIngestInput shape against server.py before finalizing
4. `wiki_query`: `{"query": "What is alpha?", "vault_path": str(tmp_path / "wiki"), "top_k": 3}`
5. `wiki_lint`: `{"vault_path": str(tmp_path / "wiki")}` — defaults are fine
6. `wiki_log`: `{"op": "note", "title": "e2e test entry", "detail": "smoke", "vault_path": str(tmp_path / "wiki")}`

Per RESEARCH.md §"6-Tool E2E Test: CWD Discipline Detail": to make `wiki_scan` produce something interesting under `tmp_path`, write a minimal `pyproject.toml` at `tmp_path` listing one fake workspace package. Without it, scan returns `added=[], updated=[], deleted=[]` — still non-error (acceptable for DACLI-02), but a single pyproject seed gives more confidence the scanner actually walked something.

Seed layout (Claude's Discretion; from RESEARCH.md Q9):
```
tmp_path/
  pyproject.toml          # minimal — names one fake workspace package "alpha"
  packages/alpha/         # contains sample.py with a docstring + one symbol
    pyproject.toml
    src/alpha/__init__.py
    src/alpha/sample.py
  wiki/                   # created by wiki_init
    .graph-wiki/
    index.md
    packages/alpha/alpha.md      # seeded post-init: frontmatter + body
    concepts/architecture.md     # body links [[packages/alpha/alpha]]
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add WikiScanInput.repo_path + unit test</name>
  <files>agents/graph-wiki-agent/src/graph_wiki_mcp/server.py, agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py</files>
  <behavior>
    - `WikiScanInput` exposes a new `repo_path: str = Field("", description="Override repo root for scanner (default: resolved from vault_path). Use for testing.")` field (PATTERNS.md lines 416-425).
    - Default round-trip: `WikiScanInput()` has `inp.repo_path == ""`.
    - Explicit round-trip: `WikiScanInput(repo_path="/tmp/test-repo")` has `inp.repo_path == "/tmp/test-repo"`.
    - The `wiki_scan` handler passes `repo_path=Path(input.repo_path).resolve() if input.repo_path else None` to `run_scan(...)` — exactly the `Path(...) if X else None` idiom used at server.py lines 125, 169, 215 (PATTERNS.md line 446).
    - Existing `WikiScanInput` fields (`vault_path`, `no_file_map`, `max_depth`) are unchanged — Karpathy surgical-change rule.
    - Existing `wiki_scan` handler logic is unchanged except for the added `repo_path=` kwarg.
  </behavior>
  <action>
**Part A — modify `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py`** (PATTERNS.md §"agents/graph-wiki-agent/src/graph_wiki_mcp/server.py" lines 396-446):

(1) Add `repo_path: str = Field("", description="Override repo root for scanner (default: resolved from vault_path). Use for testing.")` to `WikiScanInput` at lines 242-245. Append as the LAST field. Match the Field-with-description style used by sibling fields and the `WikiLogInput` pattern at lines 150-154.

(2) Modify the `run_scan(...)` call in the `wiki_scan` handler at lines 261-284. Add ONE new kwarg: `repo_path=Path(input.repo_path).resolve() if input.repo_path else None`. Place it after `max_depth=input.max_depth,`. Do not reorder existing kwargs. Do not modify any other line in the handler.

(3) `Path` is already imported (verify at top of server.py — it is per PATTERNS.md confirmation). Do NOT add an import that already exists.

**Part B — create `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py`** (PATTERNS.md §"agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py" lines 230-287):

Header:
```
from __future__ import annotations

"""Schema unit tests for WikiScanInput.repo_path field.

Requirements covered: DACLI-02 (precondition).
"""

import pytest
```

Four test functions (verbatim PATTERNS.md shape, module-level imports of `WikiScanInput` inside each test per the prevailing style at `test_mcp_new_tools.py` lines 31-50):

```
def test_wiki_scan_input_default_repo_path_is_empty() -> None:
    """WikiScanInput defaults to repo_path='' (no override — resolves from vault_path) (DACLI-02)."""
    from graph_wiki_mcp.server import WikiScanInput
    inp = WikiScanInput()
    assert inp.repo_path == ""

def test_wiki_scan_input_accepts_repo_path() -> None:
    """WikiScanInput accepts an explicit repo_path string (DACLI-02)."""
    from graph_wiki_mcp.server import WikiScanInput
    inp = WikiScanInput(repo_path="/tmp/test-repo")
    assert inp.repo_path == "/tmp/test-repo"

def test_wiki_scan_input_preserves_existing_defaults() -> None:
    """Adding repo_path does not regress existing vault_path / no_file_map / max_depth defaults (regression guard)."""
    from graph_wiki_mcp.server import WikiScanInput
    inp = WikiScanInput()
    assert inp.vault_path == ""
    assert inp.no_file_map is False
    assert inp.max_depth == 3
```

Do NOT add `@pytest.mark.asyncio` — these are sync tests.
Do NOT add an `INTEGRATION_GATE` — these are pure schema tests, no Bedrock.
  </action>
  <verify>
    <automated>uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py -x -v</automated>
    Plus regression check: `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/ -x` (all unit tests including existing `test_mcp_new_tools.py` still pass).
  </verify>
  <done>
    `WikiScanInput.repo_path` field exists with empty-string default; `wiki_scan` handler passes it through to `run_scan` using the `Path(...) if X else None` idiom.
    `test_wiki_scan_input.py` exists with three passing tests covering default, explicit-value, and regression-guard.
    Existing unit tests (`test_mcp_new_tools.py`, etc.) still pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Six-tool subprocess E2E test (test_mcp_e2e.py)</name>
  <files>agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py</files>
  <behavior>
    - One test function `test_all_six_tools_end_to_end(tmp_path)`, decorated with `INTEGRATION_GATE` (DACLI-03; D-14 — single sequential function, not six independent tests).
    - Launches `graph-wiki-mcp` via the existing `_run_server` helper (copied from `test_mcp_stdio.py`) — single subprocess, single stdin pipeline.
    - Drives JSON-RPC initialize → initialized → six `tools/call` payloads in order: `wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log` (D-12 sequence; natural dependency chain).
    - Each tool call uses an incrementing integer `id` (2, 3, 4, 5, 6, 7 — id 1 is reserved for initialize).
    - For each tool response, asserts: (a) response present with the expected `id`, (b) `"result"` key present, (c) `tool_resp["result"].get("isError") is False`.
    - The `wiki_scan` payload MUST include `"repo_path": str(tmp_path)` (DACLI-02 / D-13 — without this, scan walks the live agent-research workspace per RESEARCH.md Pitfall 4; this is the entire reason Task 1 exists).
    - Test seeds `tmp_path` with a minimal pyproject + one source file BEFORE launching the subprocess so `wiki_scan` and `wiki_ingest` have material to process.
    - `wiki_init` is the FIRST tool call (creates `.graph-wiki/`); subsequent tools operate on the same vault (D-12 — fresh tmp_path, init + inline seed).
    - No `notifications/cancelled` in this test — cancel is Plan 01's scope.
  </behavior>
  <action>
Create `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` following PATTERNS.md §"agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py" lines 93-227.

Header (PATTERNS.md §"Shared Patterns"):
```
from __future__ import annotations

"""End-to-end test launching graph-wiki-mcp as a stdio subprocess and exercising all six MCP tools.

Requirements covered: DACLI-01, DACLI-02, DACLI-03.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
```

`INTEGRATION_GATE` — redefine locally (PATTERNS.md notes either import-from-conftest or local redefinition is fine; local redef matches the existing `test_mcp_stdio.py` convention at lines 141-144):
```
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)
```

Copy helpers VERBATIM from `test_mcp_stdio.py`:
- `_run_server(payload_objs: list[dict]) -> tuple[str, str]` from lines 63-78 (PATTERNS.md lines 126-141)
- `_send_initialize() -> dict` from lines 24-32 (PATTERNS.md lines 146-156)
- `_send_initialized_notification() -> dict` from lines 35-41 (PATTERNS.md lines 158-159)

Add six new payload builders matching the `arguments: {input: {...}}` nesting shape (PATTERNS.md lines 166-194 demonstrate the pattern for `wiki_init` and `wiki_scan`). Use the input shapes listed in the `<interfaces>` block above. Each builder takes `(request_id: int, ...)` and returns the full `tools/call` dict.

Seed helper (Claude's Discretion — keep it ≤30 lines):
```
def _seed_minimal_workspace(tmp_path: Path) -> Path:
    """Seed tmp_path with a minimal uv workspace + one source file so wiki_scan/wiki_ingest have material."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "e2e-test-root"\nversion = "0.0.1"\n'
        '[tool.uv.workspace]\nmembers = ["packages/alpha"]\n'
    )
    pkg = tmp_path / "packages" / "alpha"
    (pkg / "src" / "alpha").mkdir(parents=True)
    (pkg / "pyproject.toml").write_text('[project]\nname = "alpha"\nversion = "0.0.1"\n')
    sample = pkg / "src" / "alpha" / "sample.py"
    sample.write_text('"""Alpha sample module."""\n\ndef hello() -> str:\n    return "alpha"\n')
    return sample
```

The test function:
```
@INTEGRATION_GATE
def test_all_six_tools_end_to_end(tmp_path: Path) -> None:
    """All six MCP tools round-trip through the real stdio subprocess against a seeded tmp_path vault.

    Covers DACLI-01 (subprocess launch), DACLI-02 (all 6 tools, non-error), DACLI-03 (gated).
    """
    sample = _seed_minimal_workspace(tmp_path)
    vault = tmp_path / "wiki"

    payloads = [
        _send_initialize(),
        _send_initialized_notification(),
        _send_wiki_init(2, str(vault)),
        _send_wiki_scan(3, str(vault), str(tmp_path)),         # repo_path = tmp_path (NEW FIELD)
        _send_wiki_ingest(4, str(sample), str(vault)),
        _send_wiki_query(5, "What is alpha?", str(vault)),
        _send_wiki_lint(6, str(vault)),
        _send_wiki_log(7, str(vault)),
    ]

    stdout, stderr = _run_server(payloads)
    responses = [json.loads(line) for line in stdout.splitlines() if line.strip() and json.loads(line).get("id") is not None]

    for req_id in (2, 3, 4, 5, 6, 7):
        resp = next((r for r in responses if r.get("id") == req_id), None)
        assert resp is not None, f"No response for id={req_id}.\nstderr tail: {stderr[-500:]}"
        assert "result" in resp, f"id={req_id}: missing result: {resp!r}"
        assert resp["result"].get("isError") is False, (
            f"id={req_id} flagged isError=True. result={resp['result']!r}\nstderr tail: {stderr[-500:]}"
        )
```

Notes for the executor:
- The `_run_server` 15s timeout from `test_mcp_stdio.py` is too short for the full 6-tool flow (4 Bedrock calls). BUMP the timeout in this test's `_run_server` to ~180s (matches VALIDATION.md §"Estimated runtime" — 60-180s for full integration). Adjust the helper inline or copy a renamed version `_run_server_long` with the bumped timeout. Do not touch the original helper in `test_mcp_stdio.py`.
- Stdout may interleave `notifications/progress` lines (no `id` field) with response lines (have `id`). The filter `json.loads(line).get("id") is not None` (above) excludes notifications.
- Verify exact `WikiIngestInput` shape from `server.py` before finalizing the `_send_wiki_ingest` payload. The `op: "source"` field name and the `path` parameter name are assumed from RESEARCH.md Q9 / server.py reading; correct against the real schema if it differs.
- If `wiki_query` requires a built bm25 index that `wiki_init` does not produce, either (a) call `wiki_ingest` first against a seed page that builds the index, or (b) extend the seed helper to write `.graph-wiki/index/` artifacts that `run_query` can read. Resolve by reading `commands/query.py` once before writing the test.
- All `pyproject.toml` content above is illustrative — match whatever minimum `discover_workspaces` actually accepts (verify against `commands/scan.py` if scan returns zero workspaces).

Do NOT use `notifications/cancelled` — that path is Plan 01's scope.
Do NOT split into multiple test functions — D-14 mandates one sequential test (subprocess-spawn cost amortization).
Do NOT wait for a JSON-RPC response on the `notifications/initialized` notification — notifications have no response per the MCP spec (Pitfall 5 in RESEARCH.md is for the cancel case, but the no-response-for-notifications rule applies universally).
  </action>
  <verify>
    <automated>GRAPH_WIKI_RUN_INTEGRATION=1 uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py -x -v</automated>
    Skip-when-ungated check: `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py -x -v` (must show 1 skipped, 0 failed).
  </verify>
  <done>
    `test_mcp_e2e.py` exists with one `INTEGRATION_GATE`-decorated test function.
    Ungated `pytest` run shows the test as SKIPPED (DACLI-03 gate works).
    `GRAPH_WIKI_RUN_INTEGRATION=1` run completes within ~180s and all six tools return non-error responses.
    `wiki_scan` walks `tmp_path` (NOT the agent-research workspace) — confirmed by absence of monorepo package names in scan output.
    Estimated cost per run: ≤$0.01 (RESEARCH.md §"Bedrock Cost Estimate" — ~$0.003-0.01).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

This phase introduces no new trust boundaries. The MCP stdio transport, subprocess spawn surface, and FastMCP tool handlers are all pre-existing surfaces with Phase 1–5 ASVS L1 coverage. The new `repo_path` field is a planner-controlled override consumed only by `run_scan` (already pathlib-resolved per the existing `vault_path` pattern). The E2E test runs only when the developer explicitly opts in via `GRAPH_WIKI_RUN_INTEGRATION=1`.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-02-N1 | (none) | WikiScanInput.repo_path | accept | New input field is plumbed exclusively to the already-existing `run_scan(repo_path=...)` parameter (Phase-3 surface). No new path-resolution code; `Path(...).resolve()` matches existing patterns at server.py lines 125, 169, 215. |
| T-08-02-N2 | (none) | subprocess spawn in test harness | accept | Test-only surface; gated by `GRAPH_WIKI_RUN_INTEGRATION=1`; no production code path invokes `subprocess.Popen` (RESEARCH.md §"Security Domain" — "The subprocess harness is test-only"). |

Per RESEARCH.md §"Security Domain": no new vectors introduced. ASVS coverage unchanged from Phase 1–5.

No package installs in this plan — Package Legitimacy Audit (N/A; RESEARCH.md §"Package Legitimacy Audit" — no new deps).
</threat_model>

<verification>
After both tasks land:

```bash
# Schema unit test (fast, no Bedrock)
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py -x -v

# Ungated full suite — E2E test must SKIP, no failures
uv run --package graph-wiki-agent pytest -x

# Gated integration suite — E2E test must PASS
GRAPH_WIKI_RUN_INTEGRATION=1 uv run --package graph-wiki-agent pytest -x
```

All three commands must exit 0. The middle command must show the E2E test as `s` (skipped); the third must show it as `.` (passed).
</verification>

<success_criteria>
- `WikiScanInput.repo_path` field added with empty-string default and Field description; `wiki_scan` handler passes it through to `run_scan` via the standard `Path(...) if X else None` idiom.
- `test_wiki_scan_input.py` covers default, explicit-value, and regression-guard cases — all green.
- `test_mcp_e2e.py` launches the real `graph-wiki-mcp` subprocess, drives JSON-RPC over stdin/stdout, exercises all six tools sequentially, asserts non-error for each, and respects the `GRAPH_WIKI_RUN_INTEGRATION=1` gate.
- DACLI-01, DACLI-02, DACLI-03 requirement IDs satisfied (VALIDATION.md rows 8-02-01 through 8-02-03).
- Total run time under `GRAPH_WIKI_RUN_INTEGRATION=1`: ≤180s (VALIDATION.md estimate).
- Bedrock cost per E2E run: ≤$0.01 (RESEARCH.md estimate).
</success_criteria>

<output>
Create `.planning/phases/08-host-reliability/08-02-SUMMARY.md` capturing: the exact `server.py` line numbers of the new field and the modified handler call; the exact final seed-fixture layout chosen; the observed `wiki_scan` output (counts of added/updated/deleted) to confirm scan walked `tmp_path` not the live monorepo; the observed wall-clock time for the gated E2E run; per-tool stderr extracts for any tool that nearly failed; and (if applicable) any deviations from the proposed input shapes (e.g., `wiki_ingest` `op` value differing from `"source"`).
</output>
