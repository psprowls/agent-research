# Requirements: agent-research — Milestone v1.7 (graph-io Integration & Wiki Hygiene)

**Status:** 🚧 ACTIVE — defined 2026-05-26
**Core Value:** Faithfully reproduce the graph-wiki plugin's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Milestone Goal:** Wire `graph-io` into `graph-wiki-agent` as the source of truth for librarian/scanner/ingestor, expose graph operations through a new `graph-wiki-agent graph` subcommand, fix `cg find` parser ergonomics, and burn down accumulated wiki/bootstrap/test-infra debt — so v1.7 closes with the agent actually using the ontology v1.6 built.

**Research:** `.planning/research/SUMMARY.md` (consolidates STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md)

---

## v1.7 Requirements

### HYGIENE — Wiki & Bootstrap Burn-Down

- [ ] **HYGIENE-01** — Scanner emits `[[wiki/<container>/...]]`-prefixed wikilinks in package overview / context / domain overview templates; zero broken links on freshly-bootstrapped + scanned wiki (`260521-hfr`)
- [ ] **HYGIENE-02** — `init_vault` creates stub `index.md` files in 4 missing section dirs (`concepts`, `sources`, `adrs`, `architecture`); zero broken `## More` links on fresh wiki (`260521-hfr` Task 2)
- [ ] **HYGIENE-03** — `{{CONTAINER_DIR}}` template variable wired into `package/overview.md`; scanner agent docs updated so non-`packages/` containers (agents, plugins) emit correct paths (`260521-i26`)
- [ ] **HYGIENE-04** — File-map format on package/app overview pages revised per spec (`260523-he3`)
- [ ] **HYGIENE-05** — `testing.md` subpage added to app/package templates (`260523-i35`)
- [ ] **HYGIENE-06** — Overview pages renamed per convention (`260523-iws`)
- [ ] **HYGIENE-07** — `workspace_io.config.resolve()` respects `repo-directory:` in workspace manifest when `GRAPH_WIKI_WORKSPACE` points at a workspace that is itself a git repo; + 3 other lint-driven fixes in `wiki-io` (schema file exclusion, tokens-null-on-unsupported, lint_wiki path-qualified wikilinks) (`260521-gc0`)
- [ ] **HYGIENE-08** — `workspace_io.init()` tolerates sparse v2 manifests without a `plugins` key (defensive heal on the write path) (`260521-lj3`)
- [ ] **HYGIENE-09** — graph-wiki bootstrap self-healing `uv` re-exec; uses `Path(__file__).resolve()` not `sys.argv[0]`; loop prevention env var hygiene; test from a tmp working directory (`260521-mfm`)
- [ ] **HYGIENE-10** — graph-wiki plugin docs use `uv run --project "$AGENT_RESEARCH_ROOT" python …` shim form across all `plugins/graph-wiki/agents/*.md` and `plugins/graph-wiki/skills/graph-wiki/*` files (`260521-kxi`)
- [ ] **HYGIENE-11** — `--interactive` flag wired into graph-wiki bootstrap (todo: `2026-05-21-bootstrap-interactive-flag.md`)
- [ ] **HYGIENE-12** — Bootstrap stubs empty category index files (todo: `2026-05-21-bootstrap-should-stub-empty-category-index-files.md`)
- [ ] **HYGIENE-13** — `260521-ans` (Typer `--help` ANSI strip) closed as already-resolved at scoping; 3/3 `test_cli_help.py` tests verified passing under the existing `NO_COLOR=1 TERM=dumb COLUMNS=200` env-injection pattern before close
- [ ] **HYGIENE-14** — Phase 14 SC#4 plugin smoke transcript captured at scanner-phase close (carried since v1.2; manual `/graph-wiki:query` transcript)

### CGFIND — `cg find` Parser Ergonomics

- [ ] **CGFIND-01** — `cg find --name foo.py --kind file` parses and returns correct matches
- [ ] **CGFIND-02** — `cg find` with no positional + `--name` / `--kind` / `--in-package` flags works for all valid combinations
- [ ] **CGFIND-03** — Old positional form `cg find foo.py` produces a clear parse error (no silent wrong behavior); all internal callers in `packages/graph-io/tests/` updated in the same commit

### LIBTOOLS — Librarian Grounding Tools

- [x] **LIBTOOLS-01** — `graph_tools.py` exists at `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` exposing ≤5 `@tool`-decorated callables wrapping `graph_io.queries.*`
- [x] **LIBTOOLS-02** — All tools declare `-> str` return type and serialize results via `graph_io.cli._format.render(records, fmt="human")`; row results hard-capped at 50 with explicit truncation notice
- [x] **LIBTOOLS-03** — `build_graph_tools(conn)` factory accepts an open `graph_io.store` connection via closure; single connection opened at command entry, shared by all tool callables, closed in `finally`
- [x] **LIBTOOLS-04** — `commands/query.py` opens `read_only_connect()` against `workspace_io.paths.graph_dir(workspace) / "code.db"`, calls `bind_tools()` on librarian LLM with `build_graph_tools(conn)`; graceful `NOT_INITIALIZED` fallback (librarian still runs, with a clear notice that graph-tools are unavailable)
- [x] **LIBTOOLS-05** — CountTokens pre-flight verifies system prompt + tool schemas + input stays within model context budget; gate enforced at command entry before any LLM call

### GRAPHCMD — `graph-wiki-agent graph` Subcommand

- [ ] **GRAPHCMD-01** — `graph-wiki-agent graph --help` exits 0 listing exactly 3 subcommands: `build`, `describe`, `query`
- [ ] **GRAPHCMD-02** — `graph-wiki-agent graph build` invokes graph-io update (full or incremental); only flags beyond `cg`'s are `--trace` and `--model`
- [ ] **GRAPHCMD-03** — `graph describe` and `graph query` mirror `cg` semantics; cost-tracked trace record written when `--trace` is set
- [ ] **GRAPHCMD-04** — MCP server (`graph-wiki-mcp`) exposes `graph_build`, `graph_describe`, `graph_query` tools (prefix parallel to existing `wiki_*` tools)

### SCANNER — Scanner Consumes graph-io

- [ ] **SCANNER-01** — `run_scan()` calls `cg update` (incremental) before subagent fan-out so graph URIs are fresh
- [ ] **SCANNER-02** — Scanner derives vault page slug from graph URI (not from filesystem path inference); falls back to path-based logic gracefully when graph not initialized, with a clear log line
- [ ] **SCANNER-03** — Plugin (`plugins/graph-wiki/`) end-to-end smoke runs successfully against unchanged wiki-io behavior (regression guard captured as success criterion of any phase touching wiki-io templates)

### INGESTOR — Ingestor Consumes graph-io

- [ ] **INGESTOR-01** — `run_ingest_source()` checks graph-io for canonical entity existence before ingest decisions
- [ ] **INGESTOR-02** — Clear `NOT_INITIALIZED` error surfaced (not silent fallback) when ingest invoked against a workspace with no graph-io DB
- [ ] **INGESTOR-03** — URI-drift / orphaned-page limitation explicitly documented in code comments + phase plan as a v1.8 reconciliation item (do NOT attempt to solve in v1.7)

---

## Future Requirements (Deferred to v1.8+)

- URI-keyed wiki redesign (flat-by-ID / by-domain / by-repo views from one graph)
- Scanner 9-stage pipeline restructure per ONTOLOGY-SPEC §9
- URI reconciliation for orphaned pages on package rename
- Plugin (`plugins/graph-wiki/`) wiring to graph-io
- Nyquist compliance retroactive decision (0/28+ v1.1-v1.6 phases produced VALIDATION.md)
- check-brand.sh regex over-breadth — trim `workspace_io|lattice_wiki_core` from regex; shrink `.brand-grep-allow`
- `librarian.py:21` `_SLUG_ONLY_RE` parity fix
- Pre-existing `test_integration_gate.py` failure on `sample_monorepo/tests/integration/test_top.py`

---

## Out of Scope

- Anything that re-designs schema v2 / URI identity (locked in v1.6 — STRUCT-* / SCHEMA-* requirements)
- Adopting `langgraph` or `deepagents` for orchestration (in-house `subagent-runtime` stays — see CLAUDE.md §2 stack-departure note)
- `langchain-anthropic` or direct Anthropic API (Bedrock-only constraint)
- `ChatBedrock` legacy class migration (already on `ChatBedrockConverse` since v1.0)
- Mirroring all 25 `cg` subcommands through `graph-wiki-agent graph` (3-verb curated surface only)
- New top-level `packages/` directories (architecture additive only — `graph_tools.py` + `commands/graph.py` are new modules within `agents/graph-wiki-agent/`)
- New runtime dependencies beyond the `langchain-aws>=1.4.7` floor bump and the explicit `graph-io` workspace dep

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| HYGIENE-01 | Phase 35 | Pending |
| HYGIENE-02 | Phase 35 | Pending |
| HYGIENE-03 | Phase 35 | Pending |
| HYGIENE-04 | Phase 35 | Pending |
| HYGIENE-05 | Phase 35 | Pending |
| HYGIENE-06 | Phase 35 | Pending |
| HYGIENE-07 | Phase 35 | Pending |
| HYGIENE-08 | Phase 35 | Pending |
| HYGIENE-09 | Phase 35 | Pending |
| HYGIENE-10 | Phase 35 | Pending |
| HYGIENE-11 | Phase 35 | Pending |
| HYGIENE-12 | Phase 35 | Pending |
| HYGIENE-13 | Phase 35 | Pending |
| HYGIENE-14 | Phase 35 | Pending |
| CGFIND-01 | Phase 36 | Pending |
| CGFIND-02 | Phase 36 | Pending |
| CGFIND-03 | Phase 36 | Pending |
| LIBTOOLS-01 | Phase 37 | Complete |
| LIBTOOLS-02 | Phase 37 | Complete |
| LIBTOOLS-03 | Phase 37 | Complete |
| LIBTOOLS-04 | Phase 37 | Complete |
| LIBTOOLS-05 | Phase 37 | Complete |
| GRAPHCMD-01 | Phase 38 | Pending |
| GRAPHCMD-02 | Phase 38 | Pending |
| GRAPHCMD-03 | Phase 38 | Pending |
| GRAPHCMD-04 | Phase 38 | Pending |
| SCANNER-01 | Phase 39 | Pending |
| SCANNER-02 | Phase 39 | Pending |
| SCANNER-03 | Phase 39 | Pending |
| INGESTOR-01 | Phase 40 | Pending |
| INGESTOR-02 | Phase 40 | Pending |
| INGESTOR-03 | Phase 40 | Pending |
