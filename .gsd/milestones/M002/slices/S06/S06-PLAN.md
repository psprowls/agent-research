# S06: Requirement coverage remediation

**Goal:** Close M002 validation coverage gaps by fixing package-split identity/guidance regressions, producing explicit R009/R012/R013 evidence, and updating requirement records so milestone validation has no unmapped or partial rows.
**Demo:** After this: validation evidence covers R009 by implementation or explicit requirement deferral, R013 has explicit non-regression evidence, and milestone validation can rerun without missing or partial requirement rows.

## Must-Haves

- `run_init()` writes the stable vault/workspace manifest plugin identity `graph-wiki-agent` while continuing to source the installed version from the current `graph-wiki-core` distribution.
- Ingest NOT_INITIALIZED guidance tells users to run the real current CLI command `gw graph build`, not a library-only `graph-wiki-core` executable.
- Focused core, CLI, root boundary, integration-gate, and brand checks pass after remediation.
- R009 remains explicitly deferred with validation explaining that public PyPI metadata polish is intentionally out of this milestone.
- R012 and R013 remain out of scope/anti-scope constraints but have explicit non-regression validation/proof instead of `n/a` or `unmapped` coverage.

## Proof Level

- This slice proves: Final validation-closeout proof: contract-level package identity/guidance tests plus default-safe integration/brand/boundary checks. No live Bedrock runtime is required; live integration remains environment/cost gated.

## Integration Closure

Consumes S05 package-only workspace and entrypoint baseline. Introduces no new runtime wiring; it only repairs two active package-split regressions and closes requirement traceability records. After this slice, M002 milestone validation should be able to rerun with complete R009/R012/R013 rows.

## Verification

- No runtime telemetry changes. Failure visibility is through executable tests, package boundary checks, brand guard output, and GSD requirement validation/proof fields.

## Tasks

- [x] **T01: Repair manifest identity and active CLI guidance** `est:45m`
  Why: S06 research found two small package-split regressions that undermine requirement closeout: `run_init()` currently registers `graph-wiki-core` as the manifest plugin identity despite D004/R012, and ingest NOT_INITIALIZED guidance points at the library-only `graph-wiki-core graph build` command instead of the real `gw graph build` entrypoint. Expected executor skills: tdd, python-testing-patterns, uv-package-manager, verify-before-complete.
  - Files: `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py`, `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py`, `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
  - Verify: uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -q

- [x] **T02: Record requirement coverage and run validation-closeout checks** `est:45m`
  Why: M002 validation was blocked because R009 had `Validation: unmapped` and R013 had only `n/a` proof; after T01, the requirement records need explicit deferral/non-regression evidence and a fresh closeout command set. Expected executor skills: uv-package-manager, python-testing-patterns, verify-before-complete.
  - Files: `.gsd/REQUIREMENTS.md`
  - Verify: uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -q && uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py packages/graph-wiki-cli/tests/unit/test_runtime_docs.py packages/graph-wiki-cli/tests/unit/test_cli_boundary.py -q && uv run python -m pytest tests/test_package_split_workspace.py tests/test_integration_gate.py -q && bash scripts/check-brand.sh

## Files Likely Touched

- packages/graph-wiki-core/src/graph_wiki_core/commands/init.py
- packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py
- packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py
- packages/graph-wiki-core/tests/unit/test_commands_ingest.py
- .gsd/REQUIREMENTS.md
