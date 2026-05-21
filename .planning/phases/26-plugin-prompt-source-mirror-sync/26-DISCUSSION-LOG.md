# Phase 26: plugin-prompt-source-mirror-sync - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 26-plugin-prompt-source-mirror-sync
**Areas discussed:** Scope, Direction, Anchor reconciliation, Agent-only prompts, Test-provenance strength, Brand-gate scope

---

## Scope (pre-gray-area framing)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — repair + prevent, mirror invariant only | Sync 14 drifted pairs and add mechanical enforcement. Out of scope: agent-side Python prompts | |
| Repair only | Just bring the 14 pairs back in sync; defer enforcement | |
| Expand to include Python-port alignment | Also tackle `prompts/*.py` ↔ `prompt-sources/agents/*.md` alignment | ✓ |
| Different goal | Let me describe it | |

**User's choice:** Expand to include Python-port alignment
**Notes:** Triggered the broader scope question — the discussion immediately pivoted to whether `packages/prompt-sources/` should exist at all.

---

## Direction — canonical source

| Option | Description | Selected |
|--------|-------------|----------|
| plugins/ canonical, prompt-sources mirrors it | Plugin edited first, agent runtime follows; sync script plugin → prompt-sources | |
| packages/prompt-sources/ canonical | Prompt-sources is agent runtime source-of-truth (lattice port); plugin copies from it | |
| Bidirectional, enforce identity | Either side can edit; enforce byte-equality | |
| Collapse to one location | Eliminate the duplication entirely | |

**User's choice (free-text):** "graph-wiki plugin is canonical. Do we even need prompt sources anymore? If so what role would it play? lattice-wiki is fully deprecated and all new development will happen in this repo."
**Notes:** Triggered a deeper investigation into what `prompt-sources/` actually does today (the three-role analysis: test-time anchor, eval-time anchor, Source: comment doc pointers). Confirmed the tree is anchor-only (never loaded at runtime).

---

## Future direction for `packages/prompt-sources/`

| Option | Description | Selected |
|--------|-------------|----------|
| A. Collapse — delete prompt-sources, anchor to plugin | Re-point ~50 anchors + Source: comments; delete tree; extend brand-gate | ✓ |
| B. Buffer — keep as enforced mirror of plugin | Sync script + pre-commit/CI check; sync plugin → prompt-sources once to repair | |
| C. Hybrid — collapse + runtime-load from plugin .md | A plus rewrite prompts/*.py to read markdown at module-load time | |
| Different direction | Let me think about it | |

**User's choice:** A. Collapse — delete prompt-sources, anchor to plugin
**Notes:** Locked the phase shape. C deferred to v1.5+ per CONTEXT.md `<deferred>`.

---

## Areas selected for discussion

| Option | Description | Selected |
|--------|-------------|----------|
| Anchor reconciliation strategy | How to rewrite slugs; what to do if anchored content is missing | ✓ |
| Agent-only prompts (no plugin counterpart) | Where code_reader/synthesizer specs live; where wiki-claude-md-template anchors point | ✓ |
| Test-provenance test strength | Minimal migration vs. semantic-drift upgrade | ✓ |
| Brand-gate enforcement scope | Path literal only, or also Source: prefix enforcement | ✓ |

**User's choice:** All 4 areas selected
**Notes:** Each area produced concrete D-XX decisions.

---

## Anchor reconciliation — Slug rule

| Option | Description | Selected |
|--------|-------------|----------|
| Adopt plugin's GitHub-slug for the current heading | Re-point to whatever the file's heading slugifies to (e.g. `#4-write-the-source-summary`) | ✓ |
| Add explicit HTML anchors to plugin .md | Insert `<a id="…">` markers to preserve old slug strings | |
| Drop section anchor entirely — file-only | Rewrite anchors to bare `ingestor.md`; lose precision | |

**User's choice:** Adopt plugin's GitHub-slug
**Notes:** No plugin .md edits to preserve old slugs; rubric strings churn once during the migration.

---

## Anchor reconciliation — Missing content policy

| Option | Description | Selected |
|--------|-------------|----------|
| Plugin authoritative — update rubric or drop check | Plugin canonical; if content gone, rubric is stale | |
| Restore content to plugin .md | Add dropped sections back to plugin to keep anchor resolving | |
| Case-by-case — list unresolvable anchors in PLAN.md | No blanket rule; audit table; each row decided individually | ✓ |

**User's choice:** Case-by-case audit table
**Notes:** Drives D-13 sequencing — audit is milestone 1 before any re-anchoring.

---

## Anchor reconciliation — Line-range pins

| Option | Description | Selected |
|--------|-------------|----------|
| Drop line ranges, keep section anchors only | `(L48-L56)` removed; section names stable, line numbers churn | ✓ |
| Recompute against current plugin .md | Update L48-L56 to current lines; instantly stale on next edit | |
| Keep both as best-effort hints | Update now; accept drift; no tooling | |

**User's choice:** Drop line ranges
**Notes:** Section names are the durable anchor.

---

## Agent-only prompts — code_reader and synthesizer

| Option | Description | Selected |
|--------|-------------|----------|
| Agent-local sources tree | Move to `agents/.../prompts/sources/{code_reader,synthesizer}.md` | ✓ |
| Plugin stubs marked agent-only | Add to plugin/agents/ with frontmatter excluding from dispatch | |
| Promote rubric files to canonical role specs | Expand `divergence/rubrics/*.md` to contain Workflow/Rules/etc. | |
| Inline — Python module is source of truth | Embed role spec as docstrings; drop Source: comments | |

**User's choice:** Agent-local sources tree
**Notes:** Mirrors plugin/agents/ shape; symmetric and clean.

---

## Agent-only prompts — `LOG_FORMAT` and `STYLE_RULES` anchor target

| Option | Description | Selected |
|--------|-------------|----------|
| Runtime template asset | `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` — the actual canonical source | ✓ |
| Agent-local sources tree | Duplicate of the template under `agents/.../prompts/sources/` | |
| Inline — drop Source: anchor | Treat as agent-owned constants; lose provenance link | |

**User's choice:** Runtime template asset
**Notes:** The asset IS the canonical source; pointing at the runtime artifact preserves the "Source: points at the runtime asset" property.

---

## Test-provenance strength — overall posture

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: re-point + verify path/section resolves | Mechanical migration of existing test | |
| Stronger: verify cited section text appears in the Python prompt | Catches semantic drift; more implementation | ✓ |
| Weaker: drop section check, file-exists only | Simpler test; reduces friction on heading renames | |

**User's choice:** Stronger — semantic drift detection
**Notes:** Implementation signal pinned in next question.

---

## Test-provenance strength — drift signal

| Option | Description | Selected |
|--------|-------------|----------|
| Keyword-overlap threshold | Extract identifiers + capitalized phrases; assert ≥X% appear; tunable | ✓ |
| Fixture-hash canary | Hash cited section; fail on mismatch; highest signal + highest friction | |
| Headline-only check | Verify section heading appears in Python prompt; cheap, catches gross drift only | |
| Defer — Claude's Discretion | Planner picks during plan-phase | |

**User's choice:** Keyword-overlap threshold (start 70%)
**Notes:** D-08 step 3 in CONTEXT.md captures the exact rule.

---

## Test-provenance strength — prefix whitelist

| Option | Description | Selected |
|--------|-------------|----------|
| Strict whitelist | Source: must start with one of the blessed prefixes | ✓ |
| Just require path resolves | Any in-repo path is fine if file + section exist | |

**User's choice:** Strict whitelist
**Notes:** Three allowed prefixes — see D-08 step 1 in CONTEXT.md.

---

## Brand-gate scope — what to block

| Option | Description | Selected |
|--------|-------------|----------|
| Path literal `packages/prompt-sources` only | Simple regex; matches the actual mistake to prevent | ✓ |
| Path literal + Source: prefix enforcement | Also fail on non-whitelisted Source: prefixes; duplicates test_provenance | |
| Path literal + Python `prompt_sources` module references | Both filesystem and Python import path | |

**User's choice:** Path literal only
**Notes:** D-12 — the dir was excluded from the uv workspace; no `prompt_sources` import path ever existed, so the extra coverage is unnecessary.

---

## Brand-gate scope — block shape

| Option | Description | Selected |
|--------|-------------|----------|
| New CHECK block (e.g. CHECK 5) | Phase 18 / Phase 23 pattern; per-block diagnostics | ✓ |
| Extend CHECK 1 alternation regex | Phase 21 pattern; fewer blocks; mixes concerns | |
| Defer to planner | Claude's Discretion | |

**User's choice:** New CHECK block
**Notes:** D-10 — block shape mirrors Phase 18 CHECK 2.

---

## Claude's Discretion

- Agent-local sources tree `__init__.py` presence (D-decisions / Claude's Discretion in CONTEXT.md)
- Exact wording of CHECK 5's grep header and `.brand-grep-allow` entry rationale
- Whether the unresolvable-anchor audit (D-04) is a scratchpad or committed table in PLAN.md / PATTERNS.md
- Specific keyword-extraction heuristic for D-08 step 3 (regex set + stoplist)

## Deferred Ideas

- Runtime-load of plugin markdown by `prompts/*.py` (scope discussion option C) — v1.5+
- Buffer/sync enforcement (scope discussion option B) — fallback if collapse direction turns out wrong
- Plugin-side content audit (correctness review of plugin .md content post-rebrand) — out of Phase 26 scope; potential v1.5+ phase
- Eval-harness regression coverage for the semantic drift check (benchmark dataset) — separate phase if measurement is wanted
</content>
</invoke>