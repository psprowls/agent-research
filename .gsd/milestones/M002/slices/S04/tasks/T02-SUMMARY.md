---
id: T02
parent: S04
milestone: M002
key_files:
  - README.md
  - plugins/graph-wiki/README.md
  - plugins/graph-wiki/CLAUDE.md
  - plugins/graph-wiki/.claude-plugin/plugin.json
  - packages/graph-wiki-cli/tests/unit/test_runtime_docs.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-05-31T17:04:03.603Z
blocker_discovered: false
---

# T02: Updated current Graph Wiki docs to advertise `gw` / `graph-wiki-cli` and added a runtime-docs guard against stale `graph-wiki-agent` executable guidance.

**Updated current Graph Wiki docs to advertise `gw` / `graph-wiki-cli` and added a runtime-docs guard against stale `graph-wiki-agent` executable guidance.**

## What Happened

Rewrote the root README around the current package-only Graph Wiki layout (`graph-wiki-core`, `graph-wiki-cli`, `graph-wiki-mcp`) and package-scoped `uv run --package graph-wiki-cli gw ...` usage. Updated the plugin README so Bedrock workflow prose routes to `gw` from `graph-wiki-cli` while preserving the `graph-wiki` plugin identity and slash-command namespace. Updated the plugin maintainer CLAUDE.md with the exact T01 shim-to-CLI mapping (`scan_monorepo.py` -> `gw scan`, `init_vault.py` -> `gw bootstrap`, `ingest_source.py` -> `gw ingest source`, `lint_wiki.py` -> `gw lint`, `wiki_search.py` -> `gw query`) and pointed maintainers at the shim argv regression test. Updated plugin.json description to identify `gw from graph-wiki-cli` as the Bedrock CLI companion while keeping the plugin `name` as `graph-wiki`. Added `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`, which asserts package-scoped `gw --help` examples exist, stale runtime executable patterns are absent from current docs, and plugin identity fields remain allowed separately.

## Verification

Ran the required docs guard test, the existing plugin Bedrock shim argv regression test, and a final targeted scan of edited docs for `graph-wiki-agent` mentions. All passed; the final scan reported no stale mentions in the edited docs.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_runtime_docs.py` | 0 | ✅ pass (3 tests passed) | 1524ms |
| 2 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py` | 0 | ✅ pass (5 tests passed) | 1132ms |
| 3 | `python3 - <<'PY'
from pathlib import Path
paths = [
    Path('README.md'),
    Path('plugins/graph-wiki/README.md'),
    Path('plugins/graph-wiki/CLAUDE.md'),
    Path('plugins/graph-wiki/.claude-plugin/plugin.json'),
]
found = False
for p in paths:
    for i,line in enumerate(p.read_text().splitlines(),1):
        if 'graph-wiki-agent' in line:
            print(f'{p}:{i}: {line}')
            found = True
print('stale_mentions=', found)
PY` | 0 | ✅ pass (stale_mentions=False) | 61ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `README.md`
- `plugins/graph-wiki/README.md`
- `plugins/graph-wiki/CLAUDE.md`
- `plugins/graph-wiki/.claude-plugin/plugin.json`
- `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`
