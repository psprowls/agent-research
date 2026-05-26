---
plan_id: "34-04"
phase: 34
wave: 2
depends_on: ["34-01"]
files_modified:
  - packages/graph-io/src/graph_io/update.py
  - packages/graph-io/tests/test_cli_exit_codes.py
autonomous: true
requirements:
  - BRAND-03
must_haves:
  truths:
    - "D-06: target env var name is GRAPH_WIKI_LOCK_TIMEOUT_MS"
    - "D-09 (revised): _default_lock_timeout() is a straight rename — six lines, identical to the pre-Phase-34 shape with only the env var name changed"
    - "D-07/D-08 (revised): no alias, no precedence logic, no deprecation warning, no stderr output"
    - "D-13: test_cli_exit_codes.py:130 sets GRAPH_WIKI_LOCK_TIMEOUT_MS=200; the existing timeout-respect assertion continues to pass"
    - "After this plan, grep -rF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/ returns zero hits"
    - "update.py and test_cli_exit_codes.py commit atomically (single change set)"
  goal_check: |
    uv run --package graph-io pytest packages/graph-io/tests/test_cli_exit_codes.py -q && \
    grep -qF 'GRAPH_WIKI_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py && \
    ! grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py && \
    grep -qF '"GRAPH_WIKI_LOCK_TIMEOUT_MS": "200"' packages/graph-io/tests/test_cli_exit_codes.py && \
    ! grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/tests/test_cli_exit_codes.py
---

# Plan 34-04: update.py env-var straight rename + test_cli_exit_codes.py rename (atomic)

<objective>
Rename `LATTICE_GRAPH_LOCK_TIMEOUT_MS` to `GRAPH_WIKI_LOCK_TIMEOUT_MS` in `update.py` and update
the single existing test that exercises it. Per the revised D-07/D-08/D-09/D-10, this is a
**straight rename** — no deprecation alias, no precedence logic, no warning. Single-user repo,
no backwards compatibility required.

Both edits land in the same commit because the test currently sets the old env var name and
the production code currently reads it; the rename is a coupled change.
</objective>

<tasks>

<task id="34-04-T1">
<title>Straight-rename env var in _default_lock_timeout() per revised D-09</title>
<read_first>
  - packages/graph-io/src/graph_io/update.py (lines 153-160 — the existing 6-line function)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-06 target name; D-09 revised straight-rename; D-07/D-08 revised "no alias, no warning")
</read_first>
<action>
Edit `packages/graph-io/src/graph_io/update.py`. In `_default_lock_timeout()` (currently lines
153-160), replace exactly one substring:

- `os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")` → `os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")`

That is the entire production-code change. The resulting function body:

```python
def _default_lock_timeout() -> int:
    raw = os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")
    if raw is None:
        return 30_000
    try:
        return max(0, int(raw))
    except ValueError:
        return 30_000
```

Do NOT add `import sys` (no warning code to emit). Do NOT add any branch logic (no alias to
handle). Do NOT modify any other function or import in the file.
</action>
<acceptance_criteria>
  - New env var literal is present:
    `grep -qF 'os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")' packages/graph-io/src/graph_io/update.py`
  - Old env var literal is gone from the file:
    `! grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py`
  - Function shape is unchanged (still 6 logical lines, no extra branches):
    `grep -c 'os.environ.get' packages/graph-io/src/graph_io/update.py` outputs `1`
  - No stderr-printing code was introduced:
    `! grep -qF 'file=sys.stderr' packages/graph-io/src/graph_io/update.py`
  - Python module is still syntactically valid and returns the default with no env var set:
    `uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 30000' 2>&1` exits 0 with no stderr
  - With the new env var set, function returns the parsed value silently:
    `GRAPH_WIKI_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 5000' 2>&1 | grep -c warning` outputs `0`
  - With only the old env var set, function returns the default (NOT the old value):
    `unset GRAPH_WIKI_LOCK_TIMEOUT_MS; LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 30000' 2>&1` exits 0 (the old var is ignored — no fallback)
</acceptance_criteria>
</task>

<task id="34-04-T2">
<title>Rename env var literal in test_cli_exit_codes.py per D-13</title>
<read_first>
  - packages/graph-io/tests/test_cli_exit_codes.py (line 130 + surrounding test method ~lines 100-150 to understand intent)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-13 — single-string replacement; the timeout-respect assertion continues to pass with the new env var name)
</read_first>
<action>
Edit `packages/graph-io/tests/test_cli_exit_codes.py`. Replace exactly one substring on line 130:

- `"LATTICE_GRAPH_LOCK_TIMEOUT_MS": "200"` → `"GRAPH_WIKI_LOCK_TIMEOUT_MS": "200"`

The test continues to assert the lock-timeout-honored behavior (200ms timeout, `elapsed_ms <
5000`). The new env var name is the only thing in production code that controls the timeout
post-rename.

Do NOT modify any other lines, assertions, or test methods in the file.
</action>
<acceptance_criteria>
  - Old env var literal is gone:
    `! grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/tests/test_cli_exit_codes.py`
  - New env var literal is present:
    `grep -qF '"GRAPH_WIKI_LOCK_TIMEOUT_MS": "200"' packages/graph-io/tests/test_cli_exit_codes.py`
  - Whole-file lattice grep is clean:
    `grep -cE 'lattice|LATTICE' packages/graph-io/tests/test_cli_exit_codes.py` outputs `0`
  - The test still passes:
    `uv run --package graph-io pytest packages/graph-io/tests/test_cli_exit_codes.py -q` exits 0
</acceptance_criteria>
</task>

</tasks>

<verification>
After both tasks complete (committed atomically as one logical change set):

```bash
# Production code renamed
grep -qF 'GRAPH_WIKI_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py
! grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py

# Test renamed
grep -qF '"GRAPH_WIKI_LOCK_TIMEOUT_MS": "200"' packages/graph-io/tests/test_cli_exit_codes.py
! grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/tests/test_cli_exit_codes.py

# Tests still pass
uv run --package graph-io pytest packages/graph-io/tests/test_cli_exit_codes.py -q

# Smoke check the new env var
GRAPH_WIKI_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 5000'

# Old env var is ignored (returns default)
unset GRAPH_WIKI_LOCK_TIMEOUT_MS
LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 30000'
```

All assertions exit 0.
</verification>
