---
created: 2026-05-29T01:38:16.277Z
title: Fix entity summary placeholder breaks Obsidian rendering
area: wiki-io
files:
  - packages/wiki-io/src/wiki_io/entity_writer.py:587
---

## Problem

When an entity has no description, `entity_writer` fills the frontmatter
`summary:` with the placeholder `> TODO: <add a one-line summary for {name}>`
(`packages/wiki-io/src/wiki_io/entity_writer.py:587`). This string is later
rendered inline on entity bullets in the generated wiki index (and in entity
pages), e.g.:

```
- [[wiki/entities/dep_pyyaml|pyyaml]] — > TODO: <add a one-line summary for pyyaml>
```

This breaks Obsidian rendering:
- The leading `>` makes Obsidian treat the text as a **blockquote**.
- `<add a one-line summary for ...>` is parsed as an **unclosed HTML tag**.

Together these swallow all following list items after the first placeholder —
everything below the first `> TODO:` bullet stops rendering as a list.

Surfaced during Phase 57 UAT (test 3 / IDX-03 inline summaries). The inline
summary feature itself works correctly; the defect is the placeholder *format*,
which originates in the entity-template population (Phase 56), not the Phase 57
index renderer.

## Solution

Change the placeholder to a non-blockquote, HTML-safe form. Options:
- Plain text with no `>` and no angle brackets, e.g. `TODO: add a one-line
  summary for {name}`.
- Backtick-escape the angle-bracket portion.

Pick the form that still reads as an obvious fill-me-in marker but renders
cleanly inline in Obsidian. Update the corresponding tolerant-read/empty-summary
expectations in tests if they assert on the exact placeholder string. Note the
asset templates (`page-templates/source.md`, `AGENTS.md.template`,
`CLAUDE.md.template`) use `<one-line summary>` for the same purpose — consider
whether those need the same treatment when rendered.
