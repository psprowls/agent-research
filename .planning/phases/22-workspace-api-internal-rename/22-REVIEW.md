---
phase: 22-workspace-api-internal-rename
reviewed: 2026-05-20T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
  - agents/graph-wiki-agent/src/graph_wiki_mcp/server.py
  - packages/wiki-io/src/wiki_io/_workspace.py
  - packages/workspace-io/src/workspace_io/config.py
  - packages/workspace-io/src/workspace_io/init.py
  - packages/eval-harness/src/eval_harness/isolation.py
  - packages/eval-harness/src/eval_harness/sweep.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-05-20
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

The Phase 22 rename surface is mechanically clean. Every locked invariant (D-02, D-05, D-06, D-07, D-08, D-09) holds at the boundaries that this phase claims to own:

- `resolve_wiki_and_repo` carries the exact D-06 signature.
- The f-string concatenation (D-02) is gone; `wiki_dir(workspace_path)` is used.
- The CWD-based fallback (D-05) appears exactly once.
- The YAML key hard-cut (D-08) is enforced — only `workspace-directory` is read.
- Phase 23-owned surfaces (`--vault` Typer flag, MCP Pydantic Field `vault_path`) are correctly preserved.
- No back-compat shim or deprecation warning leaks (D-07).

That said, the review surfaced one BLOCKER that escapes the phase's own grep gate (regression in `eval_harness/baseline.py` introduced by the `5f73b00` fix-up commit that reshaped `EvalWorktree`), plus several quality and semantic-consistency defects in the central API that are independently worth fixing while the surface is hot. Notable: `resolve_wiki_and_repo`'s `repo_path` parameter is silently ignored when `workspace_path is None`, and `EvalWorktree.__aenter__` leaks a tmpdir if `shutil.copytree` raises.

## Critical Issues

### CR-01: `EvalWorktree` reshape silently breaks `baseline.py` consumer

**File:** `packages/eval-harness/src/eval_harness/baseline.py:342-346` (consumer of `packages/eval-harness/src/eval_harness/isolation.py`)
**Issue:** The fix-up commit `5f73b00` ("fix(22-01): extend rename to eval_harness consumers") reshaped `EvalWorktree`:

- Before: `wt.path = <tmpdir>/vault` (the *content* directory). The source was copied to `wt.path` itself.
- After: `wt.path = <tmpdir>` (the *workspace* root). The source is copied to `wt.path / "wiki"`.

Two consumers were updated (`sweep.py` flipped 5 sites; tests updated). But `baseline.py:342-346` was missed:

```python
async with EvalWorktree(self._vault_path) as wt:
    assert wt.path is not None
    return run_headless(
        prompt=case["query"],
        worktree_path=wt.path,           # <-- now points to <tmpdir>, not <tmpdir>/wiki
        ...
    )
```

`run_headless`'s `worktree_path` was previously a vault content path; it now receives an empty workspace root (only `wiki/` underneath). Any behavior that walks files from `worktree_path` will see an empty directory instead of the wiki content. This is hidden today because `BaselineRecorder` is gated behind `GRAPH_WIKI_RUN_EVAL` and the Phase 22 pytest gate does not exercise it — the regression is latent. ROADMAP SC#1 ("workspace-wide pytest green") is technically met, but the eval-harness baseline path is silently corrupted for the next person who runs it.

**Note on scope:** The plan explicitly designates eval-harness as Phase 24 territory. However, `5f73b00` was a Phase 22 fix-up that touched isolation.py directly, and the same commit updated `sweep.py` precisely to keep its consumers in sync. Leaving `baseline.py` out of that ripple is a defect of the same fix-up commit, not a Phase 24 deferral — Phase 22 introduced the breaking change, so Phase 22 owns the fix.

**Fix:**
```python
async with EvalWorktree(self._vault_path) as wt:
    assert wt.path is not None
    return run_headless(
        prompt=case["query"],
        worktree_path=wt.path / "wiki",   # match new EvalWorktree layout
        system_prompt=self._system_prompt,
        plugin_dirs=self._plugin_dirs,
        model_override=None,
    )
```

Alternatively, if `run_headless` expects a workspace (not a wiki) path, audit and document that contract — but inspect the consumer to confirm. Either way, the current state is a silent semantic break.

## Warnings

### WR-01: `resolve_wiki_and_repo` silently ignores `repo_path` when `workspace_path is None`

**File:** `packages/wiki-io/src/wiki_io/_workspace.py:36-39`
**Issue:** The signature accepts `repo_path: Path | None = None`, but the parameter is only consulted in the `workspace_path is not None` branch:

```python
if workspace_path is not None:
    return _ws_paths.wiki_dir(workspace_path), repo_path or _find_repo_root(Path.cwd())
cfg = _ws_config.resolve()
return _ws_paths.wiki_dir(cfg.workspace), cfg.repo_root   # repo_path ignored
```

Callers that pass `repo_path=<explicit_root>` but no `workspace_path` get no error, no warning — their override is silently dropped and discovery walks from `Path.cwd()` instead. This is exactly what happens in `run_init` (commands/init.py:78): `resolve_wiki_and_repo(workspace_path, repo_root)` — when `workspace_path is None`, the `repo_root` argument is dead weight, and the second call can resolve a different workspace than the `_ws_init(repo_root, ...)` call just bootstrapped, whenever `Path.cwd() != repo_root` (e.g. when an MCP host runs the server in a different cwd than the repo it manages).

The function docstring documents `repo_path` behavior only for the `workspace_path is not None` branch, reinforcing the gap: a reader can't tell whether passing `repo_path` alone is supported or not. The D-06 signature locks this in, but the *semantics* of the second parameter when the first is omitted are undefined and silently lossy.

**Fix:** Either honor `repo_path` in the fallback branch (preferred — symmetric semantics):
```python
if workspace_path is not None:
    return _ws_paths.wiki_dir(workspace_path), repo_path or _find_repo_root(Path.cwd())
cfg = _ws_config.resolve()
return _ws_paths.wiki_dir(cfg.workspace), repo_path or cfg.repo_root
```
…or raise `TypeError("repo_path requires workspace_path")` when the asymmetric combination is passed. Silently dropping the arg is the worst option.

### WR-02: `EvalWorktree.__aenter__` leaks tmpdir on copy failure

**File:** `packages/eval-harness/src/eval_harness/isolation.py:41-45`
**Issue:** `tempfile.mkdtemp(prefix="eval-wt-")` creates the directory *before* `shutil.copytree` runs. If `copytree` raises (source missing, permission error, disk full, etc.), `__aenter__` never returns, the `async with` block does not bind, and `__aexit__` is therefore not called by the protocol. The empty `eval-wt-XXXXXX/` tmpdir is left on disk permanently. Over many sweep failures (which `asyncio.gather(return_exceptions=True)` swallows downstream) this accumulates `/tmp` pollution.

The phase docstring claims "The tmpdir (and all contents) is removed on __aexit__, even on error." — that claim only covers errors *inside* the `with` body, not enter-time errors.

**Fix:**
```python
async def __aenter__(self) -> EvalWorktree:
    self._tmp = tempfile.mkdtemp(prefix="eval-wt-")
    self.path = Path(self._tmp)
    try:
        shutil.copytree(self._source, self.path / "wiki", dirs_exist_ok=False)
    except Exception:
        shutil.rmtree(self._tmp, ignore_errors=True)
        self._tmp = None
        self.path = None
        raise
    return self
```

### WR-03: `_workspace.py` depends on a private symbol of another module

**File:** `packages/wiki-io/src/wiki_io/_workspace.py:20`
**Issue:** `from workspace_io.config import _find_repo_root` imports a leading-underscore (private-by-convention) symbol across package boundaries. This is fragile by Python convention — any future refactor of `workspace_io.config` is free to rename or delete `_find_repo_root` without warning, and the `wiki-io` package will break with no contract violation.

Either `_find_repo_root` should be promoted to public (`find_repo_root`) in the same package-public API as `resolve_workspace` (the Phase 22 already promoted one helper — same justification applies here, since this one is now a documented dependency per D-05), or `_workspace.py` should inline its own walk-up logic. Since the function is 6 lines and trivial, the latter is also acceptable.

**Fix (option A — promote):** Rename `_find_repo_root` to `find_repo_root` in `workspace_io.config`; export it; update the `_workspace.py` import.
**Fix (option B — inline):** Inline the 6-line walk-up loop in `_workspace.py` to remove the cross-package private-symbol coupling.

### WR-04: `cli.py` `query` subcommand exception handler does not chain MCP errors / non-RuntimeError types

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:390-394`
**Issue:** Only `RuntimeError` is caught for the `query` subcommand:

```python
try:
    result = asyncio.run(run_query(query_text, workspace_path, top_k=top_k))
except RuntimeError as e:
    typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(code=1)
```

All sibling subcommands (`log`, `bootstrap`, `scan`, `ingest_source`, `ingest_work_item`, `lint`) catch broader exception tuples (e.g. `(RuntimeError, FileNotFoundError, SystemExit)`). `run_query` resolves the workspace via `resolve_wiki_and_repo` and walks files — `FileNotFoundError` or `OSError` can absolutely surface from there. With the current handler, those propagate as Python tracebacks to the user's terminal instead of the structured `Error: <msg>` line and exit code 1.

This is not a Phase 22 *regression* (the handler shape is unchanged by the rename), but the rename touched this line range and it is a quality defect worth flagging during the review.

**Fix:** Align with the sibling handlers:
```python
except (RuntimeError, FileNotFoundError, OSError) as e:
    typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(code=1)
```

## Info

### IN-01: Module docstring of `_workspace.py` references "MCP boundary contract, Phase 11 SC#3"

**File:** `packages/wiki-io/src/wiki_io/_workspace.py:5`
**Issue:** Module docstring refers to "MCP boundary contract, Phase 11 SC#3" — Phase 11 is multiple milestones back and the contract is now owned by Phase 22 (D-06). The reference is stale and confusing for future readers.

**Fix:** Replace with a reference to the locked Phase 22 decision: "MCP boundary contract per D-06 (Phase 22 v1.4 milestone)".

### IN-02: `run_init` docstring still uses the legacy term "wiki vault" in summary line

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py:3,9` (module docstring) and several handler descriptions in `cli.py`/`server.py`
**Issue:** Docstrings and CLI help strings still describe the operation in vault terms (e.g. "Bootstrap a wiki vault structure"). Phase 22 is internal-rename only and the plan permits this (external wording is Phase 23 territory), but the inconsistency between the new `workspace_path` parameter name and the older "vault" prose creates ambiguity for readers comparing the code to the milestone language.

This is informational only — no action required for Phase 22 if the team prefers to batch the wording sweep with the Phase 23 external rename. Calling it out so it isn't lost.

**Fix:** Defer to Phase 23 or update opportunistically.

### IN-03: `log.py` docstring still mentions `vault` in error-condition prose

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py:54`
**Issue:** "Raises: RuntimeError: If the vault or log.md cannot be found/written." — the parameter is now `workspace_path`; the prose still says "vault". Minor consistency nit. Same disposition as IN-02.

**Fix:** Optional, defer to Phase 23.

---

_Reviewed: 2026-05-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
