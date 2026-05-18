---
phase: 06-prompt-content-port-divergence-eval
plan: 16
subsystem: eval-harness
tags: [gap-closure, test-hygiene, sys-path, WR-05]
requires: [06-15]
provides: [WR-05-fully-closed]
affects: [cores/eval-harness/tests/test_divergence.py, pyproject.toml]
tech-stack:
  added: []
  patterns: [root-pytest-pythonpath]
key-files:
  created: []
  modified:
    - pyproject.toml
    - cores/eval-harness/tests/test_divergence.py
decisions:
  - "Hoist pytest pythonpath to root pyproject.toml so eval_helpers resolves from any cwd (workspace root or package dir); keep per-package pythonpath in cores/eval-harness/pyproject.toml for in-package CI invocation."
  - "After removing sys.path block, hoist eval_helpers import next to top-level imports and drop now-obsolete `# noqa: E402`."
metrics:
  duration: ~5min
  tasks_completed: 2
  files_modified: 2
  completed: 2026-05-16
---

# Phase 06 Plan 16: WR-05 Residual — sys.path.insert Hack Removal Summary

One-liner: Hoisted pytest `pythonpath` to root `pyproject.toml` and removed the brittle 11-line `sys.path.insert` workaround from `test_divergence.py`, fully closing WR-05.

## What Changed

### (a) Root `pyproject.toml` diff

```diff
 [tool.pytest.ini_options]
 addopts = "--import-mode=importlib"
+pythonpath = ["cores/eval-harness/tests"]
```

One added line under `[tool.pytest.ini_options]`. `addopts` preserved. No other sections touched.

### (b) `cores/eval-harness/tests/test_divergence.py` header line-count delta

`1 file changed, 1 insertion(+), 17 deletions(-)` — net **−16 lines** in the file overall, and approximately **−17 lines** in the header region (lines 23-53 before, the equivalent block now spans roughly 14 lines).

Specifically removed:
- `import sys` (1 line)
- The 11-line `sys.path` manipulation block (8-line comment + 3-line `_TESTS_DIR` / `if … sys.path.insert(...)` code)
- The standalone "Eval gate and helpers" section divider banner (3 comment-rule lines)
- The `# noqa: E402` suffix on the `eval_helpers` import

Added:
- A single-line `# Eval gate and helpers — imported from eval_helpers (WR-05, WR-06)` provenance comment immediately above the now-hoisted import.

The header now reads as plain stdlib + project imports:

```python
import subprocess
from pathlib import Path

import pytest

from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
from eval_harness.divergence.metric import (
    DivergenceMetric,
    check_regression,
    load_baseline,
    write_baseline,
)

# Eval gate and helpers — imported from eval_helpers (WR-05, WR-06)
from eval_helpers import EVAL_GATE, produce_outputs as _produce_outputs
```

### (c) `cores/eval-harness/pyproject.toml` is UNCHANGED

Confirmed via `git status --short` after the commits — only the two files listed above appear in the diff. The per-package `pythonpath = ["tests"]` (line 27) remains in place to cover the in-package-cwd invocation case independently of the new workspace-root config.

## Tasks Completed

| Task | Name                                                       | Commit    |
| ---- | ---------------------------------------------------------- | --------- |
| 1    | Add cores/eval-harness/tests to root pytest pythonpath     | `6f363bc` |
| 2    | Delete sys.path.insert hack from test_divergence.py        | `72766f8` |

## Verification

- `grep -c "sys.path.insert" cores/eval-harness/tests/test_divergence.py` → **0**
- `grep -cE "^import sys" cores/eval-harness/tests/test_divergence.py` → **0**
- `grep -cE '\bsys\b' cores/eval-harness/tests/test_divergence.py` → **0** (after deletion)
- `uv run --package eval-harness pytest cores/eval-harness/tests/test_divergence.py --collect-only -q` → **4 tests collected** (librarian, ingestor, linter, scanner)
- `uv run --package eval-harness pytest cores/eval-harness/tests/ -q --ignore=cores/eval-harness/tests/test_divergence.py` → **108 passed, 14 skipped** (all 14 skips are CODE_WIKI_RUN_EVAL-gated or `--run-eval-analysis`-gated tests; pre-existing behavior)

Optional live verification (Pat can run if convenient):

```
CODE_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest cores/eval-harness/tests/test_divergence.py -k librarian -s -x
```

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed in order; the post-deletion `\bsys\b` grep returned zero matches, confirming `import sys` removal was safe per Task 2 step 2's pre-check.

## Self-Check: PASSED

- `.planning/phases/06-prompt-content-port-divergence-eval/06-16-SUMMARY.md` exists (this file).
- Commit `6f363bc` found in `git log` (Task 1).
- Commit `72766f8` found in `git log` (Task 2).
- `pyproject.toml` contains the `pythonpath` entry.
- `cores/eval-harness/tests/test_divergence.py` contains no `sys.path.insert` and no `import sys`.
- `cores/eval-harness/pyproject.toml` is unchanged (not in `git status` diff for this plan).
