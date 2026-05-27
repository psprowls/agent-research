# Architecture Research

**Domain:** v1.7 graph-io Integration & Wiki Hygiene
**Researched:** 2026-05-26
**Confidence:** HIGH (derived entirely from direct source inspection of existing codebase)

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       User Entry Points                                       │
│  graph-wiki-agent CLI (cli.py:app, Typer)    graph-wiki-mcp (FastMCP stdio)  │
└────────────────────────────┬────────────────────────────────┬─────────────────┘
                             │                                │
┌────────────────────────────▼────────────────────────────────▼─────────────────┐
│                     Command Layer  (agents/graph-wiki-agent)                   │
│  commands/query.py    commands/scan.py    commands/ingest.py                  │
│  commands/init.py     commands/lint.py    commands/log.py                     │
│  commands/graph.py  (NEW v1.7: graph build/describe/query)                    │
└────────────┬───────────────────────────────────────┬──────────────────────────┘
             │                                       │
             ▼                                       ▼
┌──────────────────────────┐           ┌────────────────────────────────────────┐
│  SubagentPool            │           │  graph_tools.py  (NEW v1.7)            │
│  (subagent-runtime)      │           │  @tool wrappers over graph_io.queries  │
│  asyncio.Semaphore       │           │  find_symbol, tests_for_file,          │
│  fan-out + trace IO      │           │  list_packages, describe_domain, etc.  │
└──────────────────────────┘           └────────────────────┬───────────────────┘
                                                            │ imports
┌───────────────────────────────────────────────────────────▼───────────────────┐
│                        Package Layer  (packages/)                              │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  graph-io      │  │  wiki-io         │  │ workspace-io │  │model-adapter│ │
│  │  store.py      │  │  scan_monorepo   │  │ config.py    │  │ make_llm()  │ │
│  │  queries.py    │  │  lint_wiki.py    │  │ init.py      │  │ load_role_  │ │
│  │  uri.py        │  │  assets/         │  │ manifest.py  │  │  config()   │ │
│  │  cli/ (cg)     │  │  page-templates/ │  │ paths.py     │  └─────────────┘ │
│  └────────────────┘  └──────────────────┘  └──────────────┘                  │
└────────────────────────────────────────────────────────────────────────────────┘
                                │
              ┌─────────────────▼──────────────────┐
              │           Storage                   │
              │  code.db (SQLite WAL, graph-io)     │
              │  search.db (embeddings, wiki)       │
              │  bm25/ (BM25 index)                 │
              │  traces/ (JSONL trace records)      │
              └────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `cli.py` (Typer `app`) | CLI entry; parse args, dispatch to `run_*` coroutines | `commands/` modules |
| `graph_wiki_mcp/server.py` | FastMCP stdio; wrap commands as MCP tools | `commands/` modules |
| `commands/query.py` | Hybrid search + librarian fan-out + synthesis | `prompts/`, `subagent-runtime`, `wiki-io`, `graph_tools.py` (v1.7) |
| `commands/scan.py` | Walk repo, diff vs vault, scanner fan-out, write stubs | `wiki-io.scan_monorepo`, `subagent-runtime`, `graph-io` (v1.7) |
| `commands/ingest.py` | Route source file to vault page type, call ingestor LLM | `wiki-io.ingest_source`, `subagent-runtime`, `graph-io` (v1.7) |
| `commands/graph.py` (NEW) | `graph build/describe/query` CLI operations | `graph-io.store`, `graph-io.queries`, `graph-io.update` |
| `graph_tools.py` (NEW) | `@tool`-decorated wrappers over `graph_io.queries.*` | `graph-io.store`, `graph-io.queries` |
| `packages/graph-io` | SQLite store + `cg` CLI (25 subcommands); `queries.py` public API | `workspace-io.paths` |
| `packages/wiki-io` | Vault read/write, scan monorepo, lint, page templates | `workspace-io` |
| `packages/workspace-io` | Workspace bootstrap, manifest IO, config resolution | (leaf library) |
| `packages/model-adapter` | `make_llm(role)` + `_GuardedChatBedrockConverse` | `langchain-aws` |
| `packages/subagent-runtime` | `SubagentPool` asyncio fan-out + JSONL trace IO | `langchain-core` |
| `plugins/graph-wiki` | Claude Code plugin (Claude Code inference; NOT wired to graph-io in v1.7) | `wiki-io`, `workspace-io` via `uv run` shell-out |

---

## Recommended Project Structure (v1.7 additions highlighted)

```
agents/graph-wiki-agent/src/graph_wiki_agent/
  cli.py                         # MODIFIED: add graph_app sub-Typer
  graph_tools.py                 # NEW: @tool wrappers over graph_io.queries
  commands/
    graph.py                     # NEW: graph build/describe/query implementations
    query.py                     # MODIFIED: bind_tools(graph_tools) for librarian
    scan.py                      # MODIFIED: graph-io URI keying + hfr/iws hygiene
    ingest.py                    # MODIFIED: graph-io existence/identity check
    init.py                      # MODIFIED: bootstrap todos (mfm, interactive, stubs)
    lint.py                      # unchanged
    log.py                       # unchanged

agents/graph-wiki-agent/src/graph_wiki_mcp/
  server.py                      # MODIFIED: add graph_build/graph_describe/graph_query tools

packages/wiki-io/src/wiki_io/
  assets/page-templates/
    package/overview.md          # MODIFIED: i26 (CONTAINER_DIR), he3 (file-map format)
    package/testing.md           # MODIFIED: i35 (testing.md subpage)
    app/overview.md              # MODIFIED: he3 (file-map format)
    app/testing.md               # MODIFIED: i35

packages/workspace-io/src/workspace_io/
  manifest.py  (or config.py)    # MODIFIED: lj3 (tolerate sparse plugins), gc0 (lint fixes)

packages/graph-io/src/graph_io/
  cli/q_find.py                  # MODIFIED: --name named-arg ergonomics fix

plugins/graph-wiki/              # MODIFIED: kxi (docs only, no code changes)
```

### Structure Rationale

- **`graph_tools.py` lives in `agents/` not `packages/`:** The `packages/` tier is library code with zero LangChain dependency. `@tool` decorators require `langchain-core`. Keeping `@tool` wrappers in the agent layer preserves this clean separation. Add to `packages/graph-io` only when a second consumer (e.g. plugin) needs the same tools (v1.8+).
- **`commands/graph.py` mirrors `commands/ingest.py` pattern:** `ingest` is the established precedent for a sub-Typer with named sub-operations. `graph` follows the same shape.
- **Hygiene changes in `packages/` only touch `wiki-io` and `workspace-io`:** No new packages needed. All changes are targeted modifications to existing files.

---

## Architectural Patterns

### Pattern 1: Agent-Local @tool Wrappers

**What:** `@tool`-decorated functions in `graph_tools.py` that accept the query parameters, call `graph_io.queries.*` with a pre-opened read-only connection, serialize the result to JSON, and return a string. The connection is opened once per command invocation, not once per tool call.

**When to use:** Any new `graph_io.queries.*` function that the librarian should invoke to ground its answers. Add a `@tool` function to `graph_tools.py`, add it to the list passed to `build_graph_tools(conn)`, include in `.bind_tools(tools)`.

**Trade-offs:** Opening the connection at command entry (not lazily) means a connection open even when the model never calls a graph tool. Acceptable — `store.read_only_connect()` against a local SQLite file is sub-millisecond. Lazy connect adds complexity for negligible gain.

**Example shape:**
```python
# agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py
from graph_io import queries, store
from langchain_core.tools import tool

def build_graph_tools(conn):
    @tool
    def find_symbol(name: str, kind: str | None = None) -> str:
        """Find code symbols by name and optional kind (function, class, file, package, ...)."""
        records = queries.find(conn, name=name, kind=kind)
        return json.dumps([...serialize(r) for r in records])

    @tool
    def tests_for_file(path: str) -> str:
        """Return test suites and test files that cover the given source file path."""
        # resolve package from path, then call tests_for_package
        ...

    return [find_symbol, tests_for_file, list_packages, describe_domain, what_tests]
```

### Pattern 2: Sub-Typer Registration (graph subcommand)

**What:** `graph_app = typer.Typer(...)` registered with `app.add_typer(graph_app, name="graph")` in `cli.py`. Commands defined in `commands/graph.py` via `@graph_app.command(name=...)`.

**When to use:** Any new top-level subcommand that groups multiple sub-operations. The existing `ingest` subcommand (`ingest_app`) is the established precedent — its shape is the template.

**Trade-offs:** Consistent with established pattern. No new pattern introduced.

**Example shape (cli.py additions):**
```python
from graph_wiki_agent.commands.graph import graph_app
app.add_typer(graph_app, name="graph")
```

**Example shape (commands/graph.py):**
```python
graph_app = typer.Typer(help="Build, describe, and query the code graph.")

@graph_app.command(name="build")
def graph_build(full: bool = typer.Option(False, "--full"), workspace: str = ...) -> None:
    ...

@graph_app.command(name="describe")
def graph_describe(target: str = typer.Argument(...), ...) -> None:
    ...

@graph_app.command(name="query")
def graph_query(query_text: str = typer.Argument(...), ...) -> None:
    ...
```

### Pattern 3: Workspace-Resolved DB Path

**What:** All graph-io access in the agent layer resolves the DB path via `workspace_io.paths.graph_dir(workspace) / "code.db"`. This is the identical resolution the `cg` CLI uses (`q_find.py`, `q_describe_package.py`, etc.).

**When to use:** Everywhere `graph_io.store.read_only_connect()` is called from the agent layer.

**Trade-offs:** Requires graph-io DB to be initialized (`cg update --full` run). On `GraphNotInitializedError`, the agent commands emit a user-friendly message ("Run `cg update --full` first to initialize the code graph.") and exit with code 1.

---

## Where graph-io @tool wrappers live

**Decision: agent-local in `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py`.**

Option analysis:
- **(a) Agent-local `graph_tools.py`** — correct. `packages/` is library tier; `@tool` is agent-tier concern. No second consumer in v1.7.
- **(b) `graph_io.tools` submodule** — wrong for v1.7. Would add `langchain-core` to `graph-io`'s deps, polluting the library. Warranted only when `plugins/graph-wiki` also needs these tools (v1.8 wiki redesign milestone).
- **(c) New `packages/graph-io-tools/` workspace member** — pure overhead. One consumer, one file worth of code. Creates a new workspace member for 50 LOC.

Option (a) wins. The existing precedent is `commands/query.py` defining `@tool read_file` inline in the agent layer. `graph_tools.py` follows the same philosophy but factored into its own file because the tool set is larger (5-8 tools vs 1).

---

## Scanner / Ingestor Consumption Pattern

**Decision: in-process Python import, not shell-out to `cg`.**

Project philosophy (confirmed by codebase inspection): SubagentPool is asyncio fan-out, not subprocess fan-out. The `cg` shell-out in `plugins/graph-wiki` is a concession to that plugin's separate runtime (Claude Code inference process), not a preferred pattern.

Concrete evidence against shell-out:
- `commands/scan.py` calls `wiki-io` functions in-process: `discover_workspaces()`, `compute_diff()`, `attach_changed_files()` — all synchronous Python calls inside an async function.
- Shell-out would require `asyncio.create_subprocess_exec`, JSON parsing, non-zero exit handling, and breaks the trace chain.

**Implementation in `commands/scan.py`:**
```python
async def run_scan(...):
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    # Open graph-io connection once; close in finally
    db_path = graph_dir(workspace_path) / "code.db"
    try:
        conn = store.read_only_connect(db_path)
    except store.GraphNotInitializedError:
        logger.warning("graph-io DB not initialized; URI keying disabled")
        conn = None
    try:
        # ... existing scan logic, using conn for URI resolution if available ...
    finally:
        if conn:
            conn.close()
```

Graceful degradation (conn=None) means the scan still works on repos where `cg update` has not been run. This matches the v1.7 scope: graph-io is "source of truth for identity" but not a hard requirement for the scanner to function.

---

## MCP Exposure of the `graph` Subcommand

**Decision: YES, expose as MCP tools in `server.py` with `graph_` prefix.**

Existing MCP tool naming: `wiki_ping`, `wiki_query`, `wiki_log`, `wiki_scan`, `wiki_ingest`, `wiki_lint`. The `wiki_` prefix signals wiki-vault operations.

New graph tools use `graph_` prefix, signaling code-graph operations:

| MCP Tool Name | CLI Equivalent | Purpose |
|---------------|----------------|---------|
| `graph_build` | `graph build` | Run `cg update [--full]` equivalent |
| `graph_describe` | `graph describe` | Describe repo/package/domain/suite by name |
| `graph_query` | `graph query` | Structured or NL query over the code graph |

These go in `server.py` as `@mcp.tool(name="graph_build", ...)` delegating to `run_graph_build()` etc. in `commands/graph.py`. Same pattern as existing `wiki_scan` → `run_scan()`.

---

## `cg find` Parser Ergonomics Fix

**Current behavior:** `cg find scan_monorepo --kind file` (positional name + optional `--kind`).

**Problem:** Users expect `cg find --name scan_monorepo --kind file` to work. The current argparse shape only accepts positional `name`.

**Fix location:** `packages/graph-io/src/graph_io/cli/q_find.py`

Current `add_arguments`:
```python
def add_arguments(parser):
    parser.add_argument("name")          # positional, required
    parser.add_argument("--kind", default=None)
```

Fix: make name optional positional + add `--name` as an alternative. The `run()` function resolves `name = args.name or args.name_opt`.

```python
def add_arguments(parser):
    parser.add_argument("name", nargs="?", default=None,
                        help="symbol name (positional, for backwards compat)")
    parser.add_argument("--name", dest="name_opt", default=None,
                        help="symbol name (named flag alternative)")
    parser.add_argument("--kind", default=None)

def run(args):
    name = args.name or args.name_opt
    if name is None and args.kind is None:
        print("error: find requires --name or a positional name argument", file=sys.stderr)
        return exit_codes.GENERIC
    ...
    records = queries.find(conn, name=name, kind=args.kind)
```

No change to `queries.find()` — purely a CLI parsing fix.

---

## Hygiene Phase Build Order and File Overlap Analysis

### Hygiene task file-ownership map

| Task ID | Files Modified |
|---------|---------------|
| `hfr` | `commands/scan.py` (wikilink prefix emitted by scanner) |
| `i26` | `wiki-io/assets/page-templates/package/overview.md` (add `{{CONTAINER_DIR}}` var) |
| `he3` | `wiki-io/assets/page-templates/package/overview.md`, `app/overview.md` (file-map format) |
| `i35` | `wiki-io/assets/page-templates/package/testing.md`, `app/testing.md`, possibly `domain/` and `plugin/` templates; wiki-io init logic for stub generation |
| `iws` | `commands/scan.py` page routing; wiki-io scan path logic (overview page rename) |
| `kxi` | `plugins/graph-wiki/` docs only — no Python code |
| `ans` | `commands/*.py` output calls; possibly `cli.py` (Typer ANSI strip) |
| `gc0` | `packages/workspace-io/` — repo discovery + 3 lint-driven fixes |
| `lj3` | `packages/workspace-io/manifest.py` or `config.py` — tolerate sparse plugins list |
| `mfm` | `commands/init.py` or `wiki-io/init_vault.py` — self-healing uv re-exec |
| bootstrap interactive flag | `commands/init.py` and/or `cli.py` |
| bootstrap stub category indexes | `commands/init.py`, `wiki-io/init_vault.py` |

### Overlap between hygiene and integration

| File | Hygiene Task | Integration Task | Risk if integration-first |
|------|-------------|-----------------|--------------------------|
| `commands/scan.py` | `hfr` (wikilink prefix), `iws` (page routing) | Scanner consumes graph-io (URI keying, ~50 new lines) | Both touch `run_scan()` body; hygiene rebases onto a larger integration diff |
| `wiki-io/assets/page-templates/package/overview.md` | `i26` (CONTAINER_DIR), `he3` (file-map format) | Scanner integration generates stubs from these templates | Integration immediately produces stubs in wrong format if templates not fixed first |
| `commands/init.py` | `mfm`, interactive flag, stub indexes | `cli.py` adds `app.add_typer(graph_app, ...)` (adjacent, same file for imports) | Lower risk — cli.py change is additive; init.py changes are in different functions |

### Verdict: Hygiene first, integration second

Hygiene is a dedicated phase before any integration work. Rationale:

1. `hfr` + `iws` both touch `commands/scan.py`. Scanner integration adds ~50 lines to `run_scan()`. Doing hygiene after integration means rebasing two quick fixes onto a larger diff — higher merge complexity, harder to review.
2. `i26` + `he3` fix templates that the scanner integration will start using immediately. Wrong templates produce wrong vault stubs from day one of integration.
3. `gc0` + `lj3` fix workspace-io. The graph-io integration calls `workspace_io.paths.graph_dir(workspace)` — a workspace-io bug present during integration creates confounding failures.
4. All hygiene tasks are narrow and independently testable. They do not block each other (except `he3` and `i26` both touch `overview.md` — combine them into a single plan).
5. `kxi` is docs-only and has zero code deps. It can go anywhere, but keeping it in the hygiene phase reduces context switching.

The one task that could reasonably go after integration is `kxi` (plugin docs) — but there is no benefit to splitting it out.

---

## Data Flow: End-to-End Integration Example

**Scenario:** User asks "what tests cover `packages/wiki-io/src/wiki_io/scan_monorepo.py`?"

```
User → graph-wiki-agent query "what tests cover packages/wiki-io/scan_monorepo.py"
    │
    ▼
cli.py:query() → asyncio.run(run_query(query_text, workspace_path, top_k=5))
    │
    ▼
commands/query.py:run_query()
    │
    ├─ [1] resolve wiki via resolve_wiki_and_repo(workspace_path)
    │       wiki = ~/Personal/graph-wiki/agent-research
    │
    ├─ [2] Hybrid search (BM25 + embeddings) over vault
    │       → top_pages = ["packages/wiki-io/scan_monorepo.md", ...]
    │
    ├─ [3] Open graph-io connection + build tools (NEW v1.7)
    │       db_path = graph_dir(workspace) / "code.db"
    │       conn = store.read_only_connect(db_path)
    │       tools = build_graph_tools(conn)   # 5-8 @tool callables
    │       librarian_llm = make_llm("librarian").bind_tools(tools)
    │
    ├─ [4] Librarian fan-out (SubagentPool.run_all) over top_pages
    │
    │   drill_page("packages/wiki-io/scan_monorepo.md"):
    │       ├─ SystemMessage(LIBRARIAN_SYSTEM)
    │       ├─ HumanMessage("Query: ...\n\nPage content: ...")
    │       │
    │       ├─ Model emits tool_call: find_symbol(name="scan_monorepo", kind="file")
    │       │       ↓
    │       │   graph_tools.find_symbol():
    │       │       records = queries.find(conn, name="scan_monorepo", kind="file")
    │       │       → NodeRecord(kind="file",
    │       │                    path="packages/wiki-io/src/wiki_io/scan_monorepo.py",
    │       │                    attrs={"uri": "file:pat/agent-research/packages/wiki-io/..."})
    │       │       return json.dumps([...])
    │       │   ToolMessage(content=json_result) → appended to msgs
    │       │
    │       ├─ Model emits tool_call: tests_for_file(path="packages/wiki-io/...")
    │       │       ↓
    │       │   graph_tools.tests_for_file():
    │       │       # resolve package name from path → "wiki-io"
    │       │       suites = queries.tests_for_package(conn, package_name="wiki-io")
    │       │       → [SuiteDescription(name="wiki-io-tests",
    │       │                           uri="test_suite:pat/agent-research/wiki-io-tests",
    │       │                           file_count=24)]
    │       │       return json.dumps([...])
    │       │   ToolMessage(content=json_result) → appended to msgs
    │       │
    │       └─ Model emits final AIMessage:
    │               "scan_monorepo.py is covered by the wiki-io-tests suite
    │                (test_suite:pat/agent-research/wiki-io-tests, 24 files).
    │                See [[wiki/packages/wiki-io/testing]] for test layout."
    │               → TaskResult(value=content, response=resp)
    │
    ├─ [5] Synthesizer call with librarian excerpts → answer string
    │
    ├─ [6] close conn  (in finally block)
    │
    └─ [7] Return QueryResult(answer, citations, pages_drilled, search_scores)
```

**Key invariant:** `conn` is opened once at the top of `run_query()`, shared by all tool closures via `build_graph_tools(conn)`, and closed in a `finally` block after the fan-out completes. This avoids per-tool connection overhead while bounding connection lifetime to the command invocation.

---

## New vs Modified: File-Level Count

### New files

| File | Approx LOC | Purpose |
|------|-----------|---------|
| `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` | ~120 | `@tool` wrappers over `graph_io.queries.*` |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` | ~150 | `graph build/describe/query` command implementations |

### Modified files (integration)

| File | Change Summary |
|------|---------------|
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` | +4 lines: import `graph_app`, `app.add_typer(graph_app, name="graph")` |
| `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` | +~80 lines: `graph_build`, `graph_describe`, `graph_query` MCP tools |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` | +~30 lines: open conn, build tools, bind to librarian LLM |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` | +~50 lines: open conn, URI resolution for package identity |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` | +~30 lines: open conn, URI existence check before write |
| `agents/graph-wiki-agent/pyproject.toml` | +1 line: add `graph-io` workspace dep |
| `packages/graph-io/src/graph_io/cli/q_find.py` | ~10 lines: `--name` named-arg ergonomics fix |

### Modified files (hygiene only)

| File | Task(s) |
|------|---------|
| `packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md` | `i26`, `he3` |
| `packages/wiki-io/src/wiki_io/assets/page-templates/app/overview.md` | `he3` |
| `packages/wiki-io/src/wiki_io/assets/page-templates/package/testing.md` | `i35` |
| `packages/wiki-io/src/wiki_io/assets/page-templates/app/testing.md` | `i35` |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` | `hfr`, `iws` |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` | `mfm`, interactive flag, stub indexes |
| `packages/workspace-io/src/workspace_io/manifest.py` (or `config.py`) | `lj3` |
| `packages/workspace-io/src/workspace_io/config.py` (or related) | `gc0` |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/*.py` (multiple) | `ans` |
| `plugins/graph-wiki/` docs | `kxi` (docs only) |

**Total: 2 new files, ~7 modified files for integration, ~10 modified files for hygiene. Zero new packages or top-level directories.**

---

## Integration Dependency Graph (within v1.7)

```
[Phase: Hygiene]
  hfr, i26+he3, i35, iws   ← wiki-io templates + scan.py routing
  gc0, lj3                  ← workspace-io fixes
  mfm + interactive + stubs ← bootstrap fixes
  kxi                       ← plugin docs (no code deps)
  ans                       ← Typer ANSI (cross-cutting)
       │
       │  hygiene merged → clean foundation
       ▼
[Phase: cg find ergonomics]
  q_find.py parser fix (graph-io only, no agent deps)
       │
       ▼
[Phase: Librarian Grounding Tools]
  graph_tools.py (new)
  commands/query.py bind_tools modification
       │
       ▼  (can proceed in parallel with grounding tools)
[Phase: graph subcommand]
  commands/graph.py (new)
  cli.py + server.py additions
       │
       ▼
[Phase: Scanner + Ingestor graph-io consumption]
  commands/scan.py URI keying
  commands/ingest.py identity check
       │
       ▼
[Tests + Integration validation]
  Unit tests: graph_tools.py
  Integration: run_query with graph tools (mocked conn)
  Integration: run_scan with graph-io connection (real DB optional)
```

**Rationale for this order:**
- Librarian grounding tools before scanner/ingestor: read-only, side-effect-free, lower risk. Validates the `build_graph_tools` / `bind_tools` pattern before scanner touches URI-keyed writes.
- `graph` subcommand can proceed in parallel with librarian tools since both only depend on hygiene being done. They touch different files (`commands/graph.py` vs `commands/query.py`).
- Scanner/ingestor integration goes last because it changes page-writing logic and is the highest-risk integration surface.

---

## Anti-Patterns

### Anti-Pattern 1: Shell-out to `cg` from agent commands

**What people do:** `subprocess.run(["cg", "find", name], capture_output=True)` instead of `queries.find(conn, name=name)`.

**Why it's wrong:** Breaks the async event loop (blocking subprocess in an async function), requires JSON parsing, adds subprocess management, breaks the cost/trace accounting chain. The `cg` shell-out in `plugins/graph-wiki` is a concession to that plugin's separate runtime — not a model for agent commands.

**Do this instead:** `from graph_io import queries, store`. Open a read-only connection in-process. Call Python functions directly.

### Anti-Pattern 2: @tool decorators inside `packages/graph-io`

**What people do:** Add `langchain-core` to `graph-io`'s deps and define `@tool` wrappers in `packages/graph-io/src/graph_io/tools.py`.

**Why it's wrong:** Introduces an agent-framework dependency into a library package. The `plugins/graph-wiki` plugin also uses `wiki-io` and `workspace-io` — if `graph-io` pulls in LangChain, it adds 100+ MB to the plugin's lightweight runtime unnecessarily.

**Do this instead:** Keep `@tool` wrappers in `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py`. Promote to `packages/` only when a second consumer (plugin) needs them.

### Anti-Pattern 3: Opening a new graph-io connection per tool call

**What people do:** Each `@tool` function inside `graph_tools.py` calls `store.read_only_connect(db_path)` independently.

**Why it's wrong:** During a single `run_query()` call the librarian may invoke 3-5 tools per page, across top-k pages (up to 10). That's potentially 50 SQLite file opens. Each open involves file-descriptor allocation and `PRAGMA query_only`, plus the schema version check.

**Do this instead:** One connection opened at the top of `run_query()`, passed into tool closures via `build_graph_tools(conn)`, closed in `finally` after fan-out completes.

### Anti-Pattern 4: Interleaving hygiene with integration changesets

**What people do:** Fix `hfr` (scan.py wikilink prefix) in the same PR/phase as the scanner graph-io integration.

**Why it's wrong:** Both touch `commands/scan.py`. The integration adds ~50 lines to `run_scan()`. Reviewing a hygiene fix buried inside a larger integration diff is error-prone and makes rollback harder.

**Do this instead:** Hygiene as its own dedicated phase first. Integration builds on the clean result.

### Anti-Pattern 5: Hardcoding the graph-io DB path

**What people do:** `store.read_only_connect(Path.home() / ".graph-wiki" / "code.db")`.

**Why it's wrong:** The canonical DB path is `workspace_io.paths.graph_dir(workspace) / "code.db"`. Hardcoding bypasses per-workspace path resolution and breaks multi-workspace setups.

**Do this instead:** Always call `graph_dir(workspace_path)` from `workspace_io.paths`. This is the same resolution `cg` uses — maintaining a single source of truth for path semantics.

---

## Sources

- Direct inspection: `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — sub-Typer pattern (`ingest_app`), full command list
- Direct inspection: `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` — MCP tool naming convention (`wiki_*`), `@mcp.tool` pattern
- Direct inspection: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — agent-local `@tool read_file` precedent, librarian fan-out shape, `build_graph_tools` entry point pattern
- Direct inspection: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — `run_scan()` structure, `hfr`/`iws` hygiene overlap surface
- Direct inspection: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` — ingestor structure, identity check integration point
- Direct inspection: `packages/graph-io/src/graph_io/queries.py` — full public query API (find, callers, callees, describe_package, tests_for_package, domain_references, etc.)
- Direct inspection: `packages/graph-io/src/graph_io/store.py` — `read_only_connect()` contract, `GraphNotInitializedError`, `SchemaMismatchError`
- Direct inspection: `packages/graph-io/src/graph_io/cli/q_find.py` — current argparse shape (positional `name`, `--kind` option)
- Direct inspection: `packages/graph-io/src/graph_io/cli/main.py` — 25-subcommand registry, `cg` dispatch pattern
- Direct inspection: `packages/graph-io/src/graph_io/uri.py` — URI composition functions, `RepoContext`
- Direct inspection: `packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md` — `{{CONTAINER_DIR}}` placeholder, file-map format (hygiene targets `i26`, `he3`)
- Direct inspection: `packages/workspace-io/src/workspace_io/config.py`, `init.py` — `gc0`, `lj3` hygiene targets
- Direct inspection: `.planning/STATE.md` — 10 deferred quick task IDs and descriptions
- Direct inspection: `.planning/PROJECT.md` — v1.7 scope, hygiene-before-integration rationale, plugin boundary constraints, phase numbering start (Phase 35)
- Direct inspection: `agents/graph-wiki-agent/pyproject.toml` — current dependency list (graph-io not yet listed)

---
*Architecture research for: v1.7 graph-io Integration & Wiki Hygiene*
*Researched: 2026-05-26*
