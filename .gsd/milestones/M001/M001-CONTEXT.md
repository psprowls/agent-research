# M001: Initialize GSD From Legacy Planning Archive

**Gathered:** 2026-05-31
**Status:** Ready for planning

## Project Description

`agent-research` is a Python `uv` workspace for AWS Bedrock-powered AI tooling. The primary product is `graph-wiki-agent`, a Bedrock-backed reimplementation of the `graph-wiki` Claude Code plugin, exposed as both a CLI and an MCP stdio server. It uses LangChain primitives, `langchain-aws`, an in-house `model-adapter`, and a bounded async `subagent-runtime` instead of a heavier orchestration framework.

This milestone initializes the new `.gsd/` project state from the old pre-fork `getting-shit-done` archive in `.planning/`. The user wants **current truth**, not a full archive conversion. `.planning/` has been backed up and can be consulted later if needed.

## Why This Milestone

The repo has no open legacy milestones and all prior work has been archived. Future work needs a clean current GSD source of truth so agents do not repeatedly rediscover or misinterpret the large `.planning` archive.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Open `.gsd/PROJECT.md` and understand the current product, shipped trajectory, package layout, and active GSD posture.
- Open `.gsd/REQUIREMENTS.md` and see which initialization capabilities are active, deferred, and explicitly out of scope.
- Open `.gsd/milestones/M001/M001-CONTEXT.md` and see why `.planning/` is archive/reference, what high notes were preserved, and what caveats remain.
- Run future GSD execution from a coherent roadmap rather than from archived `.planning` tasks.

### Entry point / environment

- Entry point: GSD artifacts under `.gsd/`; future execution via `/gsd auto`.
- Environment: local repo planning state.
- Live dependencies involved: none for this milestone. The underlying product uses AWS Bedrock and MCP, but initialization itself is local artifact work.

## Completion Class

- Contract complete means: PROJECT, REQUIREMENTS, CONTEXT, DECISIONS, and ROADMAP artifacts exist with internally consistent current-state claims and requirement coverage.
- Integration complete means: GSD artifacts agree with sampled `.planning` sources and current package manifests.
- Operational complete means: future agents can start from `.gsd` without treating `.planning` as active execution state.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- `.gsd/PROJECT.md` describes the current project and not just aspirational or stale legacy state.
- `.gsd/REQUIREMENTS.md` separates active initialization requirements, deferred future work, and out-of-scope archive conversion.
- M001 context preserves the user's exact intent: **current truth**, **manual curation**, **high notes**, and `.planning` as backed-up archive/reference.
- The roadmap slices are artifact-focused and do not claim code changes or wholesale `.planning` conversion.

## Architectural Decisions

### Lean Current-Truth Initialization

**Decision:** Initialize GSD with lean current truth and high-value archive notes, not a full `.planning` conversion.

**Rationale:** The legacy archive is large: sampled evidence found versioned roadmaps/requirements, 42 phase contexts, 148 phase summaries, quick tasks, sketches, spikes, and deferred records. Copying it wholesale would create noisy active artifacts and increase the chance that stale plans are treated as current commitments.

**Alternatives Considered:**
- Full archive import — rejected because the user asked for current truth and already backed up `.planning`.
- Structured archive index — deferred because it is useful only if archive archaeology becomes frequent.

### Manual Curation Over Migration Tooling

**Decision:** M001 uses manual curation, not a reusable migration script/checker.

**Rationale:** The user confirmed manual curation is fine. The immediate goal is to make `.gsd` usable, not to build a converter for an already-backed-up archive.

**Alternatives Considered:**
- Reusable migration automation — rejected for M001 as unnecessary implementation surface.

### Preserve Caveats Without Promoting Them to Active Work

**Decision:** Preserve high-value caveats as deferred or notes unless explicitly scoped into a future milestone.

**Rationale:** The deferred cost-frontier sweep and stale snapshot item matter, but neither is part of initialization execution. Capturing them prevents loss without derailing M001.

**Alternatives Considered:**
- Make deferred sweep work active in M001 — rejected because it is debugging/eval work with possible Bedrock cost and separate technical risk.

## Error Handling Strategy

- Treat stale legacy artifacts as expected, not exceptional.
- Resolve conflicts by preferring latest shipped milestone summaries and current codebase/package evidence.
- Preserve uncertainty explicitly instead of silently converting it into requirements.
- Keep deferred sweep work clearly labeled as deferred future work.
- Verify generated GSD artifacts for internal consistency, traceability, and honest archive boundaries.

## Risks and Unknowns

- Over-importing stale history — would make `.gsd` noisy and potentially misleading.
- Under-preserving deferred work — could cause important sweep/debug context to be lost.
- Archive/code drift — some old milestone claims may no longer match current code; M001 should cite sampled evidence and avoid exhaustive conversion claims.
- Process-debt ambiguity — old skipped audits and verification gaps should be noted as historical caveats, not automatically reopened.

## Existing Codebase / Prior Art

- `.planning/PROJECT.md` — current legacy project description and shipped state through v1.11.
- `.planning/ROADMAP.md` — shipped milestone sequence v1.0 through v1.11.
- `.planning/MILESTONES.md` — high-level shipped-history ledger and known gaps/deferred notes.
- `.planning/milestones/v1.11-ROADMAP.md` — latest shipped milestone details for TypeScript `type` node kind.
- `.planning/CONTINUE-sweep-harness-fixes-3.md` — deferred cost-frontier sweep debug/rerun/winner-selection handoff.
- `.planning/deferred-items.md` — stale graph query snapshot caveat.
- `pyproject.toml` — confirms `uv` workspace and root test/lint configuration.
- `agents/graph-wiki-agent/pyproject.toml` — confirms CLI/MCP package and workspace dependencies.
- `packages/*/pyproject.toml` — confirms current package layout for graph, source parsing, model adapter, subagent runtime, wiki IO, workspace IO, and eval harness.

## Preserved Legacy High Notes and Caveats

This section is a selective, non-exhaustive curation of high-value `.planning/` signal for future agents. It is not a wholesale archive import, does not reopen archived plans, and does not convert deferred legacy work into active M001 scope. Treat the cited paths as evidence references only; `.gsd/` remains the active planning source of truth.

### Shipped Trajectory High Notes

- **v1.1 cost-frontier, eval, and observability foundation** — v1.1 ported lattice-wiki prompt content, added divergence detection and LLM-judge rubrics, validated a Bedrock cost-frontier sweep, proved MCP host cancellation behavior, versioned JSONL trace records, added cost-aware trace rendering, and threaded project context into subagent prompts. Source: `.planning/MILESTONES.md` (`v1.1 Quality Improvements`).
- **v1.2 workspace/plugin/rebrand consolidation** — v1.2 introduced `workspace-io`, completed the `lattice` to `graph-wiki` ecosystem rebrand, locked and ported the Claude Code `/graph-wiki:*` plugin contract, refreshed the project wiki after the rebrand, and carried forward selected follow-up debt rather than treating it as M001 initialization work. Source: `.planning/MILESTONES.md` (`v1.2 Graph-Wiki Port & Debt Cleanup`).
- **v1.5 foundational graph packages and repo rename** — v1.5 retroactively captured the repo rename to `agent-research`, environment variable sweep to `AGENT_RESEARCH_ROOT`, addition of `graph-io` and `source-parser`, final `vault-io` to `wiki-io` rename, and stale documentation cleanup. The package additions were explicitly foundational; wiring them into the agent loop was deferred to later shipped milestones. Source: `.planning/MILESTONES.md` (`v1.5 Repo Rename & Foundational Package Additions`).
- **v1.6 graph ontology expansion** — v1.6 landed `graph-io` schema v2, URI identity, structural repository/package/subpackage/file nodes, entry point and test suite nodes, domain nodes and derived edges, expanded query helpers, new `cg` CLI surfaces, and a graph-wiki brand sweep. Source: `.planning/milestones/v1.6-ROADMAP.md`.
- **v1.7 through v1.10 graph/wiki evolution** — v1.7 integrated `graph-io` into the agent workflow and query tooling; v1.8 added entity-page workflow foundations; v1.9 refined graph classification and slimmed wiki filenames; v1.10 made the generated wiki more readable with enriched index/entity pages and decoupled the agent from `graph_io.cli`. Source: `.planning/MILESTONES.md` (`v1.7 graph-io Integration & Wiki Hygiene`, `v1.8 Wiki Entity Restructure`, `v1.9 Graph Refinements & Wiki Filename Slimdown`, `v1.10 Wiki Index & Entity Page Enrichment`).
- **v1.11 TypeScript `type` node handling** — v1.11 surfaced TypeScript interfaces, type aliases, and enums as a single graph `type` node kind with `ts_kind`, fixed exported-type projection that had mislabeled types as `function`, made `type` cross-kind resolvable in `graph-io`, bumped `DERIVER_VERSION` to force re-derivation, and verified the fix with source-parser, graph-io, and regression suites. Sources: `.planning/MILESTONES.md` (`v1.11 TypeScript Type Node Kind`) and `.planning/milestones/v1.11-ROADMAP.md`.

### Deferred Cost-Frontier Sweep Handoff

This is deferred future debugging/evaluation context, not active M001 execution. Source: `.planning/CONTINUE-sweep-harness-fixes-3.md`.

- `CONTINUE-sweep-harness-fixes-3.md` supersedes `CONTINUE-sweep-harness-fixes-2.md`; the round-2 Fixes B through F were committed and mechanically verified before this handoff.
- The `$3.46` full re-run completed but is **not authoritative** because judge-able answer quality collapsed. Future agents must not treat it as the selected cost-frontier result or use it to update model defaults.
- Existing `.planning/sweep/*.md` files and `.planning/sweep/INDEX.md` remain stale `$7.02` diagnostics from the old run and are also not authoritative winner-selection evidence.
- Future work order is: first debug answer degradation, then perform a clean full re-run, then ask the human to select per-role winners. M001 does not debug the harness, spend Bedrock budget, rerun the sweep, or choose winners.

### Stale Snapshot Caveat

This is a deferred test-maintenance note, not M001 scope. Source: `.planning/deferred-items.md`.

- `agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_output` has a stale syrupy snapshot because quick task `260530-gqp` added `dev_dependencies: []` to package node attributes without updating the snapshot.
- The legacy note says the fix is to run `uv run pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_output --snapshot-update`; M001 records this caveat only and does not update product snapshots.

### Historical Process-Debt Caveats

These are historical/deferred caveats pending future current-source verification, not automatic active work items. Source: `.planning/PROJECT.md`.

- Formal milestone audits were skipped for v1.6, v1.8, v1.9, and v1.10; closure relied on per-phase verification and selected gates rather than retrospective audit backfill.
- Phase 50 in v1.9 was executed and accepted at close, but formal verification was missing.
- Per-phase security reviews were skipped for v1.8 phases 42-48 and v1.9 phases 49-52; Phase 53 did produce a security audit.
- The Nyquist compliance retro-validation decision is overdue because earlier phases did not produce `VALIDATION.md` artifacts despite the toggle being enabled.
- Scanner pipeline restructure, dependency-family/dependency clustering, open ontology questions, and related graph/wiki backlog remain deferred until separately scoped and verified against current source.

### Archive and Active-Scope Boundary Rules

- `.planning/` remains a backed-up archive/reference source. It can provide evidence and caveats, but it is not the active execution graph for M001.
- M001 intentionally does not perform wholesale `.planning` conversion, exhaustive archive audit, legacy milestone backfill, cost-frontier sweep execution, or snapshot maintenance.
- Any future milestone that resumes a legacy item should first verify the claim against current source and then create fresh `.gsd/` requirements and roadmap slices.

## Relevant Requirements

- R001 — M001/S01 establishes `.gsd` as the active current source of truth.
- R002 — M001/S02 preserves legacy high notes without wholesale archive conversion.
- R003 — M001/S02 captures deferred work and caveats as labeled future context.
- R004 — M001/S03 verifies artifact consistency and traceability.
- R005 — M001/S04 produces an execution-ready roadmap.
- R006 — Deferred future milestone for cost-frontier sweep debug and authoritative rerun.
- R007 — Deferred optional archive index.
- R008, R009, R010, R011 — Explicit out-of-scope boundaries, including archive-conversion, migration/backfill, blind-resumption/audit, and cost-frontier execution exclusions.

## Scope

### In Scope

- Curate current truth into GSD artifacts.
- Preserve shipped trajectory high notes through v1.11.
- Preserve deferred/caveat context for the cost-frontier sweep, stale snapshot, and process-debt notes.
- Treat `.planning/` as a backed-up archive/reference.
- Create a small artifact-focused roadmap for completing initialization.

### Out of Scope / Non-Goals

- Wholesale `.planning` conversion.
- Reusable migration tooling.
- Blindly resuming archived plans.
- Exhaustive audit of every legacy phase, quick task, sketch, spike, or archived requirement.
- Debugging/rerunning the cost-frontier sweep in M001.

## Technical Constraints

- `.gsd/` is the active GSD state after initialization.
- `.planning/` remains reference-only and should not be treated as execution state.
- Requirements must be capability-oriented and mapped to slices where active.
- Roadmap slices should be demoable artifact increments, not code layers.
- Future code work should verify against current source, not old planning claims alone.

## Integration Points

- GSD artifact database/tools — `gsd_summary_save`, `gsd_requirement_save`, `gsd_plan_milestone`, and `gsd_decision_save` own rendered planning artifacts.
- Legacy archive `.planning/` — read-only evidence source for high notes and caveats.
- Current package manifests — evidence source for current architecture/package layout.

## Testing Requirements

Verification should include:

- Static artifact checks: PROJECT, REQUIREMENTS, CONTEXT, ROADMAP, and DECISIONS exist and render.
- Traceability checks: active requirements map to M001 slices; deferred/out-of-scope requirements are not mapped as active execution.
- Source-reference checks: cited `.planning` files and package manifests exist.
- Honesty checks: artifacts must not claim wholesale conversion or exhaustive archive audit.

## Acceptance Criteria

- S01: PROJECT captures current product shape, shipped trajectory, current package layout, and archive boundary.
- S02: M001 context captures high-value `.planning` notes, deferred sweep handoff, stale snapshot caveat, and process-debt caveats without over-importing.
- S03: REQUIREMENTS separates active, deferred, and out-of-scope requirements with owners and traceability.
- S04: Final verification demonstrates artifact consistency and readiness for future GSD execution.

## Open Questions

- Whether a future milestone should tackle the deferred cost-frontier sweep rerun and model winner selection — current thinking: yes, but only after a focused debugging milestone is scoped.
- Whether a broader `.planning` archive index will be worth creating later — current thinking: defer until archive archaeology becomes frequent.
