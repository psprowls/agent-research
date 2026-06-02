# graph-wiki Plugin → `entities/` Parity (Slice 1: Scan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `plugins/graph-wiki` Claude-hosted scan produce the same graph-driven single-`entities/`-folder wiki layout that `gw scan` produces — running entirely without AWS Bedrock — and bring every scan-related command/agent/reference doc to that layout.

**Architecture:** Add a `narrate: bool = True` flag to `graph_wiki_core.commands.scan.run_scan`. When `False`, the two LLM fan-out blocks (narrator + file-describer) are skipped and all deterministic steps (graph build → `write_entities` → file-map injection with `— TODO` rows preserved → index/log regeneration) still run. The Bedrock imports (`model_adapter`, `subagent_runtime`) are guarded with a module-top `try/except ImportError` so `narrate=False` works even when neither package is installed. The plugin scan shim calls `run_scan(narrate=False)` **in-process** (no subprocess, no `gw`); the opt-in Bedrock branch still shells out to `gw scan`. The scanner agent collapses from "hand-write pages" to "run the mechanical script → report entities → surface deletions." Reference docs are rewritten from the apps/packages/domains folder vocabulary to the single-`entities/` vocabulary.

**Tech Stack:** Python 3.11+, `uv` workspace, `pytest` + `pytest-asyncio` (`asyncio_mode = auto`), `python-frontmatter`. Packages touched: `graph-wiki-core` (scan core + CLI lives in `graph-wiki-cli`), the `plugins/graph-wiki` tree (shim + markdown).

---

## Orientation — read before starting

**The "old-layout writer" is already gone.** The spec's prose ("retire the old-layout writer path") can mislead: `wiki_io.scan_monorepo.main()` does **not** write pages — it only discovers workspaces, computes a diff, regenerates `dependencies/index.md`, and prints a JSON inventory. The legacy `wiki/packages/<name>/<name>.md` *page-writing* fan-out inside `run_scan` was already removed in a prior phase (D-08 hard cutover; see the comments at `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:820-823` and `:911-913`). In the **plugin's** Claude branch, the page-writing was done by the *scanner agent markdown* (hand-writing `overview.md` files via `ensure_package_pages`). So Slice 1's "retirement" is two concrete things, both in this plan:
1. The plugin scan **shim** stops calling `wiki_io.scan_monorepo.main()` and instead calls `run_scan(narrate=False)`, which writes `entities/` pages deterministically (Task 4).
2. The scanner **agent/command markdown** stops describing hand-written `overview.md` pages and describes the new "run the script, report entities" flow (Task 5).

There is **no Python page-writer to delete.** Do not go hunting for one. Leave `wiki_io.scan_monorepo.main()` in place — `run_scan` still imports ~12 helpers from that module (`ExistingPages`, `compute_diff`, `build_file_map`, `discover_workspaces`, `regenerate_dependencies_index`, …), and `main()` remains a usable standalone inventory CLI.

**Deletions are mechanical, not pre-confirmed.** `write_entities` hard-deletes entity pages whose graph nodes vanished (`ScanResult.entities_deleted`). Slice 1 may **not** modify `write_entities` (out of scope), so the agent cannot confirm *before* deletion. Per `.claude/rules/backward-compatibility.md`, "entity content can be deleted and regenerated at will," so this is acceptable. Task 5 handles the "never silently delete" requirement by surfacing deletions prominently after the run and offering a git-based undo / large-deletion red-flag — see that task.

**Lazy-import decision (chosen by the user):** module-top `try/except ImportError`, not function-local imports. This keeps `graph_wiki_core.commands.scan.make_llm` / `.load_role_config` / `.SubagentPool` as patchable module attributes, so the ~30 existing test patch-sites need **no** changes.

**Test runner:** from repo root,
```bash
uv run --package graph-wiki-core pytest <path>          # graph-wiki-core
uv run --package graph-wiki-cli  pytest <path>          # graph-wiki-cli
uv run pytest packages/wiki-io/                          # wiki-io
```

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | Modify | Add `narrate` param; gate fan-out; `try/except` Bedrock imports |
| `packages/graph-wiki-core/tests/unit/test_scan_narrate.py` | Create | `narrate=False` skips fan-out, preserves placeholders; lazy-import survival |
| `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` | Modify (`scan` cmd ~L569-595) | Add `--no-narrate` flag wired to `narrate=` |
| `packages/graph-wiki-cli/tests/unit/test_cli_scan_narrate.py` | Create | `--no-narrate` passes `narrate=False` to `run_scan` |
| `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py` | Rewrite | Claude branch → in-process `run_scan(narrate=False)`; Bedrock branch unchanged |
| `plugins/graph-wiki/agents/scanner.md` | Rewrite | New "run script → report entities → surface deletions" flow |
| `plugins/graph-wiki/commands/scan.md` | Rewrite | Same flow, command-level |
| `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md` | Rewrite | Graph build + `write_entities` + 7 kinds |
| `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` | Edit | Page routing collapses to single `entities/` (detection unchanged) |
| `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md` | Edit | `entities/` layout + per-kind frontmatter |
| `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md` | Edit | Entity page templates replace app/package/domain page formats |
| `plugins/graph-wiki/skills/graph-wiki/references/monorepo-principles.md` | Edit | Layout prose references `entities/` |
| `plugins/graph-wiki/CLAUDE.md` | Edit (L62-73) | "Wiki layout invariants" → `entities/` |

---

## Task 1: `run_scan` gains `narrate` flag + guarded Bedrock imports

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
- Test: `packages/graph-wiki-core/tests/unit/test_scan_narrate.py` (create)

The change has three parts: (a) wrap the two Bedrock imports in `try/except`, (b) add the `narrate` parameter, (c) gate the narrator and file-describer fan-out blocks on `narrate`. After this, `run_scan(narrate=False)` touches none of `make_llm` / `load_role_config` / `SubagentPool` / `TaskResult`.

- [ ] **Step 1: Write the failing test**

Create `packages/graph-wiki-core/tests/unit/test_scan_narrate.py`. This reuses the seed/fixtures style from `test_scan_graph_integration.py` (copy the two small seed helpers verbatim — the engineer may read tasks out of order, so they are inlined here).

```python
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter
import pytest

from graph_io import exit_codes
from graph_wiki_core.commands import scan as scan_module


def _seed_minimal_graph(db_path: Path) -> None:
    """One package node pkg-a (no domain), uri pkg:org/repo/pkg-a."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\": \"python\"}', "
            "'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n\nNo pinned containers.\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    return workspace


def test_narrate_false_skips_fanout_and_keeps_placeholder(tmp_workspace, monkeypatch):
    """run_scan(narrate=False): zero SubagentPool.run_all calls; the entity page
    keeps the template `## Narrative` placeholder and `— TODO` file-map rows."""
    workspace = tmp_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    _seed_minimal_graph(workspace / ".graph" / "code.db")
    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", "")
    )

    run_all_calls: list = []

    async def _spy_run_all(self, *, items, task, role, model_id, max_concurrency):
        run_all_calls.append(role)
        from subagent_runtime.pool import FanOutResult
        return FanOutResult()

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _spy_run_all)
    monkeypatch.setattr(scan_module, "make_llm", lambda role, *, model_override=None: MagicMock())

    # Minimal deterministic file map so the package page gets a File map section.
    pkg_a_block = (
        "## File map - pkg-a\n"
        "TODO — overview of this package's tree.\n\n"
        "### pkg-a/\n"
        "TODO — describe what this directory contains.\n\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
    )
    fake_ws = [{
        "name": "pkg-a", "path": "packages/pkg-a",
        "wiki_relative_path": "packages/pkg-a/overview.md",
        "type": "library", "language": "python",
        "changed_files": None, "file_map": pkg_a_block,
    }]
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: fake_ws)
    monkeypatch.setattr(
        scan_module, "_load_existing_pages",
        lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}),
    )
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module, "compute_diff",
        lambda ws, ex: {"new": ["pkg-a"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    result = asyncio.run(
        scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False, narrate=False)
    )

    assert run_all_calls == [], f"narrate=False must not run any fan-out; got {run_all_calls}"
    assert "pkg:org/repo/pkg-a" in result.entities_created
    assert result.entities_narrated == []

    page = next(
        p for p in (wiki / "entities").glob("*.md")
        if frontmatter.load(p).metadata.get("uri") == "pkg:org/repo/pkg-a"
    )
    text = page.read_text(encoding="utf-8")
    # Structural parity: Narrative placeholder intact, file-map rows still — TODO.
    assert "_(scanner will populate on next scan)_" in text
    assert "| `pyproject.toml` | file | — TODO |" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_narrate.py::test_narrate_false_skips_fanout_and_keeps_placeholder -v`
Expected: FAIL with `TypeError: run_scan() got an unexpected keyword argument 'narrate'`.

- [ ] **Step 3: Guard the Bedrock imports (module top)**

In `scan.py`, replace the two eager imports at lines 24-25:

```python
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult
```

with a guarded block (place it at the same location, after the `langchain_core.messages` import on line 23):

```python
# Bedrock fan-out stack — imported only for the narrated path (narrate=True).
# Guarded so the plugin's Claude branch (narrate=False) runs without these
# workspace members installed. When absent, the narrator/file-describer blocks
# are unreachable (gated on `narrate`), so the None bindings are never called.
try:
    from model_adapter.loader import load_role_config, make_llm
    from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult
except ImportError:  # pragma: no cover — exercised by the lazy-import test via reload
    load_role_config = make_llm = None  # type: ignore[assignment]
    SubagentPool = TaskResult = FanOutResult = None  # type: ignore[assignment]
```

Note: `FanOutResult` appears only in the string annotation `narrator_result: FanOutResult | None = None` (line 825) — `from __future__ import annotations` (line 1) makes that a never-evaluated string, so binding it to `None` at runtime is safe.

- [ ] **Step 4: Add the `narrate` parameter**

In the `run_scan` signature (lines 592-598), add `narrate` as the final keyword parameter:

```python
async def run_scan(
    workspace_path: Path | None = None,
    no_file_map: bool = False,
    max_depth: int = 3,
    repo_path: Path | None = None,
    model_override: str | None = None,
    narrate: bool = True,
) -> ScanResult:
```

Add to the docstring's Args section (after the `model_override` entry, before `Returns:`):

```python
        narrate:        When True (default), run the narrator and file-describer
                        Bedrock fan-outs that fill `## Narrative` bodies and
                        `— TODO` file-map descriptions. When False, skip both
                        fan-outs entirely (structural-only scan) — entity pages
                        keep their `## Narrative` placeholder and `— TODO` rows.
                        The plugin's Claude branch calls with narrate=False so the
                        scan needs neither model_adapter nor subagent_runtime.
```

- [ ] **Step 5: Gate the narrator fan-out**

In `run_scan`, change line 854 from:

```python
            if entity_write_result.needs_narrative:
```

to:

```python
            if narrate and entity_write_result.needs_narrative:
```

This leaves `narrator_items` empty when `narrate=False`, so the `if narrator_items:` block (line 868, which performs the `make_llm` / `SubagentPool` calls) is skipped.

- [ ] **Step 6: Gate the file-describer fan-out**

Change line 1051 from:

```python
        if file_mapped_pages and conn is not None:
```

to:

```python
        if narrate and file_mapped_pages and conn is not None:
```

This skips the entire Step 10c describer block (the only other `make_llm` / `SubagentPool` site) when `narrate=False`. Deterministic file-map *injection* (Step 10b, lines 956-1041) still runs — the `— TODO` rows are written but not filled.

- [ ] **Step 7: Run the new test to verify it passes**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_narrate.py::test_narrate_false_skips_fanout_and_keeps_placeholder -v`
Expected: PASS.

- [ ] **Step 8: Run the full existing scan suite — no regressions**

Run:
```bash
uv run --package graph-wiki-core pytest \
  packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py \
  packages/graph-wiki-core/tests/unit/test_commands_scan.py \
  packages/graph-wiki-core/tests/commands/test_scan_parity.py \
  packages/graph-wiki-core/tests/test_command_overrides.py -v
```
Expected: all PASS. (Because the `try/except` keeps `make_llm` / `load_role_config` / `SubagentPool` as real module attributes, every existing patch-site is unaffected. The narrated default path is unchanged.)

- [ ] **Step 9: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_scan_narrate.py
git commit -m "feat(scan): add narrate flag to run_scan; guard Bedrock imports

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Lazy-import survival test (Bedrock un-importable)

**Files:**
- Test: `packages/graph-wiki-core/tests/unit/test_scan_narrate.py` (extend)

Prove the spec's hard requirement: with `model_adapter` / `subagent_runtime` un-importable, `run_scan(narrate=False)` still completes. We force the `try/except` into its `except` branch by breaking the modules in `sys.modules` and reloading `scan.py`, then restore in `finally`.

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-core/tests/unit/test_scan_narrate.py`:

```python
def test_narrate_false_runs_without_bedrock_installed(tmp_workspace, monkeypatch):
    """With model_adapter/subagent_runtime un-importable, importing scan.py binds
    the Bedrock symbols to None (except branch) and run_scan(narrate=False) still
    completes end-to-end."""
    import importlib
    import sys

    workspace = tmp_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    _seed_minimal_graph(workspace / ".graph" / "code.db")

    # Make the Bedrock packages raise ImportError on import.
    monkeypatch.setitem(sys.modules, "model_adapter.loader", None)
    monkeypatch.setitem(sys.modules, "subagent_runtime.pool", None)

    reloaded = importlib.reload(scan_module)
    try:
        # The except branch bound the symbols to None.
        assert reloaded.make_llm is None
        assert reloaded.SubagentPool is None

        reloaded_setattr = monkeypatch.setattr
        reloaded_setattr(reloaded, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""))
        reloaded_setattr(reloaded, "discover_workspaces", lambda *a, **kw: [])
        reloaded_setattr(
            reloaded, "_load_existing_pages",
            lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}),
        )
        reloaded_setattr(reloaded, "attach_changed_files", lambda *a, **kw: None)
        reloaded_setattr(
            reloaded, "compute_diff",
            lambda ws, ex: {"new": [], "unchanged": [], "deleted": [], "renamed": []},
        )
        reloaded_setattr(
            reloaded, "compute_state_gate",
            lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
        )

        result = asyncio.run(
            reloaded.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True, narrate=False)
        )
        assert result is not None
    finally:
        # Restore real Bedrock symbols for the rest of the session.
        monkeypatch.undo()
        importlib.reload(scan_module)
```

- [ ] **Step 2: Run to verify it passes**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_narrate.py -v`
Expected: both tests PASS. (If the reload-restore leaks, run the full Step-8 suite from Task 1 again to confirm no cross-test pollution.)

- [ ] **Step 3: Confirm no module-state leak**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -v`
Expected: PASS (the `finally: importlib.reload` restored the real symbols).

- [ ] **Step 4: Commit**

```bash
git add packages/graph-wiki-core/tests/unit/test_scan_narrate.py
git commit -m "test(scan): run_scan(narrate=False) survives missing Bedrock deps

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `gw scan --no-narrate` CLI flag

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` (the `scan` command, lines 569-595)
- Test: `packages/graph-wiki-cli/tests/unit/test_cli_scan_narrate.py` (create)

Expose the flag so CLI and plugin exercise the same code path. Default stays narrated.

- [ ] **Step 1: Write the failing test**

Create `packages/graph-wiki-cli/tests/unit/test_cli_scan_narrate.py`:

```python
from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from graph_wiki_cli.cli import app
from graph_wiki_core.commands.scan import ScanResult

runner = CliRunner()


def _ok_result() -> ScanResult:
    return ScanResult(state_gate={"allowed": True, "reason": "x", "head_commit": "y"})


def test_scan_no_narrate_passes_narrate_false():
    with patch("graph_wiki_cli.cli.run_scan") as mock_run:
        async def _fake(**kwargs):
            mock_run.captured = kwargs
            return _ok_result()
        mock_run.side_effect = _fake
        result = runner.invoke(app, ["scan", "--no-narrate"])
    assert result.exit_code == 0, result.output
    assert mock_run.captured["narrate"] is False


def test_scan_default_is_narrated():
    with patch("graph_wiki_cli.cli.run_scan") as mock_run:
        async def _fake(**kwargs):
            mock_run.captured = kwargs
            return _ok_result()
        mock_run.side_effect = _fake
        result = runner.invoke(app, ["scan"])
    assert result.exit_code == 0, result.output
    assert mock_run.captured["narrate"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_cli_scan_narrate.py -v`
Expected: FAIL — `--no-narrate` is an unknown option (exit code 2), and `run_scan` is called without a `narrate` kwarg.

- [ ] **Step 3: Add the flag**

In `cli.py`, in the `scan` command (lines 569-579), add a `no_narrate` option and thread it through. Change the signature block to add (after `max_depth`, before `json_output`):

```python
    no_narrate: bool = typer.Option(
        False, "--no-narrate", help="Skip narrator/file-describer fan-out (structural-only, no Bedrock)"
    ),
```

and change the `run_scan(...)` call (line 579) to:

```python
        result = asyncio.run(
            run_scan(
                workspace_path=workspace_path,
                no_file_map=no_file_map,
                max_depth=max_depth,
                narrate=not no_narrate,
            )
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_cli_scan_narrate.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/cli.py \
        packages/graph-wiki-cli/tests/unit/test_cli_scan_narrate.py
git commit -m "feat(cli): gw scan --no-narrate for structural-only scans

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Plugin scan shim → in-process `run_scan(narrate=False)`

**Files:**
- Rewrite: `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py` (existing — must still pass; no edit expected)

The Claude branch stops importing `wiki_io.scan_monorepo.main` and instead calls `run_scan(narrate=False)` directly. The `run_scan` import lives **inside the Claude branch** (after the backend check) so the Bedrock branch — and the existing `test_plugin_bedrock_shims.py`, which installs a stub `wiki_io` — never imports `graph_wiki_core.commands.scan`.

- [ ] **Step 1: Verify the existing Bedrock-shim contract test still passes (baseline)**

Run: `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py -v`
Expected: PASS (5 parametrized cases green). This is the regression guard for Step 4.

- [ ] **Step 2: Rewrite the shim**

Replace the entire contents of `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py` with:

```python
#!/usr/bin/env python3
"""Plugin shim for scan — graph-driven entities/ scan in-process (claude) or gw (bedrock).

Claude branch: imports run_scan from graph_wiki_core and runs it with
narrate=False (structural-only — writes entity pages + indexes deterministically,
no Bedrock fan-out, no model_adapter/subagent_runtime needed). Bedrock branch:
shells out to `gw scan` (narrated), preserving the user's trailing argv.
"""
import argparse
import asyncio
import dataclasses
import json
import subprocess
import sys
from pathlib import Path

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scan the monorepo into wiki/entities/.")
    p.add_argument("--workspace", default="", help="Workspace path (default: GRAPH_WIKI_WORKSPACE)")
    p.add_argument("--no-file-map", action="store_true", help="Skip per-package file maps")
    p.add_argument("--max-depth", type=int, default=3, help="Max file-map directory depth")
    p.add_argument("--json", action="store_true", dest="json_output", help="Emit ScanResult as JSON")
    return p.parse_args(argv)


def main() -> None:
    try:
        from _config import backend_for
    except ImportError:
        def backend_for(cmd: str, repo: object = None) -> str:  # type: ignore[misc]
            return "claude"

    backend = backend_for("scan")

    if backend == "bedrock":
        result = subprocess.run(
            ["gw", "scan"] + sys.argv[1:],
            check=True,
        )
        sys.exit(result.returncode)

    # Claude branch — in-process, structural-only (no Bedrock).
    from graph_wiki_core.commands.scan import ScanAbortedError, run_scan

    args = _parse_args(sys.argv[1:])
    workspace_path = Path(args.workspace) if args.workspace else None
    try:
        result = asyncio.run(
            run_scan(
                workspace_path=workspace_path,
                no_file_map=args.no_file_map,
                max_depth=args.max_depth,
                narrate=False,
            )
        )
    except ScanAbortedError as e:
        print(f"[error] scan aborted: {e}", file=sys.stderr)
        sys.exit(2)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    if args.json_output:
        print(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        c = len(result.entities_created)
        u = len(result.entities_updated)
        d = len(result.entities_deleted)
        print(f"Scan complete: entities +{c} ~{u} -{d}")
        for uri in result.entities_deleted:
            print(f"  - deleted: {uri}")
        for err in result.entity_errors:
            print(f"  error: {err}", file=sys.stderr)

    if result.entity_errors:
        sys.exit(3)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Re-run the Bedrock-shim contract test**

Run: `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py -v`
Expected: PASS. The `scan_monorepo.py` case still maps `--workspace /tmp/wiki --json` → `["gw", "scan", "--workspace", "/tmp/wiki", "--json"]` and the bedrock branch returns before any `graph_wiki_core` import.

- [ ] **Step 4: Smoke-test the Claude branch imports Bedrock-free**

Run:
```bash
uv run --project "$PWD" python -c "import ast,sys; \
src=open('plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py').read(); \
ast.parse(src); print('shim parses OK')"
uv run --package graph-wiki-core python -c "from graph_wiki_core.commands.scan import run_scan; print('run_scan importable')"
```
Expected: both print success. (The second line confirms `graph_wiki_core.commands.scan` imports without requiring the narrated path; the guarded import means it succeeds even if model_adapter/subagent_runtime were absent.)

- [ ] **Step 5: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py
git commit -m "feat(plugin): scan shim calls run_scan(narrate=False) in-process

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Rewrite `agents/scanner.md` + `commands/scan.md` to the entities flow

**Files:**
- Rewrite: `plugins/graph-wiki/agents/scanner.md`
- Rewrite: `plugins/graph-wiki/commands/scan.md`

These are prose-and-instruction files (no automated test). The new flow: **run the mechanical script (it writes `entities/` pages + indexes + log) → report entities by URI → surface deletions (never silently) → suggest follow-ups.** No hand-writing of pages, no per-package prose review (structural-only), no `update_index`/`update_tokens`/`append_log` steps (the script already does index + log; token stamping is not part of the entity scan).

**Deletion handling (load-bearing):** `write_entities` hard-deletes vanished entity pages *during* the script run — the agent can't pre-confirm. Honor "never silently delete" by: (1) always reporting the deleted URIs prominently; (2) if the wiki is under version control, showing `git status --short wiki/entities/` and offering `git checkout -- <files>` to undo; (3) treating **>10 deletions** as a red-flag (likely a bad repo path or a failed graph build) — STOP and ask the user before proceeding. Entity pages regenerate deterministically on the next scan, so undo is always safe.

- [ ] **Step 1: Rewrite `agents/scanner.md`**

Replace the file body (keep the YAML frontmatter block at the top, lines 1-9, but update the `description:` to the entities vocabulary) with this content:

````markdown
---
name: scanner
description: Dispatched sub-agent that walks the monorepo, builds the code graph, and writes one graph-derived page per admitted entity into the wiki's single `entities/` folder (repository, domain, package, app, agent_plugin, dependency, test_suite). Reports added/updated/deleted entities by URI and surfaces deletions for confirmation. Spawn when the user says "scan the monorepo", "update entity pages", "catch the wiki up to the code", or runs /graph-wiki:scan.
skills: [graph-wiki, obsidian-markdown]
domain: engineering
model: sonnet
tools: [Read, Write, Edit, Bash, Grep, Glob]
context: fork
---

# scanner

## Role

You keep the wiki's single `<workspace>/wiki/entities/` folder in sync with what the code graph says the repo contains. The mechanical script does the writing: it builds the code graph and renders one page per admitted entity — `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite` — into `entities/`, with URI-based filenames (`pkg_<name>.md`, `app_<name>.md`, `dep_<name>.md`, `domain_<name>.md`, `repo_<name>.md`, `agent-plugin_<name>.md`, `unit_tests_<pkg>.md`, …). Your job is to **run the script, report what changed, and surface deletions** — not to hand-write pages.

The scan is **structural-only**: pages carry a `## Narrative\n_(scanner will populate on next scan)_` placeholder and `— TODO` file-map rows. You do NOT fill prose. (Prose is filled later by ingest/query.)

Spawned per scan, not long-running.

## Inputs

- Repo root and wiki path (resolved automatically via `workspace_io`)
- Current state of `<workspace>/wiki/entities/`

## Workflow

Follow `references/scan-workflow.md`. Summary:

### 1. Run the mechanical scan
```bash
uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/scan_monorepo.py --json
```

This single command builds the code graph, writes/updates/deletes `entities/*.md` pages deterministically, injects deterministic file maps (Description cells left `— TODO`), regenerates `index.md` + per-folder sub-indexes + `dependencies/index.md`, and appends a `scan` entry to `log.md`. It emits a `ScanResult` JSON with `entities_created`, `entities_updated`, `entities_deleted` (URIs), and `entity_errors`.

It runs **without Bedrock** (structural-only — `narrate=False`). It does NOT call any LLM.

**Layout-aware:** when the wiki's `CLAUDE.md` pins a `graph-wiki:layout` block, discovery scopes to those containers automatically.

### 2. Report entities
From the JSON, report to the user:
- **Created** — new entity pages (list by URI / filename)
- **Updated** — entity pages whose graph-derived frontmatter changed
- **Deleted** — entity pages removed because their graph node vanished
- Any `entity_errors`

### 3. Surface deletions (never silently)
The script has already applied deletions. Do not let them pass silently:
- Always list the deleted URIs.
- If `<workspace>/wiki/` is under version control, run `git -C <workspace>/wiki status --short entities/` and offer to undo any deletion the user objects to with `git -C <workspace>/wiki checkout -- entities/<file>`.
- Entity pages regenerate deterministically on the next scan, so undo/redo is always safe.

### 4. Report
Bulleted wikilinks to the changed entity pages. Suggest follow-ups (e.g. `/graph-wiki:lint` to catch drift, `/graph-wiki:ingest` on a README/spec to flesh out `## Narrative` and file-map descriptions).

## Rules

- **Invoke the `obsidian-markdown` skill** if you hand-edit any entity page (you normally won't — the script owns them). Scanner-owned frontmatter keys are replaced every scan; human keys (`status`, `last_reviewed`, `owner`, `notes`) and a non-empty `summary` are preserved.
- **Never silently delete.** Always surface deletions; offer git undo.
- **Structural-only.** Do not fill `## Narrative` or file-map descriptions during scan.
- **Don't hand-write entity pages.** The script renders them from the graph.

## Red flags

Stop and ask before proceeding if:
- `entities_deleted` has **>10** entries (likely a bad repo path or a failed graph build — inspect before committing).
- `entity_errors` is non-empty (partial write — report the errors verbatim).
- The script reports a hard abort (`scan aborted: cg update failed …`) — surface the diagnostic; do not retry blindly.
````

- [ ] **Step 2: Rewrite `commands/scan.md`**

Replace the "What happens" / "Rules" / "Sub-agent" sections so they describe the entities flow. Keep the frontmatter, the `## Usage` block, the `## Layout reconcile`, `## In-repo docs`, and `## When to run` sections. Replace the `description:` frontmatter line and the `## What happens` + `## Rules` sections with:

```markdown
## What happens

1. **Graph build + write** — `scripts/scan_monorepo.py` builds the code graph and writes one page per admitted entity into `<workspace>/wiki/entities/` (kinds: `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite`). Pages use URI-based filenames and are structural-only (`## Narrative` placeholder, `— TODO` file-map rows).
2. **Frontmatter** — scanner-owned keys (`uri`, `kind`, `depends_on`, `language`, …) are replaced from the graph each scan; human keys (`status`, `last_reviewed`, `owner`, `notes`) and a non-empty `summary` are preserved.
3. **Indexes + log** — `index.md`, per-folder sub-indexes, and `dependencies/index.md` are regenerated; a `scan` entry is appended to `log.md`.
4. **Report** — created / updated / deleted entities are reported by URI. Deletions are surfaced for confirmation (with a git-based undo when the wiki is versioned); >10 deletions is a stop-and-ask red flag.

This runs entirely **without Bedrock** (structural-only). No prose is generated.

## Rules

- **Don't silently delete entity pages** — always surface deletions; >10 is a red flag.
- **Structural-only** — `## Narrative` and file-map descriptions are filled later by ingest/query, not by scan.
- **The graph is the source** — entity pages are rendered from the code graph, not hand-written.
```

Also update the `description:` frontmatter line (line 3) to:

```
description: Build the code graph and write one page per admitted entity (repository, domain, package, app, agent_plugin, dependency, test_suite) into the wiki's single entities/ folder. Reports created/updated/deleted entities by URI; surfaces deletions for confirmation. Workspace and repo discovered automatically. Usage /graph-wiki:scan
```

- [ ] **Step 3: Verify no stale apps/packages/domains routing language remains**

Run:
```bash
grep -nE "overview\.md|wiki/packages/|wiki/apps/|domains/<d>/packages|ensure_package_pages|file_map_testing|update_tokens|append_log\.py|update_index\.py" \
  plugins/graph-wiki/agents/scanner.md plugins/graph-wiki/commands/scan.md
```
Expected: no matches. (The new flow has none of these — the script subsumes index/log; there is no per-container `overview.md`.)

- [ ] **Step 4: Commit**

```bash
git add plugins/graph-wiki/agents/scanner.md plugins/graph-wiki/commands/scan.md
git commit -m "docs(plugin): rewrite scanner agent + scan command for entities/ flow

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Rewrite `references/scan-workflow.md` + edit `references/detection-workflow.md`

**Files:**
- Rewrite: `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md`
- Edit: `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md`

Container *detection* is unchanged (it still feeds the pinned layout block). Only page *routing* collapses from apps/packages/domains folders to the single `entities/` folder. Use **Appendix A (Entities Vocabulary)** as the canonical source for kinds, prefixes, filenames, and frontmatter.

- [ ] **Step 1: Rewrite `scan-workflow.md`**

Rewrite around the graph-driven flow. The new structure (replace the whole file body after the `# Scan Workflow` H1):

```markdown
## Purpose

Keep the wiki's single `entities/` folder in sync with the code graph. The scan is mechanical and structural-only — it builds the graph, renders one page per admitted entity, and never calls an LLM.

## Inputs

- Repo root + wiki path (resolved via `workspace_io`).
- The pinned `graph-wiki:layout` block in `wiki/CLAUDE.md` (scopes graph build + discovery to pinned containers; detection itself is unchanged — see `detection-workflow.md`).

## What gets written

One page per admitted entity into `<workspace>/wiki/entities/`, across the **7 admitted kinds**: `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite`. Filenames are URI-derived (`pkg_<name>.md`, `app_<name>.md`, `dep_<name>.md`, `domain_<name>.md`, `repo_<name>.md`, `agent-plugin_<name>.md`, suite-kind-aware `unit_tests_<pkg>.md` / `int_tests_<pkg>.md`), with a `__<6hex>` suffix on collision. See Appendix A in the plan / `wiki-schema.md` for the full vocabulary.

## Step-by-step

### 1. Run the mechanical scan
`scan_monorepo.py --json` builds the graph (`cg update`, incremental), calls `write_entities`, injects deterministic file maps (Description cells `— TODO`), regenerates indexes, and appends to the log. Structural-only: `## Narrative` keeps its `_(scanner will populate on next scan)_` placeholder.

### 2. Report entities
From the `ScanResult` JSON: `entities_created`, `entities_updated`, `entities_deleted` (URIs), `entity_errors`.

### 3. Surface deletions
`write_entities` hard-deletes pages for vanished graph nodes. Report them; never silently. Offer a git undo when the wiki is versioned. >10 deletions is a red flag (bad repo path / failed graph build) — stop and ask.

### 4. Update cross-references / indexes
Already done by the script (`index.md`, per-folder sub-indexes, `dependencies/index.md`). No separate step.

### 5. Append to log
Already done by the script.

### 6. Report back
Bulleted wikilinks; suggest `/graph-wiki:lint` and `/graph-wiki:ingest` to flesh out narratives.

## Frontmatter contract

Scanner-owned keys (replaced every scan): `uri`, `kind`, `graph_name`, `last_scan_at`, plus per-kind edge/attr keys (`depends_on`, `domains`, `test_suites`, `entry_points`, `language`, `version`, `app_kind`, `app_signals`, `parent_domain`, `sub_domains`, `packages`, `tested_packages`, `suite_kind`, `file_count`, `ecosystem`, `used_by`, `versions_in_use`, `package_count`). Human keys preserved verbatim: `status`, `last_reviewed`, `owner`, `notes`. `summary` is fill-when-empty.

## Anti-patterns

- Hand-writing `entities/*.md` pages (the graph renders them).
- Filling `## Narrative` or file-map descriptions during scan (structural-only).
- Silently accepting a large deletion set.
- Expecting `apps/`, `packages/`, or `domains/` page folders — there are none; everything is in `entities/`.
```

(The previous file's "Package-family containers (deep / nested manifests)" worked example concerns *detection*, which is unchanged — move its essence to `detection-workflow.md` if it isn't already there; container detection still produces the pinned layout block that scopes the graph build.)

- [ ] **Step 2: Edit `detection-workflow.md`**

Detection rules (lines 10-17) are unchanged. Update the **"Container types and their templates"** table (lines 19-27) and the closing **"Scripts"** section so routing reflects `entities/`. Replace the table's "Vault dir contents" / "Per-page template" / "Per-page category" columns with an `entities/` note: after the table, add a paragraph:

```markdown
> **Page routing (2026-06).** Container *classification* still pins the layout block (used to scope the graph build). Page *routing*, however, no longer creates per-container `apps/`/`packages/`/`domains/` folders: every workspace becomes a graph node and is rendered as a single page under `wiki/entities/` (kind `package` / `app`; a `domain` container also yields `domain` entity pages). The "Per-page template / category" columns below describe the *graph kind* each container contributes, not a folder.
```

And in the "Scripts" section (lines 50-55), change the `scan_monorepo.py` line to:

```markdown
- `scan_monorepo.py` — plugin shim: runs the graph build + `write_entities` in-process (`run_scan(narrate=False)`), writing pages into `wiki/entities/`. Reads the pinned layout block to scope discovery; surfaces reconcile drift.
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -nE "overview\.md|wiki/packages/<|wiki/apps/<|domains/<d>/packages" \
  plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
```
Expected: no matches in `scan-workflow.md`. (References in `detection-workflow.md` to the detection *shape* `<container>/<child>/<manifest>` are fine — that's detection, not routing.)

- [ ] **Step 4: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md \
        plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md
git commit -m "docs(plugin): scan + detection reference docs route to entities/

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Foundational schema docs + plugin `CLAUDE.md` → `entities/` vocabulary

**Files:**
- Edit: `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`
- Edit: `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md`
- Edit: `plugins/graph-wiki/skills/graph-wiki/references/monorepo-principles.md`
- Edit: `plugins/graph-wiki/CLAUDE.md` (lines 62-73)

Use **Appendix A** as the canonical vocabulary. These are large prose docs; the edits are targeted section swaps, not full rewrites.

- [ ] **Step 1: `wiki-schema.md` — Layout + category frontmatter**

In `## Layout` (lines 5-53), replace the apps/packages/domains folder description with the single-`entities/` layout: the wiki's fixed subdirs are `entities/`, `concepts/`, `sources/`, `adrs/`, `architecture/`, `.templates/` (source of truth: `wiki_io.init_vault.FIXED_VAULT_DIRS`), plus `dependencies/` for the auto-rendered deps index. There is no inner vault dir, and there are no conditional `apps/`/`packages/`/`domains/` page folders. Bootstrap seeds `entities/.gitkeep` (self-healing — removed once real pages exist, restored when all are swept).

In `## Category-specific frontmatter` (lines 77-336), the per-page sections (`### App pages`, `### Package pages`, `### Domain pages`) currently describe legacy frontmatter. Replace the App/Package/Domain subsections with a single **`### Entity pages`** subsection that documents the entity frontmatter contract from Appendix A: the scanner-owned key set (replaced every scan), the human-preserved keys (`status`, `last_reviewed`, `owner`, `notes`), `summary` fill-when-empty, the `uri`/`kind`/`graph_name`/`last_scan_at` universals, and the per-kind edge-derived keys. Keep the non-entity sections (`### Concept pages`, `### Dependency pages`, `### Work pages`, `### Source pages`, `### Architecture pages`, `### ADR pages`) — those categories are unchanged in Slice 1.

In `## Naming conventions` (line 337), add the entity filename rule: `<prefix>_<name>[__<6hex>].md` with the prefix-per-kind table from Appendix A.

- [ ] **Step 2: `page-formats.md` — entity page templates**

Sections `## 1. App page`, `## 2. Package page`, `## 3. Domain page` (lines 82-362) describe the legacy multi-section pages. Replace these three with entity-page formats that match the packaged templates (`packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md`). Each entity page has scanner-owned frontmatter, a `## Narrative` section (the only H2 the scanner rewrites; placeholder `_(scanner will populate on next scan)_`), and — for `package`/`app` — a `## File map - <name>` section in the `| Path | Kind | Description |` table format. Show the `entity-package.md` shape as the worked example:

````markdown
## Entity page (package / app)

```markdown
---
title: <Package Name>
uri: pkg:org/repo/<name>
kind: package
graph_name: <graph-name>
last_scan_at: <YYYY-MM-DD>
domains: []
depends_on: []
test_suites: []
entry_points: []
language: ""
version: ""
updated: <YYYY-MM-DD>
---

# <name>

## Narrative
_(scanner will populate on next scan)_

## File map - <name>
| Path | Kind | Description |
|---|---|---|
| `<file>` | file | — TODO |
```
```
````

Keep the `## File map convention (apps and packages)` (lines 5-19) — it still applies. Keep the non-entity page formats (`## 4. Concept`, `## 5. Source`, `## 6. Architecture`, `## 7. ADR`, `## 8. Dependency`, `## 9. Work`). For the `## 8. Dependency page` entity (kind `dependency`) and any `test_suite`/`agent_plugin`/`repository` formats, note they live in `entities/` with the prefixes from Appendix A; you do not need to author full bodies for each — point to the packaged `entity-*.md` templates as the source of truth.

- [ ] **Step 3: `monorepo-principles.md` — layout prose**

In `## Differences from the generic LLM Wiki` (line 45) and any layout-referencing prose, replace mentions of `apps/`/`packages/`/`domains/` page folders with "a single graph-derived `entities/` folder (one page per admitted entity kind)." This is light-touch — only the sentences that describe *where pages live*.

- [ ] **Step 4: Plugin `CLAUDE.md` — Wiki layout invariants (lines 62-73)**

Update the `<workspace>/wiki/` bullet's subdir list. Change:

```
- `<workspace>/wiki/` — the LLM-curated knowledge base. Subdirs (`apps/`, `packages/`, `domains/`, `concepts/`, `dependencies/`, `sources/`, `architecture/`, `adrs/`, `.templates/`) live directly inside; there is no inner vault directory.
```

to:

```
- `<workspace>/wiki/` — the LLM-curated knowledge base. Subdirs (`entities/`, `concepts/`, `dependencies/`, `sources/`, `architecture/`, `adrs/`, `.templates/`) live directly inside; there is no inner vault directory. `entities/` holds one graph-derived page per admitted entity kind (repository, domain, package, app, agent_plugin, dependency, test_suite); there are no separate `apps/`/`packages/`/`domains/` page folders.
```

Then delete the now-stale paragraph (lines ~72-73) that says `apps/`, `packages/`, and `domains/` are "conditional … created only when the detector finds matching containers," replacing it with:

```
Inside `<workspace>/wiki/`, every workspace package/app/domain is rendered as a page under the single `entities/` folder, named `<prefix>_<name>[__hex].md`. Bootstrap seeds `entities/.gitkeep`, which `write_entities` removes once real pages exist and restores if all are swept.
```

Leave the "when changing how layout is detected … update these refs" list intact (those reference docs are exactly the ones this plan updates).

- [ ] **Step 5: Verify the doc sweep**

Run:
```bash
grep -rnE "wiki/(apps|packages|domains)/" \
  plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md \
  plugins/graph-wiki/skills/graph-wiki/references/page-formats.md \
  plugins/graph-wiki/skills/graph-wiki/references/monorepo-principles.md \
  plugins/graph-wiki/CLAUDE.md
```
Expected: no matches that describe *page routing* (a passing mention of legacy layout in historical context is acceptable, but routing instructions must be gone). Spot-read each changed section.

- [ ] **Step 6: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md \
        plugins/graph-wiki/skills/graph-wiki/references/page-formats.md \
        plugins/graph-wiki/skills/graph-wiki/references/monorepo-principles.md \
        plugins/graph-wiki/CLAUDE.md
git commit -m "docs(plugin): schema/page-format/principles + CLAUDE.md to entities/ vocab

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Full-suite verification + manual parity check

**Files:** none (verification only)

- [ ] **Step 1: Run the affected package suites**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/ -q
uv run --package graph-wiki-cli  pytest packages/graph-wiki-cli/ -q
uv run pytest packages/wiki-io/ -q
```
Expected: all green. Pay attention that `test_scan_graph_integration.py`, `test_commands_scan.py`, `test_scan_parity.py`, `test_command_overrides.py`, and `test_plugin_bedrock_shims.py` all pass unchanged.

- [ ] **Step 2: Manual parity check (plugin scan vs `gw scan --no-narrate`)**

On a throwaway fixture repo+workspace (use `fixtures/single-package/` or `fixtures/mono-shaped/` per `packages/wiki-io/tests/helpers.py`), bootstrap a wiki, then run both paths against fresh copies and diff the `entities/` trees:

```bash
# A: plugin shim (Claude branch)
uv run --project "$PWD" python plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py \
  --workspace <wsA> --json
# B: gw CLI
uv run --package graph-wiki-cli gw scan --workspace <wsB> --no-narrate --json

diff -r <wsA>/wiki/entities <wsB>/wiki/entities
```
Expected: identical `entities/` trees (same filenames, same frontmatter, same `## Narrative` placeholders, same `— TODO` file-map rows). Record the result in the task notes.

- [ ] **Step 3: Final commit (if any verification fixups were needed)**

Only if Step 1/2 surfaced fixes. Otherwise this task produces no commit.

---

## Appendix A — Entities Vocabulary (canonical)

Single source of truth for the doc tasks. Authoritative code: `packages/wiki-io/src/wiki_io/entity_writer.py`, `packages/wiki-io/src/wiki_io/init_vault.py`, and the `entity-*.md` templates under `packages/wiki-io/src/wiki_io/assets/page-templates/`.

**Folder:** one `wiki/entities/` folder. Bootstrap seeds `entities/.gitkeep` (self-healing — `write_entities` deletes it once real pages exist, restores it when all pages are swept). Fixed sibling vault dirs (`wiki_io.init_vault.FIXED_VAULT_DIRS`): `entities/`, `concepts/`, `sources/`, `adrs/`, `architecture/`, `.templates/` — plus `dependencies/` for the auto-rendered deps index.

**7 admitted kinds** (`entity_writer.ADMITTED_KINDS`): `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite`.

**Filename:** `short_filename(uri, collision_set, …)` → `<prefix>_<name>[__<6hex>].md` (the `__<6hex>` SHA suffix is added only on collision).

| Kind | Filename prefix |
|---|---|
| `repository` | `repo_` |
| `domain` | `domain_` |
| `package` | `pkg_` |
| `app` | `app_` |
| `agent_plugin` | `agent-plugin_` |
| `dependency` | `dep_` |
| `test_suite` | suite-kind-aware: `unit_tests_`, `int_tests_`, … (fallback `tests_`) |

**Frontmatter split** (`entity_writer.SCANNER_OWNED_KEYS`):
- **Scanner-owned (replaced every scan):** universal `uri`, `kind`, `graph_name`, `last_scan_at`; package `domains`, `depends_on`, `test_suites`, `entry_points`, `language`, `version`; app `app_kind`, `app_signals`; domain `parent_domain`, `sub_domains`, `packages`; test_suite `tested_packages`, `suite_kind`, `file_count`; dependency `ecosystem`, `used_by`, `versions_in_use`; repository `package_count`.
- **Human-preserved (never overwritten):** `status`, `last_reviewed`, `owner`, `notes`, and anything else outside the scanner-owned set.
- **`summary`:** fill-when-empty (scanner writes it only if absent/empty).

**Per-kind templates** each carry a scanner-owned `## Narrative\n_(scanner will populate on next scan)_` section (the only H2 the scanner rewrites). `package` and `app` templates additionally carry a `## File map - <name>` section in the `| Path | Kind | Description |` table format (Description cells default to `— TODO`).

---

## Self-Review notes (author)

- **Spec §1 (run_scan narrate + lazy imports + CLI flag):** Tasks 1, 2, 3. Lazy-import mechanism = module-top `try/except` (user-chosen) instead of function-local imports; the spec's *goal* (narrate=False works without Bedrock; lazy-import test passes) is met by Tasks 1-2.
- **Spec §2 (shim repoint, in-process, Bedrock branch unchanged, retire old writer):** Task 4. "Retire old-layout writer" clarified in Orientation — no Python writer exists to delete; retirement = shim repoint (Task 4) + markdown rewrite (Task 5).
- **Spec §3 (scan markdown):** Task 5 (scanner.md, scan.md), Task 6 (scan-workflow.md, detection-workflow.md).
- **Spec §4 (foundational schema docs + plugin CLAUDE.md):** Task 7.
- **Spec verification/success criteria:** new package tests (Task 1 structural parity + zero-fan-out; Task 2 lazy-import survival); existing Bedrock-shim argv test (Task 4 Step 1/3); manual parity check (Task 8 Step 2).
- **Out-of-scope honored:** no LLM prose generation; no ingest/lint/non-scan refs; no change to `write_entities`/`short_filename`/`ADMITTED_KINDS`/templates.
- **Type consistency:** `narrate` is the parameter name everywhere; `--no-narrate` CLI flag maps to `narrate=not no_narrate`; `run_scan(narrate=False)` in the shim. `ScanResult` field names used in the shim (`entities_created/updated/deleted`, `entity_errors`) match `scan.py:247-258`.
```
