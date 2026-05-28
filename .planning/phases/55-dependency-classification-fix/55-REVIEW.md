---
status: clean
phase: 55-dependency-classification-fix
depth: standard
files_reviewed: 4
reviewed: 2026-05-28
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
---

# Phase 55 Code Review

**Status: clean** — no Critical or Warning findings. One Info note (no action required).

## Scope

Reviewed at standard depth (inline; no `Agent` runtime available):

- `packages/graph-io/src/graph_io/packages.py`
- `packages/graph-io/src/graph_io/queries.py`
- `packages/graph-io/src/graph_io/cli/q_describe_package.py`
- `packages/graph-io/tests/test_packages.py` + `tests/test_queries.py` + `tests/test_cli_describe.py`

## Findings

### INFO-01: `classify()` runs twice per manifest

`refresh()` now calls `classify(info, pkg_dir)` in the new pre-pass (to build the
workspace-name → stored-kind map) and again in the main emission loop. `classify()`
is a pure function of `(info, pkg_dir)`, so the duplicate call is correct, just
slightly redundant. For a workspace with a handful of manifests this is negligible.
Left as-is to keep the two passes decoupled and the change surgical (per plan scope).
No action required.

## Verified clean

- **No SQL injection:** the two new `describe_package` queries use `?` placeholders only.
- **No over-broad suppression:** dependency-node suppression is gated on membership in
  the workspace-name set; external deps keep their `dependency` node + `used_by` edge
  (covered by the boto3 regression test).
- **No dangling edges:** the retargeted `used_by` and new `depends_on_package` dst
  resolve to the target's actual stored kind + name (the Rule 1 bug fixed during 55-01
  closed the one real defect here; the app-target test proves resolution).
- **Dedupe preserved:** shared `seen_edges` set keeps one `used_by` + one
  `depends_on_package` per `(consumer, target)` pair.
- **No schema migration:** `depends_on_package` is a free-text edge kind; `schema.py`
  unchanged.
- **Additive dataclass change:** new `PackageDescription` fields use
  `field(default_factory=list)`; JSON serializes automatically; existing tests green.

## Test posture

Full graph-io suite green after the phase: 462 passed, 1 skipped (pre-existing
`test_domain_depends_on_no_self_loop`), 1 xfailed.
