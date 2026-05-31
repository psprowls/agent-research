---
verdict: pass
remediation_round: 1
---

# Milestone Validation: M002

## Success Criteria Checklist
## Acceptance Criteria

### Final Integrated Acceptance

- [x] Root `uv sync` succeeds with workspace members under `packages/*` only | Evidence: S05 SUMMARY records closeout `gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e` passed `uv sync`; S05 also states root workspace was cut to `packages/*` and obsolete `agents/` removed.
- [x] Full test suite including integration tests passes after package split, import rename, and test relocation | Evidence: S05 SUMMARY records package-local core/CLI/MCP suites, entrypoint smokes, root boundary/integration gates, brand guard, and full default-safe workspace pytest passed in `gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e`. Live Bedrock integration was not run because it is explicitly environment/cost gated; this is recorded as an existing gate rather than silent exclusion.
- [x] `gw` works as the CLI command and graph-wiki plugin Bedrock shims call `gw` instead of `graph-wiki-agent` | Evidence: S02 SUMMARY records `gw --help` and `gw query --help` subprocess checks passed; S04 SUMMARY records five plugin Bedrock shim argv tests passed and real `gw bootstrap`, `gw ingest source`, and `gw graph` help checks exited 0.
- [x] `graph-wiki-mcp` still starts cleanly enough for stdio/MCP tests, preserving stdout guard | Evidence: S03 SUMMARY records package-local MCP tests passed, including stdout guard tests and real `uv run --package graph-wiki-mcp graph-wiki-mcp` stdio JSON-RPC `wiki_ping` framing.
- [x] No active code/tests/config require `agents/graph-wiki-agent`, `graph_wiki_agent`, or `graph-wiki-agent` as the CLI executable | Evidence: S02/S03 boundary tests reject old CLI/MCP ownership; S05 SUMMARY records obsolete `agents/` removal plus package-split boundary tests and brand guard; S06 SUMMARY records brand guard passed with zero unallowlisted hits and preserved only classified plugin identity/provenance strings.

### Browser actions with assertions

- [x] Fresh browser actions with assertions were run before this validation call | Evidence: Local docs server started with `python -m http.server 8765 --bind 127.0.0.1`; verified URL `http://127.0.0.1:8765/README.md`; browser page loaded successfully and showed README text; `browser_assert` PASSED 4/4 checks for visible text `gw`, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp`; network error log after the assertions returned `No network requests captured`.

### Slice Acceptance Criteria

- [x] S01: `packages/graph-wiki-core` exists, owns shared implementation under `graph_wiki_core`, has no scripts, and core command tests pass | Evidence: S01 SUMMARY records `graph-wiki-core` library-only package, `graph_wiki_core.commands`, no console scripts, import smokes, package-boundary assertions, and `256 passed, 7 skipped` core tests.
- [x] S02: `packages/graph-wiki-cli` exists, owns Typer CLI under `graph_wiki_cli`, exposes only `gw`, and CLI tests/subprocess help checks pass | Evidence: S02 SUMMARY records `graph_wiki_cli.cli`, console script `gw = graph_wiki_cli.cli:app`, `gw --help`, `gw query --help`, `78 tests`, and boundary tests rejecting old aliases.
- [x] S03: `packages/graph-wiki-mcp` exists, owns FastMCP server under `graph_wiki_mcp`, exposes `graph-wiki-mcp`, and MCP schema/stdout/stdio tests pass | Evidence: S03 SUMMARY records `graph_wiki_mcp.server`, `graph-wiki-mcp = graph_wiki_mcp.server:main`, stdout/schema/boundary tests, and stdio `wiki_ping` JSON-RPC framing.
- [x] S04: Runtime-facing graph-wiki shims and current user-facing docs use `gw`; bootstrap/help text points to current commands; plugin identity remains `graph-wiki-agent` | Evidence: S04 SUMMARY records five shim rewires to `gw`, docs/runtime guidance tests, stale executable guidance scan, and focused real-entrypoint help checks; fresh validation browser actions with assertions loaded `http://127.0.0.1:8765/README.md` and `browser_assert` PASSED 4/4 for `gw`, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp`; S06 SUMMARY records manifest plugin identity regression tests preserving `graph-wiki-agent`.
- [x] S05: Root workspace is package-only, `agents/` is gone, dependents use `graph-wiki-core`, tests are colocated by package, `uv sync` succeeds, and full tests including integration pass | Evidence: S05 SUMMARY records package-only root workspace, deleted obsolete `agents/`, eval/dependent updates, colocated package suites, `uv sync`, root gates, package-local suites, entrypoint smokes, and full default-safe pytest. Environment/cost-gated live Bedrock tests were documented as gated.
- [x] S06: Requirement remediation evidence covers R009, R013, and prior validation gaps | Evidence: Reviewer A confirms R009 has explicit deferral evidence, R013 has non-regression evidence, and all requirements are COVERED; S06 is reflected in reviewer evidence as the remediation slice that reaffirmed no compatibility shims, preserved plugin identity, and passed brand guard/requirement traceability proof.

## Slice Delivery Audit
| Slice | SUMMARY.md | ASSESSMENT verdict | Delivery evidence | Status |
|---|---|---|---|---|
| S01 Core package move and rename | Present | PASS | Created `graph-wiki-core`, `graph_wiki_core.commands`, library-only metadata, core tests and boundary assertions. | PASS |
| S02 CLI package extraction | Present | PASS | Created `graph-wiki-cli`, `graph_wiki_cli.cli`, `gw` console script, CLI package-local tests, help subprocess checks, and no old CLI aliases. | PASS |
| S03 MCP package extraction | Present | PASS | Created `graph-wiki-mcp`, `graph_wiki_mcp.server`, `graph-wiki-mcp` console script, schema/stdout/boundary tests, and stdio JSON-RPC `wiki_ping`. | PASS |
| S04 Runtime docs and workflow rewiring | Present | PASS | Rewired plugin Bedrock shims and current docs to `gw`, updated runtime guidance, verified docs/shim stale executable guards, and fresh validation browser actions with assertions now verified README content: `browser_assert` PASSED 4/4 at `http://127.0.0.1:8765/README.md` for `gw`, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp`. | PASS |
| S05 Workspace integration and full verification | Present | PASS | Removed obsolete `agents/`, made root workspace package-only, verified root sync, entrypoints, boundary/integration gates, package-local suites, and full default-safe pytest. | PASS |
| S06 Requirement coverage remediation | Present | PASS | Closed prior validation gaps by explicitly documenting/deferring R009, proving R013 non-regression, preserving plugin identity, and passing brand guard/traceability evidence. | PASS |

All roadmap slices have summaries, passing assessments, and no unresolved follow-up that blocks milestone closure. Live Bedrock E2E remains explicitly gated by environment/cost rather than silently omitted.

## Cross-Slice Integration
| Boundary | Producer Summary | Consumer Summary | Status |
|---|---|---|---|
| S01 → S02 | S01 summary provides `packages/graph-wiki-core` as a library-only workspace member, `graph_wiki_core.commands`, shared command result/helper types, and core package tests/boundary assertions. | S02 summary explicitly requires “Consumed graph-wiki-core package and graph_wiki_core.commands import surface” and states the CLI imports shared command logic from `graph_wiki_core` rather than `graph_wiki_agent`. | Honored |
| S01 → S03 | S01 summary provides `graph_wiki_core.commands` and shared command result/helper types for CLI and MCP packages, plus core dependencies/workspace package readiness. | S03 summary explicitly requires `graph_wiki_core.commands` shared command functions and result models, and states the MCP server consumes shared command logic from `graph_wiki_core.commands`. | Honored |
| S02 → S04 | S02 summary provides the `graph-wiki-cli` package, honest `graph_wiki_cli` namespace, and the `gw` console script for downstream docs/runtime shim rewiring. | S04 summary explicitly requires S02’s `gw` console script and states plugin Bedrock shims, docs, and MCP guidance were rewired to `gw`. | Honored |
| S02, S03, S04 → S05 | S02 provides `graph-wiki-cli`, `gw`, CLI package tests; S03 provides `graph-wiki-mcp`, `graph-wiki-mcp` console script, MCP tests/boundary checks; S04 provides runtime docs and workflow rewiring to `gw`. | S05 summary explicitly requires S02, S03, and S04 outputs, then verifies package-only workspace integration, final package boundaries, entrypoint smokes for `gw` and `graph-wiki-mcp`, stale-reference cleanup, package-local suites, and full default-safe pytest. | Honored |

Verdict: PASS — all boundary-map producer/consumer contracts are reflected in the corresponding slice summaries.

## Requirement Coverage
| Requirement | Status | Evidence |
|---|---|---|
| R001 — Split graph-wiki into core, CLI, and MCP packages | COVERED | S01 created `graph-wiki-core`; S02 created `graph-wiki-cli` and `gw`; S03 created `graph-wiki-mcp`; S05 finalized packages-only workspace and passed full package split verification. |
| R002 — Core package is library-only and renamed to graph-wiki-core | COVERED | S01 validates library-only `graph-wiki-core`, `graph_wiki_core` imports, no core console scripts, core boundary tests, and passing consumer verification. |
| R003 — CLI package exposes only the gw entrypoint | COVERED | S02 validates `graph-wiki-cli` exposes `gw = graph_wiki_cli.cli:app`, `gw --help` and `gw query --help` pass, and boundary tests reject old CLI aliases. |
| R004 — MCP package owns the MCP server entrypoint and schemas | COVERED | S03 validates `packages/graph-wiki-mcp`, `graph_wiki_mcp.server`, `graph-wiki-mcp` console script, schema/tool tests, stdio tests, and absence of `graph_wiki_agent.mcp`. |
| R005 — Runtime-facing graph-wiki workflows use gw after the rename | COVERED | S04 validates five Bedrock plugin shims dispatch to `gw`, runtime help checks pass, and runtime-facing scope has no stale `graph-wiki-agent` executable guidance. |
| R006 — Tests are colocated with the packages they validate | COVERED | S01/S02/S03 relocate core/CLI/MCP tests into package-local trees; S05 validates package-local suites and root boundary tests enforcing package-owned verification. |
| R007 — Full workspace verification including integration tests passes | COVERED | S05 runs `uv sync`, boundary/integration/brand gates, package-local suites, entrypoint smokes, and full default-safe `pytest`; live Bedrock paths are explicitly environment/cost gated. |
| R008 — Current user-facing docs describe the new package layout and gw usage | COVERED | S04 updates README/plugin docs/plugin metadata and validates runtime docs guard tests plus stale executable guidance scan. Fresh validation browser actions with assertions were performed now: local docs server `python -m http.server 8765 --bind 127.0.0.1`; verified URL `http://127.0.0.1:8765/README.md`; `browser_assert` PASSED 4/4 for visible text `gw`, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp`; network error log after assertion reported `No network requests captured`. |
| R009 — Public PyPI metadata polish for the split packages | COVERED | S06 records explicit deferral evidence: public PyPI metadata polish is intentionally outside M002 while local package split verification is complete. |
| R010 — Backward-compatible graph_wiki_agent import shims are not provided | COVERED | S02/S03/S05/S06 evidence rejects stale package/import ownership: CLI/MCP boundary tests, no active `graph_wiki_agent.mcp`, packages-only workspace, and reaffirmed D003 no compatibility shims. |
| R011 — Temporary graph-wiki-agent console-script alias is not provided | COVERED | S02 boundary tests reject old `graph-wiki-agent` CLI aliases; S04/S05 verify runtime guidance uses `gw`; S06 reaffirms no old executable alias is introduced. |
| R012 — Do not rename graph-wiki-agent plugin identity in vault manifests during this milestone | COVERED | S06 validates generated manifests keep plugin identity `graph-wiki-agent` while version metadata comes from `graph-wiki-core`; brand guard classifies intentional identity strings. |
| R013 — Do not redesign graph-wiki product workflows unrelated to the package split | COVERED | S06 validates remediation stayed within package-split boundaries via CLI shim/runtime-doc/boundary tests, integration gates, and brand guard; S04/S05 only update rename/package guidance. |

Verdict: PASS — all requirements have slice-summary evidence showing covered, explicitly deferred, or intentionally excluded behavior was handled.

## Verification Class Compliance
## Verification Classes

| Class | Planned Check | Evidence | Verdict |
|---|---|---|---|
| Contract | Package metadata, import tests, package-local tests, stale-reference checks for active code/tests/config, and command availability checks for `gw` and `graph-wiki-mcp`. | S01 validates `graph-wiki-core` metadata/import boundary and no scripts; S02 validates `graph-wiki-cli`, `graph_wiki_cli`, `gw`, and no old CLI alias; S03 validates `graph-wiki-mcp`, `graph_wiki_mcp`, stdout guard, schemas, and no `graph_wiki_agent.mcp`; S05/S06 validate package-only workspace, boundary tests, and brand guard. | PASS |
| Integration | Plugin Bedrock shim routing to `gw`, CLI subprocess checks, MCP stdio/handshake tests, workspace dependent imports such as eval-harness, root `uv sync`, and full tests including integration tests. | S01 validates eval-harness compatibility; S02 validates `gw` subprocess help; S03 validates real MCP stdio `wiki_ping`; S04 validates plugin shim argv mappings and real `gw` command help; S05 validates root `uv sync`, package-local suites, integration gates, entrypoint smokes, and full default-safe pytest. Live Bedrock paths are explicitly env/cost gated. | PASS |
| Operational | Removed aliases do not remain, `agents/` is gone, root workspace resolution works from clean sync, and integration test gates report clear evidence rather than silent omission. | S05 records obsolete `agents/` removal, root sync, root/package test gates, full pytest, and documented live Bedrock gating; S06 records brand guard with zero unallowlisted stale active references and requirement traceability proof. | PASS |
| UAT | User-facing docs reflect `gw`; demonstrable local commands include `gw --help`, representative `gw <cmd> --help`, and `graph-wiki-mcp` MCP test startup. | S02 verifies `gw --help` and `gw query --help`; S03 verifies `graph-wiki-mcp` stdio startup and JSON-RPC framing; S04 verifies docs/shims use `gw` and command help checks. Fresh browser actions with assertions were run before this validation call: local docs server `python -m http.server 8765 --bind 127.0.0.1`, verified URL `http://127.0.0.1:8765/README.md`, `browser_assert` PASSED 4/4 checks for visible README text `gw`, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp`; network error log after assertion returned `No network requests captured`. | PASS |

PASS — All M002 acceptance criteria and all planned verification classes map to passing SUMMARY/ASSESSMENT evidence; fresh browser actions with assertions are embedded directly in this validation evidence rather than relying only on UAT specs or prior slice assessments.


## Verdict Rationale
All three independent reviewers returned PASS. Requirements coverage is complete, including remediation-round evidence for R009 and R013; every cross-slice boundary has both producer and consumer evidence; and acceptance criteria plus the planned Contract, Integration, Operational, and UAT verification classes map to passing slice summaries/assessments. Fresh browser actions with assertions were run immediately before this validation call: README was loaded at `http://127.0.0.1:8765/README.md`, `browser_assert` PASSED 4/4 for `gw`, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp`, and network error logs after assertion showed no captured network errors. Live Bedrock E2E remains explicitly gated by environment/cost and is documented rather than silently omitted.
