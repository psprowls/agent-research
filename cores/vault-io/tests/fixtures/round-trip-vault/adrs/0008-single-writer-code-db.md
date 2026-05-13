---
title: "ADR-0008: Single-writer `code.db` — only `cg update` writes; consumers open read-only"
category: adr
summary: cg update is the only writer to <workspace>/.graph/code.db; all consumers open the database in read-only mode, enforced via SQLite write-lock and exit code 6 (UPDATE_IN_PROGRESS).
adr_id: "0008"
status: accepted
decision_date: 2026-05-07
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [adr, lattice-graph, sqlite, concurrency, read-only, single-writer]
updated: 2026-05-09
tokens: 629
---

# ADR-0008: Single-writer `code.db` — only `cg update` writes; consumers open read-only

**Status:** accepted (2026-05-07)

## Context

`<workspace>/.graph/code.db` (default: `<repo>/lattice/.graph/code.db`) is the SQLite store backing [[wiki/plugins/lattice-graph/lattice-graph]]. Multiple processes can plausibly want to touch it: the update lifecycle (re-parse on git diff), slash commands querying the graph, the MCP server, wiki integration lint, and `prefer-graph-over-grep` lookups. SQLite tolerates multi-reader-single-writer but only when callers respect that model; a stray writer can corrupt or stall queries.

## Decision

**`cg update` is the only writer to `<workspace>/.graph/code.db`.** All other consumers — slash commands, MCP server, wiki integration, `prefer-graph-over-grep`, ad-hoc scripts — open the database in **read-only mode**.

The single-writer rule is enforced **structurally**: the writer takes a SQLite write-lock for the duration of update; concurrent writer attempts return **exit code 6 (`UPDATE_IN_PROGRESS`)** and abort. Readers continue uninterrupted (WAL mode); they never block updates and updates never block them.

## Consequences

- Concurrency model is trivial to reason about — N readers, at most one writer, mediated by the OS-level write-lock SQLite already implements.
- Any future tool that needs to mutate the graph must go through `cg update` (or a sibling subcommand under the same writer-lock discipline) — no ad-hoc writers.
- `UPDATE_IN_PROGRESS` (exit code 6) is a documented contract; callers can choose to retry, queue, or surface the message to the user.
- Read paths can be opened without write-intent flags, simplifying connection setup across consumers.
- If a write operation grows to need long-running schema migrations, the writer-lock duration becomes user-visible. Acceptable tradeoff; migrations are rare and pre-announced.

## Related

- [[wiki/plugins/lattice-graph/lattice-graph]]
- [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]]
- [[wiki/adrs/0002-explicit-graph-update-lifecycle]]
- [[wiki/adrs/0007-cli-first-code-graph]]
