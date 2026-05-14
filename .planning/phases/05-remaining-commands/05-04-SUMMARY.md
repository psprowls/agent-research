---
phase: 05-remaining-commands
plan: "04"
subsystem: code-wiki-agent / vault-io / subagent-runtime
tags: [commands, scan, mcp, subagent-fan-out, scanner, stale-tag, file-map]
dependency_graph:
  requires:
    - phase: 05-01
      provides: CLI callback, log/init commands, server.py wiki_log/wiki_init pattern
    - phase: 03-query-vertical-slice
      provides: SubagentPool, FanOutResult, run_query pattern for fan-out
  provides:
    - code_wiki_agent.commands.scan.ScanResult
    - code_wiki_agent.commands.scan.run_scan
    - code_wiki_agent.commands.scan.SCANNER_SYSTEM
    - code_wiki_agent.commands.scan.build_stub_prompt
    - code_wiki_agent.commands.scan.pick_representative (local)
    - code_wiki_agent.commands.scan.update_index (local wrapper)
    - cli.py scan subcommand (--vault, --no-file-map, --max-depth, --json)
    - code_wiki_mcp.server.wiki_scan MCP tool with 2 progress notifications
  affects:
    - 05-05 (ingest command can follow same scanner fan-out pattern)
    - 05-06 (lint command can use same cli + mcp wiring pattern)
tech-stack:
  added: []
  patterns:
    - "Scanner fan-out: SubagentPool.run_all(role='scanner') after deterministic discovery phase"
    - "Deterministic file map: LLM generates body-only; build_file_map() appended after fan-out"
    - "Stale-tag mutation: _add_stale_tag() prepends stale: true idempotently to frontmatter"
    - "Local wrapper functions for missing vault_io callables (pick_representative, update_index)"
    - "MCP progress: emit before and after run_scan() for long-running commands"
key-files:
  created:
    - agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
    - (test_commands_scan.py — overwritten from stub)
    - (test_mcp_new_tools.py — overwritten from stub)
    - (test_scan_parity.py — overwritten from stub)
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py (scan subcommand added)
    - agents/code-wiki-agent/src/code_wiki_mcp/server.py (wiki_scan tool added)
key-decisions:
  - "pick_representative() implemented inline in scan.py — function absent from vault_io.scan_monorepo at current commit"
  - "update_index() local wrapper implemented inline — callable form not present in worktree's vault_io.update_index"
  - "MCP progress at 2 milestones (before + after run_scan) — simpler than splitting run_scan internals"
  - "Parity tests use inline tmp_path vault (not single-package-vault fixture) — fixture untracked in worktree at this commit"
requirements-completed: [CMD-02, MCP-01, MCP-03]
duration: 27min
completed: "2026-05-14"
---

# Phase 05 Plan 04: scan command Summary

**`scan` command end-to-end: deterministic package discovery + SubagentPool scanner fan-out with body-only LLM output + deterministic file-map append + stale-tag write-back for deleted/renamed packages**

## Performance

- **Duration:** ~27 min
- **Started:** 2026-05-14T17:40:00Z
- **Completed:** 2026-05-14T18:07:00Z
- **Tasks:** 2
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- Delivered `commands/scan.py` with `ScanResult` (6 fields), `async run_scan()`, `SCANNER_SYSTEM` prompt constant, `build_stub_prompt()`, `_add_stale_tag()`, and local helpers `pick_representative()` + `update_index()` wrapper
- Wired `scan` CLI subcommand with `--vault`, `--no-file-map`, `--max-depth`, `--json` options and partial-failure exit code 3 (CLI-06)
- Added `wiki_scan` MCP tool to server.py with `WikiScanInput`/`WikiScanOutput` Pydantic models and 2 progress notifications (MCP-03)
- 16 tests passing: 6 unit tests (scan.py), 7 MCP tests (wiki_scan registration/validation/progress), 3 parity tests (ScanResult shape + state_gate keys + JSON round-trip)

## Task Commits

1. **Task 1: commands/scan.py — run_scan, ScanResult, scanner fan-out, stale-tag write-back** - `524b049` (feat)
2. **Task 2: CLI scan subcommand + MCP wiki_scan tool + parity tests** - `f51a508` (feat)

## Files Created/Modified

- `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py` — ScanResult dataclass, run_scan() async pipeline, SCANNER_SYSTEM prompt, build_stub_prompt(), _add_stale_tag(), pick_representative(), update_index() wrapper
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — scan() subcommand added after init()
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — WikiScanInput/WikiScanOutput models + wiki_scan tool with 2 progress notifications
- `agents/code-wiki-agent/tests/unit/test_commands_scan.py` — 6 unit tests (replaced skip stub)
- `agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py` — 7 wiki_scan tests (replaced skip stub)
- `agents/code-wiki-agent/tests/commands/test_scan_parity.py` — 3 parity tests (replaced skip stub)

## SCANNER_SYSTEM Prompt (exact text for downstream plans)

```
You are a code wiki scanner. Your job is to write a concise stub page for a software package.

Produce ONLY the page body with YAML frontmatter. Do NOT include a "## File map" section — that
is added separately by the build pipeline and must not appear in your output.

Your output must include:
1. YAML frontmatter (between --- delimiters) with these fields:
   - title: <package name>
   - category: package  (use "app" if it is an application, otherwise "package")
   - summary: <one-line description of what the package does>
   - package_path: <relative path of the package in the repo>
   - language: <primary language: python, typescript, javascript, rust, go, unknown>
   - version: <version string or omit if unknown>
   - depends_on: []  (list of internal workspace dependencies, or empty list)
   - exports: []  (list of public exports/scripts, or empty list)

2. ONE short "## Overview" section (3-5 sentences) describing what the package does and why.

3. ONE short "## Notable files" section listing 2-4 key files with a one-line description each.

Keep total output under 380 tokens to stay safely under the 500-token scanner role limit.
Do NOT speculate beyond what the provided file listing shows.
Do NOT include a "## File map" section — it will be appended automatically.
```

## MCP Progress Notifications

`wiki_scan` emits **2 progress milestones**:
- `progress=0, total=2, message="Starting scan"` — before invoking `run_scan()`
- `progress=2, total=2, message="Scan complete: +N ~M -K"` — after `run_scan()` returns

This satisfies MCP-03 without refactoring `run_scan` internals.

## ScanResult Field Set (final)

```python
@dataclass
class ScanResult:
    added: list[str]       # names of packages with newly created vault pages
    updated: list[str]     # names of packages with refreshed vault pages
    deleted: list[str]     # names of packages marked stale (in vault, gone from repo)
    renamed: list[list[str]]  # [[old_name, new_name], ...] rename pairs
    errors: list[str]      # f"{pkg_name}: {exception}" for fan-out failures
    state_gate: dict       # {allowed: bool, reason: str, head_commit: str | None}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pick_representative() absent from vault_io.scan_monorepo**
- **Found during:** Task 1 (commands/scan.py implementation)
- **Issue:** Plan's interface spec listed `pick_representative` as importable from `vault_io.scan_monorepo` but the function does not exist in that module at the current commit
- **Fix:** Implemented `pick_representative(pkg_path, entries=None)` locally in `scan.py` — prioritizes entry point files, then src/lib files, returns up to 3 paths
- **Files modified:** agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
- **Committed in:** 524b049

**2. [Rule 3 - Blocking] update_index() callable absent from vault_io.update_index**
- **Found during:** Task 1 (commands/scan.py implementation)
- **Issue:** Plan called `update_index(wiki)` but the worktree's `vault_io/update_index.py` only has `main()` — the callable `update_index()` function exists in the main repo but not in the worktree at this commit
- **Fix:** Implemented `update_index(wiki)` as a local wrapper in `scan.py` using the available `scan_vault`, `render_index`, `render_category_index`, `CATEGORY_INDEX_FILES`, `CATEGORY_LABELS` exports
- **Files modified:** agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
- **Committed in:** 524b049

**3. [Rule 3 - Blocking] single-package-vault fixture absent from worktree**
- **Found during:** Task 2 (test_scan_parity.py implementation)
- **Issue:** Plan directed parity tests to use `single-package-vault` fixture; fixture exists in main repo as untracked but was not present in the worktree at this commit
- **Fix:** Parity tests rewritten using `tmp_path`-based inline `minimal_vault` fixture — fully self-contained, no external fixture dependency; tests still verify all required properties (ScanResult shape, state_gate keys, JSON round-trip)
- **Files modified:** agents/code-wiki-agent/tests/commands/test_scan_parity.py
- **Committed in:** f51a508

---

**Total deviations:** 3 auto-fixed (all Rule 3 — blocking missing dependencies)
**Impact on plan:** All fixes necessary for test correctness. No behavioral scope creep. The inline `pick_representative` and `update_index` wrapper match the expected interface exactly.

## Issues Encountered

None beyond the 3 blocking deviations above.

## Known Stubs

None — all functionality fully wired. Tests are real assertions with no placeholder data.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes at trust boundaries beyond what the plan's threat model already covers. The `wiki_scan` MCP tool follows the same trust model as `wiki_query` (same-user process, vault_path resolves to real workspace).

## Self-Check: PASSED

Files exist:
- agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py (created)
- agents/code-wiki-agent/src/code_wiki_agent/cli.py (scan subcommand added)
- agents/code-wiki-agent/src/code_wiki_mcp/server.py (wiki_scan tool added)
- agents/code-wiki-agent/tests/unit/test_commands_scan.py (6 tests, no skips)
- agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py (7 tests, no skips)
- agents/code-wiki-agent/tests/commands/test_scan_parity.py (3 tests, no skips)

Commits exist:
- 524b049 (Task 1 — scan.py + unit tests) ✓
- f51a508 (Task 2 — cli.py, server.py, parity + mcp tests) ✓

All 16 tests passing: `uv run --package code-wiki-agent pytest tests/unit/test_commands_scan.py tests/unit/test_mcp_new_tools.py tests/commands/test_scan_parity.py -x` exits 0

## Next Phase Readiness

- scan command fully wired through CLI + MCP surfaces
- SCANNER_SYSTEM prompt documented above for plan-05-05 (ingestor prompt can use same structural patterns)
- Local `pick_representative` and `update_index` wrappers are implementation details in scan.py; downstream plans (05-05, 05-06) should import from vault_io directly once main repo is merged

---
*Phase: 05-remaining-commands*
*Completed: 2026-05-14*
