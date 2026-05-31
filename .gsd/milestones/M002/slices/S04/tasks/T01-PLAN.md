---
estimated_steps: 6
estimated_files: 6
skills_used: []
---

# T01: Rewire Bedrock plugin shims to gw and lock argv mapping

Expected executor skills: `tdd`, `python-testing-patterns`, `uv-package-manager`.

Why: R005 depends on runtime-facing plugin workflows invoking the current CLI name and command shape. Two shims require semantic mapping rather than a simple executable rename: vault initialization must call `gw bootstrap`, and source ingest must call `gw ingest source`.

Do: Update the Bedrock branch in the five plugin shim scripts so `scan_monorepo.py` calls `gw scan`, `init_vault.py` calls `gw bootstrap`, `ingest_source.py` calls `gw ingest source`, `lint_wiki.py` calls `gw lint`, and `wiki_search.py` calls `gw query`. Keep the backend selector and Claude-hosted branches unchanged. Add `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py` that runs each shim as `__main__` with a fake `_config.backend_for` returning `bedrock`, monkeypatches `subprocess.run`, sets representative `sys.argv`, and asserts the exact argv passed to subprocess plus propagated `SystemExit(0)`. The test must not require Bedrock or execute `gw`.

Failure Modes (Q5): dependency on `subprocess.run` is isolated in tests; if the target executable is unavailable in a real run, the shim should surface the normal subprocess/OS failure rather than silently falling back to `graph-wiki-agent`. Malformed CLI args are delegated unchanged to `gw` so Typer remains the single argument validator.

Negative Tests (Q7): the parametrized shim test must include the two non-trivial command translations (`init_vault.py` to `bootstrap`, `ingest_source.py` to `ingest source`) so regressions to stale `init` or bare `ingest` fail.

Done when: all five shims contain no runtime-facing `graph-wiki-agent` subprocess invocation and the new shim test passes package-locally.

## Inputs

- `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`

## Expected Output

- `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`
- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`

## Verification

uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py

## Observability Impact

Adds executable regression coverage for the runtime subprocess argv contract, making stale executable or wrong command-shape failures localizable to one package-local test.
