---
plan_id: "34-02"
phase: 34
wave: 2
depends_on: ["34-01"]
files_modified:
  - packages/graph-io/README.md
  - packages/graph-io/tests/test_sync_wiki.py
  - packages/graph-io/tests/test_cli_sync_wiki.py
autonomous: true
requirements:
  - BRAND-01
  - BRAND-02
  - BRAND-04
must_haves:
  truths:
    - "README.md first line is `# graph-io` (D-01)"
    - "README.md tagline second-line tagline reads `Code-graph backend for graph-wiki. Owns:` with no markdown link (D-02)"
    - "README.md bullet 1 (SQLite path) replaces `<repo>/.lattice/graph/code.db` with prose pointing at workspace_io.paths.graph_dir() per D-03"
    - "README.md `plugins/lattice-graph/` reference is rebranded to `plugins/graph-wiki/` (D-04, RESEARCH F-04)"
    - "test_sync_wiki.py fixture rebrands `tmp_path / 'lattice'` → `tmp_path / 'graph-wiki'` and `.lattice.yaml` → `.graph-wiki.yaml` (D-11, RESEARCH F-05)"
    - "test_cli_sync_wiki.py fixture rebrands `lattice/.lattice.yaml` → `graph-wiki/.graph-wiki.yaml` (D-11)"
    - "All 8 tests in test_sync_wiki.py still pass; all 4+ tests in test_cli_sync_wiki.py still pass"
  goal_check: |
    head -1 packages/graph-io/README.md | grep -qE '^# graph-io$' && \
    ! grep -qF 'lattice' packages/graph-io/README.md && \
    ! grep -qF 'lattice' packages/graph-io/tests/test_sync_wiki.py && \
    ! grep -qF 'lattice' packages/graph-io/tests/test_cli_sync_wiki.py && \
    uv run --package graph-io pytest packages/graph-io/tests/test_sync_wiki.py packages/graph-io/tests/test_cli_sync_wiki.py -q
---

# Plan 34-02: README.md + sync-wiki test fixture rebrand

<objective>
Rebrand all `lattice` brand text in `packages/graph-io/README.md` and in the two sync-wiki test
files (`test_sync_wiki.py`, `test_cli_sync_wiki.py`). These files contain only brand text + stale
fixture data — no functional code is affected (RESEARCH F-05 confirms `.lattice.yaml` fixtures are
not read by `sync_wiki.run()`; the functional manifest is `.graph-wiki.yaml`).

This plan groups README + sync-wiki test fixtures together because both are pure documentation /
test-data edits with no production-code coupling.
</objective>

<tasks>

<task id="34-02-T1">
<title>Rebrand packages/graph-io/README.md (4 lines)</title>
<read_first>
  - packages/graph-io/README.md (current state — full file, 43 lines)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-01..D-04, §specifics for diff prototype)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-04 — line 12 plugin path; F-03 — full inventory)
  - packages/workspace-io/src/workspace_io/paths.py (verify `graph_dir` helper signature for the D-03 prose reference)
</read_first>
<action>
Edit `packages/graph-io/README.md`. Apply exactly these four replacements (all four are brand text;
no functional behavior changes):

1. **Line 1** — change `# lattice-graph-core` to `# graph-io` (D-01).
2. **Line 3** — change `Code-graph core for the [lattice](../../README.md) ecosystem. Owns:` to
   `Code-graph backend for graph-wiki. Owns:` (D-02; strip the markdown link).
3. **Line 5** — change the bullet `- SQLite schema + store at \`<repo>/.lattice/graph/code.db\``
   to `- SQLite schema + store at \`<paths.graph_dir(workspace)>/code.db\` (see \`workspace_io.paths\` for workspace-mode-aware resolution)` (D-03; prose replaces hardcoded path).
4. **Line 12** — change `The Claude Code plugin shell lives separately at \`plugins/lattice-graph/\`.` to
   `The Claude Code plugin shell lives separately at \`plugins/graph-wiki/\`.` (D-04, RESEARCH F-04;
   the actual plugin path is `plugins/graph-wiki/`).

Do NOT modify any other lines in the README. Karpathy-clean: surgical changes only.
</action>
<acceptance_criteria>
  - `head -1 packages/graph-io/README.md` outputs exactly `# graph-io`
  - `grep -c lattice packages/graph-io/README.md` outputs `0`
  - `grep -c LATTICE packages/graph-io/README.md` outputs `0`
  - `grep -qF 'Code-graph backend for graph-wiki. Owns:' packages/graph-io/README.md`
  - `grep -qF 'paths.graph_dir(workspace)' packages/graph-io/README.md`
  - `grep -qF 'plugins/graph-wiki/' packages/graph-io/README.md`
  - Line count unchanged: `wc -l < packages/graph-io/README.md` outputs `43`
</acceptance_criteria>
</task>

<task id="34-02-T2">
<title>Rebrand packages/graph-io/tests/test_sync_wiki.py fixture</title>
<read_first>
  - packages/graph-io/tests/test_sync_wiki.py (current state — confirm only the `workspace` fixture mentions lattice; lines 15 and 17)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-11, D-12 row 1 — `test_sync_wiki.py: Rebrand brand text in comments/docstrings; preserve any wiki-sync fixture paths that exercise the lattice/ prefix`)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-05 — `.lattice.yaml` is stale fixture, not functional)
</read_first>
<action>
Edit `packages/graph-io/tests/test_sync_wiki.py`. Replace exactly two lines in the `workspace`
fixture (lines 15 and 17):

1. Line 15 — change `ws = tmp_path / "lattice"` to `ws = tmp_path / "graph-wiki"`.
2. Line 17 — change `(ws / ".lattice.yaml").write_text("registered_plugins: []\n")` to
   `(ws / ".graph-wiki.yaml").write_text("registered_plugins: []\n")`.

Do NOT modify any test method bodies, assertions, or other lines. There are no `lattice/`-prefixed
fixture paths in this file that exercise `_SKIP_REPO_PREFIXES` (D-12 carve-out does not apply
here — verified RESEARCH F-05/F-06: that carve-out lives only in `test_packages.py`).
</action>
<acceptance_criteria>
  - `grep -c lattice packages/graph-io/tests/test_sync_wiki.py` outputs `0`
  - `grep -qF 'tmp_path / "graph-wiki"' packages/graph-io/tests/test_sync_wiki.py`
  - `grep -qF '.graph-wiki.yaml' packages/graph-io/tests/test_sync_wiki.py`
  - `uv run --package graph-io pytest packages/graph-io/tests/test_sync_wiki.py -q` exits 0 (all 8 tests pass)
</acceptance_criteria>
</task>

<task id="34-02-T3">
<title>Rebrand packages/graph-io/tests/test_cli_sync_wiki.py fixture</title>
<read_first>
  - packages/graph-io/tests/test_cli_sync_wiki.py (current state — confirm lattice refs are on lines 29 and 64 only)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-11, D-12 row 3 — `test_cli_sync_wiki.py: Rebrand any assertion against the cli description; preserve sync-wiki fixture data`)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-03 — full inventory)
</read_first>
<action>
Edit `packages/graph-io/tests/test_cli_sync_wiki.py`. Replace the literal string
`"lattice/.lattice.yaml"` with `"graph-wiki/.graph-wiki.yaml"` on lines 29 and 64.

These lines are dictionary keys in a `write_and_commit(..., {... }, "init")` fixture map — pure
brand text per RESEARCH F-05 (no test asserts against this path; it is a workspace marker that
the sync-wiki end-to-end smoke test creates but doesn't read). The CLI description string
assertion mentioned in D-12 row 3 is in `test_cli_exit_codes.py`, not this file — covered by
Plan 34-04.

Do NOT modify any other lines.
</action>
<acceptance_criteria>
  - `grep -c lattice packages/graph-io/tests/test_cli_sync_wiki.py` outputs `0`
  - `grep -cF 'graph-wiki/.graph-wiki.yaml' packages/graph-io/tests/test_cli_sync_wiki.py` outputs `2`
  - `uv run --package graph-io pytest packages/graph-io/tests/test_cli_sync_wiki.py -q` exits 0
</acceptance_criteria>
</task>

</tasks>

<verification>
After all three tasks complete:

```bash
# README is fully rebranded
head -1 packages/graph-io/README.md | grep -qE '^# graph-io$'
! grep -qE 'lattice|LATTICE' packages/graph-io/README.md

# Test fixtures are rebranded
! grep -qE 'lattice|LATTICE' packages/graph-io/tests/test_sync_wiki.py
! grep -qE 'lattice|LATTICE' packages/graph-io/tests/test_cli_sync_wiki.py

# Tests still pass
uv run --package graph-io pytest packages/graph-io/tests/test_sync_wiki.py packages/graph-io/tests/test_cli_sync_wiki.py -q
```

All five assertions exit 0.
</verification>
