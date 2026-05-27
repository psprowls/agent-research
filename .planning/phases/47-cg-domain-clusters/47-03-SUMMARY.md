---
phase: 47-cg-domain-clusters
plan: 03
status: complete
completed: 2026-05-27
---

# Plan 47-03: agent-research integration tests + integration marker — SUMMARY

## What was built

A new `tests/integration/` subpackage with `test_cluster_cli.py` containing
four `@pytest.mark.integration` tests that exercise `cg domain-clusters`
against the actual agent-research code.db (CLUSTER-04, CLUSTER-05). The
`integration` pytest marker is registered in `pyproject.toml`.

### Implementation

- **`packages/graph-io/pyproject.toml`** — added `markers` field to
  `[tool.pytest.ini_options]`:
  ```toml
  markers = [
    "integration: requires the agent-research workspace graph (skipped when unavailable)",
  ]
  ```

- **`packages/graph-io/tests/integration/__init__.py`** — empty package marker

- **`packages/graph-io/tests/integration/test_cluster_cli.py`** — 4 integration
  tests:
  - `test_cg_help_lists_command` (help text — always runs)
  - `test_subcommand_help_exit_zero` (subcommand help — always runs)
  - `test_run_against_agent_research_graph` (skips when `code.db` absent;
    asserts exit 0, JSON parses with locked D-20 key order, contains
    ≥1 cluster OR a degenerate_warning)
  - `test_byte_identical_repeated_invocation` (CLUSTER-05 subprocess check —
    runs `cg domain-clusters --fmt json` twice, asserts byte-identical
    `stdout`)

  Helpers walk up from the test file to find the agent-research repo root,
  use `python -m graph_io.cli.main` to avoid PATH dependence, and skip
  cleanly via `pytest.skip(...)` when the workspace graph is absent.

### Verification (Task 3)

```
$ uv run --package graph-io pytest -x -q
.................x........... ... ...............................        [100%]
380 passed, 1 skipped, 1 xfailed in 19.08s
```

- Full graph-io test suite: 380 passed (16 new in this phase: 12 unit +
  6 CLI from Plan 02 minus 2 helpers, plus 4 integration), 1 pre-existing
  skip, 1 pre-existing xfail
- 0 `PytestUnknownMarkWarning` after marker registration
- Integration tests ran in the real-data path (not skipped) because the
  agent-research workspace graph is initialised in this environment

## Decisions honored

- D-26: integration test file in `tests/integration/`, subprocess invocation
  against the real repo's code.db, exit-0 + (clusters OR warning) assertion,
  byte-identical determinism check at subprocess granularity (stronger than
  the in-process JSON test in Plan 01)
- CLUSTER-04 (integration test against agent-research graph)
- CLUSTER-05 (subprocess-level byte-identical determinism)

## Deviations

None.

## Key files modified / created

- `packages/graph-io/pyproject.toml` (1-stanza addition)
- `packages/graph-io/tests/integration/__init__.py` (new, 0 bytes)
- `packages/graph-io/tests/integration/test_cluster_cli.py` (new, 109 lines)

## Commits

- `8618621` build(47-03): register integration pytest marker in graph-io
- `f659e8e` test(47-03): add integration tests for cg domain-clusters

## Self-Check: PASSED

- `uv run --package graph-io pytest -x -q` exits 0
- `tests/integration/test_cluster_cli.py` contains exactly 4
  `@pytest.mark.integration` tests
- `pyproject.toml` registers the `integration` marker
- No `PytestUnknownMarkWarning` in pytest output
- `cg domain-clusters --fmt json` returns byte-identical output across two
  invocations against the live agent-research graph
