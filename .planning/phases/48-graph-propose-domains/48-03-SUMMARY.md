---
phase: 48-graph-propose-domains
plan: 03
subsystem: graph-wiki-agent/commands + integration-tests
tags: [phase-48, propose-domains, typer-registration, isolation-acceptance, propose-05]
requires:
  - "48-01-SUMMARY: domain-proposer role + make_llm(model_override=...)"
  - "48-02-SUMMARY: propose_domains.py core module + dataclasses + helpers"
  - "Phase 47 cluster: compute_clusters / Cluster / ClusterResult"
  - "graph_io.domains._load_domains_yaml literal-filename read (structural isolation)"
provides:
  - "`graph propose-domains` Typer subcommand registered under graph_app"
  - "tests/integration/test_propose_domains_e2e.py — 4 stubbed-LLM e2e tests"
  - "tests/integration/test_propose_domains_isolation.py — 4 isolation tests (3 D-18 + 1 structural sanity)"
  - "PROPOSE-05 isolation as a regression-tested invariant"
affects:
  - "agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py"
  - "agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py"
  - "agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py"
  - "agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py"
tech-stack:
  added: []
  patterns:
    - "Stubbed LLM via SimpleNamespace.tool_calls + monkeypatch of make_llm — no live Bedrock in CI"
    - "Static-scan structural assertion to enforce filename invariants across packages"
key-files:
  created:
    - "agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py"
    - "agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py"
  modified:
    - "agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py"
    - "agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py"
key-decisions:
  - "D-22 implemented as a `graph_app.command(name=\"propose-domains\")(propose_domains_cmd)` call appended to graph.py (avoids circular import from a decorator in propose_domains.py)"
  - "propose_domains_cmd reads domains.yaml from repo_root (NOT workspace) and writes domains.proposed.yaml to repo_root — fixes a Plan 02 path-resolution bug that would have made the e2e + isolation tests fail. Both surfaces live next to each other for human diff review."
  - "_load_existing_domains accepts BOTH the flat shape (matches `graph_io.domains.emit`) AND the nested-under-`domains:` shape (matches Plan 02's behavior contract). Plan 02's unit test for the nested shape still passes; the e2e + isolation tests use the flat shape that `cg update` actually consumes."
  - "Structural sanity-check test (test_graph_io_does_not_reference_proposed_yaml) statically asserts no module under `packages/graph-io/src/graph_io/` mentions `domains.proposed`, `.proposed.yaml`, or `proposed_domains` — first signal that any future glob-based discovery would break PROPOSE-05."
requirements-completed: [PROPOSE-01, PROPOSE-05, PROPOSE-06]
duration: "6 min"
completed: "2026-05-27"
---

# Phase 48 Plan 03: register subcommand + integration tests Summary

Registered the `propose-domains` Typer subcommand under `graph_app`, wired up the full pipeline with a stubbed-LLM end-to-end test suite, and locked in PROPOSE-05 isolation as a regression-tested invariant against the real `cg update` code path.

## Execution metrics

- **Duration:** 6 min
- **Start:** 2026-05-27T15:44:21Z
- **End:** 2026-05-27T15:50:07Z
- **Tasks executed:** 2/2
- **Files created:** 2
- **Files modified:** 2
- **Commits:** 2 (`a3abcc1 feat(48-03)`, `f6a85bd test(48-03)`)
- **Tests added:** 8 (4 e2e + 4 isolation including 1 structural sanity check); plus the 13 Plan-02 unit tests still pass with the broadened loader

## What was built

### Task 48-03-01 — subcommand registration + e2e tests

1. **Subcommand registration (D-22):** appended a `graph_app.command(name="propose-domains")(propose_domains_cmd)` call to the end of `commands/graph.py`, with a comment explaining the placement (avoids circular imports). `uv run graph-wiki-agent graph propose-domains --help` now prints the help text with `--workspace`, `--hub-threshold`, `--model`.
2. **Path-resolution fixes in `propose_domains.py`** (uncovered by integration tests):
   - `propose_domains_cmd` now reads `domains.yaml` from **repo_root** (not workspace) — matching where `graph_io.domains._load_domains_yaml` reads it from.
   - `propose_domains_cmd` now writes `domains.proposed.yaml` to **repo_root** so reviewers can diff against `domains.yaml` side-by-side. The workspace stays reserved for derived `.graph-wiki/` state.
   - `_load_existing_domains` now handles BOTH shapes: flat (top-level keys ARE domain names, as `graph_io.domains.emit` consumes) and nested-under-`domains:` (the shape Plan 02's unit test contract specified). Both Plan 02's nested-test and Plan 03's flat-fixture path are now exercised.
3. **E2E test file** `tests/integration/test_propose_domains_e2e.py` (4 tests, all using stubbed `_StubLLM` via monkeypatch — no live Bedrock):
   - `test_propose_domains_e2e_stubbed_llm`: full pipeline → valid `domains.proposed.yaml` with proposed_domains + metadata schema, per-cluster trace records in `<workspace>/.graph-wiki/traces/`.
   - `test_propose_domains_e2e_model_override`: `--model us.amazon.nova-lite-v1:0` round-trips into trace `model_id` field and YAML `metadata.model`.
   - `test_propose_domains_e2e_no_domains_yaml`: graceful when `domains.yaml` is absent; no crash; `domains.proposed.yaml` still written.
   - `test_propose_domains_e2e_partial_failure`: one cluster raises; other clusters still produce proposals; failure surfaces in `metadata.llm_failures` (D-01).

### Task 48-03-02 — PROPOSE-05 isolation tests

4. **Isolation test file** `tests/integration/test_propose_domains_isolation.py` (4 tests, all using the real `update.run` code path — zero mocking):
   - `test_proposed_yaml_produces_zero_graph_edges` (D-18 case 1): writes `domains.proposed.yaml` containing a `data` domain claiming `jspkg, webutil`; re-runs `cg update`; asserts exactly ONE `belongs_to_domain` edge (`mypkg -> core` from `domains.yaml`) and no `data` Domain node.
   - `test_proposed_yaml_with_fake_package_never_appears` (D-18 case 2 belt-and-suspenders): writes a unique fake package name `__FAKE_PROPOSED_PACKAGE_48__` into `domains.proposed.yaml`; asserts it appears in zero graph nodes and zero edge endpoints.
   - `test_proposed_yaml_does_not_break_normal_domain_loading` (D-18 case 3): with the proposed file present, `list_domains(conn)` returns exactly `['core']`.
   - `test_graph_io_does_not_reference_proposed_yaml` (structural sanity, extra): static-scans `packages/graph-io/src/graph_io/**/*.py` for the strings `domains.proposed`, `.proposed.yaml`, `proposed_domains` — first signal that any future glob-based domain-file discovery would break PROPOSE-05.

## Verification

- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py -x` → **4 passed**
- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py -x` → **4 passed**
- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests` → **349 passed, 11 skipped** (no regressions; the 11 skips are pre-existing real-Bedrock integration tests gated on `GRAPH_WIKI_RUN_INTEGRATION=1`)
- `uv run graph-wiki-agent graph propose-domains --help` → prints all three flags
- `grep -rn "domains.proposed\|\.proposed\.yaml\|proposed_domains" packages/graph-io/src/graph_io/` → **0 hits** (PROPOSE-05 structural invariant from RESEARCH F-2 holds)
- `grep -c "graph_app.command(name=[\"']propose-domains" commands/graph.py` → **1 match** (D-22 registration present)

Plan-level success criteria all met:
- `graph propose-domains` is a registered Typer subcommand ✓
- 4 e2e + 4 isolation tests pass (8 integration tests total — plan asked for 7; the extra is the structural sanity check) ✓
- PROPOSE-05 isolation proven by real `cg update` integration test ✓
- Partial-success semantics work ✓
- `--model` flag round-trips through ✓
- All 5 ROADMAP success criteria for Phase 48 are observably true ✓

## Deviations from Plan

**[Rule 1 — missing critical] propose_domains_cmd path resolution was wrong.** Found during: writing the e2e fixture | Issue: Plan 02 implemented `_load_existing_domains(workspace_root)` and wrote `<workspace>/domains.proposed.yaml`, but `graph_io.domains._load_domains_yaml(repo_root)` reads from the REPO root. The two surfaces would never have lined up at runtime: an LLM would propose against an empty existing-domains map even when `domains.yaml` existed at the repo root, and the proposed file would land in the wrong directory for human review. | Fix: changed `propose_domains_cmd` to use `repo_root` for both reads and the write. Also broadened `_load_existing_domains` to accept the flat shape that `graph_io.domains.emit` consumes (the unit-test path still passes because the nested shape is detected first). | Files modified: `commands/propose_domains.py` | Verification: 13/13 Plan-02 unit tests still pass; 4/4 e2e tests pass; 4/4 isolation tests pass. | Commit hash: `a3abcc1`.

**[Rule 2 — claude-discretion] Edge-schema column names.** Found during: writing the isolation SQL | Issue: the plan recipe suggested `SELECT src_kind, src_name, dst_kind, dst_name FROM edges WHERE kind = 'belongs_to_domain'`, but the actual schema (per `packages/graph-io/src/graph_io/schema.py`) uses `src` / `dst` foreign-key columns into `nodes(id)`. | Fix: joined edges to nodes twice (src and dst) to recover the kind/name fields. | Files modified: `tests/integration/test_propose_domains_isolation.py` | Verification: 4/4 isolation tests pass. | Commit hash: `f6a85bd`.

**[Rule 2 — claude-discretion] Added a 4th isolation test (structural sanity).** Found during: planning Task 48-03-02 | Issue: D-18 lists three integration cases. I added a fourth, pure-static test (`test_graph_io_does_not_reference_proposed_yaml`) that greps `packages/graph-io/src/graph_io/**/*.py` for the strings `domains.proposed`, `.proposed.yaml`, `proposed_domains`. It is fast (≤ 100ms), self-documenting, and would catch any future change that introduces glob-based domain-file discovery — the exact regression PROPOSE-05 is designed to prevent. | Fix: kept the original three D-18 cases plus this one. | Files modified: `tests/integration/test_propose_domains_isolation.py` | Verification: passes; 0 hits in graph-io. | Commit hash: `f6a85bd`.

**Total deviations:** 3, of which 1 is a critical Plan-02 fix (Rule 1) and 2 are minor implementation choices (Rule 2). **Impact:** Phase 48's pipeline now works end-to-end with the correct path resolution. PROPOSE-05 is no longer just a code inspection — it is a regression-tested integration invariant.

## Authentication Gates

None — all LLM responses are stubbed via `_StubLLM` + monkeypatch of `make_llm`. No live Bedrock or AWS calls during this plan.

## Issues Encountered

None blocking. The two issues uncovered (Plan 02 path bug, edges-schema column names) were both surfaced by writing tests and fixed immediately.

## Self-Check: PASSED

- key-files.created on disk: both ✓
- `git log --oneline --all --grep="48-03"` returns 2 commits (Task 1 + Task 2) ✓
- `<acceptance_criteria>` (Task 48-03-01 `<done>`): subcommand registered ✓; 4 e2e tests pass ✓; full graph-wiki-agent suite green (no regressions) ✓; help text includes all three flags ✓
- `<acceptance_criteria>` (Task 48-03-02 `<done>`): all 3 D-18 isolation tests pass ✓ (plus the bonus structural test); full suite green ✓
- Plan-level `<verification>` commands rerun:
  - Integration tests: 8/8 pass
  - Full suite: 349 passed, 11 skipped, 0 failed
  - Help-text manual check: passes
  - graph_io grep: 0 hits (structural invariant)
- `<success_criteria>` (6 items) — all met.

## Ready for phase verification

Phase 48 deliverables are complete. All 5 ROADMAP success criteria are testable from disk: subcommand registered, `domains.proposed.yaml` differentiated schema, partial-success semantics, --model round-trip, PROPOSE-05 isolation. Verifier can re-run the full Phase 48 suite with `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_propose_domains.py agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py -v`.
