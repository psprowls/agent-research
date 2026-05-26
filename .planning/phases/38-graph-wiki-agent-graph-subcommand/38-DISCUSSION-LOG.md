# Phase 38: `graph-wiki-agent graph` Subcommand - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 38-graph-wiki-agent-graph-subcommand
**Areas discussed:** Trace JSONL shape & location, MCP tool input shapes, Call mechanism, `graph describe` arg shape

---

## Trace JSONL shape & location

### Q1: Filename / lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| One file per invocation, ISO-timestamp name | `.graph-wiki/traces/<ISO>-<cmd>.jsonl`. Existing `trace <file>` already takes single file. | ✓ |
| Append-only daily file | `.graph-wiki/traces/2026-05-26.jsonl`. Multi-run per file. | |
| Append-only single rolling file | One file forever; needs rotation. | |

**User's choice:** One file per invocation, ISO-timestamp (Recommended)

### Q2: Schema strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing schema; new `event` kinds | Phase 9 OBS-04 schema unchanged; add `graph_build_*`/`graph_describe`/`graph_query` events. | ✓ |
| Bump schema_version | Phase 38 introduces vN+1; renderer falls back to best-effort. | |
| Separate trace namespace | Write to `.graph-wiki/traces/graph/...` to separate from agentic traces. | |

**User's choice:** Reuse existing schema; new `event` kinds (Recommended)

### Q3: Proxy command trace records

| Option | Description | Selected |
|--------|-------------|----------|
| Single record per invocation, no cost fields | `describe`/`query` write one record without `model_id`/tokens/cost. | ✓ |
| Skip trace file for proxy commands | `--trace` on `describe`/`query` is a no-op. | |
| Same record shape, zero cost fields | Write `model_id=null, total_tokens=0`. Misleading. | |

**User's choice:** Single trace record, no cost fields (Recommended)

---

## MCP tool input shapes

### Q1: Input shape

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror CLI 1:1 | Each MCP tool accepts same flags as CLI counterpart. | ✓ |
| MCP simplified (drop --trace/--model) | Trace/model live at MCP host level. Diverges from CLI. | |
| MCP exposes trace/model as fixed config | Server reads from env/config at startup. | |

**User's choice:** Mirror CLI 1:1 (Recommended)

### Q2: Tool naming / count

| Option | Description | Selected |
|--------|-------------|----------|
| Three tools: graph_build / graph_describe / graph_query | Per SC#4. Multiplexed describe via kind enum. | ✓ |
| Five tools — split describe per kind | Mirrors cg per-subcommand. Violates SC#4. | |
| Three tools with generic dispatch | `graph_query({subcommand, args})`. LLM has to know cg internals. | |

**User's choice:** Three tools per SC#4 (Recommended)

---

## Call mechanism

### Q1: Subprocess vs in-process

| Option | Description | Selected |
|--------|-------------|----------|
| In-process: call `ops_update.run(args)` directly | Zero overhead; full trace control; coupling already paid for. | ✓ |
| Subprocess: `subprocess.run(["cg", "update", ...])` | Zero coupling; lossy trace data; PATH dependency. | |
| Mixed (in-process for fast ops, subprocess for build) | Two code paths. Hard to justify. | |

**User's choice:** In-process import (Recommended)

### Q2: How to construct CLI args for the in-process call

| Option | Description | Selected |
|--------|-------------|----------|
| Build Namespace manually in adapter | Typer creates Namespace, passes to module.run(args). | ✓ |
| Call `graph_io.cli.main.main(["update", ...])` | Reuse cg's parser. Risk of sys.exit() side-effects. | |
| Refactor cg to expose programmatic helper | Best long-term; cross-package scope. | |

**User's choice:** Build Namespace manually in adapter (Recommended)

---

## `graph describe` arg shape

### Q1: CLI shape

| Option | Description | Selected |
|--------|-------------|----------|
| Per-kind sub-sub-commands | `graph describe package <name>`, etc. — 6 Typer commands. SC#1-compatible. | ✓ |
| Multiplexed: `graph describe --kind=package --identifier=foo` | Matches librarian. Less ergonomic for humans. | |
| Positional kind + identifier | `graph describe package foo`. Single command with enum-validated kind. | |

**User's choice:** Per-kind sub-sub-commands (Recommended)

### Q2: MCP shape

| Option | Description | Selected |
|--------|-------------|----------|
| Multiplexed: `graph_describe(kind, identifier)` | One MCP tool. Matches Phase 37 D-02 librarian shape. Satisfies SC#4 (3 tools). | ✓ |
| Per-kind MCP tools | Violates SC#4 (would be 8 tools). | |
| Both surfaces multiplexed (drop CLI sub-sub-commands) | Single mental model across CLI+MCP. Loses Typer ergonomics. | |

**User's choice:** Multiplexed MCP, per-kind CLI (Recommended)
**Notes:** CLI optimizes for human ergonomics; MCP optimizes for LLM schema simplicity. Same data, deliberately different surfaces.

---

## Claude's Discretion

- Exact ISO timestamp format (suggest `YYYY-MM-DDTHH-MM-SSZ` with `-` not `:` for FS safety)
- `--model` arg validation (free-form vs models.toml-validated)
- Exact `event` value strings
- Helper module location (suggested: `commands/graph.py` alongside the Typer command)
- Error surfacing from `ops_update.run()` (`typer.Exit(code=N)` likely)
- MCP error response shape for no-graph-io-DB case (mirror existing `wiki_*` precedent)

## Deferred Ideas

- Refactor `graph-io` to expose programmatic `run_update()` helper — defer until second consumer needs it
- Mirror all 25 cg subcommands — out of scope per ROADMAP
- MCP drops --trace / --model — kept for parity; revisit if host-level pattern emerges
- Append-only / rolling trace files — revisit on disk pressure
- schema_version bump — defer until structural changes needed
- `--model` validation against models.toml — planner's call
