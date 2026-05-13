---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
plan: 04
subsystem: infra
tags: [mcp, fastmcp, stdio, jsonrpc, pydantic, stdout-guard]

# Dependency graph
requires:
  - phase: 01-infrastructure-vault-io-and-mcp-skeleton
    provides: "agents/code-wiki-agent skeleton (01-01) + pyproject [project.scripts] code-wiki-mcp entry point (01-01)"
provides:
  - "code-wiki-mcp stdio MCP server entry point (FastMCP-based)"
  - "_StdoutGuard sentinel pattern: rebinds sys.stdout at module-init time to block any Python-level stray write while preserving .buffer for FastMCP's raw JSON-RPC writer"
  - "wiki_ping tool (D-13 debug utility) with PingInput/PingOutput Pydantic schemas — the template for all Phase 5 @mcp.tool registrations"
  - "Subprocess JSON-RPC integrity test that runs in CI by default (no Bedrock required) — the canonical MCP-05 gate"
affects: ["phase-2 ingest tools", "phase-5 wiki commands (all six MCP tools)", "any future MCP tool addition"]

# Tech tracking
tech-stack:
  added: ["mcp (1.27.1) FastMCP", "pydantic models as tool schemas"]
  patterns:
    - "_StdoutGuard rebind BEFORE any non-stdlib import (guard install is the second executable line after `import sys`)"
    - "FastMCP tool with typed Pydantic input/output (PingInput/PingOutput) instead of raw dict args"
    - "Subprocess integrity test: spawn entry point + send initialize+notifications/initialized+tools/call over stdin + assert every stdout line parses as JSON-RPC"
    - "All logging routed to sys.stderr at module init via logging.basicConfig(stream=sys.stderr); boto3/botocore loggers preemptively set to WARNING"

key-files:
  created:
    - "agents/code-wiki-agent/src/code_wiki_mcp/server.py"
    - "agents/code-wiki-agent/tests/unit/test_stdout_guard.py"
    - "agents/code-wiki-agent/tests/integration/test_mcp_stdio.py"
  modified: []

key-decisions:
  - "Expose _StdoutGuard.buffer as the original stdout's .buffer (required because mcp 1.27.1's stdio_server reads sys.stdout.buffer at startup) — without this the guard works but the server crashes on first tools/call"
  - "Send notifications/initialized between initialize and tools/call in the integration test — MCP spec requires it and FastMCP returns -32602 'Received request before initialization' without it"
  - "Tool argument shape is {'input': {'message': 'hello'}} (nested under parameter name), NOT the flat {'message': 'hello'} shown in RESEARCH Pattern 7 — FastMCP names tool args after Python parameter names when the param is a Pydantic BaseModel"
  - "Drop the `version='0.1.0'` kwarg from the FastMCP constructor — mcp 1.27.1's FastMCP.__init__ has no version parameter"
  - "Defensive: set boto3/botocore loggers to WARNING in server.py even though Plan 01-04 doesn't import them (cheap insurance against Phase 5/6 tool authors who add Bedrock-touching tools without re-reading this pattern)"

patterns-established:
  - "Stdout-clean MCP server: install _StdoutGuard before any library import, route logging to stderr, expose .buffer for FastMCP's raw writer"
  - "Typed Pydantic tool schemas (PingInput/PingOutput) — Phase 5 tools should follow the same `def tool(input: SomeInput) -> SomeOutput` shape"
  - "End-to-end MCP integrity test pattern: subprocess.Popen + 3-message JSON-RPC handshake + assert every stdout line is JSON-RPC + assert tool response carries expected payload"

requirements-completed: [MCP-05, MCP-08]

# Metrics
duration: ~15 min
completed: 2026-05-13
---

# Phase 01 Plan 04: MCP Stdio Skeleton Summary

**FastMCP `code-wiki-mcp` stdio server with `_StdoutGuard` sentinel + Pydantic-typed `wiki_ping` tool + subprocess JSON-RPC integrity test proving every stdout byte is valid framing.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-13T17:28:32Z (approx)
- **Completed:** 2026-05-13T17:43:45Z
- **Tasks:** 2
- **Files modified:** 3 (all newly created)

## Accomplishments

- `code-wiki-mcp` entry point launches a FastMCP server with `transport="stdio"` explicitly set
- `_StdoutGuard` installed at module-init time **before** the `mcp.server.fastmcp` and `pydantic` imports — any stray Python-level write to `sys.stdout` raises `RuntimeError("Illegal stdout write in MCP server: ...")`
- `_StdoutGuard.buffer` preserves the original stdout's binary buffer so FastMCP's `stdio_server` can construct its JSON-RPC writer (without this the server crashes on first `tools/call` with `AttributeError: '_StdoutGuard' object has no attribute 'buffer'`)
- Single `wiki_ping(input: PingInput) -> PingOutput` tool registered (D-13 debug utility), establishing the typed-schema pattern for all Phase 5 tools
- All logging routed to `sys.stderr` via `logging.basicConfig(stream=sys.stderr, level=WARNING)`; boto3/botocore loggers preemptively set to WARNING (Pitfall 3 mitigation, harmless when those libraries aren't imported)
- MCP-08 anti-features verified absent: no `@mcp.resource`, no `@mcp.prompt`, no sampling, no SSE / streamable-HTTP
- Subprocess integration test (`test_mcp_stdio.py`) runs in CI by default (NOT marked `pytest.mark.integration`, per D-16) — proves end-to-end that:
  - Every non-empty stdout line is `json.loads`-able with a `jsonrpc` or `id` key
  - The `tools/call wiki_ping` response carries both `"pong"` and `"hello"` and is not flagged as error

## Task Commits

Each task was committed atomically (TDD ordering for Task 1):

1. **Task 1 RED: failing unit test for `_StdoutGuard` + `wiki_ping`** — `969ae80` (test)
2. **Task 1 GREEN: implement `code_wiki_mcp.server` with `_StdoutGuard` + `wiki_ping`** — `1b64cbb` (feat)
3. **Task 2: subprocess JSON-RPC integrity test + `.buffer` passthrough fix** — `5aeb423` (feat)

No separate metadata commit — STATE.md / ROADMAP.md are owned by the orchestrator (worktree-mode rule).

## Files Created/Modified

**Created:**
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — FastMCP server: `_StdoutGuard` + `mcp = FastMCP(name="code-wiki-mcp")` + `wiki_ping` tool + `main()` entry point calling `mcp.run(transport="stdio")`
- `agents/code-wiki-agent/tests/unit/test_stdout_guard.py` — Five unit tests asserting guard semantics (raise on non-empty, tolerate empty/whitespace, flush no-op), server module exports (`mcp`, `main`), and `wiki_ping` direct-call behavior
- `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` — Two subprocess tests: stdout-is-JSON-RPC integrity + `wiki_ping` round-trip returns `pong`+`hello`

## Verification Evidence

### Final phase-wide gate
```
$ uv run pytest -q
s.............................                                           [100%]
29 passed, 1 skipped, 1 warning in 2.72s
```
(The 1 skipped is `test_bedrock_iam.py`, gated behind `CODE_WIKI_RUN_INTEGRATION` — pre-existing from Plan 01-01.)

### Stderr from the subprocess test
Empty (`''`). Nothing in the wiki_ping path triggers a logging call; logging.basicConfig is wired to stderr regardless, so when Phase 5 tools start logging at WARNING+ the output goes to stderr automatically.

### Example JSON-RPC response line from the subprocess capture
```
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{\n  \"status\": \"pong\",\n  \"echo\": \"hello\"\n}"}],"structuredContent":{"status":"pong","echo":"hello"},"isError":false}}
```
FastMCP 1.27.1 returns the typed BaseModel under both `result.structuredContent` (machine-readable) and `result.content[0].text` (text rendering). Our integration test asserts on the serialized blob so it's robust to either shape.

### FastMCP attribute name for `mcp.name`
`server.mcp.name` (direct attribute, no underscore). Verified via `inspect.signature(FastMCP)` and a live instantiation — `FastMCP(name="code-wiki-mcp").name == "code-wiki-mcp"`.

### Unit + integration subset
```
$ uv run --package code-wiki-agent pytest tests/unit/test_stdout_guard.py tests/integration/test_mcp_stdio.py -x -q
.......                                                                  [100%]
7 passed in 0.85s
```

### Static acceptance grep results
```
OK: file exists                                  (server.py)
OK: correct import                               (from mcp.server.fastmcp import FastMCP)
OK: wrong import absent                          (no `from fastmcp`)
OK: guard class present                          (class _StdoutGuard)
OK: explicit stdio transport                     (transport="stdio")
OK: tool decorator present                       (@mcp.tool)
OK: guard installed before mcp+pydantic imports  (awk ordering check)
OK: MCP-08 anti-features absent                  (no resource/prompt/streamable_http/create_sse_app)
OK: subprocess.Popen present                     (test_mcp_stdio.py)
OK: json.loads present
OK: wiki_ping name present
OK: NOT applied as a pytest mark
```

## Decisions Made

1. **`_StdoutGuard.buffer` exposes original stdout's buffer.** Required for compatibility with `mcp 1.27.1`'s `stdio_server`, which reads `sys.stdout.buffer` at startup to construct a `TextIOWrapper` for JSON-RPC writes. The guard still catches Python-level stray writes through `.write()`; FastMCP's framing path goes through `.buffer` and bypasses the guard — which is correct, those bytes ARE the legitimate stdout traffic. Documented inline with rationale.
2. **Tool argument shape:** `arguments={"input": {"message": "hello"}}` (nested), not the flat `{"message": "hello"}` from RESEARCH Pattern 7. FastMCP names tool args after the Python parameter name when that parameter is a Pydantic `BaseModel`. Verified empirically.
3. **Drop `version="0.1.0"` from `FastMCP(...)` call.** mcp 1.27.1's `FastMCP.__init__` has no `version` kwarg (verified via `inspect.signature`). Sticking with just `name="code-wiki-mcp"`.
4. **Send `notifications/initialized` between initialize and tools/call.** MCP spec requires it; FastMCP returns `-32602 "Received request before initialization"` if you skip it. RESEARCH Pattern 7 omitted this notification; the integration test adds it.
5. **Keep boto3/botocore logger silencing in `server.py` even though this plan doesn't import them.** Cheap (two lines), idempotent, prevents a Phase 5/6 regression where a tool author adds a Bedrock-touching tool without re-reading the stdout discipline. Documented inline as "harmless if these libraries are never imported".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pattern 6 missing `.buffer` exposure on `_StdoutGuard`**
- **Found during:** Task 2 (subprocess smoke before writing the integration test)
- **Issue:** RESEARCH Pattern 6 rebinds `sys.stdout` to a `_StdoutGuard()` instance with only `write` and `flush` methods. But `mcp 1.27.1`'s `mcp.server.stdio.stdio_server` reads `sys.stdout.buffer` once at startup to wrap the raw binary stream for JSON-RPC framing. Without `.buffer`, the server crashes with `AttributeError: '_StdoutGuard' object has no attribute 'buffer'` on `mcp.run(transport="stdio")` — making the integration test impossible.
- **Fix:** Capture `_ORIGINAL_STDOUT = sys.stdout` *before* the guard rebind, and expose `buffer = _ORIGINAL_STDOUT.buffer` as a class attribute on `_StdoutGuard`. This gives FastMCP the raw binary stream it needs while Python-level `sys.stdout.write(...)` still hits the guard (which is the actual threat model — `print()`, logging handlers pointing at sys.stdout, library debug chatter).
- **Files modified:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py`
- **Verification:** Subprocess test passes; stdout shows clean JSON-RPC frames; `_StdoutGuard().write("oops")` still raises `RuntimeError`.
- **Committed in:** `5aeb423` (the buffer change is bundled with the Task 2 commit because Task 1's GREEN commit `1b64cbb` would have passed unit tests without `.buffer` — the bug only surfaces at subprocess boot).

**2. [Rule 1 - Bug] Pattern 7 wire format mismatch for Pydantic-typed tool params**
- **Found during:** Task 2 (subprocess smoke)
- **Issue:** RESEARCH Pattern 7 sends `tools/call` with `arguments={"message": "hello"}` (flat), but FastMCP responded with a Pydantic validation error: `"input  Field required [type=missing, input_value={'message': 'hello'}, input_type=dict]"`. FastMCP names the tool argument after the Python parameter name (`input` in our case), so the correct wire shape is `arguments={"input": {"message": "hello"}}`.
- **Fix:** Updated `_send_tools_call()` in `test_mcp_stdio.py` to send the nested shape and documented the empirical wire format with an inline comment so future readers don't repeat the mistake.
- **Files modified:** `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py`
- **Verification:** `tools/call` now returns `"status": "pong", "echo": "hello"` with `isError: false`.
- **Committed in:** `5aeb423`.

**3. [Rule 1 - Bug] Missing `notifications/initialized` in Pattern 7 handshake**
- **Found during:** Task 2 (subprocess smoke; tools/call returned -32602 "Received request before initialization" when only initialize+tools/call were sent)
- **Issue:** MCP spec requires the client to send `notifications/initialized` after receiving the initialize response and before any `tools/call`. RESEARCH Pattern 7 omitted this notification.
- **Fix:** Added `_send_initialized_notification()` to the test helper; integration test now sends initialize → notifications/initialized → tools/call.
- **Files modified:** `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py`
- **Verification:** `tools/call` reaches the wiki_ping handler and returns pong.
- **Committed in:** `5aeb423`.

**4. [Rule 1 - Bug] `FastMCP(version="0.1.0")` raises TypeError in mcp 1.27.1**
- **Found during:** Task 1 (pre-implementation `inspect.signature(FastMCP)` probe)
- **Issue:** RESEARCH Pattern 6 passes `version="0.1.0"` to the FastMCP constructor, but mcp 1.27.1's `FastMCP.__init__` has no `version` parameter (verified via `inspect.signature`).
- **Fix:** Drop the kwarg; instantiate as `FastMCP(name="code-wiki-mcp")`. Comment documents why.
- **Files modified:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py`
- **Verification:** Import + instantiation succeed in unit test (`server.mcp.name == "code-wiki-mcp"`).
- **Committed in:** `1b64cbb`.

**5. [Rule 1 - Bug] Acceptance grep `! grep -q 'pytest.mark.integration'` matched docstring mention**
- **Found during:** Task 2 (running plan's verbatim acceptance grep)
- **Issue:** The acceptance check forbids any literal occurrence of the string `pytest.mark.integration` in the test file. The original docstring documented WHY the test is NOT marked, using the exact literal — which failed the grep even though no marker is actually applied.
- **Fix:** Reworded the docstring to "intentionally NOT marked as an integration-only test" so the literal token does not appear; the semantic check (`! grep -E '^(pytestmark|@pytest\.mark\.integration)'`) still confirms no marker is applied.
- **Files modified:** `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py`
- **Verification:** All five acceptance greps for Task 2 now pass.
- **Committed in:** `5aeb423`.

---

**Total deviations:** 5 auto-fixed (all Rule 1 — bugs in the RESEARCH/PATTERNS templates that surfaced only when running against the installed `mcp 1.27.1` API).
**Impact on plan:** All five fixes are necessary for the plan's behavior block and acceptance criteria to be satisfied with the actual installed package versions. None changed the plan's intent — they corrected mechanical specification errors in Patterns 6 and 7 that pre-dated this plan's authorship. No scope creep.

## Threat Surface Scan

No new threat surface introduced beyond the plan's `<threat_model>` (T-1-02 stdout/framing, T-1-08 ping input). The `_StdoutGuard.buffer` exposure does NOT widen the trust boundary — FastMCP already had legitimate ownership of the JSON-RPC channel; the change only makes the guard compatible with the version of FastMCP that lattice already depends on.

No threat flags.

## Known Stubs

None. wiki_ping is a permanent D-13 debug utility, not a stub.

## Issues Encountered

The 5 deviations above were all surfaced empirically during execution by running `inspect.signature` on `FastMCP.__init__` (caught the `version` kwarg mismatch) and by probing the subprocess with handcrafted JSON-RPC (caught the `.buffer` requirement, the nested-args wire shape, and the missing `notifications/initialized`). The TDD discipline (RED unit test before implementation) caught nothing extra — those tests were written against the plan's behavior block and passed once the implementation existed; the bugs all hid in subprocess-level interactions that the unit tests don't reach.

## Self-Check: PASSED

Verified items exist:
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — FOUND
- `agents/code-wiki-agent/tests/unit/test_stdout_guard.py` — FOUND
- `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` — FOUND

Verified commits exist on `worktree-agent-a111ad877b66502de`:
- `969ae80` (test: RED unit test) — FOUND
- `1b64cbb` (feat: server.py implementation) — FOUND
- `5aeb423` (feat: integration test + buffer passthrough) — FOUND

Final phase-wide `uv run pytest -q`: 29 passed, 1 skipped, 1 warning. 

## Next Phase Readiness

- MCP-05 + MCP-08 closed. The pattern is now in place for Phase 5: add new tools by writing `class XInput(BaseModel) / class XOutput(BaseModel)` + `@mcp.tool` decorated function next to `wiki_ping` in `server.py` (or in a sibling module imported AFTER the guard install).
- Phase 5 tool authors MUST keep their tool-module imports below the `sys.stdout = _StdoutGuard()` line in `server.py` (or place new tool modules behind a function-level import) — adding a top-level `from new_tool_module import x` above the guard would defeat MCP-05.
- The subprocess integrity test will continue to run in CI by default and catch any regression in MCP-05.

---
*Phase: 01-infrastructure-vault-io-and-mcp-skeleton*
*Plan: 04*
*Completed: 2026-05-13*
