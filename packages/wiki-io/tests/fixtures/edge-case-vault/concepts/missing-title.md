---
category: concept
summary: This page is intentionally missing the required title field.
tags: [edge-case, frontmatter, testing]
updated: 2026-05-14
tokens: 67
---

# Missing Title Field

This page intentionally omits the `title:` field from its frontmatter. The `title`
field is required by the wiki schema per CLAUDE.md. Linters should flag this as a
missing required field.

The `check_structural()` function in eval-harness sets `frontmatter_valid = False`
when a cited page lacks a `title` key, so this page is useful for testing that path.
