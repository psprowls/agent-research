---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
plan: 05
subsystem: infra
tags: [ruff, lint, format, vault-io, gap-closure]

# Dependency graph
requires:
  - phase: 01-infrastructure-vault-io-and-mcp-skeleton
    provides: "Plans 01-01 through 01-04 — monorepo scaffold, vault IO, MCP skeleton, model adapter"
provides:
  - "ruff check . exits 0 from repo root (I001/F401/F841 resolved)"
  - "ruff format --check . exits 0 from repo root (11 files reformatted)"
  - "Four vault-io modules free of stale LATTICE_WORKSPACE / lattice-workspace user-visible references"
  - "REVIEW WR-01 and WR-02 findings closed"
affects: [ci-lint-stage, phase-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "# noqa: I001 on load-bearing future-import block to suppress isort false-positives"

key-files:
  created: []
  modified:
    - agents/code-wiki-agent/src/code_wiki_mcp/server.py
    - cores/vault-io/src/vault_io/append_log.py
    - cores/vault-io/src/vault_io/scan_monorepo.py
    - cores/vault-io/src/vault_io/update_tokens.py
    - cores/vault-io/src/vault_io/_workspace.py
    - cores/vault-io/src/vault_io/graph_analyzer.py
    - cores/vault-io/src/vault_io/lint/common.py
    - cores/vault-io/src/vault_io/update_index.py
    - agents/code-wiki-agent/tests/integration/test_mcp_stdio.py
    - agents/code-wiki-agent/tests/unit/test_stdout_guard.py
    - cores/vault-io/tests/test_layout_io_smoke.py
    - cores/vault-io/tests/test_round_trip.py
    - cores/vault-io/tests/test_truncated_frontmatter.py
    - cores/vault-io/src/vault_io/init_vault.py
    - cores/vault-io/src/vault_io/detect_containers.py

key-decisions:
  - "Use # noqa: I001 on server.py future-import line to suppress isort false-positive — the guard-install ordering is load-bearing (D-15) and must not be moved"
  - "Leave TODO comment at init_vault.py:155 ('lattice-workspace equivalent') intact — it is an intentional Phase-5 marker explicitly documented as acceptable in the plan"

patterns-established:
  - "# noqa: I001 pattern: when import ordering is semantically required (guard-first), suppress isort rather than restructure"

requirements-completed: [INFRA-04, INFRA-05]

# Metrics
duration: 18min
completed: 2026-05-13
---

# Phase 01 Plan 05: Ruff Lint + Stale Reference Gap-Closure Summary

**Cleared three ruff check violations (I001/F401/F841), reformatted 11 files to pass ruff format --check, and replaced four stale `LATTICE_WORKSPACE`/`lattice-workspace` user-visible strings with correct `CODE_WIKI_REAL_VAULT_PATH` references — closing both gaps from 01-VERIFICATION.md so CI lint passes on next push.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-13T18:10:00Z
- **Completed:** 2026-05-13T18:28:00Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments

- Fixed all three ruff check errors that would have broken CI on next push
- Reformatted 11 files (whitespace-only) so ruff format --check . exits 0
- Replaced stale LATTICE_WORKSPACE / lattice-workspace strings in four vault-io modules with CODE_WIKI_REAL_VAULT_PATH (docstrings) and "pending Phase 5 workspace init" (init_vault.py JSON output)
- Test suite remains at 29 passed, 1 skipped — no regressions

## Task Commits

1. **Task 1: Fix three ruff check errors (I001, F401, F841)** - `1651342` (fix)
2. **Task 2: Reformat 11 files with ruff format** - `88a3978` (style)
3. **Task 3: Strip stale lattice-workspace strings from four modules** - `b7ba591` (fix)

## Files Created/Modified

**Task 1 — Lint fixes:**
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — added `# noqa: I001` to `from __future__ import annotations` line (I001 suppressed; guard ordering preserved)
- `cores/vault-io/src/vault_io/append_log.py` — removed unused `from pathlib import Path` import (F401 cleared)
- `cores/vault-io/src/vault_io/scan_monorepo.py` — removed dead `vault = wiki` assignment in `main()` at old line 1159 (F841 cleared; line 620 assignment that IS used was left intact)

**Task 2 — Formatter pass (whitespace-only, 11 files):**
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py`
- `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py`
- `agents/code-wiki-agent/tests/unit/test_stdout_guard.py`
- `cores/vault-io/src/vault_io/_workspace.py`
- `cores/vault-io/src/vault_io/graph_analyzer.py`
- `cores/vault-io/src/vault_io/lint/common.py`
- `cores/vault-io/src/vault_io/update_index.py`
- `cores/vault-io/src/vault_io/update_tokens.py`
- `cores/vault-io/tests/test_layout_io_smoke.py`
- `cores/vault-io/tests/test_round_trip.py`
- `cores/vault-io/tests/test_truncated_frontmatter.py`

**Task 3 — Stale string replacements:**
- `cores/vault-io/src/vault_io/init_vault.py` — `result['layers']['raw']` and `result['layers']['work']` values: `"owned by lattice-workspace"` → `"pending Phase 5 workspace init"` (2 occurrences)
- `cores/vault-io/src/vault_io/append_log.py` — module docstring: `LATTICE_WORKSPACE env var or git repo with lattice/ workspace directory` → `CODE_WIKI_REAL_VAULT_PATH env var (or a git repo containing a wiki/ directory)` (with line-wrap fix for E501)
- `cores/vault-io/src/vault_io/detect_containers.py` — Usage docstring: `repo discovered via lattice-workspace` → `repo discovered via CODE_WIKI_REAL_VAULT_PATH or git`
- `cores/vault-io/src/vault_io/graph_analyzer.py` — module docstring: `via \`lattice-workspace\` (defaults to \`<repo>/lattice/wiki/\`)` → `via vault_io._workspace.resolve_wiki_and_repo (reads CODE_WIKI_REAL_VAULT_PATH or walks up from cwd to find a wiki/ directory)`

## Decisions Made

- Used `# noqa: I001` on the `from __future__ import annotations` line in `server.py` rather than restructuring imports — the guard-first ordering is a correctness requirement (D-15: any mcp/pydantic import before `sys.stdout = _StdoutGuard()` could emit stdout before the guard is installed)
- Left TODO comment at `init_vault.py:155` (`# TODO Phase 5: workspace init (lattice-workspace equivalent)`) intact as directed by the plan — it is an intentional Phase-5 marker explaining what the raw/work layers are for

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed E501 line-too-long introduced by docstring replacement in append_log.py**
- **Found during:** Task 3 verification (ruff check .)
- **Issue:** The replacement docstring sentence was 159 characters on one line, exceeding the 120-char limit configured in pyproject.toml
- **Fix:** Split the sentence onto two lines with a natural break after the first sentence
- **Files modified:** `cores/vault-io/src/vault_io/append_log.py`
- **Verification:** `uv run ruff check .` exits 0 after fix
- **Committed in:** b7ba591 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** Necessary correction introduced by the docstring replacement itself. No scope creep.

## Issues Encountered

- Discovered that my first set of edits (Tasks 1 edits) went to the main repo path `/Users/pat/Personal/deep-agents/...` rather than the worktree path. Reverted those edits from the main repo and correctly applied all edits to the worktree at `/Users/pat/Personal/deep-agents/.claude/worktrees/agent-a524c401e9cd6e3e5/...`.
- The `grep -rn 'lattice-workspace\|LATTICE_WORKSPACE' cores/vault-io/src/` scan after all fixes shows two remaining matches:
  1. `init_vault.py:155` — the intentional TODO comment (plan says to leave it)
  2. `_workspace.py:5` — `"There is no lattice-workspace discovery in this codebase."` — accurate negative documentation explaining what this codebase does NOT do (not a stale reference)
  Both are acceptable per the plan and VERIFICATION.md context.

## Known Stubs

None — this plan makes no changes to data-flow or rendering logic; all changes are lint/format/docstring corrections.

## Threat Flags

None — changes are lint fixes, whitespace reformatting, and docstring updates only. No new network endpoints, auth paths, file access patterns, or schema changes.

## Verification Results

```
uv run ruff check .          → All checks passed! (exit 0)
uv run ruff format --check . → 38 files already formatted (exit 0)
uv run pytest -q             → 29 passed, 1 skipped (matches pre-gap-closure baseline)
```

Gaps closed from 01-VERIFICATION.md:
- gaps[0] "ruff check . and ruff format --check . both exit 0" → CLOSED by Tasks 1+2
- gaps[1] "vault-io modules do not leak stale lattice-workspace references" → CLOSED by Task 3

## Next Phase Readiness

- CI lint stage (`.github/workflows/ci.yml`) will pass on next push — `ruff check .` and `ruff format --check .` both exit 0
- Phase 1 is now fully complete (all gaps closed, all must-have truths satisfied)
- Phase 2 (Subagent Fan-Out Runtime) can proceed without Phase 1 cleanup debt

---
*Phase: 01-infrastructure-vault-io-and-mcp-skeleton*
*Completed: 2026-05-13*
