---
created: 2026-05-20T18:52:13.775Z
title: Fix packages dir misclassification in container detector
area: graph-wiki
resolves_phase: 25
files:
  - packages/vault-io/src/vault_io/detect_containers.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py
---

## Problem

The container detector classifies a top-level `packages/` directory containing
5/6 children with manifests as `ambiguous` instead of `package`. Reproduced
during `/graph-wiki:bootstrap` on this repo (2026-05-20):

```
packages  -> ambiguous  (6 children) — 5/6 children have manifests; 0 loose .md
agents    -> package    (1 children) — all 1 children have manifests
plugins   -> package    (1 children) — all 1 children have manifests
```

Under non-interactive bootstrap (e.g. via `graph-wiki-agent bootstrap`, which
hardcodes `non_interactive=True` in `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py:run_init`),
ambiguous rows silently become `skip`. Result: `wiki/packages/` is not
created and the workspace's biggest container is omitted from the wiki
tree. During this session I had to post-hoc patch the layout block in
`wiki/CLAUDE.md` and `mkdir wiki/packages/`.

The current heuristic in `_classify_dir` (detect_containers.py) appears to
require *all* children to carry manifests to classify as `package`. A single
non-manifested sibling flips the whole directory to `ambiguous`. That bar is
too high for real monorepos where one experimental/legacy package commonly
lacks a manifest.

## Solution

Loosen the `package` classification rule so a strong majority of manifested
children (e.g. ≥ 80%, or `manifested >= children - 1`) still counts as
`package`. Keep `ambiguous` for genuinely mixed dirs (half manifests, half
loose markdown).

Verify on this repo: bootstrap should classify `packages/` as `package`
without any interactive prompt.

Bonus consideration: `run_init` hardcoding `non_interactive=True` means
there's no escape hatch even when running on a TTY. Consider exposing
`--interactive` on `graph-wiki-agent bootstrap` so users can confirm
ambiguous classifications without dropping to `init_vault.py`.
