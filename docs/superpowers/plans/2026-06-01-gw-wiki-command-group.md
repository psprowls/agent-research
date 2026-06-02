# `gw wiki` Command Group + `migrate-vault` Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the `gw` CLI so wiki-maintenance commands live under a new `gw wiki` group (mirroring `gw graph`), and remove the dead `migrate-vault` command entirely.

**Architecture:** Extract `query`, `log`, `lint`, and the `ingest` sub-app verbatim out of `graph_wiki_cli/cli.py` into a new `graph_wiki_cli/wiki_cli/main.py` module exposing a `wiki_app` Typer group, mounted on the root app via `app.add_typer(wiki_app, name="wiki")` — structurally symmetric to the existing `graph_cli/main.py` / `graph_app`. Command bodies move unchanged (same options, exit codes, `--json` handling, error translation). `scan`, `bootstrap`, `trace`, `version`, `help`, and the `graph` group stay top-level. `migrate-vault` (CLI command + `run_migrate_vault` implementation + its tests) is deleted; no pre-v2.0 vaults exist to migrate.

**Tech Stack:** Python 3.11+, `uv` workspace, Typer (`graph-wiki-cli` package), `pytest` + `typer.testing.CliRunner`.

---

## Pre-flight context (read before starting)

The move is a **verbatim relocation**, not a rewrite — copy command bodies exactly, only changing where they're registered. The subtle breakages the spec under-counts and which this plan handles explicitly:

- Tests **monkeypatch** `graph_wiki_cli.cli.run_query` and `graph_wiki_cli.cli.run_log`. After the move those symbols live in `graph_wiki_cli.wiki_cli.main`, so the monkeypatch targets must change or the tests raise `AttributeError`.
- `test_cli_query.py` **imports `query` from `graph_wiki_cli.cli`** and asserts `hasattr(cli_module, "run_query")` — both must repoint to `wiki_cli.main`.
- There are **7** `gw query` / `["query", …]` invocations in `test_cli_query.py` (4 subprocess, 3 CliRunner), not 3. All become `gw wiki query` / `["wiki", "query", …]`.

Out-of-scope notes (do NOT act on these — just be aware):
- `packages/wiki-io/src/wiki_io/link_rewriter.py` becomes orphaned once `migrate_vault.py` is deleted (it was its only production consumer). Leave it and its tests in place — removal is not in this spec.
- `docs/gw-cli.md` and `packages/wiki-io/tests/test_entity_templates.py` already show as modified in `git status` from prior unrelated work; do not revert those pre-existing changes.

### File structure after this plan

- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` — root `gw` app: `help`, `version`, `trace`, `bootstrap`, `scan`; mounts `graph_app` and `wiki_app`. **No longer** defines `query`/`log`/`lint`/`ingest`/`migrate-vault`.
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/__init__.py` — **new**, package marker.
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` — **new**, `wiki_app` group: `query`, `log`, `lint`, `ingest source`, `ingest work-item`, plus `main()`.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/migrate_vault.py` — **deleted**.
- `packages/graph-wiki-core/tests/test_migrate_vault.py` — **deleted**.

---

## Task 1: Remove `migrate-vault` entirely

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` (remove import + command)
- Delete: `packages/graph-wiki-core/src/graph_wiki_core/commands/migrate_vault.py`
- Delete: `packages/graph-wiki-core/tests/test_migrate_vault.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` (add regression guard)

- [ ] **Step 1: Write the failing regression test**

Append to `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` (the file already imports `importlib`, `importlib.metadata`, `inspect`, and `typer` at the top):

```python
def test_migrate_vault_command_removed() -> None:
    """`gw migrate-vault` is fully removed — no command, no source reference."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "migrate-vault" not in root_command.commands

    cli_module = importlib.import_module("graph_wiki_cli.cli")
    assert "migrate_vault" not in inspect.getsource(cli_module)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py::test_migrate_vault_command_removed -v`
Expected: FAIL — `"migrate-vault"` is still a registered command and `migrate_vault` still appears in the source.

- [ ] **Step 3: Remove the import from `cli.py`**

Delete this line (currently at `cli.py:76`):

```python
from graph_wiki_core.commands.migrate_vault import run_migrate_vault
```

- [ ] **Step 4: Remove the `migrate-vault` command block from `cli.py`**

Delete this entire block (the section header comment through the end of the `migrate_vault` function — currently `cli.py:672-708`):

```python
# ---------------------------------------------------------------------------
# migrate-vault command (Phase 46 — v1.8 entity-restructure atomic cutover)
# ---------------------------------------------------------------------------


@app.command(name="migrate-vault")
def migrate_vault(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview the cutover without writing or committing."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Bypass the idempotency check (use for partial-cutover recovery).",
    ),
    no_write_marker: bool = typer.Option(
        False,
        "--no-write-marker",
        help="Testing affordance: run full cutover but skip the manifest marker write.",
        hidden=True,
    ),
) -> None:
    """Migrate the vault to v1.8 entity-first layout as one atomic commit.

    Phase 46 cutover: populates wiki/entities/, rewrites inbound wikilinks
    across the 5 curated lanes (concepts/adrs/architecture/sources/work),
    removes old layout directories, regenerates indexes, and commits — all
    atomically.

    Use --dry-run first to preview what will change.
    """
    exit_code = run_migrate_vault(
        dry_run=dry_run,
        force=force,
        write_marker=not no_write_marker,
    )
    raise typer.Exit(code=exit_code)
```

Leave the `# ingest sub-app` section header that immediately follows it intact (it is removed later, in Task 2).

- [ ] **Step 5: Delete the implementation and its test**

Run:

```bash
git rm packages/graph-wiki-core/src/graph_wiki_core/commands/migrate_vault.py \
       packages/graph-wiki-core/tests/test_migrate_vault.py
```

- [ ] **Step 6: Confirm no stray references remain**

Run: `grep -rn "migrate_vault\|migrate-vault" packages/graph-wiki-cli/src packages/graph-wiki-core/src`
Expected: no output. (A docstring mention in `packages/wiki-io/src/wiki_io/link_rewriter.py` is out of scope — leave it.)

- [ ] **Step 7: Run the regression test + both package suites**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py::test_migrate_vault_command_removed -v`
Expected: PASS

Run: `uv run --package graph-wiki-core pytest`
Expected: PASS (the deleted `test_migrate_vault.py` is simply gone; nothing else imports it).

- [ ] **Step 8: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/cli.py \
        packages/graph-wiki-cli/tests/unit/test_cli_boundary.py
git commit -m "feat(cli): remove dead migrate-vault command and implementation"
```

---

## Task 2: Create `wiki_cli/` module and move `query`/`log`/`lint`/`ingest`

**Files:**
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/__init__.py`
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- Test (new): `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py`
- Test (update): `packages/graph-wiki-cli/tests/unit/test_cli_query.py`
- Test (update): `packages/graph-wiki-cli/tests/unit/test_commands_log.py`
- Test (update): `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`

- [ ] **Step 1: Write the failing test for the new `wiki` group**

Create `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py`:

```python
from __future__ import annotations

import typer


def test_wiki_cli_module_exposes_wiki_app_and_main() -> None:
    """The relocated module exposes a `wiki` Typer app and a `main()` entry."""
    from graph_wiki_cli.wiki_cli import main as wiki_main

    assert isinstance(wiki_main.wiki_app, typer.Typer)
    assert wiki_main.wiki_app.info.name == "wiki"
    assert hasattr(wiki_main, "main")


def test_root_app_mounts_wiki_group_with_subcommands() -> None:
    """`gw wiki` is registered and exposes query/log/lint/ingest."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "wiki" in root_command.commands

    wiki_group = root_command.commands["wiki"]
    assert {"query", "log", "lint", "ingest"} <= set(wiki_group.commands)

    ingest_group = wiki_group.commands["ingest"]
    assert {"source", "work-item"} <= set(ingest_group.commands)


def test_moved_commands_no_longer_top_level() -> None:
    """query/log/lint/ingest are no longer registered at the root."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    for name in ("query", "log", "lint", "ingest"):
        assert name not in root_command.commands
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_wiki_cli.py -v`
Expected: FAIL — `graph_wiki_cli.wiki_cli` does not exist yet (`ModuleNotFoundError`).

- [ ] **Step 3: Create the `wiki_cli` package marker**

Create `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/__init__.py`:

```python
"""Relocated wiki-maintenance CLI command surface for graph-wiki-cli."""
```

- [ ] **Step 4: Create `wiki_cli/main.py` with the moved commands**

Create `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` with this exact content (command bodies are copied verbatim from `cli.py` — options, exit codes, `--json` handling, and error translation are unchanged):

```python
"""Native Typer command surface for `gw wiki`.

Wiki-maintenance commands (query, log, lint, ingest) relocated from cli.py so
the `gw wiki` group mirrors the `gw graph` group structurally. Command bodies
delegate to graph_wiki_core.commands.*; this module owns only presentation.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
from pathlib import Path
from typing import Optional

import typer

from graph_io import exit_codes as _gio_exit_codes

from graph_wiki_core.commands.ingest import (
    IngestorGraphNotInitializedError,
    run_ingest_source,
    run_ingest_work_item,
)
from graph_wiki_core.commands.lint import run_lint
from graph_wiki_core.commands.log import run_log
from graph_wiki_core.commands.query import run_query

wiki_app = typer.Typer(
    name="wiki",
    help="Wiki maintenance operations.",
    no_args_is_help=True,
)


@wiki_app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, "--top-k", help="Pages to drill (3-10)", min=3, max=10),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit QueryResult as JSON"),
    no_state_gate: bool = typer.Option(False, "--no-state-gate", help="No-op; query is read-only"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output (headless mode)"),
) -> None:
    """Query the wiki using hybrid BM25+embedding search with librarian fan-out."""
    # state gate is a no-op for query (read-only) — D-08
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_query(query_text, workspace_path, top_k=top_k))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    partial = result.pages_drilled < top_k

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(result.answer)
        if result.citations:
            typer.echo(f"\nCitations: {', '.join(result.citations)}")
        if not quiet:
            # Non-TTY mode: route meta line to stderr so stdout is clean for piping
            typer.echo(
                f"Pages drilled: {result.pages_drilled}",
                err=not sys.stdout.isatty(),
            )

    if partial:
        raise typer.Exit(code=3)


@wiki_app.command()
def log(
    op: str = typer.Option(..., "--op", help="Log operation type (scan/ingest/lint/create/update/delete/note/query)"),
    title: str = typer.Option(..., "--title", help="Short title for the log entry"),
    detail: Optional[str] = typer.Option(None, "--detail", help="Optional extended detail text"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit LogResult as JSON"),
) -> None:
    """Append a timestamped event to the wiki log.md."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_log(op=op, title=title, detail=detail, workspace_path=workspace_path))
    except (RuntimeError, FileNotFoundError, SystemExit) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[{result.date}] {result.op}: {result.title}")


@wiki_app.command()
def lint(
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    stale_days: int = typer.Option(90, "--stale-days", help="Days before a page is flagged as stale"),
    log_gap_days: int = typer.Option(14, "--log-gap-days", help="Days before a log gap is flagged"),
    json_output: bool = typer.Option(False, "--json", help="Emit LintResult as JSON"),
) -> None:
    """Run mechanical + semantic lint pass over the wiki and report findings."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_lint(workspace_path=workspace_path, stale_days=stale_days, log_gap_days=log_gap_days))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        import dataclasses as _dc
        typer.echo(json.dumps(_dc.asdict(result), indent=2, default=list))
    else:
        # Human-readable multi-section report
        typer.echo(f"Code Wiki lint — {result.wiki}")
        typer.echo(f"Total pages: {result.total_pages}")
        typer.echo("")

        def _section(label: str, items: list) -> None:
            sym = "OK" if not items else "WARN"
            typer.echo(f"[{sym}] {label}: {len(items)}")
            for item in items[:20]:
                typer.echo(f"   - {item}")
            typer.echo("")

        _section("Orphans", result.orphans)
        broken = [f"{src} -> [[{tgt}]]" for src, tgt in result.broken_links]
        _section("Broken wikilinks", broken)
        stale_items = [f"{p} (updated {d})" for p, d in result.stale]
        _section("Stale pages", stale_items)
        _section("Missing frontmatter", result.missing_frontmatter)

        if result.duplicate_titles:
            typer.echo(f"[WARN] Duplicate titles: {len(result.duplicate_titles)}")
            for title, keys in list(result.duplicate_titles.items())[:10]:
                typer.echo(f"   - '{title}': {keys}")
            typer.echo("")
        else:
            typer.echo("[OK] Duplicate titles: 0\n")

        if result.log_gap:
            typer.echo(
                f"[WARN] Log gap: last entry {result.log_gap.get('last_entry')} "
                f"({result.log_gap.get('days_ago')} days ago)\n"
            )
        else:
            typer.echo("[OK] Log gap: recent\n")

        _section("Container drift", result.container_drift)
        _section("Source sync drift", result.source_sync_drift)
        _section("File map drift", result.file_map_drift)
        _section("Package sync drift", result.package_sync_drift)
        _section("Domain placement", result.domain_placement)
        _section("Workflow hints", result.workflow_hints)

        for group, findings in result.semantic_findings.items():
            _section(f"Semantic: {group}", findings)

    if result.errors:
        for err in result.errors:
            typer.echo(f"  error: {err}", err=True)
        raise typer.Exit(code=3)


# ---------------------------------------------------------------------------
# ingest sub-app
# ---------------------------------------------------------------------------

ingest_app = typer.Typer(help="Ingest a source file or work item into the wiki.")
wiki_app.add_typer(ingest_app, name="ingest")


@ingest_app.command(name="source")
def ingest_source(
    path: Path = typer.Argument(..., help="Path to the source file to ingest"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit IngestResult as JSON"),
) -> None:
    """Ingest a source file into the wiki via the ingestor LLM."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_ingest_source(path, workspace_path))
    except IngestorGraphNotInitializedError as e:
        # Phase 40 / INGESTOR-02 / D-01: NOT_INITIALIZED has its own exit code
        # so script consumers can branch on it (3 vs generic 1).
        typer.echo(str(e), err=True)
        raise typer.Exit(code=_gio_exit_codes.NOT_INITIALIZED)
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Ingested: {result.page_path}")
        typer.echo(f"     page_type: {result.page_type}, slug: {result.slug}")


@ingest_app.command(name="work-item")
def ingest_work_item(
    frontmatter: str = typer.Option(..., "--frontmatter", help="YAML frontmatter string for the work item"),
    body: str = typer.Option(..., "--body", help="Markdown body text for the work item"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Page slug (derived from title if omitted)"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing page"),
    pkg_dir: Optional[Path] = typer.Option(None, "--pkg-dir", help="Optional vault package directory for work sub-page linking"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit IngestResult as JSON"),
) -> None:
    """File a structured work item into the wiki workspace."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_ingest_work_item(
                frontmatter_text=frontmatter,
                body=body,
                slug=slug,
                force=force,
                pkg_dir=pkg_dir,
                workspace_path=workspace_path,
            )
        )
    except (RuntimeError, ValueError, FileExistsError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Filed work item: {result.page_path}")
        typer.echo(f"     slug: {result.slug}")


def main() -> None:
    wiki_app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Remove the moved imports from `cli.py`**

In `cli.py`, delete these import lines (the `query`/`log`/`lint`/`ingest` delegations and the now-unused exit-codes import — currently `cli.py:65` and `cli.py:69-77`). The block to remove:

```python
from graph_io import exit_codes as _gio_exit_codes

from graph_wiki_cli.graph_cli.main import graph_app
from graph_wiki_core.commands.init import run_init
from graph_wiki_core.commands.ingest import (
    IngestorGraphNotInitializedError,
    run_ingest_source,
    run_ingest_work_item,
)
from graph_wiki_core.commands.lint import run_lint
from graph_wiki_core.commands.log import run_log
from graph_wiki_core.commands.query import run_query
from graph_wiki_core.commands.scan import run_scan
```

Replace it with (keep `graph_app`, `run_init`, `run_scan`; add the `wiki_app` import):

```python
from graph_wiki_cli.graph_cli.main import graph_app
from graph_wiki_cli.wiki_cli.main import wiki_app
from graph_wiki_core.commands.init import run_init
from graph_wiki_core.commands.scan import run_scan
```

- [ ] **Step 6: Remove the `query` command from `cli.py`**

Delete the entire `query` function (currently `cli.py:544-578`), from its `@app.command()` decorator through `raise typer.Exit(code=3)`:

```python
@app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, "--top-k", help="Pages to drill (3-10)", min=3, max=10),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit QueryResult as JSON"),
    no_state_gate: bool = typer.Option(False, "--no-state-gate", help="No-op; query is read-only"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output (headless mode)"),
) -> None:
    """Query the wiki using hybrid BM25+embedding search with librarian fan-out."""
    # state gate is a no-op for query (read-only) — D-08
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_query(query_text, workspace_path, top_k=top_k))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    partial = result.pages_drilled < top_k

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(result.answer)
        if result.citations:
            typer.echo(f"\nCitations: {', '.join(result.citations)}")
        if not quiet:
            # Non-TTY mode: route meta line to stderr so stdout is clean for piping
            typer.echo(
                f"Pages drilled: {result.pages_drilled}",
                err=not sys.stdout.isatty(),
            )

    if partial:
        raise typer.Exit(code=3)
```

- [ ] **Step 7: Remove the `log` command from `cli.py`**

Delete the entire `log` function (currently `cli.py:581-600`):

```python
@app.command()
def log(
    op: str = typer.Option(..., "--op", help="Log operation type (scan/ingest/lint/create/update/delete/note/query)"),
    title: str = typer.Option(..., "--title", help="Short title for the log entry"),
    detail: Optional[str] = typer.Option(None, "--detail", help="Optional extended detail text"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit LogResult as JSON"),
) -> None:
    """Append a timestamped event to the wiki log.md."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_log(op=op, title=title, detail=detail, workspace_path=workspace_path))
    except (RuntimeError, FileNotFoundError, SystemExit) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[{result.date}] {result.op}: {result.title}")
```

- [ ] **Step 8: Remove the `ingest` sub-app block from `cli.py`**

Delete the ingest section header, the `ingest_app` setup, and both ingest command functions (currently `cli.py:711-776`):

```python
# ---------------------------------------------------------------------------
# ingest sub-app
# ---------------------------------------------------------------------------

ingest_app = typer.Typer(help="Ingest a source file or work item into the wiki.")
app.add_typer(ingest_app, name="ingest")


@ingest_app.command(name="source")
def ingest_source(
    path: Path = typer.Argument(..., help="Path to the source file to ingest"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit IngestResult as JSON"),
) -> None:
    """Ingest a source file into the wiki via the ingestor LLM."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_ingest_source(path, workspace_path))
    except IngestorGraphNotInitializedError as e:
        # Phase 40 / INGESTOR-02 / D-01: NOT_INITIALIZED has its own exit code
        # so script consumers can branch on it (3 vs generic 1).
        typer.echo(str(e), err=True)
        raise typer.Exit(code=_gio_exit_codes.NOT_INITIALIZED)
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Ingested: {result.page_path}")
        typer.echo(f"     page_type: {result.page_type}, slug: {result.slug}")


@ingest_app.command(name="work-item")
def ingest_work_item(
    frontmatter: str = typer.Option(..., "--frontmatter", help="YAML frontmatter string for the work item"),
    body: str = typer.Option(..., "--body", help="Markdown body text for the work item"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Page slug (derived from title if omitted)"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing page"),
    pkg_dir: Optional[Path] = typer.Option(None, "--pkg-dir", help="Optional vault package directory for work sub-page linking"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit IngestResult as JSON"),
) -> None:
    """File a structured work item into the wiki workspace."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_ingest_work_item(
                frontmatter_text=frontmatter,
                body=body,
                slug=slug,
                force=force,
                pkg_dir=pkg_dir,
                workspace_path=workspace_path,
            )
        )
    except (RuntimeError, ValueError, FileExistsError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Filed work item: {result.page_path}")
        typer.echo(f"     slug: {result.slug}")
```

- [ ] **Step 9: Remove the `lint` command block from `cli.py`**

Delete the lint section header and the entire `lint` function (currently `cli.py:783-855`):

```python
# ---------------------------------------------------------------------------
# lint command
# ---------------------------------------------------------------------------


@app.command()
def lint(
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    stale_days: int = typer.Option(90, "--stale-days", help="Days before a page is flagged as stale"),
    log_gap_days: int = typer.Option(14, "--log-gap-days", help="Days before a log gap is flagged"),
    json_output: bool = typer.Option(False, "--json", help="Emit LintResult as JSON"),
) -> None:
    """Run mechanical + semantic lint pass over the wiki and report findings."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_lint(workspace_path=workspace_path, stale_days=stale_days, log_gap_days=log_gap_days))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        import dataclasses as _dc
        typer.echo(json.dumps(_dc.asdict(result), indent=2, default=list))
    else:
        # Human-readable multi-section report
        typer.echo(f"Code Wiki lint — {result.wiki}")
        typer.echo(f"Total pages: {result.total_pages}")
        typer.echo("")

        def _section(label: str, items: list) -> None:
            sym = "OK" if not items else "WARN"
            typer.echo(f"[{sym}] {label}: {len(items)}")
            for item in items[:20]:
                typer.echo(f"   - {item}")
            typer.echo("")

        _section("Orphans", result.orphans)
        broken = [f"{src} -> [[{tgt}]]" for src, tgt in result.broken_links]
        _section("Broken wikilinks", broken)
        stale_items = [f"{p} (updated {d})" for p, d in result.stale]
        _section("Stale pages", stale_items)
        _section("Missing frontmatter", result.missing_frontmatter)

        if result.duplicate_titles:
            typer.echo(f"[WARN] Duplicate titles: {len(result.duplicate_titles)}")
            for title, keys in list(result.duplicate_titles.items())[:10]:
                typer.echo(f"   - '{title}': {keys}")
            typer.echo("")
        else:
            typer.echo("[OK] Duplicate titles: 0\n")

        if result.log_gap:
            typer.echo(
                f"[WARN] Log gap: last entry {result.log_gap.get('last_entry')} "
                f"({result.log_gap.get('days_ago')} days ago)\n"
            )
        else:
            typer.echo("[OK] Log gap: recent\n")

        _section("Container drift", result.container_drift)
        _section("Source sync drift", result.source_sync_drift)
        _section("File map drift", result.file_map_drift)
        _section("Package sync drift", result.package_sync_drift)
        _section("Domain placement", result.domain_placement)
        _section("Workflow hints", result.workflow_hints)

        for group, findings in result.semantic_findings.items():
            _section(f"Semantic: {group}", findings)

    if result.errors:
        for err in result.errors:
            typer.echo(f"  error: {err}", err=True)
        raise typer.Exit(code=3)
```

- [ ] **Step 10: Mount the `wiki` group in `cli.py`**

Find the existing line that mounts the graph group (currently `cli.py:780`):

```python
# graph command namespace: native Typer subapp for code-graph operations.
app.add_typer(graph_app, name="graph")
```

Add the wiki mount immediately after it:

```python
# graph command namespace: native Typer subapp for code-graph operations.
app.add_typer(graph_app, name="graph")

# wiki command namespace: native Typer subapp for wiki-maintenance operations.
app.add_typer(wiki_app, name="wiki")
```

- [ ] **Step 11: Verify `cli.py` has no orphaned references**

The `query`/`log`/`lint`/`ingest` bodies used `asyncio`, `dataclasses`, `json`, `sys`, `Optional` — but `trace`/`bootstrap`/`scan`/`help`/`version` still in `cli.py` use all of these (`asyncio` in bootstrap/scan, `json` in help/trace, `sys` in `_ensure_uv_workspace`/trace, `Optional` in `log`'s old signature is gone but `help_command` and others remain; `dataclasses` is used by bootstrap/scan). Confirm nothing is left dangling:

Run: `grep -n "run_query\|run_log\|run_lint\|run_ingest\|_gio_exit_codes\|IngestorGraphNotInitializedError" packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
Expected: no output.

Run: `uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli"`
Expected: no error (clean import — catches any now-undefined name).

- [ ] **Step 12: Run the new wiki-group test**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_wiki_cli.py -v`
Expected: PASS (all three tests).

- [ ] **Step 13: Repoint `test_cli_query.py` to the new module + `wiki query` path**

In `packages/graph-wiki-cli/tests/unit/test_cli_query.py`, make these edits:

**(a)** The four subprocess invocations of `gw query` → `gw wiki query`. Change each occurrence of:

```python
        ["uv", "run", "--package", "graph-wiki-cli", "gw", "query", "--help"],
```

to:

```python
        ["uv", "run", "--package", "graph-wiki-cli", "gw", "wiki", "query", "--help"],
```

(there are three `--help` ones at lines ~49, ~65, ~96). And in `test_exit_code_1_on_unresolved_vault` (the multi-line list around line 112), change:

```python
            "gw",
            "query",
            "test query",
```

to:

```python
            "gw",
            "wiki",
            "query",
            "test query",
```

**(b)** `test_shared_impl_is_imported_from_commands` — repoint the import and the module attribute check. Replace:

```python
    from graph_wiki_cli.cli import query

    src = inspect.getsource(query)
    assert "run_query" in src
    # The import should be from graph_wiki_core.commands.query
    import graph_wiki_cli.cli as cli_module

    assert hasattr(cli_module, "run_query"), (
        "run_query must be imported at module level in cli.py"
    )
```

with:

```python
    from graph_wiki_cli.wiki_cli.main import query

    src = inspect.getsource(query)
    assert "run_query" in src
    # The import should be from graph_wiki_core.commands.query
    import graph_wiki_cli.wiki_cli.main as wiki_module

    assert hasattr(wiki_module, "run_query"), (
        "run_query must be imported at module level in wiki_cli/main.py"
    )
```

**(c)** The three `monkeypatch.setattr("graph_wiki_cli.cli.run_query", ...)` calls (lines ~154, ~180, ~209) → repoint to the new module. Change each:

```python
        "graph_wiki_cli.cli.run_query",
```

to:

```python
        "graph_wiki_cli.wiki_cli.main.run_query",
```

**(d)** The three CliRunner invocations (lines ~162, ~187, ~216) → prepend `"wiki"`. Change:

```python
        ["query", "test", "--workspace", str(tmp_path)],
```
→
```python
        ["wiki", "query", "test", "--workspace", str(tmp_path)],
```

```python
        ["query", "test", "--workspace", str(tmp_path), "--json"],
```
→
```python
        ["wiki", "query", "test", "--workspace", str(tmp_path), "--json"],
```

```python
        ["query", "test", "--workspace", str(tmp_path), "--no-state-gate"],
```
→
```python
        ["wiki", "query", "test", "--workspace", str(tmp_path), "--no-state-gate"],
```

- [ ] **Step 14: Repoint `test_commands_log.py` to the new module + `wiki log` path**

In `packages/graph-wiki-cli/tests/unit/test_commands_log.py`, in `test_cli_log_json_output`:

Change the monkeypatch target (line ~97):

```python
        "graph_wiki_cli.cli.run_log",
```
→
```python
        "graph_wiki_cli.wiki_cli.main.run_log",
```

Change the invocation (line ~102):

```python
    result = runner.invoke(app, ["log", "--op", "note", "--title", "test", "--json"])
```
→
```python
    result = runner.invoke(app, ["wiki", "log", "--op", "note", "--title", "test", "--json"])
```

- [ ] **Step 15: Update the boundary import-location test + add a symmetry test**

In `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`, replace the body of `test_cli_module_imports_core_commands_not_agent_cli_shim` so it asserts the `run_query` delegation now lives in `wiki_cli/main.py` and that neither module reaches into `graph_wiki_agent`:

```python
def test_cli_module_imports_core_commands_not_agent_cli_shim() -> None:
    """Wiki commands delegate to graph_wiki_core (in wiki_cli/main.py), not graph_wiki_agent.cli."""
    cli_module = importlib.import_module("graph_wiki_cli.cli")
    wiki_module = importlib.import_module("graph_wiki_cli.wiki_cli.main")
    cli_source = inspect.getsource(cli_module)
    wiki_source = inspect.getsource(wiki_module)

    assert "from graph_wiki_core.commands.query import run_query" in wiki_source
    assert "from graph_wiki_core.commands" in wiki_source
    for source in (cli_source, wiki_source):
        assert "graph_wiki_agent.cli" not in source
        assert "from graph_wiki_agent" not in source
```

Then add a symmetry test mirroring `test_graph_package_exposes_moved_cli_module_for_gw_graph_namespace`:

```python
def test_wiki_package_exposes_moved_cli_module_for_gw_wiki_namespace() -> None:
    wiki_module = importlib.import_module("graph_wiki_cli.wiki_cli.main")
    assert hasattr(wiki_module, "main")
    assert "gw wiki" in inspect.getsource(wiki_module)
```

(The `wiki_cli/main.py` module docstring contains the literal `gw wiki`, satisfying the last assertion.)

- [ ] **Step 16: Run the full `graph-wiki-cli` suite**

Run: `uv run --package graph-wiki-cli pytest`
Expected: PASS. Pay attention to `test_cli_help.py` (it asserts `init` is not a top-level command — still true; and `ingest` is no longer top-level, which only strengthens that negative assertion) — it should pass unchanged. Task 3 updates the Bedrock shim test; if `test_plugin_bedrock_shims.py` fails here on the query/ingest/lint cases, that is expected and resolved in Task 3 — but commit Task 2 only once everything *except* those shim cases is green. To scope this commit's verification, run:

`uv run --package graph-wiki-cli pytest --deselect packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
Expected: PASS.

- [ ] **Step 17: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/ \
        packages/graph-wiki-cli/src/graph_wiki_cli/cli.py \
        packages/graph-wiki-cli/tests/unit/test_wiki_cli.py \
        packages/graph-wiki-cli/tests/unit/test_cli_query.py \
        packages/graph-wiki-cli/tests/unit/test_commands_log.py \
        packages/graph-wiki-cli/tests/unit/test_cli_boundary.py
git commit -m "feat(cli): introduce gw wiki command group; move query/log/lint/ingest"
```

---

## Task 3: Update Bedrock plugin shims and their contract test

**Files:**
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`

- [ ] **Step 1: Update the shim-contract test expectations (failing first)**

In `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`, update the three `expected_argv` entries that point at moved commands (the `scan_monorepo.py` and `init_vault.py` cases stay unchanged):

Change the `ingest_source.py` case:

```python
            ["gw", "ingest", "source", "docs/example.md", "--workspace", "/tmp/wiki"],
```
→
```python
            ["gw", "wiki", "ingest", "source", "docs/example.md", "--workspace", "/tmp/wiki"],
```

Change the `lint_wiki.py` case:

```python
            ["gw", "lint", "--workspace", "/tmp/wiki", "--stale-days", "30"],
```
→
```python
            ["gw", "wiki", "lint", "--workspace", "/tmp/wiki", "--stale-days", "30"],
```

Change the `wiki_search.py` case:

```python
            ["gw", "query", "Where is auth documented?", "--top-k", "5"],
```
→
```python
            ["gw", "wiki", "query", "Where is auth documented?", "--top-k", "5"],
```

- [ ] **Step 2: Run the shim test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py -v`
Expected: FAIL on the `ingest_source.py`, `lint_wiki.py`, `wiki_search.py` cases (the shims still emit the old argv); `scan_monorepo.py` and `init_vault.py` pass.

- [ ] **Step 3: Update `wiki_search.py` shim argv**

In `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`, change:

```python
        result = subprocess.run(
            ["gw", "query"] + sys.argv[1:],
            check=True,
        )
```
→
```python
        result = subprocess.run(
            ["gw", "wiki", "query"] + sys.argv[1:],
            check=True,
        )
```

- [ ] **Step 4: Update `ingest_source.py` shim argv**

In `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`, change:

```python
        result = subprocess.run(
            ["gw", "ingest", "source"] + sys.argv[1:],
            check=True,
        )
```
→
```python
        result = subprocess.run(
            ["gw", "wiki", "ingest", "source"] + sys.argv[1:],
            check=True,
        )
```

- [ ] **Step 5: Update `lint_wiki.py` shim argv**

In `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`, change:

```python
        result = subprocess.run(
            ["gw", "lint"] + sys.argv[1:],
            check=True,
        )
```
→
```python
        result = subprocess.run(
            ["gw", "wiki", "lint"] + sys.argv[1:],
            check=True,
        )
```

- [ ] **Step 6: Run the shim test to verify it passes**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py -v`
Expected: PASS (all five cases).

- [ ] **Step 7: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py \
        plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py \
        plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py \
        packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py
git commit -m "feat(plugin): point bedrock shims at gw wiki command paths"
```

---

## Task 4: Update documentation

**Files:**
- Modify: `docs/gw-cli.md`
- Modify: `plugins/graph-wiki/CLAUDE.md` (Bedrock shim mapping table)

> Note: these are doc-only edits with no automated test. Verify by reading the rendered text. `docs/gw-cli.md` already has unrelated uncommitted edits — preserve them.

- [ ] **Step 1: Update the top-level command list in `docs/gw-cli.md`**

In the `## Top-level commands` section, the moved/removed commands must be regrouped under `wiki`. Replace these lines:

```markdown
- `ingest source` — ingest a source file into the wiki.
- `ingest work-item` — file a structured work item into the wiki.
- `query` — query the wiki with hybrid search and librarian fan-out.
- `log` — append a timestamped wiki log entry.
- `lint` — run mechanical and semantic wiki checks.
- `migrate-vault` — migrate an existing vault layout.
- `graph` — code-graph operations.
```

with:

```markdown
- `graph` — code-graph operations.
- `wiki` — wiki-maintenance operations (see below).
```

- [ ] **Step 2: Add a `gw wiki` commands section to `docs/gw-cli.md`**

Immediately after the `## Code graph commands` section (after its closing line `Use `gw graph <subcommand> --help` for command-specific options.`), append a parallel section:

```markdown

## Wiki commands

Wiki-maintenance commands live under the `gw wiki ...` namespace.

Available `gw wiki` subcommands:

- `query` — query the wiki with hybrid search and librarian fan-out.
- `log` — append a timestamped wiki log entry.
- `lint` — run mechanical and semantic wiki checks.
- `ingest source` — ingest a source file into the wiki.
- `ingest work-item` — file a structured work item into the wiki.

Common examples:

```bash
uv run --package graph-wiki-cli gw wiki query "Where is auth documented?" --top-k 5
uv run --package graph-wiki-cli gw wiki lint --workspace /path/to/repo/graph-wiki
uv run --package graph-wiki-cli gw wiki ingest source docs/example.md --workspace /path/to/repo/graph-wiki
```

Use `gw wiki <subcommand> --help` for command-specific options.
```

- [ ] **Step 3: Update the Bedrock shim mapping table in `plugins/graph-wiki/CLAUDE.md`**

In the "Current Bedrock shim mapping" table, update the three moved rows' "Bedrock argv prefix" column. Change:

```markdown
| `ingest_source.py` | `ingest` | `gw ingest source` |
| `lint_wiki.py` | `lint` | `gw lint` |
| `wiki_search.py` | `query` | `gw query` |
```

to:

```markdown
| `ingest_source.py` | `ingest` | `gw wiki ingest source` |
| `lint_wiki.py` | `lint` | `gw wiki lint` |
| `wiki_search.py` | `query` | `gw wiki query` |
```

(The `scan_monorepo.py` / `init_vault.py` rows are unchanged.)

- [ ] **Step 4: Verify no stale top-level references remain in docs**

Run: `grep -n "gw query\|gw log\|gw lint\|gw ingest\|migrate-vault" docs/gw-cli.md plugins/graph-wiki/CLAUDE.md`
Expected: only `gw wiki query` / `gw wiki lint` / `gw wiki ingest …` style matches (the substring `gw query` will still appear inside `gw wiki query` — that is correct). No bare `migrate-vault` line.

- [ ] **Step 5: Commit**

```bash
git add docs/gw-cli.md plugins/graph-wiki/CLAUDE.md
git commit -m "docs: document gw wiki command group; drop migrate-vault"
```

---

## Task 5: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run both package test suites**

Run: `uv run --package graph-wiki-cli pytest`
Expected: PASS (full suite, including the shim test now that Task 3 is done).

Run: `uv run --package graph-wiki-core pytest`
Expected: PASS.

- [ ] **Step 2: Spot-check the new command surface**

Run: `uv run --package graph-wiki-cli gw wiki --help`
Expected: exit 0; lists `query`, `log`, `lint`, `ingest`.

Run: `uv run --package graph-wiki-cli gw wiki ingest --help`
Expected: exit 0; lists `source`, `work-item`.

Run: `uv run --package graph-wiki-cli gw wiki query --help`
Expected: exit 0; lists `--top-k`, `--workspace`, `--json`, `--no-state-gate`, `--quiet`.

- [ ] **Step 3: Confirm the removed/moved commands are gone from the top level**

Run: `uv run --package graph-wiki-cli gw --help`
Expected: exit 0; the Commands list shows `wiki` and `graph` but NOT `query`, `log`, `lint`, `ingest`, or `migrate-vault`.

Run: `uv run --package graph-wiki-cli gw migrate-vault 2>&1; echo "exit=$?"`
Expected: a "No such command" error and a non-zero exit.

- [ ] **Step 4: Confirm the MCP server is unaffected (sanity import)**

The MCP server imports `run_*` functions directly from `graph_wiki_core.commands.*` (not via the CLI command paths), so it needs no change. Sanity-check it still imports:

Run: `uv run --package graph-wiki-mcp python -c "import graph_wiki_mcp.server"`
Expected: no error.

---

## Self-Review

**Spec coverage:**
- Remove `migrate-vault` (CLI command, `run_migrate_vault`, tests) → Task 1. ✓
- New `wiki_cli/main.py` with `wiki_app`; move `query`/`log`/`lint`/`ingest` verbatim → Task 2 (steps 3–10). ✓
- `cli.py` import cleanup + `app.add_typer(wiki_app, name="wiki")` next to graph → Task 2 (steps 5, 10). ✓
- `scan`/`bootstrap`/`trace`/`version`/`help`/`graph` stay top-level → preserved (not touched). ✓
- Bedrock shims (`wiki_search`, `ingest_source`, `lint_wiki`) → Task 3. ✓
- Tests: `test_commands_log`, `test_cli_query`, `test_plugin_bedrock_shims`, `test_cli_boundary` (import-location + symmetry), `test_cli_help` (verified, no change needed) → Tasks 2–3. ✓
- Docs: `docs/gw-cli.md` → Task 4; plus the coupled `plugins/graph-wiki/CLAUDE.md` table (beyond strict spec, but documents the exact contract changed). ✓
- Verification commands → Task 5. ✓

**Beyond-spec items flagged for the executor:** (a) `test_cli_query.py` import of `query` from `cli` and its `monkeypatch` targets, plus all 7 (not 3) query invocations — handled in Task 2 Step 13; (b) `test_commands_log.py` monkeypatch target — Task 2 Step 14; (c) `wiki_io/link_rewriter.py` becomes orphaned but is intentionally left in place.

**Placeholder scan:** No TBD/TODO/"handle edge cases" placeholders; every code step shows the full block to add or remove.

**Type/name consistency:** `wiki_app` (Typer, `name="wiki"`), `ingest_app` (nested via `wiki_app.add_typer(ingest_app, name="ingest")`), `main()` entry — names match across the module body, the `cli.py` mount, and all tests. Monkeypatch/import targets consistently use `graph_wiki_cli.wiki_cli.main`.
