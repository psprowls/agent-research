---
phase: 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands
reviewed: 2026-05-29T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
  - packages/graph-io/src/graph_io/render.py
  - packages/graph-io/src/graph_io/cli/_format.py
  - packages/graph-io/src/graph_io/cli/q_describe_package.py
  - packages/graph-io/src/graph_io/cli/q_describe_path.py
  - packages/graph-io/src/graph_io/cli/q_describe_repo.py
  - packages/graph-io/src/graph_io/cli/q_describe_domain.py
  - packages/graph-io/src/graph_io/cli/q_describe_entry_point.py
  - packages/graph-io/src/graph_io/cli/q_describe_suite.py
  - packages/graph-io/src/graph_io/cli/q_find.py
findings:
  critical: 0
  warning: 4
  info: 1
  total: 5
status: issues_found
---

# Phase 59: Code Review Report

**Reviewed:** 2026-05-29
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Phase 59 decoupled `graph-wiki-agent` from `graph_io.cli` by promoting formatting logic into a public `graph_io.render` module, implementing six `format_*` functions, a `_format.py` re-export shim for backward compatibility, and shared core functions (`run_build`, `run_describe`, `run_query`) consumed by the Typer commands, MCP tools, and `scan.py`.

The migration is structurally sound. Resource handling (try/finally `conn.close()`) is correct across all paths in `run_describe` and `run_query`, including early returns and the `raise KeyError(kind)` sentinel path. The MCP server correctly validates `identifier`-required semantics against `DESCRIBE_REQUIRES_IDENTIFIER` before calling `run_describe`. The D-03 cost-field omission is implemented correctly: the `event.startswith("graph_build")` gate in `_write_trace_record` includes `model_id` only on build events, and the `graph_describe` / `graph_query` trace paths pass `model_id=None` and reach neither gate. The duplicate truncation notice in `run_query` (notice embedded in rendered stdout AND returned in stderr) is intentional and matches the pre-migration `q_find.py` behavior (`print(render(..., on_truncate=_notice))` likewise emits to both channels).

Four warnings were found: three are stderr error-message divergences (non-byte-identical vs the prior `q_describe_*.py` inline printers on not-found paths), and one is a missing defensive guard in `run_describe` for `identifier=None` on required-identifier kinds. One informational item flags a stale count in the `_format.py` shim comment.

## Warnings

### WR-01: Stderr error message diverges from CLI for `path` not-found

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:219`
**Issue:** `run_describe` returns `"error: path not found: {identifier}"` on a miss, but `q_describe_path.py:32` prints `"error: path not found in graph: {path}"`. The phrase `" in graph"` is absent. Any caller (script, MCP client, test) that parses the not-found stderr string will see a different message from the new shared core than from the CLI.
**Fix:**
```python
# graph.py run_describe, kind=="path" branch
return exit_codes.GENERIC, "", f"error: path not found in graph: {identifier}"
```

### WR-02: Stderr error message diverges from CLI for `test_suite` not-found

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:296`
**Issue:** `run_describe` returns `"error: test-suite not found: {identifier}"` on a miss, but `q_describe_suite.py:36` prints `"error: not found: {name}"`. The canonical message uses `"not found: {name}"` (no kind prefix).
**Fix:**
```python
# graph.py run_describe, kind=="test_suite" branch
return exit_codes.GENERIC, "", f"error: not found: {identifier}"
```

### WR-03: Stderr error message diverges from CLI for `repository` not-found

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:225`
**Issue:** `run_describe` returns `"error: repository not found"` on a miss, but `q_describe_repo.py:32` prints `"error: not found: repository"`. The word order is different.
**Fix:**
```python
# graph.py run_describe, kind=="repository" branch
return exit_codes.GENERIC, "", "error: not found: repository"
```

### WR-04: `run_describe` crashes with `TypeError` when `identifier=None` for required-identifier kinds

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:257-258`
**Issue:** In the `entry_point` branch, line 257 assigns `raw = identifier` and line 258 evaluates `if ":" in raw`. When `identifier` is `None`, this raises `TypeError: argument of type 'NoneType' is not iterable`. The same gap exists for `package`, `path`, `domain`, and `test_suite` branches where `queries.*` would receive `name=None` or `path=None`.

Both the CLI (Typer `Argument(...)` is required) and the MCP server (lines 559–566 in `server.py` gate on `DESCRIBE_REQUIRES_IDENTIFIER`) prevent `None` from reaching `run_describe` in practice today. However, `run_describe` is a public function with the signature `identifier: str | None`, making the unguarded `None` dereference a latent crash for any future direct caller.
**Fix:**
```python
# At the top of the try block in run_describe, before the kind dispatch:
if kind != "repository" and identifier is None:
    return exit_codes.GENERIC, "", f"error: identifier required for kind={kind}"
```

## Info

### IN-01: `_format.py` shim comment lists `q_find` as one of 7 importers, but `q_find` was migrated

**File:** `packages/graph-io/src/graph_io/cli/_format.py:5`
**Issue:** The docstring says "7 existing cli modules import from it: q_find, q_imported_by, q_exported_by, q_exports, q_imports, q_callers, q_callees." `q_find` has been migrated in this phase to import `render` from `graph_io.render` directly (`from graph_io import exit_codes, queries, render as _render, store`). The actual importer count is 6, and `q_find` is not among them.
**Fix:** Update the shim docstring:
```python
"""Re-export shim — formatting logic lives in graph_io.render.

This module is preserved (not deleted) because 6 existing cli modules import
from it: q_imported_by, q_exported_by, q_exports, q_imports, q_callers,
q_callees. Deleting it would break those callers.

New code should import from graph_io.render directly.
"""
```

---

_Reviewed: 2026-05-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
