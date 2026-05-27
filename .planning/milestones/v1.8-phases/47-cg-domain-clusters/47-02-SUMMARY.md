---
phase: 47-cg-domain-clusters
plan: 02
status: complete
completed: 2026-05-27
---

# Plan 47-02: cg domain-clusters CLI subcommand — SUMMARY

## What was built

The `cg domain-clusters` CLI subcommand, registered in `cli/main.py`'s
dispatch table and tested via 6 subprocess-based unit tests covering all
exit codes, both output formats, threshold validation, and degenerate
warning emission.

### Implementation

- **`packages/graph-io/src/graph_io/cli/q_domain_clusters.py`** — new file
  - `add_arguments(parser)` registers `--hub-threshold` (type=float, default=0.5)
  - `run(args) -> int` opens `graph_dir(workspace) / "code.db"` via
    `store.read_only_connect`, translates `GraphNotInitializedError` →
    `exit_codes.NOT_INITIALIZED` and `SchemaMismatchError` →
    `exit_codes.SCHEMA_MISMATCH`, catches `ValueError` (out-of-range hub
    threshold) → `exit_codes.GENERIC` per D-19, writes
    `result.degenerate_warning` to stderr when non-null (D-13), then
    dispatches to `_render_human` or canonical JSON output
  - `_render_human` writes hierarchical markdown (D-21): header,
    Cross-cutting hubs section, then Cluster N: name section per cluster
  - D-22 empty-case writes `"No packages with import edges found."` to
    stderr and returns SUCCESS
  - Does NOT import `_format` — hierarchical output is custom-rendered (D-21
    supersedes the `_format.render` hint in CLUSTER-03)

- **`packages/graph-io/src/graph_io/cli/main.py`** — surgical edit
  - Added `q_domain_clusters` to imports (alphabetical: between
    `q_describe_suite` and `q_domain_deps`)
  - Added `"domain-clusters": q_domain_clusters,` to `_SUBCOMMANDS` before
    `"domain-refs"`

### Tests

- **`packages/graph-io/tests/test_cluster.py`** — 6 CLI tests appended:
  - `test_cli_subcommand_registered`
  - `test_cli_human_format`
  - `test_cli_json_format` (locks JSON key order per D-20)
  - `test_cli_hub_threshold_validation` (0.0 and 1.5 → non-zero exit)
  - `test_cli_not_initialized` (exit code 3, "graph DB not found" on stderr)
  - `test_cli_emits_degenerate_warning_to_stderr`
  - Helpers: `_cg_cmd()` using `python -m graph_io.cli.main`,
    `_seed_workspace()` building a test-mode workspace with `.graph/code.db`

## Decisions honored

- D-16: NOT_INITIALIZED on missing DB (no filesystem-rebuild fallback)
- D-17: handler mirrors `q_cross_cutting.py` shape
- D-18: subcommand registered in `_SUBCOMMANDS` dict
- D-19: out-of-range `--hub-threshold` → `exit_codes.GENERIC` (CLI translates
  `compute_clusters`'s ValueError; per planner note: exit_codes module has no
  USAGE constant, so GENERIC is the documented stand-in)
- D-20: `json.dumps(asdict(result), indent=2, sort_keys=False)` preserves
  dataclass field order: hub_threshold, n_packages_total,
  degenerate_warning, clusters, cross_cutting
- D-21: cross_cutting before clusters, markdown-style section headers,
  custom render — no `_format.render`
- D-22: empty-case stderr placeholder on human; canonical empty JSON on json

## Deviations

None.

## Verification

```
$ uv run cg --help 2>&1 | grep domain-clusters
{update,...,domain-clusters,domain-refs,...}

$ uv run cg domain-clusters --help
usage: cg domain-clusters [-h] [--hub-threshold HUB_THRESHOLD]
options:
  -h, --help            show this help message and exit
  --hub-threshold HUB_THRESHOLD
                        exclude packages imported by more than this fraction
                        of others (default 0.5)

$ uv run --package graph-io pytest tests/test_cluster.py -x -q
..................                                                       [100%]
18 passed in 0.62s
```

## Key files modified

- `packages/graph-io/src/graph_io/cli/q_domain_clusters.py` (new)
- `packages/graph-io/src/graph_io/cli/main.py` (2-line surgical addition)
- `packages/graph-io/tests/test_cluster.py` (6 new CLI tests)

## Commits

- `3f42b58` feat(47-02): add q_domain_clusters CLI handler
- `a81c1e2` feat(47-02): register domain-clusters subcommand in cli/main.py
- `a1dfe82` test(47-02): add CLI subprocess tests for cg domain-clusters

## Self-Check: PASSED

- `cg --help` lists `domain-clusters`
- `cg domain-clusters --help` shows `--hub-threshold`
- All 18 test_cluster.py tests pass (12 Plan 01 + 6 Plan 02)
- `q_domain_clusters.py` contains no `_format` reference
