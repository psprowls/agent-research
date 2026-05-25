---
title: "ADR-0011: Single workspace root `<repo>/lattice/`"
category: adr
summary: Consolidate all per-repo lattice data under a single `<repo>/lattice/` workspace root — vault at `lattice/wiki/`, work items at `lattice/work/`, machine state at `lattice/.graph/` — superseding the two-root design that was never implemented.
adr_id: "0011"
status: accepted
decision_date: 2026-05-09
deciders: [Patrick Sprowls]
supersedes: []
superseded_by:
tags: [layout, ecosystem, workspace]
updated: 2026-05-09
tokens: 845
---

# ADR-0011: Single workspace root `<repo>/lattice/`

**Status:** accepted (2026-05-09)

## Context

An earlier ADR (the original per-repo directory layout decision) prescribed two distinct roots inside a consumer repo: `<repo>/wiki/` for the vault and `<repo>/.lattice/` for machine state. The rationale was to keep human-visible and machine-regenerable data in clearly separate trees.

`packages/lattice-workspace` shipped with `DEFAULT_WORKSPACE_NAME = "lattice"`, placing all per-repo data under a single `<repo>/lattice/` root. The two-root design was never implemented. What shipped is exactly the "single root `<repo>/lattice/`" alternative that the earlier ADR rejected, though the objection ("forces machine state into the human-visible tree") is addressed by the `.graph/` subdirectory being gitignored.

This ADR records the shipped design as the accepted decision.

## Decision

Use `<repo>/lattice/` as the single workspace root. The sub-paths are:

| Path | Visibility | Purpose |
|---|---|---|
| `<repo>/lattice/wiki/` | Committed | The human-visible vault (Obsidian, markdown, committed to git). |
| `<repo>/lattice/work/` | Committed | Work items (bugs, features, tech debt) alongside the vault. |
| `<repo>/lattice/.graph/` | Gitignored at v1 | Machine state for `lattice-graph`; `code.db` lives here. |

`packages/lattice-workspace` resolves the workspace root via `DEFAULT_WORKSPACE_NAME = "lattice"` and the `LATTICE_WORKSPACE` env var override. All per-repo paths are derived from this root.

## Consequences

**Positive:**
- Single root to remember and document.
- `lattice/` is clearly ecosystem-owned; subdirectory naming (`wiki/`, `work/`, `.graph/`) makes each area's purpose visible.
- Machine state is still gitignored at v1 (same intent as the original two-root design).
- Consistent with how the live repo is already set up.

**Negative:**
- Documentation and links in earlier ingested sources still reference `<repo>/wiki/` and `<repo>/.lattice/`. These are now stale.
- The path `lattice/.graph/` is a dotfile inside a non-dot directory, which is slightly unconventional.

## Alternatives considered

- **Restore the two-root design (`<repo>/wiki/` + `<repo>/.lattice/`)** — rejected: the code ships the single-root design; reverting would require a breaking change to `packages/lattice-workspace`.

## Impact

- [[wiki/packages/lattice-workspace/lattice-workspace]] — owns the `DEFAULT_WORKSPACE_NAME` constant and workspace-root resolution.
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — vault is now `<workspace>/wiki/`, not `<repo>/wiki/`.
- [[wiki/plugins/lattice-graph/lattice-graph]] — graph DB is now `<workspace>/.graph/code.db`.
- [[wiki/plugins/lattice-work/lattice-work]] — work items live at `<workspace>/work/`.
- [[wiki/concepts/per-repo-layout]] — reflects the single-root paths.
