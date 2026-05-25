---
created: 2026-05-19T01:55:24.550Z
title: Fix workspace repo resolution in init_vault and detect_containers
area: tooling
resolves_phase: 17
files:
  - packages/wiki-io/src/wiki_io/init_vault.py:305-306
  - packages/wiki-io/src/wiki_io/detect_containers.py:174-175
---

## Problem

Both `init_vault.py` and `detect_containers.py` resolve the repo root incorrectly when the wiki lives at `<workspace>/wiki/` (the new layout):

```python
wiki, _ = resolve_wiki_and_repo()
repo = wiki.parent  # v1: repo is always wiki's parent directory
```

With the v2 workspace layout, `wiki.parent` is the empty `graph-wiki/` workspace dir, not the actual repo root. `detect_containers.py --json` returns `[]` and `init_vault.py` fails to detect any containers when run from the repo.

Discovered while running `/graph-wiki:bootstrap` on the agent-research repo — had to work around it by calling `init_wiki()` directly from Python with `repo_path=/Users/pat/Personal/agent-research`.

Secondary bug in the detector: it self-classifies the workspace dir itself (`graph-wiki/`) as a `docs` container, polluting the pinned layout block with a harmless-but-noisy entry.

## Solution

1. In `init_vault.py:305` and `detect_containers.py:174`, use the second return value:
   ```python
   _, repo = resolve_wiki_and_repo()
   ```
   `resolve_wiki_and_repo()` already returns `(wiki_path, repo_root)` — the second value is the correct repo root from `workspace_io`.

2. In `detect_containers.detect()` (or its caller), exclude the resolved workspace path from classification so the workspace dir doesn't appear in its own layout block.

3. Add a test in `packages/wiki-io/tests/` that runs the detector against a fixture repo with wiki at `<repo>/graph-wiki/wiki/` and asserts it finds repo-root containers (not workspace-root contents).
