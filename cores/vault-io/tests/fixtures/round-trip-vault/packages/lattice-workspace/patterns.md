---
title: lattice-workspace — Patterns
category: package
summary: Discovery walks `cwd` upward to `.git`, then `.lattice.local.yaml` overrides the default `<repo>/lattice/` workspace location; path accessors compose subdirectories without I/O; the v2 PyYAML-backed `.lattice.yaml` manifest tracks per-plugin `installed_version` / `applied_version`; init is idempotent, version-recording, and gitignores the local override file.
updated: 2026-05-09
tokens: 2494
---

# lattice-workspace — Patterns

## Key patterns

### Discovery: `cwd` → `LatticeConfig`

`resolve(cwd=None)` is the one entry point every consumer uses. It runs in two phases (`packages/lattice-workspace/src/lattice_workspace/config.py:45`):

1. **Find the repo root.** `_find_repo_root` (`config.py:26`) walks `cwd` and its parents looking for a directory that contains `.git`. The first match wins. If nothing matches, `repo_root` falls back to `cwd.resolve()` — discovery never throws.
2. **Resolve the workspace.** `_resolve_workspace` (`config.py:34`) reads `<repo_root>/.lattice.local.yaml` via `_local_config.read`, looks up `lattice-directory`, and:
   - returns `<repo_root>/lattice` if the key is missing or empty;
   - expands `~`, then resolves relative paths against `repo_root`, absolute paths as-is.

> [!tip] `cwd=None` defaults to `Path.cwd()`
> Callers pass `cwd` only in tests or when discovering a workspace different from the current process's cwd. Production callers (`regenerate_work_index.py`, `curator_init.py`) call `resolve()` with no args.

### Per-developer override via `.lattice.local.yaml`

The `.lattice.local.yaml` file lives at `<repo>/` (alongside `.gitignore`, NOT inside the workspace). It is **always gitignored** — `init()` appends `.lattice.local.yaml` to `<repo>/.gitignore` on every call (idempotent).

Example:

```yaml
# <repo>/.lattice.local.yaml
lattice-directory: ~/work-trees/my-repo/lattice
```

Use cases:

- Multiple worktrees of the same repo sharing one lattice workspace.
- Putting the workspace on a different filesystem (faster SSD, bigger volume).
- CI machines pointing at a pre-warmed workspace cache.

The format is a flat-only YAML subset: top-level `key: value` pairs, comments with `#`, optional surrounding quotes on values. No nesting, no lists, no anchors. The parser (`_local_config.py`) is intentionally tolerant — malformed lines are skipped, not raised. It stays stdlib-only even though the manifest reader now uses PyYAML, since it runs *before* the manifest is loaded.

### `.lattice.yaml` manifest at the workspace root (v2)

The committed manifest at `<workspace>/.lattice.yaml` records every plugin that has ever initialized the workspace, plus per-plugin version state. v0.3.0 schema (`manifest.py`):

```yaml
version: 2
initialized_at: 2026-05-09
plugins:
  - name: lattice-workflows
    installed_version: 0.6.0
    applied_version: 0.6.0
  - name: lattice-wiki
    installed_version: 0.7.0
    applied_version: 0.5.2     # update pending
```

Each plugin's `init` slash-command calls `lattice_workspace.init(repo_root, plugin=<plugin-name>, version=__version__)`. The plugin entry is added to `plugins:` if absent or updated in place if present. Re-running with the same version is a no-op — the manifest is **not rewritten** if nothing changed.

The `version: 2` bump is **lazy and one-way**. v1 manifests on disk (bare-string plugin lists) are coerced to v2 in memory by `manifest.read`'s `_coerce()` step but the file is **not rewritten** until a real mutation lands. A workspace nobody runs against stays in v1 on disk indefinitely — fine, no spurious diffs. See [[wiki/concepts/plugin-versioning-and-update-mechanism]] for the full coercion semantics.

The manifest is the only "is this a lattice workspace?" marker. `lattice-curator`'s `_find_project_root` looks for either `.git` or `.lattice.yaml` to support workspaces detached from a git repo (`plugins/lattice-curator/commands/curator_init.py:14`).

### Per-plugin staleness check at command entry

Every user-facing plugin command should call `warn_if_stale` near the top:

```python
from lattice_workspace import warn_if_stale
from lattice_wiki_core import __version__

cfg = resolve()
if warn_if_stale(cfg.workspace, plugin="lattice-wiki", version=__version__):
    print("⚠ lattice-wiki updates available — run /wiki:init to apply")
```

The function returns `True` only when the workspace's `applied_version` differs from the running plugin's `version`. It records `installed_version=version` as a side effect so subsequent `pending_updates` reads have something to compare against. The plugin owns the banner copy — `lattice-workspace` only signals.

The reference integration is `packages/lattice-wiki-core/src/lattice_wiki_core/_version_check.py`, called from the entry points of `scan_monorepo`, `lint_wiki`, `ingest_source`, `wiki_search`, and `append_log`.

### Path accessors as a stable API surface

`paths.py` exports six pure functions over a `Path`. Consumers:

```python
from lattice_workspace.config import resolve
from lattice_workspace.paths import graph_dir

cfg = resolve()
db = graph_dir(cfg.workspace) / "code.db"
```

The pattern: `resolve()` once at the entry point, pass `cfg.workspace` (or its return value) into accessors. Don't string-concatenate paths in callers.

Subdirectories owned by accessors:

| Accessor | Path | Owner |
|---|---|---|
| `wiki_dir` | `<workspace>/wiki` | [[wiki/plugins/lattice-wiki/lattice-wiki]] |
| `raw_dir` | `<workspace>/raw` | [[wiki/plugins/lattice-wiki/lattice-wiki]] (sources) |
| `work_dir` | `<workspace>/work` | shared: [[wiki/plugins/lattice-wiki/lattice-wiki]] (schema) + [[wiki/plugins/lattice-work/lattice-work]] (lifecycle) |
| `knowledge_dir` | `<workspace>/knowledge` | [[wiki/plugins/lattice-curator/lattice-curator]] |
| `graph_dir` | `<workspace>/.graph` | [[wiki/packages/lattice-graph-core/lattice-graph-core]] |
| `manifest_path` | `<workspace>/.lattice.yaml` | this package |

### Idempotent, version-recording init

`init()` is designed to be run by every plugin's `init` slash-command, in any order, any number of times. v0.3.0 guarantees:

1. **Workspace dir exists** — `mkdir(parents=True, exist_ok=True)`.
2. **Workspace is a git repo** — if not inside one, `git init -q` runs there. Lets users put the workspace outside the consumer repo (e.g., a shared `~/lattice-workspaces/` tree) and still get history. Skipped when the workspace is already inside a git repo.
3. **Manifest reflects all plugins with current versions** — adds the calling plugin if absent (with both `installed_version` and `applied_version` set to `version`); updates an existing entry's versions in place. If both already match, the file is not rewritten — true no-op.
4. **Work-item schema is present** — `schema.write_schema(<workspace>/work/)` writes `.schema.md` if absent (idempotent).
5. **Local-config file is gitignored** — appends `.lattice.local.yaml` to `<repo>/.gitignore` if absent.
6. **Workspace `CLAUDE.md` re-rendered** — `render.py` regenerates the auto-rendered plugin block from the (now-mutated) manifest.

Failures: `git init` raises `RuntimeError` with stderr; missing `version=` raises `TypeError`; filesystem failures propagate as `OSError`; YAML errors propagate as `yaml.YAMLError`.

### Runtime dependency posture

`pyproject.toml` declares `dependencies = ["pyyaml>=6.0"]` (`packages/lattice-workspace/pyproject.toml`). v0.3.0 traded the package's prior stdlib-only posture for parser correctness once the v2 manifest shape (nested dicts inside a list, including `null` values) pushed past what the hand-rolled flat parser could reasonably handle.

> [!info] Trade-off accepted in v0.3.0
> PyYAML adds ~5 MB and a transitive dep to a previously dependency-free package that sits at the bottom of the per-repo plugin dependency graph (every per-repo-data plugin transitively depends on it). Accepted: the parser-correctness win on a foundational package outweighs the install cost; lattice already pulls heavier deps elsewhere (`lattice-curator`, `lattice-wiki-agent`). See [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]].

Practical consequences:

- `manifest.py` uses `yaml.safe_load` / `yaml.safe_dump(sort_keys=False, default_flow_style=False)` exclusively. No `yaml.Loader`, no `!!python/...` tags.
- `_local_config.py` keeps its hand-rolled parser — it runs before the manifest reader and shouldn't pull in PyYAML just to read one key.
- `init.py` shells out to `git` via `subprocess` rather than depending on a Git library — that constraint did not flex in v0.3.0.

### Workspace-as-uv-workspace-member

The package is consumed via uv workspace path-deps. From `packages/lattice-graph-core/pyproject.toml:12,30`:

```toml
dependencies = [
  "lattice-source-parser",
  "lattice-workspace",
]

[tool.uv.sources]
lattice-source-parser = { workspace = true }
lattice-workspace = { workspace = true }
```

This is the canonical way other packages depend on it. Plugins that aren't full uv workspace members (`lattice-work`'s `regenerate_work_index.py`) fall back to `sys.path` munging (`scripts/regenerate_work_index.py:24-31`) — see [[wiki/packages/lattice-workspace/work]].

## Conventions

- Always call `resolve()` once at entry point; pass `cfg.workspace` into accessors. Never string-concatenate subdirectory paths in callers.
- Use `init(repo_root, plugin=<name>, version=__version__)` in every plugin's `init` slash-command — it is idempotent, version-recording, and safe to call repeatedly.
- Call `warn_if_stale(cfg.workspace, plugin=<name>, version=__version__)` at the top of every user-facing plugin command; print a plugin-owned banner if it returns `True`.
- `.lattice.local.yaml` is always gitignored — never commit it; `init()` handles the `.gitignore` entry automatically.
- Related concepts: [[wiki/concepts/per-repo-layout]], [[wiki/concepts/per-repo-data-vs-global-tooling-tier]], [[wiki/concepts/lattice-cross-plugin-contract]], [[wiki/concepts/lattice-vault-terminology]], [[wiki/concepts/plugin-versioning-and-update-mechanism]]
