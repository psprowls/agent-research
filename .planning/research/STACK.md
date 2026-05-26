# Stack Research — v1.7 graph-io Integration & Wiki Hygiene

**Domain:** Wiring an existing SQLite code-graph store (`graph-io`) into an existing AWS-Bedrock LangChain agent (`graph-wiki-agent`)
**Researched:** 2026-05-26
**Confidence:** HIGH (all decisions verified against installed packages, codebase review, and PyPI)

---

## Summary Answer

**No new runtime dependencies are required for v1.7's core integration work.** The five sub-questions below each resolve to "existing primitives cover it." Two dependency floor bumps are warranted (not breaking): `langchain-aws` to `>=1.4.7` (strip-invalid-tool-use-block fix is relevant to multi-tool fan-out) and optionally `typer` to `>=0.26.0` (released today; vendored Click simplifies conflict avoidance). The ANSI-strip test issue (`260521-ans`) does NOT require a new package — the existing `NO_COLOR` + `TERM=dumb` env-injection pattern already in `test_cli_help.py`, `test_cli_query.py`, and `test_trace_viewer.py` is the correct solution; the failing tests that motivated `260521-ans` are already passing with this pattern.

---

## Q1 — Exposing graph-io as @tool Functions to the Librarian

### Decision: No new packages. `langchain-core @tool` handles it natively against the existing graph-io Python API.

**Evidence:** `graph_io/queries.py` exposes pure Python functions (`find`, `callers`, `callees`, `imports`, `describe_package`, `describe_path`, `describe_repository`, `describe_domain`, `list_packages`, `list_domains`, `list_entry_points`, `list_test_suites`, `tests_for_package`, `domain_references`, `domain_depends_on`, `cross_cutting_packages`, etc.) that accept a `sqlite3.Connection` + keyword arguments and return frozen dataclasses (`NodeRecord`, `CallRecord`, `PackageDescription`, `PathDescription`, `DomainDescription`, etc.). These are plain Python callables.

`langchain-core`'s `@tool` decorator wraps any Python callable — it uses `inspect` to extract the signature and docstring, and `pydantic` to validate/coerce arguments from the LLM's tool call JSON. The `@tool`-decorated wrapper returns the Python function's return value directly. The librarian receives it as a `ToolMessage` string (via LangChain's message serialization).

**Integration pattern (no new package):**

```python
# agents/graph-wiki-agent/src/graph_wiki_agent/tools/graph_tools.py
from langchain_core.tools import tool
from graph_io import queries, store
from workspace_io import paths, resolve

def _open_conn():
    cfg = resolve()
    db_path = paths.graph_dir(cfg.workspace) / "code.db"
    return store.read_only_connect(db_path)

@tool
def find_symbol(name: str, kind: str | None = None) -> str:
    """Find code graph nodes by name and optional kind (function, class, file, package, etc.)."""
    conn = _open_conn()
    results = queries.find(conn, name=name, kind=kind)
    conn.close()
    return "\n".join(f"{r.kind} {r.name} at {r.path}:{r.line}" for r in results) or "not found"
```

The `sqlite3.Connection` is NOT passed through the tool signature — the tool opens and closes its own connection using `workspace_io.resolve()` (already a workspace dep). The LLM only provides `name` / `kind` — both are JSON-serializable primitive types that `@tool`'s pydantic wrapper handles natively.

**Why not `langchain-core` `StructuredTool` or `BaseTool` subclass:** `@tool` is sufficient and idiomatic; `StructuredTool` adds nothing over `@tool` for straightforward callables. `BaseTool` subclassing is only warranted when async streaming, cancellation, or complex lifecycle management is needed.

**No new packages needed.** `langchain-core>=1.4.0` is already installed (confirmed `1.4.0`). `graph-io` is already a workspace member. `workspace-io` is already a dep of `graph-wiki-agent`.

---

## Q2 — New CLI Patterns for `graph-wiki-agent graph` Subcommand

### Decision: No new packages. Existing `typer.Typer()` + `app.add_typer()` pattern (already used for `ingest`) handles it exactly.

**Evidence:** `cli.py` already uses the nested sub-app pattern:

```python
ingest_app = typer.Typer(help="Ingest a source file or work item into the wiki.")
app.add_typer(ingest_app, name="ingest")
```

The `graph` sub-app follows the identical pattern:

```python
graph_app = typer.Typer(help="Build, inspect, and query the code graph.")
app.add_typer(graph_app, name="graph")

@graph_app.command(name="build")
def graph_build(...): ...

@graph_app.command(name="describe")
def graph_describe(...): ...

@graph_app.command(name="query")
def graph_query(...): ...
```

Typer `0.25.1` (installed, confirmed) and `0.26.0` (released today, 2026-05-26) both support this. `0.26.0` only breaking change is vendoring Click — it removes the ability to extract the underlying Click app object. This project does not use Click internals directly, so there is no breakage risk. The `add_typer` / `@app.command` / `no_args_is_help=True` pattern is unchanged.

**No new packages needed.** `typer>=0.25.1` is the existing floor; `graph` sub-app mirrors `ingest` sub-app exactly.

---

## Q3 — Tool-Result Formatting Back to the LLM

### Decision: No new packages. Plain string formatting or `dataclasses.asdict` + `json.dumps` is the correct pattern; the existing `graph_io.cli._format` module provides a reusable `render()` for human-column output.

**Evidence:** LangChain's `@tool` decorator returns whatever the function returns; if it's a string, it becomes the `ToolMessage.content` directly. If it's a non-string, LangChain serializes it via `str()`. The correct approach for LLM-facing tool results is **compact, readable plain text** (not JSON blobs) — token-efficient and model-friendly.

`graph_io/cli/_format.py` already provides `render(records, fmt="human")` which produces aligned-column tabular output from any list of frozen dataclasses. This function is independent of the CLI layer (takes `records: Iterable[Any]` and `fmt: str`). The tool wrappers can import it directly:

```python
from graph_io.cli._format import render
from graph_io import queries

@tool
def list_packages_tool() -> str:
    """List all packages in the code graph."""
    conn = _open_conn()
    nodes = queries.list_packages(conn)
    conn.close()
    return render(nodes, fmt="human") or "no packages found"
```

For richer results (e.g., `PackageDescription` with nested lists), a small per-tool formatter in `graph_tools.py` using `dataclasses.asdict` + selective field rendering is sufficient — no library needed.

**What NOT to use:** Do not wrap results in `pydantic` models and return those from `@tool` — LangChain does not special-case pydantic model return types in tool messages; it calls `str()` on them, producing `PackageDescription(name='...', ...)` noise. Use explicit string formatting.

**No new packages needed.** `graph_io.cli._format.render` + `dataclasses` (stdlib) + `json` (stdlib) cover all result-formatting needs.

---

## Q4 — Test-Infra Additions for the Hygiene Phase (ANSI Strip)

### Decision: No new package. The `260521-ans` ANSI-strip issue is already solved in the codebase by the `NO_COLOR=1 TERM=dumb COLUMNS=200` env-injection pattern. Extend this pattern to new `graph` subcommand tests; do NOT add `strip-ansi`, `ansi2text`, or similar packages.

**Evidence:** The failing tests that motivated `260521-ans` are already passing:

```
agents/graph-wiki-agent/tests/unit/test_cli_help.py::test_cli_help_exits_zero      PASSED
agents/graph-wiki-agent/tests/unit/test_cli_help.py::test_cli_help_lists_bootstrap_subcommand PASSED
agents/graph-wiki-agent/tests/unit/test_cli_help.py::test_cli_help_init_subcommand_removed    PASSED
```

The fix is already in production across three test files (`test_cli_help.py`, `test_cli_query.py`, `test_trace_viewer.py`), all using the same `_PLAIN_HELP_ENV` pattern:

```python
_PLAIN_HELP_ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}
```

The `graph` subcommand help tests should follow this same established pattern. No library strip needed; the Typer/Rich rendering is suppressed at the subprocess level before any ANSI sequences are emitted.

**Why not `strip-ansi` / `ansi2text` / `rich.strip_markup`:** Post-hoc stripping of ANSI sequences from subprocess output is a symptom treatment. The env-injection approach prevents Rich from emitting ANSI in the first place. Post-hoc stripping also requires knowing which exact sequences Rich emits (SGR, hyperlinks, etc.), which is a moving target as Rich versions evolve. The env-var approach is stable and already proven in this codebase.

**No new packages needed.** Copy the `_PLAIN_HELP_ENV` pattern into the new `test_cli_graph.py` test file.

---

## Q5 — Version Pin Verification

### Current installed vs. latest PyPI (as of 2026-05-26)

| Package | Currently Pinned (pyproject.toml) | Installed | Latest on PyPI | Recommendation |
|---------|-----------------------------------|-----------|----------------|----------------|
| `langchain-aws` | `>=1.4.6` | 1.4.6 | **1.5.0** (2026-05-19) | Bump floor to `>=1.4.7` |
| `langchain-core` | (transitive) | 1.4.0 | 1.4.0 | No change — already current |
| `typer` | `>=0.25.1` | 0.25.1 | **0.26.0** (2026-05-26, today) | Optional bump to `>=0.26.0`; not blocking |
| `mcp` | `>=1.27.1` | 1.27.1 | 1.27.1 | No change — already current |

**`langchain-aws` — bump floor to `>=1.4.7`:**

Release notes confirm 1.4.7 (2026-05-15) added: *"strip streaming-only fields from invalid tool_use blocks"*. This is directly relevant to the librarian grounding tools phase — when the librarian makes multi-tool calls, an invalid `tool_use` block in the streaming response can corrupt downstream parsing. This fix belongs in-scope for v1.7. 1.5.0 adds *"use resolved base model for tracing"* (tracing improvement, not functional) and bumps `langsmith` / `langchain-classic` deps. No breaking changes to `ChatBedrockConverse` were identified in either release.

**Recommendation:** Set floor to `>=1.4.7` in `agents/graph-wiki-agent/pyproject.toml`. This is the minimum safe version for multi-tool fan-out work. `>=1.5.0` is also fine if you want the tracing improvement, but it is not load-bearing.

**`typer` — optional bump to `>=0.26.0`:**

0.26.0 (released today) vendors Click internally. The breaking change (removing Click-object extraction) does not affect this codebase — `cli.py` does not access `app.registered_groups[0].typer_instance` or any Click internals. The `add_typer`, `@app.command`, and `Typer(no_args_is_help=True)` patterns are unchanged. Vendoring Click eliminates any future Click version conflict if another package also depends on Click.

**Recommendation:** Bump to `>=0.26.0` opportunistically in the hygiene phase — zero risk, eliminates a future dependency conflict vector. If hygiene phase scope is tight, leave at `>=0.25.1`; it is not a blocker.

**`mcp` and `langchain-core` — no change:** Both are already at current stable versions.

---

## Recommended Dependency Changes for v1.7

### `agents/graph-wiki-agent/pyproject.toml`

```toml
dependencies = [
    "wiki-io",
    "model-adapter",
    "subagent-runtime",
    "workspace-io",
    "graph-io",           # ADD — v1.7 integration dep
    "bm25s==0.3.8",
    "mcp>=1.27.1",
    "langchain-aws>=1.4.7",   # BUMP from >=1.4.6 — invalid tool_use block fix
    "langchain-core>=1.4.0",  # ADD explicit pin (was transitive)
    "typer>=0.26.0",          # BUMP from >=0.25.1 — optional, vendored Click
    "pydantic>=2.0",
]

[tool.uv.sources]
wiki-io          = { workspace = true }
model-adapter    = { workspace = true }
subagent-runtime = { workspace = true }
workspace-io     = { workspace = true }
graph-io         = { workspace = true }   # ADD
```

**Summary of changes:**

| Change | Type | Reason |
|--------|------|--------|
| `graph-io` workspace dep | **Required add** | v1.7 integration — librarian tools, scanner, ingestor, `graph` subcommand all import `graph_io.*` |
| `langchain-aws>=1.4.7` | **Required bump** | Strip invalid `tool_use` blocks; load-bearing for multi-tool librarian |
| `langchain-core>=1.4.0` | **Explicit pin (recommended)** | Makes the floor visible and stable; was previously transitive-only |
| `typer>=0.26.0` | **Optional bump** | Vendored Click; zero breakage risk; eliminates future conflict vector |

---

## What NOT to Add

| Avoid | Why | What to Use Instead |
|-------|-----|---------------------|
| `langchain-openai` | Routes to direct OpenAI API; violates Bedrock-only constraint; will silently incur non-Bedrock costs if credentials happen to be present | `langchain-aws` (`ChatBedrockConverse` via `make_llm()`) |
| `langgraph` | Heavyweight state-machine framework; deliberately not adopted in this project's stack design | In-house `SubagentPool` (asyncio.Semaphore fan-out) |
| `deepagents` | Evaluated and rejected for v1 (see CLAUDE.md §2 stack-departure note) | In-house `SubagentPool` |
| `langchain-anthropic` | Direct Anthropic API; excluded by Bedrock-only constraint | `langchain-aws` only |
| `ChatBedrock` (legacy) | Deprecated; does not use Converse API; missing model support | `ChatBedrockConverse` via `make_llm(role)` |
| `strip-ansi` / `ansi2text` | Post-hoc ANSI stripping; symptom treatment for test output; already solved by `NO_COLOR=1 TERM=dumb` env injection | Existing `_PLAIN_HELP_ENV` pattern in test files |
| `pydantic` (new version) | Already pinned `>=2.0`; no change needed | Existing pin |
| `sqlite-utils` | General SQLite helper; graph-io already owns `store.py` with tight, purpose-built layer | Raw `sqlite3` (existing graph-io pattern) |
| `rich` (explicit dep) | Rich is already a transitive dep via Typer; adding it explicitly would create a version split risk | Use `typer.echo()` for output; use `NO_COLOR` in tests |
| `structlog` / `loguru` | Structured logging libraries; the project uses JSONL trace files, not a logging framework | Existing JSONL trace writer in subagent-runtime |

---

## New Module Map for v1.7 (no new packages — only new modules within existing packages)

| New Module | Package | What it does |
|------------|---------|-------------|
| `graph_wiki_agent/tools/graph_tools.py` | `graph-wiki-agent` | `@tool`-decorated callables wrapping `graph_io.queries.*`; opens read-only conn via `workspace_io.resolve()` |
| `graph_wiki_agent/commands/graph.py` | `graph-wiki-agent` | `graph_build`, `graph_describe`, `graph_query` command implementations |
| `agents/graph-wiki-agent/tests/unit/test_cli_graph.py` | `graph-wiki-agent` (tests) | `graph --help`, `graph build --help`, etc. using `_PLAIN_HELP_ENV` pattern |

No new packages in any `pyproject.toml` beyond the dependency table changes above.

---

## Sources

- `packages/graph-io/src/graph_io/queries.py` — confirmed Python API surface: `find`, `callers`, `callees`, `imports`, `describe_package`, `describe_path`, `describe_repository`, `describe_domain`, `list_packages`, `list_domains`, `list_entry_points`, `list_test_suites`, `tests_for_package`, `tests_for_domain`, `domain_references`, `domain_depends_on`, `cross_cutting_packages`, `exported_by`, `exports`, `imported_by`
- `packages/graph-io/src/graph_io/store.py` — `read_only_connect(db_path)` confirmed
- `packages/graph-io/src/graph_io/cli/_format.py` — `render(records, fmt)` confirmed importable independently of CLI
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — existing `ingest` sub-app pattern (`typer.Typer()` + `app.add_typer()`) confirmed
- `agents/graph-wiki-agent/tests/unit/test_cli_help.py` — `_PLAIN_HELP_ENV` pattern confirmed; 3/3 tests PASSED on live run
- `agents/graph-wiki-agent/pyproject.toml` — current dependency list confirmed
- `packages/model-adapter/src/model_adapter/loader.py` — `make_llm(role)` pattern confirmed; `_GuardedChatBedrockConverse` subclass; no changes needed for v1.7
- `.planning/STATE.md` — `260521-ans` deferred item confirmed; ANSI tests already passing with `NO_COLOR` fix
- PyPI: `langchain-aws` — current: 1.4.6 installed, 1.5.0 latest; 1.4.7 confirmed strip-invalid-tool-use-block fix — https://pypi.org/project/langchain-aws/
- PyPI: `langchain-core` — current: 1.4.0; latest: 1.4.0 — https://pypi.org/project/langchain-core/
- PyPI: `typer` — current: 0.25.1 installed, 0.26.0 released 2026-05-26 (today); vendored Click breaking change confirmed to not affect this codebase — https://pypi.org/project/typer/
- PyPI: `mcp` — current: 1.27.1; latest: 1.27.1 — no change — https://pypi.org/project/mcp/
- GitHub API: langchain-aws releases — 1.4.7 release notes: "strip streaming-only fields from invalid tool_use blocks"; 1.5.0: "use resolved base model for Bedrock tracing"
- Typer release notes 0.26.0: "vendors Click; removes Click-object extraction API; add_typer / @command / Typer() constructor unchanged" — https://typer.tiangolo.com/release-notes/

---

*Stack research for: v1.7 graph-io Integration & Wiki Hygiene*
*Researched: 2026-05-26*
