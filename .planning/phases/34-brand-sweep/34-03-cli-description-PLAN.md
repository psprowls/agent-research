---
plan_id: "34-03"
phase: 34
wave: 2
depends_on: ["34-01"]
files_modified:
  - packages/graph-io/src/graph_io/cli/main.py
  - packages/graph-io/src/graph_io/packages.py
  - packages/graph-io/tests/test_packages.py
autonomous: true
requirements:
  - BRAND-02
  - BRAND-04
must_haves:
  truths:
    - "cli/main.py line 45 description string reads `graph-wiki code graph CLI` (D-05)"
    - "`cg --help` output contains `graph-wiki` and does NOT contain `lattice` in any user-visible string (SC#1)"
    - "packages.py: `_SKIP_REPO_PREFIXES` and the rel-prefix check in `_should_skip` are deleted (D-16 revised). `_should_skip` reduces to delegating to `_ignore.should_skip`."
    - "test_packages.py: `test_refresh_skips_lattice_dir_manifests` is deleted (D-12 revised). All remaining tests pass."
    - "After this plan, `grep -rE 'lattice|LATTICE' packages/graph-io/src/graph_io/cli/main.py packages/graph-io/src/graph_io/packages.py packages/graph-io/tests/test_packages.py` returns zero hits."
  goal_check: |
    grep -qF 'description="graph-wiki code graph CLI"' packages/graph-io/src/graph_io/cli/main.py && \
    uv run cg --help 2>&1 | grep -qF 'graph-wiki' && \
    ! (uv run cg --help 2>&1 | grep -qiF 'lattice') && \
    ! grep -qF '_SKIP_REPO_PREFIXES' packages/graph-io/src/graph_io/packages.py && \
    ! grep -qF 'test_refresh_skips_lattice_dir_manifests' packages/graph-io/tests/test_packages.py && \
    uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -q
---

# Plan 34-03: cli/main.py description + packages.py skip-prefix removal + test_packages.py cleanup

<objective>
Three coupled edits that together leave `packages/graph-io/` with zero `lattice`/`LATTICE`
references in the touched files:

1. Rebrand the argparse `description` string in `cli/main.py` so `cg --help` reports the
   graph-wiki brand (D-05, SC#1).
2. Delete `_SKIP_REPO_PREFIXES = ("lattice/",)` and the rel-prefix check in `_should_skip()`
   from `packages.py` (D-16 revised). The function targeted a `lattice/` vendor directory that
   does not exist in this repo; `.cgignore` covers any user-driven exclusion need.
3. Delete `test_refresh_skips_lattice_dir_manifests` from `test_packages.py` (D-12 revised) —
   the function it exercised no longer exists.

These are coupled because deleting `_SKIP_REPO_PREFIXES` without deleting the test would break
the test; deleting the test without removing the dead code would leave a grep hit. They land
atomically.
</objective>

<tasks>

<task id="34-03-T1">
<title>Edit cli/main.py argparse description string</title>
<read_first>
  - packages/graph-io/src/graph_io/cli/main.py (confirm line 45 is the parser construction)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-05)
</read_first>
<action>
Edit `packages/graph-io/src/graph_io/cli/main.py`. Replace exactly one substring inside the
`_build_parser()` function:

- `description="lattice code graph CLI"` → `description="graph-wiki code graph CLI"`

Single-character-precision edit. Do NOT touch `_SUBCOMMANDS`, help strings, argparse arguments,
or any other code in the file.
</action>
<acceptance_criteria>
  - `grep -qF 'description="graph-wiki code graph CLI"' packages/graph-io/src/graph_io/cli/main.py`
  - `! grep -qF 'description="lattice code graph CLI"' packages/graph-io/src/graph_io/cli/main.py`
  - `uv run cg --help 2>&1` exits 0 AND contains the substring `graph-wiki`
  - `uv run cg --help 2>&1 | grep -ciF 'lattice'` outputs `0`
  - File diff shows exactly one changed line for this edit.
</acceptance_criteria>
</task>

<task id="34-03-T2">
<title>Delete _SKIP_REPO_PREFIXES and the rel-prefix check in _should_skip()</title>
<read_first>
  - packages/graph-io/src/graph_io/packages.py (lines 17 and 20-27)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-16 revised — delete, not allowlist)
</read_first>
<action>
Edit `packages/graph-io/src/graph_io/packages.py`. Apply two deletions:

1. **Line 17 (and the surrounding blank lines)** — delete `_SKIP_REPO_PREFIXES = ("lattice/",)`.
2. **Lines 23-27** — inside `_should_skip()`, delete the `try/except ValueError` block and the
   `return any(rel.startswith(p) for p in _SKIP_REPO_PREFIXES)` line. Replace with `return False`.

The resulting function:

```python
def _should_skip(manifest_path: Path, repo_root: Path, skip_dirs: frozenset[str]) -> bool:
    if _ignore.should_skip(str(manifest_path), skip_dirs):
        return True
    return False
```

Note: `repo_root` parameter is now unused by the function body, but keep it in the signature —
the caller in `refresh()` passes it positionally and removing the parameter would require an
additional call-site edit. Karpathy-clean: leave the parameter unused but in place; no other
callers exist.

Do NOT modify any other functions, imports, or the file's top docstring.
</action>
<acceptance_criteria>
  - `! grep -qF '_SKIP_REPO_PREFIXES' packages/graph-io/src/graph_io/packages.py`
  - `! grep -qE 'lattice|LATTICE' packages/graph-io/src/graph_io/packages.py`
  - The function `_should_skip` still exists and still takes 3 args:
    `grep -qE '^def _should_skip\(manifest_path: Path, repo_root: Path, skip_dirs: frozenset\[str\]\) -> bool:' packages/graph-io/src/graph_io/packages.py`
  - Module imports unchanged:
    `grep -q '^from graph_io import _ignore' packages/graph-io/src/graph_io/packages.py`
  - Module is syntactically valid:
    `uv run python -c 'from graph_io import packages' 2>&1` exits 0
</acceptance_criteria>
</task>

<task id="34-03-T3">
<title>Delete test_refresh_skips_lattice_dir_manifests from test_packages.py</title>
<read_first>
  - packages/graph-io/tests/test_packages.py (lines 112-126 — the test to delete; verify nothing in
    the rest of the file mentions `lattice` outside this method)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-12 revised; D-16 revised — the function under
    test is gone, the test goes with it)
</read_first>
<action>
Edit `packages/graph-io/tests/test_packages.py`. Delete the entire function
`test_refresh_skips_lattice_dir_manifests` (lines 112-126, including its leading blank line
and the blank line after `assert "tool" not in names`). The surrounding tests
(`test_refresh_skips_cgignore_manifests` and others) are unaffected.

After deletion, the file has zero `lattice`/`LATTICE` references. If `grep -nE 'lattice|LATTICE'
packages/graph-io/tests/test_packages.py` returns ANY hit after this edit, stop and report the
hit — it indicates a stray reference outside the deleted function that this plan did not catch.

Do NOT modify any other tests, imports, or fixtures in the file.
</action>
<acceptance_criteria>
  - The deleted function is gone:
    `! grep -qF 'test_refresh_skips_lattice_dir_manifests' packages/graph-io/tests/test_packages.py`
  - The surviving cgignore test is still present:
    `grep -qF 'test_refresh_skips_cgignore_manifests' packages/graph-io/tests/test_packages.py`
  - Whole-file lattice grep is clean:
    `grep -cE 'lattice|LATTICE' packages/graph-io/tests/test_packages.py` outputs `0`
  - All remaining tests pass:
    `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -q` exits 0
</acceptance_criteria>
</task>

</tasks>

<verification>
After all three tasks complete (committed atomically — the packages.py deletion and the
test_packages.py deletion MUST land together or the test suite will fail):

```bash
# CLI description rebranded
grep -qF 'description="graph-wiki code graph CLI"' packages/graph-io/src/graph_io/cli/main.py
uv run cg --help | grep -qF 'graph-wiki'
! (uv run cg --help | grep -qiF 'lattice')

# Dead code deleted
! grep -qF '_SKIP_REPO_PREFIXES' packages/graph-io/src/graph_io/packages.py
! grep -qE 'lattice|LATTICE' packages/graph-io/src/graph_io/packages.py

# Test cleaned up
! grep -qF 'test_refresh_skips_lattice_dir_manifests' packages/graph-io/tests/test_packages.py
! grep -qE 'lattice|LATTICE' packages/graph-io/tests/test_packages.py

# Tests still pass
uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -q
```

All seven assertions exit 0.
</verification>
