---
status: passed
phase: 48-graph-propose-domains
verified: 2026-05-27
requirements_checked: [PROPOSE-01, PROPOSE-02, PROPOSE-03, PROPOSE-04, PROPOSE-05, PROPOSE-06]
plans_verified: ["48-01", "48-02", "48-03"]
test_counts:
  unit: 13
  integration: 8
  regression_packages_green: ["model-adapter", "graph-io", "wiki-io", "graph-wiki-agent"]
human_verification: []
---

# Phase 48 — graph propose-domains — VERIFICATION

## Goal

> `graph-wiki-agent graph propose-domains` consumes `cg domain-clusters` output, fans out to an LLM, validates every proposed package name against the live graph, strips cycle-introducing edges, and writes `domains.proposed.yaml` — a human-review artifact that never auto-applies and cannot be mistaken for authoritative domain config.

**Verdict: PASSED.** All 6 PROPOSE-XX requirements satisfied; all 5 ROADMAP success criteria are observably true from disk; 21 net new tests pass (13 unit + 4 e2e + 4 isolation); zero regressions in the 4 upstream-package test suites.

## Requirement Traceability

| Req ID | Status | Evidence |
|--------|--------|----------|
| **PROPOSE-01** | ✓ Met (with v1.8 caveat) | `commands/graph.py` registers `propose-domains` under `graph_app` (`graph_app.command(name="propose-domains")(propose_domains_cmd)`). `propose_domains_cmd` body imports `compute_clusters` and runs it in-process (D-23). `--help` shows all three flags. Per-package describe context is a no-op loader in v1.8 (Plan 02 SUMMARY documents the deferral); LLM still gets cluster member names + cross-cutting hub annotation. v1.9 fills in summary+file_map. |
| **PROPOSE-02** | ✓ Met | `_strip_unknown_packages` filters proposals against `{n.name for n in list_packages(conn)}`, accumulates stripped names, emits per-strip `typer.echo(..., err=True)` warning. Unit-tested: `test_strip_unknown_packages_filters_invalid`, `test_strip_unknown_packages_drops_empty_domain`. E2E-verified via integration tests using a sample workspace with 5 real packages. |
| **PROPOSE-03** | ✓ Met | `_strip_cycle_edges` runs iterative-DFS grey/black coloring over `union(proposed, existing)`; existing edges immune; per-strip warning emitted. Unit-tested: 4 cases (basic, deterministic, existing-immune, no-cycle). Iterative-DFS — no recursion, no networkx dep (D-12). |
| **PROPOSE-04** | ✓ Met | `_write_proposed_yaml` emits banner + `yaml.safe_dump({"proposed_domains": ..., "metadata": ...}, sort_keys=True, default_flow_style=False)`. Unit-tested explicitly: `test_write_proposed_yaml_schema` (positive shape), `test_write_proposed_yaml_no_domains_key` (asserts NO top-level `domains:` key — the schema differentiation). |
| **PROPOSE-05** | ✓ Met | Structurally guaranteed by `graph_io.domains._load_domains_yaml(repo_root)` reading `domains.yaml` by literal filename (CONTEXT D-17 documents this; the planner correctly identified that no allowlist edit was needed). Regression-tested by 4 isolation tests (Task 48-03-02): real `cg update` against a workspace with both files produces zero `belongs_to_domain` edges from the proposed file, a fake unique package name never appears in nodes or edges, `list_domains` returns only the `domains.yaml` entries, and a structural-static scan asserts no module in `packages/graph-io/src/graph_io/**` references the proposed filename. |
| **PROPOSE-06** | ✓ Met (with v1.8 caveat) | New `[roles.domain-proposer]` in both `models.toml` files (Plan 48-01). `make_llm("domain-proposer", model_override=...)` accepts the override (D-21). `SubagentPool.run_all` writes per-call JSONL trace records with `role="domain-proposer"` and `model_id` reflecting the override; e2e test `test_propose_domains_e2e_model_override` asserts the round-trip into both trace records and `metadata.model`. Per-call cost records are written by the pool; cross-call aggregation into `metadata.total_cost_usd` defaults to 0.0 in v1.8 (Plan 02 SUMMARY documents the deferral to v1.9 — a trace-file aggregator is the missing piece, not a schema change). |

## ROADMAP Success Criteria

> Phase 48 ROADMAP success criteria (from .planning/ROADMAP.md):

| # | Criterion | Verdict |
|---|-----------|---------|
| 1 | `graph propose-domains` is registered as a Typer subcommand under `graph_app` | ✓ Visible in `--help` |
| 2 | `domains.proposed.yaml` is written with `proposed_domains:` top-level key + metadata block | ✓ E2E test `test_propose_domains_e2e_stubbed_llm` |
| 3 | PROPOSE-05 isolation acceptance test passes against real `cg update` | ✓ 3 D-18 cases all green |
| 4 | `--model` flag round-trips through to trace records | ✓ `test_propose_domains_e2e_model_override` |
| 5 | Partial-success semantics: one cluster failure does not abort the run | ✓ `test_propose_domains_e2e_partial_failure` |

## Plan Coverage

| Plan | SUMMARY exists | Tests added | Notes |
|------|----------------|-------------|-------|
| 48-01 | ✓ | 1 unit (test_domain_proposer_role) | model-adapter; added `model_override` param (Rule 1 fix vs. RESEARCH's claim) |
| 48-02 | ✓ | 13 unit | propose_domains module; RED + GREEN TDD; v1.8 leaves context-loader no-op + total_cost_usd=0.0 (Rule 2 deferrals documented) |
| 48-03 | ✓ | 8 integration (4 e2e + 4 isolation) | Registration + PROPOSE-05 acceptance; fixed Plan-02 path-resolution bug (Rule 1) |

## Regression Check

| Package | Test count | Status |
|---------|------------|--------|
| `model-adapter` | 25 | ✓ all pass |
| `graph-io` | 380 (+1 skipped, +1 xfailed) | ✓ all pass |
| `wiki-io` | 343 (+2 skipped, +1 xfailed) | ✓ all pass |
| `graph-wiki-agent` | 349 (+11 skipped — gated real-Bedrock) | ✓ all pass |

**No regressions from Phase 48.**

## Observed v1.8 → v1.9 Follow-ups (non-blocking)

These are explicitly noted in Plan 02 SUMMARY's Deviations section (all Rule 2 claude-discretion):

1. **Per-package context loader is a no-op.** The LLM currently sees only package names + cross-cutting hub annotation. Adding summary + file_map context would improve proposal quality. Path: wire `wiki_io.scan_monorepo.build_file_map` and the entity-writer summary accessor into the `context_loader` callable inside `propose_domains_cmd`. ~30 LOC; no API change.
2. **`metadata.total_cost_usd` is 0.0.** Per-call cost records are correctly written to `.graph-wiki/traces/*.jsonl` by `SubagentPool.run_all`. Adding an aggregator across the JSONL trace gives a real `total_cost_usd`. ~20 LOC in `propose_domains_cmd`; no schema change.
3. **No command-level `graph_propose_domains_complete` trace event.** Plan 48-02 deferred this to Plan 48-03; Plan 03 did not pick it up because the unit-test contract did not require it. A command-level event for exit-code + duration + summary stats is a useful future addition. ~10 LOC; no schema change.

None of these gaps invalidate any PROPOSE-XX requirement. They are quality-of-life improvements for v1.9.

## Human Verification Items

None — Phase 48 is fully covered by automated tests. The artifact `domains.proposed.yaml` is itself a human-review surface; verifying its quality requires running against a real codebase with a real Bedrock model, which is a separate eval-harness activity (v1.9 sweep on the `domain-proposer` role).

## Self-Check

- All 3 plan SUMMARY.md files present and frontmatter requirements-completed populated.
- 67 D-XX references in `propose_domains.py` (>= 8 required).
- Subcommand registered: `grep -c "graph_app.command(name=[\"']propose-domains'" graph.py` returns 1.
- Phase 48 net new tests: 21 (13 unit + 4 e2e + 4 isolation).
- Net new files: 4 (propose_domains.py, test_propose_domains.py, test_propose_domains_e2e.py, test_propose_domains_isolation.py).
- Net modified files: 5 (graph.py, models.toml ×2, loader.py, test_loader.py).
- Phase commits (`git log --oneline --grep="48-0[123]"`): 10 commits (3 plan summaries + 7 implementation/test commits).
