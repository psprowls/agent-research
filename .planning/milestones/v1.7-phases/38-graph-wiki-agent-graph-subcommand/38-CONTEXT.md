# Phase 38: `graph-wiki-agent graph` Subcommand - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose `cg` graph operations as a first-class agent-CLI subcommand group (`graph-wiki-agent graph build|describe|query`) and as three MCP tools (`graph_build`, `graph_describe`, `graph_query`) in `graph-wiki-mcp`. Wire `--trace` (cost-tracked JSONL) and `--model` (model override for `graph build`) as the only two agent-specific flags beyond `cg`'s own surface. Calls happen in-process — the agent imports `graph_io.cli.ops_update.run()` / `q_find.run()` / `q_describe_*.run()` and dispatches to them with a manually-constructed `argparse.Namespace`.

Out of scope: mirroring all 25 `cg` subcommands (curated 3-verb surface only); new MCP tools beyond the locked three; changes to existing `wiki_*` MCP tools; trace renderer changes (Phase 9's renderer at `cli.py:282` already handles the schema this phase writes); Phase 37's librarian tool surface (`cg_*` prefix, different namespace).

</domain>

<decisions>
## Implementation Decisions

### Trace JSONL Shape & Location

- **D-01: One file per invocation, ISO-timestamp filename.** Trace files land in `.graph-wiki/traces/` named `<ISO8601-Z>-<command>.jsonl` (e.g. `2026-05-26T17-03-22Z-graph-build.jsonl`). Each invocation writes its own file; no append.
  - **Why:** Easy to find a specific run's trace; can be listed by mtime; atomic write per invocation; existing `graph-wiki-agent trace <file>` command at `cli.py:282` already takes a single file. No rotation policy needed.
  - **Implementation:** Adapter constructs the filename at command entry; opens the file in `"w"` mode; passes a writer callback to the in-process call site.

- **D-02: Reuse existing Phase 9 (OBS-04) trace schema with new `event` kinds.** Records carry `schema_version`, `timestamp`, `role`, `model_id` (when applicable), and an `event` field. Phase 38 adds new `event` values: `graph_build_start`, `graph_build_complete`, `graph_describe`, `graph_query`. No schema_version bump.
  - **Why:** Existing `trace` renderer (`cli.py:282-...`) already handles the schema and gracefully ignores unknown `event` values (lenient consumer per OBS-04 D-03). Reusing the schema means Phase 38 traces show up alongside agent-loop traces with no renderer changes.
  - **`graph_build` records:** Include `command`, `args` (echo), `exit_code`, `duration_ms`. If `--model` was set, include `model_id` plus token/cost fields when the model actually runs (research item for planner: clarify whether `ops_update.run()` even invokes an LLM — if not, model-related fields are omitted).

- **D-03: Proxy commands emit a single trace record with no cost fields.** `graph describe` and `graph query` are pure proxies to `cg describe-*` / `cg find` with no LLM calls. When `--trace` is set, they write one record per invocation: `event=graph_describe` or `event=graph_query`, with `timestamp`, `command`, `args`, `exit_code`, `duration_ms`, `row_count`. **No `model_id`, no `total_tokens`, no `cost_usd`** — those fields are OMITTED (not set to null/zero) to avoid implying that cost-tracking happened when it didn't.
  - **Why:** Avoids misleading downstream tooling that reads cost fields and assumes a model was invoked. Keeps the record honest. Schema is forward-compatible: a future phase that adds cost-tracking to proxy commands can add the fields without breaking readers.

### MCP Tool Input Shapes

- **D-04: MCP tools mirror CLI args 1:1.** Each tool accepts the same flags as its CLI counterpart:
  - `graph_build(full: bool = False, trace: bool = False, model: str | None = None)`
  - `graph_describe(kind: str, identifier: str | None = None)` — multiplexed (see D-09)
  - `graph_query(name: str | None = None, kind: str | None = None, in_package: str | None = None)` — mirrors Phase 36 `cg find`
  - **Why:** Single mental model — MCP tool call == CLI invocation. Existing `wiki_*` tools follow the same pattern. The DeepAgents host doesn't need to learn two different surfaces.
  - **Auth/workspace:** MCP tools resolve `workspace` from server context (same as existing `wiki_*` tools), not from the tool input.

- **D-05: Exactly 3 MCP tools, named per SC#4.** `graph_build`, `graph_describe`, `graph_query` — locked by ROADMAP. All three appear in `wiki_ping` server discovery output. No `graph_describe_package` / `graph_describe_path` per-kind splits at the MCP layer.
  - **Why:** SC#4 literally requires exactly 3 tools with these names. Multiplexing `graph_describe` via `kind` (D-09) keeps the surface at 3 while still covering all 6 describe operations.

### Call Mechanism

- **D-06: In-process import.** The agent's `graph` Typer command imports `graph_io.cli.ops_update.run`, `graph_io.cli.q_find.run`, and the 6 `graph_io.cli.q_describe_*.run` functions directly and invokes them. No subprocess. Same approach for `graph_describe` / `graph_query`.
  - **Why:** Zero subprocess overhead (~50ms saved per call); trivial to wrap with `--trace` JSONL emission (capture exit code, duration, output before/after the call); full type safety. The agent already depends on `graph-io` as a workspace dep, so the coupling is already paid for.
  - **What it does NOT do:** Does not require `cg` to be on `PATH`; does not parse stderr/stdout. Pure Python call.

- **D-07: Build `argparse.Namespace` manually in the agent adapter.** The Typer command constructs `argparse.Namespace(repo=..., workspace=..., full=..., fmt='human', mode='workspace', _module=ops_update, _parser=...)` and passes it to `ops_update.run(args)`. Skip cg's parser entirely.
  - **Why:** Clean separation between Typer (agent's surface) and argparse (cg's surface). Agent doesn't reparse what the user already typed. If cg adds a new required arg, tests in Phase 38 catch the breakage.
  - **What it does NOT do:** Does not require a refactor of `graph-io` to expose a programmatic API. Deferred (see deferred ideas) until/unless a second consumer needs the same pattern.
  - **Implementation note:** Planner should put the Namespace-construction helpers in a single module (suggest `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` co-located with the Typer command), so when cg's args change, all three callers are in one file.

### `graph describe` Argument Shape

- **D-08: CLI uses per-kind Typer sub-sub-commands.** Surface:
  - `graph describe package <name>`
  - `graph describe path <path>`
  - `graph describe repository`
  - `graph describe domain <name>`
  - `graph describe entry-point <name>`
  - `graph describe test-suite <name>`
  - **Why:** Cleanest Typer ergonomics; `--help` shows the 6 kinds explicitly; per-kind type safety via Typer's per-command arg parsing. Humans typing `graph describe package foo` is more natural than `graph describe --kind=package --identifier=foo`.
  - **SC#1 compliance:** `graph-wiki-agent graph --help` still shows exactly the 3 subcommands (`build`, `describe`, `query`) — the 6 describe kinds are revealed by `graph describe --help`, which is a distinct help surface.

- **D-09: MCP uses multiplexed `graph_describe(kind, identifier)`.** Single MCP tool with two args: `kind` (enum, same 6 values as the CLI sub-sub-commands), `identifier` (optional for `repository`; required for the rest).
  - **Why:** SC#4 mandates exactly 3 MCP tools. Multiplexing is the only way to cover all 6 describe operations within the 3-tool budget. Matches Phase 37 D-02 `cg_describe` librarian shape — LLMs see the same multiplexed surface whether routed through the librarian's `cg_*` tools or the MCP `graph_*` tools.
  - **Cross-surface acknowledgement:** CLI optimizes for human ergonomics (sub-sub-commands); MCP optimizes for LLM schema simplicity (multiplexed). These two optimizations are deliberately different — same data, different ergonomics.

### Claude's Discretion

- Exact ISO timestamp format for the trace filename (planner picks; suggest `YYYY-MM-DDTHH-MM-SSZ` with `-` instead of `:` for filesystem safety).
- Whether `graph build`'s `--model` flag accepts arbitrary strings or validates against a known list — planner picks (consult `models.toml` for the role list).
- Exact `event` value strings for the 4+ new event kinds (D-02) — planner picks; just be consistent with the existing Phase 9 event names.
- Where the Namespace-builder helpers live (suggested: `commands/graph.py` alongside the Typer command).
- How errors from `ops_update.run()` (non-zero exit codes) surface back through Typer — `typer.Exit(code=N)` likely, but planner reviews.
- MCP error response shape when `graph_build` is called against a workspace with no graph-io DB — existing `wiki_*` tools have a precedent (planner reviews `wiki_query`'s error handling).

### Folded Todos

None. No todos match Phase 38's `graph` subcommand scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/REQUIREMENTS.md` (GRAPHCMD-01..04 section) — four locked requirements
- `.planning/ROADMAP.md` (Phase 38 section) — phase goal + 4 success criteria (SC#1 graph --help shows 3 subs; SC#2 build flags = --trace + --model only; SC#3 mirrors cg semantics + cost-tracked trace; SC#4 exactly 3 MCP tools graph_build/describe/query)

### Cross-Phase Coupling
- `.planning/phases/37-librarian-grounding-tools/37-CONTEXT.md` — Phase 37 D-01/D-02 lock `cg_*` prefix and `cg_describe(kind, identifier)` for librarian tools. Phase 38 uses `graph_*` for MCP and multiplexed `graph_describe(kind, identifier)` for MCP (D-09) — same multiplexing decision, parallel prefix namespaces. Phase 38 is NOT blocked by Phase 37 (different files; SC #2 of ROADMAP says they can run in parallel).
- `.planning/phases/36-cg-find-parser-ergonomics/36-CONTEXT.md` — `graph_query` mirrors Phase 36's `cg find` shape (named flags, AND combination, case-insensitive package match). Phase 36 is merged.

### Target Files (Net-New)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — NEW; Typer subapp with `build`, `describe` (nested subapp with 6 kinds), `query` commands + the Namespace-builder helpers (D-07)

### Target Files (Modified)
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — add `app.add_typer(graph_app, name="graph")` (parallel to existing `ingest` subapp at line 561)
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` — register 3 new MCP tools (`graph_build`, `graph_describe`, `graph_query`) with Pydantic Input/Output models (mirror the `wiki_query`/`wiki_scan` patterns at lines 117-189, 240-294)

### Read-Only References (Don't Edit)
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:561` — existing `ingest` subapp; pattern template for nested Typer command groups
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:282` — existing `trace` command; renders the JSONL Phase 38 writes (don't modify; just write compatible records)
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py:117-294` — existing `wiki_*` MCP tools; pattern template for Pydantic Input/Output models + workspace resolution + error handling
- `packages/graph-io/src/graph_io/cli/main.py:39-65` — `_SUBCOMMANDS` dict mapping cg subcommand name → module; reference for which modules to import in `commands/graph.py`
- `packages/graph-io/src/graph_io/cli/ops_update.py` — `add_arguments()` + `run(args)` for `cg update`; the Namespace constructed in D-07 must satisfy `add_arguments`'s expectations
- `packages/graph-io/src/graph_io/cli/q_find.py` — Phase 36 just refactored this; `add_arguments()` accepts `--name`/`--kind`/`--in-package`; `run(args)` consumes `args.name`/`args.kind`/`args.in_package`
- `packages/graph-io/src/graph_io/cli/q_describe_*.py` (6 files) — one per kind; each has `add_arguments` + `run(args)`. Phase 38 imports all 6 and dispatches based on the user-specified kind.

### Trace Schema Reference
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:92-275` — `_render_trace_record`, `_aggregate_trace`, `_render_collapsed_group`, `_is_groupable`. These functions implicitly define the trace schema (schema_version, role, model_id, event, content). Phase 38's records must satisfy this shape.
- `KNOWN_SCHEMA_VERSION` constant in `cli.py` — current max known schema version; Phase 38 does NOT bump it (D-02 says reuse).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app.add_typer(ingest_app, name="ingest")` at `cli.py:561` — the existing template for nested Typer subapps. Phase 38's `graph_app` follows the same pattern.
- `wiki_*` MCP tools (`wiki_query` line 117, `wiki_log` line 169, `wiki_bootstrap` line 217, `wiki_scan` line 269, `wiki_ingest` line 327) — each has paired Pydantic `Input` / `Output` models, async tool function, and workspace resolution at server level. Phase 38's 3 `graph_*` tools follow the same shape.
- `trace` Typer command at `cli.py:282` — reads JSONL traces, lenient on schema_version, collapses consecutive same-role runs. Phase 38 writes traces this consumes for free.
- Phase 9 OBS-04 trace records' existing schema (schema_version, role, model_id, event, content) — Phase 38 extends with new `event` values, no schema bump.

### Established Patterns
- All in-process call sites in `commands/*.py` use `Namespace(...)` construction when delegating to cg — there's already precedent for D-07's pattern (planner: verify by reading `commands/scan.py` and `commands/ingest.py` for analog constructions).
- Per-Typer-command exit code surfacing: existing commands use `raise typer.Exit(code=N)` for non-zero exits. `graph build` follows the same.
- `_SUBCOMMANDS` dict at `cli/main.py:39-65` — the canonical map of cg subcommand name → module. Phase 38's `commands/graph.py` imports a subset of these modules directly.

### Integration Points
- `cli.py` → `commands/graph.py`: single `app.add_typer(graph_app, name="graph")` line — same pattern as `ingest`.
- `commands/graph.py` → `graph_io.cli.ops_update.run`: direct import + Namespace dispatch (D-06/D-07).
- `commands/graph.py` → `.graph-wiki/traces/<timestamp>-graph-build.jsonl`: trace writer at command entry, captured by closure, finalized in `finally`.
- `mcp/server.py` → `commands/graph.py`: each MCP tool calls into the same in-process functions (or a shared helper) that the CLI uses, so CLI and MCP semantics stay in lockstep.

</code_context>

<specifics>
## Specific Ideas

- D-01 trace filename suggestion: `f".graph-wiki/traces/{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%SZ')}-{command}.jsonl"` — colons are filesystem-unsafe on some platforms, so use `-` instead.
- D-08 sub-sub-command names should use kebab-case to match Typer convention (`entry-point`, `test-suite`) but the underlying `kind` arg passed to MCP D-09 should be snake_case (`entry_point`, `test_suite`) — matches Phase 37 D-10's enum exactly. Planner: do the case conversion at the Typer command boundary.
- For the in-process call (D-06), wrap each `module.run(args)` call in a `try`/`except SystemExit` since cg modules occasionally call `sys.exit()` directly. Catch and convert to `typer.Exit(code=exc.code)`.
- D-04's `graph_describe` MCP signature should validate `kind` via a Literal type or enum in the Pydantic Input model — surfaces the 6 valid kinds in the tool schema for the LLM.

</specifics>

<deferred>
## Deferred Ideas

- **Refactor `graph-io` to expose a programmatic `run_update(workspace, full=False)` helper** — Considered as an alternative to D-07's manual Namespace construction. Rejected for this phase to avoid cross-package scope creep. Revisit when a second consumer needs the same pattern (Phase 39 scanner might be that consumer, but it can also use D-07's manual-Namespace approach).
- **Mirror all 25 `cg` subcommands through `graph-wiki-agent graph`** — Out of scope per ROADMAP. The curated 3-verb surface (build/describe/query) is intentional; users who need niche subcommands can run `cg` directly.
- **MCP tool exposure of `--trace` and `--model` flags** — Decided to keep them (D-04 mirror CLI 1:1), but if a future MCP host pattern emerges where per-call trace/model is configured at the host level, the MCP signatures can drop those args without breaking the CLI surface.
- **Append-only / rolling trace files** — Considered (D-01 alternative); rejected for the simpler one-file-per-invocation model. Revisit only if disk pressure becomes a real concern (`.graph-wiki/traces/` may need a rotation policy later).
- **schema_version bump for graph events** — Considered (D-02 alternative); rejected to preserve compatibility with the existing renderer. If a future phase needs structural changes (e.g. dropping `role` for non-LLM events), bump then.
- **`--model` validation against `models.toml`** — Listed in Claude's Discretion. If validation is desired, planner adds it; otherwise pass-through to `make_llm()` which handles unknown models.

</deferred>

---

*Phase: 38-graph-wiki-agent-graph-subcommand*
*Context gathered: 2026-05-26*
