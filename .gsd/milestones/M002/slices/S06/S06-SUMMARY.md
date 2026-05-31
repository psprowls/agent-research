---
id: S06
parent: M002
milestone: M002
provides:
  - Complete M002 validation coverage for R009, R012, and R013.
  - Regression-tested manifest identity and active CLI guidance for package-split closeout.
  - A clean path to rerun milestone validation without missing or partial requirement rows.
requires:
  - slice: S05
    provides: Package-only workspace, final package boundaries, integration gates, and brand guard baseline.
affects:
  - M002 milestone validation
key_files:
  - packages/graph-wiki-core/src/graph_wiki_core/commands/init.py
  - packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py
  - packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py
  - packages/graph-wiki-core/tests/unit/test_commands_ingest.py
  - .gsd/REQUIREMENTS.md
  - .gsd/gsd.db
  - .brand-grep-allow
key_decisions:
  - Reaffirmed D003: do not introduce backward-compatible `graph_wiki_agent` imports or `graph-wiki-agent` executable aliases.
  - Reaffirmed D004/R012: vault/workspace manifests keep plugin identity `graph-wiki-agent` during this milestone even though package/distribution/import names changed.
patterns_established:
  - Package-split brand checks should distinguish stale executable/import guidance from intentional plugin identity/provenance strings.
  - Requirement closeout for deferred/out-of-scope rows should include explicit validation/proof text rather than `unmapped` or bare `n/a`.
observability_surfaces:
  - Focused pytest regressions for manifest identity and ingest guidance.
  - Brand guard classification for allowed plugin identity/provenance strings.
  - Requirement traceability proof extraction for R009/R012/R013.
drill_down_paths:
  - .gsd/milestones/M002/slices/S06/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S06/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-31T18:18:22.486Z
blocker_discovered: false
---

# S06: Requirement coverage remediation

**Closed M002 validation coverage gaps by repairing manifest identity and ingest guidance regressions, then recording explicit R009/R012/R013 proof.**

## What Happened

S06 consumed the completed package-only workspace baseline from S05 and focused on validation closeout rather than introducing new runtime wiring. T01 repaired two package-split regressions: `run_init()` now writes the stable vault/workspace manifest plugin identity `graph-wiki-agent` while still reading installed version metadata from the current `graph-wiki-core` distribution, and ingest NOT_INITIALIZED guidance now directs users to the real current command `gw graph build` instead of a library-only `graph-wiki-core graph build` invocation. Regression coverage was added around generated manifests and initialization guidance. T02 updated the requirement coverage records so R009 is explicitly deferred, R012 has concrete non-regression proof for stable plugin identity, and R013 has explicit proof that package-boundary remediation did not redesign unrelated graph-wiki workflows. The brand guard initially required classification for the intentional `graph-wiki-agent` fixture in the bootstrap regression test; a narrow `.brand-grep-allow` entry now documents that this occurrence is allowed plugin identity/provenance text, not stale CLI/import guidance. Closeout verification re-ran the slice command set and a current requirement-proof extraction successfully.

## Verification

Fresh closeout verification passed via gsd_exec 62b86848-01df-48ad-a9f4-dc31971bc01d: `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -q` passed with 27 tests; `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py packages/graph-wiki-cli/tests/unit/test_runtime_docs.py packages/graph-wiki-cli/tests/unit/test_cli_boundary.py -q` passed with 11 tests; `uv run python -m pytest tests/test_package_split_workspace.py tests/test_integration_gate.py -q` passed with 6 tests; and `bash scripts/check-brand.sh` reported zero unallowlisted hits. Additional requirement traceability verification passed via gsd_exec 2ea73dc9-ebb7-4dc1-b1eb-cb22d6f30be0, proving R009/R012/R013 traceability rows no longer contain unmapped or bare n/a proof. Operational readiness: the slice adds no telemetry surface, but health/failure signals are the focused pytest suites, package-boundary/integration gates, brand guard, and requirement proof extraction; recovery for regressions is to inspect those failing gates and the generated manifest/guidance tests.

## Requirements Advanced

- R009 — Explicitly deferred with validation explaining PyPI metadata polish is outside M002.
- R012 — Out-of-scope constraint now has executable non-regression proof via bootstrap manifest identity tests.
- R013 — Out-of-scope anti-feature now has explicit proof that remediation stayed within package-split boundaries.

## Requirements Validated

- R012 — M002/S06 T01 and closeout verification prove generated manifests keep `graph-wiki-agent` plugin identity while reading version metadata from `graph-wiki-core`.
- R013 — M002/S06 closeout verification passed CLI shim/runtime-doc/boundary tests, integration gates, and brand guard without redesigning unrelated graph-wiki workflows.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

- R009 — Not invalidated; explicitly deferred from M002 because public PyPI metadata polish is outside this milestone.

## Operational Readiness

None.

## Deviations

The task executor noted that its harness lacked the `gsd_requirement_update` wrapper and used GSD's installed DB writer path to keep `.gsd/gsd.db` and `.gsd/REQUIREMENTS.md` synchronized. A narrow `.brand-grep-allow` entry was added for the intentional D004/R012 bootstrap fixture.

## Known Limitations

Public PyPI metadata polish remains intentionally deferred under R009. Live Bedrock runtime integration remains environment/cost gated and was not required for this validation-closeout slice.

## Follow-ups

Rerun M002 milestone validation now that R009/R012/R013 coverage rows are complete.

## Files Created/Modified

- `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py` — Preserves stable `graph-wiki-agent` manifest plugin identity while sourcing version metadata from `graph-wiki-core`.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` — Updates NOT_INITIALIZED guidance to `gw graph build`.
- `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py` — Adds regression coverage for generated manifest plugin identity and version metadata.
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` — Adds/updates regression coverage for active ingest initialization guidance.
- `.gsd/REQUIREMENTS.md` — Rendered requirement records with explicit R009/R012/R013 validation/proof.
- `.gsd/gsd.db` — Canonical GSD requirement state updated for R009/R012/R013.
- `.brand-grep-allow` — Allows the intentional bootstrap plugin-identity fixture while preserving stale-reference guard behavior.
