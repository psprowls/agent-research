# Production Pyright Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-source pyright gate and clean all production-source pyright errors while excluding tests, fixtures, worktrees, virtualenvs, and generated workspace artifacts from CLI and VS Code checking.

**Architecture:** Establish the shared pyright/Pylance configuration first, then split cleanup into independent package domains that can be assigned to concurrent subagents. Each domain owns separate files and verification commands; a final integration task reruns `pyright`, scoped Ruff, and all touched package tests.

**Tech Stack:** Python 3.11, uv workspace, pyright 1.1.410, VS Code/Pylance settings, pytest, ruff, Typer CLI, dataclasses, Protocol types.

---

## Parallel Execution Shape

Run Task 1 first. After Task 1 is committed, Tasks 2, 3, 4, and 5 can run concurrently because they edit separate package surfaces.

Recommended concurrent assignments:

- Subagent A: Task 2, CLI namespace protocols
- Subagent B: Task 3, graph-io graph record/type cleanup
- Subagent C: Task 4, graph-wiki-core guarded Bedrock import narrowing
- Subagent D: Task 5, small package remainder

After those return, run Task 6 as the coordinator integration pass. Do not run Task 6 until all concurrent package tasks have been reviewed and applied.

## File Structure

- Create `pyrightconfig.json`: command-line pyright production-source target.
- Create `.vscode/settings.json`: editor/Pylance production-source exclusions and interpreter hint.
- Create `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/_args.py`: shared `Protocol` contracts for Typer-created command namespaces passed to graph CLI modules.
- Modify `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/*.py`: replace `run(args: object)` with precise protocol types and narrow dynamic router helpers.
- Create `packages/graph-io/src/graph_io/records.py`: helper to convert mutable graph emitter lists into immutable `GraphRecords`.
- Modify `packages/graph-io/src/graph_io/*.py`: use `records.as_graph_records(...)`, fix real optional values, and preserve graph output ordering.
- Modify `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`: narrow guarded Bedrock imports after runtime checks.
- Modify `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py`: apply the same guarded import narrowing pattern.
- Modify `packages/eval-harness/src/eval_harness/*.py`: fix optional score/workspace and proxy type mismatches.
- Modify `packages/wiki-io/src/wiki_io/*.py`: fix frontmatter `Path` stub mismatches and unbound `log_path`.
- Modify `packages/source-parser/src/source_parser/grammars.py`, `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, and `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py` for the singleton diagnostics.

## Task 1: Production Pyright And VS Code Configuration

**Files:**
- Create: `pyrightconfig.json`
- Create: `.vscode/settings.json`
- Preserve: `.vscode/launch.json`
- Read: `docs/superpowers/specs/2026-06-06-production-pyright-cleanup-design.md`

- [ ] **Step 1: Add repo-root pyright config**

Create `pyrightconfig.json` with this content:

```json
{
  "include": [
    "packages/*/src",
    "plugins/graph-wiki/skills/graph-wiki/scripts"
  ],
  "exclude": [
    "**/tests/**",
    "**/fixtures/**",
    ".venv/**",
    ".worktrees/**",
    ".git/**",
    ".hypothesis/**",
    ".claude/**",
    ".gsd/**",
    ".agents/**",
    "graph-wiki/**",
    "**/__pycache__/**",
    "**/dist/**",
    "**/build/**",
    "**/node_modules/**"
  ],
  "pythonVersion": "3.11",
  "venvPath": ".",
  "venv": ".venv",
  "typeCheckingMode": "standard"
}
```

- [ ] **Step 2: Add VS Code analysis settings**

Create `.vscode/settings.json` with this content:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.analysis.typeCheckingMode": "standard",
  "python.analysis.include": [
    "packages/*/src",
    "plugins/graph-wiki/skills/graph-wiki/scripts"
  ],
  "python.analysis.exclude": [
    "**/tests/**",
    "**/fixtures/**",
    ".venv/**",
    ".worktrees/**",
    ".git/**",
    ".hypothesis/**",
    ".claude/**",
    ".gsd/**",
    ".agents/**",
    "graph-wiki/**",
    "**/__pycache__/**",
    "**/dist/**",
    "**/build/**",
    "**/node_modules/**"
  ]
}
```

- [ ] **Step 3: Run pyright through the new config**

Run:

```bash
pyright --outputjson > /private/tmp/agent-research-pyright-configured.json
jq '.summary' /private/tmp/agent-research-pyright-configured.json
```

Expected: pyright exits non-zero while the source cleanup is still pending. The summary should be close to the approved baseline:

```json
{
  "filesAnalyzed": 190,
  "errorCount": 269,
  "warningCount": 0,
  "informationCount": 0
}
```

Small count drift is acceptable only if it is explained by pyright config path semantics. Tests and fixtures must not appear in diagnostics.

- [ ] **Step 4: Verify tests and fixtures are excluded**

Run:

```bash
jq -r '.generalDiagnostics[].file' /private/tmp/agent-research-pyright-configured.json | rg '/tests/|/fixtures/' || true
```

Expected: no output.

- [ ] **Step 5: Commit configuration**

Run:

```bash
git add pyrightconfig.json .vscode/settings.json
git commit -m "chore: add production pyright config"
```

## Task 2: Graph Wiki CLI Namespace Protocols

**Files:**
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/_args.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/ops_dump.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/ops_status.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/ops_sync_wiki.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/ops_update.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_*.py`
- Test: `packages/graph-wiki-cli/tests`

- [ ] **Step 1: Create shared argparse namespace protocols**

Create `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/_args.py`:

```python
"""Static contracts for Typer-created graph CLI command namespaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class WorkspaceArgs(Protocol):
    workspace: Path


class FormatArgs(WorkspaceArgs, Protocol):
    fmt: str


class RepoWorkspaceArgs(WorkspaceArgs, Protocol):
    repo: Path


class UpdateArgs(RepoWorkspaceArgs, Protocol):
    full: bool


class NameArgs(FormatArgs, Protocol):
    name: str


class DepthNameArgs(NameArgs, Protocol):
    depth: int


class OptionalNameArgs(FormatArgs, Protocol):
    name: str | None


class FindArgs(FormatArgs, Protocol):
    name: str | None
    kind: str | None
    in_package: str | None


class DescribeArgs(FormatArgs, Protocol):
    selector: str | None
    kind: str | None
    ecosystem: str | None


class MutableDescribeArgs(DescribeArgs, Protocol):
    name: str
    uri: str
    path: str


class DependencyDescribeArgs(NameArgs, Protocol):
    ecosystem: str | None


class BuiltinDescribeArgs(FormatArgs, Protocol):
    uri: str


class PathDescribeArgs(FormatArgs, Protocol):
    path: str


class ListArgs(FormatArgs, Protocol):
    kind: str | None


class ListScriptsArgs(FormatArgs, Protocol):
    kind: str | None
    owner: str | None


class WhatTestsArgs(FormatArgs, Protocol):
    name: str
    kind: str | None


class DomainArgs(FormatArgs, Protocol):
    name: str


class AnyRunModule(Protocol):
    def run(self, args: Any) -> int:
        pass
```

- [ ] **Step 2: Update simple operation modules**

Apply these import and signature changes while leaving each existing function body unchanged.

```python
# ops_dump.py, ops_sync_wiki.py
from graph_wiki_cli.graph_cli._args import WorkspaceArgs


def run(args: WorkspaceArgs) -> int:
```

```python
# ops_status.py
from typing import Protocol

from graph_wiki_cli.graph_cli._args import FormatArgs, RepoWorkspaceArgs


class StatusArgs(RepoWorkspaceArgs, FormatArgs, Protocol):
    pass


def run(args: StatusArgs) -> int:
```

```python
# ops_update.py
from graph_wiki_cli.graph_cli._args import UpdateArgs


def run(args: UpdateArgs) -> int:
```

- [ ] **Step 3: Update repeated query modules**

Use these mappings:

```python
from graph_wiki_cli.graph_cli._args import DepthNameArgs

def run(args: DepthNameArgs) -> int:
```

Apply to:

- `q_callers.py`
- `q_callees.py`

```python
from graph_wiki_cli.graph_cli._args import NameArgs

def run(args: NameArgs) -> int:
```

Apply to query modules whose only selector is `args.name` plus `args.workspace` and `args.fmt`, including package/app/domain/suite/agent-plugin/list-by-name describe helpers where the file confirms those attributes.

```python
from graph_wiki_cli.graph_cli._args import FindArgs

def run(args: FindArgs) -> int:
```

Apply to `q_find.py`.

- [ ] **Step 4: Update describe router without broad ignores**

In `q_describe.py`, import the protocol types:

```python
from typing import cast

from graph_wiki_cli.graph_cli._args import AnyRunModule, MutableDescribeArgs
```

Change `_DISPATCH` annotation:

```python
_DISPATCH: dict[str, tuple[AnyRunModule, str | None]]
```

Change signatures:

```python
def _resolve_kind(args: MutableDescribeArgs) -> str | int:


def run(args: MutableDescribeArgs) -> int:
```

If pyright cannot prove the dynamically selected module accepts the mutated namespace, use one local cast at the dispatch call:

```python
module = cast(AnyRunModule, module)
return module.run(args)
```

Do not add `# type: ignore` to every attribute access.

- [ ] **Step 5: Run CLI pyright slice**

Run:

```bash
pyright packages/graph-wiki-cli/src --pythonpath .venv/bin/python
```

Expected: no `reportAttributeAccessIssue` diagnostics for `graph_wiki_cli/graph_cli`.

- [ ] **Step 6: Run CLI tests**

Run:

```bash
uv run --package graph-wiki-cli pytest -m "not integration"
```

Expected: pass. Existing skips and xfails are acceptable.

- [ ] **Step 7: Commit CLI cleanup**

Run:

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli
git commit -m "fix: type graph CLI command namespaces"
```

## Task 3: Graph IO Record Boundary And Source Typing

**Files:**
- Create: `packages/graph-io/src/graph_io/records.py`
- Modify: `packages/graph-io/src/graph_io/agent_plugins.py`
- Modify: `packages/graph-io/src/graph_io/builtins.py`
- Modify: `packages/graph-io/src/graph_io/cluster.py`
- Modify: `packages/graph-io/src/graph_io/derived_edges.py`
- Modify: `packages/graph-io/src/graph_io/domains.py`
- Modify: `packages/graph-io/src/graph_io/entry_points.py`
- Modify: `packages/graph-io/src/graph_io/packages.py`
- Modify: `packages/graph-io/src/graph_io/render.py`
- Modify: `packages/graph-io/src/graph_io/structural_nodes.py`
- Modify: `packages/graph-io/src/graph_io/sync_wiki.py`
- Modify: `packages/graph-io/src/graph_io/test_suites.py`
- Modify: `packages/graph-io/src/graph_io/upsert.py`
- Test: `packages/graph-io/tests`

- [ ] **Step 1: Add GraphRecords conversion helper**

Create `packages/graph-io/src/graph_io/records.py`:

```python
"""Helpers for building immutable parser graph records from mutable emitters."""

from __future__ import annotations

from collections.abc import Iterable

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords


def as_graph_records(
    nodes: Iterable[GraphNode] = (),
    edges: Iterable[GraphEdge] = (),
) -> GraphRecords:
    """Return GraphRecords with the tuple boundary expected by source-parser."""
    return GraphRecords(nodes=tuple(nodes), edges=tuple(edges))
```

- [ ] **Step 2: Replace direct list-based `GraphRecords(...)` calls**

In each graph-io emitter, import the helper:

```python
from graph_io.records import as_graph_records
```

Replace calls like:

```python
upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
```

with:

```python
upsert.upsert_records(conn, as_graph_records(nodes=nodes, edges=edges))
```

Replace empty-list calls like:

```python
GraphRecords(nodes=[], edges=edges_out)
```

with:

```python
as_graph_records(edges=edges_out)
```

Apply this to all direct `GraphRecords(` construction in `packages/graph-io/src/graph_io`.

- [ ] **Step 3: Remove stale direct imports where possible**

After Step 2, remove `GraphRecords` from imports where the file no longer constructs it directly:

```python
from source_parser.projections.graph import GraphEdge, GraphNode
```

Keep `GraphRecords` imported only in files that still need the type directly.

- [ ] **Step 4: Fix `upsert._insert_node` return narrowing**

In `packages/graph-io/src/graph_io/upsert.py`, replace:

```python
return cursor.lastrowid
```

with:

```python
if cursor.lastrowid is None:
    raise RuntimeError("SQLite did not return a row id for inserted graph node")
return cursor.lastrowid
```

- [ ] **Step 5: Fix graph source optional key diagnostics**

For each diagnostic where a `GraphNode.path` or `GraphNode.name` argument is `str | None`, add a local guard before construction:

```python
if path_value is None:
    continue
```

or, when the graph node must exist and the current runtime behavior would already be invalid:

```python
if path_value is None:
    raise ValueError("graph node path is required for this projection")
```

Use `continue` for skipped optional discovery rows and `raise ValueError` only where the function contract requires the value.

- [ ] **Step 6: Fix dict/object diagnostics in render and cluster helpers**

In `packages/graph-io/src/graph_io/render.py`, avoid `dict(row)` for sqlite rows or dataclasses when pyright cannot prove the iterable type. Use an explicit comprehension:

```python
return {str(key): value for key, value in row.items()}
```

If the value is a dataclass, use `dataclasses.asdict(value)` and annotate the result:

```python
out: dict[str, Any] = asdict(value)
return out
```

In `cluster.py`, narrow objects before arithmetic/indexing:

```python
if not isinstance(value, tuple) or len(value) < 2:
    continue
```

Use the concrete local variable names from the file; do not change clustering behavior.

- [ ] **Step 7: Run graph-io pyright slice**

Run:

```bash
pyright packages/graph-io/src --pythonpath .venv/bin/python
```

Expected: zero graph-io source errors.

- [ ] **Step 8: Run graph-io tests**

Run:

```bash
uv run --package graph-io pytest
```

Expected: pass.

- [ ] **Step 9: Commit graph-io cleanup**

Run:

```bash
git add packages/graph-io/src/graph_io
git commit -m "fix: clean graph-io production pyright errors"
```

## Task 4: Graph Wiki Core Guarded Bedrock Import Narrowing

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_scan.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py`
- Test: `packages/graph-wiki-core/tests/commands/test_propagate_drift.py`

- [ ] **Step 1: Add typed fallback imports for scan.py**

In `scan.py`, change the typing imports:

```python
from typing import Any, TYPE_CHECKING, cast
```

Add after the guarded import block:

```python
if TYPE_CHECKING:
    from model_adapter.loader import load_role_config as LoadRoleConfigFn
    from model_adapter.loader import make_llm as MakeLlmFn
    from subagent_runtime.pool import SubagentPool as SubagentPoolType
    from subagent_runtime.pool import TaskResult as TaskResultType
```

- [ ] **Step 2: Add scan.py narrowing helper**

Add this helper below the guarded import block:

```python
def _bedrock_stack() -> tuple["LoadRoleConfigFn", "MakeLlmFn", type["SubagentPoolType"], type["TaskResultType"]] | None:
    if load_role_config is None or make_llm is None or SubagentPool is None or TaskResult is None:
        return None
    return (
        cast("LoadRoleConfigFn", load_role_config),
        cast("MakeLlmFn", make_llm),
        cast(type["SubagentPoolType"], SubagentPool),
        cast(type["TaskResultType"], TaskResult),
    )
```

- [ ] **Step 3: Use scan.py helper in drift, narrative, and file-description fan-out blocks**

Replace checks like:

```python
if make_llm is None or SubagentPool is None:
    return
```

with:

```python
stack = _bedrock_stack()
if stack is None:
    return
load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
```

Then replace calls in that block:

```python
drift_cfg = load_role_config("drift_judge")
drift_llm = make_llm("drift_judge", model_override=model_override)
drift_pool = SubagentPool(trace_dir=graph_dir(wiki.parent) / "traces")
return TaskResult(value=parse_drift_verdict(resp.content), response=resp)
```

with:

```python
drift_cfg = load_role_config_fn("drift_judge")
drift_llm = make_llm_fn("drift_judge", model_override=model_override)
drift_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")
return task_result_type(value=parse_drift_verdict(resp.content), response=resp)
```

Use the same local aliases for narrator and code-reader fan-out. Do not instantiate Bedrock clients outside `make_llm_fn`.

- [ ] **Step 4: Apply the same pattern to propagate_drift.py**

In `propagate_drift.py`, import `TYPE_CHECKING` and `cast`, add typed imports, and add:

```python
def _bedrock_stack() -> tuple["LoadRoleConfigFn", "MakeLlmFn", type["SubagentPoolType"], type["TaskResultType"]] | None:
    if load_role_config is None or make_llm is None or SubagentPool is None or TaskResult is None:
        return None
    return (
        cast("LoadRoleConfigFn", load_role_config),
        cast("MakeLlmFn", make_llm),
        cast(type["SubagentPoolType"], SubagentPool),
        cast(type["TaskResultType"], TaskResult),
    )
```

Use the returned aliases in the judged path.

- [ ] **Step 5: Run core pyright slice**

Run:

```bash
pyright packages/graph-wiki-core/src --pythonpath .venv/bin/python
```

Expected: zero graph-wiki-core source errors.

- [ ] **Step 6: Run focused core tests**

Run:

```bash
uv run --package graph-wiki-core pytest \
  tests/unit/test_commands_scan.py \
  tests/unit/test_commit_gated_narrative.py \
  tests/unit/test_commit_gated_file_map.py \
  tests/commands/test_propagate_drift.py
```

Expected: pass with existing skips only.

- [ ] **Step 7: Commit core cleanup**

Run:

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py
git commit -m "fix: narrow guarded Bedrock imports for pyright"
```

## Task 5: Small Package Remainder

**Files:**
- Modify: `packages/eval-harness/src/eval_harness/divergence/metric.py`
- Modify: `packages/eval-harness/src/eval_harness/judge.py`
- Modify: `packages/eval-harness/src/eval_harness/sweep.py`
- Modify: `packages/wiki-io/src/wiki_io/append_log.py`
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py`
- Modify: `packages/wiki-io/src/wiki_io/proposals.py`
- Modify: `packages/source-parser/src/source_parser/grammars.py`
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`

- [ ] **Step 1: Regenerate small-package diagnostic list**

Run:

```bash
pyright --outputjson > /private/tmp/agent-research-pyright-small.json
jq -r '.generalDiagnostics[] | (.file | sub(".*/pyright-fixes/"; "")) + ":" + ((.range.start.line + 1)|tostring) + " [" + (.rule // "none") + "] " + .message' /private/tmp/agent-research-pyright-small.json \
  | rg 'eval-harness|wiki-io|source-parser|graph-wiki-mcp|plugins/graph-wiki'
```

Expected: only diagnostics for the files in this task.

- [ ] **Step 2: Fix optional score appends in eval harness**

In `metric.py` and `judge.py`, replace score appends where the score can be `None`:

```python
if metric.score is not None:
    scores.append(metric.score)
```

If the surrounding code needs a reason even when the score is missing, keep the existing reason append unchanged. Do not coerce `None` to `0.0`.

- [ ] **Step 3: Fix eval harness optional workspace values**

In `sweep.py`, add explicit guards before passing an optional workspace path to `graph_dir(...)` or `check_structural(...)`:

```python
if wt.path is None:
    raise RuntimeError("eval worktree did not provide a workspace path")
```

Use the actual local variable where pyright reports `Path | None`. Preserve current successful runtime behavior.

- [ ] **Step 4: Unify eval harness agent output proxy type**

Where `sweep.py` defines or imports an `AgentOutputProxy` that conflicts with `eval_harness.divergence.check.AgentOutputProxy`, use the divergence check type directly:

```python
from eval_harness.divergence.check import AgentOutputProxy
```

Remove the local duplicate class or alias if it exists. The goal is that `DivergenceMetric.run_programmatic(...)` receives `list[tuple[str, AgentOutputProxy]]` from the same module that defines the expected type.

- [ ] **Step 5: Fix wiki-io unbound log_path**

In `append_log.py`, after the `except FileNotFoundError` block, add an unreachable raise so pyright knows `_error(...)` does not return:

```python
    except FileNotFoundError as e:
        _error(str(e), as_json, raise_exception=raise_exception)
        raise AssertionError("unreachable after _error")
```

Apply the same pattern after the `except OSError` block if pyright reports variables remain possibly unbound in that path.

- [ ] **Step 6: Fix frontmatter Path stub mismatches**

In `entity_writer.py` and `proposals.py`, wrap `frontmatter.load(Path)` with a local helper:

```python
def _load_frontmatter(path: Path) -> frontmatter.Post:
    return frontmatter.load(str(path))
```

Then replace production-source calls in that file:

```python
post = frontmatter.load(page_path)
```

with:

```python
post = _load_frontmatter(page_path)
```

Do not change test files in this production-source pass.

- [ ] **Step 7: Fix singleton source-parser, MCP, and plugin diagnostics**

In `packages/source-parser/src/source_parser/grammars.py`, import the package's supported-language type and cast only after the existing membership check:

```python
from typing import cast

from tree_sitter_language_pack import SupportedLanguage
```

Then change:

```python
return _pack_get_language(name)
```

to:

```python
return _pack_get_language(cast(SupportedLanguage, name))
```

In `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, guard the optional repo returned by `resolve_wiki_and_repo(...)` before calling `run_propagate_drift(...)`:

```python
    wiki, repo = resolve_wiki_and_repo(workspace)
    if repo is None:
        raise RuntimeError("repo path is required to propagate drift")
```

In `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`, remove the stale ignore on the fallback helper after confirming the signature matches `_config.backend_for`:

```python
        def backend_for(cmd: str, repo: object = None) -> str:
            return "claude"
```

Keep script output and command behavior unchanged.

- [ ] **Step 8: Run package pyright slices**

Run:

```bash
pyright packages/eval-harness/src packages/wiki-io/src packages/source-parser/src packages/graph-wiki-mcp/src plugins/graph-wiki/skills/graph-wiki/scripts --pythonpath .venv/bin/python
```

Expected: zero errors in these paths.

- [ ] **Step 9: Run package tests**

Run tests for packages changed in this task:

```bash
uv run --package eval-harness pytest
uv run --package wiki-io pytest
uv run --package source-parser pytest
uv run --package graph-wiki-mcp pytest
```

Expected: pass with existing skips only.

- [ ] **Step 10: Commit small-package cleanup**

Run:

```bash
git add packages/eval-harness/src packages/wiki-io/src packages/source-parser/src packages/graph-wiki-mcp/src plugins/graph-wiki/skills/graph-wiki/scripts
git commit -m "fix: clean remaining production pyright errors"
```

## Task 6: Integration Verification

**Files:**
- Review: all files changed by Tasks 1-5
- No planned production edits unless integration reveals a real conflict

- [ ] **Step 1: Confirm branch status and commit stack**

Run:

```bash
git status --short
git log --oneline -6
```

Expected: clean status before final verification. The log should include the spec commit plus Task 1-5 commits.

- [ ] **Step 2: Run final pyright gate**

Run:

```bash
pyright
```

Expected:

```text
0 errors, 0 warnings, 0 informations
```

- [ ] **Step 3: Confirm tests and fixtures are still excluded**

Run:

```bash
pyright --outputjson > /private/tmp/agent-research-pyright-final.json
jq -r '.generalDiagnostics[].file' /private/tmp/agent-research-pyright-final.json | rg '/tests/|/fixtures/' || true
```

Expected: no output.

- [ ] **Step 4: Run scoped Ruff over changed production paths**

Run:

```bash
uv run ruff check pyrightconfig.json .vscode/settings.json packages/graph-wiki-cli/src packages/graph-io/src packages/graph-wiki-core/src packages/eval-harness/src packages/wiki-io/src packages/source-parser/src packages/graph-wiki-mcp/src plugins/graph-wiki/skills/graph-wiki/scripts
```

Expected: pass.

- [ ] **Step 5: Run touched package tests**

Run:

```bash
uv run --package graph-wiki-cli pytest -m "not integration"
uv run --package graph-io pytest
uv run --package graph-wiki-core pytest
uv run --package eval-harness pytest
uv run --package wiki-io pytest
uv run --package source-parser pytest
uv run --package graph-wiki-mcp pytest
```

Expected: pass with existing skips and xfails only.

- [ ] **Step 6: Inspect final diff for accidental scope expansion**

Run:

```bash
git diff --stat develop..HEAD
git diff --name-only develop..HEAD
```

Expected: changed files are limited to pyright/editor config, the plan/spec docs, and the production-source files listed in this plan. No test or fixture files should be modified unless a package task found and justified a real production behavior ambiguity.

- [ ] **Step 7: Commit final integration adjustments if needed**

If Task 6 required a small integration-only adjustment, commit it:

Run `git status --short`, inspect the integration-only changed files, and stage all integration adjustments. Then commit:

```bash
git status --short
git add -A
git commit -m "chore: verify production pyright cleanup"
```

If no files changed during Task 6, do not create an empty commit.
