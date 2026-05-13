---
title: "ADR-0004: Filesystem-only `affects:` resolution in work items for v1"
category: adr
summary: In v1, `affects:` fields in work items are matched by filesystem path prefix only; graph-aware resolution is deferred until lattice-graph ships.
adr_id: "0004"
status: accepted
decision_date: 2026-05-07
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [adr, lattice-work, work-items, affects, code-graph, scope]
updated: 2026-05-07
tokens: 491
---

# ADR-0004: Filesystem-only `affects:` resolution in work items for v1

**Status:** accepted (2026-05-07)

## Context

Work items carry an `affects:` field listing the code surfaces (paths, packages, symbols) that the work touches. The richest version of this field would be matched against [[wiki/plugins/lattice-graph/lattice-graph]]'s graph — symbol names resolve to graph nodes, allowing reverse lookups ("which work items affect this function?"). But `lattice-graph` has not yet shipped, and v1 of [[wiki/plugins/lattice-work/lattice-work]] needs a complete contract.

## Decision

In v1, the `affects:` field is matched by **filesystem path prefix only**. The v1 sidecar (`work-index.json` regenerator) makes no graph queries. Symbol-level matching, package-graph traversal, and any other graph-aware resolution are deferred until `lattice-graph` ships and the v1.1 work-tracker upgrade can be planned around a stable graph schema.

## Consequences

- v1 ships independently of `lattice-graph` — no blocking peer dependency.
- The `affects:` field's v1 expressivity is limited to paths; users who want symbol granularity must wait or list explicit paths.
- The contract is forward-compatible: graph-aware resolution can be added in v1.1 without changing the field's surface syntax (paths remain valid; graph identifiers become an additional accepted form).
- The sidecar's complexity stays bounded — no graph queries, no caching layer, no schema-version coupling to a peer plugin in v1.

## Related

- [[wiki/plugins/lattice-work/lattice-work]]
- [[wiki/plugins/lattice-graph/lattice-graph]]
