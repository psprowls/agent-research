# Phase 38: `graph-wiki-agent graph` Subcommand — Research

**Researched:** 2026-05-26
**Status:** Research complete; ready for planning.

> Read alongside `38-CONTEXT.md` — this RESEARCH.md does NOT restate D-01..D-09.
> Its job is to surface implementation-level facts the planner needs that are not in CONTEXT.md.

## RESEARCH COMPLETE

---

## 1. Existing Typer subapp + in-process import pattern (the structural template)

**The `ingest` subapp at `cli.py:556-561`** is the canonical pattern that Phase 38's `graph` subapp will mirror:

```python
ingest_app = typer.Typer(help="Ingest a source file or work item into the wiki.")
app.add_typer(ingest_app, name="ingest")

@ingest_app.command(name="source")
def ingest_source(path: Path = typer.Argument(...), workspace: str = typer.Option(""), ...) -> None:
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_ingest_source(path, workspace_path))
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
```

Phase 38's `graph_app` will be a `typer.Typer(help=...)` registered via `app.add_typer(graph_app, name="graph")` — same single line. The 3 subcommands (`build`, `describe`, `query`) become `@graph_app.command()`-decorated functions in `commands/graph.py`. `graph describe` is itself a nested `typer.Typer()` (a "subapp within a subapp") so that `describe package <name>`, `describe path <path>`, etc. work as 6 distinct sub-sub-commands (D-08). Typer supports nested subapps via the same `add_typer` call recursively.

**No async required for Phase 38.** Unlike `ingest`/`scan`/`query` which call `asyncio.run(...)`, `cg`'s `ops_update.run` / `q_find.run` / `q_describe_*.run` functions are SYNCHRONOUS argparse-style entry points. The agent's Typer commands invoke them directly without `asyncio.run`. This simplifies the trace-wrapper plumbing (no coroutine/finally interleaving).

## 2. The `cg` SUBCOMMAND CLI shape — argparse `add_arguments` + `run(args)` contract

Every `cg` subcommand module (`packages/graph-io/src/graph_io/cli/<name>.py`) follows the same shape:

```python
def add_arguments(parser: argparse.ArgumentParser) -> None: ...
def run(args: argparse.Namespace) -> int: ...
```

The dispatch loop in `packages/graph-io/src/graph_io/cli/main.py:88-92` registers each module as `sp.set_defaults(_module=mod, _parser=sp)` so `args._module` and `args._parser` are set on the parsed Namespace before `run(args)` is called.

**This matters for D-07's manually-constructed Namespace:** `q_find.py:41` calls `args._parser.error(...)` when no filter is provided. The agent constructs a Namespace WITHOUT a `_parser` attribute → `args._parser.error(...)` would raise AttributeError. The agent's `cg_find`-wrapping commands MUST avoid the no-args path (the agent always supplies at least one filter, or fails fast with a Typer error BEFORE calling `q_find.run`).

**Field shape per module (verified by reading each file):**

| Module | Required Namespace fields beyond `repo`, `workspace`, `fmt`, `mode` |
|---|---|
| `ops_update` | `full: bool` |
| `q_find` | `name: str \| None`, `kind: str \| None`, `in_package: str \| None`, `_parser` (avoid no-args path) |
| `q_describe_package` | `name: str` |
| `q_describe_path` | `path: str` |
| `q_describe_repo` | (no extras) |
| `q_describe_domain` | `name: str` |
| `q_describe_suite` | `name: str` |

**Mandatory fields on every Namespace:** `repo: Path`, `workspace: Path` (resolved upfront), `fmt: str = "human"`, `mode: str = "workspace"`, `_module=<the_module>`, `_parser=<unused_unless_q_find_no_args>`.

The agent constructs `argparse.Namespace(**fields)` and calls `module.run(args)`. The return value (int exit code) is mapped to `typer.Exit(code=N)` when non-zero.

## 3. **CRITICAL GAP**: `q_describe_entry_point.py` does NOT exist

`packages/graph-io/src/graph_io/cli/` has 5 describe modules (`q_describe_package`, `q_describe_path`, `q_describe_repo`, `q_describe_domain`, `q_describe_suite`) — **no `q_describe_entry_point.py`**. The underlying query function `queries.describe_entry_point(conn, name=...)` DOES exist (`queries.py:475`), but is not exposed via `cg` CLI.

CONTEXT D-08 lists `graph describe entry-point <name>` as one of the 6 sub-sub-commands. CONTEXT canonical_refs (line 112) says: "Phase 38 imports all 6 and dispatches based on the user-specified kind."

**Planner's two options:**

- **Option A: Create `q_describe_entry_point.py` in graph-io as a Wave-1 prerequisite.** Mirror `q_describe_package.py` exactly (positional `name` arg, identical error handling, `queries.describe_entry_point(conn, name=args.name)`). Add it to `_SUBCOMMANDS` dict in `main.py`. Net effect: `cg describe-entry-point <name>` becomes a real CLI command for the first time. **Recommended** — keeps the Phase 38 in-process import pattern uniform across all 6 kinds and adds a missing parity feature to `cg` as a side effect.

- **Option B: Special-case entry-point in the agent adapter.** The dispatch table in `commands/graph.py` calls `queries.describe_entry_point(conn, name=...)` directly for `kind=="entry_point"` (bypassing the cg CLI layer for that one kind only). Net effect: smaller diff (no graph-io changes), but breaks the uniform "always go through `cg.cli.<module>.run`" pattern.

Recommend Option A. The added `q_describe_entry_point.py` is ~30 lines (mirror `q_describe_package.py`) and brings cg's CLI parity to all 6 kinds at once.

## 4. Trace JSONL: filename, schema, and the OBS-04 lenient renderer

**The agent already writes trace JSONL in 3 places** — Phase 38 adds a 4th:

| Writer | Filename pattern | Where |
|---|---|---|
| `SubagentPool.run_all` | `<unix_ts>_<uuid8>.jsonl` | `pool.py:146` |
| `commands/query.py` query summary | `query_<query_id>.jsonl` | `query.py:1176` |
| `commands/ingest.py` ingest trace | `ingest_<ts>_<uuid8>.jsonl` | `ingest.py:448` |
| **Phase 38: graph commands** | `<ISO8601-Z>-<command>.jsonl` per D-01 | NEW |

All use `wiki / ".graph-wiki" / "traces" / <name>.jsonl`. Trace renderer at `cli.py:282-426` reads any file matching that location; OBS-04 D-03 (`_is_groupable`, `KNOWN_SCHEMA_VERSION`, lenient unknown-event handling) ensures the renderer gracefully handles records with `event` keys it has never seen.

**Re-using the existing schema (D-02):** The Phase-9 record shape is (per `subagent_runtime/trace_io.py:68-83`):

```python
{
    "schema_version": 1,
    "role": str,           # e.g. "graph_build"
    "model_id": str,       # required by trace_io but optional semantically — Phase 38 uses "-" for proxy commands
    "prompt_hash": None,
    "item_id": str,        # the command name + invocation marker
    "status": "success"|"error",
    "latency_ms": int,
    "tokens_in": int|None,
    "tokens_out": int|None,
    "cost_usd": float|None,
    "timestamp": "YYYY-MM-DDTHH:MM:SSZ",
    # optional:
    "event": str,          # NEW for Phase 38 — graph_build_start, graph_build_complete, graph_describe, graph_query
    "error": str,
}
```

**Phase 38 proxy records (D-03)**: For `graph describe` and `graph query` (no LLM calls), the writer OMITS `model_id` (or sets to `"-"`), OMITS `tokens_in`/`tokens_out`/`cost_usd` (rather than null/zero, per D-03's "honest" requirement). Add `command: str`, `args: dict` (echoed flags), `exit_code: int`, `duration_ms: int`, and optionally `row_count: int` for `query`.

**Phase 38 `graph build` records:** May include `model_id` IF `--model` is passed AND the build path actually invokes a model. **Important fact:** `ops_update.run()` does NOT invoke an LLM (verified by reading `packages/graph-io/src/graph_io/cli/ops_update.py` — it calls `graph_io.update.run(args.repo, workspace=args.workspace, full=args.full)` and `graph_io.update` is pure Python: tree-sitter + sqlite, no Bedrock calls). The `--model` flag on `graph build` is therefore **purely informational** — it records the model in the trace for parity with future LLM-using builds but does not actually use the model. The planner should either:
- (a) Reject `--model` with a clear error "graph build does not invoke a model in v1.7" — strict but honest, OR
- (b) Accept `--model`, write it to the trace record's `model_id` field, but emit a stderr note "note: --model is recorded but unused — graph build does not invoke an LLM in v1.7."

Recommend (b): preserves CONTEXT's "Mirror CLI 1:1 (D-04)" promise — the MCP tool accepts `model: str | None` whether or not the model is used. Trace records remain forward-compatible: when a future phase wires an LLM call into update (e.g. for embedding regeneration), `model_id` is already in the record shape.

**One file per invocation, write mode `"w"` (D-01):** Open with `open(path, "w")` (not `"a"`) so each invocation overwrites any prior file with the same timestamp (effectively impossible at 1-second resolution, but defensive). Records are typically 1-3 per invocation (`graph_build_start` + `graph_build_complete`, or a single `graph_describe`/`graph_query`).

**Filename per D-01:** Use `datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")` (colons → `-` for filesystem safety on Windows/macOS). Example: `2026-05-26T17-03-22Z-graph-build.jsonl`. Use the SAME timestamp for `started_at` (ISO with colons) inside the record and the filename's collision-prevention marker.

## 5. MCP tool input/output shapes — Pydantic models follow the wiki_* pattern

**Every existing `wiki_*` tool** (lines 84-446 of `mcp/server.py`) has 3 declarations:
1. `class FooInput(BaseModel)` with `model_config = ConfigDict(extra='forbid')` (strict input)
2. `class FooOutput(BaseModel)` — the structured return shape
3. `@mcp.tool(name="foo", description="...")` decorated async function

Phase 38's 3 MCP tools follow the same pattern. **Input models per D-04:**

```python
class GraphBuildInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    full: bool = Field(False, description="Full rebuild (else incremental)")
    trace: bool = Field(False, description="Write JSONL trace to .graph-wiki/traces/")
    model: str | None = Field(None, description="Model ID override (recorded in trace; not used in v1.7)")
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")

class GraphDescribeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal["package", "path", "repository", "domain", "entry_point", "test_suite"] = Field(..., description="Entity kind")
    identifier: str | None = Field(None, description="Identifier; required for all kinds except 'repository'")
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")

class GraphQueryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(None, description="Node name (exact match)")
    kind: str | None = Field(None, description="Node kind (one of the cg find --kind choices)")
    in_package: str | None = Field(None, description="Filter to nodes in named package (case-insensitive)")
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")
```

**Output models** — return the rendered string + exit code + the parsed records when possible. Recommend a uniform shape:

```python
class GraphCommandOutput(BaseModel):
    status: str                # "success" | "error"
    exit_code: int
    stdout: str                # captured human-format render
    stderr: str                # captured error text, if any
    trace_path: str | None     # absolute path of trace file when trace=True
```

**One uniform output class** keeps the 3 tool signatures simple and matches DeepAgents CLI's "return structured payload" pattern. Each tool's docstring documents what `stdout` contains for that tool. Alternatives (per-tool typed outputs that parse `desc.name`, `desc.uri`, etc.) are more work and bind the MCP surface to graph-io internals — defer.

**Workspace resolution at server boundary:** Mirror `wiki_query` (server.py:126): `vault = Path(input.workspace_path) if input.workspace_path else None`. The agent-side adapter (Section 6) resolves the workspace from the env var when `vault is None`.

**stdout/stderr capture from cg modules:** cg modules use `print(...)` for human output and `print(..., file=sys.stderr)` for errors. MCP tools must capture both. Use `io.StringIO` + `contextlib.redirect_stdout` + `redirect_stderr` around the `module.run(args)` call. This is necessary because the MCP server's `_StdoutGuard` (server.py:31-48) BLOCKS any stdout write — letting cg's `print()` reach stdout would crash the server. **Capturing is mandatory for the MCP path, optional for the CLI path** (the CLI legitimately writes to stdout).

## 6. Shared adapter pattern — single helper, 3 callers (CLI + MCP × build/describe/query)

The cleanest factoring places ONE helper function per cg command in `commands/graph.py`:

```python
# commands/graph.py — agent-side adapter (NEW FILE)

import argparse, contextlib, datetime, io, json, sys, time
from pathlib import Path
from typing import Any

from graph_io.cli import ops_update, q_find
from graph_io.cli import (
    q_describe_package, q_describe_path, q_describe_repo,
    q_describe_domain, q_describe_suite,
)
# Option A from Section 3:
from graph_io.cli import q_describe_entry_point
from workspace_io.config import resolve as resolve_workspace

# Maps Phase 38 sub-sub-command name (kebab-case from CLI; snake_case from MCP enum)
# to the cg CLI module that handles the describe.
_DESCRIBE_DISPATCH = {
    "package":     (q_describe_package, "name"),
    "path":        (q_describe_path,    "path"),
    "repository":  (q_describe_repo,    None),
    "domain":      (q_describe_domain,  "name"),
    "entry_point": (q_describe_entry_point, "name"),
    "test_suite":  (q_describe_suite,   "name"),
}

def _build_namespace(module, *, repo: Path, workspace: Path, **extras) -> argparse.Namespace:
    """Construct a Namespace satisfying the cg module's parsed-args contract."""
    return argparse.Namespace(
        repo=repo,
        workspace=workspace,
        fmt="human",
        mode="workspace",
        _module=module,
        _parser=None,  # only q_find no-args uses this; agent never takes that path
        **extras,
    )

def _capture_run(module, args: argparse.Namespace) -> tuple[int, str, str]:
    """Call cg module.run(args) with stdout/stderr captured. Returns (exit_code, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    exit_code = 1
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            exit_code = module.run(args)
        except SystemExit as exc:
            # Some cg modules call sys.exit() directly (rare; argparse via _parser.error).
            exit_code = int(exc.code) if exc.code is not None else 0
    return exit_code, out.getvalue(), err.getvalue()
```

`_capture_run` is the SAME helper for CLI and MCP paths. The CLI command wrapper re-emits captured stdout/stderr via `typer.echo`; the MCP tool packs them into the `GraphCommandOutput`.

## 7. Where the workspace and repo paths come from

Both the CLI (`--workspace`) and MCP (`workspace_path`) accept an optional path. Resolution chain:

1. Explicit arg (CLI flag / MCP field): use that.
2. Else: `os.environ.get("GRAPH_WIKI_WORKSPACE")` (env var fallback).
3. Else: error — surface a typer.Exit / MCP error.

The agent's `cg` Namespace requires BOTH `repo` and `workspace`. Recommendation:

```python
workspace = Path(workspace_arg).resolve() if workspace_arg else Path(os.environ["GRAPH_WIKI_WORKSPACE"]).resolve()
repo = workspace_io.config.resolve(workspace, require_manifest=False).repo  # or .workspace.parent
```

Verify by reading `packages/workspace-io/src/workspace_io/config.py` — `resolve()` returns a `WorkspaceConfig` with both `.workspace` and `.repo` attributes. The planner reads that file once to confirm the exact field names.

**Trace dir construction:** `trace_dir = wiki / ".graph-wiki" / "traces"`. Mirror `query.py:1174-1175`:
```python
trace_dir = wiki / ".graph-wiki" / "traces"
trace_dir.mkdir(parents=True, exist_ok=True)
```

## 8. The `--model` flag on `graph build` — practical scope

CONTEXT D-04 says `graph_build` accepts `model: str | None`. CONTEXT discretion section (line 73): "Whether `graph build`'s `--model` flag accepts arbitrary strings or validates against a known list — planner picks (consult `models.toml` for the role list)."

**`models.toml` roles** (verified at `packages/model-adapter/src/model_adapter/models.toml`): `orchestrator`, `librarian`, `scanner`, `ingestor`, `code_reader`, `synthesizer`. No "graph_builder" role exists.

**Recommendation:** Accept `--model` as a free-form string (no `make_llm` call in `graph build`; the model is purely a trace field per Section 4 above). Document in `--help` text: "Model ID recorded in trace; not actually invoked in v1.7." This keeps the CLI flag mirrored at the MCP boundary (D-04) without misleading users.

If/when a future phase wires LLM-driven embedding regeneration into `cg update`, the flag becomes meaningful and the validator can be added then. v1.7 stays minimal.

## 9. Error handling chain — typer.Exit ↔ cg exit_codes

`cg` modules return `graph_io.exit_codes.{SUCCESS, GENERIC, NOT_INITIALIZED, NOT_IN_GIT_REPO, UPDATE_IN_PROGRESS, SCHEMA_MISMATCH}` (verified by `grep "from graph_io import exit_codes"` in cg modules). Phase 38's Typer commands map these:

```python
exit_code, _stdout, _stderr = _capture_run(ops_update, args)
typer.echo(_stdout, nl=False)
if _stderr:
    typer.echo(_stderr, err=True, nl=False)
if exit_code != 0:
    raise typer.Exit(code=exit_code)
```

This faithfully surfaces cg's exit codes through the agent CLI (matching SC#2/SC#3's "mirrors cg semantics"). The MCP path doesn't raise — it packs `exit_code` into the output model and the MCP host decides what to do with non-zero.

## 10. Per-D-09 case-conversion at the Typer boundary

CONTEXT specifics (line 146): "D-08 sub-sub-command names should use kebab-case to match Typer convention (`entry-point`, `test-suite`) but the underlying `kind` arg passed to MCP D-09 should be snake_case (`entry_point`, `test_suite`)."

Typer command names are kebab-case (`@graph_describe_app.command(name="entry-point")`). The MCP `kind` enum is snake_case. The dispatch table key in `_DESCRIBE_DISPATCH` uses snake_case (Python identifier-friendly). At the CLI boundary, the per-kind command function calls the dispatch with the snake_case key directly (since each Typer sub-sub-command is its own function and already knows its kind).

```python
@graph_describe_app.command(name="entry-point")
def graph_describe_entry_point(name: str, workspace: str = "") -> None:
    _run_describe(kind="entry_point", identifier=name, workspace_arg=workspace)
```

## 11. Naming conflict: `query` vs `graph query`

The top-level `query` Typer command (`cli.py:428`) is the wiki-query (BM25+embedding+librarian) command — distinct from `graph query` (cg find). They share the verb `query` at different levels: top-level is wiki; under `graph` namespace is graph.

This is intentional per CONTEXT — both surfaces are independent. The agent's `--help` makes the distinction clear:
- `graph-wiki-agent query "..."` → wiki Q&A (existing)
- `graph-wiki-agent graph query --name foo` → graph node lookup (NEW Phase 38)

No code conflict — different Typer registrations. Just a docs note in `graph_app.help` to disambiguate.

## 12. Repo/cross-cutting gotchas

- **Phase 35 in-flight commits** touched `cli.py` (the existing trace renderer). Phase 38 does NOT modify `cli.py:92-426` (the renderer functions or the `trace` command). It ADDS one line at the bottom: `app.add_typer(graph_app, name="graph")` alongside the existing `app.add_typer(ingest_app, name="ingest")`. Conflict-free if Phase 35 lands first.

- **Phase 37 in-flight commits** introduce `graph_tools.py` in `agents/graph-wiki-agent/src/graph_wiki_agent/` (the **librarian-side** graph tools, `cg_*` prefix). Phase 38 creates `commands/graph.py` (the **CLI-side** graph commands, `graph_*` prefix). Different files, different namespaces, **no overlap** — CONTEXT line 95 explicitly locks this. The agent's `pyproject.toml` already has `graph-io` as a dependency from Phase 37, so Phase 38 doesn't need to bump it.

- **`langchain-aws>=1.4.7` is already pinned** in the agent's `pyproject.toml` (verified by reading the file). Phase 38 does NOT touch pyproject.

- **`_StdoutGuard` (server.py:31-48)** will crash if any cg module's `print()` reaches stdout in the MCP path. The capture pattern in Section 5/6 is MANDATORY for the MCP tools. Unit tests should assert that calling the 3 MCP tool functions from a test that has the guard installed does NOT raise.

- **`sys.exit()` from cg modules.** Most `cg` modules return an int (e.g. `return exit_codes.SUCCESS`). A few — specifically `q_find.py:41` — invoke `args._parser.error(...)` which calls `sys.exit(2)`. The agent's adapter NEVER takes that path (it pre-validates that at least one filter is supplied before constructing the Namespace), so `_capture_run` doesn't strictly need to catch SystemExit — but the catch is included as defensive code (Section 6) per CONTEXT specifics line 147.

- **`workspace_io.config.resolve(require_manifest=...)`:** `cg`'s main.py:99 passes `require_manifest=True if args.mode == "workspace" else False`. The agent's adapter sets `mode="workspace"` and calls `resolve(repo, require_manifest=True)`. **However**, Phase 38's commands MAY want to allow workspace-less paths (e.g., for `graph describe` against a workspace that was just created but hasn't been manifest-tagged yet). Recommend `require_manifest=False` in the agent adapter — strictly more permissive than `cg` itself. The downstream `graph_dir(workspace) / "code.db"` check fires anyway if the graph isn't built, so usability isn't degraded.

## 13. Test strategy

### Existing test patterns to mirror

| Test surface | Pattern | Example |
|---|---|---|
| Typer CLI invocation | `typer.testing.CliRunner` + `result = runner.invoke(app, [...])` | `agents/graph-wiki-agent/tests/unit/test_cli_*.py` |
| In-process cg dispatch | Construct `argparse.Namespace`, call `module.run(args)` directly, assert `exit_codes.SUCCESS` | `packages/graph-io/tests/test_cli_*.py` |
| MCP tool surface | Direct call of the `@mcp.tool` async function with a Pydantic Input instance | `agents/graph-wiki-agent/tests/unit/test_mcp_*.py` (one exists for `wiki_query`) |
| Trace file write | Inspect `<tmp>/.graph-wiki/traces/` for the expected filename + parse JSONL | `agents/graph-wiki-agent/tests/unit/test_query_*.py` (query summary trace test) |

### Tests Phase 38 needs

| Surface | Test |
|---|---|
| `graph --help` exits 0 listing exactly 3 subs (SC#1) | `CliRunner().invoke(app, ["graph", "--help"])` → assert `result.exit_code == 0` and `"build"`, `"describe"`, `"query"` in `result.output`, no others |
| `graph build --help` shows only `--full`, `--trace`, `--model`, `--workspace` (SC#2) | parse help text; assert flag set |
| `graph build` invokes `ops_update.run` with `full=False` by default | mock `ops_update.run`, run `graph build`, assert called once with `args.full == False` |
| `graph build --full` sets `args.full == True` | mock and assert |
| `graph build --trace` writes a `.graph-wiki/traces/<ts>-graph-build.jsonl` file | tmp wiki path, invoke, glob for file, parse JSONL, assert `event == "graph_build_complete"` |
| `graph build --model <id>` writes `model_id` to the trace record | invoke with --model, assert record contains `"model_id": "<id>"` |
| `graph describe package <name>` dispatches to `q_describe_package.run` | mock module.run, assert Namespace contains `name=<name>` |
| `graph describe path <path>` dispatches to `q_describe_path.run` (uses `path` attr, not `name`) | per Section 2 field shape |
| `graph describe repository` calls `q_describe_repo.run` (no identifier needed) | invoke without positional arg |
| `graph describe entry-point <name>` dispatches to `q_describe_entry_point.run` | requires Option A from Section 3 |
| `graph describe domain <name>` / `test-suite <name>` mirror package shape | parametrize |
| `graph query --name foo` dispatches to `q_find.run` with `args.name == "foo"` | mock and assert |
| `graph query --kind class --in-package foo-pkg` mirrors Phase 36 args | full flag exercise |
| `graph query` with no filters fails fast at Typer layer (not at cg parser) | invoke without any flag; assert non-zero exit with usage error |
| `graph describe` (no kind) shows help | invoke without sub-sub-command; assert kind list |
| trace record for `graph describe` OMITS `cost_usd`, `tokens_in`, `tokens_out`, `model_id` (D-03) | parse JSONL; assert those keys are absent |
| trace record for `graph query` OMITS the same fields | parametrize |
| trace renderer reads new event values gracefully | existing OBS-04 D-03 test already covers this; Phase 38 just must not bump `schema_version` |
| `graph_build` MCP tool returns success on a valid workspace | direct call of the async tool function |
| `graph_describe` MCP tool with `kind="bogus"` is rejected by Pydantic Literal validation | assert `ValidationError` |
| `graph_describe(kind="repository", identifier=None)` succeeds (identifier ignored) | assert success |
| `graph_describe(kind="package", identifier=None)` raises a clear error | the dispatch requires an identifier for non-repository kinds |
| `graph_query` MCP tool with all None filters returns clean error (mirrors cg behavior) | the adapter pre-validates and returns `exit_code=2` with stderr message |
| MCP `_StdoutGuard` not tripped by `graph_*` tools | tools must capture cg's `print()` via redirect_stdout |
| Trace path returned in MCP output when `trace=True` | parse `output.trace_path` and confirm file exists |
| All 3 `graph_*` MCP tools appear in `wiki_ping`/discovery | invoke `mcp.list_tools()` or equivalent; assert names |

### Out of scope for Phase 38 tests
- Cost tracking under `--model`: cost is unmeasurable without an actual LLM call. Phase 38 records `model_id` only as a string.
- Integration test against real Bedrock: not needed; `graph build/describe/query` are pure Python.

## 14. Open Questions / Planner's Discretion (research data attached)

These are the items CONTEXT.md left for the planner. Research data is attached.

1. **ISO timestamp format for the trace filename** — CONTEXT discretion line 72 suggests `YYYY-MM-DDTHH-MM-SSZ`. Recommend: `datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")`. UTC-stamped, sortable lexicographically, filesystem-safe (no colons).

2. **`--model` validation** — Pure pass-through string (Section 8). Document as "recorded in trace; not invoked in v1.7."

3. **Event values for the 4 new event kinds (D-02)** — Recommend:
   - `graph_build_start` (emitted before `ops_update.run`)
   - `graph_build_complete` (emitted after, with `exit_code`)
   - `graph_describe` (single record per invocation)
   - `graph_query` (single record per invocation)
   Snake_case to match existing Phase 9 OBS-04 convention.

4. **Where helpers live** — `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` is the single home for the Typer command functions AND the `_build_namespace` / `_capture_run` / `_write_trace_record` / `_DESCRIBE_DISPATCH` helpers (per CONTEXT specifics line 52). One file, ~250 lines. No `helpers/` subdir.

5. **Error mapping from `ops_update.run` non-zero exits** — `raise typer.Exit(code=exit_code)` (mirrors cg's exit codes faithfully; see Section 9).

6. **MCP error when graph DB absent** — Mirror `wiki_query`'s error pattern (`raise RuntimeError(f"...")` inside the tool body — surfaces as a structured MCP error per server.py:356). For `graph_build` against a stale workspace, the error comes from `ops_update.run` returning `NOT_IN_GIT_REPO` or similar; the MCP tool packages it in `exit_code` + `stderr` and the host sees a normal (non-error) MCP response.

7. **`q_describe_entry_point.py` creation** — **Recommended Option A** (Section 3): create the cg-side module as a Wave-1 prerequisite plan. ~30 lines, mirrors `q_describe_package.py` exactly.

## 15. Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Phase 37 in-flight conflicts with Phase 38 over `pyproject.toml` | low | Phase 37 modifies `dependencies` already (graph-io, langchain-aws); Phase 38 does NOT touch pyproject. Disjoint git diffs. |
| Phase 35 in-flight modifies `cli.py` | medium | Phase 35 modifies init/lint flows in `cli.py`. Phase 38 adds ONE line near the bottom (`app.add_typer(graph_app, name="graph")`). 3-way merge resolves cleanly. |
| `q_describe_entry_point.py` is created in graph-io (Option A) — modifies a package outside the agent | low | Single new file mirroring `q_describe_package.py` + one line added to `_SUBCOMMANDS` in `main.py`. Tests in `packages/graph-io/tests/` parametrize over kinds; new test for entry-point added. |
| `_StdoutGuard` trips during MCP tool execution | medium without capture; low with capture | All 3 MCP tools wrap `cg` calls in `contextlib.redirect_stdout(StringIO())`. Unit test asserts `_StdoutGuard.write` is NOT called during a normal tool call. |
| cg `args._parser.error(...)` fires via the no-args path for q_find | low | Agent's `graph query` Typer command pre-validates that at least one of `--name`/`--kind`/`--in-package` is supplied. Failing fast at Typer layer with `typer.Exit(code=2)` and message. |
| Trace record writer fails with OSError (disk full / permission) | low | Wrap in try/except OSError + logger.warning. Mirror `query.py:1194-1195`. NEVER raise from the trace path. |
| `graph_dir(workspace) / "code.db"` doesn't exist when `graph describe` is called | medium | `cg`'s own `read_only_connect` raises `GraphNotInitializedError`; the cg module catches and returns `exit_codes.NOT_INITIALIZED`. Agent surfaces via `typer.Exit(code=<NOT_INITIALIZED>)` + stderr message. |
| MCP tool input rejects `kind="bogus"` via Literal validation | high (this is the GOOD case) | Pydantic raises `ValidationError` before the tool body runs; the MCP host receives a structured input-validation error. No further mitigation. |
| Concurrent invocations write trace files with the same filename | low | ISO-second resolution + per-invocation file (write mode `"w"`) — collision requires 2 invocations in the same wall-clock second, which is rare. If it happens, the later write overwrites; acceptable for trace. |

## 16. Files the Planner Will Touch

**Net-new:**
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — Typer subapp + describe sub-sub-app + 6 dispatch functions + Namespace builder + capture helper + trace writer + `_DESCRIBE_DISPATCH` table.
- `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` — CLI surface tests (Typer CliRunner).
- `agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py` — MCP tool tests (direct async call).
- **(Option A from Section 3)** `packages/graph-io/src/graph_io/cli/q_describe_entry_point.py` — mirrors `q_describe_package.py` shape; `cg describe-entry-point <name>` becomes available.
- **(Option A)** `packages/graph-io/tests/test_cli_describe_entry_point.py` — small parity test.

**Modified:**
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — add `app.add_typer(graph_app, name="graph")` (1 line near bottom, parallel to `ingest_app` at line 561).
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` — add 3 new MCP tools (`graph_build`, `graph_describe`, `graph_query`) at bottom, before `def main()`. Each ~30 lines (Pydantic models + async tool function).
- **(Option A)** `packages/graph-io/src/graph_io/cli/main.py` — add `q_describe_entry_point` to imports and `_SUBCOMMANDS` dict.

**Unchanged (read-only references):**
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:92-426` — trace renderer untouched.
- `packages/graph-io/src/graph_io/queries.py` — `describe_entry_point` already exists; Phase 38 just exposes it.
- `packages/graph-io/src/graph_io/cli/ops_update.py`, `q_find.py`, `q_describe_*.py` — called via in-process imports; not modified.
- `packages/subagent-runtime/src/subagent_runtime/trace_io.py` — `write_trace_record` is the existing schema; Phase 38 emits records of the same shape directly (without calling this helper, since the helper is tuned to SubagentPool's per-task records — Phase 38's records are command-level and include extra fields like `event`, `command`, `args`, `exit_code`, `duration_ms`).

## 17. Wave Layout Recommendation

This phase splits cleanly into 2 plans (similar to Phase 37's `tool factory + integration` split):

- **Plan 38-01 (Wave 1, autonomous):** Create `commands/graph.py` with Typer subapp + 3 commands (`build`, `describe`, `query`) + describe sub-sub-app + Namespace builder + capture helper + trace writer + `_DESCRIBE_DISPATCH` table. **Also creates `q_describe_entry_point.py`** in graph-io (Option A from Section 3) — this is a Wave 1 prerequisite for the 6-kind describe dispatch. Wires `app.add_typer(graph_app, name="graph")` in `cli.py`. CLI-side unit tests in `tests/unit/test_commands_graph.py`. **Does NOT touch `mcp/server.py`.**

- **Plan 38-02 (Wave 2, depends on 38-01, autonomous):** Register 3 MCP tools (`graph_build`, `graph_describe`, `graph_query`) in `mcp/server.py`. Each tool imports and reuses helpers from `commands/graph.py` (the `_capture_run` + `_DESCRIBE_DISPATCH` + trace writer). MCP-side unit tests in `tests/unit/test_mcp_graph_tools.py`. **Does NOT touch `commands/graph.py`** (Plan 01's deliverable is stable by then).

The wave split keeps the CLI surface testable in isolation before adding the MCP wrapper complexity. Both plans are bounded (~250 lines each); a single-plan collapse is acceptable but the split helps the executor focus.

---

*Phase: 38-graph-wiki-agent-graph-subcommand*
*Research completed: 2026-05-26*
