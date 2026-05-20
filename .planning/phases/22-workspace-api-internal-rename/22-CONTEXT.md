# Phase 22: workspace-api-internal-rename - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Hard-rename the **internal Python API** from `vault_path` to `workspace_path`. Scope is the in-tree Python surface only:

- `packages/vault-io/src/vault_io/_workspace.py::resolve_wiki_and_repo` signature
- All 6 `run_*` command function signatures in `agents/graph-wiki-agent/src/graph_wiki_agent/commands/` (init, scan, lint, ingest, query, log)
- All in-tree callers that pass `vault_path=` as a kwarg
- ~70 `patch("...resolve_wiki_and_repo", ...)` mock points across ~20 test files
- `.graph-wiki.local.yaml` key: hard-cut `graph-wiki-directory` → `workspace-directory`
- `workspace_io.config._resolve_workspace` promoted to public `resolve_workspace`; `workspace_io.init.init()` defaults to `resolve_workspace(repo_root)` instead of hardcoded `repo_root / "graph-wiki"`

**Explicitly NOT in this phase:**
- Typer CLI flag renames (`--vault` → `--workspace`) — Phase 23
- MCP Pydantic field renames — Phase 23
- eval-harness internal renames — Phase 24
- `packages/` misclassification fix — Phase 25
- `vault-io` package directory/module name — out of milestone scope

</domain>

<decisions>
## Implementation Decisions

### WIP Handling
- **D-01:** Adopt the 5 unstaged files on `main` (cli.py, commands/init.py, vault-io/_workspace.py, workspace-io/{config,init}.py) as the foundation for the implementation plan. Do NOT stash and rebuild — the prototype work is sound for WSAPI-01, WSAPI-02 (init only), WSAPI-05, and WSAPI-06.
- **D-02:** Replace the f-string hack `Path(f"{workspace_path}" + "/wiki").resolve()` in `vault-io/_workspace.py` with `workspace_io.paths.wiki_dir(workspace_path)` per the milestone-locked decision. The hack contradicts the contract from REQUIREMENTS.md and must be fixed before commit.

### Plan Chunking
- **D-03:** **Big-bang single plan** — all 6 WSAPI requirements + the ~70 test-mock-point sweep land in one plan and one commit. This explicitly overrides an earlier "split by package" consideration for the test sweep. Trade-off accepted: one large commit, bisect-hostile, but eliminates ordering risk between the API rename and the test updates (tests would break for any intermediate state if split).
- **D-04:** Single-plan gate is `uv run pytest` (workspace-wide) green. No per-package gating between the API rename and the test sweep.

### resolve_wiki_and_repo Semantics
- **D-05:** When `repo_path` is not explicitly specified by the caller, walk up from `Path.cwd()` (NOT from `workspace_path`) to find the repo root. This differs from the current WIP, which walks up from `workspace_path`. Intent: callers that only know their workspace shouldn't have a different repo discovery path than callers that know nothing — both fall back to CWD-based discovery.
- **D-06:** Signature is `resolve_wiki_and_repo(workspace_path: Path | None = None, repo_path: Path | None = None) -> tuple[Path, Path | None]`. When `workspace_path` is supplied, return `(workspace_io.paths.wiki_dir(workspace_path), repo_path or _find_repo_root(Path.cwd()))`. When `workspace_path` is None, continue to delegate to `workspace_io.config.resolve()`.

### Carried Forward (milestone-level locks — non-negotiable)
- **D-07:** Hard rename, no back-compat shims (no deprecation period for the kwarg).
- **D-08:** `.graph-wiki.local.yaml` key hard-cut to `workspace-directory`. Existing files with the old `graph-wiki-directory` key silently fall back to the default workspace location. Document in release notes only.
- **D-09:** Wiki path always derived via `workspace_io.paths.wiki_dir(workspace_path)` — never string concatenation.
- **D-10:** `vault-io` package directory and `vault_io` module path STAY. Only nomenclature changes, not module renames.
- **D-11:** Phase 25 owns the pending `packages-dir-misclassification` todo — explicitly NOT folded here.

### Claude's Discretion
- Test-mock sweep is mechanical; planner/executor decides per-file order and whether to run intermediate `pytest` between files inside the single plan.
- The constant rename `LATTICE_DIRECTORY_KEY` → `WORKSPACE_DIRECTORY_KEY` is internal to `workspace_io.config` — if any other module imports the constant, update at the import site (executor's call).
- Docstring update style on `run_*` functions is at executor's discretion as long as the `vault_path` term is purged.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone requirements (locked decisions)
- `.planning/REQUIREMENTS.md` §"Workspace API — Internal Rename (WSAPI)" — WSAPI-01 through WSAPI-06 acceptance criteria
- `.planning/ROADMAP.md` §"Phase 22: workspace-api-internal-rename" — goal + 5 numbered success criteria

### Files in the rename surface
- `packages/vault-io/src/vault_io/_workspace.py` — `resolve_wiki_and_repo` (the central entry point)
- `packages/workspace-io/src/workspace_io/config.py` — `LATTICE_DIRECTORY_KEY` constant + `_resolve_workspace` to promote
- `packages/workspace-io/src/workspace_io/init.py` — `init()` default workspace logic
- `packages/workspace-io/src/workspace_io/paths.py` — `wiki_dir()` (the canonical derivation function — already exists, just use it)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/{init,scan,lint,ingest,query,log}.py` — 6 `run_*` signatures
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — Typer entry points (kwarg-name rename only, NOT the `--vault` flag literal — that's Phase 23)

### In-flight prototype (adopt as starting point per D-01)
- `git diff` on `main` against `00f3c06` — 5 unstaged files prototyping WSAPI-01, WSAPI-02 (init only), WSAPI-05, WSAPI-06

### Prior milestone artifacts (for pattern alignment)
- `.planning/milestones/v1.3-ROADMAP.md` Phase 20 (workspace manifest model config) — prior precedent for hard-cut config-key removal with no shim
- `.planning/milestones/v1.3-ROADMAP.md` Phase 21 (graph-wiki-agent rename) — prior precedent for atomic-rename plan execution

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `workspace_io.paths.wiki_dir(workspace_path: Path) -> Path` — the canonical wiki-derivation function. Already exists. All callers MUST use it instead of string concatenation.
- `workspace_io.config._find_repo_root(start: Path) -> Path | None` — existing repo-root walk-up helper. Used by D-05's CWD-based fallback.
- `workspace_io.config.resolve()` — existing full-discovery path when neither workspace_path nor repo_path is supplied. Stays as the fallback.

### Established Patterns
- `_resolve_workspace` is the established helper that reads `.graph-wiki.local.yaml` and returns the resolved workspace path. Phase 22 promotes it to public (`resolve_workspace`) without behavior change.
- All 6 `run_*` command functions follow the same signature shape today (`vault_path: Path | None = None`). The rename is mechanically uniform across them.
- Workspace-side init (`workspace_io.init.init()`) currently hardcodes `workspace = repo_root / "graph-wiki"` when no workspace is passed — the WIP already routes this through `resolve_workspace(repo_root)`.

### Integration Points
- `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` reads `input.vault_path` from the MCP Pydantic schemas. This is OUT OF SCOPE for Phase 22 (it's Phase 23). However, the MCP server's *internal Python call* to `run_*` functions must update the kwarg name from `vault_path=` to `workspace_path=` even though the MCP field stays `vault_path` until Phase 23. Plan must thread this carefully.
- `packages/eval-harness/` has its own `vault_path` concentration — entirely out of scope for Phase 22 (Phase 24 territory).

</code_context>

<specifics>
## Specific Ideas

- "Adopt + fix the hack" — the f-string `Path(f"{workspace_path}/wiki").resolve()` must become `workspace_io.paths.wiki_dir(workspace_path)`. This is the single most important correctness point of the phase.
- "Big-bang single plan" was a deliberate trade-off: the user chose one-large-commit over per-package atomicity because the rename's intermediate states are uncompilable (signatures and call sites must move together with mocks).
- "Walk up from CWD if nothing explicitly specified" — the user clarified that when `repo_path` is absent, the discovery starting point is `Path.cwd()`, not `workspace_path`. Subtle but important.

</specifics>

<deferred>
## Deferred Ideas

### Phase 23 (workspace-api-external-rename)
- Typer flag literal rename `--vault` → `--workspace`
- 6 MCP Pydantic Field renames (`vault_path: str` → `workspace_path: str`)
- Scan JSON output field rename (`vault_path` → `wiki_relative_path`)
- Plugin markdown docs sync
- DA-CLI integration test (`test_mcp_e2e.py`) under `GRAPH_WIKI_RUN_INTEGRATION=1`
- `scripts/check-brand.sh` extension banning reintroduction of `vault_path` Field name, `--vault` flag literal, and the `"vault_path"` JSON field

### Phase 24 (eval-harness-workspace-rename)
- All `vault_path` parameters in `eval_harness.{sweep,baseline,structural}` and `--vault` argparse flag in `baseline.py`
- `divergence/{linter,ingestor,scanner,code_reader,synthesizer}.py` rename `vault: Path` → `wiki: Path`
- `eval/README.md` references

### Phase 25 (packages-dir-misclassification-fix)
- `_classify_dir` ≥80% majority heuristic
- `bootstrap --interactive` flag exposure
- Pending todo `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` resolution

### Reviewed Todos (not folded)
- **Fix packages dir misclassification in container detector** (`2026-05-20-fix-packages-dir-misclassification.md`) — matched on keywords (`packages`, `vault`, `src`) but explicitly owned by Phase 25 per REQUIREMENTS.md §PKGCLS. Not folded into Phase 22.

</deferred>

---

*Phase: 22-workspace-api-internal-rename*
*Context gathered: 2026-05-20*
