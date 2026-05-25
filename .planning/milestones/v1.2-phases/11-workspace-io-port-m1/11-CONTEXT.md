# Phase 11: workspace-io Port (M1) - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a new `packages/workspace-io/` Python package — a `graph-wiki`-rebranded port of `lattice-workspace` — and make `wiki-io._workspace.resolve_wiki_and_repo` delegate to `workspace_io.config.resolve()` so that all in-tree wiki-io callers (8 modules + the CLI) gain `.graph-wiki.yaml` manifest discovery without changing their call sites.

**In scope:** new `packages/workspace-io/` workspace member (pyproject, src, tests); port of 7 source modules from `lattice-workspace` (`config`, `init`, `manifest`, `paths`, `render`, `versions`, `_local_config`); port of `assets/CLAUDE.md.template`; rebrand sweep across the ported package (`LATTICE_WORKSPACE` → `GRAPH_WIKI_WORKSPACE`, `.lattice.yaml` → `.graph-wiki.yaml`, `LatticeConfig` → `GraphWikiConfig`, `lattice_workspace.*` → `workspace_io.*`); rewrite of `wiki-io._workspace.py` to delegate; rewrite of the two wiki-io tests that referenced `GRAPH_WIKI_REAL_VAULT_PATH`; port of `lattice-workspace/tests/` under the new module path with `.graph-wiki.yaml` filename expectations; wire `workspace_io.init` into `graph-wiki-agent init` so a single command bootstraps both the workspace shell and the wiki tree.

**Out of scope (delegated to later phases):** rebrand of `wiki-io` body, agents, planning, CLAUDE.md (Phase 12 BRAND-01..04); selective drift backport of lint/* / init_vault.py (Phase 12 BACKPORT-01..04); plugin spec/port (Phases 13–14); wiki self-update (Phase 15); v1.1 carry-forward debt (Phase 16).

</domain>

<decisions>
## Implementation Decisions

### Resolution priority + env-var lifecycle

- **D-01:** `GRAPH_WIKI_REAL_VAULT_PATH` is **dropped entirely** in this phase. Only `GRAPH_WIKI_WORKSPACE` is honored post-port. Code, conftest fixtures, CLI help strings, and the two wiki-io test functions (`test_resolve_wiki_and_repo_raises_on_no_config`, `test_resolve_wiki_and_repo_honors_env_var` in `packages/wiki-io/tests/test_ports_importable.py`) all switch to the new name. No alias, no deprecation warning.
- **D-02:** `wiki-io._workspace.resolve_wiki_and_repo` becomes a **two-tier passthrough**: (1) if `vault_path` argument is provided, short-circuit and return `(vault_path.resolve(), <git-discovered repo_root or None>)`; (2) otherwise call `workspace_io.config.resolve()` and return `(paths.wiki_dir(config.workspace), config.repo_root)`. All env-var handling, `.graph-wiki.yaml` walk-up, and error messages live inside `workspace_io.config` — wiki-io stays a thin shim. The explicit-path branch (step 1) is the MCP boundary contract (Phase 11 SC#3) and stays intact.
- **D-03:** `workspace_io.config.resolve(cwd=None)` is **strict** — no fallbacks beyond `GRAPH_WIKI_WORKSPACE` env override and `.graph-wiki.yaml` cwd walk-up. If neither yields a manifest, raise `RuntimeError` with a message that names `graph-wiki-agent init <path>` as the bootstrap command. No `wiki/` directory sniffing, no `wiki-config.toml` fallback.
- **D-04:** Convention preserved from lattice: `paths.wiki_dir(workspace) = workspace / "wiki"`. The wiki tree is a `wiki/` subdir of the manifest-bearing workspace; manifest sits at `<workspace>/.graph-wiki.yaml`.
- **D-05:** The existing `~/Personal/graph-wiki/agent-research` content is **throwaway**. Pat will delete it and re-init at a new supported location via `graph-wiki-agent init` (which calls `workspace_io.init` followed by `wiki-io.init_vault.init_wiki`). No migration script, no content move.

### Module trim — port-as-is vs drop

- **D-06:** **Drop** `schema.py`. Verified in spike-style read: `_SCHEMA_CONTENT` is 100% work-item frontmatter and the only caller is `lattice-workspace.init.init` invoking `write_schema(work_dir)`. Work-layer is out of scope. The `write_schema(work_dir)` call site is removed from the ported `workspace_io.init`. **Closes WS-06** with verdict "verified work-layer-only, dropped".
- **D-07:** **Port** `init.py` and wire it into `graph-wiki-agent init`. `graph-wiki-agent init <path>` calls `workspace_io.init(repo_root=<path>, plugin='graph-wiki-agent', version=<importlib.metadata>)` first to create `<workspace>/`, `.graph-wiki.yaml`, `git init` if needed, `.gitignore` entry, and workspace `CLAUDE.md`; then calls the existing `wiki-io.init_vault.init_wiki(<workspace>/wiki)` to populate the wiki tree.
- **D-08:** **Port** `render.py` + `versions.py` + `assets/CLAUDE.md.template`. Template content is rebranded (lattice ecosystem prose → graph-wiki ecosystem prose) but the module shapes are unchanged. `versions.warn_if_stale` runs at command startup (off `graph-wiki-agent` entry point) but is effectively a no-op locally until asset hash drifts. **Out of phase:** template body wording polish — port a minimum-viable rebrand; a future ingest cycle can refine.
- **D-09:** **Port** `paths.py` verbatim — all 5 helpers (`wiki_dir`, `raw_dir`, `work_dir`, `knowledge_dir`, `graph_dir`). Tiny module, zero cost, preserves shape compatibility. Callers ignore helpers they don't use.
- **D-10:** **Port** `config.py`, `manifest.py`, `_local_config.py` (the delegation-critical core).

### Manifest field set

- **D-11:** `.graph-wiki.yaml` v2 schema = `{version: 2, initialized_at: 'YYYY-MM-DD', plugins: [{name, installed_version, applied_version}]}` — **same shape as lattice v2**. The `plugins[]` field is preserved (not dropped, not replaced with a generic `metadata` bag) so the manifest is future-compatible with a real plugin-tracking lifecycle should one emerge.
- **D-12:** `workspace_io.init` registers `graph-wiki-agent` as a plugin entry on first init and on re-init. **Both `installed_version` and `applied_version` are written to the same value** = the current `graph-wiki-agent` package version. This makes `versions.warn_if_stale` a no-op locally (installed == applied) while preserving the field shape.
- **D-13:** Version source = `importlib.metadata.version('graph-wiki-agent')` at runtime. Reads from the installed wheel metadata (works under `uv run` editable installs). No hard-coded `__version__` constant.

### Manifest v1→v2 coercion + repo_root semantics

- **D-14:** **Drop** the v1→v2 coercion path. `manifest.read()` requires `version: 2` and raises a friendly error on v1 with guidance to hand-edit (no `migrate-manifest` CLI subcommand in this phase). Saves ~15 lines + matching test surface; agent-research has never written a v1 file.
- **D-15:** `repo_root` from `workspace_io.config.resolve()` is **real git-discovery from cwd** — walk up from cwd looking for `.git`; if found, that's `repo_root`; if not found, fall back to `workspace.parent`. The 8 wiki-io modules that destructure `wiki, _ = resolve_wiki_and_repo()` keep ignoring it (zero behavior change), but `repo_root` is now meaningful for any future caller. Matches `lattice_workspace.config._find_repo_root` semantics directly.
- **D-16:** `.lattice.local.yaml` renames to `.graph-wiki.local.yaml`; the `lattice-directory` key renames to `graph-wiki-directory`. Gitignore entry in `workspace_io.init` updates accordingly. Lets Pat override workspace location per-repo without committing the override — preserves lattice's affordance under the new brand.

### Claude's Discretion

- Internal module structure of `packages/workspace-io/src/workspace_io/` — Claude picks files/grouping (will mirror lattice's flat module layout).
- Test file naming, fixture organization, and pytest fixture reuse strategy under `packages/workspace-io/tests/` — port lattice's structure as the default; reorganize only if rebrand surfaces obvious confusion.
- Error-message wording for the strict-manifest-required `RuntimeError` (D-03) — recommend naming `graph-wiki-agent init` in the message.
- Whether `workspace_io.init` is idempotent across re-runs in the same dir — lattice's already is; preserve that property without re-asking.
- Layout of `assets/` packaging inside the wheel (`[tool.hatch.build.targets.wheel] package-data` vs `[tool.uv_build] include` vs MANIFEST.in) — choose whichever ships the template file correctly via `uv build`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & planning artifacts
- `.planning/ROADMAP.md` §Phase 11 — phase goal, success criteria, requirement mapping (WS-01..10).
- `.planning/REQUIREMENTS.md` §Workspace-IO Port (M1) — full requirement text for WS-01 through WS-10.
- `.planning/threads/next-milestone-planning.md` §"Revised Plan (post-spike-002) §M1" — port scope, module list, open questions (the open questions are now resolved in this CONTEXT.md — see D-01 through D-16).
- `.planning/spikes/002-lattice-drift-inventory/README.md` §Investigation B — `lattice-workspace` import-or-skip analysis; informs which modules are dead weight and the "deferred architectural rejection" framing that this port reverses.
- `.planning/PROJECT.md` §Key Decisions — existing locked decisions to honor (wiki-io keeps name, MCP boundary contract, single-developer velocity).

### Source code being ported (read-only references)
- `/Users/pat/Personal/lattice/packages/lattice-workspace/pyproject.toml` — source package metadata; informs ported pyproject shape (hatchling vs uv_build is open; see D Claude's Discretion).
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/config.py` — port to `workspace_io.config`. `LatticeConfig` → `GraphWikiConfig`. `LATTICE_WORKSPACE` → `GRAPH_WIKI_WORKSPACE`. `LOCAL_CONFIG_FILENAME` → `.graph-wiki.local.yaml`. `LATTICE_DIRECTORY_KEY` → `graph-wiki-directory`. `DEFAULT_WORKSPACE_NAME` → consider `graph-wiki` (matches kebab brand).
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/manifest.py` — port to `workspace_io.manifest`. Filename `.lattice.yaml` → `.graph-wiki.yaml`. **Drop the v1 coercion code path (D-14).**
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/init.py` — port to `workspace_io.init`. Remove the `write_schema(work_dir)` call (D-06). Plugin entry: tracked (D-12).
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/paths.py` — port verbatim (all 5 helpers, D-09).
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/render.py` + `assets/CLAUDE.md.template` — port; rebrand template body content to graph-wiki ecosystem.
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/versions.py` — port; works against rebranded asset hash.
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/_local_config.py` — port to `workspace_io._local_config`.
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/schema.py` — **DO NOT PORT** (D-06).
- `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/` — port all 13 test files; rewrite imports + manifest filename + symbol names; drop v1-read test (D-14).

### Existing agent-research code that changes
- `packages/wiki-io/src/wiki_io/_workspace.py` — rewritten as a thin delegation shim (D-02). Docstring updated.
- `packages/wiki-io/src/wiki_io/__init__.py` — public `resolve_wiki_and_repo` re-export stays; no API change.
- `packages/wiki-io/tests/test_ports_importable.py` — rename `GRAPH_WIKI_REAL_VAULT_PATH` → `GRAPH_WIKI_WORKSPACE` in `test_resolve_wiki_and_repo_raises_on_no_config` and `test_resolve_wiki_and_repo_honors_env_var`. Add a new test for the strict-manifest-required error.
- `packages/wiki-io/tests/conftest.py` (line 35) — fixture references `GRAPH_WIKI_REAL_VAULT_PATH`; updates to `GRAPH_WIKI_WORKSPACE`.
- `packages/wiki-io/src/wiki_io/{append_log,detect_containers,graph_analyzer,ingest_source,ingest_work_item,init_vault,scan_monorepo,update_index,update_tokens}.py` — docstrings/error messages mentioning `GRAPH_WIKI_REAL_VAULT_PATH` get rebranded; the `wiki, _ = resolve_wiki_and_repo()` call sites are unchanged.
- `agents/graph-wiki-agent/src/graph_wiki_agent/config.py` (line 38) — docstring updated.
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (line 433) — `--vault` help text updated (`GRAPH_WIKI_REAL_VAULT_PATH` → `GRAPH_WIKI_WORKSPACE`).
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` (or wherever the `init` command lives) — extended to call `workspace_io.init` before `init_vault.init_wiki` (D-07).
- `pyproject.toml` (root) — `[tool.uv.workspace] members` already covers `packages/*`; no change unless `workspace-io` needs explicit listing.

### Project-level constraints
- `CLAUDE.md` — locked tech stack (Python 3.11+, uv workspace, `pyyaml` dependency on workspace_io); ChatBedrockConverse path unchanged by this phase but the rebrand pass must avoid breaking imports.
- `wiki-config.toml` (repo root) — confirmed **NOT the same surface** as `.graph-wiki.yaml`. `wiki-config.toml` = `{models_path, vault_path}` for graph-wiki-agent CLI runtime; `.graph-wiki.yaml` = workspace manifest. No migration script; record this verdict in PROJECT.md Key Decisions during execution (closes WS-10).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wiki-io._workspace.resolve_wiki_and_repo` — public function that 8 wiki-io modules + the CLI consume. Body is replaced; signature `resolve_wiki_and_repo(vault_path: Path | None = None) -> tuple[Path, Path | None]` stays bit-identical so callers don't touch.
- `wiki-io.init_vault.init_wiki` — runs after `workspace_io.init` in the chained `graph-wiki-agent init` flow. No changes needed; just a new caller upstream.
- Existing pytest patterns: `monkeypatch.setenv` / `monkeypatch.delenv` (used in `test_ports_importable.py`); `tmp_path` fixture (used heavily for vault layout). Ported workspace-io tests follow the same idioms.

### Established Patterns
- **Each package is its own pyproject.toml + src/ + tests/** with `[tool.uv.workspace] members = ["packages/*", "agents/*"]` declaring members at root. Build backend choice varies (model-adapter, eval-harness use hatchling; subagent-runtime mixed). Default to **hatchling** for `workspace-io` for consistency with model-adapter and to match lattice-workspace's source `pyproject.toml` (already hatchling).
- **`from __future__ import annotations`** at top of every module (used in `_workspace.py`, lattice sources). Preserve.
- **No `setuptools` / `setup.py`** anywhere — pyproject-only.
- **`pyyaml>=6.0`** is the workspace-io runtime dep (same as lattice-workspace's source pyproject). Test deps follow the root `[dependency-groups] dev` block.

### Integration Points
- `wiki-io.pyproject.toml` — gains a workspace dependency on `workspace-io`. The wiki-io workspace member declaration in root pyproject already auto-includes `packages/workspace-io/` if it lives under `packages/*` (no member-list edit needed; verify with `uv sync` post-port).
- `graph-wiki-agent` CLI `init` command — calls into `workspace_io.init` directly (workspace-io is added as a `graph-wiki-agent` workspace dep too).
- Trace / log / observability pipelines — none touched in this phase (manifest write is silent, init records nothing in trace JSONL).

</code_context>

<specifics>
## Specific Ideas

- **Clean slate over migration.** Pat will delete the existing `~/Personal/graph-wiki/agent-research` content and re-init at a new supported location. This is a vault-side action, not a code-side action — but it informs the strict-manifest-required policy (D-03) since no in-tree code needs a back-compat path.
- **Direct rebrand for `.graph-wiki.local.yaml`.** The file rename is mechanical (D-16) but it deserves a small callout: lattice's `_local_config` already supports an unkeyed YAML, so the port preserves graceful-handling of an empty/missing file (returns `{}`).
- **`importlib.metadata` over `__version__`.** Pat chose runtime introspection (D-13). Verify this returns a sensible value under `uv run --package graph-wiki-agent` in editable mode during planning research.
- **Two-phase init in one CLI command** (D-07) — `graph-wiki-agent init <path>` is the one user-facing surface; both workspace + wiki bootstrap happen behind it. No new subcommand surface.

</specifics>

<deferred>
## Deferred Ideas

- **`graph-wiki-agent migrate-manifest <path>` CLI subcommand** — surfaced when discussing v1→v2 coercion (D-14). Not needed in this phase (no v1 files locally); would belong in a later phase IF Pat ever imports a v1 `.lattice.yaml` from an external repo and the friendly error proves insufficient.
- **`versions.pending_updates` CLI startup warning** — could fire a one-time "your workspace template is stale" message on `graph-wiki-agent` startup. Skipped here; revisit if template drift becomes a real problem in v1.3+.
- **Template body content polish** — the rebranded `assets/CLAUDE.md.template` ships with a minimum-viable lattice→graph-wiki sweep. A dedicated writing pass to make the workspace `CLAUDE.md` actually useful for agents entering the workspace is deferred — possibly to Phase 15 (wiki self-update) or its own polish phase.
- **`DEFAULT_WORKSPACE_NAME` literal** — lattice uses `"lattice"` as the default workspace dir name when no `.graph-wiki.local.yaml` override is present. Recommend `"graph-wiki"` for graph-wiki. Confirmed via D Claude's Discretion; not a question to surface.
- **Refining `repo_root` to be `Path | None` vs always-`Path`** — D-15 has a `workspace.parent` fallback, so `repo_root` is always a Path post-port. The current type hint `Path | None` could tighten to `Path`. Deferred; tighten in a future cleanup if no caller relies on `None`.

</deferred>

---

*Phase: 11-workspace-io-port-m1*
*Context gathered: 2026-05-17*
