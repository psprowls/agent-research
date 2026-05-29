# Phase 59: Decouple graph-wiki-agent from `graph_io.cli` - Research

**Researched:** 2026-05-29
**Domain:** Python refactoring — graph_io formatter promotion + typed-API migration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Promote the rendering into a public `graph_io` module (out of `graph_io.cli`, e.g. `graph_io.render` / `graph_io.format`) imported by both the agent and cg. The agent imports this public formatter; it does **not** import `graph_io.cli`.
- **D-02:** Promotion goes the full distance — true single source of truth. Move `_format.render` (and its helpers `_to_dict`/importer-batch handling) to the public module AND extract the 6 inline describe formatters into it, then refactor the cg cli modules to consume the public formatter too. No duplicated/drift-prone formatting.
- **D-03:** Output fidelity bar is **byte-identical** (human format only for the agent; cg additionally supports `fmt="json"`, which the promoted formatter must still support).
- **D-04:** Reproduce the cg exit-code contract exactly via a shared connect+map helper in the agent: one helper opens `read_only_connect(graph_dir(workspace)/"code.db")`, catches `graph_io.store` exceptions, and maps them to `graph_io.exit_codes` values — reused by all 6 describe commands and `graph query`.
- **D-05:** Exit-code mapping to preserve: `GraphNotInitializedError → NOT_INITIALIZED (3)`, `SchemaMismatchError → SCHEMA_MISMATCH (4)`, describe not-found → `GENERIC (1)`, find `--in-package` no-match → `GENERIC (1)` (D-07 quirk), success → `SUCCESS (0)`. **Research gap flagged below:** AMBIGUOUS (7) must also be included for entry_point.
- **D-06:** `graph build` migrates to `graph_io.update.run(repo_root, *, workspace=..., full=...)` which returns `None` and raises on error. Wrap it separately. Preserve `--model` behavior (recorded in trace, NOT invoked). Note: `update.run` does not raise `GraphNotInitializedError` — it creates the DB.
- **D-07:** Keep the Phase 9 OBS-04 trace schema exactly: `schema_version = 1` (do NOT bump), same event values, same honest-omission of cost fields, same per-invocation JSONL path. `exit_code` written to the trace now comes from the agent's own mapping.
- **D-08:** Replace the existing `test_commands_graph.py` tests — they mock cg-module dispatch and assert the `argparse.Namespace` shape. New tests seed a real graph DB and snapshot the human output + exit codes for each subcommand.
- **D-09:** Reuse the existing session-scoped `seeded_graph_conn` fixture. Point `GRAPH_WIKI_WORKSPACE` at the seeded repo so each subcommand opens the same DB. Snapshot via syrupy. Error/exit-code branches awkward to provoke with a real DB may stay mock-based.

### Claude's Discretion

- Exact public module name/location for the promoted formatter (`graph_io.render` vs `graph_io.format` vs other).
- Internal structure of the shared connect+map helper (where it lives in the agent package, signature).
- Which describe error branches use snapshot-vs-mock per D-09.

### Deferred Ideas (OUT OF SCOPE)

- Whether to keep the `cg` CLI as a human-facing debug surface.

</user_constraints>

---

## Summary

Phase 59 has two interlocking concerns. First, `graph_io.cli._format.render` and all six inline describe formatters must be relocated into a new public `graph_io` module so neither the agent nor the cg CLI modules need to duplicate formatting logic. Second, `commands/graph.py` must replace every `_build_namespace` + `_capture_run` call with direct typed-API calls: `graph_io.queries.*`, `graph_io.update.run`, and `graph_io.store.read_only_connect`.

The code analysis reveals one gap in CONTEXT.md D-05: `q_describe_entry_point.py` returns `exit_codes.AMBIGUOUS (7)` when a bare entry-point name matches multiple packages. This exit code must be included in the agent's connect+map helper even though D-05 does not list it — the current code passes it through automatically, and the migrated code must do the same.

The domain describe command has a structural complication: `queries.describe_domain()` returns only `DomainDescription` (name, uri, parent, description) and does not fetch the package membership or subdomain lists. Those require two extra SQL queries executed inline in `q_describe_domain.py`. The promoted formatter for domain must therefore accept packages and subdomains as explicit arguments alongside the `DomainDescription`.

**Primary recommendation:** Use `graph_io.render` as the public module name (matches existing `_format.render` verb). Implement one function per describe kind plus one function for `find`. Have cg cli modules call these functions and have the agent call them too — satisfying D-02's single-source-of-truth requirement.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Human/JSON formatting of graph entities | `graph_io` library (public `render` module) | — | Both cg and the agent need identical output; formatting belongs in the library, not in consumers |
| DB connection management + error mapping | Agent command layer (`commands/graph.py`) | — | The agent owns its own retry/exit-code policy; scan.py establishes the pattern |
| Typed graph queries | `graph_io.queries` | — | Already typed; this phase migrates callers, not the queries themselves |
| Exit-code constants | `graph_io.exit_codes` | — | Stable since v1; no new codes added |
| CLI entry-point argument parsing | Agent's Typer layer | — | Already there; Namespace construction is what gets removed |
| Entry-point disambiguation logic | Agent command layer (migrate from q_describe_entry_point) | — | The bare-vs-"package:entry" parse is non-trivial; must move into agent since CLI module is no longer called |

---

## Standard Stack

No new packages are installed in this phase. All dependencies are already present.

| Library | Role | Status |
|---------|------|--------|
| `graph_io.queries` | Typed query destination | Already in workspace |
| `graph_io.update` | `run(repo_root, *, workspace, full)` for build | Already in workspace |
| `graph_io.store` | `read_only_connect`, `GraphNotInitializedError`, `SchemaMismatchError` | Already in workspace |
| `graph_io.exit_codes` | `SUCCESS/GENERIC/NOT_INITIALIZED/SCHEMA_MISMATCH/AMBIGUOUS` | Already in workspace |
| `workspace_io.paths.graph_dir` | Resolves `workspace/.graph/code.db` path | Already in workspace |
| `syrupy` 5.1.0 | Snapshot testing for SC#3 | Already in workspace dev deps |
| `pytest` ≥8.3 | Test runner | Already in workspace |
| `pytest-asyncio` 1.3.0 | Not needed for this phase (no async code) | Already in workspace |

## Package Legitimacy Audit

> No new packages are installed in this phase. All code changes affect existing workspace members.

**Packages installed:** None.

---

## Architecture Patterns

### System Architecture Diagram

```
Before (current):
  graph.py Typer commands
      → _build_namespace(module, ...)       # argparse.Namespace construction
      → _capture_run(module, args)          # redirect_stdout/stderr + module.run(args)
          → graph_io.cli.ops_update.run(args)       # int return
          → graph_io.cli.q_describe_*.run(args)     # int return + print to stdout
          → graph_io.cli.q_find.run(args)           # int return + print to stdout

After (target):
  graph.py Typer commands
      → graph_io.update.run(repo_root, workspace=ws, full=full)   # raises on error
      → _open_readonly_conn(workspace)      # new agent helper: read_only_connect + exception map
          → graph_io.store.read_only_connect(graph_dir(ws)/"code.db")
          → except GraphNotInitializedError → typer.Exit(NOT_INITIALIZED)
          → except SchemaMismatchError      → typer.Exit(SCHEMA_MISMATCH)
      → graph_io.queries.describe_package(conn, name=name)    # typed, returns dataclass | None
      → graph_io.render.format_package(desc, fmt="human")     # promoted formatter
      → typer.echo(output)
```

### Recommended Project Structure

```
packages/graph-io/src/graph_io/
├── render.py              # NEW: promoted public formatter (moved from cli/_format.py)
│                          # contains: render(), _to_dict, _is_importer_batch, _importer_human,
│                          # _importer_json, format_package(), format_path(), format_repo(),
│                          # format_domain(), format_entry_point(), format_suite()
├── cli/
│   ├── _format.py         # DELETED or replaced with: from graph_io.render import render (thin shim)
│   ├── q_describe_package.py   # CHANGED: call graph_io.render.format_package() instead of inline print
│   ├── q_describe_path.py      # CHANGED: call graph_io.render.format_path()
│   ├── q_describe_repo.py      # CHANGED: call graph_io.render.format_repo()
│   ├── q_describe_domain.py    # CHANGED: call graph_io.render.format_domain()
│   ├── q_describe_entry_point.py  # CHANGED: call graph_io.render.format_entry_point()
│   ├── q_describe_suite.py     # CHANGED: call graph_io.render.format_suite()
│   └── q_find.py               # CHANGED: import render from graph_io.render (not graph_io.cli._format)

agents/graph-wiki-agent/src/graph_wiki_agent/commands/
├── graph.py               # CHANGED: remove imports of graph_io.cli.*; call typed API + graph_io.render
```

### Pattern 1: Shared connect+map helper (mirrors scan.py)

**What:** A single private function inside `commands/graph.py` that opens the read-only graph connection and maps store exceptions to Typer exits. Reused by all 6 describe commands and `graph query`.

**When to use:** Any subcommand that needs to read from the graph DB.

```python
# Source: scan.py:541-558 (established pattern), adapted for graph.py

from graph_io import exit_codes
from graph_io.store import GraphNotInitializedError, SchemaMismatchError, read_only_connect
from workspace_io.paths import graph_dir

def _open_graph_conn(workspace: Path) -> sqlite3.Connection:
    """Open a read-only graph connection, raising typer.Exit on store errors."""
    db = graph_dir(workspace) / "code.db"
    try:
        return read_only_connect(db)
    except GraphNotInitializedError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=exit_codes.NOT_INITIALIZED)
    except SchemaMismatchError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=exit_codes.SCHEMA_MISMATCH)
```

**Note:** `typer.Exit` is raised (not returned) so the caller does not need to check a return value. The helper does not close the connection — callers use `try/finally: conn.close()`.

### Pattern 2: `graph build` exception-to-exit mapping

**What:** The typed `update.run()` raises typed exceptions instead of returning int codes. The agent wraps it with its own exception map.

```python
# Source: packages/graph-io/src/graph_io/cli/ops_update.py:16-30 (the contract to mirror)
from graph_io import update

try:
    update.run(repo, workspace=workspace_path, full=full)
except update.NotInGitRepoError as exc:
    typer.echo(f"error: {exc}", err=True)
    exit_code = exit_codes.NOT_IN_GIT_REPO   # 5
    raise typer.Exit(code=exit_code)
except update.UpdateInProgressError as exc:
    typer.echo(f"error: {exc}", err=True)
    exit_code = exit_codes.UPDATE_IN_PROGRESS  # 6
    raise typer.Exit(code=exit_code)
except store.SchemaMismatchError as exc:
    typer.echo(f"error: {exc}", err=True)
    exit_code = exit_codes.SCHEMA_MISMATCH     # 4
    raise typer.Exit(code=exit_code)
except Exception as exc:
    typer.echo(f"error: {exc}", err=True)
    exit_code = exit_codes.GENERIC             # 1
    raise typer.Exit(code=exit_code)
```

**Note:** There is no `NOT_INITIALIZED` path from `update.run` — it uses `store.connect(create=True)` which creates the DB if absent. This confirms the memory note: "graph-io ops_update lacks distinct NOT_INITIALIZED exit code."

### Pattern 3: Domain describe extra SQL

**What:** `queries.describe_domain()` only returns `DomainDescription` (name, uri, parent, description). The packages and subdomains lists are fetched by two separate SQL queries that live inline in `q_describe_domain.py`. After migration, the agent must replicate these queries and pass the results to `graph_io.render.format_domain()`.

```python
# Source: packages/graph-io/src/graph_io/cli/q_describe_domain.py:34-51
# Agent must do these queries itself (or they must move into a new queries helper)

desc = queries.describe_domain(conn, name=name)
if desc is None:
    typer.echo(f"error: not found: {name}", err=True)
    raise typer.Exit(code=exit_codes.GENERIC)

pkg_rows = conn.execute(
    "SELECT p.name FROM edges e "
    "JOIN nodes p ON e.src = p.id "
    "JOIN nodes d ON e.dst = d.id "
    "WHERE e.kind='belongs_to_domain' AND d.kind='domain' AND d.name = ? "
    "ORDER BY p.name",
    (name,),
).fetchall()
packages = [r[0] for r in pkg_rows]

sub_rows = conn.execute(
    "SELECT c.name FROM edges e "
    "JOIN nodes c ON e.dst = c.id "
    "JOIN nodes p ON e.src = p.id "
    "WHERE e.kind='domain_contains_domain' AND p.kind='domain' AND p.name = ? "
    "ORDER BY c.name",
    (name,),
).fetchall()
subdomains = [r[0] for r in sub_rows]
# Then: output = graph_io.render.format_domain(desc, packages, subdomains, fmt="human")
```

**Recommendation:** Keep these queries inline in the agent (they are domain-specific) and extend `format_domain()` to accept `packages` and `subdomains` as parameters. Do not force them into `DomainDescription` — that changes the queries.py API surface unnecessarily.

### Pattern 4: Entry-point disambiguation (migrate from CLI module)

**What:** `q_describe_entry_point.py` implements a non-trivial disambiguation step: parse the identifier as bare name or "package:entry" form, and if bare, scan all packages for a match. This logic does NOT live in `queries.describe_entry_point()` — it lives in the CLI module. After migration the agent must replicate it.

```python
# Source: packages/graph-io/src/graph_io/cli/q_describe_entry_point.py:45-75
# The agent must implement this disambiguation in commands/graph.py

raw = identifier  # the typer argument
if ":" in raw:
    package_name, entry_name = raw.split(":", 1)
    desc = queries.describe_entry_point(conn, package_name=package_name, entry_name=entry_name)
else:
    # Bare name — scan all packages
    rows = conn.execute(
        "SELECT pkg.name FROM nodes pkg "
        "JOIN edges de ON de.src = pkg.id AND de.kind='declares_entry_point' "
        "JOIN nodes ep ON ep.id = de.dst AND ep.kind='entry_point' "
        "WHERE pkg.kind IN ('package', 'app') AND ep.name = ?",
        (raw,),
    ).fetchall()
    if not rows:
        desc = None
    elif len(rows) > 1:
        packages = ", ".join(r[0] for r in rows)
        typer.echo(
            f"error: entry point not found: {raw} "
            f"(ambiguous across packages: {packages}; use 'package:entry')",
            err=True,
        )
        raise typer.Exit(code=exit_codes.AMBIGUOUS)  # exit code 7
    else:
        desc = queries.describe_entry_point(conn, package_name=rows[0][0], entry_name=raw)
```

**Important:** `AMBIGUOUS (7)` is NOT listed in CONTEXT.md D-05 but IS returned by the current code path and must be preserved. See the Assumptions Log, A1.

### Pattern 5: `queries.describe_entry_point` has a different signature than the agent dispatch table assumes

`queries.describe_entry_point(conn, *, package_name: str, entry_name: str)` — NOT `(conn, name=...)`.

The current agent dispatch table (`_DESCRIBE_DISPATCH`) stores `id_attr="name"` for entry_point and passes `{name: identifier}` to `_build_namespace`. After migration, the agent must not assume a single `name=` kwarg for entry points — it must use the disambiguation logic in Pattern 4.

### Pattern 6: `queries.describe_test_suite` takes `suite_name=`, not `name=`

```python
# Source: queries.py:727-728
def describe_test_suite(conn: sqlite3.Connection, *, suite_name: str) -> SuiteDescription | None:
```

The agent's dispatch currently stores `id_attr="name"` for test_suite, which maps to `args.name`. After migration, the agent must pass the identifier as `suite_name=name`, not `name=name`.

### Anti-Patterns to Avoid

- **Using `_capture_run` or `argparse.Namespace` after migration:** These must be deleted entirely.
- **Importing anything from `graph_io.cli` in `commands/graph.py`:** The SC#1 invariant. Enforced by grep.
- **Closing conn inside the `_open_graph_conn` helper:** The helper raises `typer.Exit` on errors but does NOT close the conn — callers use `try/finally`.
- **Sharing seeded_graph_conn across tests that need GRAPH_WIKI_WORKSPACE:** The existing `seeded_graph_conn` fixture yields only a `sqlite3.Connection`, not the workspace path. Add a companion `seeded_graph_workspace` fixture that yields the workspace `Path`, used by CliRunner snapshot tests.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Generic record formatting (find results) | Custom dict serializer | `graph_io.render.render()` (promoted from `_format.render`) | Handles `ImporterRecord` batches, truncation, aligned columns, both `fmt="human"` and `fmt="json"` |
| Exit code constants | Magic ints in graph.py | `graph_io.exit_codes.*` | Stable since v1; consumers depend on them |
| DB file path arithmetic | Custom path join | `workspace_io.paths.graph_dir(workspace) / "code.db"` | Canonical path; changes in one place |
| Workspace resolution from env or arg | `os.environ.get` + Path join | `workspace_io.config.resolve(path, require_manifest=False)` | Handles `GRAPH_WIKI_WORKSPACE` env override correctly |

---

## Research Question Findings

### RQ1: Formatter promotion (D-01/D-02) — exact shapes

**`_format.render(records, fmt, *, cap, on_truncate)` — source: `packages/graph-io/src/graph_io/cli/_format.py:50-103`**

- Accepts: `Iterable[Any]`, `fmt: str`, `cap: int | None`, `on_truncate: Callable[[int, int], None] | None`
- Detects `ImporterRecord` batch via `_is_importer_batch()` (checks `type(rows[0]).__name__ == "ImporterRecord"`)
- For generic records: calls `dataclasses.asdict()` via `_to_dict()`, then aligns columns for human or produces JSON array
- Returns: `str` (never prints, never writes to stderr)
- The `on_truncate` callback is used by `q_find.py` to write `"... showing N of M (truncated)"` to stderr

**6 inline describe formatters — per-command output shape:**

| Command | Formatted fields | Bespoke structure? |
|---------|-----------------|-------------------|
| `package` | `package: {name}`, `language: {language}`, `version: {version}`, `files: {len(files)}`, `counts: {counts}`, `internal deps: {joined or -}`, `internal dependents: {joined or -}` | No nested blocks |
| `path` | `path: {path}`, `children:` then `  {kind}  {name}  line {line}` per child, `imports:` then `  {i.path}` per import | Two indented sub-lists |
| `repository` | `repository: {name}`, `uri: {uri}`, `url: {url or "(none)"}`, `default_branch: {branch or "(none)"}`, `package_count: {count}` | No nested blocks |
| `domain` | `domain: {name}`, `uri: {uri}`, `parent: {parent or "(none)"}`, `description: {description or "(none)"}`, `packages:` then `  - {name}` per pkg, `subdomains:` then `  - {name}` per subdomain | Two indented bullet-lists; needs extra data beyond DomainDescription |
| `entry_point` | `entry-point: {name}`, `uri: {uri}`, `kind: {kind}`, `callable: {callable or "(none)"}`, `path: {impl_path or "(none)"}`, `source: {source or "(none)"}` | No nested blocks |
| `suite` | `suite: {name}`, `uri: {uri}`, `kind: {kind}`, `files: {file_count}` | No nested blocks; note label is `suite:` not `test_suite:` |

**JSON output for all 6 describe commands:** `dataclasses.asdict(desc)` plus `print(json.dumps(...))`. The domain JSON also includes `packages` and `subdomains` keys alongside `DomainDescription` fields.

**Proposed public module: `graph_io.render`**

```python
# graph_io/render.py — proposed public API

# Promotes: _format.render, _to_dict, _is_importer_batch, _importer_human, _importer_json
def render(records: Iterable[Any], fmt: str, *, cap: int | None = None,
           on_truncate: Callable | None = None) -> str: ...  # existing generic find renderer

# New per-kind formatters (extracted from the 6 q_describe_*.py modules)
def format_package(desc: PackageDescription, fmt: str) -> str: ...
def format_path(desc: PathDescription, fmt: str) -> str: ...
def format_repo(desc: RepoDescription, fmt: str) -> str: ...
def format_domain(desc: DomainDescription, packages: list[str], subdomains: list[str], fmt: str) -> str: ...
def format_entry_point(desc: EntryPointDescription, fmt: str) -> str: ...
def format_suite(desc: SuiteDescription, fmt: str) -> str: ...
```

**cg modules that change (D-02):** `q_describe_package.py`, `q_describe_path.py`, `q_describe_repo.py`, `q_describe_domain.py`, `q_describe_entry_point.py`, `q_describe_suite.py`, `q_find.py` (changes import from `graph_io.cli._format` to `graph_io.render`).

`_format.py` itself can be deleted or converted to a re-export shim (`from graph_io.render import render`) — the latter is safer if any third-party code imports it. Given this is a personal project, deletion is fine.

**cg tests/snapshots that must change:** `test_cli_format.py` currently imports from `graph_io.cli._format`. After promotion it imports from `graph_io.render` — the tests themselves remain identical. No snapshot files in graph-io tests exist today (verified: `packages/graph-io/tests/__snapshots__/` does not exist). The existing `test_cli_anti_regression.py`, `test_cli_exit_codes.py`, `test_cli_describe.py`, `test_cli_describe_entry_point.py` test output via subprocess or by asserting on key strings — they are the guard that cg output stays byte-identical.

### RQ2: `update.run` error contract (D-06)

**Source: `packages/graph-io/src/graph_io/update.py:232-323`**

`run(repo_root, *, workspace=None, full=False, lock_timeout_ms=None) -> None`

Exceptions raised (confirmed by reading `update.py` and `ops_update.py`):

| Exception | Where raised | Maps to exit code |
|-----------|-------------|-------------------|
| `update.NotInGitRepoError` | `_head()` when `git rev-parse` fails (`update.py:60`) | `NOT_IN_GIT_REPO (5)` |
| `update.UpdateInProgressError` | `sqlite3.OperationalError` with "locked" in message (`update.py:316`) | `UPDATE_IN_PROGRESS (6)` |
| `store.SchemaMismatchError` | Non-full update on mismatched schema (`update.py:260`) | `SCHEMA_MISMATCH (4)` |
| Any other `Exception` | Unexpected errors | `GENERIC (1)` |

`GraphNotInitializedError` is **NOT** raised by `update.run` — it calls `store.connect(create=True)` which creates the DB. The memory note "graph-io ops_update lacks distinct NOT_INITIALIZED exit code" is confirmed.

`--model` behavior to preserve: `typer.echo("note: --model is recorded in the trace but not invoked in v1.7 ...", err=True)` when `model is not None` — this stderr note is tested by `test_graph_build_model_recorded_not_invoked`.

The trace records `model_id` in `graph_build_complete` whether or not `--model` is passed (`record["model_id"] = model_id` where `model_id` is `None` when `--model` is not passed). This is because the condition is `if model_id is not None or event.startswith("graph_build")`.

### RQ3: Exit-code contract per command (D-04/D-05)

**Source: read from all 6 `q_describe_*.py`, `q_find.py`, `ops_update.py`, `exit_codes.py`**

| Command | Success | Not found / no results | Store errors | Special cases |
|---------|---------|----------------------|--------------|---------------|
| `graph build` | `SUCCESS (0)` | — | `NOT_IN_GIT_REPO (5)`, `UPDATE_IN_PROGRESS (6)`, `SCHEMA_MISMATCH (4)`, `GENERIC (1)` | `SchemaMismatchError` not raised on `--full` (rebuild path) |
| `describe package` | `SUCCESS (0)` | `GENERIC (1)` + stderr | `NOT_INITIALIZED (3)`, `SCHEMA_MISMATCH (4)` | — |
| `describe path` | `SUCCESS (0)` | `GENERIC (1)` + stderr | `NOT_INITIALIZED (3)`, `SCHEMA_MISMATCH (4)` | — |
| `describe repository` | `SUCCESS (0)` | `GENERIC (1)` + stderr | `NOT_INITIALIZED (3)`, `SCHEMA_MISMATCH (4)` | — |
| `describe domain` | `SUCCESS (0)` | `GENERIC (1)` + stderr | `NOT_INITIALIZED (3)`, `SCHEMA_MISMATCH (4)` | — |
| `describe entry-point` | `SUCCESS (0)` | `GENERIC (1)` + stderr | `NOT_INITIALIZED (3)`, `SCHEMA_MISMATCH (4)` | **`AMBIGUOUS (7)`** when bare name matches multiple packages |
| `describe test-suite` | `SUCCESS (0)` | `GENERIC (1)` + stderr | `NOT_INITIALIZED (3)`, `SCHEMA_MISMATCH (4)` | — |
| `graph query` | `SUCCESS (0)` | `SUCCESS (0)` (name/kind zero-result); **`GENERIC (1)`** (`--in-package` no-match) | `NOT_INITIALIZED (3)`, `SCHEMA_MISMATCH (4)` | D-07 quirk: `--in-package` non-empty result set required, else GENERIC |

**D-07 quirk confirmed (source: `q_find.py:66-68`):**

```python
if args.in_package is not None and not records:
    return exit_codes.GENERIC
```

This triggers when `--in-package` is specified but produces zero results, regardless of whether `--name` or `--kind` were also specified.

**D-05 gap:** CONTEXT.md does not list `AMBIGUOUS (7)` in the exit-code mapping for `describe entry-point`. The current code returns it and the migrated code must too. See Assumptions Log A1.

**Shared connect+map helper location:** Belongs in `commands/graph.py` as a private `_open_graph_conn(workspace)` function — does not need to be in a separate module given the single consumer. Mirrors the `scan.py:541` pattern.

### RQ4: Trace records (D-07)

**Source: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:58, 132-169`**

The trace schema (`schema_version = 1`) is defined at module level. Fields written per record:

```json
{
  "schema_version": 1,
  "timestamp": "<ISO-Z>",
  "event": "<graph_build_start|graph_build_complete|graph_describe|graph_query>",
  "command": "<graph build|graph describe <kind>|graph query>",
  "args": {"<command-specific dict>"},
  "exit_code": "<null for start, int for complete>",
  "duration_ms": 0
}
```

Additional field for `graph_build_*` events only: `"model_id": model_id` (may be `null`). Cost fields (`tokens_in`, `tokens_out`, `cost_usd`) are NEVER present.

After migration, `exit_code` in the trace comes from the agent's own exception-to-code mapping (not from an int returned by the cg module). The `_write_trace_record` function, `_trace_path` function, and `_iso_utc_*` helpers are unchanged — only the `_capture_run` and `_build_namespace` helpers are removed.

### RQ5: Test rebuild (D-08/D-09)

**Existing tests to replace (`test_commands_graph.py:1-237`):**

The file contains 8 test functions:
1. `test_graph_help_lists_exactly_three_subcommands` — CLI shape (keep, doesn't test the mechanism)
2. `test_graph_build_help_flags` — help text (keep, doesn't test the mechanism)
3. `test_graph_describe_help_lists_six_kinds` — help text (keep)
4. `test_graph_build_dispatches_to_ops_update` — mocks `ops_update.run`, asserts `args._module is ops_update` (REPLACE)
5. `test_graph_build_writes_trace` — mocks `ops_update.run` (REPLACE with real update.run + trace check)
6. `test_graph_build_model_recorded_not_invoked` — mocks `ops_update.run` (REPLACE with real update.run)
7. `test_graph_describe_dispatch_all_six_kinds` — mocks all 6 `q_describe_*.run`, asserts `args._module` (REPLACE with real DB snapshots)
8. `test_graph_describe_trace_omits_cost_fields` — mocks `q_describe_package.run` (REPLACE with real DB)
9. `test_graph_query_dispatch` — mocks `q_find.run` (REPLACE with real DB)
10. `test_graph_query_no_filters_fails_fast` — pure Typer-layer validation, no mock (KEEP, no real DB needed)
11. `test_cg_exit_codes_propagate` — mocks `ops_update.run` returning specific exit codes (REPLACE with exception-based mocks)

**`seeded_graph_conn` fixture analysis (`agents/graph-wiki-agent/tests/conftest.py:95-128`):**

The fixture:
1. Copies `packages/graph-io/tests/fixtures/sample_monorepo` to a temp dir as `repo_root`
2. Runs `git init` + `git commit` on it
3. Calls `update.run(repo_root, full=True)` — this creates `repo_root/graph-wiki/.graph/code.db`
4. Resolves `ws = resolve_workspace(repo_root, require_manifest=False).workspace` → `repo_root/graph-wiki`
5. Opens `read_only_connect(graph_dir(ws)/"code.db")` and yields the connection

The fixture only yields the connection (`conn`), NOT `ws`. The new graph command tests need `ws` to pass as `GRAPH_WIKI_WORKSPACE` to `CliRunner.invoke(app, argv, env={"GRAPH_WIKI_WORKSPACE": str(ws)})`.

**Required new fixture:** Add `seeded_graph_workspace` session-scoped fixture to `tests/conftest.py` that seeds the same monorepo and yields `ws` (workspace path, not conn). This is a second independent session fixture — it does not disrupt existing `seeded_graph_conn` callers.

```python
@pytest.fixture(scope="session")
def seeded_graph_workspace(tmp_path_factory):
    """Session-scoped workspace path for graph command tests.

    Seeds the same sample_monorepo as seeded_graph_conn but yields the
    workspace Path so CliRunner tests can pass GRAPH_WIKI_WORKSPACE.
    """
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    if not _GRAPH_IO_FIXTURE.exists():
        pytest.skip(f"sample_monorepo fixture not found at {_GRAPH_IO_FIXTURE}")

    repo_root = tmp_path_factory.mktemp("gwa_graph_cmd_ws") / "repo"
    shutil.copytree(_GRAPH_IO_FIXTURE, repo_root)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seeded init"], cwd=repo_root, check=True)
    update.run(repo_root, full=True)
    ws = resolve_workspace(repo_root, require_manifest=False).workspace
    return ws  # not a generator — session-scoped, no teardown needed
```

**sample_monorepo contents (available for snapshot assertions):**

| Kind | Names |
|------|-------|
| Packages | `commonlib`, `jspkg`, `mypkg`, `pyutil`, `webutil` |
| Domains | `core` (packages: mypkg, pyutil), `web` (packages: jspkg, webutil), `presentation` (parent of web) |
| Entry point | `mypkg-run` (confirmed in `test_cli_describe_entry_point.py:68`) |
| Test suites | present (Python + JS; exact names depend on fixture files) |

**Which subcommands can use real DB vs which need mock:**

| Branch | Approach | Reason |
|--------|----------|--------|
| Happy-path describe + query | Snapshot (syrupy) | Real DB available; byte-identical bar (D-03) requires exact output match |
| `describe entry-point` happy path | Snapshot with `mypkg-run` | Confirmed available in fixture |
| `graph build` (update.run) | Monkeypatch `update.run` | Full update run is slow; build is tested elsewhere; trace behavior verifiable with mock |
| `NOT_INITIALIZED` / `SCHEMA_MISMATCH` | Mock `read_only_connect` to raise | Awkward to create uninitialized DB state with a real fixture |
| `--in-package` no-match → GENERIC | Real DB with non-existent package name | Easy: `--in-package nonexistent` |
| `find --no-filters` → exit 2 | Pure Typer-layer, no DB | Already keep from existing tests |
| `AMBIGUOUS` entry-point | Mock `conn.execute` or create fixture with duplicate entry names | Difficult to provoke with sample_monorepo; mock-based |

**syrupy wiring:** syrupy 5.1.0 is already in workspace dev deps (`pyproject.toml:10`). The `test_trace_viewer.py` already uses `SnapshotAssertion`. No setup change needed — syrupy is auto-discovered via pytest plugin. Snapshot files are written to `tests/unit/__snapshots__/test_commands_graph.ambr`.

---

## Common Pitfalls

### Pitfall 1: `_format.py` still imported via `q_find.py` after promotion

**What goes wrong:** If `graph_io.cli._format` is deleted but `q_find.py` still imports from it, `cg find` breaks.
**Why it happens:** `q_find.py` imports `from graph_io.cli import _format` (line 11). It must be updated to import from the new public module.
**How to avoid:** Update `q_find.py` import before deleting `_format.py`. Run `cg find --name foo` as a smoke test after the refactor.
**Warning signs:** `ImportError: cannot import name '_format' from 'graph_io.cli'` in any test.

### Pitfall 2: Domain formatter receives closed connection

**What goes wrong:** `q_describe_domain.py`'s `finally: conn.close()` runs in all paths including the early `return exit_codes.GENERIC` inside the `try` block. This is correct Python — `finally` runs before the return propagates. But if the migrated agent uses `try/finally` incorrectly, it may try to execute the extra SQL queries after the connection is closed.
**Why it happens:** The domain command needs the connection for both `queries.describe_domain()` and the two extra SQL queries. If `conn.close()` is called too early, the extra queries fail.
**How to avoid:** Keep all three queries (describe_domain + 2 extras) inside the same `try` block before `conn.close()` in the `finally`.

### Pitfall 3: `queries.describe_test_suite` kwarg is `suite_name=`, not `name=`

**What goes wrong:** The agent currently stores `id_attr="name"` in `_DESCRIBE_DISPATCH` for test_suite, but `queries.describe_test_suite(conn, suite_name=...)` uses the kwarg `suite_name`. After migration, passing `name=` raises `TypeError`.
**Why it happens:** The `q_describe_suite.py` module bridges this via `args.name` → `suite_name=args.name` (line 34). After migration this bridge is gone.
**How to avoid:** In the migrated `graph.py`, call `queries.describe_test_suite(conn, suite_name=identifier)` explicitly.

### Pitfall 4: `queries.describe_entry_point` signature is `(conn, package_name=, entry_name=)`, not `(conn, name=)`

**What goes wrong:** Calling `queries.describe_entry_point(conn, name=identifier)` raises `TypeError`.
**Why it happens:** The agent's old dispatch table stored `id_attr="name"` and passed a single identifier; the `q_describe_entry_point.py` module handled the disambiguation. After migration, the disambiguation must be replicated in the agent.
**How to avoid:** Use Pattern 4 above. Never call `queries.describe_entry_point` with `name=`.

### Pitfall 5: AMBIGUOUS exit code (7) missing from the connect+map helper

**What goes wrong:** `describe entry-point` with an ambiguous bare name returns exit code 7 via the current cg module. If the migrated agent doesn't raise `typer.Exit(7)` for the ambiguous case, the exit code changes from 7 to 0 (or the typer default).
**Why it happens:** CONTEXT.md D-05 omits AMBIGUOUS from the exit-code mapping list.
**How to avoid:** Explicitly handle the multi-match case in the entry-point disambiguation logic (Pattern 4) with `raise typer.Exit(code=exit_codes.AMBIGUOUS)`.

### Pitfall 6: `seeded_graph_conn` yields conn only — not workspace path

**What goes wrong:** New snapshot tests invoke Typer commands via CliRunner and need `GRAPH_WIKI_WORKSPACE` set to the seeded workspace path. Using the existing `seeded_graph_conn` fixture provides no way to get that path.
**Why it happens:** The fixture was designed for the `build_graph_tools(conn)` tests (Phase 37), not for CLI invocation tests.
**How to avoid:** Add the companion `seeded_graph_workspace` fixture (Pattern 5 / RQ5 section above). Do NOT modify `seeded_graph_conn` to yield a tuple — that breaks `test_graph_tools.py` and `test_query_graph_tools_wiring.py`.

### Pitfall 7: `update.run` no-op when already up-to-date

**What goes wrong:** `update.run` returns `None` silently when `not changed and prev == head and not full`. This is correct behavior but the trace `graph_build_complete` record should still be written (with `exit_code=0`).
**Why it happens:** The current code in graph.py writes the complete trace record regardless of whether `ops_update.run` returned 0 (no-change) or did work. This behavior must be preserved: the trace records the invocation, not whether work was done.
**How to avoid:** Wrap `update.run(...)` in try/except that captures `None` return as `exit_code = 0` before writing the trace.

---

## Code Examples

### Formatter function signatures (to implement in `graph_io/render.py`)

```python
# Source: packages/graph-io/src/graph_io/cli/_format.py + 6 q_describe_*.py files

# The existing generic renderer (keep signature, just relocate)
def render(records: Iterable[Any], fmt: str, *,
           cap: int | None = None,
           on_truncate: Callable[[int, int], None] | None = None) -> str:
    ...

# Per-kind formatters with exact output shape:

def format_package(desc: PackageDescription, fmt: str) -> str:
    """human: 7 labeled lines. json: dataclasses.asdict(desc)."""
    # Source: q_describe_package.py:36-47

def format_path(desc: PathDescription, fmt: str) -> str:
    """human: path + children (kind/name/line) + imports (path). json: asdict."""
    # Source: q_describe_path.py:38-46

def format_repo(desc: RepoDescription, fmt: str) -> str:
    """human: 5 labeled lines (url/branch default '(none)'). json: asdict."""
    # Source: q_describe_repo.py:37-45

def format_domain(desc: DomainDescription, packages: list[str],
                  subdomains: list[str], fmt: str) -> str:
    """human: 6 labeled lines + indented bullet lists. json: asdict+packages+subdomains."""
    # Source: q_describe_domain.py:55-80
    # NOTE: packages and subdomains come from extra SQL queries, not DomainDescription

def format_entry_point(desc: EntryPointDescription, fmt: str) -> str:
    """human: 6 labeled lines (callable/path/source default '(none)'). json: asdict."""
    # Source: q_describe_entry_point.py:81-93

def format_suite(desc: SuiteDescription, fmt: str) -> str:
    """human: 4 labeled lines (label is 'suite:', not 'test_suite:'). json: asdict."""
    # Source: q_describe_suite.py:39-46
```

### graph build after migration

```python
# After migration in commands/graph.py
from graph_io import exit_codes, update
from graph_io import store

@graph_app.command(name="build")
def graph_build_cmd(...) -> None:
    repo, workspace_path = _resolve_paths(workspace)
    if model is not None:
        typer.echo("note: --model is recorded in the trace but not invoked in v1.7 ...", err=True)
    
    shared_stamp = _iso_utc_timestamp()
    trace_file = _trace_path(workspace_path, "graph-build", shared_stamp) if trace else None
    args_dict = {"full": full, "model": model}
    
    if trace_file:
        _write_trace_record(trace_file, event="graph_build_start", ..., exit_code=None, duration_ms=0, model_id=model)
    
    exit_code = exit_codes.SUCCESS
    t0 = time.monotonic()
    try:
        update.run(repo, workspace=workspace_path, full=full)
    except update.NotInGitRepoError as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.NOT_IN_GIT_REPO
    except update.UpdateInProgressError as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.UPDATE_IN_PROGRESS
    except store.SchemaMismatchError as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.SCHEMA_MISMATCH
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.GENERIC
    dur_ms = int((time.monotonic() - t0) * 1000)
    
    if trace_file:
        _write_trace_record(trace_file, event="graph_build_complete", ..., exit_code=exit_code, duration_ms=dur_ms, model_id=model)
    
    if exit_code != 0:
        raise typer.Exit(code=exit_code)
```

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CONTEXT.md D-05 omits `AMBIGUOUS (7)` from the exit-code list for `describe entry-point`. The code at `q_describe_entry_point.py:71` returns `exit_codes.AMBIGUOUS`. The migrated agent must preserve this. **This is VERIFIED in code, not assumed — flagged because CONTEXT.md is inconsistent with the code.** | RQ3, Pattern 4 | If omitted, entry-point describe on ambiguous names returns exit 0 instead of 7; silent regression. |
| A2 | `seeded_graph_workspace` must be a separate session fixture (not modifying `seeded_graph_conn`). If the plan modifies `seeded_graph_conn` to return a tuple, `test_graph_tools.py` and other callers would break. | RQ5 | Breaking existing tests is caught immediately by `uv run --package graph-wiki-agent pytest`. |

---

## Open Questions

1. **`_format.py` — delete or shim?**
   - What we know: `_format.py` is imported by `q_find.py` (inside `graph_io.cli`). After promotion, `q_find.py` will import from `graph_io.render` instead.
   - What's unclear: Whether any external consumer imports `graph_io.cli._format` directly (outside cg and the agent).
   - Recommendation: Delete `_format.py` after updating `q_find.py`. The project is a personal monorepo with no public API consumers yet.

2. **`format_domain` extra SQL queries — keep inline or add a `query_domain_members` helper to `queries.py`?**
   - What we know: The two SQL queries (packages, subdomains) are currently inline in `q_describe_domain.py`. They are domain-traversal queries, not complex.
   - What's unclear: Whether future code (e.g. wiki-io entity writer) would benefit from a reusable `queries.domain_packages()` helper.
   - Recommendation: Keep the queries inline in the agent's `commands/graph.py` for this phase (scope control). The promoted `format_domain()` accepts `packages` and `subdomains` as parameters. Adding query helpers to `queries.py` is deferred.

---

## Environment Availability

This phase is code-only refactoring. No external services or new tools required. All dependencies are already installed via the `uv` workspace.

| Dependency | Status | Notes |
|------------|--------|-------|
| `graph_io` workspace member | Available | Source of typed API |
| `workspace_io` workspace member | Available | Path resolution |
| `syrupy` 5.1.0 | Available (dev dep) | Snapshot testing |
| `pytest` ≥8.3 | Available | Test runner |
| `uv` 0.11.14 | Available | `uv run --package graph-wiki-agent pytest` |

---

## Validation Architecture

> `workflow.nyquist_validation: true` — section included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 + syrupy 5.1.0 |
| Config file | `agents/graph-wiki-agent/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run --package graph-wiki-agent pytest tests/unit/test_commands_graph.py -x` |
| Full suite command | `uv run --package graph-wiki-agent pytest` |
| graph-io tests (cg formatter changes) | `uv run --package graph-io pytest tests/test_cli_format.py tests/test_cli_describe.py tests/test_cli_describe_entry_point.py tests/test_cli_exit_codes.py tests/test_cli_anti_regression.py -x` |

### Phase Requirements → Test Map

| SC | Behavior | Test Type | Automated Command | File Status |
|----|----------|-----------|-------------------|-------------|
| SC#1 | No `graph_io.cli` import in `agents/graph-wiki-agent/` | Static grep assertion | `grep -r "from graph_io.cli" agents/graph-wiki-agent/src/ \|\| echo "CLEAN"` | Wave 0 task |
| SC#2 | No `argparse.Namespace` or `_capture_run` in `graph.py` | Static grep assertion | `grep -E "_build_namespace\|_capture_run\|argparse" agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py \|\| echo "CLEAN"` | Wave 0 task |
| SC#3 (build) | `graph build` runs update.run and writes trace | unit + snapshot | `pytest tests/unit/test_commands_graph.py::test_graph_build_writes_trace -x` | Wave 0 gap |
| SC#3 (describe 6 kinds) | Human output byte-identical per subcommand | snapshot (syrupy) | `pytest tests/unit/test_commands_graph.py -k "describe" --snapshot-update` then `pytest tests/unit/test_commands_graph.py -k "describe" -x` | Wave 0 gap |
| SC#3 (query) | `graph query` output byte-identical | snapshot (syrupy) | `pytest tests/unit/test_commands_graph.py -k "query" -x` | Wave 0 gap |
| SC#3 (exit codes) | All 8 commands return correct exit codes | unit | `pytest tests/unit/test_commands_graph.py -k "exit_code or not_initialized or in_package" -x` | Wave 0 gap |
| SC#3 (trace omits cost) | Proxy commands trace omits model_id/tokens_in/tokens_out/cost_usd | unit | `pytest tests/unit/test_commands_graph.py::test_graph_describe_trace_omits_cost_fields -x` | Wave 0 gap (new) |
| SC#3 (cg byte-identical) | cg describe-* output unchanged after formatter promotion | existing cg tests | `uv run --package graph-io pytest tests/test_cli_anti_regression.py tests/test_cli_describe.py tests/test_cli_describe_entry_point.py -x` | Existing — run as regression guard |
| SC#4 | Full suite green | integration | `uv run --package graph-wiki-agent pytest` | Run at phase gate |

### Sampling Rate

- **Per task commit:** `uv run --package graph-wiki-agent pytest tests/unit/test_commands_graph.py -x && uv run --package graph-io pytest tests/test_cli_format.py -x`
- **Per wave merge:** `uv run --package graph-wiki-agent pytest && uv run --package graph-io pytest tests/test_cli_format.py tests/test_cli_describe.py tests/test_cli_exit_codes.py tests/test_cli_anti_regression.py`
- **Phase gate:** Full suite of both packages green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` — full replacement (remove mock-based tests, add syrupy snapshot tests + real-DB exit-code tests)
- [ ] `agents/graph-wiki-agent/tests/conftest.py` — add `seeded_graph_workspace` session fixture (yields `ws: Path`)
- [ ] `packages/graph-io/src/graph_io/render.py` — new public module (promoted from `_format.py` + 6 inline formatters)
- [ ] Snapshot generation: `uv run --package graph-wiki-agent pytest tests/unit/test_commands_graph.py --snapshot-update` (run once after Wave 1 implementation to seed `.ambr` files)

---

## Security Domain

> `security_enforcement: true` (default). Phase is internal refactoring with no new external inputs, network calls, or auth surfaces.

### Applicable ASVS Categories

| ASVS Category | Applies | Notes |
|---------------|---------|-------|
| V2 Authentication | No | No auth logic changes |
| V3 Session Management | No | No session logic |
| V4 Access Control | No | No permission changes |
| V5 Input Validation | Minimal | `graph query` args already validated at Typer layer (no-filter guard preserved); entry-point disambiguation parse is read-only against an existing DB |
| V6 Cryptography | No | No crypto |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `--workspace` arg | Tampering | Existing: `workspace_io.config.resolve()` resolves and normalizes the path; no user-controlled path reaches `open()` without normalization |
| SQL injection via `--name/--kind/--in-package` | Tampering | Existing: `queries.find()` uses parameterized queries (`?` placeholders). No change in this phase. |

---

## Sources

### Primary (HIGH confidence)

All findings are grounded in source code read during this session with file:line citations.

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — the module being replaced; full read
- `packages/graph-io/src/graph_io/cli/_format.py` — formatter to promote; full read
- `packages/graph-io/src/graph_io/cli/q_describe_package.py` — inline formatter; full read
- `packages/graph-io/src/graph_io/cli/q_describe_path.py` — inline formatter; full read
- `packages/graph-io/src/graph_io/cli/q_describe_repo.py` — inline formatter; full read
- `packages/graph-io/src/graph_io/cli/q_describe_domain.py` — inline formatter + extra SQL; full read
- `packages/graph-io/src/graph_io/cli/q_describe_entry_point.py` — inline formatter + disambiguation; full read
- `packages/graph-io/src/graph_io/cli/q_describe_suite.py` — inline formatter; full read
- `packages/graph-io/src/graph_io/cli/q_find.py` — find + D-07 quirk; full read
- `packages/graph-io/src/graph_io/cli/ops_update.py` — update error contract; full read
- `packages/graph-io/src/graph_io/update.py:232-323` — typed update.run exceptions; read
- `packages/graph-io/src/graph_io/store.py` — `read_only_connect`, exceptions; full read
- `packages/graph-io/src/graph_io/exit_codes.py` — all constants; full read
- `packages/graph-io/src/graph_io/queries.py` — typed function signatures; read
- `agents/graph-wiki-agent/tests/conftest.py` — `seeded_graph_conn` fixture; full read
- `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` — tests to replace; full read
- `packages/graph-io/tests/conftest.py` — `seeded_db` sibling fixture; full read
- `packages/graph-io/tests/test_cli_exit_codes.py` — exit code tests; read
- `packages/graph-io/tests/test_cli_describe.py` — describe tests; read
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:535-558` — typed consumer pattern; read
- `agents/graph-wiki-agent/pyproject.toml` — syrupy dependency confirmed

### Secondary (MEDIUM confidence)

- `packages/workspace-io/src/workspace_io/config.py` — `resolve()` and `resolve_workspace()` behavior; full read
- `packages/workspace-io/src/workspace_io/paths.py` — `graph_dir()` returns `workspace/.graph`; full read

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all libraries confirmed present
- Architecture: HIGH — all function signatures, exceptions, and output shapes confirmed from source code
- Pitfalls: HIGH — all grounded in code reads, not inference
- Test strategy: HIGH — fixture internals read directly

**Research date:** 2026-05-29
**Valid until:** 2026-06-28 (stable Python refactoring; not affected by external package churn)
