---
created: 2026-05-29T01:38:16.277Z
title: Test suites fan out under every package in wiki index
area: wiki-io
files:
  - packages/wiki-io/src/wiki_io/index_generator.py:282
  - packages/graph-io/src/graph_io/queries.py
---

## Problem

In the generated wiki index `## By Kind` section, **every** package/app nests
the **same nine** `Test Suites`, instead of each package showing only the suite(s)
that actually test it. Surfaced during Phase 57 UAT (test 4 / IDX-04). The IDX-04
structure itself (nested sub-lists, no flat `### Test Suites` group) is correct —
the defect is the breadth of what nests.

### Likely root cause (needs discussion / confirmation)

All 9 `test_suite` nodes in the live graph share the same node **name: `tests`**.
`_consumer_pkgs(kind='test_suite', entity_name=...)`
(`index_generator.py:282`) resolves a suite's target packages with
`WHERE t.kind='tests' AND ts.name = ?`. Because the join keys on **name**, not
node id, a query for name `tests` matches the `tests` edges of *all nine* suites
at once — so each suite inherits every other suite's targets and nests under
every consumer package.

Evidence from the live graph (`.graph/code.db`):
- test_suite nodes: 9 (all named `tests`)
- package+app nodes: 8
- `tests` edges: **23** (NOT the full 72 fan-out) — i.e. the underlying
  per-suite edges are correct; the renderer's name-based resolution collapses them.

## Solution

TBD — discuss first. Candidate directions:
- Resolve consumer packages by test_suite **node id** rather than `name`
  (`_place_entities` already has the `PlacedEntity`; thread the id/uri through
  `_consumer_pkgs` instead of the name).
- And/or give test_suite nodes **unique names** at scan time (e.g.
  `tests-<package>`), in graph-io / source-parser scan-time population, so
  name-based lookups disambiguate.
- Confirm whether `_consumer_pkgs_in_domain` has the same name-keyed flaw.

Pat does not yet understand the cause fully — revisit and decide approach before
implementing.
