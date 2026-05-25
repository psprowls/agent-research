---
slug: graph-io-require-manifest
status: resolved
created: 2026-05-25T21:28:15Z
updated: 2026-05-25T21:35:00Z
trigger: user_report
goal: find_and_fix
tdd_mode: false
---

# Debug Session: graph-io require_manifest=False still raises

## Symptoms

Tests in `packages/graph-io/tests/test_cli_exit_codes.py` were failing because `update --full` raised `RuntimeError: No .graph-wiki.yaml found in <tmp>/graph-wiki`, despite the CLI being invoked in `--mode test` (which is supposed to set `require_manifest=False`).

## Resolution

**Root cause:** graph-io had two call sites to `workspace_io.config.resolve()`. The CLI dispatcher (`cli/main.py:76`) correctly mapped `--mode test` → `require_manifest=False`, but `update.run()` re-resolved the workspace independently at `update.py:142` without the kwarg, so the default `require_manifest=True` raised.

**Fix (alt — thread workspace through, eliminating double-resolve):**

1. `packages/graph-io/src/graph_io/update.py`:
   - Added `workspace: Path | None = None` parameter to `update.run()`.
   - When `workspace` is provided, use as-is (callers like the CLI already resolved it).
   - When `workspace is None`, resolve with `require_manifest=False` (update is the bootstrap path; manifest may not exist yet).

2. `packages/graph-io/src/graph_io/cli/ops_update.py`:
   - Pass `workspace=args.workspace` through to `update.run()`.

3. `packages/graph-io/src/graph_io/cli/main.py`: no change — already sets `args.workspace = resolve(args.repo, require_manifest).workspace`.

**Test results:**
- Before: all 7 `test_cli_exit_codes.py` tests blocked at first failure on `RuntimeError`.
- After: 5/7 pass. The 2 remaining failures (`test_exit_4_schema_mismatch`, `test_exit_6_update_in_progress`) are unrelated — they hardcode `tmp_path / "lattice" / ".graph" / "code.db"` while workspace_io resolves to `graph-wiki/`. Separate test-setup issue, out of scope.
- Full graph-io suite: 107 passed, 4 failed, 2 errors. All remaining failures are unrelated to `require_manifest`:
  - The 2 `test_cli_exit_codes` failures above.
  - `test_cli_sync_wiki.py` and `test_e2e.py` invoke the CLI without `--mode test`, so they hit the (correct) strict-manifest enforcement at the CLI layer. Separate test-setup concern.

## Evidence

- timestamp: 2026-05-25T21:29Z — Failing test confirmed: `error: No .graph-wiki.yaml found ...`.
- timestamp: 2026-05-25T21:30Z — Read `workspace_io/config.py`; `resolve()` raises only when `require_manifest=True` AND manifest absent. Correct behavior.
- timestamp: 2026-05-25T21:30Z — Read `cli/main.py:76`; passes `require_manifest` correctly.
- timestamp: 2026-05-25T21:30Z — Found `update.py:142` calling `resolve_workspace(repo_root)` with default `True`. Root cause.
- timestamp: 2026-05-25T21:31Z — `grep` confirmed two call sites only.
- timestamp: 2026-05-25T21:34Z — Applied "alt" fix (thread workspace through). Verified by test re-run.
