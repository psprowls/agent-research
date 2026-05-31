# S06: Requirement coverage remediation — UAT

**Milestone:** M002
**Written:** 2026-05-31T18:18:22.486Z

## UAT Type

Contract and regression UAT for package-split closeout.

## Preconditions

- Repository is the M002 package-only workspace after S05.
- `uv` dependencies are synced or syncable from the workspace lockfile.
- No live Bedrock credentials or live integration opt-in are required for this UAT.

## Steps

1. Run the focused core regression suite:
   `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -q`.
2. Confirm the bootstrap/init regression covers a generated manifest whose plugin identity is `graph-wiki-agent` while version metadata is sourced from the `graph-wiki-core` distribution.
3. Confirm the ingest NOT_INITIALIZED regression instructs users to run `gw graph build` and does not endorse `graph-wiki-core graph build`.
4. Run the focused CLI/runtime boundary suite:
   `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py packages/graph-wiki-cli/tests/unit/test_runtime_docs.py packages/graph-wiki-cli/tests/unit/test_cli_boundary.py -q`.
5. Run the root package split and integration-gate checks:
   `uv run python -m pytest tests/test_package_split_workspace.py tests/test_integration_gate.py -q`.
6. Run the brand guard:
   `bash scripts/check-brand.sh`.
7. Inspect requirement traceability for R009, R012, and R013.

## Expected Outcomes

- Core regression tests pass and prove the stable manifest plugin identity remains `graph-wiki-agent`.
- Ingest initialization guidance points to `gw graph build`.
- CLI shim/runtime-doc/boundary tests pass, preserving current `gw` runtime guidance.
- Root package split and integration gate tests pass.
- Brand guard reports zero unallowlisted hits; any remaining `graph-wiki-agent` strings are classified as intentional plugin identity/provenance or historical fixture text.
- R009 is explicitly deferred with rationale that PyPI metadata polish is outside M002.
- R012 and R013 have explicit non-regression proof instead of `n/a` or `unmapped` coverage.

## Edge Cases

- If a generated manifest registers `graph-wiki-core` as a plugin identity, UAT fails because it violates D004/R012.
- If user-facing guidance names `graph-wiki-core graph build`, UAT fails because that command is library-only and not the current CLI.
- If brand guard finds unclassified `graph-wiki-agent` usage, classify whether it is an allowed plugin identity/provenance fixture or a stale executable/import reference before proceeding.
- If requirement traceability reverts to `unmapped` or bare `n/a` for R009/R012/R013, milestone validation is still blocked.
