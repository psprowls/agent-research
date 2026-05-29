# Phase 59: Decouple graph-wiki-agent from `graph_io.cli` - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/graph-io/src/graph_io/render.py` | utility/formatter | transform | `packages/graph-io/src/graph_io/cli/_format.py` | exact (promotion) |
| `packages/graph-io/src/graph_io/cli/q_describe_package.py` | CLI module (refactor) | request-response | itself (pre-refactor) | exact |
| `packages/graph-io/src/graph_io/cli/q_describe_path.py` | CLI module (refactor) | request-response | itself + `q_describe_package.py` | exact |
| `packages/graph-io/src/graph_io/cli/q_describe_repo.py` | CLI module (refactor) | request-response | itself + `q_describe_package.py` | exact |
| `packages/graph-io/src/graph_io/cli/q_describe_domain.py` | CLI module (refactor) | request-response | itself (pre-refactor) | exact |
| `packages/graph-io/src/graph_io/cli/q_describe_entry_point.py` | CLI module (refactor) | request-response | itself (pre-refactor) | exact |
| `packages/graph-io/src/graph_io/cli/q_describe_suite.py` | CLI module (refactor) | request-response | itself + `q_describe_package.py` | exact |
| `packages/graph-io/src/graph_io/cli/q_find.py` | CLI module (refactor) | request-response | itself (pre-refactor) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` | command/controller | request-response | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` | role-match |
| `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` | test | CRUD + snapshot | `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` + itself (pre-refactor) | role-match |
| `agents/graph-wiki-agent/tests/conftest.py` | test fixture | CRUD | `packages/graph-io/tests/conftest.py` (`seeded_db`) | exact |
| `packages/graph-io/tests/test_cli_format.py` (update import) | test | transform | itself | exact |

---

## Pattern Assignments

### `packages/graph-io/src/graph_io/render.py` (utility/formatter, transform)

**Analog:** `packages/graph-io/src/graph_io/cli/_format.py` (lines 1–103; full file)

This is a **promotion**, not a new design. The entire contents of `_format.py` move verbatim into `render.py`, then 6 new per-kind formatter functions are added. The module-level docstring and all four private helpers are preserved as-is.

**Imports pattern** (`_format.py` lines 1–8):
```python
"""Render lists of dataclass records as JSON or aligned-column human output."""

from __future__ import annotations

import dataclasses
import json as _json
from typing import Any, Callable, Iterable
```

**Core pattern — existing `render()` function** (`_format.py` lines 50–103, keep exactly):
```python
def render(
    records: Iterable[Any],
    fmt: str,
    *,
    cap: int | None = None,
    on_truncate: Callable[[int, int], None] | None = None,
) -> str:
    rows = list(records)
    total = len(rows)
    truncated = cap is not None and total > cap
    if truncated:
        rows = rows[:cap]
        if on_truncate is not None:
            on_truncate(cap, total)

    if _is_importer_batch(rows):
        if fmt == "json":
            return _importer_json(rows)
        if fmt == "human":
            out = _importer_human(rows)
            if truncated:
                trailer = f"... showing {cap} of {total} (truncated)"
                return f"{out}\n{trailer}" if out else trailer
            return out
        raise ValueError(f"unknown format: {fmt!r}")

    dicts = [_to_dict(r) for r in rows]
    if fmt == "json":
        return json.dumps(dicts, default=str)
    if fmt == "human":
        if not dicts:
            return ""
        keys = list(dicts[0].keys())
        widths = {k: max(len(str(r.get(k, ""))) for r in dicts + [dict.fromkeys(keys, k)]) for k in keys}
        lines = []
        for r in dicts:
            lines.append("  ".join(str(r.get(k, "")).ljust(widths[k]) for k in keys))
        if truncated:
            lines.append(f"... showing {cap} of {total} (truncated)")
        return "\n".join(lines)
    raise ValueError(f"unknown format: {fmt!r}")
```

**New per-kind formatter signatures** — extract output logic from each `q_describe_*.py`:

```python
# format_package: extracted from q_describe_package.py lines 36–47
def format_package(desc: PackageDescription, fmt: str) -> str:
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    lines = [
        f"package: {desc.name}",
        f"language: {desc.language}",
        f"version:  {desc.version}",
        f"files:    {len(desc.files)}",
        f"counts:   {desc.counts}",
        f"internal deps:       {', '.join(desc.internal_dependencies) or '-'}",
        f"internal dependents: {', '.join(desc.internal_dependents) or '-'}",
    ]
    return "\n".join(lines)

# format_path: extracted from q_describe_path.py lines 39–46
def format_path(desc: PathDescription, fmt: str) -> str:
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    lines = [f"path: {desc.path}", "children:"]
    for c in desc.children:
        lines.append(f"  {c.kind}  {c.name}  line {c.line}")
    lines.append("imports:")
    for i in desc.imports:
        lines.append(f"  {i.path}")
    return "\n".join(lines)

# format_repo: extracted from q_describe_repo.py lines 39–46
def format_repo(desc: RepoDescription, fmt: str) -> str:
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    url = desc.url if desc.url else "(none)"
    default_branch = desc.default_branch if desc.default_branch else "(none)"
    lines = [
        f"repository:     {desc.name}",
        f"uri:            {desc.uri}",
        f"url:            {url}",
        f"default_branch: {default_branch}",
        f"package_count:  {desc.package_count}",
    ]
    return "\n".join(lines)

# format_domain: extracted from q_describe_domain.py lines 55–80
# NOTE: packages and subdomains are NOT in DomainDescription; callers pass them explicitly
def format_domain(
    desc: DomainDescription,
    packages: list[str],
    subdomains: list[str],
    fmt: str,
) -> str:
    if fmt == "json":
        payload = {**dataclasses.asdict(desc), "packages": packages, "subdomains": subdomains}
        return _json.dumps(payload, default=str)
    parent = desc.parent if desc.parent else "(none)"
    description = desc.description if desc.description else "(none)"
    lines = [
        f"domain:        {desc.name}",
        f"uri:           {desc.uri}",
        f"parent:        {parent}",
        f"description:   {description}",
        "packages:",
    ]
    if packages:
        for name in packages:
            lines.append(f"  - {name}")
    else:
        lines.append("  (none)")
    lines.append("subdomains:")
    if subdomains:
        for name in subdomains:
            lines.append(f"  - {name}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)

# format_entry_point: extracted from q_describe_entry_point.py lines 83–92
def format_entry_point(desc: EntryPointDescription, fmt: str) -> str:
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    callable_value = desc.callable if desc.callable else "(none)"
    impl_path = desc.implemented_by_path if desc.implemented_by_path else "(none)"
    source = desc.source if desc.source else "(none)"
    lines = [
        f"entry-point: {desc.name}",
        f"uri:         {desc.uri}",
        f"kind:        {desc.kind}",
        f"callable:    {callable_value}",
        f"path:        {impl_path}",
        f"source:      {source}",
    ]
    return "\n".join(lines)

# format_suite: extracted from q_describe_suite.py lines 43–46
# NOTE: label is "suite:", not "test_suite:"
def format_suite(desc: SuiteDescription, fmt: str) -> str:
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    lines = [
        f"suite:  {desc.name}",
        f"uri:    {desc.uri}",
        f"kind:   {desc.kind}",
        f"files:  {desc.file_count}",
    ]
    return "\n".join(lines)
```

**Output fidelity contract:** Each `format_*` function must produce output **byte-identical** to the current inline `print()` calls in the corresponding `q_describe_*.py`. The formatter returns a single string; callers do `print(output)` or `typer.echo(output)`. Using `"\n".join(lines)` without a trailing newline means `print()` adds the final newline — this matches the current behavior since each `print()` call adds its own newline (the last `print()` produces a trailing newline; `"\n".join()` + single `print()` also produces exactly one trailing newline).

---

### `packages/graph-io/src/graph_io/cli/q_describe_package.py` (CLI module refactor)

**Analog:** itself, pre-refactor (`packages/graph-io/src/graph_io/cli/q_describe_package.py` lines 1–48)

**Change:** Replace the inline format block (lines 36–47) with a call to `graph_io.render.format_package`. Everything else is unchanged.

**Import to add** (after line 12):
```python
from graph_io import render as _render
```

**Core pattern change** (lines 36–47 become):
```python
    if args.fmt == "json":
        print(_render.format_package(desc, fmt="json"))
    else:
        print(_render.format_package(desc, fmt="human"))
```

**Or more concisely:**
```python
    print(_render.format_package(desc, fmt=args.fmt))
```

**Error handling / connect pattern stays identical** (lines 19–35 — no change).

---

### `packages/graph-io/src/graph_io/cli/q_describe_path.py` (CLI module refactor)

**Analog:** `packages/graph-io/src/graph_io/cli/q_describe_path.py` lines 1–47 + `q_describe_package.py` (same pattern)

**Change:** Replace inline format block (lines 37–46) with `print(_render.format_path(desc, fmt=args.fmt))`. Add `from graph_io import render as _render`. Remove `import dataclasses` and `import json as _json` if they become unused.

---

### `packages/graph-io/src/graph_io/cli/q_describe_repo.py` (CLI module refactor)

**Analog:** `packages/graph-io/src/graph_io/cli/q_describe_repo.py` lines 1–47 + `q_describe_package.py` (same pattern)

**Change:** Replace inline format block (lines 37–46) with `print(_render.format_repo(desc, fmt=args.fmt))`. Add `from graph_io import render as _render`. Remove `import dataclasses` and `import json as _json` if they become unused.

---

### `packages/graph-io/src/graph_io/cli/q_describe_domain.py` (CLI module refactor)

**Analog:** `packages/graph-io/src/graph_io/cli/q_describe_domain.py` lines 1–82

**Change:** Replace inline format block (lines 55–80) with `print(_render.format_domain(desc, packages, subdomains, fmt=args.fmt))`. The two extra SQL queries (lines 34–51) remain — they feed `packages` and `subdomains` into the formatter. Add `from graph_io import render as _render`. Remove `import dataclasses` and `import json as _json`.

**Extra SQL queries that stay** (lines 34–51 — no change):
```python
        pkg_rows = conn.execute(
            "SELECT p.name FROM edges e "
            "JOIN nodes p ON e.src = p.id "
            "JOIN nodes d ON e.dst = d.id "
            "WHERE e.kind='belongs_to_domain' AND d.kind='domain' AND d.name = ? "
            "ORDER BY p.name",
            (args.name,),
        ).fetchall()
        packages = [r[0] for r in pkg_rows]
        sub_rows = conn.execute(
            "SELECT c.name FROM edges e "
            "JOIN nodes c ON e.dst = c.id "
            "JOIN nodes p ON e.src = p.id "
            "WHERE e.kind='domain_contains_domain' AND p.kind='domain' AND p.name = ? "
            "ORDER BY c.name",
            (args.name,),
        ).fetchall()
        subdomains = [r[0] for r in sub_rows]
```

---

### `packages/graph-io/src/graph_io/cli/q_describe_entry_point.py` (CLI module refactor)

**Analog:** `packages/graph-io/src/graph_io/cli/q_describe_entry_point.py` lines 1–94

**Change:** Replace inline format block (lines 81–92) with `print(_render.format_entry_point(desc, fmt=args.fmt))`. All disambiguation logic (lines 44–76) stays — that logic is in the CLI module, not in the formatter. Add `from graph_io import render as _render`. Remove `import dataclasses` and `import json as _json`.

---

### `packages/graph-io/src/graph_io/cli/q_describe_suite.py` (CLI module refactor)

**Analog:** `packages/graph-io/src/graph_io/cli/q_describe_suite.py` lines 1–48

**Change:** Replace inline format block (lines 40–47) with `print(_render.format_suite(desc, fmt=args.fmt))`. Add `from graph_io import render as _render`. Remove `import dataclasses` and `import json as _json`.

---

### `packages/graph-io/src/graph_io/cli/q_find.py` (CLI module refactor)

**Analog:** `packages/graph-io/src/graph_io/cli/q_find.py` lines 1–75

**Change:** Replace `from graph_io.cli import _format` (line 11) with `from graph_io import render as _render`. Replace `_format.render(...)` (line 73) with `_render.render(...)`. No other changes.

**Import change** (line 11 replaces):
```python
# BEFORE:
from graph_io.cli import _format
# AFTER:
from graph_io import render as _render
```

**Usage change** (line 73 replaces):
```python
# BEFORE:
print(_format.render(records, fmt=args.fmt, cap=50, on_truncate=_notice))
# AFTER:
print(_render.render(records, fmt=args.fmt, cap=50, on_truncate=_notice))
```

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` (command/controller, request-response)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` lines 540–558 (connect+error pattern) and `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` lines 125–420 (overall structure to preserve).

This is the primary migration. The shim (`_build_namespace`, `_capture_run`, all `graph_io.cli.*` imports) is deleted. All other structure (trace helpers, Typer app/subapp declarations, `_resolve_paths`, `_trace_path`, `_write_trace_record`, `_SCHEMA_VERSION`) is preserved.

**Imports to remove** (graph.py lines 35–55):
```python
# DELETE these:
import argparse
import contextlib
import io
from graph_io.cli import (
    ops_update,
    q_describe_domain,
    q_describe_entry_point,
    q_describe_package,
    q_describe_path,
    q_describe_repo,
    q_describe_suite,
    q_find,
)
```

**Imports to add:**
```python
import sqlite3
from graph_io import exit_codes, queries, render as _render, update
from graph_io.store import GraphNotInitializedError, SchemaMismatchError, read_only_connect
from workspace_io.paths import graph_dir
```

**New shared connect+map helper** (mirrors `scan.py` lines 540–558):
```python
def _open_graph_conn(workspace: Path) -> sqlite3.Connection:
    """Open a read-only graph connection, raising typer.Exit on store errors.

    Source pattern: scan.py:540-558 (read_only_connect + except GraphNotInitializedError).
    Does NOT close the connection — callers use try/finally: conn.close().
    """
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

**`graph build` after migration** (replaces lines 232–254):
```python
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
    except SchemaMismatchError as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.SCHEMA_MISMATCH
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.GENERIC
    dur_ms = int((time.monotonic() - t0) * 1000)
    # ... write trace record ...
    if exit_code != 0:
        raise typer.Exit(code=exit_code)
```

**`graph describe` describe dispatch pattern** (replaces `_run_describe` body, lines 269–300):

For 5 of the 6 kinds (package, path, repository, domain, suite), the shape is:
```python
    repo, workspace_path = _resolve_paths(workspace_arg)
    conn = _open_graph_conn(workspace_path)  # raises typer.Exit on store errors
    try:
        desc = queries.describe_package(conn, name=identifier)
    finally:
        conn.close()
    if desc is None:
        typer.echo(f"error: package not found: {identifier}", err=True)
        raise typer.Exit(code=exit_codes.GENERIC)
    typer.echo(_render.format_package(desc, fmt="human"))
    # ... write trace record ...
```

**Entry-point disambiguation** (replaces `_run_describe` for `entry_point` kind — must NOT use a generic dispatch table):

Source: `q_describe_entry_point.py` lines 44–76. Copy verbatim into graph.py, converting `return exit_codes.AMBIGUOUS` to `raise typer.Exit(code=exit_codes.AMBIGUOUS)` and `print(..., file=sys.stderr)` to `typer.echo(..., err=True)`:
```python
    raw = identifier
    conn = _open_graph_conn(workspace_path)
    try:
        if ":" in raw:
            package_name, entry_name = raw.split(":", 1)
            desc = queries.describe_entry_point(conn, package_name=package_name, entry_name=entry_name)
        else:
            rows = conn.execute(
                "SELECT pkg.name "
                "FROM nodes pkg "
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
                raise typer.Exit(code=exit_codes.AMBIGUOUS)
            else:
                desc = queries.describe_entry_point(conn, package_name=rows[0][0], entry_name=raw)
    finally:
        conn.close()
```

**Test-suite kwarg difference** (not in dispatch table — call explicitly):
```python
# CORRECT:
desc = queries.describe_test_suite(conn, suite_name=identifier)
# WRONG (raises TypeError):
desc = queries.describe_test_suite(conn, name=identifier)
```

**`graph query` after migration** (replaces lines 390–419):
```python
    conn = _open_graph_conn(workspace_path)
    try:
        records = queries.find(conn, name=name, kind=kind, in_package=in_package)
    finally:
        conn.close()

    # D-07 quirk: --in-package non-empty result required, else GENERIC (exit 1)
    # Source: q_find.py lines 67–68
    if in_package is not None and not records:
        if trace_file:
            _write_trace_record(trace_file, ..., exit_code=exit_codes.GENERIC, ...)
        raise typer.Exit(code=exit_codes.GENERIC)

    def _notice(shown: int, total: int) -> None:
        typer.echo(f"... showing {shown} of {total} (truncated)", err=True)

    typer.echo(_render.render(records, fmt="human", cap=50, on_truncate=_notice))
```

**What NOT to change:**
- `_SCHEMA_VERSION = 1` (graph.py line 58) — do NOT bump
- `_iso_utc_timestamp`, `_iso_utc_record_timestamp`, `_resolve_paths`, `_trace_path`, `_write_trace_record` — preserve exactly
- All 6 `@graph_describe_app.command(name="...")` decorators and their CLI argument signatures — preserve exactly
- The `propose-domains` registration at the bottom (lines 431–435) — preserve exactly
- `_write_trace_record` condition `if model_id is not None or event.startswith("graph_build")` (graph.py line 161) — preserve exactly

---

### `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` (test, CRUD + snapshot)

**Analog:** `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` (CliRunner pattern) + itself pre-refactor (structural shape to partially preserve).

**Tests to keep unchanged** (CLI shape tests — do not depend on the deleted mechanism):
- `test_graph_help_lists_exactly_three_subcommands` (lines 49–54)
- `test_graph_build_help_flags` (lines 57–64)
- `test_graph_describe_help_lists_six_kinds` (lines 67–71)
- `test_graph_query_no_filters_fails_fast` (lines 216–222) — pure Typer-layer, no mock

**Tests to replace** (all mock `_capture_run`/`_build_namespace`/`ops_update.run`/`q_describe_*.run`/`q_find.run`):
- `test_graph_build_dispatches_to_ops_update` → replace with real `update.run` via `seeded_graph_workspace`
- `test_graph_build_writes_trace` → replace with monkeypatched `update.run` + trace file assertion
- `test_graph_build_model_recorded_not_invoked` → replace with monkeypatched `update.run`
- `test_graph_describe_dispatch_all_six_kinds` → replace with 6 syrupy snapshot tests over real DB
- `test_graph_describe_trace_omits_cost_fields` → replace with real DB + trace assertion
- `test_graph_query_dispatch` → replace with real DB syrupy snapshot
- `test_cg_exit_codes_propagate` → replace with exception-raise mocks (not int-return mocks)

**New syrupy snapshot pattern** (from `test_trace_viewer.py` + `test_prompt_snapshots.py`):
```python
from syrupy.assertion import SnapshotAssertion
from typer.testing import CliRunner
from graph_wiki_agent.cli import app

def test_describe_package_output(
    runner: CliRunner,
    seeded_graph_workspace: Path,
    snapshot: SnapshotAssertion,
) -> None:
    result = runner.invoke(
        app,
        ["graph", "describe", "package", "mypkg"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot
```

**New exit-code mock pattern** (replaces int-return mocks with exception-raise mocks):
```python
def test_graph_build_not_in_git_repo(runner, tmp_workspace):
    from graph_io import update
    from unittest.mock import patch
    with patch.object(update, "run", side_effect=update.NotInGitRepoError("not a repo")):
        result = runner.invoke(app, ["graph", "build"])
    assert result.exit_code == exit_codes.NOT_IN_GIT_REPO
```

---

### `agents/graph-wiki-agent/tests/conftest.py` (test fixture — additive only)

**Analog:** `packages/graph-io/tests/conftest.py` lines 17–58 (`seeded_db` fixture) and `agents/graph-wiki-agent/tests/conftest.py` lines 95–128 (`seeded_graph_conn` — the fixture being mirrored).

**New fixture to add** (does NOT modify existing `seeded_graph_conn`):
```python
@pytest.fixture(scope="session")
def seeded_graph_workspace(tmp_path_factory):
    """Session-scoped workspace Path for graph command CliRunner tests.

    Seeds the same sample_monorepo as seeded_graph_conn but yields the
    workspace Path (not a conn) so CliRunner tests can set GRAPH_WIKI_WORKSPACE.

    Source pattern: seeded_graph_conn (conftest.py:95-128) + seeded_db
    (packages/graph-io/tests/conftest.py:17-58).
    Do NOT modify seeded_graph_conn — it yields conn, and test_graph_tools.py
    depends on that shape.
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

**Key difference from `seeded_graph_conn`:** Returns `ws: Path` directly (no `yield`, no `conn.close()`). Each CliRunner test invocation opens its own connection internally via `_open_graph_conn`. The `scope="session"` means one DB build per test session, shared across all snapshot tests.

---

## Shared Patterns

### Read-only connect + store error mapping

**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` lines 540–558  
**Apply to:** All describe subcommands and `graph query` in `commands/graph.py`

```python
# scan.py:540-558 — the established pattern for opening graph conn in agent commands
if _graph_ready:
    try:
        conn = read_only_connect(graph_dir(wiki.parent) / "code.db")
    except GraphNotInitializedError as exc:
        sys.stderr.write(
            f"[NOT_INITIALIZED fallback: graph could not be initialized ({exc}); using path-based slugs]\n"
        )
        conn = None
```

The migrated graph.py version converts this to `typer.Exit` raises (not `conn = None` fallbacks) since graph commands have no fallback path — they fail with the correct exit code.

### Exit code constants

**Source:** `packages/graph-io/src/graph_io/exit_codes.py` lines 1–13  
**Apply to:** All of `commands/graph.py`

```python
SUCCESS = 0
GENERIC = 1
STALE = 2
NOT_INITIALIZED = 3
SCHEMA_MISMATCH = 4
NOT_IN_GIT_REPO = 5
UPDATE_IN_PROGRESS = 6
AMBIGUOUS = 7
```

Always import from `graph_io.exit_codes` — never use magic integers. AMBIGUOUS (7) is required for the entry-point disambiguation path even though CONTEXT.md D-05 omits it.

### Typer echo conventions

**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` lines 283–286  
**Apply to:** All subcommands in `commands/graph.py`

```python
# stdout output:
typer.echo(output)          # or typer.echo(output, nl=False) for pre-terminated strings
# stderr output (errors, warnings, notes):
typer.echo(f"error: {exc}", err=True)
typer.echo("note: ...", err=True)
```

The migrated code switches from `_capture_run`'s buffered `stdout`/`stderr` forwarding to direct `typer.echo()` calls. Formatters return strings without trailing newlines; `typer.echo()` adds one.

### Trace record schema (preserve exactly)

**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` lines 132–169  
**Apply to:** All trace-writing logic in the migrated `graph.py`

```python
record: dict[str, Any] = {
    "schema_version": _SCHEMA_VERSION,   # must stay 1
    "timestamp": _iso_utc_record_timestamp(),
    "event": event,
    "command": command,
    "args": args_dict,
    "exit_code": exit_code,
    "duration_ms": duration_ms,
}
# model_id ONLY for graph_build events (lines 161–162):
if model_id is not None or event.startswith("graph_build"):
    record["model_id"] = model_id
```

Cost fields (`tokens_in`, `tokens_out`, `cost_usd`) are NEVER written — honest-omission per D-03. This behavior is tested by `test_graph_describe_trace_omits_cost_fields`.

### cg module connect pattern (stays unchanged after formatter refactor)

**Source:** `packages/graph-io/src/graph_io/cli/q_describe_package.py` lines 19–32  
**Apply to:** All 6 `q_describe_*.py` and `q_find.py` refactors

```python
def run(args: argparse.Namespace) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        # ... query ...
    finally:
        conn.close()
```

This pattern is unchanged by the formatter refactor — only the format step after the query changes.

---

## No Analog Found

All files in this phase have close analogs. No entries in this section.

---

## Critical Pitfalls (for planner)

| Pitfall | File | Guard |
|---------|------|-------|
| `format_domain()` must accept `packages` and `subdomains` args — they are NOT in `DomainDescription` | `render.py`, `q_describe_domain.py`, `graph.py` | `render.format_domain(desc, packages, subdomains, fmt=...)` signature |
| `queries.describe_test_suite` kwarg is `suite_name=`, not `name=` | `graph.py` | `queries.describe_test_suite(conn, suite_name=identifier)` |
| `queries.describe_entry_point` is `(conn, package_name=, entry_name=)` — no `name=` | `graph.py` | Use Pattern 4 disambiguation logic, never `name=` |
| `AMBIGUOUS (7)` must be raised for entry-point multi-match | `graph.py` | `raise typer.Exit(code=exit_codes.AMBIGUOUS)` in disambiguation block |
| `seeded_graph_conn` yields `conn` only — add `seeded_graph_workspace` as a separate fixture | `tests/conftest.py` | Do NOT modify `seeded_graph_conn` |
| `_format.py` import in `q_find.py` must be updated before `_format.py` is deleted | `q_find.py` | Update import first, then delete |
| `update.run` does NOT raise `GraphNotInitializedError` — it creates the DB | `graph.py` `graph build` | Only wrap `NotInGitRepoError`, `UpdateInProgressError`, `SchemaMismatchError`, `Exception` |

---

## Metadata

**Analog search scope:** `agents/graph-wiki-agent/src/`, `agents/graph-wiki-agent/tests/`, `packages/graph-io/src/`, `packages/graph-io/tests/`
**Files scanned:** 16 source files read directly
**Pattern extraction date:** 2026-05-29
