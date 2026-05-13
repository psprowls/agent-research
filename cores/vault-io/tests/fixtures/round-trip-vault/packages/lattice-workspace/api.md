---
title: lattice-workspace — API
category: package
summary: Public surface of `lattice-workspace` v0.3.0 — `LatticeConfig`, `resolve()`, `init(version=…)`, six path accessors, the v2 PyYAML-backed `.lattice.yaml` manifest reader/writer, the `warn_if_stale` / `pending_updates` versioning API, and the embedded work-item schema.
updated: 2026-05-09
tokens: 3083
---

# lattice-workspace — API

## Public API

### Top-level surface

`from lattice_workspace import …` re-exports five names (`packages/lattice-workspace/src/lattice_workspace/__init__.py`):

| Name | Kind | Source |
|---|---|---|
| `LatticeConfig` | frozen dataclass | `config.py:20` |
| `resolve` | function | `config.py:45` |
| `init` | function | `init.py` |
| `warn_if_stale` | function | `versions.py` |
| `PendingUpdate` | frozen dataclass | `versions.py` |

`pending_updates` is also exposed (`from lattice_workspace import pending_updates`). Submodules (`paths`, `manifest`, `schema`, `versions`, `render`, `_local_config`) are imported directly: `from lattice_workspace.paths import graph_dir`. `_local_config` is internal — leading underscore.

### `LatticeConfig`

```python
@dataclass(frozen=True)
class LatticeConfig:
    workspace: Path
    repo_root: Path
```

`packages/lattice-workspace/src/lattice_workspace/config.py:20`. Both fields are absolute `Path`s. Frozen, so safe to share across threads/callers.

### `resolve(cwd=None) -> LatticeConfig`

`packages/lattice-workspace/src/lattice_workspace/config.py:45`.

Discovery sequence:

1. `cwd` defaults to `Path.cwd()` if not passed.
2. `_find_repo_root(cwd)` walks `cwd` and its parents looking for a directory containing `.git` (`config.py:26`). If none found, `repo_root` falls back to `cwd.resolve()`.
3. `_resolve_workspace(repo_root)` reads `<repo_root>/.lattice.local.yaml` and looks for the `lattice-directory` key (`config.py:34`).
   - Empty/missing → `<repo_root>/lattice` (the `DEFAULT_WORKSPACE_NAME` constant, `config.py:17`).
   - Absolute path → used as-is (after `~` expansion).
   - Relative path → resolved against `repo_root`.
4. Returns `LatticeConfig(workspace=<resolved>, repo_root=<repo_root>)`.

Both paths are returned `.resolve()`-d (canonical, symlinks chased).

### `init(repo_root, *, plugin, version, workspace=None) -> None`

`packages/lattice-workspace/src/lattice_workspace/init.py`. Idempotent bootstrap. `version=` is **required** as of v0.3.0 — see [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] and [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]].

| Arg | Required | Notes |
|---|---|---|
| `repo_root` | yes | Path to the consumer repo. |
| `plugin` | yes (kw-only) | Plugin name to record in `.lattice.yaml`'s `plugins:` list. Matches `plugin.json` `name`. |
| `version` | yes (kw-only) | Plugin version string (e.g. `__version__`). Recorded as both `installed_version` and `applied_version` for `plugin`. |
| `workspace` | no (kw-only) | Override workspace path. Defaults to `repo_root / "lattice"`. |

Steps:

1. Resolve `repo_root` and `workspace`.
2. `workspace.mkdir(parents=True, exist_ok=True)`.
3. If `workspace` is **not** inside any git repo, run `git init -q <workspace>`. Handles the case of an external workspace outside the consumer's repo.
4. Read existing `.lattice.yaml` if present, otherwise seed `{version: 2, initialized_at: <today>, plugins: []}`. v1 manifests are coerced to v2 in memory (see `manifest.read` below).
5. Add or update `plugin`'s entry in `plugins[]`. Sets both `installed_version=version` and `applied_version=version`. Idempotent: if the entry already matches, the file is **not** rewritten.
6. Write `<workspace>/work/.schema.md` (idempotent — does nothing if the file exists).
7. Append `.lattice.local.yaml` to `<repo_root>/.gitignore`, creating the file if absent. No-op if already present.
8. Re-render `<workspace>/CLAUDE.md` from `assets/CLAUDE.md.template` via `render.py` so the auto-rendered plugin block stays in sync.

The function raises `RuntimeError` if `git init` fails. A missing `version=` raises `TypeError` (the breaking API change in v0.3.0; external callers must update).

### `warn_if_stale(workspace, *, plugin, version) -> bool`

`packages/lattice-workspace/src/lattice_workspace/versions.py`. Top-of-command staleness check that *also writes* `installed_version` on mismatch.

| Arg | Required | Notes |
|---|---|---|
| `workspace` | yes | Workspace path (typically `resolve().workspace`). |
| `plugin` | yes (kw-only) | Plugin slug. |
| `version` | yes (kw-only) | The plugin's currently-installed version (e.g. `__version__`). |

Behavior:

| Manifest state | Returns | Writes |
|---|---|---|
| No entry for `plugin` | `False` | nothing |
| `applied_version is None` (v1-coerced) | `False` | nothing |
| `applied_version == version` | `False` | nothing |
| `applied_version != version` | `True` | sets `installed_version=version` (leaves `applied_version` untouched) |

Caller (the plugin) is responsible for printing a banner when this returns `True`. `warn_if_stale` only signals — see [[wiki/concepts/plugin-versioning-and-update-mechanism]] for the rationale (banner-not-auto-apply).

### `pending_updates(workspace) -> list[PendingUpdate]`

`packages/lattice-workspace/src/lattice_workspace/versions.py`. Pure read — never mutates the manifest. Returns one `PendingUpdate` per plugin where `installed_version is not None and installed_version != applied_version`. v1-coerced entries (both versions `None`) are excluded — they only surface once a plugin run records an `installed_version`.

```python
@dataclass(frozen=True)
class PendingUpdate:
    plugin: str
    applied_version: str | None
    installed_version: str
```

### `paths` — pure path accessors

All six functions are pure path composition; no filesystem I/O. Source: `packages/lattice-workspace/src/lattice_workspace/paths.py`.

| Function | Returns | Line |
|---|---|---|
| `manifest_path(workspace)` | `<workspace>/.lattice.yaml` | `paths.py:11` |
| `wiki_dir(workspace)` | `<workspace>/wiki` | `paths.py:15` |
| `raw_dir(workspace)` | `<workspace>/raw` | `paths.py:19` |
| `work_dir(workspace)` | `<workspace>/work` | `paths.py:23` |
| `knowledge_dir(workspace)` | `<workspace>/knowledge` | `paths.py:27` |
| `graph_dir(workspace)` | `<workspace>/.graph` | `paths.py:31` |

Callers obtain `workspace` from `resolve().workspace` and pass it to these accessors.

> [!note] `graph_dir` lives **inside** the workspace
> `<workspace>/.graph/` — with the default workspace this is `<repo>/lattice/.graph/`. [[wiki/concepts/per-repo-layout]] describes the single-root layout.

### `manifest` — `.lattice.yaml` reader/writer

`packages/lattice-workspace/src/lattice_workspace/manifest.py`. PyYAML-backed since v0.3.0 (`yaml.safe_load` / `yaml.safe_dump(sort_keys=False, default_flow_style=False)` exclusively — no `yaml.Loader`, no `!!python/...` tags).

#### Schema (v2)

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

| Field | Meaning |
|---|---|
| `name` | Plugin slug — matches `plugin.json` `name`. |
| `installed_version` | What the plugin reported about itself the last time any of its commands ran here. May be `null` for v1-coerced entries until the plugin runs. |
| `applied_version` | The last version whose update path completed successfully against this workspace. May be `null` for v1-coerced entries. |

Three recognized keys at the top level. Anything else is silently dropped on write.

#### `read(path) -> dict`

Returns `{"version": 2, "initialized_at": str, "plugins": list[dict]}`. Returns `{}` when the file doesn't exist.

The internal `_coerce()` step runs on every read:

- v1 input (top-level `version: 1` or missing, plugins as bare strings): each `"foo"` becomes `{"name": "foo", "installed_version": None, "applied_version": None}`. In-memory `version` is promoted to `2`.
- v2 input: pass-through.

The disk file is **not** rewritten by coercion alone. Disk rewrite happens only when a real mutation lands (`init` bumps versions, `warn_if_stale` writes a new `installed_version`).

PyYAML parses bare ISO dates (e.g. `2026-05-09`) as `datetime.date`; `read()` normalizes `initialized_at` back to `str` so callers see a stable type.

#### `write(path, data) -> None`

Creates parent dirs. Writes the three top-level keys via `yaml.safe_dump(data, sort_keys=False, default_flow_style=False)` — preserves key order and block style for stable diffs.

### `_local_config` — `.lattice.local.yaml` reader

`packages/lattice-workspace/src/lattice_workspace/_local_config.py`. Internal; only `config.py` calls it.

`read(path) -> dict[str, str]` parses flat top-level `key: value` pairs. Behavior:

- Returns `{}` if the file is absent.
- Skips blank lines and `#` comment lines.
- Drops malformed lines (no `:`) silently.
- Strips inline `# …` comments from values **outside** quotes.
- Strips matching surrounding single/double quotes from values.
- All values are `str` — no booleans/numbers/lists.

Recognized keys (consumed by `config.py`):

| Key | Type | Effect |
|---|---|---|
| `lattice-directory` | str | Workspace path. Empty → `<repo>/lattice`. Relative → `<repo>/<value>`. Absolute → used as-is. `~` expanded. |

> [!note] Why a separate hand-rolled parser
> `_local_config` is intentionally tolerant and stdlib-only — it runs *before* the manifest reader (which now depends on PyYAML) is called, and its inputs (per-developer overrides, gitignored) shouldn't pull in a parser dep just to read one key.

### `schema` — embedded work-item schema

`packages/lattice-workspace/src/lattice_workspace/schema.py`. The module embeds the canonical work-item `.schema.md` as a string constant.

`write_schema(work_dir) -> None` writes `<work_dir>/.schema.md`. Idempotent — does nothing if the file already exists. Creates `work_dir` if absent.

The schema describes the frontmatter contract for `<workspace>/work/*.md` files, shared with [[wiki/plugins/lattice-work/lattice-work]] per [[wiki/concepts/lattice-work-namespace-schema]].

### `render` — workspace `CLAUDE.md` rendering

`packages/lattice-workspace/src/lattice_workspace/render.py`. Renders `<workspace>/CLAUDE.md` from `assets/CLAUDE.md.template` and the `.lattice.yaml` manifest. Iterates plugin entries as dicts (`entry["name"]`) — the v0.3.0 update needed to handle the v2 schema. The rendered block surfaces only plugin names, not version info (a future enhancement; see [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]] follow-ups).

Called by `init()` after every manifest mutation so the rendered block stays in sync.

### Constants

| Name | Value | Source |
|---|---|---|
| `LOCAL_CONFIG_FILENAME` | `".lattice.local.yaml"` | `config.py:15` |
| `LATTICE_DIRECTORY_KEY` | `"lattice-directory"` | `config.py:16` |
| `DEFAULT_WORKSPACE_NAME` | `"lattice"` | `config.py:17` |
| `_GITIGNORE_ENTRY` | `".lattice.local.yaml"` | `init.py` |

### Exit codes / errors

- `init()` raises `TypeError` if `version=` is omitted.
- `init()` raises `RuntimeError` if `git init` fails, surfacing the captured stderr.
- All other functions either succeed or propagate stdlib exceptions (`OSError`, `yaml.YAMLError`, etc.). No custom exception hierarchy.

## CLI

`python -m lattice_workspace.config` prints the resolved workspace path and exits 0 (`config.py:53`). Useful in shell scripts that need the workspace path without writing Python.

## Sources

- [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] — design spec for the v0.3.0 surface (`init(version=)`, `warn_if_stale`, `pending_updates`, v2 manifest, PyYAML).
