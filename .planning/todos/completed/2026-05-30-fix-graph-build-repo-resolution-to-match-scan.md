---
created: 2026-05-30T18:44:34.009Z
title: Fix graph build repo resolution to match scan
area: graph
files:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:61
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:435
  - packages/workspace-io/src/workspace_io/config.py
  - packages/wiki-io/src/wiki_io/_workspace.py
---

## Problem

`graph-wiki-agent graph build` resolves the **source repo** differently from `scan`,
and the divergence breaks the standard layout where the wiki workspace is a separate
git repo from the source repo.

- `graph build` uses `_resolve_paths()` (`commands/graph.py:61`, called at `:435`) →
  `workspace_io.config.resolve(workspace_path)`, which walks up from the **workspace**
  directory looking for `.git`.
- `scan` uses `resolve_wiki_and_repo()` (`wiki_io/_workspace.py`) →
  `_find_repo_root(Path.cwd())`, i.e. the repo discovered from the current working dir.

On the standard repo≠workspace layout (e.g. workspace `~/Personal/graph-wiki/mono-repo-live`
is bootstrapped as its own commit-less git repo; source is `~/Personal/mono-repo`),
`graph build --full` resolves `repo_root = the workspace` and runs `git rev-parse HEAD`
there, dying with:

```
fatal: ambiguous argument 'HEAD': unknown revision or path not in the working tree.
```

Even if the workspace repo had commits, `graph build` would graph the **wrong tree**
(the wiki vault, not the source code). `scan` works because it resolves the repo from cwd.

Discovered 2026-05-30 while verifying the electron-classification fix (quick task
260530-gqp): `scan` re-ran the graph fine, but `graph build --full` failed.

## Solution

Make `graph build` resolve the source repo the way `scan` does — via cwd
(`_find_repo_root(Path.cwd())`) and/or by honoring a `repo-directory:` pin in
`<workspace>/.graph-wiki.yaml` consistently. Align `_resolve_paths()` with
`resolve_wiki_and_repo()` so the two entry points can never diverge.

Workaround until fixed: pin `repo-directory: <source-repo-abs-path>` in
`<workspace>/.graph-wiki.yaml` — `workspace_io.config._repo_directory_override` honors it.
