---
phase: 12-drift-backport-ecosystem-rebrand-m2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/wiki-io/DRIFT-DECISIONS-RAW.md
  - scripts/drift-diff.sh
autonomous: true
requirements:
  - BACKPORT-01
  - BACKPORT-02
  - BACKPORT-03
  - BACKPORT-04
must_haves:
  truths:
    - "Future-Pat can read a single file (DRIFT-DECISIONS-RAW.md) and see every body diff between wiki-io and lattice-wiki-core for all 11 overlapping module rows from spike 002 §A."
    - "The upstream commit SHA at diff time is pinned in the file header so the diff is auditable and reproducible."
    - "Diff generation is scripted (not hand-run) so a future re-sync can regenerate the dump by bumping the SHA and re-running the script."
  artifacts:
    - path: "packages/wiki-io/DRIFT-DECISIONS-RAW.md"
      provides: "Per-file unified diff dump of all 11 overlapping spike-table module rows vs upstream lattice-wiki-core @ pinned SHA. `lint/*` is a single collapsed section that dumps all 8 lint sub-file diffs inline."
      contains: "1b45172a9900842b0f8eea525c8270e7fff50605"
    - path: "scripts/drift-diff.sh"
      provides: "Reproducible diff generator (re-runnable on future upstream-bump syncs)"
  key_links:
    - from: "packages/wiki-io/DRIFT-DECISIONS-RAW.md"
      to: "/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/*"
      via: "diff -u (pinned SHA in header)"
      pattern: "1b45172a9900842b0f8eea525c8270e7fff50605"
---

<objective>
P-A (per CONTEXT.md SQ-01.1): scripted raw diff dump. Produce `packages/wiki-io/DRIFT-DECISIONS-RAW.md` containing per-file `diff -u` output between every overlapping wiki-io module and its upstream `lattice-wiki-core` counterpart at the pinned SHA. No verdicts, no judgment — just the diffs. P-B reads this file to assign verdicts and land backports.

The canonical module set is the **11-row table in spike 002 §Investigation A "Overlapping modules"** with `lint/*` collapsed as a single row (operator decision on Blocker #1). The 11 rows are: `git_state.py`, `append_log.py`, `update_index.py`, `update_tokens.py`, `ingest_work_item.py`, `init_vault.py`, `lint/*` (one row covering 8 sub-files), `layout_io.py`, `detect_containers.py`, `scan_monorepo.py`, `ingest_source.py`. DRIFT-DECISIONS-RAW.md emits exactly 11 top-level `### ` sections matching that list; the `### lint/*` section contains all 8 lint sub-file diffs dumped inline beneath it.

Purpose: separates mechanical diff generation (this plan) from human verdict assignment (next plan), so the diff is auditable and the verdict step has 100% of its source material on disk before judgment begins.

Output: `packages/wiki-io/DRIFT-DECISIONS-RAW.md` (per D-03/D-04) and a reusable generator script.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md
@.planning/spikes/002-lattice-drift-inventory/README.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write scripts/drift-diff.sh — reproducible 11-row diff generator (lint/* collapsed)</name>
  <files>scripts/drift-diff.sh</files>
  <read_first>
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (DD-01, DD-03, DD-04 — pinned SHA 1b45172a9900842b0f8eea525c8270e7fff50605; the 11-row spike-table module list)
    - .planning/spikes/002-lattice-drift-inventory/README.md §Investigation A "Overlapping modules" (the canonical 11-row table — operator confirmed this is the source-of-truth module set)
    - packages/wiki-io/src/wiki_io/ (confirm local file paths)
    - /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ (confirm upstream file paths)
  </read_first>
  <action>
    Create `scripts/drift-diff.sh` (executable; `chmod +x`). Script behavior:

    - Pin variable UPSTREAM_SHA=1b45172a9900842b0f8eea525c8270e7fff50605 at top.
    - Pin UPSTREAM_REPO=/Users/pat/Personal/lattice.
    - Pin UPSTREAM_PKG_REL=packages/lattice-wiki-core/src/lattice_wiki_core.
    - Pin LOCAL_PKG_REL=packages/wiki-io/src/wiki_io.
    - Verify the upstream repo HEAD matches UPSTREAM_SHA (fail loudly with a clear message if it does not — instruct the operator to `git -C "$UPSTREAM_REPO" checkout 1b45172a9900842b0f8eea525c8270e7fff50605` or to bump UPSTREAM_SHA explicitly).

    Define the canonical row list as an ordered bash array `MODULES` with exactly 11 entries (matching spike 002 §A row order). For each row, the script emits a single `### <row-id>` top-level section heading, then dumps one or more diffs beneath it:

    Row layout (operator decision on B1):
    ```
    MODULES=(
      "git_state.py"
      "append_log.py"
      "update_index.py"
      "update_tokens.py"
      "ingest_work_item.py"
      "init_vault.py"
      "lint/*"
      "layout_io.py"
      "detect_containers.py"
      "scan_monorepo.py"
      "ingest_source.py"
    )
    LINT_FILES=(
      "lint/common.py"
      "lint/container.py"
      "lint/dependency.py"
      "lint/domain.py"
      "lint/file_map.py"
      "lint/package_sync.py"
      "lint/source_sync.py"
      "lint/workflow_hints.py"
    )
    ```

    For each entry in `MODULES`:
    - If the entry is `lint/*`: emit `### lint/*` heading, then for EACH file in `LINT_FILES` emit a sub-heading `#### <relpath>` followed by a fenced ```diff block containing `diff -u "$UPSTREAM_REPO/$UPSTREAM_PKG_REL/<relpath>" "$LOCAL_PKG_REL/<relpath>"` output (or `IDENTICAL` marker if diff exit code is 0). All 8 sub-file diffs are dumped inline under the single `### lint/*` row.
    - Otherwise: emit `### <relpath>` heading followed by a fenced ```diff block containing `diff -u "$UPSTREAM_REPO/$UPSTREAM_PKG_REL/<relpath>" "$LOCAL_PKG_REL/<relpath>"` output. If `diff` exit code is 0 (byte-identical), emit `IDENTICAL` instead of an empty fence.

    (Per CONTEXT.md domain note: spike 002 §A lists these 11 overlapping module rows. `lint/__init__.py` is empty in both and excluded from `LINT_FILES`.)

    - Emit a header block at the top of stdout: title, pinned SHA, diff date (use `date -u +%Y-%m-%dT%H:%M:%SZ`), command-invocation provenance.
    - Print everything to stdout; the caller redirects to the target file. Script must be idempotent (no in-place writes from inside the script).
    - Use `set -euo pipefail`.
  </action>
  <verify>
    <automated>test -x scripts/drift-diff.sh &amp;&amp; bash -n scripts/drift-diff.sh &amp;&amp; grep -q '1b45172a9900842b0f8eea525c8270e7fff50605' scripts/drift-diff.sh &amp;&amp; for m in git_state.py append_log.py update_index.py update_tokens.py ingest_work_item.py init_vault.py 'lint/\*' layout_io.py detect_containers.py scan_monorepo.py ingest_source.py; do grep -qF "$m" scripts/drift-diff.sh || { echo "MISSING module entry in MODULES: $m"; exit 1; }; done &amp;&amp; for f in lint/common.py lint/container.py lint/dependency.py lint/domain.py lint/file_map.py lint/package_sync.py lint/source_sync.py lint/workflow_hints.py; do grep -qF "$f" scripts/drift-diff.sh || { echo "MISSING lint sub-file: $f"; exit 1; }; done</automated>
  </verify>
  <acceptance_criteria>
    - `scripts/drift-diff.sh` exists, is executable (`-x`), and passes `bash -n` syntax check.
    - File contains literal `1b45172a9900842b0f8eea525c8270e7fff50605` (SHA pin).
    - File contains a `MODULES` array with exactly 11 entries matching the spike-table row order: `git_state.py`, `append_log.py`, `update_index.py`, `update_tokens.py`, `ingest_work_item.py`, `init_vault.py`, `lint/*`, `layout_io.py`, `detect_containers.py`, `scan_monorepo.py`, `ingest_source.py`.
    - File references all 8 lint sub-file relpaths (`lint/common.py`, `lint/container.py`, `lint/dependency.py`, `lint/domain.py`, `lint/file_map.py`, `lint/package_sync.py`, `lint/source_sync.py`, `lint/workflow_hints.py`) inside the lint-iteration block.
    - File uses `set -euo pipefail`.
    - Script writes only to stdout; no in-place file writes.
  </acceptance_criteria>
  <done>Reproducible diff generator script committed with the 11-row collapsed-lint module set; can be re-run on future re-syncs by bumping the SHA pin.</done>
</task>

<task type="auto">
  <name>Task 2: Run drift-diff.sh and commit DRIFT-DECISIONS-RAW.md</name>
  <files>packages/wiki-io/DRIFT-DECISIONS-RAW.md</files>
  <read_first>
    - scripts/drift-diff.sh (the script created in Task 1)
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (DD-03 file-shape spec, DD-04 header pin requirement)
  </read_first>
  <action>
    Run `bash scripts/drift-diff.sh > packages/wiki-io/DRIFT-DECISIONS-RAW.md`. Verify the output file:
    - Has a top-level title (e.g., `# wiki-io ⟷ lattice-wiki-core Raw Drift Dump`).
    - Header contains the pinned SHA `1b45172a9900842b0f8eea525c8270e7fff50605` and an ISO-8601 UTC timestamp.
    - Contains exactly 11 `### ` top-level sections — one per overlapping module ROW from spike 002 §A. The `### lint/*` section contains 8 `#### <relpath>` sub-headings (one per lint sub-file) with their diffs dumped inline.
    - Each section (or lint sub-section) contains either an `IDENTICAL` marker or a ```diff fenced block with `diff -u` output.
    - Add a short prose preamble (3–6 lines) immediately under the title noting: source-of-truth role (per DD-03), regeneration command (`bash scripts/drift-diff.sh > packages/wiki-io/DRIFT-DECISIONS-RAW.md`), the 11-row + lint-collapsed structure, and a pointer to `packages/wiki-io/DRIFT-DECISIONS.md` (forthcoming in plan 02) as the human-verdict companion.

    Do NOT assign verdicts, write rationale, or land any code changes in this plan. This is the raw-diff capture step only. Spurious pytest-related acceptance criteria are intentionally removed from this task per checker W1 — this task writes a markdown file and runs a shell script; pytest is irrelevant.
  </action>
  <verify>
    <automated>head -30 packages/wiki-io/DRIFT-DECISIONS-RAW.md | grep -q '1b45172a9900842b0f8eea525c8270e7fff50605' &amp;&amp; test "$(grep -c '^### ' packages/wiki-io/DRIFT-DECISIONS-RAW.md)" -eq 11 &amp;&amp; for m in 'git_state.py' 'append_log.py' 'update_index.py' 'update_tokens.py' 'ingest_work_item.py' 'init_vault.py' 'lint/\*' 'layout_io.py' 'detect_containers.py' 'scan_monorepo.py' 'ingest_source.py'; do grep -qE "^### $m" packages/wiki-io/DRIFT-DECISIONS-RAW.md || { echo "MISSING top-level section: $m"; exit 1; }; done &amp;&amp; for f in lint/common.py lint/container.py lint/dependency.py lint/domain.py lint/file_map.py lint/package_sync.py lint/source_sync.py lint/workflow_hints.py; do grep -qF "$f" packages/wiki-io/DRIFT-DECISIONS-RAW.md || { echo "MISSING lint sub-file: $f"; exit 1; }; done</automated>
  </verify>
  <acceptance_criteria>
    - `packages/wiki-io/DRIFT-DECISIONS-RAW.md` exists.
    - `head -30 packages/wiki-io/DRIFT-DECISIONS-RAW.md | grep -q '1b45172a9900842b0f8eea525c8270e7fff50605'` succeeds (SHA pin in header).
    - `grep -c '^### ' packages/wiki-io/DRIFT-DECISIONS-RAW.md` equals exactly `11` (one top-level section per overlapping ROW from spike 002 §A).
    - The file contains a top-level section heading for each of: `git_state.py`, `append_log.py`, `update_index.py`, `update_tokens.py`, `ingest_work_item.py`, `init_vault.py`, `lint/*`, `layout_io.py`, `detect_containers.py`, `scan_monorepo.py`, `ingest_source.py`.
    - The `### lint/*` section contains inline diffs for all 8 lint sub-files: `lint/common.py`, `lint/container.py`, `lint/dependency.py`, `lint/domain.py`, `lint/file_map.py`, `lint/package_sync.py`, `lint/source_sync.py`, `lint/workflow_hints.py`.
    - No source code under `packages/wiki-io/src/` was modified by this task (verify with `git status`).
  </acceptance_criteria>
  <done>Raw diff dump committed at `packages/wiki-io/DRIFT-DECISIONS-RAW.md` with pinned SHA in header, all 11 row sections present, and all 8 lint sub-file diffs nested under the `### lint/*` row.</done>
</task>

</tasks>

<verification>
- `bash -n scripts/drift-diff.sh` succeeds.
- `head -30 packages/wiki-io/DRIFT-DECISIONS-RAW.md | grep '1b45172a9900842b0f8eea525c8270e7fff50605'` returns a hit.
- `grep -c '^### ' packages/wiki-io/DRIFT-DECISIONS-RAW.md` returns `11`.
- All 11 spike-table row names appear as top-level `### ` headings; all 8 lint sub-file names appear inside the `### lint/*` section.
- No `packages/wiki-io/src/` files modified by this plan.
</verification>

<success_criteria>
Raw drift dump artifact lives at `packages/wiki-io/DRIFT-DECISIONS-RAW.md`, contains all 11 overlapping module ROW diffs (with `lint/*` collapsed as 1 row containing 8 inline sub-file diffs), and pins the upstream SHA at `1b45172a9900842b0f8eea525c8270e7fff50605`. P-B (plan 02) can now read each diff and assign verdicts without re-running the diff command.
</success_criteria>

<output>
Create `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-01-SUMMARY.md` recording: SHA used, number of `### ` top-level sections produced (must be 11), list of any modules / lint sub-files that came back `IDENTICAL`, and a quick visual scan note for how large the diffs are per row (informs P-B sizing).
</output>
