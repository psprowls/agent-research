---
id: T01
parent: S01
milestone: M002
key_files:
  - packages/graph-wiki-core/pyproject.toml
  - packages/graph-wiki-core/src/graph_wiki_core
  - packages/graph-wiki-core/tests/test_package_boundary.py
  - uv.lock
key_decisions:
  - Copied shared source into `graph_wiki_core` while leaving `cli.py` and `mcp/` in `graph_wiki_agent` for later presentation-package extraction.
  - Kept Typer as a dependency for S01 because migrated command modules still import Typer wrappers, but did not declare any console scripts in `graph-wiki-core`.
duration: 
verification_result: passed
completed_at: 2026-05-31T16:06:30.539Z
blocker_discovered: false
---

# T01: Created the library-only `graph-wiki-core` workspace package and migrated shared graph-wiki source into the `graph_wiki_core` namespace.

**Created the library-only `graph-wiki-core` workspace package and migrated shared graph-wiki source into the `graph_wiki_core` namespace.**

## What Happened

Created `packages/graph-wiki-core` as a uv workspace member with `uv_build`, no `[project.scripts]`, Python `>=3.11`, workspace-local dependencies, and explicit direct runtime dependencies for the moved modules. Copied only the shared implementation from `agents/graph-wiki-agent/src/graph_wiki_agent` into `packages/graph-wiki-core/src/graph_wiki_core`: `commands/`, `prompts/`, `graph_tools.py`, `config.py`, `uri_slug.py`, and package `__init__.py`. Rewrote migrated source references from `graph_wiki_agent`/`graph-wiki-agent` to `graph_wiki_core`/`graph-wiki-core`, while intentionally leaving presentation-only `cli.py` and `mcp/` in the original agent package. Added package-boundary tests that assert no console scripts are declared, migrated Python source has no stale old namespace references, bytecode files were not copied into source paths, and the query command imports from `graph_wiki_core.commands.query`. During verification, an early bytecode assertion was narrowed because runtime imports and pytest legitimately create `__pycache__`; the final artifact cleanup separately verifies no `__pycache__` or `.pyc` remains in the new package tree.

## Verification

Verified the required import smoke with `uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.query"`. Ran the new package-boundary pytest suite with `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests`, which passed 4 tests. Ran a final artifact cleanliness check after removing runtime-generated caches to confirm `packages/graph-wiki-core` contains no `__pycache__` directories or `.pyc` files. Also confirmed `uv.lock` contains a `graph-wiki-core` entry after uv resolved the new workspace package.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.query"` | 0 | ✅ pass | 959ms |
| 2 | `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests` | 0 | ✅ pass | 665ms |
| 3 | `find packages/graph-wiki-core -type d -name '__pycache__' -prune -exec rm -rf {} +; find packages/graph-wiki-core -type f -name '*.pyc' -delete; python - <<'PY'
from pathlib import Path
root=Path('packages/graph-wiki-core')
artifacts=[str(p) for p in root.rglob('*') if p.name == '__pycache__' or p.suffix == '.pyc']
print('stale_artifacts=', artifacts)
raise SystemExit(1 if artifacts else 0)
PY` | 0 | ✅ pass | 45ms |
| 4 | `python - <<'PY'
from pathlib import Path
text=Path('uv.lock').read_text()
print('graph-wiki-core in uv.lock=', 'name = "graph-wiki-core"' in text)
PY` | 0 | ✅ pass | 37ms |

## Deviations

Added explicit `langchain-core>=1.4.0` and `pyyaml>=6.0` to the new package dependencies because migrated modules import them directly, even though the task plan only called out the highest-risk moved dependencies by name.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-core/pyproject.toml`
- `packages/graph-wiki-core/src/graph_wiki_core`
- `packages/graph-wiki-core/tests/test_package_boundary.py`
- `uv.lock`
