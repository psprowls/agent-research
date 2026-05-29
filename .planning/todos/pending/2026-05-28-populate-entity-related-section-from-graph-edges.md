---
created: 2026-05-28
title: Populate entity-page `## Related` section from graph edges
area: wiki-io
origin: Phase 56 UAT (Test 1) — surfaced by Pat while verifying generated entity pages
files:
  - packages/wiki-io/src/wiki_io/entity_writer.py            # write_entities / _render_entity_page
  - packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md   # static ## Related block
  - packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md
  - packages/wiki-io/src/wiki_io/assets/page-templates/entity-domain.md
---

## Problem

Generated entity pages ship with literal placeholder links in their `## Related`
section, e.g.:

```
## Related
- [[concepts/<concept>]]
- [[apps/<other-app>]]
- [[domains/<domain>]]
- [[packages/<pkg>]]
```

These are `<...>` authoring-instruction placeholders, retained on purpose under
Phase 56's D-01 two-token rule (`{{var}}` = scanner-substituted data; `<...>` =
authoring instruction left untouched). So this is **NOT a Phase 56 defect** — the
`{{...}}` data tokens all substitute correctly and every page got real prose.

But the result is a visible blemish: the graph already *knows* the true
relationships for each node (a package's `depends_on` packages, its domain
membership, dependency libs, etc.), yet the Related section is static template
text. Nothing in `entity_writer.py` or the narrator step populates it from graph
edges — confirmed by grep during Phase 56 UAT. Even with the narrator (Bedrock)
running, Related stays as placeholders.

## Solution

TBD — new scope, candidate for a future phase. Likely shape:

- In `write_entities` / `_render_entity_page`, replace the static `## Related`
  block with links derived from the node's graph edges (depends_on → packages,
  domain membership → domains, dependency edges → dependencies, etc.).
- Decide per-kind which edge types map into Related and in what order.
- Fall back to a `> TODO:` marker (D-03 style) only when a node genuinely has no
  related edges, rather than emitting `<...>` placeholders.

Things to verify before building:
- Whether Related should be a scanner-owned (re-derived each scan) or
  fill-when-empty (human-editable, like `summary:`) field. Likely scanner-owned,
  since it's pure graph projection — but that overwrites any hand-curated links.
- Interaction with the index generator's relationship rendering (Phase 57 IDX
  work) so the two stay consistent.
- Re-baseline entity-page golden/integration fixtures once links become dynamic.
