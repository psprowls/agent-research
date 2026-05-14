---
title: Broken Wikilinks Example
category: concept
summary: This page contains wikilinks to pages that do not exist in this vault.
tags: [edge-case, wikilinks, testing]
updated: 2026-05-14
tokens: 134
---

# Broken Wikilinks Example

This page intentionally references non-existent pages to test wikilink resolution.

## Broken internal links

The following wikilinks point to pages that do not exist in this vault:

- [[wiki/packages/nonexistent-package/nonexistent-package]] — no such package page
- [[wiki/concepts/also-missing]] — no such concept page
- [[wiki/adrs/9999-never-written]] — no such ADR

## Valid link

The following link points to a page that does exist:

- [[wiki/concepts/missing-title]] — this page exists (though it lacks a title field)

A robust wikilink linter should report the three broken links above without crashing,
and correctly identify the fourth link as resolvable.
