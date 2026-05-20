---
phase: 06-prompt-content-port-divergence-eval
plan: "02"
subsystem: test-scaffolding
tags: [test-scaffolding, wave-1, divergence-eval, prompt-port, syrupy, pytest]
dependency_graph:
  requires: []
  provides:
    - agents/graph-wiki-agent/tests/prompts/
    - cores/eval-harness/tests/test_divergence_checks.py
    - cores/eval-harness/tests/test_divergence_baseline.py
    - cores/eval-harness/tests/test_divergence.py
    - cores/eval-harness/tests/conftest.py (--accept-divergence-baseline option)
  affects:
    - "06-03 through 06-11: all tasks can point <automated> blocks at these test paths immediately"
tech_stack:
  added: []
  patterns:
    - "Import-guard + pytestmark.skipif for graceful skip when implementation is absent"
    - "FRAGMENT_DIR anchored to Path(__file__).resolve() for cwd-independent test paths"
    - "EVAL_GATE = pytest.mark.skipif(not os.environ.get('GRAPH_WIKI_RUN_EVAL'), ...) for eval-gated integration tests"
key_files:
  created:
    - agents/graph-wiki-agent/tests/prompts/__init__.py
    - agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py
    - agents/graph-wiki-agent/tests/prompts/test_provenance.py
    - cores/eval-harness/tests/test_divergence_checks.py
    - cores/eval-harness/tests/test_divergence_baseline.py
    - cores/eval-harness/tests/test_divergence.py
  modified:
    - cores/eval-harness/tests/conftest.py
decisions:
  - "Used module-level pytestmark.skipif import guard pattern so tests skip (not error) when divergence package is absent — matches the plan's 'collectible now' requirement"
  - "FRAGMENT_DIR uses Path(__file__).resolve().parents[2] / 'src' / ... anchoring rather than cwd-relative paths per project convention"
  - "EVAL_GATE in test_divergence.py defines its own constant (not imported from conftest) to avoid circular import edge cases, matching test_sweep_eval.py precedent"
  - "pytest_addoption added with type annotation pytest.Parser and fixture with pytest.FixtureRequest for ruff compliance"
metrics:
  duration_seconds: 209
  completed_date: "2026-05-15"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 1
---

# Phase 06 Plan 02: Prompt + Divergence Test Scaffolding Summary

**One-liner:** Six skip-marked test skeletons + `--accept-divergence-baseline` conftest option establish the complete test contract for PORT-01..06 and EVAL-11..13 before any implementation lands.

## What Was Built

### Task 1: graph-wiki-agent prompt test scaffolding (commit 40a321d)

- `agents/graph-wiki-agent/tests/prompts/__init__.py` — empty package marker
- `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py` — 8 syrupy snapshot tests (one per `*_SYSTEM` constant: librarian, ingestor, linter×3, scanner, synthesizer, code_reader); each wraps its import in try/except ImportError → `pytest.skip`
- `agents/graph-wiki-agent/tests/prompts/test_provenance.py` — 2 unit tests with `_PROVENANCE_RE` regex matching the 3-line `# Source: / # Anchor: / # Source-commit:` header; both skip cleanly when `_fragments/` is absent

### Task 2: eval-harness divergence test scaffolding + accept_baseline (commit 6b5501c)

- `cores/eval-harness/tests/conftest.py` (modified) — added `pytest_addoption` registering `--accept-divergence-baseline` and `accept_baseline` fixture; existing `EVAL_GATE` and `fixture_vault_path` fixture preserved untouched
- `cores/eval-harness/tests/test_divergence_checks.py` — 5 import-guarded skip-stub tests for LIB-001, ING-001, LNT-002, SCN-001 rules
- `cores/eval-harness/tests/test_divergence_baseline.py` — 5 import-guarded skip-stub tests for load/write/regression-check/accept-baseline behaviors
- `cores/eval-harness/tests/test_divergence.py` — `EVAL_GATE`-marked integration test, parametrized over 4 roles (librarian/ingestor/linter/scanner)

## Verification Results

```
24 tests collected total (10 prompt + 14 divergence)
All 24 tests: SKIPPED (no failures, no collection errors)
49 existing eval-harness tests: PASSED (no regressions from conftest.py edit)
--accept-divergence-baseline: visible in pytest --help when running against cores/eval-harness/tests/
```

## Deviations from Plan

None — plan executed exactly as written.

The `pytest --help | grep -- '--accept-divergence-baseline'` verification step in the plan's `<verify>` block requires a path argument to load the conftest (`uv run pytest cores/eval-harness/tests/ --help`) rather than bare `uv run pytest --help`. This is expected pytest behavior: conftest files are only loaded for the test paths in scope. The option is correctly registered and works as intended.

## Known Stubs

All files are intentionally skeletal. Stubs are the deliverable — they provide collectible test IDs that later plans (06-04..06-11) will fill with real assertions. None of the stubs prevent the plan's goal (establish test contract), which is fully achieved.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Test files only read from the filesystem (Path.__file__-anchored) and register a single pytest option. No threat flags.

## Self-Check: PASSED

All 7 source/test files found at expected paths. Both commits (40a321d, 6b5501c) verified in git log. SUMMARY.md written to shared .planning/ directory (correct for worktree execution mode).
