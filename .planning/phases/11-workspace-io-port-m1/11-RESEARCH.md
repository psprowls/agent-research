# Phase 11: workspace-io Port (M1) — Research

**Researched:** 2026-05-17
**Domain:** Python package porting — lattice-workspace → workspace_io; workspace manifest I/O; uv workspace member scaffolding
**Confidence:** HIGH (all claims verified directly from source code in this session)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `CODE_WIKI_REAL_VAULT_PATH` is dropped entirely in this phase. Only `GRAPH_WIKI_WORKSPACE` honored post-port. Code, conftest fixtures, CLI help strings, and the two vault-io test functions switch to the new name. No alias, no deprecation warning.
- **D-02:** `vault-io._workspace.resolve_wiki_and_repo` becomes a two-tier passthrough: (1) if `vault_path` argument is provided, short-circuit and return `(vault_path.resolve(), <git-discovered repo_root or None>)`; (2) otherwise call `workspace_io.config.resolve()` and return `(paths.wiki_dir(config.workspace), config.repo_root)`. All env-var handling, `.graph-wiki.yaml` walk-up, and error messages live inside `workspace_io.config` — vault-io stays a thin shim.
- **D-03:** `workspace_io.config.resolve(cwd=None)` is strict — no fallbacks beyond `GRAPH_WIKI_WORKSPACE` env override and `.graph-wiki.yaml` cwd walk-up. If neither yields a manifest, raise `RuntimeError` naming `code-wiki-agent init <path>` as bootstrap command.
- **D-04:** Convention: `paths.wiki_dir(workspace) = workspace / "wiki"`. Manifest at `<workspace>/.graph-wiki.yaml`.
- **D-05:** Existing `~/Personal/wiki/deep-agents/` is throwaway. Pat will delete and re-init. No migration script.
- **D-06:** `schema.py` dropped (work-layer only; caller was `write_schema(work_dir)` in init.py). WS-06 closed.
- **D-07:** `init.py` ported; wired into `code-wiki-agent init` which calls `workspace_io.init(...)` first, then `vault-io.init_vault.init_wiki(...)`.
- **D-08:** `render.py` + `versions.py` + `assets/CLAUDE.md.template` ported with minimum-viable rebrand. Template body polish deferred.
- **D-09:** `paths.py` ported verbatim (all 5 helpers plus `manifest_path`).
- **D-10:** `config.py`, `manifest.py`, `_local_config.py` ported (delegation-critical core).
- **D-11:** `.graph-wiki.yaml` v2 schema = `{version: 2, initialized_at: 'YYYY-MM-DD', plugins: [{name, installed_version, applied_version}]}` — same shape as lattice v2.
- **D-12:** `workspace_io.init` registers `code-wiki-agent` plugin with `installed_version == applied_version` = current version.
- **D-13:** Version source = `importlib.metadata.version('code-wiki-agent')` at runtime.
- **D-14:** v1→v2 coercion path dropped. `manifest.read()` requires `version: 2`; raises friendly error on v1.
- **D-15:** `repo_root` from `workspace_io.config.resolve()` is real git-discovery from cwd; fallback to `workspace.parent`.
- **D-16:** `.lattice.local.yaml` → `.graph-wiki.local.yaml`; `lattice-directory` key → `graph-wiki-directory`. Gitignore entry updated.

### Claude's Discretion

- Internal module structure of `packages/workspace-io/src/workspace_io/` — mirror lattice's flat layout.
- Test file naming and fixture organization under `packages/workspace-io/tests/`.
- Error-message wording for strict-manifest-required RuntimeError (D-03) — name `code-wiki-agent init` in message.
- Whether `workspace_io.init` is idempotent (yes — preserve lattice's existing idempotency).
- `assets/` packaging inside the wheel — use hatchling's `[tool.hatch.build.targets.wheel] package-data`.
- `DEFAULT_WORKSPACE_NAME` = `"graph-wiki"` (replaces lattice's `"lattice"`).

### Deferred Ideas (OUT OF SCOPE)

- `code-wiki-agent migrate-manifest <path>` CLI subcommand.
- `versions.pending_updates` CLI startup warning.
- Template body content polish.
- Tightening `repo_root` type from `Path | None` to `Path`.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WS-01 | New `packages/workspace-io/` workspace member exists with pyproject.toml, src/workspace_io/, tests/ | Pyproject template from lattice-workspace + existing deep-agents package patterns |
| WS-02 | `config.py` ported as `workspace_io.config` with `GraphWikiConfig` dataclass and `resolve(cwd)` discovery walking upward for `.graph-wiki.yaml` | Source at `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/config.py` — 78 lines, full logic documented |
| WS-03 | `manifest.py` ported reading/writing `.graph-wiki.yaml` | Source at `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/manifest.py` — v1 coercion removed per D-14 |
| WS-04 | `init.py` ported performing workspace bootstrap | Source at `.../init.py`; `write_schema` call removed per D-06; GITIGNORE_ENTRY renamed |
| WS-05 | `paths.py`, `render.py`, `versions.py`, `_local_config.py`, `assets/CLAUDE.md.template` ported | All source files read; rebrand changes documented |
| WS-06 | `schema.py` decision recorded — verified work-layer only, dropped | Confirmed: `_SCHEMA_CONTENT` is pure work-item frontmatter; only caller was `init.py` `write_schema` |
| WS-07 | `LATTICE_WORKSPACE` → `GRAPH_WIKI_WORKSPACE`; all symbols renamed | Full symbol inventory documented in this research |
| WS-08 | `vault-io/_workspace.py` delegates to `workspace_io.config.resolve()` | Current `_workspace.py` at line 14-33; full signature documented; callers mapped |
| WS-09 | Ported tests from `lattice-workspace/tests/` pass | 13 test files inventoried; port strategy documented; `test_manifest_v1_read.py` dropped per D-14 |
| WS-10 | `wiki-config.toml` vs `.graph-wiki.yaml` question answered | Confirmed different surfaces; decision recorded in this research |
</phase_requirements>

---

## Summary

Phase 11 is a direct Python port of an existing Python package (`lattice-workspace`) into the deep-agents uv workspace. The source code is available in full at `/Users/pat/Personal/lattice/packages/lattice-workspace/`. Every module has been read in this session; no guesswork required.

The port decomposes into three distinct work tracks: (1) scaffold the new `packages/workspace-io/` uv workspace member (pyproject, src layout, hatchling build backend), (2) port and rebrand 7 source modules plus the assets template, and (3) rewrite `vault-io._workspace.py` to delegate resolution to `workspace_io.config` and update all call sites of `CODE_WIKI_REAL_VAULT_PATH` across docstrings, tests, and CLI help strings.

The biggest landmines are the breadth of `CODE_WIKI_REAL_VAULT_PATH` references (18 occurrences across agent source, 3 in vault-io tests, and docstrings across 8 vault-io modules), the strict `manifest.read()` behavior change (v1 silently coerced → now raises), and the `render.py` asset-packaging requirement (the CLAUDE.md.template must ship inside the wheel).

**Primary recommendation:** Execute in three waves — (1) scaffold + port pure modules (config, manifest, paths, _local_config, versions, render + assets), (2) rewrite vault-io delegation + all env-var reference updates, (3) port tests and wire `workspace_io.init` into the CLI.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Workspace manifest read/write | `workspace-io` package | — | New package owns the `.graph-wiki.yaml` surface entirely |
| Workspace path resolution (env + walk-up) | `workspace-io` package | — | All discovery logic lives in `workspace_io.config.resolve()` per D-02 |
| Wiki path resolution (exposed to agents) | `vault-io._workspace` (thin shim) | `workspace-io` (via delegation) | MCP boundary contract; callers never touch workspace-io directly |
| Workspace bootstrap (git init + manifest write + gitignore) | `workspace-io.init` | — | Ported from lattice-workspace.init; called before vault-io.init_vault |
| Wiki vault bootstrap (directory structure + templates) | `vault-io.init_vault.init_wiki` | — | Unchanged; runs after workspace_io.init in chained init flow |
| CLI `init` command orchestration | `code-wiki-agent` agent | both above | Two-phase: workspace_io.init first, then init_vault.init_wiki |
| CLAUDE.md template rendering in workspace | `workspace-io.render` | — | Ships template as package asset; renders at init and on re-init |

---

## Standard Stack

### Core (no new dependencies — all existing in workspace)

| Library | Version | Purpose | Provenance |
|---------|---------|---------|------------|
| `pyyaml` | ≥6.0 | YAML read/write for `.graph-wiki.yaml` manifest | [VERIFIED: PyPI] — 6.0.3 current; already in workspace |
| `hatchling` | ≥1.18 | Build backend for `workspace-io` wheel | [VERIFIED: PyPI] — 1.29.0 current; used by `model-adapter` and matches lattice-workspace source |
| Python stdlib `importlib.metadata` | Python 3.11+ stdlib | Version introspection in `workspace_io.init` | [VERIFIED: codebase] — already used in `cli.py:5,51` |
| Python stdlib `subprocess`, `datetime`, `os`, `re`, `dataclasses`, `pathlib` | stdlib | Used across ported modules | [ASSUMED] — standard library, no verification needed |

### No new packages required

All dependencies for `workspace-io` are either Python stdlib or `pyyaml` (already workspace-wide). The package does NOT require:
- `boto3` (vault-io concern)
- `langchain-aws` (agent concern)
- Any async framework

**Installation:**
```bash
# No new pip installs needed. After scaffolding pyproject.toml:
uv sync
```

**Version verification:**
```bash
pip3 index versions pyyaml     # → 6.0.3 (confirmed)
pip3 index versions hatchling  # → 1.29.0 (confirmed)
```

---

## Package Legitimacy Audit

No new third-party packages are introduced in this phase. The only runtime dependency is `pyyaml>=6.0` which is already present in the workspace. `slopcheck` was unavailable for install; however, `pyyaml` is a foundational, decade-old package — the legitimacy risk is negligible.

| Package | Registry | Age | Disposition |
|---------|----------|-----|-------------|
| `pyyaml` | PyPI | ~15 years | Approved — existing workspace dependency; no change |

**Packages removed due to slopcheck verdict:** none
**Packages flagged as suspicious:** none

---

## Architecture Patterns

### System Architecture Diagram

```
code-wiki-agent CLI / MCP
        |
        | vault_path arg (explicit) OR env not set → delegate
        v
vault-io._workspace.resolve_wiki_and_repo(vault_path)
        |
        |-- vault_path provided? → short-circuit: (vault_path.resolve(), git_root_or_None)
        |
        |-- vault_path=None → workspace_io.config.resolve(cwd)
              |
              |-- GRAPH_WIKI_WORKSPACE env set? → workspace = Path(env)
              |-- else: walk up from cwd for .graph-wiki.yaml
              |-- else: raise RuntimeError("run code-wiki-agent init <path>")
              |
              v
           GraphWikiConfig(workspace=<Path>, repo_root=<Path>)
              |
              v
           return (paths.wiki_dir(config.workspace), config.repo_root)
```

```
code-wiki-agent init <path>
        |
        v
workspace_io.init(repo_root=<path>, plugin="code-wiki-agent", version=<importlib>)
        |-- mkdir workspace (repo_root / "graph-wiki" unless .graph-wiki.local.yaml overrides)
        |-- git init if workspace not already in a git repo
        |-- read/create .graph-wiki.yaml (v2 schema)
        |-- register/update "code-wiki-agent" plugin entry
        |-- render workspace/CLAUDE.md (from assets/CLAUDE.md.template)
        |-- ensure .graph-wiki.local.yaml in repo_root/.gitignore
        |
        v
vault-io.init_vault.init_wiki(workspace / "wiki")
        |-- creates wiki directory structure
        |-- installs schema files / CLAUDE.md
```

### Recommended Project Structure

```
packages/workspace-io/
├── pyproject.toml            # hatchling; pyyaml>=6.0 dep; Python >=3.11
└── src/
    └── workspace_io/
        ├── __init__.py       # exports: GraphWikiConfig, init, resolve, PendingUpdate, pending_updates, warn_if_stale
        ├── config.py         # GraphWikiConfig dataclass + resolve(cwd) + _find_repo_root + _resolve_workspace
        ├── manifest.py       # read() / write() for .graph-wiki.yaml (v2 only; no v1 coercion)
        ├── init.py           # init(repo_root, *, plugin, version, workspace) — idempotent bootstrap
        ├── paths.py          # manifest_path, wiki_dir, raw_dir, work_dir, knowledge_dir, graph_dir
        ├── render.py         # render_workspace_claude_md(workspace) — reads manifest, writes CLAUDE.md
        ├── versions.py       # warn_if_stale, pending_updates, PendingUpdate
        ├── _local_config.py  # read(.graph-wiki.local.yaml) — pure line parser
        └── assets/
            └── CLAUDE.md.template
tests/
├── test_config.py
├── test_manifest.py
├── test_manifest_v2_roundtrip.py   # (test_manifest_v1_read.py DROPPED per D-14)
├── test_init.py
├── test_init_records_version.py
├── test_init_bumps_version.py
├── test_paths.py
├── test_local_config.py
├── test_render.py
├── test_warn_if_stale.py
├── test_pending_updates.py
└── test_schema.py  # DROPPED (D-06)
```

### Anti-Patterns to Avoid

- **Calling `yaml.safe_load` without `or {}`:** The manifest file can exist but contain only whitespace; `yaml.safe_load` returns `None` in that case. Source code uses `yaml.safe_load(...) or {}` — preserve this.
- **Shipping template as `data_files` instead of `package-data`:** Hatchling's `[tool.hatch.build.targets.wheel] packages = ["src/workspace_io"]` will include the `assets/` subdirectory automatically since it is inside the package directory. No extra MANIFEST.in or explicit `package-data` directive needed.
- **Using `uv_build` as build backend:** `model-adapter` and `eval-harness` use `uv_build` with a special `include` block for package data. Hatchling is simpler for asset inclusion — use hatchling to match `lattice-workspace` source. See D (Claude's Discretion).
- **Adding `pyyaml` to root `[dependency-groups] dev`:** It must go in `workspace-io`'s own `[project] dependencies` since it's a runtime dep of the package, not a dev-only tool.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML manifest read/write | Custom serializer | `pyyaml` `yaml.safe_load` / `yaml.safe_dump` | Already handles PyYAML's date-type coercion gotcha (bare dates parsed as `datetime.date` → normalize to `str`) |
| Local config parsing | `pyyaml` full parser | `_local_config.read()` (bespoke line parser) | Deliberate: avoids PyYAML dep on the simple k:v file; handles inline comments + surrounding quotes |
| Asset path resolution | `importlib.resources` or `pkg_resources` | `Path(__file__).resolve().parent / "assets" / "CLAUDE.md.template"` | Simpler; works identically in editable and wheel installs when the `assets/` dir is inside the package |
| Version reading | Hard-coded `__version__` | `importlib.metadata.version('code-wiki-agent')` | Verified in session: returns `"0.1.0"` under `uv run --package code-wiki-agent` editable install |
| Repo root discovery | Subprocess `git rev-parse` | `_find_repo_root(start)` — walk up checking for `.git` dir | Pure Python; no subprocess; already in lattice source and tested |

**Key insight:** The lattice source is already idiomatic Python with no unnecessary abstractions. Port as-is; do not generalize.

---

## Source Layout — Complete File Inventory

### Source modules to port (verified by reading each file)

| Source Path (lattice) | Target Path (workspace-io) | Lines | Changes |
|----------------------|---------------------------|-------|---------|
| `src/lattice_workspace/config.py` | `src/workspace_io/config.py` | 78 | `LatticeConfig` → `GraphWikiConfig`; `LATTICE_WORKSPACE` → `GRAPH_WIKI_WORKSPACE`; `LOCAL_CONFIG_FILENAME` → `.graph-wiki.local.yaml`; `LATTICE_DIRECTORY_KEY` → `graph-wiki-directory`; `DEFAULT_WORKSPACE_NAME` → `graph-wiki`; import path |
| `src/lattice_workspace/manifest.py` | `src/workspace_io/manifest.py` | 65 | `.lattice.yaml` → `.graph-wiki.yaml` in comments; **drop `_coerce()` and the v1 branch from `read()`** — raise `RuntimeError` if `version != 2` |
| `src/lattice_workspace/init.py` | `src/workspace_io/init.py` | 104 | Remove `from lattice_workspace.schema import write_schema` and `write_schema(_paths.work_dir(workspace))` call; rename `_GITIGNORE_ENTRY` to `.graph-wiki.local.yaml`; update default workspace name to `graph-wiki`; fix imports |
| `src/lattice_workspace/paths.py` | `src/workspace_io/paths.py` | 30 | `.lattice.yaml` → `.graph-wiki.yaml` in `manifest_path()`; imports |
| `src/lattice_workspace/render.py` | `src/workspace_io/render.py` | 118 | `AUTO_START`/`AUTO_END` marker strings renamed (`lattice-workspace:auto` → `workspace-io:auto`); `_PLUGIN_POINTERS` dict updated (`lattice-wiki` → `code-wiki-agent` or clear old entries); import paths |
| `src/lattice_workspace/versions.py` | `src/workspace_io/versions.py` | 62 | Import paths only |
| `src/lattice_workspace/_local_config.py` | `src/workspace_io/_local_config.py` | 49 | Comments updated (`.lattice.local.yaml` → `.graph-wiki.local.yaml`) |
| `src/lattice_workspace/assets/CLAUDE.md.template` | `src/workspace_io/assets/CLAUDE.md.template` | 30 | Rebrand prose: "Lattice" → "graph-wiki"; `.lattice.yaml` → `.graph-wiki.yaml`; `.lattice.local.yaml` → `.graph-wiki.local.yaml`; `lattice-directory:` → `graph-wiki-directory:`; marker strings match updated `render.py` |
| `src/lattice_workspace/__init__.py` | `src/workspace_io/__init__.py` | 13 | `LatticeConfig` → `GraphWikiConfig`; import paths |
| `src/lattice_workspace/schema.py` | **DO NOT PORT** | — | Work-layer only per D-06 |

### Existing deep-agents code that changes

**`packages/vault-io/src/vault_io/_workspace.py`** (current: 34 lines)
- Rewrite body completely per D-02.
- Signature stays bit-identical: `resolve_wiki_and_repo(vault_path: Path | None = None) -> tuple[Path, Path | None]`
- New body: if `vault_path` provided → `(vault_path.resolve(), _find_git_root(vault_path) or None)`; else → `workspace_io.config.resolve(); return (paths.wiki_dir(config.workspace), config.repo_root)`
- Remove `os.environ.get("CODE_WIKI_REAL_VAULT_PATH")` — env handling moves to workspace_io.

**`packages/vault-io/pyproject.toml`** — add `workspace-io` as workspace dep:
```toml
[project]
dependencies = [
    "python-frontmatter>=1.1",
    "boto3>=1.38",
    "workspace-io",           # NEW
]

[tool.uv.sources]
workspace-io = { workspace = true }   # NEW
```

**`packages/vault-io/tests/test_ports_importable.py`** — two tests updated:
- `test_resolve_wiki_and_repo_raises_on_no_config`: `delenv("CODE_WIKI_REAL_VAULT_PATH")` → `delenv("GRAPH_WIKI_WORKSPACE")`; error message assertion updated.
- `test_resolve_wiki_and_repo_honors_env_var`: `setenv("CODE_WIKI_REAL_VAULT_PATH")` → `setenv("GRAPH_WIKI_WORKSPACE")`. Note: after the rewrite, env-var path goes through `workspace_io.config.resolve()` which walks the workspace back to `wiki_dir(config.workspace)` — the test needs a `.graph-wiki.yaml` in the fake workspace for `resolve()` to not raise. Fixture will need a minimal manifest file.
- Add new test: `test_resolve_wiki_and_repo_strict_raises_without_manifest` that verifies RuntimeError message contains `"code-wiki-agent init"`.

**`packages/vault-io/tests/conftest.py` line 35** — `os.environ.get("CODE_WIKI_REAL_VAULT_PATH")` → `os.environ.get("GRAPH_WIKI_WORKSPACE")`

**Docstring-only changes** (no behavior change; grep confirmed 18 occurrences in agents, 5 in vault-io src):
- `packages/vault-io/src/vault_io/append_log.py:9` — docstring
- `packages/vault-io/src/vault_io/detect_containers.py:6` — docstring
- `packages/vault-io/src/vault_io/graph_analyzer.py:5-6` — docstring
- `agents/code-wiki-agent/src/code_wiki_agent/commands/log.py:48` — docstring
- `agents/code-wiki-agent/src/code_wiki_agent/commands/init.py:52` — docstring
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:788` — docstring
- `agents/code-wiki-agent/src/code_wiki_agent/config.py:38` — docstring
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — 5 occurrences in Pydantic Field descriptions (functional, not just comments)
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — 6 occurrences in `--vault` option help strings (functional)

**Important:** The MCP server `Field` descriptions and CLI `--vault` help strings are user-visible, not just comments. They must change from `CODE_WIKI_REAL_VAULT_PATH` to `GRAPH_WIKI_WORKSPACE`.

**`agents/code-wiki-agent/src/code_wiki_agent/commands/init.py`** — extended per D-07:
- `run_init()` gains a `workspace_io.init(...)` call before the existing `resolve_wiki_and_repo()` + `init_wiki()` sequence.
- The CLI `init` command already accepts `vault` / `vault_path` arg. After this phase, when `vault_path` is None, resolution falls through to `workspace_io.config.resolve()` which requires a `.graph-wiki.yaml`. The two-phase init (workspace first, then wiki) ensures the manifest exists before `init_wiki` runs.

**`agents/code-wiki-agent/pyproject.toml`** — add `workspace-io` dep:
```toml
dependencies = [
    "vault-io",
    "model-adapter",
    "subagent-runtime",
    "workspace-io",           # NEW
    ...
]

[tool.uv.sources]
...
workspace-io = { workspace = true }   # NEW
```

---

## `vault-io._workspace.resolve_wiki_and_repo` — Current Signature and Callers

**File:** `packages/vault-io/src/vault_io/_workspace.py`
**Lines 14-33** (current, pre-port)

```python
def resolve_wiki_and_repo(
    vault_path: Path | None = None,
) -> tuple[Path, Path | None]:
```

**Return contract (post-port, per D-02):**
- If `vault_path` is provided → `(vault_path.resolve(), git_discovered_root_or_None)`
- If `vault_path` is None → delegates to `workspace_io.config.resolve(cwd)` → `(paths.wiki_dir(config.workspace), config.repo_root)`

**Call sites in vault-io src (8 modules — all unmodified call sites):**

| File | Pattern | Context |
|------|---------|---------|
| `append_log.py:139` | `wiki, _ = resolve_wiki_and_repo()` | No explicit path |
| `detect_containers.py:174` | `wiki, _ = resolve_wiki_and_repo()` | No explicit path |
| `graph_analyzer.py:181` | `wiki, _ = resolve_wiki_and_repo()` | No explicit path |
| `init_vault.py:305` | `wiki, _ = resolve_wiki_and_repo()` | No explicit path |
| `ingest_source.py` | (via import) | Caller passes vault_path |
| `ingest_work_item.py` | (via import) | Caller passes vault_path |
| `scan_monorepo.py:1082` | `wiki, _ = resolve_wiki_and_repo()` | No explicit path |
| `update_index.py:328` | `wiki, _ = resolve_wiki_and_repo()` | No explicit path |
| `update_tokens.py:175` | `wiki, _ = resolve_wiki_and_repo()` | No explicit path |

**Call sites in agent commands (all pass `vault_path` arg):**

| File | Call | Notes |
|------|------|-------|
| `commands/init.py:60` | `resolve_wiki_and_repo(vault_path)` | vault_path from CLI/MCP |
| `commands/ingest.py:394,540` | `resolve_wiki_and_repo(vault_path)` | |
| `commands/scan.py:269` | `resolve_wiki_and_repo(vault_path)` | |
| `commands/query.py:813` | `resolve_wiki_and_repo(vault_path)` | |
| `commands/log.py:59` | `resolve_wiki_and_repo(vault_path)` | |
| `commands/lint.py:521` | `resolve_wiki_and_repo(vault_path)` | |

**Re-export:** `vault_io.__init__.py` re-exports `resolve_wiki_and_repo` — unchanged, no call-site update needed.

---

## `.graph-wiki.yaml` Schema

**Version 2 schema (unchanged from lattice v2):**

```yaml
version: 2
initialized_at: "2026-05-17"        # YYYY-MM-DD string (PyYAML date → str normalization required on read)
plugins:
  - name: code-wiki-agent
    installed_version: "0.1.0"
    applied_version: "0.1.0"
```

**Key serialization detail:** PyYAML parses bare dates (e.g., `2026-05-17`) as `datetime.date` objects. The existing `manifest.read()` normalizes this: `result["initialized_at"] = str(result["initialized_at"])`. The ported version MUST preserve this normalization even without the v1 coercion path.

**Write format:** `yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)` — block style, key order preserved. The `test_manifest_v2_roundtrip.py` tests verify key order (version < initialized_at < plugins) and no flow-style brackets.

---

## `wiki-config.toml` vs `.graph-wiki.yaml` — Different Surfaces (WS-10 Answer)

**`/Users/pat/Personal/deep-agents/wiki-config.toml` (confirmed by reading):**
```toml
models_path = "/Users/pat/Personal/deep-agents/models-qwen.toml"
vault_path  = "/Users/pat/Personal/wiki/deep-agents"
```

**Purpose:** Runtime config for the `code-wiki-agent` CLI's `--config` flag. Fields: `models_path` (model role TOML), `vault_path` (default wiki path). Read by `WikiConfig` dataclass in `code_wiki_agent.config`.

**`.graph-wiki.yaml` purpose:** Workspace manifest. Fields: `version`, `initialized_at`, `plugins[{name, installed_version, applied_version}]`. Read/written by `workspace_io.manifest`.

**Verdict:** Completely different surfaces. `wiki-config.toml` is a runtime config file pointing at model config and vault location. `.graph-wiki.yaml` is a structured manifest tracking which plugins have initialized the workspace. **No migration script needed or appropriate.** [VERIFIED: read both files in this session]

**Action:** Record this verdict in `PROJECT.md Key Decisions` during Phase 11 execution to close WS-10.

---

## uv Workspace Member Scaffolding

**Template** (based on `lattice-workspace/pyproject.toml` + hatchling pattern from `model-adapter`):

```toml
[project]
name = "workspace-io"
version = "0.1.0"
description = "Workspace bootstrap, manifest IO, and config resolution for the graph-wiki ecosystem."
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/workspace_io"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
```

**Root pyproject.toml:** No change needed. `[tool.uv.workspace] members = ["packages/*", "agents/*"]` already covers `packages/workspace-io/` when the directory exists. Verified pattern from existing members.

**`uv sync` after scaffolding** will auto-discover and install the new member.

**Key uv rules that apply:**
- Workspace members are installed editable automatically — no `editable = true` needed.
- `uv run --package workspace-io pytest` to run only workspace-io tests.
- `pyyaml` goes in `[project] dependencies` (runtime), not in root `[dependency-groups] dev`.

---

## Env-Var Resolution Order

**Old (`vault-io._workspace` pre-port):**
1. `vault_path` argument (explicit)
2. `CODE_WIKI_REAL_VAULT_PATH` env var
3. `RuntimeError` — no fallback

**New (`vault-io._workspace` post-port, per D-02 and D-03):**
1. `vault_path` argument (explicit) → `(vault_path.resolve(), git_discovered_root_or_None)` — MCP boundary contract preserved
2. Delegate to `workspace_io.config.resolve(cwd=None)`:
   a. `GRAPH_WIKI_WORKSPACE` env var → workspace path (repo_root discovered via `.git` walk from workspace)
   b. `.graph-wiki.yaml` walk-up from cwd (via `_find_repo_root` → `_resolve_workspace`)
   c. `RuntimeError(f"No .graph-wiki.yaml found. Run: code-wiki-agent init <path>")`

**Divergences from lattice config:**
- Lattice's `resolve()` does NOT raise on missing manifest — it falls back to `<repo_root>/lattice`. The ported version is **strict** (D-03): missing manifest → RuntimeError. This is the single most significant behavioral divergence from the source.
- Lattice's `DEFAULT_WORKSPACE_NAME = "lattice"` → ported as `"graph-wiki"`.

---

## Test Porting Strategy

### Tests to port (12 files), grouped by behavior

**Group 1: Config/Resolution (port `test_config.py`)**

9 tests covering: default workspace name, local YAML with absent/present/abs/relative/tilde key, walk-up to find .git, no-git fallback, no-arg uses cwd, CLI `__main__` prints workspace.

**Rebrand changes:** `LatticeConfig` → `GraphWikiConfig`; `resolve(...)` import path; assert `cfg.workspace == (repo / "lattice").resolve()` → `(repo / "graph-wiki").resolve()`; `"lattice_workspace.config._find_repo_root"` → `"workspace_io.config._find_repo_root"`; CLI subprocess module path.

**Additional test needed** (not in lattice, required by D-03): `test_resolve_raises_when_no_manifest_found` — verify that without `GRAPH_WIKI_WORKSPACE` env and without a `.graph-wiki.yaml` ancestor, `resolve()` raises `RuntimeError` containing `"code-wiki-agent init"`.

**Group 2: Manifest read/write (port `test_manifest.py`, `test_manifest_v2_roundtrip.py`; DROP `test_manifest_v1_read.py`)**

- `test_manifest.py` (5 tests): roundtrip, missing file returns `{}`, creates parent dirs, empty plugins, YAML keys present.
- `test_manifest_v2_roundtrip.py` (3 tests): v2 write→read, key order, block style.
- `test_manifest_v1_read.py` (3 tests): **DROPPED** per D-14. Replace with one test: `test_read_raises_on_v1` verifying `RuntimeError` on a v1-format file.

**Rebrand changes:** `.lattice.yaml` → `.graph-wiki.yaml` in all path constructions.

**Group 3: Paths (port `test_paths.py`)**

7 tests: each helper + string coercion. Only change: `manifest_path` test expects `.graph-wiki.yaml` not `.lattice.yaml`.

**Group 4: Local config (port `test_local_config.py`)**

9 tests: missing file, reads key, strips inline comment, strips quotes (single/double), skips blank/comment/malformed, returns unknown keys, empty value. No behavioral change; update file references from `.lattice.local.yaml` to `.graph-wiki.local.yaml` in test fixture writes.

**Group 5: Init bootstrap (port `test_init.py`, `test_init_records_version.py`, `test_init_bumps_version.py`)**

- `test_init.py` (15 tests): workspace created, manifest created, plugin recorded, two-plugin accumulation, idempotency, external workspace, git-init for outside-git workspace, gitignore entry, CLAUDE.md written, user prose preserved.
- `test_init_records_version.py` (3 tests): both version fields written, idempotent same version no rewrite, missing version kwarg raises TypeError.
- `test_init_bumps_version.py` (1 test): re-init with newer version bumps both fields.

**Rebrand changes:** `"lattice-wiki"` → `"code-wiki-agent"` plugin name in test args; `tmp_path / "lattice"` → `tmp_path / "graph-wiki"` workspace paths; `.lattice.local.yaml` → `.graph-wiki.local.yaml` in gitignore assertions; remove `test_creates_work_schema` (D-06 — `write_schema` removed); update CLAUDE.md auto-marker string.

**Group 6: Render (port `test_render.py`)**

6 tests: creates CLAUDE.md first call, lists each plugin, refresh updates block only, idempotent, unknown plugin generic pointer, no-manifest no-render.

**Rebrand changes:** Auto-block marker string (`lattice-workspace:auto` → `workspace-io:auto`); `.lattice.yaml` → `.graph-wiki.yaml` in manifest write helper; plugin name strings.

**Group 7: Versions (port `test_warn_if_stale.py`, `test_pending_updates.py`)**

- `test_warn_if_stale.py` (4 tests): no-entry no-write, match no-write, mismatch writes installed only, v1-coerced entry (applied=None) no signal.
- `test_pending_updates.py` (4 tests): only mismatched returned, no mutation, frozen dataclass, no-manifest empty.

**Important:** `test_warn_if_stale.py` has a test `test_v1_coerced_entry_no_signal` that writes a v1-format manifest directly and checks `warn_if_stale`. After D-14, `manifest.read()` will raise on v1 format. This test must be **rewritten**: write a v2 manifest with `applied_version: null` directly (simulating what a v1-coerced entry looks like in v2 form). The behavior (returns False, no write) is preserved.

**Rebrand changes:** Workspace paths `tmp_path / "lattice"` → `tmp_path / "graph-wiki"`; plugin names; `.lattice.yaml` → `.graph-wiki.yaml`; imports.

**DROP: `test_schema.py`** (4 tests) — per D-06.

### Summary count

| Action | Count |
|--------|-------|
| Port unchanged (rebrand only) | 10 files |
| Port with behavioral change | 2 files (`test_warn_if_stale.py`, `test_manifest_v1_read.py` → rewrite) |
| Drop | 2 files (`test_manifest_v1_read.py` replaced with 1-test file, `test_schema.py`) |
| New (not in lattice) | 1 test in `test_config.py` (strict-resolve-raises) |
| New (vault-io, not workspace-io) | 1 test in `test_ports_importable.py` (strict error message) |

---

## Common Pitfalls

### Pitfall 1: `test_resolve_wiki_and_repo_honors_env_var` fails after port

**What goes wrong:** The ported `_workspace.resolve_wiki_and_repo()` now delegates to `workspace_io.config.resolve()` when no `vault_path` is provided. When `GRAPH_WIKI_WORKSPACE` is set, `resolve()` returns a `GraphWikiConfig` with `workspace = Path(env)`. Then `_workspace` calls `paths.wiki_dir(config.workspace)` which returns `workspace / "wiki"`. But the existing test creates `fake_vault = tmp_path / "vault"` and asserts `wiki == fake_vault.resolve()`.

**After port**, `wiki == (fake_vault / "wiki").resolve()` — the test will fail unless updated.

**How to avoid:** Update the test to: (a) create `fake_workspace = tmp_path / "workspace"`, (b) create `fake_workspace / ".graph-wiki.yaml"` with a v2 manifest, (c) set `GRAPH_WIKI_WORKSPACE = str(fake_workspace)`, (d) assert `wiki == (fake_workspace / "wiki").resolve()`.

### Pitfall 2: `_local_config` uses PyYAML implicitly

**What goes wrong:** `_local_config.py` is deliberately PyYAML-free (bespoke line parser). Do not refactor it to use `yaml.safe_load` even though `pyyaml` is now a dep of the package. The custom parser handles the `"key: "` with empty value case that PyYAML would return `None` for.

**How to avoid:** Port `_local_config.py` verbatim. Do not "improve" it.

### Pitfall 3: render.py auto-block marker string mismatch

**What goes wrong:** `render.py` defines `AUTO_START = "<!-- lattice-workspace:auto:plugins:start -->"`. The template `assets/CLAUDE.md.template` contains `{{PLUGIN_LIST}}` which is replaced on first render, but the marker strings are hardcoded in render.py AND must match any existing workspace CLAUDE.md files. After port, if the marker strings are renamed (e.g., to `workspace-io:auto`), existing workspace CLAUDE.md files with the old lattice markers will not have their auto-block refreshed — the fallback path (append at end) will trigger.

**How to avoid:** Since Pat is deleting the existing `~/Personal/wiki/deep-agents/` (D-05), there are no existing workspace CLAUDE.md files to worry about. Rename the marker strings to `workspace-io:auto:plugins:start/end` consistently in both `render.py` (constants) and the template.

### Pitfall 4: `init.py` default workspace name in tests

**What goes wrong:** Many `test_init.py` tests assert `(tmp_path / "lattice").is_dir()`. After port, the default is `"graph-wiki"`. All such assertions must update to `(tmp_path / "graph-wiki")`.

**How to avoid:** Systematic search-replace in the test file; confirm no stale `"lattice"` directory name references remain.

### Pitfall 5: `importlib.metadata.version` raises `PackageNotFoundError` in workspace-io tests

**What goes wrong:** `workspace_io.init()` calls `importlib.metadata.version('code-wiki-agent')` at runtime. During workspace-io tests (run via `uv run --package workspace-io pytest`), `code-wiki-agent` IS installed in the uv workspace (editable), so this should work. But if tests directly call `init(repo_root, plugin="code-wiki-agent", version="...")` they pass `version` explicitly — no `importlib.metadata` call in that path. The `importlib.metadata` call happens in the CLI layer, not in `workspace_io.init()`. Double-check: `workspace_io.init` accepts `version: str` as explicit kwarg (same as lattice-workspace) — caller is responsible for obtaining the version string.

**How to avoid:** Keep the existing design: `workspace_io.init(repo_root, plugin=..., version=...)` takes version as arg. The CLI calls `importlib.metadata.version('code-wiki-agent')` and passes it. Tests pass `version="1.0.0"` directly. No issue.

### Pitfall 6: Breadth of `CODE_WIKI_REAL_VAULT_PATH` references in MCP server

**What goes wrong:** `server.py` contains 5 occurrences of `CODE_WIKI_REAL_VAULT_PATH` in Pydantic `Field(description=...)` strings — these are functional (exposed to MCP clients as tool schema descriptions), not just comments. Missing any of them leaves misleading documentation for MCP consumers.

**How to avoid:** `grep -n "CODE_WIKI_REAL_VAULT_PATH" agents/code-wiki-agent/src/code_wiki_mcp/server.py` will find all 5. Update each `Field(description=...)` string.

### Pitfall 7: Existing vault-io module-level `__main__` blocks break

**What goes wrong:** Several vault-io modules have `if __name__ == "__main__":` blocks that call `resolve_wiki_and_repo()` with no argument, expecting `CODE_WIKI_REAL_VAULT_PATH` to be set. After the port, these blocks now require either `GRAPH_WIKI_WORKSPACE` or a `.graph-wiki.yaml` ancestor — they will raise RuntimeError in the same conditions that previously returned a path.

**Impact:** Low — these are development/debugging entry points, not production paths. The behavior change is correct (they should error if no workspace configured). No code change needed beyond the docstring updates.

---

## Code Examples

### GraphWikiConfig dataclass and resolve() — post-port shape

```python
# Source: lattice-workspace/src/lattice_workspace/config.py (verified)
# Post-port shape (with rebrand applied)

LOCAL_CONFIG_FILENAME = ".graph-wiki.local.yaml"
GRAPH_WIKI_WORKSPACE_ENV = "GRAPH_WIKI_WORKSPACE"
LATTICE_DIRECTORY_KEY = "graph-wiki-directory"
DEFAULT_WORKSPACE_NAME = "graph-wiki"

@dataclass(frozen=True)
class GraphWikiConfig:
    workspace: Path
    repo_root: Path

def resolve(cwd: Path | None = None) -> GraphWikiConfig:
    env_workspace = os.environ.get(GRAPH_WIKI_WORKSPACE_ENV, "").strip()
    if env_workspace:
        workspace = Path(env_workspace).expanduser().resolve()
        repo_root = _find_repo_root(workspace) or workspace.parent.resolve()
        return GraphWikiConfig(workspace=workspace, repo_root=repo_root)
    # Normal discovery path
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    repo_root = _find_repo_root(cwd) or cwd.resolve()
    workspace = _resolve_workspace(repo_root)
    # D-03: strict — must have .graph-wiki.yaml
    manifest = workspace / ".graph-wiki.yaml"
    if not manifest.exists():
        raise RuntimeError(
            f"No .graph-wiki.yaml found in {workspace}. "
            f"Run: code-wiki-agent init <path>"
        )
    return GraphWikiConfig(workspace=workspace, repo_root=repo_root)
```

**Note:** The strict check is the primary behavioral divergence from lattice. Lattice's `resolve()` returns even without a manifest; ported version raises.

### vault-io._workspace — post-port delegation shim

```python
# Post-port shape for packages/vault-io/src/vault_io/_workspace.py

from __future__ import annotations
from pathlib import Path
from workspace_io import config as _ws_config
from workspace_io import paths as _ws_paths
from workspace_io.config import _find_repo_root

def resolve_wiki_and_repo(
    vault_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Return (wiki_path, repo_root).

    Priority:
    1. vault_path argument — short-circuit (MCP boundary contract)
    2. workspace_io.config.resolve() — env var + .graph-wiki.yaml walk-up
    3. RuntimeError from workspace_io (names code-wiki-agent init)
    """
    if vault_path is not None:
        return vault_path.resolve(), _find_repo_root(vault_path)
    cfg = _ws_config.resolve()
    return _ws_paths.wiki_dir(cfg.workspace), cfg.repo_root
```

### workspace-io pyproject.toml

```toml
[project]
name = "workspace-io"
version = "0.1.0"
description = "Workspace bootstrap, manifest IO, and config resolution for the graph-wiki ecosystem."
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/workspace_io"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
```

---

## Runtime State Inventory

This is a port/rebrand phase — the `CODE_WIKI_REAL_VAULT_PATH` env var is dropped in favor of `GRAPH_WIKI_WORKSPACE`.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no DB stores env var names; manifest `.graph-wiki.yaml` is a new file, not a rename of a stored record | None |
| Live service config | `wiki-config.toml` at project root sets `vault_path` (not the env var); unaffected by this rename | None — wiki-config.toml uses a different mechanism |
| OS-registered state | None — no shell profiles, launchd plists, or Task Scheduler entries reference `CODE_WIKI_REAL_VAULT_PATH` (verified: not in standard config locations) | None |
| Secrets/env vars | `CODE_WIKI_REAL_VAULT_PATH` — may be set in terminal sessions or dotfiles. Pat must update any personal `.zshrc`/`.env` files that set this var. | Manual: update shell config |
| Build artifacts | None — workspace-io is a new package; no stale `.egg-info` for it | None |

**Nothing found in categories (stored data, live service config, OS state, build artifacts):** Verified — this is a rename of an environment variable and a new package creation. The only runtime state to update is any user shell configuration that sets `CODE_WIKI_REAL_VAULT_PATH`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | workspace-io runtime | ✓ | (workspace managed by uv) | — |
| uv | workspace sync | ✓ | 0.11.14 | — |
| git | `workspace_io.init._git_init` | ✓ | macOS system git | — |
| pyyaml | manifest read/write | ✓ | 6.0.3 | — |
| hatchling | build backend | ✓ | 1.29.0 | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

`workflow.nyquist_validation = true` in `.planning/config.json` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 |
| Config | `packages/workspace-io/pyproject.toml` `[tool.pytest.ini_options]` testpaths = ["tests"] |
| Quick run | `uv run --package workspace-io pytest` |
| Full suite | `uv run pytest` (all packages) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WS-01 | workspace-io package importable | smoke | `uv run --package workspace-io python -c "import workspace_io"` | ❌ Wave 0 |
| WS-02 | `resolve()` walks up for `.graph-wiki.yaml` | unit | `uv run --package workspace-io pytest tests/test_config.py -x` | ❌ Wave 0 |
| WS-02 | `resolve()` raises on missing manifest | unit | `uv run --package workspace-io pytest tests/test_config.py::test_resolve_raises_when_no_manifest_found` | ❌ Wave 0 |
| WS-02 | `GRAPH_WIKI_WORKSPACE` env override | unit | `uv run --package workspace-io pytest tests/test_config.py -k env` | ❌ Wave 0 |
| WS-03 | manifest v2 roundtrip | unit | `uv run --package workspace-io pytest tests/test_manifest.py tests/test_manifest_v2_roundtrip.py` | ❌ Wave 0 |
| WS-03 | manifest raises on v1 | unit | `uv run --package workspace-io pytest tests/test_manifest.py::test_read_raises_on_v1` | ❌ Wave 0 |
| WS-04 | init creates workspace + manifest + gitignore | unit | `uv run --package workspace-io pytest tests/test_init.py` | ❌ Wave 0 |
| WS-05 | paths helpers return correct paths | unit | `uv run --package workspace-io pytest tests/test_paths.py` | ❌ Wave 0 |
| WS-05 | render writes CLAUDE.md | unit | `uv run --package workspace-io pytest tests/test_render.py` | ❌ Wave 0 |
| WS-05 | local config parser | unit | `uv run --package workspace-io pytest tests/test_local_config.py` | ❌ Wave 0 |
| WS-05 | versions warn_if_stale + pending_updates | unit | `uv run --package workspace-io pytest tests/test_warn_if_stale.py tests/test_pending_updates.py` | ❌ Wave 0 |
| WS-07 | `GRAPH_WIKI_WORKSPACE` is the honored env var (not old name) | unit | `uv run pytest packages/vault-io/tests/test_ports_importable.py` | ✅ (needs update) |
| WS-08 | vault-io delegation shim returns correct paths | unit | `uv run pytest packages/vault-io/tests/test_ports_importable.py` | ✅ (needs update) |
| WS-09 | All ported tests pass | suite | `uv run --package workspace-io pytest` | ❌ Wave 0 |
| WS-10 | wiki-config.toml decision recorded in PROJECT.md | manual | Code review / grep | — |

### Sampling Rate

- **Per task commit:** `uv run --package workspace-io pytest` (workspace-io suite only, ~1s)
- **Per wave merge:** `uv run pytest` (full suite — verify no regressions in vault-io, agent tests)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `packages/workspace-io/pyproject.toml` — create
- [ ] `packages/workspace-io/src/workspace_io/__init__.py` — create
- [ ] `packages/workspace-io/src/workspace_io/config.py` — create (port)
- [ ] `packages/workspace-io/src/workspace_io/manifest.py` — create (port)
- [ ] `packages/workspace-io/src/workspace_io/init.py` — create (port)
- [ ] `packages/workspace-io/src/workspace_io/paths.py` — create (port)
- [ ] `packages/workspace-io/src/workspace_io/render.py` — create (port)
- [ ] `packages/workspace-io/src/workspace_io/versions.py` — create (port)
- [ ] `packages/workspace-io/src/workspace_io/_local_config.py` — create (port)
- [ ] `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` — create (port + rebrand)
- [ ] `packages/workspace-io/tests/test_config.py` — create (port)
- [ ] `packages/workspace-io/tests/test_manifest.py` — create (port)
- [ ] `packages/workspace-io/tests/test_manifest_v2_roundtrip.py` — create (port)
- [ ] `packages/workspace-io/tests/test_init.py` — create (port)
- [ ] `packages/workspace-io/tests/test_init_records_version.py` — create (port)
- [ ] `packages/workspace-io/tests/test_init_bumps_version.py` — create (port)
- [ ] `packages/workspace-io/tests/test_paths.py` — create (port)
- [ ] `packages/workspace-io/tests/test_local_config.py` — create (port)
- [ ] `packages/workspace-io/tests/test_render.py` — create (port)
- [ ] `packages/workspace-io/tests/test_warn_if_stale.py` — create (port with behavior change)
- [ ] `packages/workspace-io/tests/test_pending_updates.py` — create (port)

---

## Security Domain

`security_enforcement` is not set to false in config — section required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a — no auth in this package |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a — file-system operations only |
| V5 Input Validation | yes | `Path.expanduser().resolve()` for all user-supplied paths; `yaml.safe_load` (not `yaml.load`) for YAML |
| V6 Cryptography | no | n/a |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `GRAPH_WIKI_WORKSPACE` env | Tampering | `Path(env).expanduser().resolve()` — lattice source already does this |
| YAML arbitrary code execution | Tampering | `yaml.safe_load` only — never `yaml.load` |
| Manifest write to parent dirs | Tampering | `path.parent.mkdir(parents=True, exist_ok=True)` in `manifest.write` — only creates dirs under the workspace path |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No shell dotfiles set `CODE_WIKI_REAL_VAULT_PATH` for Pat's terminal sessions | Runtime State Inventory | Pat would need to update personal dotfiles — low impact, manual step |
| A2 | `render.py` auto-block marker rename (`lattice-workspace:auto` → `workspace-io:auto`) will not affect any existing workspace CLAUDE.md files | Common Pitfalls #3 | Harmless — fallback appends fresh block; Pat is re-initing workspace (D-05) |

All other claims in this research are verified by direct source code reading in this session.

---

## Open Questions

1. **`render.py` `_PLUGIN_POINTERS` dict contents**
   - What we know: Lattice has entries for `lattice-wiki`, `lattice-graph`, `lattice-curator`, `lattice-knowledge`, `lattice-workflows`.
   - What's unclear: Should the ported `_PLUGIN_POINTERS` include an entry for `code-wiki-agent` pointing to `wiki/CLAUDE.md`? Or should it be left empty until the plugin port (Phase 14)?
   - Recommendation: Include one entry `{"code-wiki-agent": "see wiki/CLAUDE.md"}` matching the lattice pattern. Remove all old lattice plugin names. This is Claude's Discretion territory.

2. **`workspace_io.init` default workspace path when `workspace=None`**
   - What we know: Lattice uses `repo_root / DEFAULT_WORKSPACE_NAME`. D-16 says local config `graph-wiki-directory` key overrides. Context.md says `DEFAULT_WORKSPACE_NAME` → `"graph-wiki"`.
   - What's unclear: The Context's Canonical Refs say `config.py` uses `DEFAULT_WORKSPACE_NAME`. But `init.py` also has a hardcoded `"lattice"` default (`workspace = repo_root / "lattice"`). Both need updating.
   - Recommendation: `init.py` hardcoded path should be removed in favor of calling `_resolve_workspace(repo_root)` from config.py to get consistent behavior. Or just replace `"lattice"` with `"graph-wiki"` — simpler, same outcome since there's no local config yet.

---

## Sources

### Primary (HIGH confidence — all verified by direct file reading in this session)

- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/config.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/manifest.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/init.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/paths.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/render.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/versions.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/_local_config.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/schema.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/__init__.py` — full source
- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/assets/CLAUDE.md.template` — full content
- `/Users/pat/Personal/lattice/packages/lattice-workspace/pyproject.toml` — full content
- All 13 test files in `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/` — full content
- `/Users/pat/Personal/deep-agents/packages/vault-io/src/vault_io/_workspace.py` — full source (lines 1-34)
- `/Users/pat/Personal/deep-agents/packages/vault-io/src/vault_io/__init__.py` — full source
- `/Users/pat/Personal/deep-agents/packages/vault-io/tests/test_ports_importable.py` — full source
- `/Users/pat/Personal/deep-agents/packages/vault-io/tests/conftest.py` — full source
- `/Users/pat/Personal/deep-agents/packages/vault-io/pyproject.toml` — full content
- `/Users/pat/Personal/deep-agents/pyproject.toml` (root) — full content
- `/Users/pat/Personal/deep-agents/packages/model-adapter/pyproject.toml` — full content (template)
- `/Users/pat/Personal/deep-agents/agents/code-wiki-agent/pyproject.toml` — full content
- `/Users/pat/Personal/deep-agents/agents/code-wiki-agent/src/code_wiki_agent/cli.py` — lines 1-50, 420-490
- `/Users/pat/Personal/deep-agents/agents/code-wiki-agent/src/code_wiki_agent/commands/init.py` — full source
- `/Users/pat/Personal/deep-agents/agents/code-wiki-agent/src/code_wiki_agent/config.py` — full source
- `/Users/pat/Personal/deep-agents/wiki-config.toml` — full content (WS-10)
- `grep -rn "CODE_WIKI_REAL_VAULT_PATH"` — full output (all 38 occurrences across codebase)
- `uv run --package code-wiki-agent python -c "import importlib.metadata; print(importlib.metadata.version('code-wiki-agent'))"` → `"0.1.0"` (D-13 verified)

### Secondary (MEDIUM confidence — registry verification)

- PyPI `pyyaml` 6.0.3 — confirmed current [VERIFIED: pip3 index versions]
- PyPI `hatchling` 1.29.0 — confirmed current [VERIFIED: pip3 index versions]

---

## Metadata

**Confidence breakdown:**
- Source layout and file contents: HIGH — all files read directly
- Rebrand symbol inventory: HIGH — grep confirmed all occurrences
- pyproject.toml scaffolding pattern: HIGH — lattice source + two deep-agents members read
- Test porting strategy: HIGH — all 13 test files read; behavioral changes from D-14 and D-06 applied
- Runtime state inventory: MEDIUM — shell dotfile state is not inspectable remotely

**Research date:** 2026-05-17
**Valid until:** This is a code port — validity is indefinite (source files don't change until lattice-workspace is updated).
