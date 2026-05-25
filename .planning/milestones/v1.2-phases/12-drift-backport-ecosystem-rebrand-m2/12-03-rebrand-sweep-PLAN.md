---
phase: 12-drift-backport-ecosystem-rebrand-m2
plan: 03
type: execute
wave: 3
depends_on:
  - 12-02
files_modified:
  - packages/wiki-io/src/wiki_io/__init__.py
  - packages/wiki-io/src/wiki_io/init_vault.py
  - packages/wiki-io/src/wiki_io/update_index.py
  - packages/wiki-io/src/wiki_io/scan_monorepo.py
  - packages/wiki-io/src/wiki_io/ingest_work_item.py
  - packages/wiki-io/src/wiki_io/git_state.py
  - packages/wiki-io/src/wiki_io/layout_io.py
  - packages/wiki-io/src/wiki_io/ingest_source.py
  - packages/wiki-io/src/wiki_io/update_tokens.py
  - packages/wiki-io/src/wiki_io/append_log.py
  - packages/wiki-io/src/wiki_io/detect_containers.py
  - packages/wiki-io/tests/
  - packages/eval-harness/src/eval_harness/baseline.py
  - packages/eval-harness/src/eval_harness/pricing.py
  - packages/eval-harness/tests/
  - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/
  - plugins/
  - .planning/ROADMAP.md
  - .planning/REQUIREMENTS.md
  - .planning/STATE.md
  - .planning/PROJECT.md
  - .planning/spikes/CONVENTIONS.md
  - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md
  - CLAUDE.md
autonomous: true
requirements:
  - BRAND-01
  - BRAND-02
must_haves:
  truths:
    - "After this plan completes, the only `lattice` references in in-scope paths are those covered by the allowlist (round-trip-vault fixtures, eval baselines/rubrics, archived planning docs)."
    - "Each of the four-or-five rebrand commits is independently revertable."
    - "`uv run pytest` is green after EACH rebrand commit, not just at the end (SQ-03)."
    - "A `12-03-carry-forward-refs.md` file is written (possibly empty) listing any intentionally-preserved `lattice` references in CLAUDE.md or `.planning/` — plan 04's allowlist authoring task reads this file."
  artifacts:
    - path: "plugins/"
      provides: "Empty directory placeholder for Phase 14 plugin port (created if missing)"
    - path: ".planning/spikes/CONVENTIONS.md"
      provides: "Corrected reference (`cores/` → `packages/`) — BRAND-02 fix"
    - path: ".planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md"
      provides: "Inventory of intentional `lattice` references preserved after the rebrand sweep (hand-off to plan 04's `.brand-grep-allow` authoring step)"
  key_links:
    - from: "rebranded surfaces"
      to: ".planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (R-01..R-04)"
      via: "allowlist exclusions defined by user decision"
      pattern: "R-0[1234]"
    - from: ".planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md"
      to: "plan 04 Task 1 (.brand-grep-allow authoring)"
      via: "explicit hand-off file read by plan 04"
      pattern: "12-03-carry-forward-refs.md"
---

<objective>
P-C (per CONTEXT.md SQ-01.3): four (or five) atomic, independently-revertable rebrand commits sweep `lattice` / `LATTICE` / `lattice_workspace` / `lattice_wiki_core` references to `graph-wiki` / `graph_wiki` across the in-scope surfaces. Each commit is gated by `uv run pytest` (SQ-03 green-or-revert).

Sequence comes AFTER backports (plan 02) BECAUSE body-diffing against still-named upstream is easier — once the rebrand lands, upstream comparisons get harder (per CONTEXT.md SQ-01 rationale). Comes BEFORE the grep-gate (plan 04) which verifies the sweep landed.

Output: four-or-five commits (Claude's Discretion on whether to fold the CONVENTIONS.md fix into commit 4); `12-03-carry-forward-refs.md` written; no source under R-01/R-02/R-03 allowlist scopes is touched.

**SQ-03 reminder (W2 — checker warning):** this plan touches ~20 files in a single plan (acceptable per SQ-02 locked decision). The executor MUST follow SQ-03 strictly: run `uv run pytest` after EACH commit; if red, revert that commit (`git reset --hard HEAD~1` or surgical revert) before proceeding. No "fix forward" — revert and retry. Per-commit green is the contract.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md
@CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Commit 1 — rebrand packages/ source (wiki-io + eval-harness non-baseline)</name>
  <files>packages/wiki-io/src/wiki_io/__init__.py, packages/wiki-io/src/wiki_io/init_vault.py, packages/wiki-io/src/wiki_io/update_index.py, packages/wiki-io/src/wiki_io/scan_monorepo.py, packages/wiki-io/src/wiki_io/ingest_work_item.py, packages/wiki-io/src/wiki_io/git_state.py, packages/wiki-io/src/wiki_io/layout_io.py, packages/wiki-io/src/wiki_io/ingest_source.py, packages/wiki-io/src/wiki_io/update_tokens.py, packages/wiki-io/src/wiki_io/append_log.py, packages/wiki-io/src/wiki_io/detect_containers.py, packages/wiki-io/tests/, packages/eval-harness/src/eval_harness/baseline.py, packages/eval-harness/src/eval_harness/pricing.py, packages/eval-harness/tests/</files>
  <read_first>
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (R-01 round-trip-vault exclusion, R-02 baseline/rubric exclusion, SQ-02 commit-1 scope, SQ-03 mid-sweep test gate)
    - Each file listed in `files_modified` for this task before editing it (so the rebrand is informed by the actual reference shape — docstring vs error string vs identifier vs prose).
  </read_first>
  <action>
    Sweep `lattice` → `graph-wiki` (kebab in user-facing prose / paths / CLI strings) or `graph_wiki` (snake in Python identifiers) across:

    - All `packages/wiki-io/src/wiki_io/*.py` files (12 modules per CONTEXT.md): replace `lattice`, `LATTICE`, `lattice_workspace`, `lattice_wiki_core`, `.lattice.yaml`, `/lattice-wiki:*` command paths, "lattice workspace" prose, etc. with the graph-wiki equivalents. Phase 11 already renamed `.graph-wiki.yaml` and `GRAPH_WIKI_WORKSPACE`; sweep updates any remaining docstrings, error messages, and legacy strings.
    - Any surviving `LatticeConfig` / `LatticeWorkspace*` Python identifiers (most should be gone after Phase 11's delegation rewrite — check, and rename if any remain to `GraphWikiConfig` etc.).
    - `packages/wiki-io/tests/*.py`: rebrand prose / identifier references. CRITICAL: do NOT touch any string literal that is testing real vault-data round-trip — that's allowlisted per R-01 (`round-trip-vault/` fixtures). For each test file, before editing a string, ask: is this asserting against real test-data ingested from `tests/fixtures/round-trip-vault/`? If yes, leave verbatim. Otherwise rebrand.
    - `packages/eval-harness/src/eval_harness/baseline.py` + `pricing.py`: rebrand implementation prose (docstrings, variable names that aren't baseline-data refs, comments). DO NOT rename any literal that names recorded baseline data (per R-02 — "lattice-wiki literals inside `baseline.py` + `pricing.py` if they reference recorded data" stay verbatim). The disambiguation rule: if the literal is the comparison-baseline label or refers to recorded output from lattice-wiki, leave it; if it's implementation prose about how the eval works, rebrand.
    - `packages/eval-harness/tests/*.py`: same disambiguation — test-data references stay (R-02), prose/identifier references rebrand.

    DO NOT touch:
    - `packages/wiki-io/tests/fixtures/round-trip-vault/` — anything inside this directory tree (R-01).
    - `packages/eval-harness/baselines/divergence-*.json` (R-02).
    - `packages/eval-harness/src/eval_harness/divergence/rubrics/*.md` (R-02).

    Run `uv run pytest`. If any failure: investigate. If the failure is from over-eager renaming, fix or revert. Per SQ-03: green before commit.

    Commit with subject `refactor: rebrand lattice → graph-wiki in packages/` (per SQ-02 commit 1 wording).
  </action>
  <verify>
    <automated>uv run pytest 2&gt;&amp;1 | tail -5; PYTEST_RC=${PIPESTATUS[0]}; test "$PYTEST_RC" -eq 0 || { echo "PYTEST FAILED rc=$PYTEST_RC"; exit 1; }; HEAD_SUBJECT=$(git log -1 --format='%s'); echo "$HEAD_SUBJECT" | grep -q '^refactor: rebrand lattice → graph-wiki in packages/' || { echo "HEAD subject mismatch: $HEAD_SUBJECT"; exit 1; }; if git show --stat HEAD | grep -qE '(round-trip-vault|baselines/divergence-|rubrics/)'; then echo "TOUCHED-DISALLOWED-PATH-ABORT"; exit 1; fi</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest` exits 0 (SQ-03 gate) — captured as `PYTEST_RC` via `${PIPESTATUS[0]}` so the pipe-to-`tail` does not mask a red run.
    - HEAD commit subject is exactly `refactor: rebrand lattice → graph-wiki in packages/`.
    - HEAD commit does NOT modify any file under `packages/wiki-io/tests/fixtures/round-trip-vault/`, `packages/eval-harness/baselines/`, or `packages/eval-harness/src/eval_harness/divergence/rubrics/` — verified by the `if ... grep -qE` block in the verify command (script exits 1 if any disallowed path appears in `git show --stat HEAD`).
    - `grep -rE 'lattice_workspace|lattice_wiki_core' packages/wiki-io/src/ packages/eval-harness/src/eval_harness/baseline.py packages/eval-harness/src/eval_harness/pricing.py` returns zero matches (the high-confidence symbol forms — any allowed lattice-wiki literal references inside baseline.py/pricing.py should NOT match this stricter pattern).
  </acceptance_criteria>
  <done>Commit 1 landed; tests green; no allowlisted path touched.</done>
</task>

<task type="auto">
  <name>Task 2: Commit 2 — rebrand agents/graph-wiki-agent source</name>
  <files>agents/graph-wiki-agent/src/graph_wiki_agent/cli.py, agents/graph-wiki-agent/src/graph_wiki_agent/commands/, agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/</files>
  <read_first>
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (SQ-02 commit-2 scope; SQ-03 mid-sweep test gate)
    - Each file under `agents/graph-wiki-agent/src/graph_wiki_agent/` that turns up in a pre-edit `grep -rE 'lattice|LATTICE' agents/graph-wiki-agent/src/` scan.
  </read_first>
  <action>
    Sweep `lattice` → `graph-wiki` / `graph_wiki` across `agents/graph-wiki-agent/src/graph_wiki_agent/`:
    - `cli.py` — Phase 11 already updated `--vault` help text; sweep verifies and updates any surviving lattice references.
    - `commands/*.py` — rebrand command-prose / docstrings / error messages.
    - `prompts/_fragments/*.py` — rebrand prompt-fragment prose. Note: many prompt fragments reference lattice-wiki as the upstream reference vault — those references describe the actual upstream system, so use editorial judgment: if the fragment instructs the agent about behavior that is now graph-wiki's own behavior, rebrand; if it explicitly names upstream lattice-wiki as the historical reference, allowlist by leaving verbatim AND record the path in `12-03-carry-forward-refs.md` (written in Task 4) so plan 04 can pick it up. For commit-2, prefer rebranding unless the reference is unambiguously historical/provenance.

    Run `uv run pytest`. Per SQ-03: green or revert before commit.

    Commit with subject `refactor: rebrand lattice → graph-wiki in agents/graph-wiki-agent` (per SQ-02 commit 2 wording).
  </action>
  <verify>
    <automated>uv run pytest 2&gt;&amp;1 | tail -5; PYTEST_RC=${PIPESTATUS[0]}; test "$PYTEST_RC" -eq 0 || { echo "PYTEST FAILED rc=$PYTEST_RC"; exit 1; }; HEAD_SUBJECT=$(git log -1 --format='%s'); echo "$HEAD_SUBJECT" | grep -q '^refactor: rebrand lattice → graph-wiki in agents/graph-wiki-agent' || { echo "HEAD subject mismatch: $HEAD_SUBJECT"; exit 1; }; if git show --stat HEAD | grep -qE '(round-trip-vault|baselines/divergence-|rubrics/)'; then echo "TOUCHED-DISALLOWED-PATH-ABORT"; exit 1; fi</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest` exits 0 (SQ-03 gate) — captured as `PYTEST_RC` via `${PIPESTATUS[0]}` so the pipe-to-`tail` does not mask a red run.
    - HEAD commit subject is exactly `refactor: rebrand lattice → graph-wiki in agents/graph-wiki-agent`.
    - `grep -rE 'lattice_workspace|lattice_wiki_core' agents/graph-wiki-agent/src/` returns zero matches.
    - Any surviving `lattice` reference in `agents/graph-wiki-agent/src/` is unambiguously a historical/provenance reference to upstream lattice-wiki (carried forward into Task 4's `12-03-carry-forward-refs.md`).
  </acceptance_criteria>
  <done>Commit 2 landed; agent CLI/command/prompt surface is rebranded; tests green.</done>
</task>

<task type="auto">
  <name>Task 3: Commit 3 — create empty plugins/ directory placeholder (if absent)</name>
  <files>plugins/</files>
  <read_first>
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (SQ-02 commit-3 scope: "only if not already present; Phase 14 will populate it")
    - `ls plugins/` output (check whether the directory exists)
  </read_first>
  <action>
    Check whether `plugins/` directory exists at repo root. If absent: create `plugins/` and a `plugins/.gitkeep` file (so the empty directory can be committed). If already present: skip this task entirely (commit no-op; document the skip in the SUMMARY).

    If creating: commit with subject `chore: create empty plugins/ directory placeholder` (per SQ-02 commit 3 wording). Run `uv run pytest` first (sanity, even though no Python touched). Per SQ-03: green before commit.
  </action>
  <verify>
    <automated>test -d plugins || { echo "plugins/ missing"; exit 1; }; if git log -5 --format='%s' | grep -q '^chore: create empty plugins/ directory placeholder'; then echo "plugins-commit-present"; else echo "PRE-EXISTING-PLUGINS-DIR-SKIP-DOCUMENTED"; fi &amp;&amp; uv run pytest 2&gt;&amp;1 | tail -3</automated>
  </verify>
  <acceptance_criteria>
    - `plugins/` directory exists at repo root after this task.
    - Either HEAD (or a recent commit) has subject `chore: create empty plugins/ directory placeholder`, OR the task SUMMARY documents that the directory pre-existed and the commit was skipped.
    - `uv run pytest` exits 0.
  </acceptance_criteria>
  <done>`plugins/` exists; commit 3 landed or skipped-and-documented; tests green.</done>
</task>

<task type="auto">
  <name>Task 4: Commit 4 — rebrand live planning surface + CLAUDE.md + CONVENTIONS.md fix; write 12-03-carry-forward-refs.md</name>
  <files>.planning/ROADMAP.md, .planning/REQUIREMENTS.md, .planning/STATE.md, .planning/PROJECT.md, .planning/spikes/CONVENTIONS.md, CLAUDE.md, .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md</files>
  <read_first>
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md (R-03 archived-doc exclusion list; SQ-02 commit-4 + commit-5 scope; "Claude's Discretion" on whether commit 5 folds into commit 4)
    - `.planning/ROADMAP.md` (identify current-milestone section — Phases 11+ — vs historic milestone sections)
    - `.planning/REQUIREMENTS.md` (live)
    - `.planning/STATE.md` (live)
    - `.planning/PROJECT.md` (identify current sections vs historic key-decisions-log entries with dated lattice references — R-03 keeps the historic dated entries verbatim)
    - `.planning/spikes/CONVENTIONS.md` (for the `cores/` → `packages/` fix, BRAND-02)
    - `CLAUDE.md` (rebrand prose, allowlist intentional historical references per executor judgment)
  </read_first>
  <action>
    Rebrand `lattice` → `graph-wiki` / `graph_wiki` across the LIVE planning surface only:

    - `.planning/ROADMAP.md` — current-milestone section (Phases 11+, v1.2 onwards). Leave historic milestone sections (v1.0 / v1.1) verbatim per R-03.
    - `.planning/REQUIREMENTS.md` — full file is live.
    - `.planning/STATE.md` — full file is live.
    - `.planning/PROJECT.md` — current sections (current-milestone, current focus, north-star). Leave historic key-decisions-log entries with dated lattice references verbatim per R-03.
    - `CLAUDE.md` — rebrand the current-state prose. Historical / provenance references to upstream lattice-wiki stay (CONTEXT.md domain: "the file already references graph-wiki / lattice-wiki together; current-state language gets rebranded, historical references in commit-history-style prose may need allowlisting case by case"). Use editorial judgment — when in doubt, leave the historical reference verbatim and record it in `12-03-carry-forward-refs.md`.
    - `.planning/spikes/CONVENTIONS.md` — fix `cores/` → `packages/` (BRAND-02). Per Claude's Discretion, this can fold into commit 4 (single combined commit) OR be a separate fifth commit `chore: fix cores/ → packages/ in spikes/CONVENTIONS.md`. Choose ONE approach; either is acceptable. Recommend: fold into commit 4 since the CONVENTIONS.md fix is one or two lines.

    DO NOT touch (R-03 allowlist):
    - `.planning/RETROSPECTIVE.md`
    - `.planning/MILESTONES.md`
    - `.planning/milestones/v1.0-*.md` and `.planning/milestones/v1.1-*.md`
    - `.planning/spikes/00*/README.md` (including spike 002)
    - `.planning/spikes/WRAP-UP-SUMMARY.md`
    - `.planning/sweep/STORY.md`
    - `.planning/research/*.md`
    - `.planning/threads/next-milestone-planning.md`

    **B4 — write carry-forward refs file (close-out step, executed before this task's commit):**

    After completing the rebrand edits but BEFORE staging/committing, enumerate any surviving `lattice` references in `CLAUDE.md` or `.planning/` (outside the R-03 allowlist scope) that were intentionally preserved as historical/provenance prose. Run:

    ```bash
    grep -rEn 'lattice|LATTICE' CLAUDE.md .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md .planning/PROJECT.md .planning/spikes/CONVENTIONS.md 2>/dev/null || true
    ```

    Also grep `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/` for any prompt-fragment references that Task 2 decided to keep verbatim as historical provenance:

    ```bash
    grep -rEn 'lattice|LATTICE' agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/ 2>/dev/null || true
    ```

    Write `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md` with this structure (file MUST exist even if empty — plan 04 Task 1 reads it):

    ```markdown
    # Phase 12 Carry-Forward `lattice` References

    Hand-off to plan 04 Task 1 (`.brand-grep-allow` authoring). Each row lists a surviving `lattice` reference left verbatim after the rebrand sweep, with one-line rationale.

    | Path | Line(s) | One-line rationale |
    |------|---------|--------------------|
    | <path or "(none)"> | <line numbers or —> | <historical / provenance / commit-history prose / etc.> |
    ```

    If no surviving references exist, write a single data row: `| (none) | — | No carry-forward references — rebrand was clean. |`. The file MUST still exist (empty allowlist need from plan 04 is still satisfied).

    Stage all rebrand edits + `12-03-carry-forward-refs.md` in the SAME commit. Run `uv run pytest`. Per SQ-03: green before commit (pytest covers more than just Python — but since this is docs only, expect green trivially).

    Commit (folded): `docs: rebrand live planning surface to graph-wiki (incl. CONVENTIONS.md cores→packages + carry-forward refs)`. OR if separate commit 5 is chosen: commit 4 `docs: rebrand live planning surface to graph-wiki`, then commit 5 `chore: fix cores/ → packages/ in spikes/CONVENTIONS.md`. EITHER PATH IS ACCEPTABLE — but `12-03-carry-forward-refs.md` MUST be included in commit 4 (not commit 5).
  </action>
  <verify>
    <automated>uv run pytest 2&gt;&amp;1 | tail -3; PYTEST_RC=${PIPESTATUS[0]}; test "$PYTEST_RC" -eq 0 || { echo "PYTEST FAILED rc=$PYTEST_RC"; exit 1; }; git log -3 --format='%s' | grep -E '^(docs: rebrand live planning surface to graph-wiki|chore: fix cores/ → packages/ in spikes/CONVENTIONS.md)' || { echo "no matching commit subject in last 3"; exit 1; }; if grep -qE 'cores/' .planning/spikes/CONVENTIONS.md; then echo "cores/ still present in CONVENTIONS.md"; exit 1; fi; test -f .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md || { echo "carry-forward-refs.md missing"; exit 1; }; for forbidden in '\.planning/RETROSPECTIVE\.md' '\.planning/MILESTONES\.md' '\.planning/milestones/v1\.0-' '\.planning/milestones/v1\.1-' '\.planning/spikes/00.*/README\.md' '\.planning/spikes/WRAP-UP-SUMMARY\.md' '\.planning/sweep/STORY\.md' '\.planning/research/.*\.md' '\.planning/threads/next-milestone-planning\.md'; do if git show --stat HEAD HEAD~1 2&gt;/dev/null | grep -qE "$forbidden"; then echo "TOUCHED-DISALLOWED-PATH-ABORT: $forbidden"; exit 1; fi; done</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest` exits 0 (SQ-03 gate) — captured as `PYTEST_RC` via `${PIPESTATUS[0]}` so the pipe-to-`tail` does not mask a red run.
    - HEAD or HEAD~1 commit subject matches one of: `^docs: rebrand live planning surface to graph-wiki` or `^chore: fix cores/ → packages/ in spikes/CONVENTIONS.md`.
    - `grep -E 'cores/' .planning/spikes/CONVENTIONS.md` returns empty (BRAND-02 satisfied).
    - `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md` exists (may contain `(none)` as the only data row if no carry-forwards needed).
    - No file under the R-03 allowlist scope was modified by commits 4 or 5 — enforced by the `for forbidden in ...; if git show --stat ... grep -q ...; then exit 1; fi` loop in the verify command.
  </acceptance_criteria>
  <done>Live planning surface + CLAUDE.md + spikes/CONVENTIONS.md rebranded; `12-03-carry-forward-refs.md` written (possibly empty) for plan 04 hand-off; archived/historical scope untouched; tests green. BRAND-01 + BRAND-02 surfaces covered (verification by grep-gate in plan 04).</done>
</task>

</tasks>

<verification>
- `uv run pytest` is green at the end (and was green after each of the 4–5 commits — verified per-commit via SQ-03; each task's verify captures pytest's exit code through `${PIPESTATUS[0]}` so a red run cannot be masked by `tail`).
- The four-or-five rebrand commits are present in `git log --oneline` with the expected subjects.
- No file under R-01/R-02/R-03 allowlist scopes was modified — Task 4 verify includes an explicit `if grep -q ...; then exit 1; fi` loop for each forbidden path pattern.
- `grep -E 'cores/' .planning/spikes/CONVENTIONS.md` returns empty.
- `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md` exists and contains a data row for every intentionally-preserved `lattice` reference (or a single `(none)` row).
</verification>

<success_criteria>
SC#3 (zero `lattice*` hits in in-scope paths) is set up for verification in plan 04; SC#4 (`.planning/spikes/CONVENTIONS.md` reflects `packages/`) satisfied here; SC#5 (`uv run pytest` green after rebrand) maintained per-commit via SQ-03. BRAND-01 and BRAND-02 surfaces edited; final assertion happens in plan 04. Carry-forward inventory is persisted to disk for plan 04's allowlist authoring step.
</success_criteria>

<output>
Create `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-SUMMARY.md`: list of the 4–5 commits landed (subject + short SHA), any cases where Claude's Discretion was exercised (e.g., folding commit 5 into commit 4; deciding a prompt-fragment reference is historical), an explicit pointer to `12-03-carry-forward-refs.md` as the hand-off artifact, and a one-line summary of how many entries it contains (or "empty — no carry-forwards").
</output>
