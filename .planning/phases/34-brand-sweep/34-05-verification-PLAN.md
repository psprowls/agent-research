---
plan_id: "34-05"
phase: 34
wave: 3
depends_on: ["34-01", "34-02", "34-03", "34-04"]
files_modified:
  - .planning/phases/34-brand-sweep/34-VERIFICATION.md
autonomous: true
requirements:
  - BRAND-01
  - BRAND-02
  - BRAND-03
  - BRAND-04
must_haves:
  truths:
    - "scripts/check-brand.sh exits 0 on the post-sweep tree (SC#4)"
    - "VERIFICATION.md captures the four SC checks in the order D-18 specifies"
    - "All four SC checks are fully automated — no manual scenarios (D-14 revised)"
    - "Every BRAND-01..BRAND-04 requirement has at least one verification step bound to it"
    - "Full graph-io pytest suite passes"
    - "packages/graph-io/ is grep-clean of lattice|LATTICE post-sweep"
  goal_check: |
    bash scripts/check-brand.sh && \
    uv run --package graph-io pytest packages/graph-io -q && \
    test -f .planning/phases/34-brand-sweep/34-VERIFICATION.md && \
    grep -qF 'SC#1' .planning/phases/34-brand-sweep/34-VERIFICATION.md && \
    grep -qF 'SC#2' .planning/phases/34-brand-sweep/34-VERIFICATION.md && \
    grep -qF 'SC#3' .planning/phases/34-brand-sweep/34-VERIFICATION.md && \
    grep -qF 'SC#4' .planning/phases/34-brand-sweep/34-VERIFICATION.md
---

# Plan 34-05: Verification — fully-automated gate + VERIFICATION.md

<objective>
Wave-3 verification plan. Runs after the four sweep plans (34-01 allowlist + 34-02/03/04 edits)
so the tree is in its final state. Produces `34-VERIFICATION.md` capturing the four SC checks
from CONTEXT D-18 (revised); all four are fully automated. The original 3 manual deprecation
scenarios from D-14 are dropped — there is no alias to verify (D-08/D-09/D-14 revised).

This plan also runs the BRAND-04 grep gate (SC#4) and the full graph-io pytest suite to confirm
no regressions before phase-verify can mark Phase 34 complete.
</objective>

<tasks>

<task id="34-05-T1">
<title>Write VERIFICATION.md with the four automated SC checks</title>
<read_first>
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-18 revised — the exact verification commands; D-14 revised — no manual scenarios)
  - .planning/ROADMAP.md (Phase 34 Success Criteria block — confirm SC literal text)
</read_first>
<action>
Create `.planning/phases/34-brand-sweep/34-VERIFICATION.md` with the following content. Operator
fills in pass/fail markers at phase-verify time; all four checks are runnable in a single shell
session.

```markdown
# Phase 34: Brand Sweep — Verification

**Status:** Pending operator execution
**Order:** Run sections in the order they appear (D-18 revised).

All four SC checks are fully automated. There are no manual scenarios; the alias-with-warning
contract from the original Phase 34 design was dropped (single-user repo, no backwards
compatibility required).

## SC#1 — `cg --help` brand check (BRAND-02)

Goal: `cg --help` output contains "graph-wiki" and does NOT contain "lattice" in any
user-visible string.

```bash
uv run cg --help | grep -qF 'graph-wiki'                 # must exit 0
uv run cg --help | grep -ciF 'lattice'                   # must output 0
```

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## SC#2 — README.md brand check (BRAND-01)

Goal: first line is `# graph-io`; the hardcoded `~/.lattice/graph/code.db` path is gone; the
README contains zero `lattice`/`LATTICE` references.

```bash
test "$(head -1 packages/graph-io/README.md)" = '# graph-io'                 # must exit 0
! grep -qF '~/.lattice/graph/code.db' packages/graph-io/README.md            # must exit 0
grep -qF 'paths.graph_dir(workspace)' packages/graph-io/README.md            # must exit 0 (per D-03)
! grep -qE 'lattice|LATTICE' packages/graph-io/README.md                     # must exit 0
```

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## SC#3 — Env var rename (BRAND-03)

Goal: `GRAPH_WIKI_LOCK_TIMEOUT_MS` is the only env var that controls the lock timeout; the old
`LATTICE_GRAPH_LOCK_TIMEOUT_MS` name is gone from the codebase entirely (no alias, no warning).

```bash
# New env var name is read by the production code
grep -qF 'os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")' packages/graph-io/src/graph_io/update.py

# Old env var name has zero occurrences in graph-io
! grep -rqE 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/

# The CLI exit-code test passes with the new env var name
uv run --package graph-io pytest packages/graph-io/tests/test_cli_exit_codes.py -q

# Setting the new env var changes the timeout
GRAPH_WIKI_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 5000'

# Setting the old env var does NOT change the timeout (returns default)
unset GRAPH_WIKI_LOCK_TIMEOUT_MS
LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 30000'
```

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## SC#4 — Brand grep gate + graph-io grep-cleanliness (BRAND-04)

Goal: `scripts/check-brand.sh` exits 0; `packages/graph-io/` has zero `lattice|LATTICE` matches
after the sweep; `.brand-grep-allow` does NOT contain any `packages/graph-io/` entry.

```bash
bash scripts/check-brand.sh                                                  # must exit 0
test -f .brand-grep-allow                                                    # must exit 0

# Packages/graph-io/ is grep-clean of lattice|LATTICE (no allowlist needed for it)
! grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' 'lattice|LATTICE' packages/graph-io/

# Allowlist does NOT contain a graph-io carve-out (the sweep eliminates all hits there)
! grep -q '^packages/graph-io/' .brand-grep-allow
```

**Note on allowlist form (RESEARCH F-08):** entries are file-path substrings (matched against
`grep -rEl` output), not content substrings. The post-sweep allowlist covers the workspace_io
package, source-parser/eval-harness ported-from comments, the wiki-io fixture vault,
cross-package workspace_io imports, .planning historical docs, and CLAUDE.md.

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## Regression check — full graph-io test suite

```bash
uv run --package graph-io pytest packages/graph-io -q                        # must exit 0
```

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## Sign-off

When all five sections above are PASS, mark Phase 34 ready for phase-verify. Every check is
automated — verification is a single shell session.
```

Do NOT inline pass/fail markers — leave them blank (`[ ]`) for the operator. Do NOT add the
three old manual deprecation scenarios; per D-14 revised they are dropped along with the alias.
</action>
<acceptance_criteria>
  - File exists: `test -f .planning/phases/34-brand-sweep/34-VERIFICATION.md`
  - Contains all four SC headers (one per SC):
    - `grep -qE '^## SC#1' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `grep -qE '^## SC#2' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `grep -qE '^## SC#3' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `grep -qE '^## SC#4' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
  - Does NOT contain any of the old manual deprecation scenarios:
    - `! grep -qF 'Scenario A: only the deprecated var is set' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `! grep -qF 'Scenario B: both env vars set' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `! grep -qF 'Scenario C: only the new env var set' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
  - Contains the regression-check section: `grep -qF 'uv run --package graph-io pytest' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
</acceptance_criteria>
</task>

<task id="34-05-T2">
<title>Run the BRAND-04 grep gate + full test suite + assert post-sweep cleanliness</title>
<read_first>
  - .brand-grep-allow (final post-sweep state; created by Plan 34-01)
  - scripts/check-brand.sh (read once to confirm the invocation contract)
  - .planning/phases/34-brand-sweep/34-VERIFICATION.md (the SC checks just written by T1)
</read_first>
<action>
Run the following commands in order and capture exit codes. All four SC checks plus the
regression suite are automated; if any exits non-zero, STOP and report the failure — the phase
cannot ship.

```bash
# SC#1
uv run cg --help | grep -qF 'graph-wiki'
[ "$(uv run cg --help 2>&1 | grep -ciF 'lattice')" = "0" ]

# SC#2
test "$(head -1 packages/graph-io/README.md)" = '# graph-io'
! grep -qF '~/.lattice/graph/code.db' packages/graph-io/README.md
grep -qF 'paths.graph_dir(workspace)' packages/graph-io/README.md
! grep -qE 'lattice|LATTICE' packages/graph-io/README.md

# SC#3
grep -qF 'os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")' packages/graph-io/src/graph_io/update.py
! grep -rqE 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/
GRAPH_WIKI_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 5000'
unset GRAPH_WIKI_LOCK_TIMEOUT_MS
LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 uv run python -c 'from graph_io.update import _default_lock_timeout; assert _default_lock_timeout() == 30000'

# SC#4
bash scripts/check-brand.sh
! grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' 'lattice|LATTICE' packages/graph-io/ 2>/dev/null
! grep -q '^packages/graph-io/' .brand-grep-allow

# Regression
uv run --package graph-io pytest packages/graph-io -q
```
</action>
<acceptance_criteria>
  - `uv run cg --help 2>&1 | grep -qF 'graph-wiki'` exits 0
  - `uv run cg --help 2>&1 | grep -ciF 'lattice'` outputs `0`
  - `head -1 packages/graph-io/README.md` outputs exactly `# graph-io`
  - `grep -qE 'lattice|LATTICE' packages/graph-io/README.md` exits non-zero (no hits)
  - `grep -qF 'paths.graph_dir(workspace)' packages/graph-io/README.md` exits 0
  - `grep -rqE 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/` exits non-zero (no hits)
  - `grep -qF 'os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")' packages/graph-io/src/graph_io/update.py` exits 0
  - `bash scripts/check-brand.sh` exits 0
  - `grep -rEl 'lattice|LATTICE' packages/graph-io/` returns nothing (or exits non-zero)
  - `grep -q '^packages/graph-io/' .brand-grep-allow` exits non-zero (no graph-io carve-out)
  - `uv run --package graph-io pytest packages/graph-io -q` exits 0
</acceptance_criteria>
</task>

</tasks>

<verification>
This plan IS the verification plan; success means:

1. `.planning/phases/34-brand-sweep/34-VERIFICATION.md` exists with four automated SC sections
   and the regression-check section. Zero manual scenarios.
2. The full automated check from T2 passes: `cg --help` is rebranded; README is rebranded and
   grep-clean; `update.py` uses only the new env var name; `packages/graph-io/` is grep-clean of
   `lattice|LATTICE`; `bash scripts/check-brand.sh` exits 0; the full pytest suite passes.

After this plan completes, Phase 34 is in the "ready for /gsd:verify-phase 34" state.
</verification>
