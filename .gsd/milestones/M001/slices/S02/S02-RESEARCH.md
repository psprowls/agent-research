# S02 — Research

## Summary

S02 owns active requirements R002 and R003: preserve high-value legacy `.planning` notes without wholesale archive conversion, and label deferred work/caveats so future agents do not treat archived material as active commitments. The evidence is already concentrated in a small set of local planning files, so this is targeted document-curation work rather than broad code research.

The implementation should update the M001 context as the primary artifact. `.gsd/PROJECT.md` already establishes current truth, the v1.0-v1.11 trajectory, and the archive/reference boundary from S01; S02 should not rework that stable source-of-truth artifact unless verification finds a direct contradiction. The slice should add a curated high-notes/caveats section to `.gsd/milestones/M001/M001-CONTEXT.md`, with source-path references to the sampled legacy files and explicit labels for deferred or historical-process-debt items.

## Recommendation

Take a lean curation approach: add a concise, source-linked section to `M001-CONTEXT.md` that preserves the useful historical signal from `.planning/` while repeating the boundary that `.planning/` is reference-only. Group the content into: shipped trajectory high notes, deferred cost-frontier sweep handoff, stale snapshot caveat, historical process-debt caveats, and archive boundary rules. Do not import detailed phase plans, old requirement tables, or all deferred backlog items.

Use `.planning/MILESTONES.md` as the best compact ledger for shipped high notes and known gaps; use `.planning/CONTINUE-sweep-harness-fixes-3.md` for the authoritative deferred sweep handoff; use `.planning/deferred-items.md` for the stale `test_graph_query_output` snapshot caveat; use `.planning/PROJECT.md` only to cross-check the broader deferred/process-debt list and boundary language. This keeps R002/R003 traceable without converting `.planning` into active GSD state.

## Implementation Landscape

### Key Files

- `.gsd/milestones/M001/M001-CONTEXT.md` — primary target. It already contains high-level S02 acceptance language but lacks the detailed curated high-note/caveat set that proves R002/R003. Add a dedicated section such as `## Preserved Legacy High Notes and Caveats` after `Existing Codebase / Prior Art` or before `Scope`.
- `.gsd/PROJECT.md` — S01-stable current-truth frame. It already says `.gsd/` is active, `.planning/` is archive/reference, summarizes v1.0-v1.11, and excludes wholesale conversion, Phase 60 reactivation, and old process-debt completion. Treat as input, not an S02 edit target unless a direct inconsistency is found.
- `.gsd/REQUIREMENTS.md` — R002 and R003 are active and owned by M001/S02. Execution/closeout should validate them after context verification, but the research-stage file change is the context artifact.
- `.planning/MILESTONES.md` — compact source for preserved high notes. Especially relevant: v1.11 TypeScript `type` node kind; v1.10 wiki index/entity enrichment and `graph_io.cli` decoupling; v1.9 builtin/app/short filename work; v1.2-v1.7 package/rebrand/graph/wiki integration trajectory; known gaps around skipped audits and Phase 50 verification.
- `.planning/CONTINUE-sweep-harness-fixes-3.md` — authoritative deferred sweep handoff. Key facts: supersedes round 2; fixes B-F committed/mechanically verified; `$3.46` rerun is explicitly **not authoritative**; on-disk `.planning/sweep/*.md` and `INDEX.md` remain old `$7.02` diagnostic docs and must not be trusted as winners; future work order is debug answer degradation, then clean rerun, then human winner selection.
- `.planning/deferred-items.md` — source for stale snapshot caveat. Key fact: `agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_output` syrupy snapshot is stale because `dev_dependencies: []` was added to package node attrs; fix is snapshot update command, but that is not M001 scope.
- `.planning/PROJECT.md` — broad historical source. Relevant deferred/process-debt notes: skipped formal milestone audits for v1.6/v1.8/v1.9/v1.10, Phase 50 formal verification missing, v1.8/v1.9 per-phase security reviews skipped except Phase 53, Nyquist retro-validation decision overdue, scanner pipeline restructure/dependency clustering/open ontology questions still deferred.
- `.planning/milestones/v1.11-ROADMAP.md` — latest shipped milestone detail. Confirms v1.11 shipped Phase 61 only, includes issues deferred for inline TS `export { type Foo }` handling and Phase 60 sweep run/winner selection.

### Natural Seams / Suggested Tasks

1. **Curate high-note content in M001 context** — Add a concise source-linked section covering the shipped trajectory highlights worth preserving: v1.1 cost-frontier/eval/observability, v1.2 workspace/plugin/rebrand, v1.5 foundational `graph-io` + `source-parser`, v1.6-v1.10 graph/wiki evolution, and v1.11 `type` node fix.
2. **Curate deferred/caveat content in M001 context** — Add a clearly labeled subsection for deferred future work and caveats: cost-frontier sweep debug/rerun/winner selection, stale graph query snapshot, skipped audits/verification/security review process debt, and technical deferred graph/wiki items. Mark each as historical/deferred unless a future milestone adopts it.
3. **Verify S02 and validate R002/R003** — Run an artifact check that proves the context includes required source paths and labels, while avoiding affirmative overclaims like wholesale import, authoritative sweep winners, or active Phase 60 execution. Then update requirements R002/R003 to validated if checks pass.

### Build Order

First update `M001-CONTEXT.md`, because all S02 value is in that artifact and downstream S03 needs this curated caveat set before normalizing active/deferred/out-of-scope requirements. Keep the first pass narrow: insert one well-labeled section rather than spreading caveats across many existing sections. After the content exists, run verification against required phrases/source paths and negation-sensitive boundary checks; only then should requirement status be changed.

### Verification Approach

Use a small `gsd_exec` verifier rather than noisy greps in the main context. Suggested checks:

- `M001-CONTEXT.md` contains a `Preserved Legacy High Notes` / caveats section.
- It references the source files: `.planning/MILESTONES.md`, `.planning/CONTINUE-sweep-harness-fixes-3.md`, `.planning/deferred-items.md`, `.planning/PROJECT.md`, and `.planning/milestones/v1.11-ROADMAP.md`.
- It explicitly includes the terms or equivalents: `cost-frontier`, `not authoritative`, `debug`, `clean re-run`, `winner selection`, `stale snapshot`, `test_graph_query_output`, `Phase 50`, `formal milestone audit`, `security review`, `Nyquist`, `archive/reference`.
- It preserves boundary language that these are deferred/historical/reference items, not active M001 work.
- It does not claim wholesale conversion, exhaustive archive audit, authoritative sweep winners, or completed historical process-debt backfill.

Example verifier shape:

```bash
python - <<'PY'
from pathlib import Path
p = Path('.gsd/milestones/M001/M001-CONTEXT.md')
text = p.read_text()
required = [
  '.planning/MILESTONES.md', '.planning/CONTINUE-sweep-harness-fixes-3.md',
  '.planning/deferred-items.md', '.planning/milestones/v1.11-ROADMAP.md',
  'cost-frontier', 'not authoritative', 'clean re-run', 'winner selection',
  'stale snapshot', 'test_graph_query_output', 'Phase 50',
  'formal milestone audit', 'security review', 'Nyquist', 'archive/reference',
]
missing = [s for s in required if s not in text]
prohibited = [
  'converted the entire .planning archive',
  'authoritative sweep winners selected',
  'Phase 60 is active in M001',
  'historical audits are complete',
]
violations = [s for s in prohibited if s in text]
assert not missing, missing
assert not violations, violations
print('S02 context verification passed')
PY
```

## Constraints

- `.gsd/` is the active planning state; `.planning/` must remain read-only reference evidence.
- S02 should not run or debug the cost-frontier sweep. That work has possible Bedrock cost, quota constraints, and separate technical risk.
- Avoid exhaustive archive conversion. The legacy archive is large and includes many old phases, quick tasks, sketches, spikes, and stale records; S02 should preserve selected high notes only.
- Downstream S03 needs the deferred/caveat list to distinguish active initialization requirements from deferred future work and explicit non-goals.

## Common Pitfalls

- **Promoting deferred work into M001 scope** — The cost-frontier sweep, stale snapshot update, Phase 50 backfill, audits, security review backfills, and Nyquist decision are notes for future planning unless explicitly adopted later.
- **Trusting old sweep docs as authoritative** — `.planning/CONTINUE-sweep-harness-fixes-3.md` says on-disk `.planning/sweep/*.md` and `INDEX.md` are still the old `$7.02` diagnostic and the `$3.46` run was reverted/not authoritative.
- **Over-preserving backlog noise** — Do not copy every deferred bullet from `.planning/PROJECT.md`; preserve categories and the most actionable caveats.
- **Boundary-check false positives** — Verification should allow mentions of prohibited scope when they appear as explicit exclusions; use negation-aware checks like S01 did.

## Open Risks

- The phrase `high notes` can be interpreted broadly. The safest planner choice is to preserve representative shipped trajectory and caveat categories with source links, not an exhaustive list of every legacy accomplishment.
- Some legacy caveats may already have been resolved in current code. S02 should not adjudicate those resolutions; label them as archive caveats requiring current-source verification before future execution.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| GSD/Markdown artifact writing | `write-docs` | Installed and relevant conceptually for making the context readable to a fresh agent; no additional install needed. |
| Python/uv/product runtime | `uv-package-manager`, `python-testing-patterns` | Installed but not central to S02 because this is planning-artifact curation, not runtime/test implementation. |
