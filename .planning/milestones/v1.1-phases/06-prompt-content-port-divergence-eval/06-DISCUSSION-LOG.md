# Phase 6: Prompt Content Port + Divergence Eval - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 6-Prompt Content Port + Divergence Eval
**Areas discussed:** Prompt module layout, Port fidelity (verbatim vs adapted), Divergence metric mechanism, Baseline + scope (synthesizer/code-reader)

---

## Prompt module layout

| Option | Description | Selected |
|--------|-------------|----------|
| One file per role | `prompts/{role}.py` each exporting a single SYSTEM string; shared rules duplicated inline per role | |
| Composable fragments | `prompts/_fragments/` (iron_rules, citation_rules, page_categories, refusal_patterns) composed by per-role files | ✓ |
| Markdown source + thin loader | `prompts/{role}.md` with a tiny loader at import time | |

**User's choice:** Composable fragments
**Notes:** Fragment composition wins because iron rules and page-category content overlap verbatim across all four lattice-wiki agent files; deduplication > the indirection cost. Per-role files compose fragments at import time; downstream call sites import a single `*_SYSTEM` string.

---

## Provenance comment encoding (PORT-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Inline header comment per fragment | Top of each fragment file: `# Source:`, `# Anchor:`, `# Source-commit:` | ✓ |
| Structured metadata dict | Each fragment exports a `PROVENANCE` dict alongside content | |
| Single PROVENANCE.md table at prompts/ | One central table aggregating all fragments | |

**User's choice:** Inline header comment per fragment
**Notes:** Simple grep-friendly; lives next to the content it documents; no separate registry to drift from.

---

## Canonical-source drift detection

| Option | Description | Selected |
|--------|-------------|----------|
| CI script that compares source SHAs | Pytest iterates fragments, fetches sibling-repo source, fails if SHA differs | |
| Manual re-sync, no automation | Provenance is documentation only; rely on attention | |
| Vendored copy under cores/prompt-sources/ | Copy canonical sources verbatim into repo at port time | ✓ |

**User's choice:** Vendored copy under `cores/prompt-sources/`
**Notes:** Decouples agent package from sibling lattice repo; cleaner for the eventual OSS release; drift detection becomes a trivial in-repo diff plus a `Source-commit` comparison when re-vendored.

---

## Port fidelity (verbatim vs adapted)

| Option | Description | Selected |
|--------|-------------|----------|
| Adapted — rewrite tool/host refs, preserve semantic rules | Strip slash-command + Claude-Code-SDK references; preserve iron rules, citation rules, page-type routing, refusal patterns verbatim | ✓ |
| Verbatim canonical block + adaptation layer | Two-layer per-role prompt: verbatim block + override block | |
| Verbatim everything | Copy source verbatim including host-specific lines | |

**User's choice:** Adapted — rewrite tool/host refs, preserve semantic rules
**Notes:** Tool surface in `graph-wiki-agent` is different from Claude Code's; verbatim slash-command refs would waste tokens at best and confuse tool-calling at worst. Adaptation is local to per-role composition layer; shared fragments stay closer to canonical wording.

---

## Divergence metric mechanism (EVAL-11)

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid — rules for structural, judge for semantic | Programmatic checkers for deterministic items + `GEval` panel for semantic items | ✓ |
| Rule-based only | Pure programmatic, no judge cost | |
| Judge-only | Single LLM-judge against SKILL.md context | |

**User's choice:** Hybrid
**Notes:** Programmatic for wikilink-resolves / citation-present / frontmatter-valid / page-type-routing; LLM-judge (Phase 4 heterogeneous panel: `claude-sonnet-4-6` + `nova-pro-v1:0`) for refusal-pattern appropriateness and semantic iron-rule violations.

---

## Per-role rule definitions

| Option | Description | Selected |
|--------|-------------|----------|
| Per-role rule modules under cores/eval-harness/divergence/ | One file per role exporting `DivergenceCheck` lists | ✓ |
| Single divergence rule registry (YAML/TOML) | One config file at `divergence/rules.toml` | |
| Rules co-located with prompts under prompts/_fragments/ | Each fragment ships its own check list | |

**User's choice:** Per-role rule modules under `cores/eval-harness/divergence/`
**Notes:** Schema locked: `DivergenceCheck(id, source_anchor, severity, check)`. Rule IDs follow `<ROLE>-<NNN>-<slug>` (e.g., `LIB-001-wikilink-resolves`); `source_anchor` points back to the vendored canonical source for two-way traceability.

---

## Baseline storage + acceptance flow (EVAL-13)

| Option | Description | Selected |
|--------|-------------|----------|
| Single JSON snapshot per role | `baselines/divergence-{role}.json` with per-check counts + accepted-failures excerpts | ✓ |
| Per-fixture pinned expectations | `expected_divergences.json` next to each fixture | |
| Aggregate count threshold only | Per-role failure rate only; no concrete examples | |

**User's choice:** Single JSON snapshot per role
**Notes:** Schema locked (preview shown during discussion). `accepted_failures` array satisfies EVAL-12's "concrete examples" clause. `--accept-divergence-baseline` rewrites the file. Hard-severity check increases fail the gate; soft-severity is reported only.

---

## Synthesizer + code-reader scope

| Option | Description | Selected |
|--------|-------------|----------|
| Move to prompts/ but don't content-port | Refactor for uniformity; no port (no canonical source exists) | ✓ |
| Defer entirely — leave inline in query.py | Phase 6 touches only the 4 PORT-named roles | |
| Full port: extract + author a rules doc | Create canonical doc under `cores/prompt-sources/` for these roles | |

**User's choice:** Move to `prompts/` but don't content-port
**Notes:** Avoids leaving the prompt code split between `prompts/` and `commands/query.py`. No divergence checks for these roles in Phase 6 since there is no canonical source to compare against.

---

## LLM-judge rubric input

| Option | Description | Selected |
|--------|-------------|----------|
| Curated per-role rubric file | `divergence/rubrics/{role}.md` distills canonical rules into binary scoring criteria | ✓ |
| Vendored SKILL.md + agent.md embedded directly | Judge loads canonical sources verbatim | |
| Embed rules inline in DivergenceCheck definition | Each judge-type check carries its own scoring prompt | |

**User's choice:** Curated per-role rubric file
**Notes:** Agent prompts tell the agent how to behave; rubrics tell the judge what counts as a violation — different jobs, different artifacts. Rubric files carry provenance comments pointing to source anchors in `cores/prompt-sources/`.

---

## Claude's Discretion

- Detailed file/module names within `prompts/_fragments/` — left to the planner once source files are read end-to-end.
- Specific fixture additions for divergence checks (e.g., a "no-evidence question" fixture for refusal coverage) — planner/researcher identifies gaps vs Phase 4 fixture corpus.
- Whether to add a `scripts/re-vendor-prompt-sources.py` helper — planner decides if it pays back this phase or gets deferred.

## Deferred Ideas

- Synthesizer + code-reader content port (no canonical source exists yet).
- Re-vendor automation script.
- Pre-commit hook for source-SHA drift detection.
- Per-fixture pinned divergence expectations.
- Divergence dashboard / trend report (natural fit for Phase 9).
</content>
</invoke>