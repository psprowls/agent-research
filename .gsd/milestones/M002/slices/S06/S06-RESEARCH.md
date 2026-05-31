# S06 Research: Requirement coverage remediation

## Summary

S06 is not a feature slice; it is a validation-closeout remediation slice. The immediate blocker is `S05-ASSESSMENT.md`: round-0 milestone validation found package-split implementation acceptable, but requirement coverage was not closable because R009 was missing and R013 was only partially evidenced.

Current `.gsd/REQUIREMENTS.md` has no Active requirements. R001-R008 are validated. R009 is Deferred with `Validation: unmapped`; R010-R013 are Out of Scope, but R013 still has only `Validation: n/a` and traceability proof `n/a`. S06 should make deferred/out-of-scope requirements explicitly covered in the requirement record and milestone validation evidence, not implement unrelated product behavior.

Key surprise: while researching R013 non-regression evidence, I found two active package-split artifacts that may conflict with existing milestone constraints:

- `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py` now registers `plugin="graph-wiki-core"` in `.graph-wiki.yaml`. That appears to contradict D004/R012, which say the vault/workspace manifest plugin identity remains `graph-wiki-agent` during M002.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` tells users to run `graph-wiki-core graph build`, but `graph-wiki-core` is library-only and has no console script. The current CLI command should be `gw graph build`.

Those are package-split correctness issues, not workflow redesigns. They are natural S06 remediation candidates because they keep the requirement/exclusion story honest before final validation reruns.

## Requirement Coverage Findings

### R009 — Public PyPI metadata polish for the split packages

Current state:

- Status: `deferred`
- Primary owner/supporting slices: none
- Validation: `unmapped`
- Notes already say metadata can remain minimal because the user is not planning a public release soon.

Package metadata is indeed minimal:

- `packages/graph-wiki-core/pyproject.toml`: name/version/description/requires-python/dependencies only; no authors/license/readme/classifiers/URLs.
- `packages/graph-wiki-cli/pyproject.toml`: same minimal metadata plus only `gw` console script.
- `packages/graph-wiki-mcp/pyproject.toml`: same minimal metadata plus only `graph-wiki-mcp` console script.

Recommendation: do not polish PyPI metadata in S06 unless the user changes scope. Instead, update R009 with explicit deferral validation, and cite the package pyproject files as evidence that metadata remains minimal by design. This should turn the traceability proof from `unmapped` into a conscious deferral row.

### R013 — Do not redesign graph-wiki product workflows unrelated to the package split

Current state:

- Status: `out-of-scope`
- Validation: `n/a`
- Traceability proof: `n/a`

Existing evidence already supports most of R013:

- S04 package-local tests verify Bedrock plugin shims preserve command args while only mapping from plugin script calls to `gw`:
  - `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
- Runtime docs tests verify current user-facing docs do not advertise stale `graph-wiki-agent` executable guidance:
  - `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`
- CLI boundary tests verify `graph-wiki-cli` exposes `gw` and imports `graph_wiki_core`, not an old shim:
  - `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
- S05 full verification passed package-local core/CLI/MCP suites and full default-safe pytest.

Additional research comparison against `HEAD` showed the moved workflow code is almost identical after expected namespace/entrypoint normalization:

- `commands/scan.py`: similarity 1.000, changed lines 0
- `commands/query.py`: similarity 0.999, changed lines 2
- `commands/ingest.py`: similarity 0.999, changed lines 2
- `commands/graph.py`: similarity 0.998, changed lines 2
- `commands/init.py`: similarity 0.972, changed lines 6
- `cli.py`: similarity 0.997, changed lines 4
- `mcp/server.py`: similarity 1.000, changed lines 0

The few changed lines are naming/version/help text, not product workflow logic. However, two of them are likely incorrect current guidance/identity changes (see surprise above), so fix those before using this as final R013 non-regression evidence.

## Implementation Landscape

### Files to change or verify

- `.gsd/REQUIREMENTS.md` / GSD DB records for R009 and R013
  - Prefer `gsd_requirement_update`, not direct edits, so DB and rendered requirements stay consistent.
  - R009 should retain `status=deferred` but gain explicit validation/proof text.
  - R013 should retain `status=out-of-scope` but gain explicit non-regression validation/proof text.

- `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py`
  - Potentially change workspace manifest registration from `plugin="graph-wiki-core"` back to `plugin="graph-wiki-agent"` while keeping version sourced from the available package metadata (`graph-wiki-core` is acceptable if the manifest identity remains stable).
  - Add/update a test proving `run_init()` writes `.graph-wiki.yaml` with plugin `name: graph-wiki-agent` if D004/R012 still stands.

- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
  - Change active error guidance from `graph-wiki-core graph build` to `gw graph build` because core is library-only and does not expose a console script.
  - Update `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` expectation currently asserting `graph-wiki-core graph build`.

- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
  - Existing R013 evidence: Bedrock shim mapping to `gw` preserves argv. Re-run after any remediation.

- `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`
  - Existing user-facing stale guidance evidence. Re-run after any remediation.

- `tests/test_package_split_workspace.py`
  - Existing package boundary evidence. Re-run for no old import/script alias regressions.

- `scripts/check-brand.sh` and `.brand-grep-allow`
  - Existing stale/brand guard. Re-run; likely no edits needed unless changing allowlist scope.

### Natural seams for planner

1. **Requirement-record remediation**
   - Use `gsd_requirement_update` to add explicit validation text for R009 and R013.
   - No product code required if planner decides the two surprise findings are outside S06; but validation will be stronger if they are fixed first.

2. **Current guidance / plugin identity remediation**
   - Fix `run_init()` manifest plugin identity if D004/R012 still applies.
   - Fix `ingest.py` active CLI guidance to `gw graph build`.
   - Update focused tests.

3. **Non-regression evidence pass**
   - Re-run focused tests and a small static comparison/scan that demonstrates no unrelated workflow redesign occurred.
   - Capture gsd_exec evidence ID for S06 summary and milestone validation.

4. **Milestone validation rerun inputs**
   - Ensure final milestone validation requirement coverage includes explicit rows for R009 and R013, not `unmapped`/`n/a`.

## First Proof

Highest-risk first proof is the D004/R012 identity check, because a final validation pass could discover it even though S05 assessment only named R009/R013.

Suggested first proof after implementation:

```bash
uv run --package graph-wiki-core python -m pytest \
  packages/graph-wiki-core/tests/unit/test_commands_ingest.py \
  packages/graph-wiki-core/tests/unit/test_cli_bootstrap.py \
  -q
```

If no bootstrap test currently checks manifest plugin identity, add or extend one around `run_init()` before running it. The assertion should distinguish package distribution name from manifest plugin identity.

## Verification Plan

Focused verification for S06:

```bash
uv run --package graph-wiki-core python -m pytest \
  packages/graph-wiki-core/tests/unit/test_commands_ingest.py \
  -q

uv run --package graph-wiki-cli python -m pytest \
  packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py \
  packages/graph-wiki-cli/tests/unit/test_runtime_docs.py \
  packages/graph-wiki-cli/tests/unit/test_cli_boundary.py \
  -q

uv run python -m pytest \
  tests/test_package_split_workspace.py \
  tests/test_integration_gate.py \
  -q

bash scripts/check-brand.sh
```

Closeout/default-safe verification should reuse the S05 pattern if time permits:

```bash
uv sync
uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests -q
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests -q
uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests -q
uv run --package graph-wiki-cli gw --help
uv run --package graph-wiki-cli gw query --help
uv run --package graph-wiki-cli gw graph --help
uv run --package graph-wiki-mcp graph-wiki-mcp --help
uv run python -m pytest -q
```

Live Bedrock integration remains environment/cost gated unless `GRAPH_WIKI_RUN_INTEGRATION=1` and credentials are available.

## Skill Discovery

Relevant technologies are local project/GSD requirement management, uv workspaces, pytest, Typer CLI, and package metadata. Installed skills already cover the useful execution mechanics:

- `uv-package-manager` for uv workspace command/package semantics.
- `python-testing-patterns` for focused pytest updates and regression evidence.
- `write-docs` only if executor needs to revise validation prose manually, but prefer GSD requirement tools for `REQUIREMENTS.md`.

No external skill search is needed for PyPI metadata because R009 is explicitly deferred, not being implemented.

## Open Questions / Planner Decisions

- Should S06 expand from R009/R013 to also fix the observed D004/R012 manifest identity regression? I recommend yes, because it is a requirement coverage remediation slice and the change is small.
- If manifest plugin identity remains `graph-wiki-agent`, which package version should populate `installed_version`? The least-coupled option from core is `importlib.metadata.version("graph-wiki-core")` while keeping `name: graph-wiki-agent`.
- Should final R013 evidence live only in S06 summary/validation, or should a reusable verifier script be added? I recommend summary + fresh `gsd_exec` evidence unless validation tooling requires a durable script; existing tests already cover runtime non-regression.