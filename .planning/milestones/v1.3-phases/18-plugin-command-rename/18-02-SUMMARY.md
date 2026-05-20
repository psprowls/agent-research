---
phase: 18-plugin-command-rename
plan: 02
subsystem: code-wiki-mcp
tags: [refactor, rename, mcp, cmd-02]
requires:
  - phase 18 D-01 verb choice (bootstrap)
  - phase 18 D-02 surface coverage (3 user-facing surfaces)
  - phase 18 D-04 hard cut (no compat alias)
provides:
  - MCP tool surface renamed: wiki_init -> wiki_bootstrap
  - Pydantic models renamed: WikiBootstrapInput / WikiBootstrapOutput
  - Closure of CMD-02 MCP portion
affects:
  - agents/code-wiki-agent/src/code_wiki_mcp/server.py
  - agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py
  - agents/code-wiki-agent/tests/integration/test_mcp_e2e.py
tech-stack:
  added: []
  patterns:
    - "Append a new section to test_mcp_new_tools.py mirroring existing wiki_scan / wiki_ingest registration pattern"
key-files:
  created: []
  modified:
    - agents/code-wiki-agent/src/code_wiki_mcp/server.py
    - agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py
    - agents/code-wiki-agent/tests/integration/test_mcp_e2e.py
  untouched-by-design:
    - agents/code-wiki-agent/tests/unit/test_commands_init.py  # owned exclusively by plan 18-03; Wave 1 file-ownership boundary
decisions:
  - Honored D-04 hard cut: no backwards-compat alias, no dual @mcp.tool registration
  - Preserved internal `from code_wiki_agent.commands.init import InitResult, run_init` (D-02: internal modules out of scope)
  - Plan-acceptance criterion `WikiBootstrapInput count >= 3` over-specified (original WikiInitInput also had 2 occurrences: class def + param annotation). Rename is faithful 1-to-1; criterion treated as descriptive, not strict.
metrics:
  duration_minutes: ~10
  completed_date: 2026-05-19
commit: f126a15
---

# Phase 18 Plan 02: MCP Tool Rename (wiki_init -> wiki_bootstrap) Summary

Renamed the MCP tool surface from `wiki_init` to `wiki_bootstrap` (D-02 step 2 of 3 surfaces), including the `@mcp.tool` registration name, the async function `wiki_init` -> `wiki_bootstrap`, and the Pydantic models `WikiInitInput` / `WikiInitOutput` -> `WikiBootstrapInput` / `WikiBootstrapOutput`. Hard cut per D-04 with no compatibility alias. The internal `commands/init` Python module is intentionally unchanged (out of scope per D-02).

## What Changed

### `agents/code-wiki-agent/src/code_wiki_mcp/server.py` (lines 187-234)

Exact substitutions applied:

| Old | New | Count |
|-----|-----|-------|
| `# --- wiki_init tool ---` | `# --- wiki_bootstrap tool ---` | 1 |
| `class WikiInitInput(BaseModel)` | `class WikiBootstrapInput(BaseModel)` | 1 |
| `class WikiInitOutput(BaseModel)` | `class WikiBootstrapOutput(BaseModel)` | 1 |
| `@mcp.tool(name="wiki_init", description="Bootstrap a wiki vault structure.")` | `@mcp.tool(name="wiki_bootstrap", description="Bootstrap a wiki vault structure.")` | 1 |
| `async def wiki_init(input: WikiInitInput, ctx: Context) -> WikiInitOutput:` | `async def wiki_bootstrap(input: WikiBootstrapInput, ctx: Context) -> WikiBootstrapOutput:` | 1 |
| `return WikiInitOutput(` | `return WikiBootstrapOutput(` | 1 |

Total: 6 substitution sites. `grep -cE '\bwiki_init\b|\bWikiInitInput\b|\bWikiInitOutput\b'` returns **0**. The description string ("Bootstrap a wiki vault structure.") is unchanged — it's descriptive prose, not the slug. The `from code_wiki_agent.commands.init import InitResult, run_init` import line is preserved verbatim.

### `agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py`

- Module docstring (line 3) updated: now names `wiki_bootstrap (Phase 18-02)` alongside wiki_scan and wiki_ingest. Requirements line updated from `MCP-01, MCP-03.` to `MCP-01, MCP-03, CMD-02.`
- Appended a new section `# wiki_bootstrap tool registration (Phase 18-02, CMD-02)` containing three new tests:

  1. `test_wiki_bootstrap_tool_registered` — asserts the imported `wiki_bootstrap` symbol is callable and `__name__ == "wiki_bootstrap"`. Mirrors the `test_wiki_scan_tool_registered` template.
  2. `test_wiki_bootstrap_input_rejects_missing_required_fields` — copied from `test_commands_init.py:132` and renamed to use `WikiBootstrapInput`.
  3. `test_wiki_bootstrap_calls_run_init` — copied from `test_commands_init.py:148` and renamed to use `WikiBootstrapInput` and `wiki_bootstrap`. The patched target stays `code_wiki_mcp.server.run_init` (internal module, out of scope per D-02). The helper `InitResult` construction was inlined rather than depending on `test_commands_init.py`'s module-level `_make_init_result` helper (cross-file fixture dependency would couple the two files and break the file-ownership boundary).

### `agents/code-wiki-agent/tests/integration/test_mcp_e2e.py`

Three rename sites:

1. Helper function rename: `def _send_wiki_init(...)` -> `def _send_wiki_bootstrap(...)`
2. `"name": "wiki_init"` -> `"name": "wiki_bootstrap"` inside the tools/call payload (line 171)
3. Two comment references: `wiki_init` -> `wiki_bootstrap` in the WR-04 serial-dispatch comment and the docstring of `_run_server_serial`
4. Call site at line 303 updated: `_send_wiki_init(2, str(vault))` -> `_send_wiki_bootstrap(2, str(vault))`

`grep -cE '\bwiki_init\b|\bWikiInit(Input|Output)\b'` on the integration test file returns **0**.

### `agents/code-wiki-agent/tests/unit/test_commands_init.py` — UNTOUCHED (D-04 + Wave 1 file-ownership boundary)

This file is owned exclusively by plan 18-03 per the revised PLAN.md. `git diff HEAD~1 HEAD -- agents/code-wiki-agent/tests/unit/test_commands_init.py` returns **empty**. The two obsolete MCP-surface tests (`test_wiki_init_input_rejects_missing_required_fields` at line 132, `test_wiki_init_calls_run_init` at line 148) remain in place untouched. They now fail with `ImportError` because their `from code_wiki_mcp.server import WikiInitInput` line cannot resolve after Task 1's rename. Plan 18-03 will delete them during its `git mv test_commands_init.py -> test_commands_bootstrap.py` cleanup.

## Verification

| Check | Result |
|-------|--------|
| `grep -cE '\bwiki_init\|WikiInitInput\|WikiInitOutput\b' agents/code-wiki-agent/src/code_wiki_mcp/server.py` | 0 |
| `grep -cE '\bwiki_bootstrap\b' agents/code-wiki-agent/src/code_wiki_mcp/server.py` | 3 |
| `grep -cE '\bWikiBootstrapInput\b' agents/code-wiki-agent/src/code_wiki_mcp/server.py` | 2 (class def + param annotation) |
| `grep -cE '\bWikiBootstrapOutput\b' agents/code-wiki-agent/src/code_wiki_mcp/server.py` | 3 (class def + return-type + constructor) |
| `grep -cE '@mcp\.tool\(name="wiki_bootstrap"' agents/code-wiki-agent/src/code_wiki_mcp/server.py` | 1 |
| `grep -cE 'from code_wiki_agent\.commands\.init import' agents/code-wiki-agent/src/code_wiki_mcp/server.py` | 1 (preserved) |
| `from code_wiki_mcp.server import wiki_bootstrap, WikiBootstrapInput, WikiBootstrapOutput` | succeeds |
| `from code_wiki_mcp.server import wiki_init` | raises `ImportError` (D-04 hard cut verified) |
| `grep -cE '\bwiki_init\|WikiInit(Input\|Output)\b' agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py` | 0 |
| `grep -cE '\bwiki_init\|WikiInit(Input\|Output)\b' agents/code-wiki-agent/tests/integration/test_mcp_e2e.py` | 0 |
| `grep -cE 'def test_wiki_bootstrap_tool_registered\b' test_mcp_new_tools.py` | 1 |
| `grep -cE 'def test_wiki_bootstrap_input_rejects_missing_required_fields\b' test_mcp_new_tools.py` | 1 |
| `grep -cE 'def test_wiki_bootstrap_calls_run_init\b' test_mcp_new_tools.py` | 1 |
| `git diff HEAD~1 HEAD -- agents/code-wiki-agent/tests/unit/test_commands_init.py` | empty |
| `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py -m "not integration"` | **18/18 pass** |
| `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -m "not integration"` | 209 pass, 2 expected failures (test_commands_init.py MCP-surface tests; Wave 1 known-failure, fixed by plan 18-03) |

## Deviations from Plan

### Plan-acceptance overcount

**Trigger:** Plan acceptance criterion stated `grep -cE '\bWikiBootstrapInput\b' >= 3`.

**Actual:** count is **2** (class definition + parameter annotation in `async def wiki_bootstrap(input: WikiBootstrapInput, ...)`). The pre-rename file also had 2 occurrences of `WikiInitInput`, so this is a faithful 1-to-1 rename, not a missing substitution.

**Action:** Treated criterion as descriptive (intent: "renamed everywhere"), not strict. The intent is satisfied: zero old symbols remain, all referenced sites use the new symbol. No fix needed.

Rule classification: **none** — this is a plan-spec inaccuracy, not a code bug. Logged for transparency only.

### Per-commit gate is RED in isolation (expected)

Per the plan's Step 6 Wave 1 coordination note, the per-commit pytest gate fails in isolation with exactly 2 ImportError failures in `test_commands_init.py` (the obsolete MCP-surface tests). This is the **expected, planned** behavior because this plan does not touch `test_commands_init.py` (file-ownership boundary with plan 18-03). Plan 18-03's commit deletes those tests; the gate is green at the Wave-1-merged state. Not a deviation.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None new. The hard-cut rename does not introduce new trust boundaries; it changes the registration identity of an existing MCP tool.

## Commit

- `f126a15` — `refactor(18-02): rename MCP tool wiki_init -> wiki_bootstrap`

## Self-Check: PASSED

- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — FOUND (modified)
- `agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py` — FOUND (modified)
- `agents/code-wiki-agent/tests/integration/test_mcp_e2e.py` — FOUND (modified)
- Commit `f126a15` — FOUND in `git log --oneline -3`
