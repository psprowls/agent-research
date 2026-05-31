---
estimated_steps: 6
estimated_files: 4
skills_used: []
---

# T01: Repair manifest identity and active CLI guidance

Why: S06 research found two small package-split regressions that undermine requirement closeout: `run_init()` currently registers `graph-wiki-core` as the manifest plugin identity despite D004/R012, and ingest NOT_INITIALIZED guidance points at the library-only `graph-wiki-core graph build` command instead of the real `gw graph build` entrypoint. Expected executor skills: tdd, python-testing-patterns, uv-package-manager, verify-before-complete.

Do: Update `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py` so `_ws_init()` is called with `plugin="graph-wiki-agent"` while keeping `version=importlib.metadata.version("graph-wiki-core")`. Update nearby comments to distinguish stable manifest plugin identity from current Python distribution name. Add or extend a core unit test in `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py` that executes `run_init()` with a temporary workspace/repo and asserts `.graph-wiki.yaml` contains a plugin entry named `graph-wiki-agent` with version fields populated from the mocked/current core distribution, not `graph-wiki-core`. Update `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` so `IngestorGraphNotInitializedError` recommends `gw graph build`, and update `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` to assert the new guidance.

Done when: The focused core tests fail on the old `graph-wiki-core` identity/guidance and pass with the corrected `graph-wiki-agent` manifest identity plus `gw graph build` CLI guidance.

Requirement impact (Q4): Touches R003, R012, and R013. Re-verify core command tests plus CLI/boundary checks in T02. Decision revisited: D004 is reaffirmed, not changed.

Failure modes (Q5): If importlib metadata is unavailable in an editable uv test environment, mock or patch only the version lookup in the new test; do not hardcode a stale package version. If manifest YAML shape changes, assert through the existing workspace manifest reader rather than brittle text matching.

Negative tests (Q7): The bootstrap test should prove `graph-wiki-core` is not registered as the plugin name. The ingest test should prove stale executable guidance is gone by asserting the replacement guidance string.

## Inputs

- `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py`
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
- `packages/workspace-io/tests/test_manifest.py`
- `packages/workspace-io/tests/test_init.py`
- `.gsd/DECISIONS.md`
- `.gsd/REQUIREMENTS.md`

## Expected Output

- `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py`
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

## Verification

uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -q

## Observability Impact

Improves failure diagnostics by making active error guidance executable (`gw graph build`) and by adding a regression test for manifest identity drift.
