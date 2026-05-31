---
id: T01
parent: S04
milestone: M002
key_files:
  - plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py
  - packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-05-31T17:00:38.544Z
blocker_discovered: false
---

# T01: Rewired the graph-wiki Bedrock plugin shims from `graph-wiki-agent` to `gw` and added argv-mapping regression coverage.

**Rewired the graph-wiki Bedrock plugin shims from `graph-wiki-agent` to `gw` and added argv-mapping regression coverage.**

## What Happened

Updated the Bedrock subprocess branch in all five graph-wiki plugin shims while preserving their backend selector calls and Claude-hosted `wiki_io` branches. The simple command shims now call `gw scan`, `gw lint`, and `gw query`; the semantic translations now call `gw bootstrap` for vault initialization and `gw ingest source` for source ingestion. Added a package-local pytest file that executes each shim as `__main__`, fakes `_config.backend_for` to return `bedrock`, monkeypatches `subprocess.run`, supplies representative `sys.argv`, and asserts the exact subprocess argv plus propagated `SystemExit(0)`. The tests fake only import-time `wiki_io` modules so they do not require Bedrock and never execute `gw`.

## Verification

Ran the required package-local pytest target and confirmed all five parametrized shim cases pass. Also ran a static check over the five touched shim scripts confirming no remaining `graph-wiki-agent` references in those files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py` | 0 | ✅ pass (5 passed) | 1558ms |
| 2 | `python - <<'PY'
from pathlib import Path
files = [
Path('plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py'),
Path('plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py'),
Path('plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py'),
Path('plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py'),
Path('plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py'),
]
failed = False
for p in files:
    text = p.read_text()
    contains = 'graph-wiki-agent' in text
    print(f'{p}: graph-wiki-agent={contains}')
    failed = failed or contains
raise SystemExit(1 if failed else 0)
PY` | 0 | ✅ pass (no stale executable references in touched shims) | 55ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`
- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
