---
phase: 17-wiki-io-bug-fixes
plan: "05"
subsystem: wiki-io
tags: [wiki-io, wsres, gap-closure, workspace-exclusion, v2-layout, tdd]
one_liner: "WSRES-02 workspace exclusion plumbed through _resolve_pinned_containers and _discover_heuristic via surgical TDD edits closing the SC#4 gap"

dependency_graph:
  requires:
    - "17-03-PLAN.md — detect_containers.detect() D-11 guard (reference implementation)"
  provides:
    - "WSRES-02 satisfied across all three call paths: detect_containers.main(), init_vault._resolve_pinned_containers, scan_monorepo._discover_heuristic"
  affects:
    - "packages/wiki-io/src/wiki_io/init_vault.py"
    - "packages/wiki-io/src/wiki_io/scan_monorepo.py"

tech_stack:
  added: []
  patterns:
    - "D-11 guard parity (wd != repo_r and wd.parent == repo_r) replicated in _discover_heuristic workspace_segments computation"
    - "TDD RED/GREEN cycle: failing test committed before implementation for both call paths"

key_files:
  created:
    - packages/wiki-io/tests/test_init_vault.py
    - packages/wiki-io/tests/test_scan_monorepo.py
  modified:
    - packages/wiki-io/src/wiki_io/init_vault.py
    - packages/wiki-io/src/wiki_io/scan_monorepo.py
    - .planning/phases/17-wiki-io-bug-fixes/17-VERIFICATION.md

decisions:
  - "Did NOT replicate the D-11 guard logic inside _resolve_pinned_containers — instead delegated entirely to _detect_containers which already owns the guard; keeping the guard in one place (detect_containers.detect) is the correct pattern"
  - "Applied workspace_segments filter to BOTH rglob loops in _discover_heuristic (pyproject.toml and .claude-plugin/plugin.json) rather than only the first, per plan spec"
  - "Used workspace_segments: set[str] approach (matching plan interface spec exactly) rather than a direct path comparison inside the loop"

metrics:
  duration_seconds: 217
  completed_date: "2026-05-19"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 5
---

# Phase 17 Plan 05: WSRES-02 Gap Closure Summary

## What Was Built

Plumbed the WSRES-02 workspace exclusion through the two production call paths that were bypassing it:

1. **`init_vault._resolve_pinned_containers`** — extended signature with `workspace_path: Path | None = None`, forwarded to `_detect_containers(repo, workspace_path=workspace_path)`, and updated the `init_wiki` caller to pass `workspace_path=workspace_path` (already computed at line 162).

2. **`scan_monorepo._discover_heuristic`** — extended signature with `workspace_dir=None`, added D-11 guard-parity `workspace_segments` computation, applied the skip to both rglob loops (pyproject.toml and .claude-plugin/plugin.json). Extended `discover_workspaces` with `workspace_dir=None` and plumbed through to `_discover_heuristic`. Updated `main()` to pass `workspace_dir=workspace`.

3. **7 new unit tests** — 3 in `test_init_vault.py` and 4 in `test_scan_monorepo.py` — all using synthetic `tmp_path` fixtures, with TDD RED/GREEN commits.

4. **Gap closure documentation** — appended `## Gap Closure (Plan 17-05)` section to `17-VERIFICATION.md` with evidence.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for _resolve_pinned_containers | 73ac0a1 | tests/test_init_vault.py |
| 1 (GREEN) | Plumb workspace_path through init_vault | 7aee628 | src/wiki_io/init_vault.py |
| 2 (RED) | Failing tests for _discover_heuristic | 85f0a9b | tests/test_scan_monorepo.py |
| 2 (GREEN) | Add workspace_dir filter to scan_monorepo | 82ba791 | src/wiki_io/scan_monorepo.py |
| 3 | Full-suite verification + gap closure docs | cacceea | 17-VERIFICATION.md |

## Verification

- `uv run --package wiki-io pytest packages/wiki-io/ -q` → **93 passed**, 1 skipped
- 86 pre-existing tests all pass (no regressions)
- 7 new tests pass (3 init_vault + 4 scan_monorepo)
- No unguarded `_detect_containers(repo)` call remains in init_vault.py
- No unguarded `_discover_heuristic(repo)` call remains in scan_monorepo.py production code
- `workspace_segments` appears at 4 locations in scan_monorepo.py

## Deviations from Plan

None — plan executed exactly as written. All surgical edits confined to the three target call sites per plan spec.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. Edits are internal function signatures only.

## Self-Check: PASSED

- `packages/wiki-io/tests/test_init_vault.py` — exists, 3 tests pass
- `packages/wiki-io/tests/test_scan_monorepo.py` — exists, 4 tests pass
- `packages/wiki-io/src/wiki_io/init_vault.py` — modified, commits 7aee628 present
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — modified, commit 82ba791 present
- `.planning/phases/17-wiki-io-bug-fixes/17-VERIFICATION.md` — gap closure appended, original 5 SC# sections intact
- All 5 task commits present in git log
