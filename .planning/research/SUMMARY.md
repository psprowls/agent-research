# Project Research Summary

**Project:** agent-research — v1.7 graph-io Integration & Wiki Hygiene
**Domain:** Wiring an existing SQLite code-graph store (graph-io) into an existing AWS Bedrock LangChain agent (graph-wiki-agent)
**Researched:** 2026-05-26
**Confidence:** HIGH

## Executive Summary

v1.7 is an integration milestone, not a greenfield build. v1.6 delivered a full graph-io ontology (schema v2 + URI identity, 25 `cg` subcommands, structural containment tree, domains, entry points, test suites) with zero agent consumers wired. v1.7's job is to close that gap: make graph-io the agent's identity layer for librarian grounding, scanner page routing, and ingestor existence checks, while also exposing graph operations through a new `graph-wiki-agent graph` subcommand. All four research threads converged on the same top-level conclusion: **hygiene must land first**, then integration builds on the clean foundation. The file-touch overlap between hygiene tasks and integration targets (`commands/scan.py`, `wiki-io` templates) is concrete — doing them interleaved produces merge conflicts and silent reversions.

The recommended approach requires no new runtime dependencies. `graph-io` is already a workspace member; adding it as an explicit dep of `graph-wiki-agent` is the only `pyproject.toml` change. The `langchain-core @tool` decorator, `workspace_io.paths.graph_dir()`, and `graph_io.store.read_only_connect()` are all already in-repo. Tool wrappers live in the agent layer (`graph_tools.py`) not in `packages/graph-io` — preserving the clean library/agent tier separation. The `graph-wiki-agent graph` subcommand follows the established `ingest_app` sub-Typer pattern exactly, limited to 3 verbs (`build`, `describe`, `query`). In-process Python imports replace any shell-out temptation.

The primary risks are: (1) overexposing graph-io queries as too many `@tool` callables, degrading librarian tool-routing quality — hard cap at 5 tools; (2) tools returning raw dataclasses or large row sets, causing Bedrock `ValidationException` or context overflow — all tools return `-> str` with a 50-row cap using `_format.render()`; (3) interleaving hygiene with integration, causing scan.py merge conflicts. One item requires a scoping action: `260521-ans` is already resolved (the `NO_COLOR=1 TERM=dumb` env-injection pattern is in place and all targeted tests pass), so it should be closed as already-done at scoping rather than executed as a phase task.

## Key Findings

### Recommended Stack

No new runtime packages are required for v1.7's core work. The one required dependency change is adding `graph-io` as an explicit workspace member dep in `agents/graph-wiki-agent/pyproject.toml`. A floor bump from `langchain-aws>=1.4.6` to `>=1.4.7` is warranted because 1.4.7 added the strip-invalid-`tool_use`-block fix, which is directly relevant to the multi-tool librarian fan-out this milestone introduces. An optional bump to `typer>=0.26.0` (released 2026-05-26, vendored Click) eliminates a future dependency conflict vector with zero breakage risk.

**Core technologies:**
- `graph_io.queries` (in-repo): pure Python query API — consumed via in-process import, never shell-out to `cg`
- `graph_io.store.read_only_connect()` (in-repo): the only connection factory the agent layer should use; opened once per command at entry, shared by all tool closures, closed in `finally`
- `graph_io.cli._format.render(records, fmt="human")` (in-repo): existing human-column formatter; the correct return serializer for all `@tool` callables — avoids raw dataclass or JSON return pitfalls
- `langchain_core.tools.@tool` (existing dep): wraps any Python callable; sufficient for all graph-io tool wrappers — no `StructuredTool` or `BaseTool` subclassing needed
- `workspace_io.paths.graph_dir(workspace)` (existing dep): canonical DB path resolver — must be used everywhere; hardcoding DB paths is an explicit anti-pattern
- `langchain-aws>=1.4.7` (bump): strip-invalid-`tool_use`-block fix is load-bearing for multi-tool librarian

**New modules only (no new packages):**
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` (~120 LOC): `@tool` wrappers over `graph_io.queries.*`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` (~150 LOC): `graph build/describe/query` implementations

### Expected Features

**Must have (table stakes for v1.7 to deliver its stated goal):**
- Librarian grounding tools — 5 `@tool` callables wrapping `graph_io.queries.*`; librarian system prompt updated; `bind_tools()` wired in `commands/query.py`
- Scanner consumes graph-io — URI-keyed vault page routing; fallback to path-keyed logic when graph not initialized
- Ingestor consumes graph-io — graph as authoritative manifest with graceful `NOT_INITIALIZED` error (clear error, not silent fallback)
- `cg find` parser ergonomics — `--name` named flag added; `cg find --name foo.py --kind file` works; single-commit break-and-fix
- Hygiene burn-down — all 10 quick tasks + 2 bootstrap todos applied before integration phases touch overlapping files

**Should have (differentiator, v1.7 stretch):**
- `graph-wiki-agent graph` subcommand (`build`, `describe`, `query`) with cost-tracked trace records — adds agent-awareness to graph operations; `cg` CLI continues to work for raw inspection

**Defer (v1.8+):**
- URI-keyed wiki redesign (flat-by-ID / by-domain / by-repo views)
- Scanner 9-stage pipeline restructure (ONTOLOGY-SPEC §9)
- URI reconciliation for orphaned pages on package rename
- Plugin wiring to graph-io (only `kxi` docs fix touches `plugins/` in v1.7)

**Already done — close at scoping, do NOT execute:**
- `260521-ans` (ANSI strip): the `NO_COLOR=1 TERM=dumb COLUMNS=200` env-injection pattern is already in production across three test files; 3/3 targeted tests pass today. Close as already-resolved at requirements/scoping.

### Architecture Approach

The architecture is additive: two new files (`graph_tools.py`, `commands/graph.py`), targeted modifications to five existing command files, and a hygiene sweep across `wiki-io` templates and `workspace-io`. The key structural decision — confirmed by all four researchers independently — is that `@tool` wrappers live in the agent layer, not in `packages/graph-io`. The existing `@tool read_file` in `commands/query.py` is the precedent. `graph_tools.py` follows the same philosophy but factored out because the tool set is larger (5 tools vs 1). The `graph` subcommand mirrors the established `ingest_app` sub-Typer pattern exactly.

**Major components and their v1.7 changes:**
1. `graph_tools.py` (NEW) — `build_graph_tools(conn)` factory returns ≤5 `@tool` callables; connection passed via closure; all return `-> str` using `_format.render()`
2. `commands/query.py` (MODIFIED) — opens `read_only_connect()` at command entry, calls `build_graph_tools(conn)`, `.bind_tools(tools)` on librarian LLM; conn closed in `finally`
3. `commands/scan.py` (MODIFIED) — calls `cg update` (incremental) before fan-out; derives vault page slug from graph URI; graceful degradation when `NOT_INITIALIZED`
4. `commands/ingest.py` (MODIFIED) — checks graph for canonical entity existence; clear error on `NOT_INITIALIZED`; documents URI-drift limitation (v1.8 reconciliation)
5. `commands/graph.py` (NEW) — thin wrappers; only additions over `cg` semantics are `--trace` and `--model`; 3 verbs maximum
6. `wiki-io` templates (MODIFIED) — hygiene tasks `i26`, `he3`, `i35` fix `{{CONTAINER_DIR}}`, file-map format, and testing.md subpage; must land before scanner integration
7. `workspace-io` (MODIFIED) — `gc0` (4 lint fixes) and `lj3` (sparse plugins tolerance); must land before integration calls `graph_dir()`

### Critical Pitfalls

1. **Over-exposed `@tool` surface degrades librarian routing** — Bedrock Converse shows measurable quality degradation above ~10 tools. The 15+ distinct `queries.py` query shapes must be collapsed to ≤5 broader callables grouped by concern. Design the tool surface before writing any implementation. If the count exceeds 6, redesign is required before proceeding.

2. **Tools returning non-string types cause Bedrock `ValidationException`** — all `@tool` callables must declare `-> str` and serialize all graph-io records before returning. Never return dataclasses, Pydantic models, or lists. Use `_format.render(records, fmt="human")`. Hard-cap list results at 50 rows with a truncation notice.

3. **Hygiene interleaved with integration causes `scan.py` merge conflicts** — `hfr` (wikilink prefix), `iws` (page routing), and scanner graph-io integration all touch `commands/scan.py`. `i26`/`he3` fix templates the scanner immediately uses. Hygiene must be a dedicated phase that merges before any integration work starts.

4. **Opening a new graph-io connection per tool call** — during a single `run_query()` the librarian may invoke 3-5 tools per page across up to 10 pages (up to 50 SQLite file opens). Use `build_graph_tools(conn)` to close over a single connection opened at command entry and closed in `finally`.

5. **`cg find` positional removal silently breaks internal test callers** — when converting the positional `name` to `--name`, grep all `main(["find", "foo.py"])` callsites in `packages/graph-io/tests/`. Fix callers in the same commit. Smoke test: `cg find --name SubagentPool --kind class` must exit 0 or 1, not 2.

6. **Feature drift between `graph-wiki-agent graph` and `cg`** — the agent subcommand must be a thin wrapper. No new flags beyond `--trace` and `--model`. Enforce this constraint in the phase plan before implementation, not at code review.

## Implications for Roadmap

Phases start at Phase 35. All four researchers converged on hygiene-first ordering. The file-touch overlap evidence is concrete and documented in ARCHITECTURE.md's hygiene/integration overlap table. This is the recommended sequence:

### Phase 35: Wiki & Bootstrap Hygiene Burn-Down

**Rationale:** All 10 deferred quick tasks + 2 bootstrap todos must land before integration because `hfr`/`iws` touch `commands/scan.py` (same file as scanner integration), `i26`/`he3`/`i35` fix templates the scanner immediately uses, and `gc0`/`lj3` fix `workspace-io` that graph-io integration calls. A file-touch matrix must be produced before plan wave assignment — tasks that share a file must be in the same plan or in sequentially-ordered plans. Note: `hfr` must precede `i26` (both touch `package/overview.md`); `iws` must precede scanner integration.

**Delivers:** Zero broken template wikilinks, ANSI-clean test output, sparse-plugins tolerance, self-healing uv re-exec, overview page naming fixed, file-map format correct, bootstrap stubs working. `260521-ans` closed as already-done (no execution).
**Addresses:** `hfr`, `i26`, `he3`, `i35`, `iws`, `kxi`, `gc0`, `lj3`, `mfm`, bootstrap interactive flag, bootstrap stub category indexes; close `260521-ans` as already-resolved
**Avoids:** Pitfall 3 (scan.py merge conflicts), Pitfall 7 (hygiene file-touch ordering regressions), Pitfall 8 (wiki-io template changes break plugin without verification)
**Research flag:** SKIP — all tasks have pre-written PLANs; patterns are established

### Phase 36: `cg find` Parser Ergonomics

**Rationale:** Small, self-contained, touches only `packages/graph-io/cli/q_find.py`. Landing it before librarian grounding tools means `@tool` callers can use `--name` / `--kind` keyword style from the start. Single-commit break-and-fix: the old positional form `cg find foo.py` should produce a clear parse error (not silent wrong behavior) after the change.

**Delivers:** `cg find --name foo.py --kind file` works; `cg find foo.py` produces clear parse error; all internal callers updated; smoke test passes
**Addresses:** `cg find` ergonomics fix (target feature 5)
**Avoids:** Pitfall 5 (silently broken internal test callers)
**Research flag:** SKIP — fix shape fully specified in ARCHITECTURE.md; 5-10 line change with known pattern

### Phase 37: Librarian Grounding Tools

**Rationale:** Read-only, side-effect-free, lower risk than scanner/ingestor. Validates the `build_graph_tools(conn)` / `bind_tools()` pattern before any page-writing changes. The `@tool` callable surface (count and shape) is the critical design decision for this phase — must be locked before writing any implementation. CountTokens validation of effective context budget (system prompt + tool schemas + input) is a required verification step before shipping.

**Delivers:** `graph_tools.py` with ≤5 `@tool` callables; `commands/query.py` wired with `bind_tools()`; librarian system prompt updated; CountTokens validation; unit tests with mocked `conn`
**Addresses:** Librarian grounding tools (target feature 1)
**Avoids:** Pitfall 1 (over-exposed tool surface), Pitfall 2 (result payload overflow), Pitfall 3 (non-string return types), Pitfall 4 (per-tool connection open), Pitfall 14 (token budget regression from tool schemas)
**Open question for phase scoping:** The exact grouping of the 5 librarian tools is a design choice — research caps the COUNT but not the SHAPE. Decide at scoping.
**Research flag:** SKIP — tool wrapper pattern, `build_graph_tools(conn)` factory shape, and `_format.render()` as return serializer are all fully specified

### Phase 38: `graph-wiki-agent graph` Subcommand

**Rationale:** Can proceed in parallel with Phase 37 (different files). Depends only on hygiene being done. The critical constraint is thin-wrapper-only: no new flags beyond `--trace` and `--model`. The `ingest_app` sub-Typer pattern is the exact template. MCP exposure uses `graph_` prefix (parallel to existing `wiki_` prefix tools in `server.py`).

**Delivers:** `graph-wiki-agent graph build|describe|query` CLI; `graph_build`, `graph_describe`, `graph_query` MCP tools in `server.py`; cost-tracked trace record for `graph build`; `graph-wiki-agent graph --help` exits 0 listing 3 subcommands
**Addresses:** `graph-wiki-agent graph` subcommand (target feature 4)
**Avoids:** Pitfall 6 (feature drift between `graph-wiki-agent graph` and `cg`), Pitfall 13 (Typer subcommand name collision)
**Research flag:** SKIP — Typer sub-app pattern is established; `ingest_app` is the template; 3-verb surface fully specified

### Phase 39: Scanner Consumes graph-io

**Rationale:** Scanner integration is higher risk than librarian tools because it changes page-writing logic. Must come after hygiene (`hfr`/`iws` both touch `run_scan()`). `run_scan()` must call `cg update` (incremental) before fan-out — this is a hard requirement for URI freshness on every scan. The Phase 14 SC#4 plugin smoke transcript (carried since v1.2) must be captured at phase close as the regression baseline.

**Delivers:** Scanner derives vault page slug from graph URI; graceful degradation when `NOT_INITIALIZED`; `run_scan()` calls `cg update` before fan-out; before/after live vault smoke sample committed; SC#4 transcript captured
**Addresses:** Scanner consumes graph-io (target feature 2)
**Avoids:** Pitfall 4 (per-command vs per-tool connection), Pitfall 11 (stale graph on first scan), Pitfall 8 (template changes break plugin)
**Research flag:** SKIP — integration pattern and connection-lifetime contract fully specified in ARCHITECTURE.md

### Phase 40: Ingestor Consumes graph-io

**Rationale:** Goes last because it changes page-writing logic based on graph existence checks. Placing it after scanner ensures URI-keyed slugs are consistent. The URI-drift / orphaned-page limitation must be explicitly documented in the phase plan (v1.8 reconciliation path), not solved in v1.7.

**Delivers:** `run_ingest_source()` checks graph for canonical entity existence; clear error on `NOT_INITIALIZED`; URI-drift limitation documented; unit tests with mocked `conn`
**Addresses:** Ingestor consumes graph-io (target feature 3)
**Avoids:** Pitfall 12 (URI identity drift on package rename — document, don't solve in v1.7)
**Research flag:** SKIP — integration pattern mirrors scanner; authoritative-manifest-with-graceful-degradation approach specified

### Phase Ordering Rationale

- **Hygiene first** is the unanimous conclusion across all four research files, backed by concrete file-touch overlap evidence. `commands/scan.py` is touched by `hfr`, `iws`, AND scanner graph-io integration. `wiki-io` templates are touched by `i26`/`he3`/`i35` AND consumed immediately by scanner integration output.
- **`cg find` ergonomics second** because it is trivial, standalone, and unblocks `@tool` callers that always use keyword-style invocation.
- **Librarian grounding tools before scanner/ingestor** because it is read-only and validates the `build_graph_tools` / `bind_tools` pattern without page-writing risk.
- **`graph` subcommand** can be parallelized with Phase 37 — it touches different files; shown as Phase 38 for simplicity, not as a sequencing constraint.
- **Scanner before ingestor** because URI-keyed page routing (scanner) must be established before ingestor's existence-check diff is meaningful.

### Research Flags

Phases needing deeper research during planning: **NONE.** All four researchers worked from direct codebase inspection. Patterns are fully specified, precedents exist in-repo, implementation shapes are documented.

Phases with standard patterns (skip research-phase):
- **Phase 35 (Hygiene):** Pre-written PLANs exist for all 10 quick tasks; execute as written
- **Phase 36 (`cg find`):** Fix shape fully specified; 5-10 line change
- **Phase 37 (Librarian tools):** `build_graph_tools(conn)` pattern, tool count cap, return format all specified; open question on tool grouping is a scoping decision, not a research gap
- **Phase 38 (`graph` subcommand):** `ingest_app` sub-Typer is the exact template; 3-verb surface fully specified
- **Phase 39 (Scanner):** Integration pattern and connection-lifetime contract documented
- **Phase 40 (Ingestor):** Mirrors scanner; authoritative-manifest approach specified

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All decisions verified against installed packages, live codebase, and PyPI; no new packages needed |
| Features | HIGH | Derived from direct codebase inspection of `queries.py`, `scan.py`, `ingest.py`, `librarian.py`, and all 10 quick-task PLANs |
| Architecture | HIGH | Full codebase inspection; `build_graph_tools(conn)` pattern, connection lifetime, sub-Typer shape, and file-touch matrix all verified against live code |
| Pitfalls | HIGH | Grounded in existing codebase (RETROSPECTIVE.md, live test runs, argparse source inspection); no speculative pitfalls |

**Overall confidence:** HIGH

### Gaps to Address

- **Exact grouping of the 5 librarian tools is a design decision for phase scoping** — research establishes the count ceiling (≤5) and the return format (`_format.render()` + 50-row cap + `-> str`) but does not prescribe which specific `queries.py` functions become tools or how they are grouped. The roadmapper should flag Phase 37 scoping as requiring this decision before implementation starts.

- **`260521-ans` scoping action** — this item appears in the deferred quick tasks list with a pre-written PLAN, but the task is already done (tests pass with the existing `NO_COLOR=1` pattern). The requirements step must close it as already-resolved. Confirm by running the 3 tests listed in the PLAN before closing.

- **Phase 14 SC#4 plugin smoke transcript** — carried since v1.2 close; must be captured at end of Phase 39 (scanner integration) as the regression baseline for the plugin end-to-end happy path. Flag as a success criterion for Phase 39.

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `packages/graph-io/src/graph_io/queries.py` — full query API surface confirmed
- `packages/graph-io/src/graph_io/store.py` — `read_only_connect()`, `GraphNotInitializedError` confirmed
- `packages/graph-io/src/graph_io/cli/_format.py` — `render(records, fmt)` confirmed importable independently of CLI
- `packages/graph-io/src/graph_io/cli/q_find.py` — positional-only `name` arg confirmed; ergonomics fix shape specified
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — `ingest_app` sub-Typer pattern confirmed
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — `@tool read_file` agent-local precedent confirmed
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — `run_scan()` structure; hygiene overlap surface confirmed
- `agents/graph-wiki-agent/tests/unit/test_cli_help.py` — `_PLAIN_HELP_ENV` pattern; 3/3 ANSI tests passing confirmed on live run
- `.planning/STATE.md` — 10 deferred quick task IDs; `260521-ans` confirmed already passing
- `.planning/PROJECT.md` — v1.7 scope, Phase 35 numbering, plugin boundary constraints
- `.planning/quick/260521-*/` and `.planning/quick/260523-*/` — all 10 quick task PLANs confirmed written

### Primary (HIGH confidence — PyPI + release notes)
- PyPI `langchain-aws` 1.4.7 — strip-invalid-`tool_use`-block fix confirmed; no breaking changes to `ChatBedrockConverse`
- PyPI `typer` 0.26.0 — vendored Click; `add_typer` / `@app.command` unchanged; no breakage for this codebase
- PyPI `langchain-core` 1.4.0, `mcp` 1.27.1 — both at current stable; no changes needed

---
*Research completed: 2026-05-26*
*Ready for roadmap: yes*
