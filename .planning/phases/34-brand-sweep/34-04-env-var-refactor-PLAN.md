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
    - "D-06: target env var name is GRAPH_WIKI_LOCK_TIMEOUT_MS (per SC#3 literal — not GRAPH_IO_LOCK_TIMEOUT_MS)"
    - "D-07: when both env vars are set, GRAPH_WIKI_LOCK_TIMEOUT_MS wins and stderr warns that LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated and ignored"
    - "D-08: when only the old var is set, its value is respected AND stderr warns once per invocation (no suppression mechanism)"
    - "D-09: _default_lock_timeout() refactor uses a sequential branch tree reading GRAPH_WIKI_LOCK_TIMEOUT_MS first then falling back to the deprecated alias"
    - "D-10: deprecation timeline — alias kept through v1.7; Phase 34 ships the alias + warning, NOT the removal (which happens in v1.8 or later)"
    - "D-13: existing env-var test refactor — test_cli_exit_codes.py sets GRAPH_WIKI_LOCK_TIMEOUT_MS=200 instead of LATTICE_GRAPH_LOCK_TIMEOUT_MS=200; lock-timeout assertion still passes"
    - "When only GRAPH_WIKI_LOCK_TIMEOUT_MS is set, no warning is emitted (silent acceptance)"
    - "Invalid values still fall back to 30000ms (preserves pre-Phase-34 behavior)"
    - "update.py and test_cli_exit_codes.py commit atomically (single change set), per D-Discretion item 5"
  goal_check: |
    uv run --package graph-io pytest packages/graph-io/tests/test_cli_exit_codes.py -q && \
    grep -qF 'GRAPH_WIKI_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py && \
    grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated' packages/graph-io/src/graph_io/update.py && \
    grep -qF '"GRAPH_WIKI_LOCK_TIMEOUT_MS": "200"' packages/graph-io/tests/test_cli_exit_codes.py
---

# Plan 34-04: update.py env-var refactor + test_cli_exit_codes.py rename (atomic)

<objective>
Rewrite `_default_lock_timeout()` in `update.py` per D-09: so it (a) prefers
`GRAPH_WIKI_LOCK_TIMEOUT_MS` (the target name fixed by D-06: per SC#3 literal — NOT a more
package-scoped `GRAPH_IO_LOCK_TIMEOUT_MS`), (b) accepts the deprecated
`LATTICE_GRAPH_LOCK_TIMEOUT_MS` with a stderr warning, and (c) emits a "deprecated and ignored"
warning when both are set. Atomically update the single existing test that exercises the old
var name (`test_cli_exit_codes.py:130`) per D-13: so CI passes immediately after this plan ships.

Per D-10: the deprecation alias ships in v1.6 (Phase 34) and is retained through v1.7; removal
happens in v1.8 or later. This plan SHIPS the alias + warning — it does NOT ship the removal.

D-Discretion item 5 requires that the production-code edit and the test edit land in the same
commit — they are coupled because the test currently sets `LATTICE_GRAPH_LOCK_TIMEOUT_MS=200`
and the new code still respects that value but ALSO emits a stderr warning; renaming the env
var in the test keeps the test asserting the silent-success path (no warning expected on stderr
when the new var is used).

Per RESEARCH F-02: `sys` is ALREADY imported in `update.py` (line 9). The D-09 code-snippet
imported `sys` defensively; this plan does NOT add a duplicate import.
</objective>

<tasks>

<task id="34-04-T1">
<title>Refactor _default_lock_timeout() in update.py per D-09</title>
<read_first>
  - packages/graph-io/src/graph_io/update.py (current state — focus on lines 1-20 to confirm `import sys` is on line 9 (per RESEARCH F-02), and lines 153-160 for the existing `_default_lock_timeout` body)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-06: target env var name; D-07: precedence when both set; D-08: deprecation warning text; D-09: full refactor code; D-10: deprecation timeline (alias kept through v1.7); also §specifics for the diff prototype)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-02 — `sys` already imported; F-07 — only one test exercises this code path)
</read_first>
<action>
Replace the body of `_default_lock_timeout()` (currently lines 153-160, the 6-line function that
reads `os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")` and returns 30_000 on missing/invalid).
The new body is exactly D-09's sequential-branch tree:

```python
def _default_lock_timeout() -> int:
    new = os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")
    old = os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")
    if new is not None and old is not None:
        print(
            f"warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated and "
            f"ignored; using GRAPH_WIKI_LOCK_TIMEOUT_MS={new}",
            file=sys.stderr,
        )
        raw = new
    elif new is not None:
        raw = new
    elif old is not None:
        print(
            f"warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated, "
            f"use GRAPH_WIKI_LOCK_TIMEOUT_MS instead (value={old} still respected)",
            file=sys.stderr,
        )
        raw = old
    else:
        return 30_000
    try:
        return max(0, int(raw))
    except ValueError:
        return 30_000
```

Do NOT add an `import sys` line — the module already imports `sys` on line 9. Do NOT factor a
`_resolve_env_alias()` helper — D-09 calls this out as premature (only one env var renamed in
v1.6). Do NOT modify any other function or import in the file.
</action>
<acceptance_criteria>
  - The function body matches D-09 verbatim:
    - `grep -qF 'os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")' packages/graph-io/src/graph_io/update.py`
    - `grep -qF 'os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")' packages/graph-io/src/graph_io/update.py`
    - `grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated and ignored; using GRAPH_WIKI_LOCK_TIMEOUT_MS=' packages/graph-io/src/graph_io/update.py`
    - `grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated, use GRAPH_WIKI_LOCK_TIMEOUT_MS instead (value=' packages/graph-io/src/graph_io/update.py`
    - `grep -qF 'file=sys.stderr' packages/graph-io/src/graph_io/update.py`
  - No duplicate `import sys` added:
    `grep -c '^import sys$' packages/graph-io/src/graph_io/update.py` outputs `1`
  - File still imports `os`:
    `grep -q '^import os$' packages/graph-io/src/graph_io/update.py`
  - Python module is still syntactically valid:
    `uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 30000' 2>&1` exits 0 with no stderr (when neither env var is set)
  - With only the new env var set, function returns the parsed value without warning:
    `GRAPH_WIKI_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 5000' 2>&1 | grep -c warning` outputs `0`
  - With only the old env var set, function returns the parsed value AND emits a stderr warning:
    `unset GRAPH_WIKI_LOCK_TIMEOUT_MS; LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 5000' 2>&1 | grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated'`
  - With both env vars set, new wins and "ignored" warning fires:
    `LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 GRAPH_WIKI_LOCK_TIMEOUT_MS=2000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 2000' 2>&1 | grep -qF 'deprecated and ignored; using GRAPH_WIKI_LOCK_TIMEOUT_MS=2000'`
</acceptance_criteria>
</task>

<task id="34-04-T2">
<title>Rename env var in test_cli_exit_codes.py per D-13</title>
<read_first>
  - packages/graph-io/tests/test_cli_exit_codes.py (focus on line 130 and the surrounding test method ~lines 100-150 to understand the test's intent)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-13 — single-string-replacement; test continues to assert timeout-respect behavior)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-07 — this is the only test referencing the env var)
</read_first>
<action>
Edit `packages/graph-io/tests/test_cli_exit_codes.py`. Replace exactly one substring on line 130:

- `"LATTICE_GRAPH_LOCK_TIMEOUT_MS": "200"` → `"GRAPH_WIKI_LOCK_TIMEOUT_MS": "200"`

The test continues to assert the lock-timeout-honored behavior (200ms timeout, `elapsed_ms <
5000`). By using the NEW env var name, the test exercises the silent-success branch of D-09 (no
stderr warning) — which is also the only branch with automated coverage (D-14 documents the
gap for the deprecation-warning branches).

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
After both tasks complete (committed atomically as one logical change set per D-Discretion item 5):

```bash
# Production code refactored
grep -qF 'GRAPH_WIKI_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py
grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated' packages/graph-io/src/graph_io/update.py

# Test renamed
grep -qF '"GRAPH_WIKI_LOCK_TIMEOUT_MS": "200"' packages/graph-io/tests/test_cli_exit_codes.py
! grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/tests/test_cli_exit_codes.py

# Tests still pass
uv run --package graph-io pytest packages/graph-io/tests/test_cli_exit_codes.py -q

# Smoke check the new env var
GRAPH_WIKI_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 5000'
```

All assertions exit 0.

**Note on the deprecation-warning paths (D-14, RESEARCH F-07):** the both-set and old-only-set
branches of `_default_lock_timeout()` are NOT covered by any automated test. Per D-14 this gap is
intentional; Plan 34-05 captures the three manual scenarios in VERIFICATION.md so the deprecation
contract is verified at phase-verify time.
</verification>
