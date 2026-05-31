---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T02: Record requirement coverage and run validation-closeout checks

Why: M002 validation was blocked because R009 had `Validation: unmapped` and R013 had only `n/a` proof; after T01, the requirement records need explicit deferral/non-regression evidence and a fresh closeout command set. Expected executor skills: uv-package-manager, python-testing-patterns, verify-before-complete.

Do: Use `gsd_requirement_update` rather than direct file edits to update R009, R012, and R013. Keep R009 `status=deferred`, with validation/proof text explaining that public PyPI metadata polish is intentionally deferred because `packages/graph-wiki-core/pyproject.toml`, `packages/graph-wiki-cli/pyproject.toml`, and `packages/graph-wiki-mcp/pyproject.toml` remain minimal by design until a public release is planned. Keep R012 `status=out-of-scope`, with validation/proof citing the T01 bootstrap test and D004: manifest plugin identity remains `graph-wiki-agent` even though the Python distribution/import namespace changed. Keep R013 `status=out-of-scope`, with validation/proof citing focused CLI shim/runtime-doc/boundary tests, brand guard, and the T01 remediation as evidence that package rename changes did not redesign unrelated graph-wiki product workflows. Run focused validation checks and capture the final evidence ID in task completion/summary.

Done when: `.gsd/REQUIREMENTS.md` no longer shows R009 as `unmapped`, R012/R013 no longer rely on bare `n/a` proof, and the focused validation suite passes with evidence suitable for milestone validation.

Requirement impact (Q4): Owns R009 closeout, supports R012 and R013 non-regression closeout, and re-verifies R001/R003/R006/R007 boundaries through tests. Decisions revisited: D003 and D004 are reaffirmed.

Failure modes (Q5): If a requirement update tool rejects a field name, inspect the current requirement shape through the tool contract and update only supported fields such as validation/notes/status/owner/supporting slices. If live Bedrock integration is unavailable, do not collect secrets or force live cost-gated tests; document it as environment/cost gated like S05.

Negative tests (Q7): Boundary and brand checks must continue to reject old executable/import shims while allowing classified plugin identity/provenance strings. CLI tests must continue to prove `gw` is the user-facing command and Bedrock shims preserve arguments while mapping to `gw`.

## Inputs

- `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py`
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
- `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
- `tests/test_package_split_workspace.py`
- `tests/test_integration_gate.py`
- `scripts/check-brand.sh`
- `.brand-grep-allow`
- `packages/graph-wiki-core/pyproject.toml`
- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-mcp/pyproject.toml`
- `.gsd/REQUIREMENTS.md`

## Expected Output

- `.gsd/REQUIREMENTS.md`

## Verification

uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -q && uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py packages/graph-wiki-cli/tests/unit/test_runtime_docs.py packages/graph-wiki-cli/tests/unit/test_cli_boundary.py -q && uv run python -m pytest tests/test_package_split_workspace.py tests/test_integration_gate.py -q && bash scripts/check-brand.sh

## Observability Impact

Adds durable requirement validation/proof text so future agents can diagnose milestone validation state from the rendered requirements and GSD DB instead of reconstructing S06 research.
