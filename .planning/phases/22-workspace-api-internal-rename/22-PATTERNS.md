# Phase 22: workspace-api-internal-rename - Pattern Map

**Mapped:** 2026-05-20
**Files analyzed:** 9 source files + ~15 test files
**Analogs found:** 9 / 9 (every rename target has an in-tree analog — either a WIP-prototype file on `main` or a sibling that already matches the target shape)

## Phase Shape

This is a **mechanical rename** phase. There is no novel design — every "new" pattern has a direct in-tree precedent. Per D-01, 5 WIP files on `main` (uncommitted, vs `00f3c06`) already prototype WSAPI-01, WSAPI-02 (init only), WSAPI-05, WSAPI-06 and are adopted as the implementation foundation. The planner's job is to:

1. Adopt the 5 WIP diffs as-is **except** for the `_workspace.py` f-string hack (D-02 fix).
2. Replicate the same kwarg-rename pattern across the 5 unchanged sibling commands (scan, lint, ingest, query, log) and the corresponding cli.py + MCP server Python call sites.
3. Sweep ~70 `patch("...resolve_wiki_and_repo", ...)` mock points + `vault_path=` kwarg call sites across ~15 test files.
4. Rename 2 YAML literal strings in `packages/workspace-io/tests/test_config.py` (`graph-wiki-directory` → `workspace-directory`).

## File Classification

### Source files (rename targets)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `packages/wiki-io/src/wiki_io/_workspace.py` | utility (path resolver) | request-response | **WIP diff on `main`** (already renamed; needs D-02 fix) | exact + 1-line fix |
| `packages/workspace-io/src/workspace_io/config.py` | config | request-response | **WIP diff on `main`** (constant + helper promoted) | exact |
| `packages/workspace-io/src/workspace_io/init.py` | init/bootstrap | CRUD (file I/O) | **WIP diff on `main`** (routes through `resolve_workspace`) | exact (one stray comment to delete) |
| `packages/workspace-io/src/workspace_io/paths.py` | utility | pure function | (unchanged — already correct) | n/a — consume only |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` | command (agent entry) | request-response | **WIP diff on `main`** (signature already renamed, both kwargs added) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` | command (agent entry) | request-response | `commands/init.py` (WIP) | role+flow match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` | command (agent entry) | request-response | `commands/init.py` (WIP) | role+flow match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` | command (agent entry) | request-response | `commands/init.py` (WIP) | role+flow match — 2 functions: `run_ingest_source` + `run_ingest_work_item` |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` | command (agent entry) | request-response | `commands/init.py` (WIP) | role+flow match — also has private helpers `_discover_pages(vault_path)`, `_cosine_search_sqlite(vault_path, …)`, `_resolve_repo_root(vault_path)` that are docstring-only renames (D-discretion) |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py` | command (agent entry) | request-response | `commands/init.py` (WIP) | role+flow match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` | CLI entry (Typer) | request-response | **WIP diff on `main`** (bootstrap subcommand already renamed) | partial — bootstrap done; 5 other subcommands (`query`, `log`, `scan`, `ingest`/2, `lint`) follow same pattern |
| `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` | service (MCP server) | request-response | bootstrap subcommand in WIP `cli.py` (parallel "local var → kwarg" rename) | partial — 6 internal `vault_path=` kwarg call sites only; Pydantic field name STAYS (Phase 23) |

### Test files (mock-point + kwarg sweep)

| File | Patch-mock count | `vault_path=` kwarg call sites | Notes |
|------|------------------|-------------------------------|-------|
| `agents/graph-wiki-agent/tests/unit/test_commands_ingest.py` | 8 | 5+ (`run_ingest_work_item(... vault_path=wiki)`) | largest sweep target |
| `agents/graph-wiki-agent/tests/test_command_overrides.py` | 8 | 6+ (`run_query`, `run_scan`, `run_lint`, `run_ingest_source` all with `vault_path=vault`) | |
| `agents/graph-wiki-agent/tests/unit/test_commands_scan.py` | 7 | none observed in grep slice — kwarg use via `run_scan(...)` likely | |
| `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py` | 3 | n/a (comment-only reference) | |
| `agents/graph-wiki-agent/tests/unit/test_commands_lint.py` | 2 | 0 | |
| `agents/graph-wiki-agent/tests/unit/test_commands_log.py` | 2 | 1 (`run_log(... vault_path=None)`) | |
| `agents/graph-wiki-agent/tests/unit/test_query_result.py` | 2 | 4 (`run_query("...", vault_path=vault, top_k=3)`) | |
| `agents/graph-wiki-agent/tests/test_ingest_trace_unit.py` | 2 | 0 (uses positional?) | |
| `agents/graph-wiki-agent/tests/unit/test_query_code_fallback.py` | 1 | 4 (`run_query(... vault_path=vault, ...)`) | |
| `agents/graph-wiki-agent/tests/unit/test_commands_bootstrap.py` | 1 | 1 (`run_init(... vault_path=None)`) | already partially mooted by WIP — verify |
| `agents/graph-wiki-agent/tests/test_query_trace_unit.py` | 1 | 3 (`run_query("what?", vault_path=vault, ...)`) | |
| `agents/graph-wiki-agent/tests/unit/test_query_summary_schema_version.py` | 1 | 1 (`run_query(... vault_path=tmp_path, ...)`) — also has a `lambda vault_path=None: ...` mock-side-effect signature | mock signature lambda also needs renaming |
| `agents/graph-wiki-agent/tests/commands/test_scan_parity.py` | 2 | 0 | |
| `packages/eval-harness/tests/test_sweep.py` | 1 | 3 (`run_query(... vault_path=wt.path)`, `run_sweep(..., fixture_vault_path, ...)`) | **CROSS-PACKAGE RIPPLE** — eval-harness test calls agent `run_query` by kwarg name; renames here even though Phase 24 owns eval-harness internals (D-04 is workspace-wide pytest gate, so this test MUST pass) |
| `packages/wiki-io/tests/test_ports_importable.py` | 10 (only the `def test_resolve_wiki_and_repo_*` function names — these are TEST NAMES, not mock points) | 0 | **NOT IN SCOPE** — these are test function identifiers containing the substring; renaming them is cosmetic. Leave alone unless executor's discretion. |
| `packages/workspace-io/tests/test_config.py` | 0 | 0 — but **3 YAML literal strings** `"graph-wiki-directory: ..."` at lines 49, 58, 70 | Hard-cut: D-08 says these break silently if not updated; tests would still pass against the default workspace, but no longer exercise the override. Rename literals to `workspace-directory:`. |
| `packages/workspace-io/tests/test_local_config.py` | 0 | 0 — 13 YAML literal strings `"graph-wiki-directory: ..."` | **OUT OF SCOPE.** This test exercises `_local_config.read()` (a generic YAML parser); the string is opaque data. Leave alone — these tests don't depend on the constant. |

**Approximate total:** ~50 `patch(... resolve_wiki_and_repo ...)` mock-point lines + ~30 `vault_path=` kwarg call sites across ~14 files = matches the ~70 estimate in CONTEXT.md.

### Out-of-scope siblings (must NOT change)

| File | Why preserved |
|------|---------------|
| `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` Pydantic `Field` names (6× `vault_path: str = Field(...)`) | Phase 23 (external rename). Only internal kwarg-name on `run_*(vault_path=...)` flips. |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` Typer flag literal `"--vault"` | Phase 23. Only the local variable name + kwarg-name flips. |
| `packages/eval-harness/src/eval_harness/{baseline,sweep,structural,isolation,divergence/*}.py` `vault_path` parameters | Phase 24. |
| `packages/wiki-io/src/wiki_io/{ingest_source,scan_monorepo,lint_wiki,query helpers,…}.py` `vault_path` parameters | These are **internal helpers**, not part of the `resolve_wiki_and_repo`/`run_*` boundary. Out of scope. CONTEXT.md `<domain>` scopes the rename to (a) `resolve_wiki_and_repo` signature, (b) `run_*` signatures, (c) callers that pass `vault_path=` kwarg. Pure-internal `def _foo(vault_path: Path)` helpers stay. |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` private helpers (`_discover_pages`, `_cosine_search_sqlite`, `_resolve_repo_root`) | Same reason — internal helpers, not boundary. (Docstring may mention `vault_path` — executor discretion per D-discretion-3.) |
| `packages/workspace-io/tests/test_local_config.py` | Tests opaque YAML reader; the key string is data, not behavior. |
| `*/conftest.py` `vault_path` and `fixture_vault_path` **pytest fixtures** | Fixture names, not runtime kwargs. Out of scope. |

## Pattern Assignments

### `packages/wiki-io/src/wiki_io/_workspace.py` — central rename (WSAPI-01)

**Analog:** WIP diff against `00f3c06` (the file already has 80% of the rename applied).

**Current (WIP, with the D-02 hack still present), lines 23–39:**
```python
def resolve_wiki_and_repo(
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Return (wiki_path, repo_root).

    Priority:
    1. ``vault_path`` argument if provided — short-circuit. ``repo_root`` is
       discovered by walking up from ``vault_path`` looking for ``.git``.
    2. ``GRAPH_WIKI_WORKSPACE`` env var (via ``workspace_io.config.resolve``).
    3. ``.graph-wiki.yaml`` walk-up from cwd (via ``workspace_io.config.resolve``).
    4. Raises ``RuntimeError`` — names ``graph-wiki-agent init <path>`` as fix.
    """
    if workspace_path is not None:
        return Path(f"{workspace_path}" + "/wiki").resolve(), repo_path if repo_path else _find_repo_root(workspace_path)
    cfg = _ws_config.resolve()
    return _ws_paths.wiki_dir(cfg.workspace), cfg.repo_root
```

**Two deviations from CONTEXT.md decisions that the plan MUST fix:**

1. **D-02 fix** (the f-string hack). Replace `Path(f"{workspace_path}" + "/wiki").resolve()` with `_ws_paths.wiki_dir(workspace_path)` (already imported on line 19).

2. **D-05 fix** (CWD-based repo discovery). Current WIP walks up from `workspace_path` to find the repo. CONTEXT.md D-05 says: walk up from `Path.cwd()` instead. Change `_find_repo_root(workspace_path)` → `_find_repo_root(Path.cwd())`.

3. **Docstring stale terms** — three remaining occurrences of `vault_path` in the docstring (lines 30, 31, 33).

**Target (per D-02 + D-05 + D-06):**
```python
def resolve_wiki_and_repo(
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Return (wiki_path, repo_root).

    Priority:
    1. ``workspace_path`` argument if provided — short-circuit. When ``repo_path``
       is not supplied, walk up from ``Path.cwd()`` to find the repo root.
    2. ``GRAPH_WIKI_WORKSPACE`` env var (via ``workspace_io.config.resolve``).
    3. ``.graph-wiki.yaml`` walk-up from cwd (via ``workspace_io.config.resolve``).
    4. Raises ``RuntimeError`` — names ``graph-wiki-agent bootstrap <path>`` as fix.
    """
    if workspace_path is not None:
        return _ws_paths.wiki_dir(workspace_path), repo_path or _find_repo_root(Path.cwd())
    cfg = _ws_config.resolve()
    return _ws_paths.wiki_dir(cfg.workspace), cfg.repo_root
```

Note: `Path` is already imported (line 16); `_ws_paths` already imported (line 19); `_find_repo_root` already imported (line 20). No new imports.

---

### `packages/workspace-io/src/workspace_io/config.py` — constant + promotion (WSAPI-05)

**Analog:** WIP diff against `00f3c06` (already complete).

The WIP already:
- Renamed constant `LATTICE_DIRECTORY_KEY` → `WORKSPACE_DIRECTORY_KEY` (line 21).
- Renamed YAML key value `"graph-wiki-directory"` → `"workspace-directory"` (line 21).
- Promoted `_resolve_workspace` → `resolve_workspace` (line 39); updated internal call site at line 70.
- Updated stale `init` → `bootstrap` term in error message (line 76).

**Per-CONTEXT.md verification:**
- No other module imports `LATTICE_DIRECTORY_KEY` or `_resolve_workspace` — grep confirms zero ripples. ✓
- Constant rename is purely internal to this module + its consumer in `init.py`. ✓
- One docstring drift remaining: module docstring line 4 still says `graph-wiki-directory` (cosmetic — executor's discretion per D-discretion-3).

---

### `packages/workspace-io/src/workspace_io/init.py` — default workspace via resolve_workspace (WSAPI-06)

**Analog:** WIP diff against `00f3c06` (already complete).

The WIP:
- Adds `from workspace_io.config import resolve_workspace` (line 17).
- Replaces `workspace = repo_root / "graph-wiki"` with `workspace = resolve_workspace(repo_root=repo_root)` (line 32).
- Leaves a stray commented-out line `# workspace = repo_root / "graph-wiki"` (line 33) — **delete in plan**.

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` — `run_init` signature (WSAPI-02 init half)

**Analog:** WIP diff against `00f3c06` (already complete; matches D-06).

Current WIP signature (lines 43–47):
```python
async def run_init(
    *,
    topic: str,
    tool: str,
    force: bool,
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
) -> InitResult:
```

Body (lines 65–77):
```python
repo_root = repo_path if repo_path is not None else Path.cwd()
_ws_init(
    repo_root,
    workspace=workspace_path,
    plugin="graph-wiki-agent",
    version=importlib.metadata.version("graph-wiki-agent"),
)
# Phase 2: existing wiki-io resolution + wiki tree population.
wiki, repo = resolve_wiki_and_repo(workspace_path, repo_root)
```

This is the **template** the other 5 commands replicate.

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/{scan,lint,ingest,query,log}.py` — replicate WSAPI-02

**Analog:** `commands/init.py` (WIP) above. The mechanical transform is:

| Step | Current | Target |
|------|---------|--------|
| Signature kwarg | `vault_path: Path \| None = None,` | `workspace_path: Path \| None = None,` |
| Internal var (call to resolver) | `wiki, repo = resolve_wiki_and_repo(vault_path)` | `wiki, repo = resolve_wiki_and_repo(workspace_path)` |
| Docstring `Args:` term | `vault_path: ...` | `workspace_path: ...` (executor discretion per D-discretion-3) |
| Module docstring blob | `run_lint(vault_path, ...)` | `run_lint(workspace_path, ...)` (D-discretion) |

**Per-file scope:**

- `scan.py` — line 227 signature; line 269 call site. **Note:** `run_scan` already has a `repo_path: Path | None = None` parameter (line 230) used for override-based testing; keep it untouched. Pass through `workspace_path` only.
- `lint.py` — line 499 signature; line 525 call site.
- `ingest.py` — **TWO functions:** `run_ingest_source` (line 369–399) AND `run_ingest_work_item` (line 538–576). Both have `vault_path: Path | None = None`; both call `resolve_wiki_and_repo(vault_path)`.
- `query.py` — line 802–808 signature; ALSO has internal `vault_path` parameters in `_discover_pages` (line 191), `_cosine_search_sqlite` (line 241), `_resolve_repo_root` (line 305). These are **private helpers** — out of phase scope unless the executor opts in (D-discretion-3 allows docstring sweep but not param renames in private helpers, since they are not the rename boundary).
- `log.py` — line 36–40 signature; line 59 call site.

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — Typer entry kwarg rename only

**Analog:** WIP diff on the `bootstrap` subcommand (lines 439–453) — already renamed.

WIP `bootstrap` pattern to replicate across other subcommands:
```python
# OLD:
vault: str = typer.Option("", "--vault", help="...")
...
vault_path = Path(vault) if vault else None
result = asyncio.run(run_X(vault_path=vault_path, ...))

# NEW (per WIP bootstrap):
workspace: str = typer.Option("", "--vault", help="...")   # flag literal "--vault" UNCHANGED (Phase 23)
...
workspace_path = Path(workspace) if workspace else None
result = asyncio.run(run_X(workspace_path=workspace_path, ...))
```

**Concrete call sites needing the rename** (grep on `cli.py`):

| Line | Subcommand | Current call | Target call |
|------|------------|--------------|-------------|
| 389–391 | `query` | `run_query(query_text, vault_path, top_k=top_k)` (positional!) | Either rename local var + keep positional, OR convert to kwarg `workspace_path=workspace_path` |
| 424–426 | `log` | `run_log(... vault_path=vault_path)` | `run_log(... workspace_path=workspace_path)` |
| 471–473 | `scan` | `run_scan(vault_path=vault_path, ...)` | `run_scan(workspace_path=workspace_path, ...)` |
| 507–509 | `ingest_source` | `run_ingest_source(path, vault_path)` (positional!) | rename local var |
| 532–541 | `ingest_work_item` | `run_ingest_work_item(... vault_path=vault_path, ...)` | `... workspace_path=workspace_path, ...` |
| 568–570 | `lint` | `run_lint(vault_path=vault_path, ...)` | `run_lint(workspace_path=workspace_path, ...)` |

**Do NOT change:**
- Typer flag literal `"--vault"` — Phase 23.
- Typer parameter name (the variable bound to the option) — the WIP renamed it from `vault` to `workspace`; replicate that pattern, but the flag literal `--vault` stays in the `typer.Option("", "--vault", ...)` call until Phase 23.

---

### `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` — Pydantic field STAYS, kwarg flips

**Analog:** WIP `cli.py` bootstrap pattern (local-var rename without touching the external interface).

6 call sites at lines 105/125/129, 154/169/174, 196/215/220, 243/266/269, 309/332/347, 375/406/409. Each follows:

```python
# Pydantic field — UNCHANGED (Phase 23):
vault_path: str = Field("", description="Vault path (...)")

# Local var inside handler:
vault = Path(input.vault_path) if input.vault_path else None    # input.vault_path UNCHANGED

# Internal Python call — FLIPS:
await run_X(
    ...
    vault_path=vault,    # ← rename kwarg to `workspace_path=vault`
    ...
)
```

**Critical:** `input.vault_path` (Pydantic field access) stays. Only the Python kwarg in the `run_*(vault_path=…)` call flips to `workspace_path=…`. The local var name `vault` can stay as-is or be renamed to `workspace` — executor discretion.

---

## Shared Patterns

### Pattern A: `run_*` kwarg-only rename (covers WSAPI-02 sweep)

**Apply to:** `scan.py`, `lint.py`, `ingest.py` (2 functions), `query.py`, `log.py`.

```python
# BEFORE
async def run_X(
    ...,
    vault_path: Path | None = None,
    ...,
) -> XResult:
    ...
    wiki, repo = resolve_wiki_and_repo(vault_path)

# AFTER
async def run_X(
    ...,
    workspace_path: Path | None = None,
    ...,
) -> XResult:
    ...
    wiki, repo = resolve_wiki_and_repo(workspace_path)
```

The init.py WIP additionally adds `repo_path: Path | None = None` — but this is **NOT required** for the other 5 commands by CONTEXT.md. Only `init.py` needs the repo_path passthrough (because it forwards to `_ws_init(repo_root, ...)`). The other 5 only call `resolve_wiki_and_repo`, which itself accepts an optional `repo_path` but the callers don't need to expose it.

### Pattern B: Test mock-point rename (covers test sweep)

```python
# BEFORE — string is identical regardless of test file:
patch("graph_wiki_agent.commands.<cmd>.resolve_wiki_and_repo", return_value=(wiki, tmp_path))

# AFTER — string is unchanged:
patch("graph_wiki_agent.commands.<cmd>.resolve_wiki_and_repo", return_value=(wiki, tmp_path))
```

**Important:** The `patch()` target string `"graph_wiki_agent.commands.X.resolve_wiki_and_repo"` does NOT change. The function name `resolve_wiki_and_repo` is unchanged in Phase 22 — only its parameter name changes. Mock-point patch strings are stable. ✓

What DOES change in tests:

```python
# BEFORE — kwarg name in the call to run_*:
await run_query("test", vault_path=wt.path, top_k=3)

# AFTER:
await run_query("test", workspace_path=wt.path, top_k=3)
```

And mock side-effect lambdas like:
```python
# BEFORE (test_query_summary_schema_version.py:84):
lambda vault_path=None: (tmp_path.resolve(), None)

# AFTER:
lambda workspace_path=None: (tmp_path.resolve(), None)
```

### Pattern C: YAML literal rename (covers .graph-wiki.local.yaml key cut, D-08)

**Apply to:** `packages/workspace-io/tests/test_config.py` lines 49, 58, 70 ONLY.

```python
# BEFORE
(repo / ".graph-wiki.local.yaml").write_text(f"graph-wiki-directory: {elsewhere}\n")

# AFTER (D-08 hard-cut):
(repo / ".graph-wiki.local.yaml").write_text(f"workspace-directory: {elsewhere}\n")
```

`test_local_config.py` literals are NOT touched — they test the opaque YAML parser, not the key semantics.

## No Analog Found

None. Every file in scope has either a WIP-prototype analog or a sibling-pattern analog. This phase is fully precedented.

## Notable Deviations Between WIP and CONTEXT.md (must be fixed in plan)

| # | WIP state | CONTEXT.md decision | Required fix |
|---|-----------|---------------------|--------------|
| 1 | `_workspace.py:37` uses f-string hack `Path(f"{workspace_path}" + "/wiki").resolve()` | D-02 / D-09: use `workspace_io.paths.wiki_dir(workspace_path)` | Replace with `_ws_paths.wiki_dir(workspace_path)` (already imported) |
| 2 | `_workspace.py:37` walks up from `workspace_path` to find repo when `repo_path` is None | D-05: walk up from `Path.cwd()` | Replace `_find_repo_root(workspace_path)` with `_find_repo_root(Path.cwd())` |
| 3 | `_workspace.py:30-33` docstring still says `vault_path` (3 refs) | D-07: hard rename, no back-compat | Sweep docstring |
| 4 | `init.py:33` (workspace-io) leaves stray comment `# workspace = repo_root / "graph-wiki"` | clean rename | Delete stray comment |
| 5 | `cli.py:442` keeps `--vault` flag literal but renames local var to `workspace` | Phase 23 territory but consistent with Phase 22 scope (kwarg name, not flag literal) | OK as-is; replicate to 5 other subcommands |

## Metadata

**Analog search scope:**
- `packages/wiki-io/src/wiki_io/_workspace.py` (rename target)
- `packages/workspace-io/src/workspace_io/{config,init,paths}.py` (rename targets + consumed paths helper)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/{init,scan,lint,ingest,query,log}.py` (6 commands)
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (Typer entry)
- `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` (MCP boundary)
- `agents/graph-wiki-agent/tests/**` (15 test files w/ mock points or kwarg calls)
- `packages/workspace-io/tests/test_config.py` (YAML literal sweep)
- `packages/eval-harness/tests/test_sweep.py` (cross-package ripple — `run_query(vault_path=...)`)

**Files scanned:** ~30
**Git base for WIP diff:** `00f3c06`
**WIP files (unstaged on `main`):**
1. `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
2. `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py`
3. `packages/wiki-io/src/wiki_io/_workspace.py`
4. `packages/workspace-io/src/workspace_io/config.py`
5. `packages/workspace-io/src/workspace_io/init.py`

**Pattern extraction date:** 2026-05-20
