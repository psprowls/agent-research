# Phase 59: Decouple graph-wiki-agent from `graph_io.cli` - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands
**Areas discussed:** Output formatting location, Formatter promotion scope, Test strategy, Error/exit-code mapping

---

## Output formatting location

The cg cli modules own the human-readable formatting (inline f-strings for the 6 describe modules; `graph_io.cli._format.render` for find). SC#1 forbids importing `graph_io.cli`; SC#3 wants output unchanged. Where should rendering live?

| Option | Description | Selected |
|--------|-------------|----------|
| Promote shared formatter into graph_io | Extract rendering into a public graph_io module imported by both cg and the agent. Single source, byte-identical, but expands phase to touch graph_io. | ✓ |
| Duplicate formatting in the agent | Reimplement the formatters inline in the agent's graph.py. Self-contained, graph_io untouched, but drift risk. | |
| Agent owns a new output format | Let the agent format records however reads best, relaxing SC#3's byte-identical bar. Cleanest code, but diverges from cg. | |

**User's choice:** Promote shared formatter into graph_io
**Notes:** Keystone decision — frames the whole approach and intentionally accepts a graph_io-package change.

---

## Formatter promotion scope

How far does the promotion go — refactor the cg cli modules to consume the new public formatter too?

| Option | Description | Selected |
|--------|-------------|----------|
| Refactor cg to use it too (true single source) | Move `_format.render` to public + extract the 6 describe formatters, then rewrite both cg cli modules and the agent to call the public funcs. No drift. Touches cg modules + tests; cg's tests guard output parity. | ✓ |
| Add public formatters, leave cg as-is | Create the public formatter for the agent only; don't touch cg's inline prints. Smaller blast radius, but describe formatting lives in two places and must be kept identical by hand. | |

**User's choice:** Refactor cg to use it too (true single source)
**Notes:** Chose single source of truth over minimal blast radius.

---

## Test strategy

Existing graph.py tests mock cli-module dispatch and assert the argparse.Namespace shape — they test the mechanism being deleted. How to replace them to verify SC#3?

| Option | Description | Selected |
|--------|-------------|----------|
| Seed a real graph DB + snapshot output | Build a fixture graph DB, run each subcommand, snapshot human output + exit codes. Real end-to-end verification incl. formatting; heavier setup. | ✓ |
| Mock the typed functions | Patch queries.* / update.run, assert call args + exit-code mapping. Light/fast, but no real formatting verification. | |
| Hybrid | Seed-DB snapshots for happy path + mocks for awkward error branches. | |

**User's choice:** Seed a real graph DB + snapshot output
**Notes:** During scout, found the agent already has a session-scoped `seeded_graph_conn` fixture (`tests/conftest.py:95`) building a real `code.db` from `sample_monorepo` via `update.run(..., full=True)` — infra effectively in place. Awkward error branches may still use mocks (folded into CONTEXT D-09).

---

## Error/exit-code mapping

cg modules map errors to specific exit codes and `update.run` raises instead of returning a code. How to structure the agent's reproduction of that contract?

| Option | Description | Selected |
|--------|-------------|----------|
| Shared connect+map helper | One agent helper opens read_only_connect, catches graph_io exceptions, maps to graph_io.exit_codes; reused by all describe + query commands. Mirrors scan.py. | ✓ |
| Inline per command | Each command does its own connect / try-except / exit-code translation inline. More verbose but linear to read. | |

**User's choice:** Shared connect+map helper
**Notes:** `graph build` wraps `update.run` separately with its own exception→code mapping (it raises rather than returning an int).

---

## Claude's Discretion

- Exact public module name/location for the promoted formatter (constraint: public, not under `graph_io.cli`).
- Internal structure/location of the shared connect+map helper in the agent package.
- Which describe error branches use snapshot vs. mock.

## Deferred Ideas

- Whether to keep the `cg` CLI as a human-facing debug surface — carried from the ROADMAP out-of-scope note; later decision.
- 3 phase-matched todos (entity `## Related` from edges, entity-summary Obsidian fix, test-suite fan-out in index) — all wiki-io entity/index work, reviewed and not folded (out of scope for this CLI decoupling).
