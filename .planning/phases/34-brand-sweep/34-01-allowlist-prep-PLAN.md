---
plan_id: "34-01"
phase: 34
wave: 1
depends_on: []
files_modified:
  - .brand-grep-allow
autonomous: true
requirements:
  - BRAND-04
must_haves:
  truths:
    - ".brand-grep-allow exists at repo root with path-substring entries covering legitimate uses elsewhere in the codebase (workspace_io package itself, ported-from comments in source-parser and eval-harness, wiki-io test fixture vault, cross-package workspace_io imports, .planning historical docs, CLAUDE.md)"
    - "Zero entries under packages/graph-io/ — the sweep eliminates every match there (D-15 revised)"
    - "Entries are file-path substrings per check-brand.sh's `grep -vF -f` filtering (RESEARCH F-08)"
    - "scripts/check-brand.sh is NOT modified (D-17)"
  goal_check: |
    test -f .brand-grep-allow && \
    grep -q '^packages/workspace-io/$' .brand-grep-allow && \
    grep -q '^packages/source-parser/$' .brand-grep-allow && \
    grep -q '^packages/eval-harness/$' .brand-grep-allow && \
    grep -q '^packages/wiki-io/$' .brand-grep-allow && \
    grep -q '^packages/model-adapter/$' .brand-grep-allow && \
    grep -q '^agents/graph-wiki-agent/$' .brand-grep-allow && \
    grep -q '^plugins/graph-wiki/$' .brand-grep-allow && \
    grep -q '^\.planning/$' .brand-grep-allow && \
    grep -q '^CLAUDE\.md$' .brand-grep-allow && \
    ! grep -q '^packages/graph-io/' .brand-grep-allow
---

# Plan 34-01: Create `.brand-grep-allow` with broader-codebase carve-outs

<objective>
Create the `.brand-grep-allow` file at repo root with path-substring entries that allow
`scripts/check-brand.sh` to exit 0 post-sweep. The entries cover **legitimate uses elsewhere in
the codebase** (the workspace_io package itself, ported-from comments in source-parser and
eval-harness, wiki-io test fixture vault that preserves the historical lattice-* layout,
cross-package imports of workspace_io, `.planning/` historical milestone docs, and CLAUDE.md).

**Zero entries cover `packages/graph-io/`** — the rest of Phase 34's sweep eliminates every
`lattice|LATTICE` match there. The deprecation alias is gone (Plan 34-04), `_SKIP_REPO_PREFIXES`
is gone (Plan 34-03), and all brand text + fixture paths get rebranded (Plans 34-02, 34-03).

This plan runs FIRST (Wave 1) so the gate is *runnable* before Waves 2 trigger any post-edit
checks. Per D-17 the script itself is not modified.
</objective>

<tasks>

<task id="34-01-T1">
<title>Create .brand-grep-allow with the broader-codebase path-substring entries</title>
<read_first>
  - scripts/check-brand.sh (confirm the `grep -vF -f` invocation; entries match file paths, not content)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-15 revised — no Phase-34-specific entries; D-19 — the minimal allowlist content; D-17 — do NOT modify check-brand.sh)
</read_first>
<action>
Write a new file at `.brand-grep-allow` (repo root) containing exactly the following content, with
`#` comments and one blank line between groups:

```
# workspace_io package directory — the package is literally named workspace_io
packages/workspace-io/

# Ported-from comments referencing the original lattice-* packages
packages/source-parser/
packages/eval-harness/

# Wiki test fixture vault — round-trip-vault preserves the historical lattice-* layout
packages/wiki-io/

# Cross-package imports of workspace_io
packages/model-adapter/
agents/graph-wiki-agent/
plugins/graph-wiki/

# Historical milestone documentation references the original lattice provenance
.planning/

# CLAUDE.md references workspace_io as the canonical package name
CLAUDE.md
```

The file ends with a trailing newline.

Do NOT add any entry under `packages/graph-io/`. The rest of Phase 34's sweep is responsible for
ensuring `packages/graph-io/` is grep-clean of `lattice|LATTICE`; if the gate hits anything in
`packages/graph-io/` post-sweep, that is a Phase 34 bug, not an allowlist gap.

Do NOT edit `scripts/check-brand.sh` (D-17).
</action>
<acceptance_criteria>
  - File exists: `test -f .brand-grep-allow`
  - Contains all nine entries (anchored regex):
    - `grep -qE '^packages/workspace-io/$' .brand-grep-allow`
    - `grep -qE '^packages/source-parser/$' .brand-grep-allow`
    - `grep -qE '^packages/eval-harness/$' .brand-grep-allow`
    - `grep -qE '^packages/wiki-io/$' .brand-grep-allow`
    - `grep -qE '^packages/model-adapter/$' .brand-grep-allow`
    - `grep -qE '^agents/graph-wiki-agent/$' .brand-grep-allow`
    - `grep -qE '^plugins/graph-wiki/$' .brand-grep-allow`
    - `grep -qE '^\.planning/$' .brand-grep-allow`
    - `grep -qE '^CLAUDE\.md$' .brand-grep-allow`
  - Contains no graph-io entry:
    `! grep -q '^packages/graph-io/' .brand-grep-allow`
  - `scripts/check-brand.sh` was NOT modified: `git diff --name-only scripts/check-brand.sh | wc -l` outputs `0`
  - Running `bash scripts/check-brand.sh` does NOT print `BRAND-04 FAIL: .brand-grep-allow not found at repo root` (it may still exit non-zero for unrelated hits at this Wave 1 stage — Waves 2 resolve those)
</acceptance_criteria>
</task>

</tasks>

<verification>
After this plan completes:
- `.brand-grep-allow` exists at repo root with nine path-substring entries covering legitimate
  uses elsewhere in the codebase.
- `bash scripts/check-brand.sh` no longer exits with code 2 ("allowlist missing"). It will likely
  still exit non-zero because Wave 2 hasn't run yet — but the gate is *runnable*.
- Subsequent plans can run the gate between edits without false-positive failures.
- Wave-3 verification (Plan 34-05) confirms `bash scripts/check-brand.sh` exits 0 on the final
  post-sweep tree.

No tests run for this plan.
</verification>
