# S04: Runtime docs and graph-wiki workflow rewiring

**Goal:** Rewire runtime-facing graph-wiki Bedrock workflows and current user-facing docs from the removed graph-wiki-agent executable to the new gw CLI, with regression tests proving the plugin shim argv mapping and docs-facing command guidance.
**Demo:** Plugin Bedrock shims and current user-facing docs invoke `gw`; runtime-facing help and bootstrap messages no longer point users at `graph-wiki-agent`.

## Must-Haves

- The five plugin Bedrock shim scripts dispatch to `gw` using current CLI command shapes: `scan`, `bootstrap`, `ingest source`, `lint`, and `query`.
- Package-local tests under `packages/graph-wiki-cli/tests` prove shim argv mapping without requiring AWS Bedrock.
- Current user-facing/runtime docs (`README.md`, `plugins/graph-wiki/README.md`, `plugins/graph-wiki/CLAUDE.md`, and `plugins/graph-wiki/.claude-plugin/plugin.json`) describe the v1.12 package layout and `gw` usage, while preserving allowed plugin identity strings per D004.
- Focused help checks for `gw bootstrap` and `gw ingest source` pass through the real graph-wiki-cli package entrypoint.
- Remaining `graph-wiki-agent` references in the planned verification scope are either negative boundary assertions, plugin identity, historical artifacts, or S05-owned obsolete workspace cleanup, not runtime-facing executable guidance.

## Proof Level

- This slice proves: Integration proof. This slice does not require live AWS Bedrock because the runtime boundary under change is the local plugin shim subprocess contract; tests must exercise the Python shim `main()` paths with a fake Bedrock backend and fake `subprocess.run`. Real runtime required: no. Human/UAT required: no.

## Integration Closure

Upstream surfaces consumed: S02's `gw` console script from `graph-wiki-cli`, current Typer command names in `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`, and D003/D004 compatibility boundaries. New wiring introduced: plugin Bedrock shims now invoke the current CLI executable and command shapes. Remaining milestone work: S05 still owns package-only workspace cleanup, removal of obsolete `agents/`, broad stale-reference cleanup, root sync, and full integration verification.

## Verification

- No new runtime telemetry is added. Failure visibility improves because missing or stale Bedrock workflow execution will now fail as a missing/current `gw` command or command-shape error, and package-local regression tests make the subprocess argv contract inspectable by future agents.

## Tasks

- [x] **T01: Rewire Bedrock plugin shims to gw and lock argv mapping** `est:1h`
  Expected executor skills: `tdd`, `python-testing-patterns`, `uv-package-manager`.
  - Files: `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`, `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py`, `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`, `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`, `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`, `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
  - Verify: uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py

- [x] **T02: Update current docs and add docs-facing stale executable guard** `est:1h`
  Expected executor skills: `write-docs`, `uv-package-manager`.
  - Files: `README.md`, `plugins/graph-wiki/README.md`, `plugins/graph-wiki/CLAUDE.md`, `plugins/graph-wiki/.claude-plugin/plugin.json`, `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`
  - Verify: uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_runtime_docs.py

- [x] **T03: Verify S04 integration contract and classify remaining references** `est:30m`
  Expected executor skills: `verify-before-complete`, `uv-package-manager`.
  - Verify: uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests

## Files Likely Touched

- plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py
- plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py
- plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py
- plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py
- plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py
- packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py
- README.md
- plugins/graph-wiki/README.md
- plugins/graph-wiki/CLAUDE.md
- plugins/graph-wiki/.claude-plugin/plugin.json
- packages/graph-wiki-cli/tests/unit/test_runtime_docs.py
