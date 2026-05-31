---
estimated_steps: 6
estimated_files: 5
skills_used: []
---

# T02: Update current docs and add docs-facing stale executable guard

Expected executor skills: `write-docs`, `uv-package-manager`.

Why: R008 requires current user-facing docs to explain the v1.12 package split and `gw` usage instead of directing users to the removed `graph-wiki-agent` executable. D004 still protects plugin identity strings, so this is a targeted documentation rewrite rather than a blanket string purge.

Do: Update `README.md` to describe the package-only target layout with `packages/graph-wiki-core`, `packages/graph-wiki-cli`, and `packages/graph-wiki-mcp`, and replace current quickstart/help examples with package-scoped `uv run --package graph-wiki-cli gw --help` style usage. Update `plugins/graph-wiki/README.md` so Bedrock workflow prose says shims route to `gw` / `graph-wiki-cli`, while preserving `.graph-wiki.yaml` plugin identity wording where it names the plugin rather than the executable. Update `plugins/graph-wiki/CLAUDE.md` runtime maintainer guidance to document the exact shim-to-CLI mapping from T01. Update `plugins/graph-wiki/.claude-plugin/plugin.json` description to refer to `gw` / `graph-wiki-cli` as the Bedrock CLI companion while keeping `name` as `graph-wiki`. Add `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py` with focused assertions over these current docs: current help examples mention `gw`, runtime-facing executable guidance does not instruct `graph-wiki-agent`, and plugin identity fields are allowed separately.

Requirement Impact (Q4): touches R008 directly and supports R005 by aligning runtime maintainer docs with actual shims. Re-verify the docs guard and shim tests; no decisions are revisited.

Negative Tests (Q7): the docs test should fail on active prose such as `uv run graph-wiki-agent --help`, `graph-wiki-agent <cmd>`, or plugin descriptions naming `graph-wiki-agent` as the Bedrock CLI companion, while allowing explicit plugin identity examples required by D004.

Done when: current docs no longer advertise the stale executable for runtime use, and the docs guard test passes.

## Inputs

- `README.md`
- `plugins/graph-wiki/README.md`
- `plugins/graph-wiki/CLAUDE.md`
- `plugins/graph-wiki/.claude-plugin/plugin.json`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`

## Expected Output

- `README.md`
- `plugins/graph-wiki/README.md`
- `plugins/graph-wiki/CLAUDE.md`
- `plugins/graph-wiki/.claude-plugin/plugin.json`
- `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`

## Verification

uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_runtime_docs.py

## Observability Impact

Adds a lightweight docs regression test so future agents can distinguish active stale executable guidance from allowed plugin identity or historical references.
