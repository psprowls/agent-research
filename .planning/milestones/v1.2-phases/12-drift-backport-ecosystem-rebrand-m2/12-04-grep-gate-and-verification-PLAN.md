---
phase: 12-drift-backport-ecosystem-rebrand-m2
plan: 04
type: execute
wave: 4
depends_on:
  - 12-03
files_modified:
  - scripts/check-brand.sh
  - .brand-grep-allow
autonomous: true
requirements:
  - BRAND-01
  - BRAND-04
must_haves:
  truths:
    - "`bash scripts/check-brand.sh` exits 0 — zero unallowlisted `lattice` hits across in-scope paths (`packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md`)."
    - "The grep-gate is reproducible — future phases (13, 14, 16) can re-run the same command cheaply."
    - "The allowlist file documents WHY each excluded path is excluded, referencing the R-01/R-02/R-03/R-04 decision IDs."
    - "The allowlist incorporates every carry-forward reference recorded in plan 03's `12-03-carry-forward-refs.md`."
    - "`uv run pytest` is green at the end of the phase."
  artifacts:
    - path: "scripts/check-brand.sh"
      provides: "Standalone, re-runnable BRAND-04 grep gate script (per SQ-04); grep target list includes `plugins/` for forward-compatibility with Phase 14"
    - path: ".brand-grep-allow"
      provides: "Versioned allowlist of paths/globs excluded from the grep gate (per R-04), incorporating plan 03 carry-forward entries"
  key_links:
    - from: "scripts/check-brand.sh"
      to: ".brand-grep-allow"
      via: "grep -vF -f .brand-grep-allow"
      pattern: "\\.brand-grep-allow"
    - from: ".brand-grep-allow"
      to: ".planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md"
      via: "Task 1 reads carry-forward file and adds entries to allowlist before running the gate"
      pattern: "12-03-carry-forward-refs.md"
---

<objective>
P-D (per CONTEXT.md SQ-01.4): land `scripts/check-brand.sh` (SQ-04 shape, grep target list including `plugins/`) and `.brand-grep-allow` (R-04 format, incorporating plan 03's `12-03-carry-forward-refs.md` entries). Run the gate; expect zero unallowlisted hits. Run `uv run pytest`; expect green. Closes BRAND-04 and verifies BRAND-01.

Purpose: provides the reproducible mechanism that future phases (13, 14, 16) re-run cheaply before merging, and provides the auditable record of which paths legitimately keep their `lattice` references and why.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md
@.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write .brand-grep-allow (incorporating plan 03 carry-forward refs) and scripts/check-brand.sh (with plugins/ in grep targets)</name>
  <files>.brand-grep-allow, scripts/check-brand.sh</files>
  <read_first>
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (R-01 round-trip-vault, R-02 baselines + rubrics + baseline.py/pricing.py data refs, R-03 archived planning, R-04 allowlist file format, SQ-04 script shape, "Claude's Discretion" self-allowlist)
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md (REQUIRED — Task 1 incorporates every non-`(none)` row's path into `.brand-grep-allow` before running the gate). Plan 03 guarantees this file exists; if it is missing, STOP and surface the error to the operator — do not proceed with allowlist authoring while the hand-off file is absent.
    - The 12-03 SUMMARY (if available) for any additional editorial-judgment context.
  </read_first>
  <action>
    **Step 1: Read and parse `12-03-carry-forward-refs.md`.**

    Read the file. For every data row whose `Path` cell is NOT the literal `(none)`, extract the path (and optional line-anchor) and the one-line rationale. These become additional entries in `.brand-grep-allow` keyed by path (or path + line anchor if `grep -vF -f` line-substring matching needs the more specific form to avoid over-allowing).

    If the file contains only the `(none)` row: no carry-forward entries to add; proceed with the base allowlist only.

    **Step 2: Author `.brand-grep-allow`.**

    Create `.brand-grep-allow` at repo root. Format per R-04: one path or path-glob per line; lines starting with `#` are comments. Use `grep -vF` line-substring matching semantics (the file lists path fragments; `grep -vF -f` excludes any line whose path contains one of these fragments).

    Required base entries (with `#` comments grouped by R-decision):

    - `# R-01: round-trip-vault test fixtures — real lattice vault for byte-identical round-trip parsing`
    - `packages/wiki-io/tests/fixtures/round-trip-vault/`
    - `# R-02: eval-harness baselines + divergence rubrics — record what was measured`
    - `packages/eval-harness/baselines/`
    - `packages/eval-harness/src/eval_harness/divergence/rubrics/`
    - (Optionally also explicit file paths for any `lattice-wiki` literals inside `packages/eval-harness/src/eval_harness/baseline.py` / `pricing.py` that name recorded baseline data — only include if `grep -E 'lattice' packages/eval-harness/src/eval_harness/{baseline,pricing}.py` still returns hits after plan 03; the executor runs that grep before deciding whether to add `baseline.py`/`pricing.py` to the allowlist.)
    - `# R-03: archived / historical planning documents — provenance value preserved`
    - `.planning/RETROSPECTIVE.md`
    - `.planning/MILESTONES.md`
    - `.planning/milestones/v1.0-`
    - `.planning/milestones/v1.1-`
    - `.planning/spikes/001-subagent-context-audit/README.md`
    - `.planning/spikes/002-lattice-drift-inventory/README.md`
    - `.planning/spikes/WRAP-UP-SUMMARY.md`
    - `.planning/sweep/STORY.md`
    - `.planning/research/`
    - `.planning/threads/next-milestone-planning.md`
    - `# R-04 (self-allowlist per Claude's Discretion): this file itself contains 'lattice' as pattern text`
    - `.brand-grep-allow`
    - `# Phase 12 drift artifacts — diff dumps embed upstream content with lattice symbols intact`
    - `packages/wiki-io/DRIFT-DECISIONS-RAW.md`
    - `packages/wiki-io/DRIFT-DECISIONS.md`
    - `# Phase 12 plans + context themselves reference 'lattice' as the source-of-truth domain`
    - `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/`
    - `# scripts/check-brand.sh contains 'lattice' as the search pattern itself`
    - `scripts/check-brand.sh`
    - `# scripts/drift-diff.sh references upstream lattice-wiki-core paths`
    - `scripts/drift-diff.sh`

    Then append a section for carry-forward entries from plan 03:

    - `# Phase 12 plan-03 carry-forward refs (from .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md)`
    - <one path entry per non-`(none)` row in the carry-forward file, each preceded by a `# rationale:` comment line>

    If `12-03-carry-forward-refs.md` contains only the `(none)` row, write only the section header comment (no entries) so the audit trail records that the carry-forward step was executed and produced zero entries.

    **Step 3: Author `scripts/check-brand.sh`.**

    Create `scripts/check-brand.sh` (executable; `chmod +x`). Per SQ-04 sample shape, with `plugins/` added to grep targets per checker W5:

    - Use `set -euo pipefail`.
    - Compute hits across `packages/ agents/ plugins/ .planning/ CLAUDE.md`:

      ```bash
      HITS=$(grep -rEl 'lattice|LATTICE|lattice_workspace|lattice_wiki_core' \
          packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null \
          | grep -vF -f .brand-grep-allow || true)
      ```

      `2>/dev/null` swallows the "is a directory" / "no such file" noise for the case where `plugins/` is empty (forward-compatibility with Phase 14 per W5 — `grep -r` on an empty directory returns nothing, which is correct).
    - If `HITS` is non-empty: print each hit, then `echo "BRAND-04 FAIL: $(echo "$HITS" | wc -l) unallowlisted hits"`, then `exit 1`.
    - If `HITS` is empty: `echo "BRAND-04 OK: zero unallowlisted hits"`, then `exit 0`.

    Note: `scripts/check-brand.sh` must include the literal token `lattice` as part of its grep pattern, which is why the script self-allowlists.
  </action>
  <verify>
    <automated>test -f .brand-grep-allow || { echo ".brand-grep-allow missing"; exit 1; }; test -x scripts/check-brand.sh || { echo "check-brand.sh not executable"; exit 1; }; bash -n scripts/check-brand.sh || { echo "check-brand.sh syntax error"; exit 1; }; for token in 'round-trip-vault' 'baselines/' 'milestones/v1.0-' 'next-milestone-planning' '.brand-grep-allow'; do grep -qF "$token" .brand-grep-allow || { echo "MISSING allowlist entry: $token"; exit 1; }; done; grep -q 'lattice' scripts/check-brand.sh || { echo "script grep pattern missing"; exit 1; }; grep -qF 'plugins/' scripts/check-brand.sh || { echo "plugins/ missing from grep target list"; exit 1; }; test -f .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md || { echo "carry-forward file not read"; exit 1; }; grep -qF '12-03-carry-forward-refs.md' .brand-grep-allow || grep -qF 'plan-03 carry-forward' .brand-grep-allow || { echo "carry-forward section header missing from allowlist"; exit 1; }</automated>
  </verify>
  <acceptance_criteria>
    - `.brand-grep-allow` exists at repo root.
    - File contains base entries covering R-01 (`round-trip-vault`), R-02 (`baselines/`, `rubrics/`), R-03 (RETROSPECTIVE, MILESTONES, milestones/v1.0-, milestones/v1.1-, spikes/00*/README.md, sweep/STORY, research/, threads/next-milestone-planning), and self-allowlist (`.brand-grep-allow`).
    - File contains R-decision comment headers (`R-01:`, `R-02:`, `R-03:`).
    - File contains a comment section header referencing `12-03-carry-forward-refs.md` (so the audit trail records that the carry-forward read step was executed, even if no entries were added because plan 03 produced an empty/`(none)` file).
    - For every non-`(none)` row in `12-03-carry-forward-refs.md`, the corresponding path is present in `.brand-grep-allow` under the carry-forward section, preceded by a `# rationale:` comment line copying the one-line rationale from plan 03.
    - `scripts/check-brand.sh` exists, is executable, passes `bash -n`.
    - Script uses `set -euo pipefail` and `grep -vF -f .brand-grep-allow`.
    - Script's grep pattern matches `lattice|LATTICE|lattice_workspace|lattice_wiki_core`.
    - Script's grep target list includes `plugins/` (W5 — forward-compatibility with Phase 14).
  </acceptance_criteria>
  <done>Allowlist (with plan 03 carry-forward refs incorporated) + gate script (with `plugins/` in targets) committed; ready for the gate run in Task 2.</done>
</task>

<task type="auto">
  <name>Task 2: Run check-brand.sh and uv run pytest — staged final verification with explicit exit codes</name>
  <files></files>
  <read_first>
    - scripts/check-brand.sh (the gate script just created)
    - .brand-grep-allow (the allowlist just created)
  </read_first>
  <action>
    Run the gate and the test suite as TWO independent stages with explicit named exit-code capture (per checker W4 — no combined `&&` invocation that obscures which stage failed).

    Stage 1 — grep gate:

    ```bash
    bash scripts/check-brand.sh
    GATE_RC=$?
    ```

    If `GATE_RC != 0`: read the printed hits. For each:
    - If the hit is a legitimate fork-and-allowlist case (R-01/R-02/R-03 scope that was missed, OR a carry-forward ref that plan 03 forgot to record): add it to `.brand-grep-allow` with an `# R-0X` or `# carry-forward (post-hoc):` comment explaining why. Re-run the gate stage and re-capture `GATE_RC`.
    - If the hit is a genuine missed-rebrand: STOP. Surface to operator with the list of unallowlisted hits. The operator decides whether to amend an earlier rebrand commit or to extend the allowlist. (This is a hard gate — do not paper over genuine misses by adding them to the allowlist without operator approval.)
    - Iterate until `GATE_RC == 0`. Each allowlist update must be a single small commit `chore: extend brand allowlist for <reason>` so the audit trail is clean.

    Once `GATE_RC == 0`, proceed to Stage 2.

    Stage 2 — pytest:

    ```bash
    uv run pytest 2>&1 | tail -5
    TEST_RC=${PIPESTATUS[0]}
    ```

    If `TEST_RC != 0`: STOP and surface. This would indicate a regression from one of the rebrand commits that SQ-03 should have caught — a serious signal warranting operator attention.

    If both stages green: phase verification complete. Commit final state (if any allowlist amendments landed during the iteration above) with subject `chore: land brand grep-gate + allowlist (BRAND-04)`. If Task 1 already committed `scripts/check-brand.sh` + `.brand-grep-allow` and no iteration was required, this task adds no new commit.
  </action>
  <verify>
    <automated>bash scripts/check-brand.sh; GATE_RC=$?; test "$GATE_RC" -eq 0 || { echo "GATE FAILED rc=$GATE_RC"; exit "$GATE_RC"; }; uv run pytest 2&gt;&amp;1 | tail -5; TEST_RC=${PIPESTATUS[0]}; test "$TEST_RC" -eq 0 || { echo "TESTS FAILED rc=$TEST_RC"; exit "$TEST_RC"; }</automated>
  </verify>
  <acceptance_criteria>
    - Stage 1: `bash scripts/check-brand.sh` exits 0 (`GATE_RC == 0`); BRAND-04 gate green.
    - Stage 2: `uv run pytest` exits 0 (`TEST_RC == 0`); SC#5 satisfied.
    - Each stage has its exit code captured in a named variable (`GATE_RC`, `TEST_RC`) and asserted independently — failure of either stage produces a distinguishable error message and propagates the original exit code.
    - Every hit that triggered an allowlist amendment during the gate-run iteration is documented in `.brand-grep-allow` with an `# R-0X` or `# carry-forward (post-hoc):` rationale comment.
    - No genuine missed-rebrand was silently allowlisted (operator was involved in any ambiguous decisions).
  </acceptance_criteria>
  <done>Grep gate green; pytest green; both stages exit codes captured and asserted independently; phase verification complete. BRAND-01 + BRAND-04 closed; SC#3 + SC#5 satisfied.</done>
</task>

</tasks>

<verification>
- `bash scripts/check-brand.sh` exits 0 (captured as `GATE_RC=0`).
- `uv run pytest` exits 0 (captured as `TEST_RC=0` via `PIPESTATUS[0]`).
- `grep -rE 'lattice|LATTICE|lattice_workspace|lattice_wiki_core' packages/ agents/ plugins/ .planning/ CLAUDE.md | grep -vF -f .brand-grep-allow` returns empty (the gate's underlying assertion; `plugins/` included per W5).
- All entries in `.brand-grep-allow` are commented with an R-decision or carry-forward rationale.
- `.brand-grep-allow` references the plan 03 carry-forward section (header comment present even when no entries were added).
</verification>

<success_criteria>
SC#3 (`grep -rE 'lattice|LATTICE|...' packages/ agents/ plugins/ .planning/ CLAUDE.md` returns zero hits, excluding allowlist) and SC#5 (`uv run pytest` passes after rebrand) from ROADMAP §Phase 12 are satisfied. BRAND-01 + BRAND-04 closed. Phase 12 verification complete.
</success_criteria>

<output>
Create `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-04-SUMMARY.md` with: gate result (hit count = 0; `GATE_RC=0`), pytest result (`TEST_RC=0`), the final `.brand-grep-allow` contents inline (for audit), a one-line entry per R-decision noting which paths it covers, an explicit note on how many plan-03 carry-forward entries were incorporated, and a "Next steps" footer pointing at Phase 13 (Plugin Spec).
</output>
