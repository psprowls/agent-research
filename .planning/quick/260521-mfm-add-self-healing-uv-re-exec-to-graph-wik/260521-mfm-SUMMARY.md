---
quick_id: 260521-mfm
slug: add-self-healing-uv-re-exec-to-graph-wik
status: complete
date: 2026-05-21
---

# Quick Task 260521-mfm: Add self-healing uv re-exec to graph-wiki plugin shim scripts

## Goal

Make `python <plugin-shim>.py` work from any shell, not just under `uv run --project packages/wiki-io`. Previously, bare-`python` invocations failed with `ModuleNotFoundError: No module named 'wiki_io'` because the shims import workspace packages at top level.

## What changed

- **New file** `plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py` — 45-line bootstrap helper. `ensure()` tries `import wiki_io`; on `ImportError`, walks up from `__file__` to find `packages/wiki-io/pyproject.toml`, then `os.execvpe`s under `uv run --project <pkg> python <self> <args...>`. A `GRAPH_WIKI_SHIM_REEXEC=1` env-var guard prevents infinite loops if uv itself can't satisfy the import.
- **Wired into 6 shims** — `detect_containers.py`, `ingest_source.py`, `init_vault.py`, `lint_wiki.py`, `scan_monorepo.py`, `wiki_search.py`. Each calls `_ensure_uv()` immediately before the existing `from wiki_io...` import.

## Commits

| Commit  | What                                              |
|---------|---------------------------------------------------|
| ab40a43 | feat(graph-wiki): add _uv_reexec.ensure() bootstrap helper |
| 9484187 | feat(graph-wiki): wire _uv_reexec.ensure() into 6 plugin shims |

## Smoke test

From a clean cwd (`/tmp`) with no uv project context:

```
$ /usr/bin/env python3 /Users/pat/Personal/agent-research/plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help
usage: detect_containers.py [-h] [--json]
Classify a repo's top-level dirs.
…
exit: 0
```

Re-exec via uv succeeds; help text from the real `wiki_io.detect_containers` is printed.

Guard verified:

```
$ GRAPH_WIKI_SHIM_REEXEC=1 python3 .../detect_containers.py --help
Traceback (most recent call last):
  …
ModuleNotFoundError: No module named 'wiki_io'
exit: 1
```

With the guard set, `ensure()` returns early and the real ImportError surfaces — no infinite loop.

## Execution notes (workflow incident)

The first spawned executor (worktree-agent-a24b889d809b70b33) only completed Task 1 — created `_uv_reexec.py` — and then committed it directly to `main` instead of its worktree branch. It then halted with an erroneous "I destroyed commits" report based on a misread of the reflog (the `git reset --hard` it claimed to have run does not appear in `main`'s reflog; no commits were lost). The orchestrator verified `git log` / `git reflog`, confirmed no damage, cleaned up the orphaned worktree, and finished Tasks 2–3 (wiring + smoke test) directly without re-spawning. The ab40a43 commit on main is the helper-creation work from that aborted executor; 9484187 is the orchestrator's atomic wiring commit.

## Out of scope (left intact)

- `_config.py` also imports `workspace_io` but inside a `try/except ImportError` already — not breaking anything, deferred.
- Docs/command bodies were not updated; the point of this change is to make them unnecessary.
