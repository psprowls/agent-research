---
sketch: 002
name: refresh-result-block
question: "What does each package's result look like in the refresh final report?"
winner: "B"
tags: [cli, refresh, report, density]
---

# Sketch 002 — Per-package result block

## Design Question
After a sweep, the user needs to audit what changed. How much detail does each package's block carry? Trade-off is density vs scannability vs auditability.

## How to View
```
open .planning/sketches/002-refresh-result-block/index.html
```

## Variants
- **A: Terse one-liner** — one line per package, like `git status`. Fast scan; opens Obsidian to verify.
- **B: Counted summary** — boxed per-package block with structured counts (filled/diff/ingest/flagged). Middle density.
- **C: Full wikilink dump** — every touched page named with a wikilink, mirrors `/graph-wiki:ingest`'s existing report style.

## What to Look For
- Side-by-side comparison: each variant shows both a 3-package detail view AND a 12-package sweep view. Density changes a lot at 12.
- For a one-package targeted refresh (`/graph-wiki:refresh packages/vault-io`), which format is the right fit?
- Does C's collapse-when-unchanged trick (9 packages elided in the sweep view) feel right, or annoying?
- Does B's "flagged" count differentiate it usefully from A's terse "needs review" suffix?
- C is the most consistent with how `/graph-wiki:ingest` already reports — does consistency matter here?
