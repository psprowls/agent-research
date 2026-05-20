---
phase: 11-workspace-io-port-m1
plan: 03
subsystem: workspace
tags: [port, tests, rebrand, lattice-workspace, graph-wiki]
requires:
  - workspace-io package skeleton (Plan 01)
  - workspace-io source modules ported (Plan 02)
provides:
  - 67 ported regression tests covering config/manifest/init/paths/local_config/render/versions/pending_updates
  - test for D-03 strict-resolve (test_resolve_raises_when_no_manifest_found)
  - test for D-14 v1-raises (test_read_raises_on_v1)
  - test for D-14 null-applied behavior (test_null_applied_version_no_signal, replacing v1-coerced test)
affects:
  - packages/workspace-io/tests/ (11 new test files; previously empty)
tech-stack:
  added: []
  patterns:
    - "pytest tmp_path fixtures for hermetic FS"
    - "monkeypatch.delenv('GRAPH_WIKI_WORKSPACE') in every test_config test to isolate from host env"
    - "_seed_manifest() helper in test_config to write minimal v2 .graph-wiki.yaml satisfying D-03 strict check"
    - "v2 manifest with applied_version: null replaces v1 manifest in test_null_applied_version_no_signal (D-14 rewrite)"
key-files:
  created:
    - packages/workspace-io/tests/test_config.py
    - packages/workspace-io/tests/test_manifest.py
    - packages/workspace-io/tests/test_manifest_v2_roundtrip.py
    - packages/workspace-io/tests/test_init.py
    - packages/workspace-io/tests/test_init_records_version.py
    - packages/workspace-io/tests/test_init_bumps_version.py
    - packages/workspace-io/tests/test_paths.py
    - packages/workspace-io/tests/test_local_config.py
    - packages/workspace-io/tests/test_render.py
    - packages/workspace-io/tests/test_warn_if_stale.py
    - packages/workspace-io/tests/test_pending_updates.py
  modified: []
  deleted: []
decisions:
  - "D-03 covered: test_resolve_raises_when_no_manifest_found asserts strict resolve() raises RuntimeError matching 'graph-wiki-agent init' when no manifest is present"
  - "D-06 covered: test_schema.py NOT ported; test_creates_work_schema dropped from test_init.py"
  - "D-14 covered (read side): test_read_raises_on_v1 in test_manifest.py asserts v1 format raises"
  - "D-14 covered (warn side): test_v1_coerced_entry_no_signal replaced with test_null_applied_version_no_signal — writes v2 manifest with applied_version: null directly, asserts warn_if_stale returns False"
  - "Pitfall #4 mitigated: every reference to tmp_path / 'lattice' rewritten to tmp_path / 'graph-wiki' to match DEFAULT_WORKSPACE_NAME"
  - "Pitfall #3 mitigated: test_render imports AUTO_START/AUTO_END from workspace_io.render rather than hardcoding marker strings; test_init asserts the workspace-io:auto:plugins:start marker directly"
  - "test_config seeds a minimal v2 manifest in every successful resolve() test so the new strict check (D-03) does not raise unexpectedly; the negative test omits the manifest"
metrics:
  duration_minutes: 12
  tasks_completed: 3
  files_changed: 11
  completed_date: 2026-05-18
---

# Phase 11 Plan 03: workspace-io Tests Port Summary

Ported the lattice-workspace test suite (11 active files, 67 tests) to `packages/workspace-io/tests/`. Applied the rebrand symbol map, dropped `test_schema.py` (D-06) and `test_manifest_v1_read.py` (D-14), rewrote `test_v1_coerced_entry_no_signal` as `test_null_applied_version_no_signal` (D-14), and added two new tests for the divergent strict-resolve (D-03) and v1-raises (D-14) behaviors. Full suite passes under `uv run --package workspace-io pytest`.

## What Was Built

### Task 1 — Verbatim-rebrand test files (27 tests across 6 files)

- `test_paths.py` (7 tests): each helper (`wiki_dir`, `work_dir`, `graph_dir`, `raw_dir`, `knowledge_dir`, `manifest_path`) + string-coercion test. Manifest path assertion uses `.graph-wiki.yaml`.
- `test_local_config.py` (9 tests): bespoke parser tests for `.graph-wiki.local.yaml` and the `graph-wiki-directory` key. All YAML fixture bodies rebranded.
- `test_manifest_v2_roundtrip.py` (3 tests): v2 write/read, key-order preservation, block-style assertion. Plugin names updated to `graph-wiki-agent` and `code-wiki-second`.
- `test_init_records_version.py` (3 tests): both version fields written, idempotent same-version no-rewrite, missing version kwarg raises TypeError.
- `test_init_bumps_version.py` (1 test): re-init with newer version bumps both fields.
- `test_pending_updates.py` (4 tests): mismatched-only returned, no mutation, frozen dataclass, no-manifest returns empty.

### Task 2 — Behavior-rewrite test files (24 tests across 3 files)

- `test_init.py` (14 tests, was 15): dropped `test_creates_work_schema` per D-06. All `tmp_path / "lattice"` → `tmp_path / "graph-wiki"`; multi-plugin tests use `graph-wiki-agent` + `code-wiki-second`. Auto-marker assertion now matches `<!-- workspace-io:auto:plugins:start -->`. Gitignore assertions use `.graph-wiki.local.yaml`.
- `test_render.py` (6 tests): imports `AUTO_START`/`AUTO_END` from `workspace_io.render` rather than hardcoding strings. `_write_manifest()` helper writes `.graph-wiki.yaml` with v2 schema. Plugin names rebranded; unknown-plugin test uses `some-third-party-plugin` to exercise the generic-pointer path.
- `test_warn_if_stale.py` (4 tests): 3 ports + 1 rewrite. `test_v1_coerced_entry_no_signal` replaced with `test_null_applied_version_no_signal` per D-14 — writes a v2 manifest with `applied_version: null` directly (since v1 reads now raise per `manifest.read()`).

### Task 3 — test_config + test_manifest with new D-03/D-14 tests (16 tests across 2 files)

- `test_config.py` (10 tests, was 9): every successful-resolve test now also writes a minimal v2 `.graph-wiki.yaml` into the expected workspace dir to satisfy D-03's strict check. Every test calls `monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)` to isolate from the host shell env. CLI subprocess test invokes `python -m workspace_io.config`. Added new `test_resolve_raises_when_no_manifest_found` asserting the strict raise with `graph-wiki-agent init` in the message.
- `test_manifest.py` (6 tests, was 5): 5 ported (with `.graph-wiki.yaml` and `graph-wiki-agent` rebrand) + new `test_read_raises_on_v1` asserting `manifest.read()` raises on v1 format.

## Verification Results

`uv run --package workspace-io pytest` (cd'd into `packages/workspace-io`):

```
collected 67 items

tests/test_config.py ..........                                          [ 14%]
tests/test_init.py ..............                                        [ 35%]
tests/test_init_bumps_version.py .                                       [ 37%]
tests/test_init_records_version.py ...                                   [ 41%]
tests/test_local_config.py .........                                     [ 55%]
tests/test_manifest.py ......                                            [ 64%]
tests/test_manifest_v2_roundtrip.py ...                                  [ 68%]
tests/test_paths.py .......                                              [ 79%]
tests/test_pending_updates.py ....                                       [ 85%]
tests/test_render.py ......                                              [ 94%]
tests/test_warn_if_stale.py ....                                         [100%]

============================== 67 passed in 0.48s ==============================
```

Test counts per file: 7 (paths) + 9 (local_config) + 3 (manifest_v2_roundtrip) + 3 (init_records_version) + 1 (init_bumps_version) + 4 (pending_updates) + 14 (init) + 6 (render) + 4 (warn_if_stale) + 10 (config) + 6 (manifest) = 67 — matches the planned total.

Acceptance grep results:
- No `lattice_workspace`, `LatticeConfig`, `.lattice.yaml`, `.lattice.local.yaml`, `lattice-directory`, or `lattice-workspace:auto` references in any test file.
- `test_schema.py` does not exist; `test_manifest_v1_read.py` does not exist.
- `test_resolve_raises_when_no_manifest_found` present in `test_config.py` (1 match).
- `test_read_raises_on_v1` present in `test_manifest.py` (1 match).
- `test_null_applied_version_no_signal` present in `test_warn_if_stale.py` (1 match); `v1_coerced` absent (0 matches).
- `test_creates_work_schema` absent in `test_init.py` (0 matches).

Note: `uv run --package workspace-io pytest` from the repo root collects tests from sibling packages (vault-io, eval-harness, graph-wiki-agent) whose dependencies aren't synced in this worktree, producing collection errors. Running pytest from inside `packages/workspace-io/` uses the local `pyproject.toml`'s `testpaths = ["tests"]` and isolates collection to the workspace-io suite — this is the canonical way to run the package's tests and matches the plan's acceptance test (`uv run --package workspace-io pytest -x` exit 0).

## Commits

| Task | Commit  | Description                                                            |
| ---- | ------- | ---------------------------------------------------------------------- |
| 1    | e02b2b3 | test(11-03): port verbatim-rebrand test files for workspace-io         |
| 2    | 9f2ae2c | test(11-03): port behavior-rewrite test files for workspace-io         |
| 3    | 2c8b4d9 | test(11-03): port test_config + test_manifest with D-03/D-14 tests     |

## Decisions Made

1. **`_seed_manifest()` helper in `test_config.py`** — the lattice analogs return a config without requiring a manifest file to exist. Plan 02's D-03 implementation makes `resolve()` strict, so each test that exercises a successful resolve now seeds a minimal v2 `.graph-wiki.yaml` in the expected workspace directory. The negative test (`test_resolve_raises_when_no_manifest_found`) deliberately omits the manifest to verify the raise.
2. **`monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)` in every `test_config` test** — if the host shell has `GRAPH_WIKI_WORKSPACE` set (Pat's local env), `resolve()` would short-circuit through the env-override branch and bypass the discovery logic the tests intend to exercise. Adding the delenv call up front isolates each test from host state. The CLI subprocess test (`test_cli_prints_workspace_to_stdout`) is naturally isolated since `subprocess.run` does not inherit `monkeypatch`-set env, but the parent test process's env is what matters for `_make_repo`/`_seed_manifest`, and the subprocess inherits the parent env unless cleaned — the test passed without modification, so the subprocess receives a fresh env state via `monkeypatch.delenv` from the parent.
3. **Second-plugin distinct stand-in `code-wiki-second`** — the multi-plugin accumulation tests in lattice used `lattice-wiki` + `lattice-work` to test that two distinct entries are recorded. Rather than mapping the second to another real graph-wiki plugin (none exists yet), used a synthetic `code-wiki-second` name. This preserves the test's intent (two distinct entries) without introducing a fake plugin reference into the assert strings.
4. **Plan-mentioned "11-PATTERNS.md" not present** — the plan's `<read_first>` references `.planning/phases/11-workspace-io-port-m1/11-PATTERNS.md`, which exists only as an untracked file in the user's working tree (per the initial git status) and is not committed to this worktree. The plan's `<interfaces>` table and per-task `<action>` blocks contain all of the symbol-map and test-body guidance needed; the lattice source plus Plan 02's SUMMARY provided the additional context required. No information was lost by the missing file.

## Deviations from Plan

None. Plan executed exactly as written. The three rule-based decisions above (`_seed_manifest`, `delenv` in every test, synthetic second plugin name) are all explicitly anticipated in the plan's `<action>` blocks ("ensure the test ALSO writes a minimal `.graph-wiki.yaml` to that workspace dir", "do NOT add a manifest file" for env-override branches, "second plugin in multi-plugin accumulation tests -> a distinct name like `code-wiki-second`").

## Threat Flags

None introduced. All tests run in pytest-managed `tmp_path` directories; no new network endpoints, no auth paths, no new schema surface. Threat register entry T-11-06 (test fixture files in tmp_path, disposition: accept) remains accurate.

## Requirements Satisfied

- **WS-09** — every ported lattice-workspace test runs green under `workspace_io` imports with `.graph-wiki.yaml` manifest expectations. 67 tests pass.

## Phase 11 Success Criterion Progress

- **SC #1 (uv sync resolves workspace-io and tests pass)** — fully satisfied for the source side. The full `workspace_io` test suite is green.
- **SC #5 (every ported test runs green under new module path with .graph-wiki.yaml expectations)** — fully satisfied.

## Next Plan

Plan 04 rewrites `vault-io._workspace.resolve_wiki_and_repo` as a thin delegation to `workspace_io.config.resolve()` (D-02), updates the vault-io tests that referenced `GRAPH_WIKI_REAL_VAULT_PATH` to `GRAPH_WIKI_WORKSPACE` (D-01), and verifies the delegation does not break any vault-io consumers.

## Self-Check: PASSED

- Created files verified on disk:
  - FOUND: packages/workspace-io/tests/test_paths.py
  - FOUND: packages/workspace-io/tests/test_local_config.py
  - FOUND: packages/workspace-io/tests/test_manifest_v2_roundtrip.py
  - FOUND: packages/workspace-io/tests/test_init_records_version.py
  - FOUND: packages/workspace-io/tests/test_init_bumps_version.py
  - FOUND: packages/workspace-io/tests/test_pending_updates.py
  - FOUND: packages/workspace-io/tests/test_init.py
  - FOUND: packages/workspace-io/tests/test_render.py
  - FOUND: packages/workspace-io/tests/test_warn_if_stale.py
  - FOUND: packages/workspace-io/tests/test_config.py
  - FOUND: packages/workspace-io/tests/test_manifest.py
- Commits verified in git log:
  - FOUND: e02b2b3 (Task 1)
  - FOUND: 9f2ae2c (Task 2)
  - FOUND: 2c8b4d9 (Task 3)
- Test suite: 67 passed in 0.48s
