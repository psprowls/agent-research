---
plan_id: "34-03"
phase: 34
wave: 2
depends_on: ["34-01"]
files_modified:
  - packages/graph-io/src/graph_io/cli/main.py
  - packages/graph-io/tests/test_packages.py
autonomous: true
requirements:
  - BRAND-02
  - BRAND-04
must_haves:
  truths:
    - "cli/main.py line 45 description string reads `graph-wiki code graph CLI` (D-05)"
    - "`cg --help` output contains `graph-wiki` and does NOT contain `lattice` in any user-visible string (SC#1)"
    - "test_packages.py: brand-text mentions rebranded; `test_refresh_skips_lattice_dir_manifests` and its `lattice/` fixture literals are preserved verbatim (D-12, RESEARCH F-06)"
    - "All tests in test_packages.py still pass"
  goal_check: |
    grep -qF 'description="graph-wiki code graph CLI"' packages/graph-io/src/graph_io/cli/main.py && \
    uv run cg --help 2>&1 | grep -qF 'graph-wiki' && \
    ! (uv run cg --help 2>&1 | grep -qiF 'lattice') && \
    uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -q
---

# Plan 34-03: cli/main.py argparse description + test_packages.py brand-text

<objective>
Edit the top-level argparse `description` string in `cli/main.py` so `cg --help` reports the
graph-wiki brand (D-05, SC#1). Rebrand brand-text mentions in `test_packages.py` while preserving
the functional carve-out (`test_refresh_skips_lattice_dir_manifests` — RESEARCH F-06, D-12 row 2).

This plan groups these two files together because the `cli/main.py` edit is one character-precision
line change and the `test_packages.py` rebrand is a surgical sweep with a clearly-scoped carve-out;
neither needs a dedicated plan and both touch BRAND-02 / BRAND-04 surfaces.
</objective>

<tasks>

<task id="34-03-T1">
<title>Edit cli/main.py argparse description string</title>
<read_first>
  - packages/graph-io/src/graph_io/cli/main.py (current state — confirm line 45 is the parser construction; verify Phase 33 has NOT yet edited lines 28-45, or if it has, that line 45 remains the parser description per RESEARCH F-10)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-05, §specifics for diff)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-10 — Phase 33 disjointness confirmed)
</read_first>
<action>
Edit `packages/graph-io/src/graph_io/cli/main.py`. Replace exactly one substring inside the
`_build_parser()` function:

- `description="lattice code graph CLI"` → `description="graph-wiki code graph CLI"`

This is a single-character-precision edit. Do NOT touch the `_SUBCOMMANDS` dict above (Phase 33
territory), help strings, argparse arguments, or any other code in the file.
</action>
<acceptance_criteria>
  - `grep -qF 'description="graph-wiki code graph CLI"' packages/graph-io/src/graph_io/cli/main.py`
  - `! grep -qF 'description="lattice code graph CLI"' packages/graph-io/src/graph_io/cli/main.py`
  - `uv run cg --help 2>&1` exits 0 AND contains the substring `graph-wiki`
  - `uv run cg --help 2>&1 | grep -ciF 'lattice'` outputs `0` (no user-visible lattice text)
  - File diff shows exactly one changed line: `git diff --numstat packages/graph-io/src/graph_io/cli/main.py | awk '{print $1, $2}'` shows `1 1`
</acceptance_criteria>
</task>

<task id="34-03-T2">
<title>Rebrand test_packages.py brand text while preserving the _SKIP_REPO_PREFIXES test verbatim</title>
<read_first>
  - packages/graph-io/tests/test_packages.py (current state — focus on lines 112-126 which contain `test_refresh_skips_lattice_dir_manifests`)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-11, D-12 row 2 — `PRESERVE _SKIP_REPO_PREFIXES test that asserts lattice/ filtering`)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-06 — the carve-out test is the ONLY method that keeps lattice literals)
  - packages/graph-io/src/graph_io/packages.py (verify `_SKIP_REPO_PREFIXES = ("lattice/",)` is the functional filter being tested)
</read_first>
<action>
Edit `packages/graph-io/tests/test_packages.py`. Apply the following carve-out rule:

**PRESERVE verbatim** (do NOT modify):
- The function name `test_refresh_skips_lattice_dir_manifests` (line 112).
- All string literals inside that function body that contain `"lattice"` or `"lattice/"` —
  specifically `tmp_path / "lattice" / "some-tool"` on line 113 and the surrounding test logic
  (lines 112-126). These exercise the BRAND-04-excluded `_SKIP_REPO_PREFIXES = ("lattice/",)`
  functional filter (PITFALLS.md). Modifying them would break the assertion that
  `packages.refresh()` skips `lattice/*` manifests.

**REBRAND** any OTHER brand-text mentions of `lattice` / `LATTICE` in the file — for example
docstrings, comments, or test-data fixtures that do NOT exercise `_SKIP_REPO_PREFIXES`. Use
`graph-wiki` as the replacement brand. If there are NO such other mentions (likely: the only
lattice references in this file are in `test_refresh_skips_lattice_dir_manifests`), make NO
edits to the file in this task — and document that conclusion in the commit message.

The file's allowlist entry (added by Plan 34-01: `packages/graph-io/tests/test_packages.py`)
covers the surviving `lattice/` literals so `scripts/check-brand.sh` will not flag them.
</action>
<acceptance_criteria>
  - The function `test_refresh_skips_lattice_dir_manifests` still exists verbatim:
    `grep -qE '^def test_refresh_skips_lattice_dir_manifests' packages/graph-io/tests/test_packages.py`
  - The fixture literal is preserved:
    `grep -qF 'tmp_path / "lattice" / "some-tool"' packages/graph-io/tests/test_packages.py`
  - All `lattice` occurrences in the file are inside the body of `test_refresh_skips_lattice_dir_manifests`
    (verify by inspecting `grep -n lattice packages/graph-io/tests/test_packages.py` — every hit line
    number must be between the function's `def` line and its closing line; if there are hits OUTSIDE
    that function, they must have been rebranded by this task)
  - `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -q` exits 0 (all tests pass, including the carve-out test)
  - `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py::test_refresh_skips_lattice_dir_manifests -q` exits 0 (the functional carve-out is intact)
</acceptance_criteria>
</task>

</tasks>

<verification>
After both tasks complete:

```bash
# CLI description rebranded
grep -qF 'description="graph-wiki code graph CLI"' packages/graph-io/src/graph_io/cli/main.py
uv run cg --help | grep -qF 'graph-wiki'
! (uv run cg --help | grep -qiF 'lattice')

# test_packages.py carve-out preserved
grep -qE '^def test_refresh_skips_lattice_dir_manifests' packages/graph-io/tests/test_packages.py

# Tests still pass
uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -q
```

All four assertions exit 0.
</verification>
