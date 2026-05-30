---
phase: quick-260530-gqp
plan: 01
subsystem: graph-io
tags: [classification, electron, devDependencies, javascript]
requirements: [QUICK-GQP-01]
key_files:
  modified:
    - packages/graph-io/src/graph_io/packages.py
    - packages/graph-io/src/graph_io/classification.py
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/tests/test_classification.py
    - packages/graph-io/tests/test_packages.py
    - packages/graph-io/tests/integration/test_e2e_apps.py
    - packages/graph-io/tests/test_queries.py
decisions:
  - "Merge devDependencies into the single dependencies list classify() reads; carry dev-origin names as a separate dev_dependencies marker on the node"
  - "electron inserted before spa in _FRAMEWORK_PRECEDENCE so Electron+Vite apps resolve to electron not spa"
  - "dev_dependencies defaults to [] for Python manifests (no devDependencies field exists)"
metrics:
  duration: ~12 minutes
  completed: "2026-05-30"
  tasks_completed: 3
  files_changed: 7
---

# Quick Task 260530-gqp Summary

**One-liner:** Fix devDependency-blind Electron app misclassification by merging devDependencies into the dependency list and adding an 'electron' signal with electron-before-spa precedence.

## What Was Built

Electron apps like `apps/app-electron-ts` declare `electron` and `vite` under `devDependencies`, which `_read_package_json` previously ignored. This caused Electron apps to misclassify as `pkg:` entities (no signal found).

### Changes

**`packages.py` — `_read_package_json`:**
- Reads `devDependencies` alongside `dependencies`
- Merges runtime + dev dep names into a sorted union (deduped) as `info["dependencies"]`
- Adds `info["dev_dependencies"]` = sorted list of dev-only dep names

**`packages.py` — `refresh()` attrs dict:**
- Adds `"dev_dependencies": info.get("dev_dependencies", [])` to node attrs
- Python manifests get `[]` by default (they have no devDependencies)

**`classification.py`:**
- Adds `electron` signal: `if "electron" in deps: signals.append("electron")`
- Updates `_FRAMEWORK_PRECEDENCE = ("nextjs", "expo", "electron", "spa")` — electron before spa so Electron+Vite apps resolve to `electron` not `spa`

**`queries.py`:**
- Adds `"electron"` to `_VALID_APP_KINDS` frozenset (write-time gate)

### Tests Added

- `test_classification.py`: 2 new tests — `test_classify_js_electron` and `test_classify_js_electron_before_spa`
- `test_packages.py`: 3 new tests — electron app from devDeps, dev/runtime split, Python default
- `test_e2e_apps.py`: 1 new e2e test — Electron+Vite app via `update.run()` -> `describe_app` -> `app_kind == 'electron'`
- `test_queries.py`: Updated `test_valid_app_kinds_contents` to include 'electron'

## Deviations from Plan

**[Rule 1 - Bug] Updated stale test_valid_app_kinds_contents assertion**
- **Found during:** Task 3 regression sweep
- **Issue:** `test_queries.py::test_valid_app_kinds_contents` pinned the old 4-element `_VALID_APP_KINDS` set and failed after `"electron"` was added
- **Fix:** Updated the assertion to include `"electron"` — diff is exactly the new member
- **Files modified:** `packages/graph-io/tests/test_queries.py`
- **Commit:** b753ff4

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| T1 RED | f0daf2f | test(260530-gqp-01): add failing tests for electron signal + precedence |
| T1 GREEN | faebf6c | feat(260530-gqp-01): electron signal + devDependencies merge in packages/classification |
| T2 | 23506c8 | feat(260530-gqp-01): surface dev_dependencies attr on package nodes + electron e2e |
| T3 | b753ff4 | fix(260530-gqp-01): update test_valid_app_kinds_contents to include 'electron' |

## Known Stubs

None — all behavior is wired and exercised by tests.

## Threat Flags

None — this change is purely read/classification-time; no new network endpoints, auth paths, or trust boundaries introduced.

## Self-Check: PASSED

- `packages/graph-io/src/graph_io/packages.py` exists with devDependencies merge + dev_dependencies attr
- `packages/graph-io/src/graph_io/classification.py` exists with electron signal + precedence updated
- `packages/graph-io/src/graph_io/queries.py` exists with 'electron' in _VALID_APP_KINDS
- Commits f0daf2f, faebf6c, 23506c8, b753ff4 all present in git log
- Full suite: 480 passed, 0 failures (1 pre-existing ERROR in source-file false-positive unrelated to this change)
