---
phase: 41-address-v1-7-tech-debt-integration-gate-traceability
plan: 01
subsystem: meta
tags:
  - tech-debt
  - integration-gate
  - traceability
  - v1.7-closeout
requires:
  - .planning/v1.7-MILESTONE-AUDIT.md (items 1 & 2 in Recommendations)
provides:
  - "Canonical INTEGRATION_GATE on agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py"
  - "Up-to-date traceability table: HYGIENE-01..14, CGFIND-01..03, INGESTOR-01..03 marked Satisfied"
affects:
  - agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py
  - .planning/REQUIREMENTS.md
tech-stack:
  added: []
  patterns:
    - "pytest.mark.skipif(not os.environ.get(\"GRAPH_WIKI_RUN_INTEGRATION\"), ...) — canonical INTEGRATION_GATE pattern (matches conftest.py:19-22 verbatim)"
key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py
    - .planning/REQUIREMENTS.md
decisions:
  - "Followed CONTEXT.md D-01..D-08 verbatim — minimum-scope remediation, no bundled cleanups"
  - "Used replace_all for `| Pending |` → `| Satisfied |` because the file had exactly 20 occurrences and no `Pending` literals outside the table"
metrics:
  duration: "~6 minutes"
  completed: 2026-05-26
requirements: []
---

# Phase 41 Plan 01: Address v1.7 Tech Debt — Integration Gate + Traceability Summary

Restored the canonical `GRAPH_WIKI_RUN_INTEGRATION` gate on the Phase 39 scan-end-to-end integration test and synced `.planning/REQUIREMENTS.md` (20 checkboxes + 20 traceability rows) to reflect the actual shipped state of v1.7 phases 35, 36, and 40.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add canonical INTEGRATION_GATE to scan-end-to-end test | `a601f33` | `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` (+9 lines) |
| 2 | Sync REQUIREMENTS.md — flip 20 checkboxes + 20 traceability rows | `9dc14d8` | `.planning/REQUIREMENTS.md` (+40/-40 lines) |

## What Was Built

### Task 1 — Canonical INTEGRATION_GATE wiring

Applied the three-edit recipe from PATTERNS.md verbatim:

1. Added `import os` to the existing stdlib import block (alphabetical placement between `import asyncio` and `import shutil`).
2. Added the `INTEGRATION_GATE` constant immediately after the existing module-level `pytestmark = pytest.mark.integration`, copying the canonical block from `test_bedrock_iam.py` lines 30-35 verbatim (only the `reason=` string adapted to the scan→graph scenario).
3. Decorated `test_run_scan_creates_graph_db_and_uri_derived_slug` with `@INTEGRATION_GATE` on its own line above the `def`. Module-level `pytestmark` retained per D-03 ("alongside, not replacement").

All 8 Task 1 acceptance grep counts pass (see Self-Check). AST parse succeeds.

### Task 2 — REQUIREMENTS.md sync

Two markdown edits, no structural changes:

- **Edit 1:** Flipped exactly 20 checkboxes `- [ ] **{REQ-ID}** —` → `- [x] **{REQ-ID}** —` for HYGIENE-01..14, CGFIND-01..03, INGESTOR-01..03 via 20 surgical single-line `Edit` calls.
- **Edit 2:** Single `replace_all` of `| Pending |` → `| Satisfied |` — safe because the file had exactly 20 occurrences (one per target row), and no other markdown context used the literal `Pending` token.

LIBTOOLS-*, GRAPHCMD-*, SCANNER-* rows untouched (they were already `Complete`). Future Requirements section untouched (D-07 fence). Resulting diff is 40 insertions + 40 deletions — exactly 2× 20 lines (checkbox + status), no other hunks.

## Verification

### Task 1 acceptance criteria (all pass)
- `grep -c '^import os$' …`: **1** ✓
- `grep -c 'INTEGRATION_GATE = pytest.mark.skipif' …`: **1** ✓
- `grep -c 'GRAPH_WIKI_RUN_INTEGRATION' …`: **3** ✓ (≥1 required; the body comment + constant + reason all reference it)
- `grep -c '^@INTEGRATION_GATE$' …`: **1** ✓
- `grep -c '# integration-gate-allow' …`: **0** ✓ (D-04 prohibition honored)
- `grep -c '^pytestmark = pytest.mark.integration$' …`: **1** ✓ (preserved)
- `ast.parse(…)`: exits 0 ✓

### Task 2 acceptance criteria (all pass)
- `grep -c '^- \[x\] \*\*HYGIENE-' …`: **14** ✓
- `grep -c '^- \[x\] \*\*CGFIND-' …`: **3** ✓
- `grep -c '^- \[x\] \*\*INGESTOR-' …`: **3** ✓
- `grep -cE '^- \[ \] \*\*(HYGIENE|CGFIND|INGESTOR)-' …`: **0** ✓
- `grep -c '| HYGIENE-.* | Phase 35 | Satisfied |' …`: **14** ✓
- `grep -c '| CGFIND-.* | Phase 36 | Satisfied |' …`: **3** ✓
- `grep -c '| INGESTOR-.* | Phase 40 | Satisfied |' …`: **3** ✓
- `grep -c '| {GROUP}-.* | Phase X | Pending |' …`: **0** for all three groups ✓
- `grep -c '| LIBTOOLS-.* | Phase 37 | Complete |' …`: **5** ✓ (untouched)
- `grep -c '| GRAPHCMD-.* | Phase 38 | Complete |' …`: **4** ✓ (untouched)
- `grep -c '| SCANNER-.* | Phase 39 | Complete |' …`: **3** ✓ (untouched)
- `grep -c '## Future Requirements' …`: **1** ✓ (untouched)
- `git diff --stat`: exactly 1 file modified ✓; diff body is *only* checkbox and status flips ✓

### Success oracle (`pytest tests/test_integration_gate.py -x`)

Before this phase: red with TWO divergent files —
1. `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` (Phase 39 regression)
2. `packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py` (v1.6-era fixture)

After Task 1: red with ONE divergent file — only the v1.6-era `sample_monorepo/test_top.py` remains. **See "Deviations" below — this is the intended outcome per CONTEXT.md D-01, but the plan's literal success-oracle wording ("exits 0") was unachievable given the D-01 scope fence.**

## Deviations from Plan

### 1. [Rule 1 — Plan inconsistency, NOT a Task 1 implementation bug] Success oracle wording vs D-01 scope fence

- **Found during:** Task 1 verify step.
- **Issue:** The plan's `<verify>` and `<success_criteria>` say `pytest tests/test_integration_gate.py -x` must exit 0. But the meta-test discovers via `rglob("tests/integration/test_*.py")` and currently flags TWO offenders, only one of which (the agent test) is in this phase's scope per CONTEXT.md D-01. The other (`packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py`) is explicitly deferred to v1.8 by D-01 and listed in REQUIREMENTS.md "Future Requirements" line 75.
- **Resolution:** Implemented Task 1 exactly as specified (all 8 file-level acceptance criteria pass). Did NOT touch the sample_monorepo fixture (would have violated D-01). The meta-test transitioned from `divergent: [2 files]` → `divergent: [1 file]` — the intended progress under D-01's scope rules. No code change required; this is a plan-text inconsistency that the planner already documented in CONTEXT.md "Deferred Ideas" and in REQUIREMENTS.md "Future Requirements" line 75.
- **Files modified:** None for this deviation (Task 1 implementation files only).
- **Commit:** N/A (no extra code; documented here).

### 2. [Rule 3 — Minor tooling note] System `python` shim broken; used `uv run python` for AST parse

- **Found during:** Task 1 verification step.
- **Issue:** `python -c "import ast; ast.parse(...)"` exited 134 due to a stale homebrew dyld reference (`Library not loaded: /opt/homebrew/Cellar/python@3.12/...`).
- **Resolution:** Re-ran the same AST parse via `uv run --package graph-wiki-agent python -c …` — succeeded. The check passes; only the host's bare `python` shim is broken.
- **Files modified:** None.

No other deviations. No Rule 4 architectural decisions needed.

## Reconciliation Notes

The plan's `<action>` text for Task 2 already flagged the "24 vs 20" count mismatch between CONTEXT.md narrative and the explicit ID lists (D-05/D-06). I trusted the ID lists (14 + 3 + 3 = 20) per the plan's instruction; all acceptance criteria are pinned to 20 and pass.

## Self-Check: PASSED

Created files: none required by plan output spec beyond this SUMMARY.

Modified files (verified present and committed):
- ✓ `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` — found, +9 lines (commit `a601f33`)
- ✓ `.planning/REQUIREMENTS.md` — found, +40/-40 lines (commit `9dc14d8`)

Commits verified in `git log --oneline -5`:
- ✓ `a601f33` test(41-01): add canonical INTEGRATION_GATE to scan-end-to-end test
- ✓ `9dc14d8` docs(41-01): sync REQUIREMENTS.md — flip 20 checkboxes + 20 traceability rows
