---
created: 2026-05-21T17:45:00.000Z
title: graph-wiki-agent bootstrap --interactive flag
area: graph-wiki
origin_phase: 25
deferred_from: PKGCLS-03 (D-12)
files:
  - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py
---

## Problem

`agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py:run_init` hardcodes
`non_interactive=True` when calling into `init_vault`, so any genuinely ambiguous
(empty / unrecognized) container row is silently skipped during `graph-wiki-agent
bootstrap` — there is no escape hatch even on a TTY.

Phase 25 (PKGCLS-01..05) loosened `_classify_dir` Rule 3 to permissive
(`≥1 manifested child → package`), which narrows the surface where this matters
but does not eliminate it: genuinely mixed/empty directories still fall to
`ambiguous` and silently skip under non-interactive bootstrap.

Original PKGCLS-03 requirement scoped the `--interactive` Typer flag in with the
classifier fix, but D-12 deferred the flag work to keep Phase 25 surgical
(classifier rewrite + tests + doc + todo move only). This todo carries that work
forward as its own backlog item.

## Solution

Add a `--interactive` Typer flag (default off) on `graph-wiki-agent bootstrap`
and thread a corresponding `non_interactive` boolean through `run_init` so that:

- Default (`--interactive` off): current behavior — silent-skip ambiguous rows.
- `--interactive` on, with TTY: prompt the user to confirm each ambiguous
  classification (mirrors what `init_vault.py` already supports internally).

Acceptance:

- `graph-wiki-agent bootstrap --interactive --help` shows the flag.
- Running `graph-wiki-agent bootstrap --interactive` against a repo with at
  least one fallback-ambiguous container produces a prompt rather than a silent
  skip.
- Unit test for the `non_interactive` thread-through in `run_init`.
- Plugin shim and MCP `WikiBootstrapInput` updated in lockstep if/when the
  decision is to expose the flag at the MCP surface as well (open question —
  defer to discuss-phase).

## References

- `.planning/phases/25-packages-dir-misclassification-fix/25-VERIFICATION.md`
  PKGCLS-03 row (PARTIALLY SATISFIED — doc-side only)
- `.planning/phases/25-packages-dir-misclassification-fix/25-01-SUMMARY.md`
  §"Next Phase Readiness" — draft backlog wording (verbatim)
- `.planning/phases/25-packages-dir-misclassification-fix/25-CONTEXT.md`
  D-12 — flag deferral lock
