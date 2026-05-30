---
created: 2026-05-30T19:17:22.985Z
title: Converge propose_domains _resolve_paths onto shared resolver
area: graph
files:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py:564-570,609
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:61-78
  - packages/wiki-io/src/wiki_io/_workspace.py
---

## Problem

`propose_domains.py` has its **own copy** of `_resolve_paths(workspace_arg)` (same
name, signature, and return contract as `graph.py`'s) that still uses the **old,
buggy** repo-resolution path — it was NOT fixed by quick task 260530-hxy.

```python
# propose_domains.py:564  (STILL BROKEN)
def _resolve_paths(workspace_arg: str) -> tuple[Path, Path]:
    if workspace_arg:
        cfg = resolve_config(Path(workspace_arg).resolve(), require_manifest=False)  # walks up from WORKSPACE
    else:
        cfg = resolve_config(None, require_manifest=False)
    return cfg.repo_root, cfg.workspace
```

`resolve_config` walks up from the **workspace** dir for `.git`, so on the standard
repo≠workspace layout (workspace is its own commit-less git repo) `cfg.repo_root`
binds to the **wiki vault's** `.git`, not the source repo — the exact divergence
260530-hxy eliminated in `graph.py:_resolve_paths` (which now delegates to
`resolve_wiki_and_repo`, resolving the repo from cwd like `scan`).

**Failure mode here is quieter than `graph build`'s** (which died loudly with
`fatal: ambiguous argument 'HEAD'`): `propose_domains_cmd` uses `repo_root` to write
`<repo_root>/domains.proposed.yaml` (`propose_domains.py:605-606`), so on the broken
layout it silently writes the proposed-domains file **into the wiki vault** instead
of the source repo (and resolves `code.db` via a workspace_root computed the old
way). Wrong output location rather than a crash — arguably nastier.

## Solution

Don't just patch propose_domains to match — **extract the corrected `_resolve_paths`
into ONE shared helper** that both `graph.py` and `propose_domains.py` import, so a
single source of truth makes future divergence structurally impossible (the same DRY
motivation behind routing both through `resolve_wiki_and_repo`).

1. Lift the fixed `graph.py:61-78` `_resolve_paths` into a shared module (e.g. a
   small `graph_wiki_agent/commands/_paths.py`, or alongside `resolve_wiki_and_repo`
   in `wiki-io` if call-site needs match — verify before placing).
2. Replace both `graph.py` and `propose_domains.py` copies with imports of it.
3. Drop the now-unused `resolve_config` import in `propose_domains.py:61` if orphaned.
4. Add a test reproducing the repo≠workspace case for `propose-domains` (proposed
   YAML lands in the source repo, not the vault) — mirror the 260530-hxy test.

## Related

Follow-up from quick task 260530-hxy (graph build repo resolution fix) — see
`.planning/quick/260530-hxy-fix-graph-build-repo-resolution-to-match/`. The hxy
planner surfaced this duplicate and deliberately left it out of scope.
