---
estimated_steps: 6
estimated_files: 12
skills_used: []
---

# T03: Verify S04 integration contract and classify remaining references

Expected executor skills: `verify-before-complete`, `uv-package-manager`.

Why: S04 spans runtime shim behavior, CLI command availability, docs, and compatibility decisions. Before completion, the executor must prove both the specific contracts and the package-local CLI surface still hold.

Do: Run focused real-entrypoint help checks for `gw bootstrap --help` and `gw ingest source --help` through `uv run --package graph-wiki-cli`. Run the new shim and docs tests. Run the full `packages/graph-wiki-cli/tests` suite to catch CLI presentation regressions. Then perform a focused stale-reference scan over `README.md`, `plugins/graph-wiki`, and the three graph-wiki packages; classify any remaining `graph-wiki-agent` or `graph_wiki_agent` occurrences in the task summary as allowed plugin identity, negative tests, historical/generated/S05-owned cleanup, or a blocker requiring edits. Do not edit `.gsd/` or generated planning artifacts.

Threat Surface (Q3): no auth or data exposure changes; the only input trust boundary is user CLI args, which shims continue to pass through to Typer unchanged. Abuse/data exposure: none introduced.

Load Profile (Q6): per-operation cost is one local subprocess from a plugin shim to `gw`, unchanged in scale from the prior executable; 10x usage would be bounded by local process startup cost, not shared service state.

Done when: all verification commands pass and the remaining-reference classification shows no active runtime-facing executable guidance to `graph-wiki-agent` in S04-owned files.

## Inputs

- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
- `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`
- `packages/graph-wiki-cli/tests`
- `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`
- `README.md`
- `plugins/graph-wiki/README.md`
- `plugins/graph-wiki/CLAUDE.md`
- `plugins/graph-wiki/.claude-plugin/plugin.json`

## Expected Output

- Update the implementation and proof artifacts needed for this task.

## Verification

uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests

## Observability Impact

No runtime observability change; this task produces fresh verification evidence and a stale-reference classification for S05 handoff.
