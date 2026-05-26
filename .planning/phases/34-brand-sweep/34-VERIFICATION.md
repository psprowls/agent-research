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
