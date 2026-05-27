# Phase 48: `graph propose-domains` - Discussion Log

**Date:** 2026-05-27
**Phase:** 48 — `graph propose-domains`

This log captures the conversation that produced `48-CONTEXT.md`. For audit / retrospective use only.

---

## Gray Area Selection

User selected all four offered areas:

1. LLM input shape + fan-out strategy
2. LLM output schema + parsing strategy
3. Cross-cutting hub treatment
4. Cycle detection scope + grounding semantics

---

## Area 1: LLM input shape + fan-out strategy

**Q1 — Fan-out strategy:**

Options:
1. Per-cluster fan-out via SubagentPool (Recommended)  ← chosen
2. Single bulk call
3. Hybrid: bulk-name + per-cluster-refine

**User chose:** Option 1 — per-cluster via SubagentPool. One LLM call per cluster, concurrency-bounded, partial-success.

→ Captured as D-01.

**Q2 — Per-package context depth:**

Options:
1. Name + summary + file_map only (Recommended)  ← chosen
2. Name + summary only
3. Name + summary + file_map + README

**User chose:** Option 1 — name + summary + file_map. Mirrors scanner's stub-generation context shape.

→ Captured as D-02.

---

## Area 2: LLM output schema + parsing

**Question:** How does the LLM return its proposal?

Options:
1. Structured JSON via Bedrock tool-use (Recommended)  ← chosen
2. Structured JSON in prose response
3. YAML directly

**User chose:** Option 1 — Bedrock tool-use with strict JSON schema. langchain-aws ChatBedrockConverse.bind_tools support. Zero parsing-failure risk.

→ Captured as D-05 (tool schema), D-06 (ProposeResult dataclass aggregation).

---

## Area 3: Cross-cutting hub treatment

**Q1 — Hub treatment:**

Options:
1. Annotate each cluster's prompt; no dedicated hub-domain (Recommended)
2. Dedicated `core` / `shared` proposed domain  ← chosen
3. Hubs as their own proposed sub-domain candidates
4. Skip hubs entirely

**User chose:** Option 2 — dedicated proposed domain for hubs. Mechanically aggregated, no LLM call.

→ Captured as D-07.

**Q2 — Cluster prompts see hubs as context?**

Options:
1. Cluster prompts include 'hubs used' annotation (Recommended)  ← chosen
2. Cluster prompts don't see hubs at all

**User chose:** Option 1 — cluster prompts include 'hubs used' annotation for naming/description signal. Hubs are NOT in the cluster's packages list.

→ Captured as D-03.

**Q3 — Hub domain name:**

Options:
1. `shared` (Recommended)
2. `core`
3. `cross-cutting`  ← chosen
4. `infrastructure`

**User chose:** Option 3 — `cross-cutting`. Most descriptive; matches Phase 47 terminology.

→ Captured as D-08 (name fixed, not configurable).

---

## Area 4: Cycle detection + grounding

**Q1 — Cycle scope:**

Options:
1. Proposed edges only (Recommended)
2. Proposed + existing domains.yaml unioned  ← chosen

**User chose:** Option 2 — union of proposed + existing parent edges; existing edges immune; strip proposed edges that introduce cycles.

→ Captured as D-10, D-11 (immunity rationale), D-12 (iterative DFS, no networkx).

**Q2 — Grounding for existing-domain packages:**

Options:
1. Validate against `list_packages` only; allow LLM to propose moving existing-domain packages (Recommended)  ← chosen
2. Strip packages already in existing domains
3. Flag conflicts but include both in output

**User chose:** Option 1 — grounding against list_packages only. LLM may propose moving packages from existing domains. domains.proposed.yaml is a human-review artifact.

→ Captured as D-09.

---

## Notable Cross-Phase Consequences

- **Direct dependency on Phase 47's `ClusterResult` dataclass.** Phase 48 imports `compute_clusters` in-process (D-23). Phase 47's JSON output schema (also D-07 of 47-CONTEXT.md) is the IPC contract on disk; in-process call returns the dataclass directly.
- **PROPOSE-05 isolation guard requires verification.** D-17 specifies the Phase 48 plan must research the current state of `packages.refresh`'s allowlist and confirm `domains.proposed.yaml` is excluded. If not, planner adds the exclusion as a small edit.
- **New `domain-proposer` role in models.toml** (D-19) joins existing `scanner`, `narrator` (post-Phase-45). Three role tiers now distinguishable for cost tracking and tuning.
- **No Phase 42-46 dependencies.** Phase 48 lives entirely in agents/graph-wiki-agent + reads from graph-io. Can ship after Phase 47 lands; doesn't wait on wiki-entity-restructure.

---

## Deferred Ideas

Captured in `48-CONTEXT.md` `<deferred>` section. Key items:

- Iterative refinement / self-critique — v1.9 quality improvement.
- Interactive review TUI — out of scope.
- Cross-cluster coherence pass — rejected for v1.8 (added LLM cost).
- Confidence thresholding (`--min-confidence`) — user can grep YAML manually.
- `graph adopt-proposed` command — manual cp/merge in v1.8.
- package_family proposals — Phase 43 deferred to v1.9; Phase 48 follows.
- Multi-parent / graph hierarchies — v1.9 if needed.
- Eval scaffolding for proposal quality — v1.9 separate phase.

---

## Claude's Discretion

Items left to the planner's judgment (documented in `<decisions>` Claude's discretion block):

- Exact prompt wording for `propose_domain` (D-04 is a sketch).
- LLM-call retry policy (lean: SubagentPool's existing retry config, 2 retries).
- Whether `confidence` is exposed in YAML (lean: yes).
- Whether cluster `id` from Phase 47 appears in YAML output (lean: no).
- Banner comment at top of `domains.proposed.yaml` (lean: yes).
- `_build_cross_cutting_domain` when hubs are empty (lean: skip).
- Stripping a domain when ALL its packages are stripped (lean: yes).

---

*Discussion concluded: 2026-05-27*
