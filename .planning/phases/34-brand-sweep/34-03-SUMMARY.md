---
phase: 34-brand-sweep
plan: 03
subsystem: graph-io
tags: [brand-sweep, cli, dead-code-deletion]

requires:
  - plan: 34-01
    provides: .brand-grep-allow (gate runnable mid-sweep)
provides:
  - cg --help shows graph-wiki branding (SC#1)
  - _SKIP_REPO_PREFIXES dead code deleted
  - test_refresh_skips_lattice_dir_manifests deleted (function under test no longer exists)
  - cg = "graph_io.cli.main:main" registered as a [project.scripts] entry (deviation)
affects: [34-05]

tech-stack:
  added: ["cg" workspace-installed script entry point]
  patterns: [delete-dead-code-rather-than-allowlist]

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/cli/main.py
    - packages/graph-io/src/graph_io/packages.py
    - packages/graph-io/tests/test_packages.py
    - packages/graph-io/pyproject.toml (deviation — add cg script entry)

key-decisions:
  - "D-05 applied: argparse description string lattice → graph-wiki."
  - "D-16 revised applied: _SKIP_REPO_PREFIXES deleted (lattice/ vendor dir doesn't exist in this repo)."
  - "D-12 revised applied: test_refresh_skips_lattice_dir_manifests deleted with the function under test."
  - "Deviation: added [project.scripts] cg = graph_io.cli.main:main to graph-io/pyproject.toml. Required because the previous `cg` was a globally-installed uv tool from outdated `lattice-graph-core` package; without a workspace script entry, `uv run cg --help` (the SC#1 verification command) had no in-workspace target. One-line addition to satisfy plan goal_check + SC#1."

patterns-established:
  - "Delete-rather-than-allowlist: when a brand-flagged pattern targets a feature that doesn't exist (lattice/ vendor dir in this repo), delete the dead code instead of carving it out."

requirements-completed:
  - BRAND-02 (CLI description)
  - BRAND-04 (graph-io grep-clean of lattice|LATTICE in touched files)

duration: ~10min
---

# Plan 34-03 Summary

Three coupled edits:
1. argparse description rebrand (cli/main.py:45)
2. `_SKIP_REPO_PREFIXES` constant + rel-prefix check deletion (packages.py)
3. Corresponding test deletion (test_packages.py)

One deviation from the plan's files_modified: added `[project.scripts] cg = "graph_io.cli.main:main"`
to `packages/graph-io/pyproject.toml`. This was required because the SC#1 verification command
(`uv run cg --help`) was resolving to a stale globally-installed `cg` shim from an outdated
`lattice-graph-core` uv tool install, not to the workspace package's CLI. The plan's goal_check
and SC#1 both assume `uv run cg` dispatches to the workspace package, which requires a
`[project.scripts]` entry. One-line addition; no semantic impact.

All 7 test_packages.py tests pass post-deletion.
