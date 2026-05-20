# Phase 12: Drift Backport + Ecosystem Rebrand (M2) - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Two parallel tracks landing together as the v1.2 "make the codebase actually graph-wiki" milestone step:

1. **Selective drift backport** — body-diff `lattice-wiki-core` against `vault-io` for the modules where vault-io is NOT intentionally ahead (per spike 002 §A); land bug fixes / new helpers / new checker rules / behavior-preserving refactors; explicitly leave-alone the modules vault-io diverged from on purpose (lib-ification, package-family strip, CLI removal, MCP error-handling). Decision per file recorded in `packages/vault-io/DRIFT-DECISIONS.md`.

2. **Ecosystem rebrand** — every remaining `lattice` / `LATTICE` / `lattice_workspace` / `lattice_wiki_core` reference across `packages/`, `agents/`, `.planning/` (live surface only), and `CLAUDE.md` renamed to `graph-wiki` (kebab) or `graph_wiki` (snake). Phase 11 already rebranded the env var (`GRAPH_WIKI_WORKSPACE`) and manifest filename (`.graph-wiki.yaml`); everything else still says lattice.

**In scope:**
- `packages/vault-io/DRIFT-DECISIONS.md` + `DRIFT-DECISIONS-RAW.md` (per-file diff dump + verdict table).
- Backport of substantive changes for the 9 candidate modules from spike 002 §A (lint/*, init_vault.py, ingest_work_item.py, append_log, update_index, update_tokens, layout_io, detect_containers, scan_monorepo, ingest_source — total 11 rows including byte-identical git_state.py).
- Rebrand sweep across `packages/vault-io/src/` (12 modules with hits), `packages/eval-harness/src/` (rubric/source files, NOT baselines), `agents/graph-wiki-agent/src/`, `CLAUDE.md`, and the live `.planning/` surface (current ROADMAP.md section, REQUIREMENTS.md, STATE.md, PROJECT.md current sections).
- `.planning/spikes/CONVENTIONS.md` `cores/` → `packages/` correction (BRAND-02).
- `scripts/check-brand.sh` — reproducible BRAND-04 grep-gate consuming an allowlist file.
- Brand-allowlist file at repo root encoding the legitimate exclusions enumerated in this context.

**Out of scope (delegated to later phases or excluded entirely):**
- Plugin spec / plugin port (Phases 13–14).
- Wiki self-update against rebranded codebase (Phase 15, BRAND-03).
- v1.1 carry-forward debt (Phase 16: TRACE-FU-01, SWEEP-FU-02/03/04, MCP-CAN-01/02, MODEL-FU-01).
- Restoring package-family monorepo support (PROJECT.md "Explicitly out of v1.2").
- Restoring the `work/` subsystem (PROJECT.md "Explicitly out of v1.2"; GSD covers work-item lifecycle).
- Rebranding the `~/Personal/lattice/` source tree references in commit messages or historical commit-history pointers (R-03).
- Rebranding archived planning docs, RETROSPECTIVE, spike READMEs, eval baselines, or round-trip-vault test fixtures (R-01..R-03; see allowlist).

</domain>

<decisions>
## Implementation Decisions

### Rebrand scope & exclusions

- **R-01:** Test fixtures under `packages/vault-io/tests/fixtures/round-trip-vault/` stay verbatim. They contain real lattice plugin/package directory names (`plugins/lattice-wiki/`, `plugins/lattice-graph/`, `plugins/lattice-workspace/`, `packages/lattice-wiki-core/`, etc.) and exist precisely to verify byte-identical round-trip parsing of a real lattice vault. Renaming them would test a fictional vault. The entire `round-trip-vault/` directory is allowlisted in BRAND-04.
- **R-02:** Eval-harness baselines and divergence rubrics stay verbatim. Specifically: `packages/eval-harness/baselines/divergence-*.json` (recorded outputs against lattice-wiki on a pinned commit), `packages/eval-harness/src/eval_harness/divergence/rubrics/*.md` (rubric prose that names lattice-wiki as the comparison baseline), and the `lattice-wiki` literals inside `packages/eval-harness/src/eval_harness/baseline.py` + `pricing.py` if they reference recorded data. Renaming would lie about what was measured.
- **R-03:** Historical / archived planning docs untouched. Specifically the allowlist includes: `.planning/RETROSPECTIVE.md`, `.planning/MILESTONES.md`, `.planning/milestones/v1.0-*.md`, `.planning/milestones/v1.1-*.md`, `.planning/spikes/002-lattice-drift-inventory/README.md`, `.planning/spikes/001-subagent-context-audit/README.md`, `.planning/spikes/WRAP-UP-SUMMARY.md`, `.planning/sweep/STORY.md`, `.planning/research/*.md`. Rebrand only the live planning surface: `.planning/ROADMAP.md` current-milestone section (Phases 11+), `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/PROJECT.md` current sections (NOT historic key-decisions-log entries with dated `lattice` references), `.planning/threads/next-milestone-planning.md` is provenance and stays.
- **R-04:** Encode the exclusions in a checked-in allowlist file at repo root (e.g., `.brand-grep-allow`) consumed by the BRAND-04 grep gate. Format: one path or path-glob per line; lines starting with `#` are comments. Future runs are reproducible without re-deriving the exclusion command each time.

### DRIFT-DECISIONS.md workflow & shape

- **DD-01:** Cover **all 11 overlapping modules** from spike 002 §Investigation A — including the byte-identical `git_state.py` and the `LEAVE-AHEAD` modules. Single canonical artifact future-Pat can scan without cross-referencing the spike.
- **DD-02:** Single markdown table with columns: `file | upstream-commit | LOC Δ | verdict | rationale (one line) | backport-commit-sha (or — for non-PORT)`. Prose appendix only if a decision needs more nuance than one line.
- **DD-03:** Two-file workflow. `packages/vault-io/DRIFT-DECISIONS-RAW.md` holds the scripted per-file `diff -u <vault-io-file> <upstream-file>` dump (one `### file.py` section per file with the unified diff inline). `packages/vault-io/DRIFT-DECISIONS.md` holds the human verdict table and references the raw dump.
- **DD-04:** Lives at `packages/vault-io/DRIFT-DECISIONS.md`. Header block pins: `Upstream: lattice-wiki-core @ 1b45172a9900842b0f8eea525c8270e7fff50605 at 2026-05-18` (current `~/Personal/lattice` HEAD at diff time). Re-syncs in a future phase bump the SHA and re-run the diff.

### Substantive vs cosmetic rubric

- **SR-01 (PORT criteria — any of):**
  - Bug fixes (observable behavior change that prevents an error or wrong result).
  - New helper functions / extracted methods that vault-io's overlapping code would benefit from.
  - New checker rules / new lint cases applicable to graph-wiki vaults.
  - Behavior-preserving refactors (renames, extractions, reformatting) — port these too. Rationale: keeps vault-io close to upstream where the divergence isn't intentional, shrinks the diff for the next sync. Caveat: do NOT port a refactor that drags in stripped-subsystem code (work-layer, package-family); those get `LEAVE-ARCH` verdicts on the affected files.

- **SR-02 (Skip criteria — any of):**
  - Comment-only / docstring-only changes.
  - Formatting / whitespace / import-order changes.
  - Changes that would undo vault-io's MCP-boundary error-handling additions (WR-01 `raise_exception=True`, WR-02 stderr-JSON in lieu of `sys.exit`). These are intentional forks — verdict `LEAVE-AHEAD` with rationale referencing WR-01/WR-02.

- **SR-03 (Verdict vocabulary — fixed set):**
  - `PORT` — substantive upstream change landed; row has a backport-commit-sha.
  - `LEAVE-AHEAD` — vault-io is intentionally ahead of upstream (lib-ification, MCP error-handling, no-tiktoken). Includes per-decision reference.
  - `LEAVE-ARCH` — upstream serves a subsystem vault-io stripped (work-layer, package-family, CLI main()). Per PROJECT.md "Explicitly out of v1.2".
  - `LEAVE-COSMETIC` — only comment / formatting / docstring diff; nothing observable.
  - `IDENTICAL` — `diff -q` reports no difference.

- **SR-04 (Closure gate for BACKPORT-01/02/03):** All 11 rows have verdict + one-line rationale; `PORT` rows have a backport-commit-sha in the row; `uv run pytest` stays green at the end. No per-backport new regression test required by default; if a backport introduces behavior that wasn't covered by an existing test, the executor adds a minimal test in the same commit.

### Atomicity & commit sequencing

- **SQ-01 (Phase order):**
  1. **P-A: Raw diff dump.** Run a bash script that per-file `diff -u`s every overlapping module against `~/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/...`; commit `DRIFT-DECISIONS-RAW.md` with the dumps embedded. Pin upstream SHA in the file header.
  2. **P-B: Verdict + backports.** Read each diff, write the verdict row, land any `PORT` changes in vault-io as separate atomic commits (one commit per backport), update the row with the backport SHA. Commit the final `DRIFT-DECISIONS.md`.
  3. **P-C: Rebrand sweep.** Five commits per SQ-02. Body-diff against still-named upstream is easier (filenames/symbols match) — that's why this step comes after P-B but BEFORE the rebrand makes the upstream comparison harder.
  4. **P-D: Grep-gate + verification.** Land `scripts/check-brand.sh` + `.brand-grep-allow`. Run it; expect zero unallowlisted hits. Run `uv run pytest`; expect green.

- **SQ-02 (Rebrand commit granularity):** One commit per surface. Five commits:
  1. `refactor: rebrand lattice → graph-wiki in packages/` (vault-io src, eval-harness non-baseline src — does NOT touch round-trip-vault/, baselines, rubrics).
  2. `refactor: rebrand lattice → graph-wiki in agents/graph-wiki-agent`.
  3. `chore: create empty plugins/ directory placeholder` (only if not already present; Phase 14 will populate it).
  4. `docs: rebrand live planning surface to graph-wiki` (live ROADMAP/REQUIREMENTS/STATE/PROJECT/CLAUDE.md per R-03 scope).
  5. `chore: fix cores/ → packages/ reference in spikes/CONVENTIONS.md` (BRAND-02; tiny fix; could fold into commit 4 if cleaner).

- **SQ-03 (Mid-sweep safety):** Run `uv run pytest` after EACH surface commit. If red, fix or revert before moving to the next surface. This is the SC#5 ("full test suite passes after the rebrand") protective gate.

- **SQ-04 (Grep-gate script):** Standalone `scripts/check-brand.sh` consuming `.brand-grep-allow`. Sample command shape:
  ```bash
  HITS=$(grep -rEl 'lattice|LATTICE|lattice_workspace|lattice_wiki_core' \
      packages/ agents/ .planning/ CLAUDE.md \
    | grep -vF -f .brand-grep-allow)
  test -z "$HITS"
  ```
  Phase 12 verification runs this script; future re-runs (e.g., before merging Phase 14) re-run it cheaply.

### Claude's Discretion

- Whether commit 5 (CONVENTIONS.md fix) folds into commit 4 or stays separate — executor's call based on diff cleanliness.
- Exact column widths / formatting of the DRIFT-DECISIONS.md table — readability over rigidity.
- Whether `DRIFT-DECISIONS-RAW.md` is checked in or regenerated on demand (recommend checked-in so future readers don't have to re-resolve the upstream SHA).
- Whether the brand-allowlist file lives at repo root (`.brand-grep-allow`) or under `scripts/` (`scripts/brand-allow.txt`) — pick whichever reads better at the grep invocation site.
- Symbol-by-symbol rename of `LatticeConfig` → `GraphWikiConfig` etc. inside `packages/vault-io/src/` if any survive — most should be gone after Phase 11's delegation rewrite, but executor checks.
- Whether the `.brand-grep-allow` file itself should be added to its own allowlist (since it literally contains the word "lattice" as a pattern fragment) — yes, recommend self-allowlist.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & planning artifacts
- `.planning/ROADMAP.md` §Phase 12 — phase goal, success criteria, requirement mapping (BACKPORT-01..04, BRAND-01/02/04; BRAND-03 belongs to Phase 15).
- `.planning/REQUIREMENTS.md` — full text for BACKPORT-01 (lint/*), BACKPORT-02 (init_vault.py), BACKPORT-03 (ingest_work_item.py), BACKPORT-04 (DRIFT-DECISIONS.md location), BRAND-01 (rename surfaces), BRAND-02 (CONVENTIONS.md `cores/`), BRAND-04 (grep-gate).
- `.planning/threads/next-milestone-planning.md` §"Revised Plan (post-spike-002) §M2" — port scope, module table with action column, ecosystem rebrand scope, modules-NOT-ported list.
- `.planning/spikes/002-lattice-drift-inventory/README.md` §Investigation A — drift map (8-row module table), source-only-in-lattice module table, "vault-io is a deliberate fork" framing. This is the empirical evidence for the verdict column. Allowlisted from BRAND-04 (R-03).
- `.planning/PROJECT.md` §Current Milestone — "Explicitly out of v1.2" enumerates what NOT to backport (work-layer, package-family, modules vault-io is ahead on).
- `.planning/phases/11-workspace-io-port-m1/11-CONTEXT.md` — Phase 11 decisions (D-01..D-16): env var name, manifest filename, delegation shim shape, clean-slate posture. Phase 12 builds on these.

### Source code being diffed (read-only references)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/*.py` — upstream lint modules. 7 of 9 differ from `packages/vault-io/src/vault_io/lint/*.py` per a fresh `diff -q` run. Largest delta: `common.py` (+18 LOC upstream).
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/init_vault.py` — upstream candidate for BACKPORT-02.
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_work_item.py` — upstream candidate for BACKPORT-03 (PROJECT.md recommends `LEAVE-AHEAD` since vault-io's `file_work_item` lib shape fits MCP).
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/{git_state,append_log,update_index,update_tokens,layout_io,detect_containers,scan_monorepo,ingest_source}.py` — the rest of the overlapping module set.
- Upstream SHA at diff time: `1b45172a9900842b0f8eea525c8270e7fff50605` (current `~/Personal/lattice` HEAD). Pinned in DRIFT-DECISIONS.md header.

### Existing deep-agents code that changes
- `packages/vault-io/src/vault_io/lint/*.py` — `PORT` rows land here. 7 candidate files (excluding `__init__.py` empty, `domain.py` identical).
- `packages/vault-io/src/vault_io/init_vault.py` — rebrand surfaces visible (`/lattice-wiki:scan`, "lattice workspace" prose, `.lattice.yaml` docstring); may also receive a `PORT` from BACKPORT-02 depending on body-diff.
- `packages/vault-io/src/vault_io/{update_index,scan_monorepo,ingest_work_item,init_vault,git_state,layout_io,ingest_source,update_tokens,append_log}.py` — 12 src files have `lattice` grep hits; mostly docstrings, error messages, and a few `.lattice.yaml` legacy strings. Rebrand sweep updates these.
- `packages/vault-io/src/vault_io/__init__.py` — single `lattice` reference (likely a docstring). Sweep updates.
- `packages/vault-io/tests/{test_lint_modules,test_ingest_source,test_ingest_work_item,test_wikilink_predicate}.py` — `lattice` refs in test prose / expected strings; sweep updates, but pre-check whether the reference is testing real vault data (then it's allowlisted per R-01) vs prose.
- `packages/eval-harness/src/eval_harness/{baseline,pricing}.py` — preliminary grep shows hits; executor verifies whether they reference baseline data (allowlist per R-02) vs implementation prose (rebrand).
- `packages/eval-harness/tests/*.py` — same disambiguation: test data references vs identifier references.
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — Phase 11 already updated `--vault` help text; sweep verifies no surviving `lattice` references in CLI surface.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/*.py` + `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/*.py` — sweep updates any remaining `lattice` references in command prose and prompt fragments.
- `CLAUDE.md` (repo root) — sweep updates the prose (the file already references graph-wiki / lattice-wiki together; current-state language gets rebranded, historical references in commit-history-style prose may need allowlisting case by case).
- `.planning/ROADMAP.md` (active sections), `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/PROJECT.md` (current sections only — see R-03).
- `.planning/spikes/CONVENTIONS.md` — `cores/` → `packages/` (BRAND-02).
- `scripts/check-brand.sh` (NEW) — see SQ-04. Owns the BRAND-04 grep command.
- `.brand-grep-allow` (NEW, repo root) — see R-04. Owns the exclusion allowlist.
- `packages/vault-io/DRIFT-DECISIONS.md` (NEW) — see DD-04.
- `packages/vault-io/DRIFT-DECISIONS-RAW.md` (NEW) — see DD-03.

### Project-level constraints
- `CLAUDE.md` — Python 3.11+, uv workspace, no tiktoken (informs `update_tokens.py` `LEAVE-AHEAD` verdict), MCP error-handling pattern (WR-01/WR-02 informs `LEAVE-AHEAD` verdicts).
- Memory `[[project_wiki_setup]]` — deep-agents wiki at `~/Personal/wiki/deep-agents` is the Phase 15 self-update target; Phase 12 does NOT touch the wiki itself.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 11 delegation shim** (`packages/vault-io/src/vault_io/_workspace.py`) — already rewritten as a `workspace_io.config.resolve()` passthrough. No further changes expected here unless a body-diff against lattice surfaces something.
- **`grep -rEl` infrastructure** — Phase 11 used the same grep family for env-var sweep; SQ-04's `check-brand.sh` is a polished version of that ad-hoc command.
- **Phase 11 pattern: rebrand env var + docstrings across many files in a single commit** — repeatable; Phase 12 just operates on a wider surface (no env var changes — those landed in Phase 11).

### Established Patterns
- **One-source-of-truth artifacts in `packages/vault-io/`** — Phase 11's `_workspace.py` shim is the delegation contract; Phase 12 adds `DRIFT-DECISIONS.md` as the per-file drift contract. Both are inside the package they describe.
- **Provenance comments** — Phase 9 / 10 fragments use `# Source: / # Anchor: / # Source-commit:` headers. Apply the same shape to any backported helper inside vault-io that's lifted verbatim from upstream (helps the next sync trace what came from where).
- **Atomic per-surface commits** — Phase 11's M1 sweep used per-source-tree commits (workspace-io scaffold → port modules → port tests → vault-io shim → CLI rebrand → docs decision). Phase 12's SQ-02 mirrors that pattern.
- **`uv run pytest` as the green-or-revert gate** — used through v1.0 + v1.1; SQ-03 doesn't introduce a new gate, just enforces it per surface.

### Integration Points
- **No new package boundary changes.** All work is intra-package within `vault-io`, `eval-harness` (rubric prose only), `agents/graph-wiki-agent` (prose only), and `.planning/`.
- **No MCP boundary changes.** Phase 11 D-02 (two-tier passthrough) is unaffected; vault-io's `resolve_wiki_and_repo` signature is bit-identical.
- **`scripts/check-brand.sh` consumed by:** Phase 12 verification, future Phase 13–16 verifications (cheap re-run), any future re-sync between vault-io and upstream lattice-wiki-core.
- **No trace / observability pipeline touch.** Rebrand of trace JSONL schema is out of scope (Phase 16 owns TRACE-FU-01).

</code_context>

<specifics>
## Specific Ideas

- **Pin the upstream SHA in `DRIFT-DECISIONS.md` header** (`1b45172a9900842b0f8eea525c8270e7fff50605`, current `~/Personal/lattice` HEAD as of 2026-05-18). Future re-syncs bump the SHA and re-run the diff — the file becomes an auditable history of vault-io's relationship to upstream.
- **Behavior-preserving refactors get ported too** (SR-01). Surprising-looking choice but deliberate: shrinks the next-sync diff and keeps vault-io close to upstream where divergence isn't intentional. Executor must NOT port a refactor that drags in stripped-subsystem code — those rows get `LEAVE-ARCH` verdicts.
- **`scripts/check-brand.sh` is the long-lived artifact.** It lives past Phase 12 — Phases 13, 14, 16 all re-run it cheaply during their own verification. Allowlist file is its companion; both versioned together.
- **The five rebrand commits are reviewable independently.** If the agents-sweep introduces a test regression, revert that commit and keep the packages-sweep landed.
- **`.brand-grep-allow` self-allowlisting:** the file itself contains the word `lattice` as part of its pattern documentation, so the script's grep must exclude this file too (either by path or by the filtering step).

</specifics>

<deferred>
## Deferred Ideas

- **Per-backport regression tests as a hard requirement** — SR-04 keeps this soft (only add tests for behavior not covered by existing suite). If a future sync surfaces a class of upstream changes that the existing suite doesn't catch, tighten the rubric in a follow-up phase.
- **JSON / structured-data shape for DRIFT-DECISIONS.md** — single-developer tool; markdown table fits. Could change if a future tool wants to consume it programmatically.
- **Rebranding the `~/Personal/lattice/` source tree** — out of scope entirely. lattice is upstream; deep-agents doesn't own it.
- **Rebranding archived/historical planning docs** — explicit R-03 decision. Could reconsider in a future "documentation polish" phase if the historical references confuse contributors, but provenance value is real.
- **Re-recording eval baselines against rebranded code** — out of scope per R-02. Baselines are a record of measured behavior; only re-record if the prompt or model meaningfully changes (Phase 7 already validated cost-frontier picks).
- **Wiki self-update against rebranded codebase** — Phase 15 (BRAND-03). Scanning + ingesting `~/Personal/wiki/deep-agents` against the post-rebrand repo happens AFTER Phase 14's plugin port lands.
- **Add a `pytest` test that shells out to `check-brand.sh`** — alternative to Phase 12 verification owning the call. Could land in Phase 16 if "brand drift" becomes a recurring concern.

</deferred>

---

*Phase: 12-drift-backport-ecosystem-rebrand-m2*
*Context gathered: 2026-05-18*
