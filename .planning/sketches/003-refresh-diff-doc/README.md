---
sketch: 003
name: refresh-diff-doc
question: "What does raw/diffs/<pkg>-<from>..<to>.md contain when refresh writes it for ingest?"
winner: "C (with tweak — drop Pointers section, inline diff for 1-3 surface-change files)"
tags: [refresh, diff, raw, ingest, format]
---

# Sketch 003 — Diff doc anatomy

## Design Question
Refresh writes a synthetic source to `raw/diffs/` and dispatches `/graph-wiki:ingest` on it. The shape of that document determines:
1. Token cost of every refresh
2. Whether ingest produces good page updates
3. Whether a human can audit the doc later

## How to View
```
open .planning/sketches/003-refresh-diff-doc/index.html
```

## Variants
- **A: Raw git diff** — `git log --stat` + full `git diff` wrapped in markdown frontmatter. Lossless, mechanical, big (~18k tokens for the example).
- **B: Curated semantic delta** — LLM pre-pass extracts TL;DR, API changes, new concepts, decisions, contradictions. Compact (~1.8k). Adds a model call. Loses code fidelity.
- **C: Hybrid** — machine-generated structural sections (commits, stat, exports added/removed) + LLM prose for summary/decisions/contradictions + pointers back to the full git diff for on-demand drill-down. Middle cost (~4.5k).

## What to Look For
- This is the cost lever for refresh. A 12-package sweep with 3 stale packages: A pays 3 × 18k = 54k tokens *just for ingest input*. B pays 3 × 1.8k = 5.4k. Multiply by frequency.
- Does the ingestor actually need code-level fidelity? `/graph-wiki:ingest` already updates pages from prose sources (specs, articles, PRs). Diff docs could be the same.
- The hybrid (C) has a nice property: the machine sections never lie. If you can't trust the LLM summary, you can re-read the structural data.
- Token estimates in each variant's filebar are example-sized — your real-world packages may differ.
- The fact that B and C both call an LLM for the synthesis suggests refresh's cost story is "two model passes per stale package" (synthesize + ingest) vs A's one.
