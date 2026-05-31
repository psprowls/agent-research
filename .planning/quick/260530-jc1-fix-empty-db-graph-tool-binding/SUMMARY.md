---
status: complete
phase: quick-260530-jc1
plan: "01"
subsystem: graph-wiki-agent
tags: [bug-fix, graph-tools, sweep-harness, judge-signal]
key_files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
    - agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py
decisions:
  - Guard on node count, not connection success — ox1 (e42ae87) made read_only_connect succeed on a zero-node code.db, so connection-success was no longer a sufficient signal that graph tools should bind.
metrics:
  completed: "2026-05-30T00:00:00Z"
  tasks_completed: 1
  commit: c03550b
---

# quick-260530-jc1 — Guard empty-but-valid graph DB before binding graph tools

## What

Fixed the sweep judge-signal collapse. After ox1 (`e42ae87`) made
`read_only_connect` succeed on a zero-node `code.db`, `run_query` bound the graph
tools against an empty DB → librarian hit the iteration cap → emitted the
code-fallback disclaimer → judge scored ~0.10 for every candidate.

`query.py` now checks `SELECT COUNT(*) FROM nodes == 0` inside the graph-connection
try-block (`query.py:952`) and, when the graph is empty, skips `build_graph_tools`
and appends a fallback addendum instead of binding tools.

## Verification

- Guard line present at `query.py:952`.
- `test_query_graph_tools_wiring.py` covers the empty-DB-no-tools wiring.
- Shipped in commit `c03550b` (`fix(quick-260530-jc1): guard against empty graph DB before binding tools`).

## Note

Retroactively authored during v1.11 milestone close — the original quick-task run
committed the PLAN (`e0a048e`) and the fix (`c03550b`) but never wrote this SUMMARY.
Content reconstructed from the PLAN, STATE.md, and the verified guard in source.
