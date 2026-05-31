---
id: T01
parent: S06
milestone: M002
key_files:
  - packages/graph-wiki-core/src/graph_wiki_core/commands/init.py
  - packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py
  - packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py
  - packages/graph-wiki-core/tests/unit/test_commands_ingest.py
key_decisions:
  - Reaffirmed D004/R012 stable manifest identity: manifests record `graph-wiki-agent` even though version metadata is read from the `graph-wiki-core` distribution.
duration: 
verification_result: passed
completed_at: 2026-05-31T18:11:01.913Z
blocker_discovered: false
---

# T01: Repaired graph-wiki manifest identity and ingest initialization guidance regressions.

**Repaired graph-wiki manifest identity and ingest initialization guidance regressions.**

## What Happened

Updated `run_init()` to register the stable manifest plugin identity `graph-wiki-agent` while continuing to source installed/applied version values from the `graph-wiki-core` Python distribution. The nearby comment now distinguishes stable plugin identity from the current distribution name. Updated ingest NOT_INITIALIZED guidance to recommend the active `gw graph build` entrypoint. Added a bootstrap regression test that runs `run_init()` against temporary repo/workspace paths with the distribution version lookup patched to a sentinel, reads the generated manifest through `workspace_io.manifest`, and asserts `graph-wiki-agent` is present with matching version fields while `graph-wiki-core` is not registered as a plugin. Updated the ingest NOT_INITIALIZED test to assert the new guidance and explicitly reject the stale `graph-wiki-core graph build` text.

## Verification

Ran the focused core command tests required by the task plan; all 27 tests passed. Also ran a targeted stale-string diagnostic confirming the old plugin registration string and stale ingest guidance are absent from the touched runtime/test files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -q` | 0 | ✅ pass — 27 passed in 0.42s | 2157ms |
| 2 | `python - <<'PY'
from pathlib import Path
checks = {
    'init_plugin_core': ('packages/graph-wiki-core/src/graph_wiki_core/commands/init.py', 'plugin="graph-wiki-core"'),
    'ingest_old_guidance': ('packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py', 'graph-wiki-core graph build'),
    'ingest_test_old_positive': ('packages/graph-wiki-core/tests/unit/test_commands_ingest.py', 'assert "graph-wiki-core graph build" in msg'),
}
failed = []
for name, (path, needle) in checks.items():
    text = Path(path).read_text(encoding='utf-8')
    present = needle in text
    print(f'{name}: {"present" if present else "absent"}')
    if present:
        failed.append(name)
if failed:
    raise SystemExit(f'stale strings remain: {failed}')
PY` | 0 | ✅ pass — stale strings absent | 104ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py`
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
