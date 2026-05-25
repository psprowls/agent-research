# Phase 12: Drift Backport + Ecosystem Rebrand (M2) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 12-drift-backport-ecosystem-rebrand-m2
**Areas discussed:** Rebrand scope & exclusions, DRIFT-DECISIONS.md workflow & shape, Substantive vs cosmetic rubric, Atomicity & commit sequencing

---

## Rebrand scope & exclusions

### Q1: Test fixture policy (round-trip-vault/)

| Option | Description | Selected |
|--------|-------------|----------|
| Leave as-is — they're sample data | Round-trip test parses a REAL lattice vault. Renaming would test a fictional vault. Allowlist this directory. | ✓ |
| Snapshot to a generic fictional vault | Rebuild with names like 'sample-plugin'. Loses fidelity to real lattice shapes. | |
| Rename to graph-wiki variants | plugins/graph-wiki/, packages/graph-wiki-core/. Pretends it's a graph-wiki vault. Misleading. | |

**User's choice:** Leave as-is (Recommended).

### Q2: Eval baselines + rubrics policy

| Option | Description | Selected |
|--------|-------------|----------|
| Leave as-is — recorded baselines are historical facts | Allowlist eval-harness baselines + rubric references in BRAND-04. | ✓ |
| Re-record baselines against graph-wiki references | Run a fresh recording pass. Adds Bedrock cost + delays milestone. | |
| Rebrand the prose but keep recorded data | Inconsistent — rubric describes a comparison that doesn't match the data. | |

**User's choice:** Leave as-is (Recommended).

### Q3: Historical planning docs policy

| Option | Description | Selected |
|--------|-------------|----------|
| Leave historical/archived docs untouched; rebrand only live planning surface | Archived ROADMAPs, RETROSPECTIVE, spike READMEs untouched. Rebrand live ROADMAP/REQUIREMENTS/STATE/PROJECT. | ✓ |
| Mass-rebrand everything under .planning/ | Loses provenance. High churn for zero codebase impact. | |
| Leave .planning/ entirely; only rebrand code | Inconsistent — going-forward planning would still say 'lattice'. | |

**User's choice:** Leave historical untouched, rebrand live (Recommended).

### Q4: BRAND-04 grep exclusion encoding

| Option | Description | Selected |
|--------|-------------|----------|
| Allowlist file checked into wiki-io (or repo root) | Single allowlist file consumed by the grep gate. Auditable. | ✓ |
| Inline grep --exclude flags documented in verification doc | Equivalent but less self-documenting. | |
| No allowlist — expect zero hits literally | Only viable if all above chose 'rename'. | |

**User's choice:** Allowlist file at repo root (Recommended).

---

## DRIFT-DECISIONS.md workflow & shape

### Q1: Coverage scope

| Option | Description | Selected |
|--------|-------------|----------|
| All 11 overlapping modules from spike 002 §A | Every module that appears in both lattice-wiki-core and wiki-io, including byte-identical and 'leave' verdicts. | ✓ |
| Only active candidates — lint/* + init_vault + ingest_work_item | Matches BACKPORT-01/02/03 literally. Smaller artifact but loses context. | |
| Only modules we actually backport | Loses 'we considered X and chose to leave it' value. | |

**User's choice:** All 11 overlapping modules (Recommended).

### Q2: File shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single markdown table with file / upstream-commit / LOC Δ / verdict / rationale / backport-commit-sha | Scannable, machine-greppable. | ✓ |
| Per-file H2 section with diff snippet + prose rationale | Heavier doc. Useful for second-guessing each decision. | |
| JSON/YAML structured data file | Worse for human review. Wrong fit for single-developer. | |

**User's choice:** Markdown table (Recommended).

### Q3: Body-diff workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Scripted diff dump → DRIFT-DECISIONS-RAW.md, then verdict in DRIFT-DECISIONS.md | Reproducible. Diff context preserved for future re-read. | ✓ |
| Manual diff -u inline, no raw dump committed | Faster, but diff context not preserved. | |
| Subagent fans out body-diffs in parallel and produces recommendations | Overkill for ~10 files; lower verdict trust. | |

**User's choice:** Two-file workflow with raw dump (Recommended).

### Q4: Location + SHA pinning

| Option | Description | Selected |
|--------|-------------|----------|
| packages/wiki-io/DRIFT-DECISIONS.md, header pins ~/Personal/lattice commit SHA at diff time | Matches BACKPORT-04 text. Resolves 'which version did we diff against'. | ✓ |
| packages/wiki-io/docs/DRIFT-DECISIONS.md | Slightly more discoverable as 'a doc', but minor deviation from spec. | |
| Repo-root DRIFT-DECISIONS.md | Wrong scope — this is wiki-io specific. | |

**User's choice:** packages/wiki-io/DRIFT-DECISIONS.md with SHA-pinned header (Recommended).

---

## Substantive vs cosmetic rubric

### Q1: Substantive criteria (multiSelect)

| Option | Description | Selected |
|--------|-------------|----------|
| Bug fixes | Observable behavior change that prevents an error or wrong result. | ✓ |
| New helper functions / extracted methods used by ported code | Port if wiki-io's overlapping code would benefit. | ✓ |
| New checker rules / new lint cases | Port if the rule applies to graph-wiki vaults. | ✓ |
| Behavior-preserving refactors | Default no in the prompt; user chose yes — keeps wiki-io close to upstream. | ✓ |

**User's choice:** All four (including refactors). Note: this is a deliberate stricter-than-default position — accepts churn in exchange for smaller next-sync diff.

### Q2: Skip criteria (multiSelect)

| Option | Description | Selected |
|--------|-------------|----------|
| Comment-only / docstring-only changes | Skip unconditionally. | ✓ |
| Formatting / whitespace / import-order changes | Skip. | ✓ |
| Anything tied to stripped-out subsystems (work-layer, package-family, CLI main()) | NOT selected — handled via LEAVE-ARCH verdict in the table instead of skip-list. | |
| Changes that touch wiki-io's MCP-boundary error-handling additions (WR-01/WR-02) | Skip / reject — wiki-io diverged on purpose. | ✓ |

**User's choice:** Comments, formatting, MCP-boundary protection. Stripped-subsystem changes handled via `LEAVE-ARCH` verdict instead of skip-list.

### Q3: Verdict vocabulary

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed: PORT / LEAVE-AHEAD / LEAVE-ARCH / LEAVE-COSMETIC / IDENTICAL | Scannable, comparable across rows. | ✓ |
| Freeform verdict text | More expressive but loses at-a-glance audit value. | |
| Just port/leave binary | Loses the 'why' for leave rows. | |

**User's choice:** Fixed vocabulary (Recommended).

### Q4: Closure gate

| Option | Description | Selected |
|--------|-------------|----------|
| All rows have verdict + rationale; ported rows have backport-commit-sha; tests stay green | Three-fold proof: documented, in git, no regression. | ✓ |
| All rows have verdict; ported behavior covered by a new regression test | Stronger but likely overkill for small lint fixes. | |
| All rows have verdict; no per-backport test requirement | Lighter; relies on existing suite. | |

**User's choice:** Verdict + commit SHA + green tests (Recommended).

---

## Atomicity & commit sequencing

### Q1: Backport vs rebrand order

| Option | Description | Selected |
|--------|-------------|----------|
| Backport first, DRIFT-DECISIONS.md committed, THEN rebrand sweep | Body-diff against still-named upstream is easier. Plan: P-A raw diff, P-B verdict+backports, P-C rebrand, P-D grep-gate. | ✓ |
| Rebrand first, then body-diff against rebranded code | Body-diff has to mentally translate every lattice_* → graph_wiki_*. Higher cognitive load. | |
| Interleaved per-file | Smaller steps but more git noise; backports tend to be cross-file. | |

**User's choice:** Backport first (Recommended).

### Q2: Rebrand commit granularity

| Option | Description | Selected |
|--------|-------------|----------|
| One commit per surface: packages, agents, plugins-dir, planning, CLAUDE.md | Logical grouping, easy to review/revert per surface. ~5 commits. | ✓ |
| Single atomic commit for the whole rebrand | Cleaner history but one massive diff. Hard to review/bisect. | |
| Per-file commits | Too noisy. Mechanical renames don't deserve individual commits. | |

**User's choice:** One commit per surface (Recommended).

### Q3: Mid-sweep safety

| Option | Description | Selected |
|--------|-------------|----------|
| Run `uv run pytest` after each surface commit; revert if red | Surface-by-surface keeps blast radius small. Matches SC#5. | ✓ |
| Single sweep + test at the end | Faster if it works; bisect if not. | |
| Type-check + import-resolve as separate gate, tests only at end | Python's late-bound imports mean type-check misses things. | |

**User's choice:** pytest after each surface (Recommended).

### Q4: Grep gate location

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone scripts/check-brand.sh, run in verification | Single source of truth: command + allowlist. Easy to re-run. | ✓ |
| pytest test that shells out to grep | Discoverable but adds non-Python concern to pytest. | |
| Manual ad-hoc grep at phase verification only | No reproducible artifact. | |

**User's choice:** scripts/check-brand.sh (Recommended).

---

## Claude's Discretion

- Whether commit 5 (CONVENTIONS.md `cores/` fix) folds into commit 4 or stays separate — executor's call based on diff cleanliness.
- Exact column widths / formatting of the DRIFT-DECISIONS.md table — readability over rigidity.
- Whether `DRIFT-DECISIONS-RAW.md` is checked in or regenerated on demand (recommend checked-in).
- Whether the brand-allowlist file lives at repo root (`.brand-grep-allow`) or under `scripts/` — pick whichever reads better at the grep invocation site.
- Whether the brand-allowlist file should self-allowlist (since it contains the word `lattice` as a pattern fragment) — recommend yes.

## Deferred Ideas

- Per-backport regression tests as hard requirement (SR-04 keeps soft).
- JSON / structured-data shape for DRIFT-DECISIONS.md (deferred — markdown fits single-developer use).
- Rebranding `~/Personal/lattice/` source tree (out of scope — upstream).
- Rebranding archived/historical planning docs (R-03 — could reconsider in a future polish phase).
- Re-recording eval baselines (R-02 — out of scope unless prompt/model changes meaningfully).
- Wiki self-update against rebranded codebase (Phase 15, BRAND-03).
- Pytest test wrapping `check-brand.sh` (Phase 16 candidate if brand drift recurs).
