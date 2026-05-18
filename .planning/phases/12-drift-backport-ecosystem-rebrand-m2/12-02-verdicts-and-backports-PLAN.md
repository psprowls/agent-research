---
phase: 12-drift-backport-ecosystem-rebrand-m2
plan: 02
type: execute
wave: 2
depends_on:
  - 12-01
files_modified:
  - packages/vault-io/DRIFT-DECISIONS.md
  - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md
  - packages/vault-io/src/vault_io/lint/common.py
  - packages/vault-io/src/vault_io/lint/container.py
  - packages/vault-io/src/vault_io/lint/dependency.py
  - packages/vault-io/src/vault_io/lint/domain.py
  - packages/vault-io/src/vault_io/lint/file_map.py
  - packages/vault-io/src/vault_io/lint/package_sync.py
  - packages/vault-io/src/vault_io/lint/source_sync.py
  - packages/vault-io/src/vault_io/lint/workflow_hints.py
  - packages/vault-io/src/vault_io/init_vault.py
  - packages/vault-io/src/vault_io/ingest_work_item.py
  - packages/vault-io/src/vault_io/git_state.py
  - packages/vault-io/src/vault_io/append_log.py
  - packages/vault-io/src/vault_io/update_index.py
  - packages/vault-io/src/vault_io/update_tokens.py
  - packages/vault-io/src/vault_io/layout_io.py
  - packages/vault-io/src/vault_io/detect_containers.py
  - packages/vault-io/src/vault_io/scan_monorepo.py
  - packages/vault-io/src/vault_io/ingest_source.py
autonomous: false
requirements:
  - BACKPORT-01
  - BACKPORT-02
  - BACKPORT-03
  - BACKPORT-04
must_haves:
  truths:
    - "Every one of the 11 overlapping module ROWS (spike 002 §A; `lint/*` collapsed as a single row) has a verdict (PORT / LEAVE-AHEAD / LEAVE-ARCH / LEAVE-COSMETIC / IDENTICAL) recorded in DRIFT-DECISIONS.md."
    - "Verdict assignments are persisted to a scratch file `12-02-scratch-verdicts.md` before Task 2 reads them into the final table."
    - "Every PORT verdict has a corresponding atomic backport commit referenced by SHA in the table."
    - "Every LEAVE-AHEAD row references a Phase 11 D-ID or WR-01/WR-02 in its rationale."
    - "`uv run pytest` is green after all backport commits have landed."
  artifacts:
    - path: "packages/vault-io/DRIFT-DECISIONS.md"
      provides: "Human-verdict table for the 11 overlapping module rows (spike 002 §A, lint/* collapsed); canonical record of vault-io ↔ upstream relationship at the pinned SHA"
      contains: "1b45172a9900842b0f8eea525c8270e7fff50605"
    - path: ".planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md"
      provides: "Persisted verdict scratch file — pre-filled 11-row template the executor fills out before writing DRIFT-DECISIONS.md"
  key_links:
    - from: "packages/vault-io/DRIFT-DECISIONS.md"
      to: "packages/vault-io/DRIFT-DECISIONS-RAW.md"
      via: "table verdicts reference the raw diff dump as source-of-truth"
      pattern: "DRIFT-DECISIONS-RAW.md"
    - from: "PORT verdict rows"
      to: "atomic backport commits in vault-io src"
      via: "backport-commit-sha column"
      pattern: "[a-f0-9]{7,}"
---

<objective>
P-B (per CONTEXT.md SQ-01.2): for each of the 11 module ROWS in `DRIFT-DECISIONS-RAW.md` (matching spike 002 §A "Overlapping modules", with `lint/*` collapsed as a single row covering all 8 lint sub-files), read the diff, assign a verdict per SR-01/SR-02/SR-03, and — for any `PORT` verdicts — land the change as a separate atomic commit in `packages/vault-io/`. Verdicts are first persisted to a scratch file before being rendered into the final `packages/vault-io/DRIFT-DECISIONS.md` (DD-02 table shape, DD-04 location, DD-01 coverage). Closes BACKPORT-01..04.

The 11 row IDs (in spike-table order) are: `git_state.py`, `append_log.py`, `update_index.py`, `update_tokens.py`, `ingest_work_item.py`, `init_vault.py`, `lint/*`, `layout_io.py`, `detect_containers.py`, `scan_monorepo.py`, `ingest_source.py`.

Purpose: separates judgment (this plan) from rebrand surgery (next plan). After this plan the substantive drift question is settled and the surface is ready for the rebrand sweep.

Output: per-module backport commits + `12-02-scratch-verdicts.md` (intermediate) + final `packages/vault-io/DRIFT-DECISIONS.md`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md
@.planning/phases/11-workspace-io-port-m1/11-CONTEXT.md
@.planning/spikes/002-lattice-drift-inventory/README.md
@packages/vault-io/DRIFT-DECISIONS-RAW.md
@CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Persist scratch verdicts to 12-02-scratch-verdicts.md, then land PORT backports as atomic per-module commits</name>
  <files>.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md, packages/vault-io/src/vault_io/lint/common.py, packages/vault-io/src/vault_io/lint/container.py, packages/vault-io/src/vault_io/lint/dependency.py, packages/vault-io/src/vault_io/lint/domain.py, packages/vault-io/src/vault_io/lint/file_map.py, packages/vault-io/src/vault_io/lint/package_sync.py, packages/vault-io/src/vault_io/lint/source_sync.py, packages/vault-io/src/vault_io/lint/workflow_hints.py, packages/vault-io/src/vault_io/init_vault.py, packages/vault-io/src/vault_io/ingest_work_item.py, packages/vault-io/src/vault_io/git_state.py, packages/vault-io/src/vault_io/append_log.py, packages/vault-io/src/vault_io/update_index.py, packages/vault-io/src/vault_io/update_tokens.py, packages/vault-io/src/vault_io/layout_io.py, packages/vault-io/src/vault_io/detect_containers.py, packages/vault-io/src/vault_io/scan_monorepo.py, packages/vault-io/src/vault_io/ingest_source.py</files>
  <read_first>
    - packages/vault-io/DRIFT-DECISIONS-RAW.md (every `### ` section — read each diff in full before assigning a verdict)
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (SR-01 PORT criteria, SR-02 skip criteria, SR-03 verdict vocabulary, SR-04 closure gate)
    - .planning/phases/11-workspace-io-port-m1/11-CONTEXT.md (D-IDs referenced by LEAVE-AHEAD rows; WR-01/WR-02 MCP error-handling decisions)
    - .planning/PROJECT.md §"Explicitly out of v1.2" (LEAVE-ARCH justification for work-layer / package-family / CLI main())
    - CLAUDE.md (no-tiktoken constraint → informs `update_tokens.py` LEAVE-AHEAD rationale)
    - For each module being PORTed: the corresponding `packages/vault-io/src/vault_io/<relpath>` file (the file you are about to modify)
    - For each module being PORTed: the upstream file at `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/<relpath>` (so you understand the surrounding upstream context, not just the diff hunks)
  </read_first>
  <action>
    **Step 1: Pre-fill the scratch verdict file (B2 — persistence requirement).**

    Create `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md` with a pre-filled 11-row template. One row per spike-table module ROW. The verdict column starts BLANK; the executor fills it in during Step 2. Spike-derived guidance from the operator decision sits in the `Spike Verdict` and `Hint` columns as priors — they are NOT pre-assignments, the executor still reads the diff and applies SR-01/SR-02/SR-03.

    Template structure:

    ```markdown
    # Phase 12 Drift Verdict Scratch (pre-fill — fill `Verdict` + `Rationale` columns inline)

    Source-of-truth row list: spike 002 §A "Overlapping modules" (11 rows; `lint/*` collapsed).
    Verdict vocabulary (SR-03 — fixed set): PORT | LEAVE-AHEAD | LEAVE-ARCH | LEAVE-COSMETIC | IDENTICAL.

    | # | Module (relpath) | Spike Verdict | LOC Δ | Hint (operator priors — not pre-assignment) | Verdict | Rationale (one line) | Backport SHA |
    |---|------------------|---------------|-------|---------------------------------------------|---------|----------------------|--------------|
    | 1 | `git_state.py` | IDENTICAL (byte-equal) | 0 | IDENTICAL |  |  | — |
    | 2 | `append_log.py` | DRIFTED-COMPATIBLE | +30 | LEAVE-AHEAD (WR-01/WR-02) |  |  | — |
    | 3 | `update_index.py` | DRIFTED-COMPATIBLE | +29 | LEAVE-AHEAD (lib-ification, public `update_index(wiki)`) |  |  | — |
    | 4 | `update_tokens.py` | DRIFTED-COMPATIBLE | +6 | LEAVE-AHEAD (no-tiktoken project rule per CLAUDE.md §3) |  |  | — |
    | 5 | `ingest_work_item.py` | DRIFTED-INCOMPATIBLE-API | -1 | LEAVE-AHEAD (`file_work_item` lib shape — PROJECT.md recommendation) |  |  | — |
    | 6 | `init_vault.py` | DRIFTED-COMPATIBLE | -15 | TBD — body-diff determines PORT vs LEAVE-COSMETIC |  |  | — |
    | 7 | `lint/*` | DRIFTED-COMPATIBLE | various | TBD per-file inside row — likely PORT for each (BACKPORT-01); if sub-files diverge add footnote |  |  | — |
    | 8 | `layout_io.py` | DRIFTED-FEATURE-LOSS | -98 | LEAVE-ARCH (package-family strip — out of v1.2) |  |  | — |
    | 9 | `detect_containers.py` | DRIFTED-FEATURE-LOSS | -129 | LEAVE-ARCH (package-family strip) |  |  | — |
    | 10 | `scan_monorepo.py` | DRIFTED-FEATURE-LOSS | -151 | LEAVE-ARCH (package-family strip) |  |  | — |
    | 11 | `ingest_source.py` | DRIFTED-CLI-STRIPPED | -181 | LEAVE-ARCH (CLI `main()` strip) |  |  | — |
    ```

    Commit this scratch file BEFORE assigning any verdicts (so the file exists in git as the pre-fill template). Commit subject: `docs(12): scaffold drift-verdict scratch template (11 rows)`.

    **Step 2: Assign verdicts row-by-row by reading the raw diffs.**

    For EACH of the 11 module ROWS in `DRIFT-DECISIONS-RAW.md`, in order:

    1. Read the diff in full. If `IDENTICAL`, fill `Verdict: IDENTICAL` in the scratch row.
    2. Apply SR-01 (PORT criteria) and SR-02 (skip criteria). Assign exactly one of the SR-03 vocabulary terms: `PORT`, `LEAVE-AHEAD`, `LEAVE-ARCH`, `LEAVE-COSMETIC`, `IDENTICAL`. Do NOT invent new verdicts.
    3. Fill the `Verdict` and `Rationale` cells in `12-02-scratch-verdicts.md`. Rationale is one line; LEAVE-AHEAD rows MUST cite a Phase 11 D-ID or WR-01/WR-02; LEAVE-ARCH rows MUST cite a stripped subsystem from PROJECT.md "Explicitly out of v1.2".
    4. If verdict is `PORT`:
       - Apply the substantive upstream change to the corresponding `packages/vault-io/src/vault_io/<relpath>` file (or for `lint/*` row, to each affected lint sub-file). Do NOT bring along stripped-subsystem code (work-layer, package-family, CLI `main()`); if a hunk mixes substantive + stripped-subsystem code, lift only the substantive part.
       - Preserve vault-io's intentional forks: MCP error-handling additions (WR-01 `raise_exception=True`, WR-02 stderr-JSON), the no-tiktoken posture, the lib-ification surface. Do not let upstream undo them.
       - If the backport adds behavior not covered by the existing test suite, add a minimal regression test in the SAME commit (SR-04). Otherwise skip the test (SR-04 default).
       - Run `uv run pytest`. If it goes red, fix or revert before continuing.
       - Commit as `backport(vault-io): <one-line summary of substantive change> for <relpath>`. One commit per backport (for the `lint/*` row this MAY be either one commit covering all changed lint sub-files OR one commit per sub-file — executor's discretion based on whether the changes are semantically related). Record the resulting commit SHA in the scratch row's `Backport SHA` cell.
    5. If verdict is `LEAVE-AHEAD` / `LEAVE-ARCH` / `LEAVE-COSMETIC` / `IDENTICAL`: write the one-line rationale; no code change, no commit; `Backport SHA` cell stays `—`.

    Per CONTEXT.md "Recommended LEAVE-AHEAD candidates": `ingest_work_item.py` likely `LEAVE-AHEAD` (file_work_item lib shape fits MCP per BACKPORT-03 text). `git_state.py` likely `IDENTICAL` per CONTEXT.md DD-01. `update_tokens.py` style references LEAVE-AHEAD (no-tiktoken). DO NOT pre-commit to verdicts before reading the actual diffs; these are priors, not assignments.

    **Step 3: Commit the filled scratch file.**

    After all 11 verdict cells are filled (and any PORT commits have landed), commit the populated scratch file with subject `docs(12): record drift verdicts in scratch (11 rows)`. This makes the verdict list the persistent, auditable source-of-truth that Task 2 reads.

    **Acceptance gate before Task 2 starts:** the scratch file exists, has exactly 11 data rows, and every row's `Verdict` cell contains a token from the SR-03 vocabulary (no blank cells, no other tokens).
  </action>
  <verify>
    <automated>test -f .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md &amp;&amp; ROWS=$(grep -cE '^\| [0-9]+ \| ' .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md) &amp;&amp; test "$ROWS" -eq 11 || { echo "Expected 11 scratch rows, got $ROWS"; exit 1; } &amp;&amp; for m in 'git_state.py' 'append_log.py' 'update_index.py' 'update_tokens.py' 'ingest_work_item.py' 'init_vault.py' 'lint/\*' 'layout_io.py' 'detect_containers.py' 'scan_monorepo.py' 'ingest_source.py'; do grep -qF "$m" .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md || { echo "MISSING scratch row: $m"; exit 1; }; done &amp;&amp; BAD=$(grep -E '^\| [0-9]+ \| ' .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md | awk -F'\\|' '{gsub(/^ +| +$/, "", $7); if ($7 !~ /^(PORT|LEAVE-AHEAD|LEAVE-ARCH|LEAVE-COSMETIC|IDENTICAL)$/) print NR": bad verdict ["$7"]"}') &amp;&amp; test -z "$BAD" || { echo "Bad verdict cells:"; echo "$BAD"; exit 1; } &amp;&amp; uv run pytest 2&gt;&amp;1 | tail -5</automated>
  </verify>
  <acceptance_criteria>
    - `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md` exists and is committed to git.
    - Scratch file has exactly 11 data rows whose Module column matches the 11 spike-table row IDs in spike-table order.
    - Every row's `Verdict` cell contains exactly one of the SR-03 vocabulary tokens: `PORT`, `LEAVE-AHEAD`, `LEAVE-ARCH`, `LEAVE-COSMETIC`, `IDENTICAL`. No blanks, no other tokens.
    - Every LEAVE-AHEAD row's `Rationale` text references a Phase 11 D-ID (e.g., `D-02`, `D-08`) or `WR-01` or `WR-02`.
    - Every LEAVE-ARCH row's `Rationale` text references a stripped subsystem (one of: `work-layer`, `package-family`, `CLI main()`).
    - Every PORT row's `Backport SHA` cell contains a real short SHA returned by `git log --oneline`.
    - `uv run pytest` exits 0 after all backport commits have landed (SR-04 closure gate).
    - For every PORT verdict, there is at least one atomic commit in `git log` whose subject line starts with `backport(vault-io):` and whose touched files are confined to the corresponding `packages/vault-io/src/vault_io/<relpath>` (plus optionally a regression test under `packages/vault-io/tests/`). The `lint/*` row MAY produce 1+ commits per the executor's discretion in Step 2.4.
    - No PORT commit touches files outside `packages/vault-io/`.
    - No PORT commit reintroduces an `import` of stripped-subsystem code (no new references to `lattice_workspace`, `work`-layer modules, or package-family code paths in vault-io src).
    - If ANY diff is genuinely ambiguous (executor cannot decide between two SR-03 verdicts after reading the diff and the surrounding upstream code), STOP and surface the ambiguity to the operator before continuing — this plan is marked `autonomous: false` precisely so verdict-assignment ambiguities pause for human input. Resume signal: operator picks the verdict.
  </acceptance_criteria>
  <done>Scratch verdict file fully populated (11/11 verdicts from SR-03 vocabulary); every PORT verdict landed as atomic commit(s); vault-io tests green; scratch file is the persistent source-of-truth that Task 2 reads to write the final DRIFT-DECISIONS.md table.</done>
</task>

<task type="auto">
  <name>Task 2: Write final packages/vault-io/DRIFT-DECISIONS.md from the scratch verdict file</name>
  <files>packages/vault-io/DRIFT-DECISIONS.md</files>
  <read_first>
    - packages/vault-io/DRIFT-DECISIONS-RAW.md (back-reference target)
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md (the populated scratch file — this is now the source-of-truth for verdict assignments)
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (DD-01, DD-02 table shape, DD-04 header pin)
    - `git log --oneline -20` output to confirm backport SHAs
  </read_first>
  <action>
    Read `12-02-scratch-verdicts.md`. Render its 11 rows into `packages/vault-io/DRIFT-DECISIONS.md` with this structure:

    1. Title: `# vault-io ⟷ lattice-wiki-core Drift Decisions`.
    2. Header block listing: `Upstream: lattice-wiki-core @ 1b45172a9900842b0f8eea525c8270e7fff50605 at 2026-05-18`, link/reference to `DRIFT-DECISIONS-RAW.md`, link/reference to spike 002 README, link/reference to Phase 12 plans.
    3. Short prose preamble (under 10 lines) defining the verdict vocabulary inline: `PORT`, `LEAVE-AHEAD`, `LEAVE-ARCH`, `LEAVE-COSMETIC`, `IDENTICAL`. (Per SR-03.) Note that the row set is the 11 overlapping module ROWS from spike 002 §A with `lint/*` collapsed; the `lint/*` row may carry a footnote if sub-files diverge.
    4. The verdict table (DD-02 shape). Columns: `file | upstream-commit | LOC Δ | verdict | rationale (one line) | backport-commit-sha`. Exactly 11 data rows — one per overlapping module ROW from `12-02-scratch-verdicts.md`. EVERY row's `file` column starts with the path literal wrapped in backticks: ``` | `git_state.py` | ```, ``` | `append_log.py` | ```, ..., ``` | `lint/*` | ```, ``` | `ingest_source.py` | ```. `upstream-commit` column carries the pinned SHA (same for every row at this sync). `LOC Δ` is copied from the scratch file. `verdict` is one of the SR-03 vocabulary terms. `rationale` is the one-line justification copied from the scratch file. `backport-commit-sha` is the short SHA for PORT rows or `—` for non-PORT rows.
    5. Optional prose appendix at the end ONLY for rows where one-line rationale is genuinely insufficient. The `lint/*` row appendix is REQUIRED if any lint sub-file received a verdict different from the row-level verdict (per operator decision on B1: "If a lint sub-file needs a different verdict than the others, the executor adds a footnote under the table"). Default is no appendix.

    File must include the literal SHA `1b45172a9900842b0f8eea525c8270e7fff50605` in the header.
  </action>
  <verify>
    <automated>head -30 packages/vault-io/DRIFT-DECISIONS.md | grep -q '1b45172a9900842b0f8eea525c8270e7fff50605' || { echo "MISSING SHA pin in header"; exit 1; }; EXPECTED_MODULES=(git_state.py append_log.py update_index.py update_tokens.py ingest_work_item.py init_vault.py 'lint/*' layout_io.py detect_containers.py scan_monorepo.py ingest_source.py); for m in "${EXPECTED_MODULES[@]}"; do grep -qF "| \`$m\`" packages/vault-io/DRIFT-DECISIONS.md || { echo "MISSING ROW: $m"; exit 1; }; done; ROWS=$(grep -cE '^\| \`' packages/vault-io/DRIFT-DECISIONS.md); test "$ROWS" -eq 11 || { echo "Expected 11 rows, got $ROWS"; exit 1; }; BAD=$(grep -E '^\| \`' packages/vault-io/DRIFT-DECISIONS.md | grep -vE '\| (PORT|LEAVE-AHEAD|LEAVE-ARCH|LEAVE-COSMETIC|IDENTICAL) \|'); if [ -n "$BAD" ]; then echo "Row missing SR-03 verdict:"; echo "$BAD"; exit 1; fi; uv run pytest 2&gt;&amp;1 | tail -5</automated>
  </verify>
  <acceptance_criteria>
    - File `packages/vault-io/DRIFT-DECISIONS.md` exists.
    - `head -30 packages/vault-io/DRIFT-DECISIONS.md | grep -q '1b45172a9900842b0f8eea525c8270e7fff50605'` succeeds (SHA pin).
    - Each of the 11 expected module path-literals appears in the table, asserted by the explicit loop in the verify command: `git_state.py`, `append_log.py`, `update_index.py`, `update_tokens.py`, `ingest_work_item.py`, `init_vault.py`, `lint/*`, `layout_io.py`, `detect_containers.py`, `scan_monorepo.py`, `ingest_source.py`.
    - `grep -cE '^\| \`' packages/vault-io/DRIFT-DECISIONS.md` equals exactly `11` (verdict-table data rows).
    - Every data row contains exactly one SR-03 vocabulary token (`PORT`, `LEAVE-AHEAD`, `LEAVE-ARCH`, `LEAVE-COSMETIC`, `IDENTICAL`) — enforced by the inverse-grep check in the verify command.
    - Every PORT row's `backport-commit-sha` column matches a real commit returned by `git log --oneline`.
    - Every LEAVE-AHEAD row's rationale text contains a Phase 11 D-ID reference (e.g., `D-02`, `D-08`) OR `WR-01` OR `WR-02`.
    - Every LEAVE-ARCH row's rationale text contains a reference to a stripped subsystem (one of: `work-layer`, `package-family`, `CLI main()`).
    - `uv run pytest` is green.
  </acceptance_criteria>
  <done>`packages/vault-io/DRIFT-DECISIONS.md` published; exactly 11 module rows present (matching spike 002 §A row IDs); per-module path-literal presence enforced by explicit loop assertion; PORT rows have real backport SHAs; LEAVE-AHEAD rows cite Phase 11 decisions; tests green. BACKPORT-01..04 closed.</done>
</task>

</tasks>

<verification>
- `uv run pytest` exits 0.
- `head -30 packages/vault-io/DRIFT-DECISIONS.md | grep '1b45172a9900842b0f8eea525c8270e7fff50605'` returns a hit.
- Verdict table contains exactly 11 rows; every expected module path-literal is present (per-module assertion loop in Task 2 verify).
- Every row's verdict cell contains exactly one SR-03 vocabulary token.
- All PORT verdicts have a corresponding commit in `git log --oneline` whose subject begins `backport(vault-io):`.
- No backport commit touches files outside `packages/vault-io/`.
- `12-02-scratch-verdicts.md` is committed and has 11 fully-populated verdict rows.
</verification>

<success_criteria>
SC#1 (lint matches upstream on substantive changes; DRIFT-DECISIONS.md per-file verdicts) and SC#2 (init_vault + ingest_work_item documented with backport or leave-alone justification) from ROADMAP §Phase 12 are satisfied. BACKPORT-01, BACKPORT-02, BACKPORT-03, BACKPORT-04 closed.
</success_criteria>

<output>
Create `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-SUMMARY.md` with: verdict tally per category (e.g., `PORT: N, LEAVE-AHEAD: M, ...`), list of backport commit SHAs, any modules where the verdict required operator input (autonomous=false pause points), and an explicit pointer to `12-02-scratch-verdicts.md` as the canonical verdict ledger.
</output>
