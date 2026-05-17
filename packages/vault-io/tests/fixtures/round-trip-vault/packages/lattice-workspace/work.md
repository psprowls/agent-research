---
title: lattice-workspace — Work
category: package
summary: Open gaps and migration TODOs surfaced from reading the source — most notably the `lattice-wiki` migration to use lattice-workspace that hasn't happened yet.
updated: 2026-05-09
tokens: 1021
---

# lattice-workspace — Work

## Bugs

### `resolve()` with `cwd` outside any git repo

Falls back to `cwd.resolve()` as `repo_root` (`config.py:48`), then resolves workspace under that. The behavior is reasonable but means a misconfigured shell could create a `lattice/` directory in the wrong place. No test coverage for this case.

### `init()` with a workspace inside a different repo than `repo_root`

`_is_inside_git_repo(workspace)` walks the workspace's parents — so if the workspace is inside any git repo (not necessarily `repo_root`'s), `git init` is skipped (`init.py:69-79` covers this case). Behavior is technically correct but not documented.

### Symlinked workspaces

`resolve()` calls `.resolve()` on both `workspace` and `repo_root`, which chases symlinks. If a user symlinks `<repo>/lattice` → external dir, `cfg.workspace` is the canonical path, not the link. Probably fine; not documented.

## Tech debt

### `lattice-work` uses sys.path munging

`plugins/lattice-work/scripts/regenerate_work_index.py:24-31` falls back to `sys.path.insert(0, …)` to import `lattice_workspace` when it isn't already importable. This works because the plugin is invoked from a repo where the package source sits at `<repo>/packages/lattice-workspace/src/`. It will not work when the plugin is installed via the marketplace into a consumer repo without the package source. **Fix:** publish `lattice-workspace` to PyPI (or pin a wheel in the plugin's distribution) so this import is reliable.

### Manifest writer is lossy

`manifest.write()` (`manifest.py:28`) only writes the three known keys (`version`, `initialized_at`, `plugins`). If a future field is added to `.lattice.yaml`, manual edits in that field are dropped on the next `init()` call. **Fix:** read-modify-write rather than rebuilding from a fixed schema, OR move to a real YAML parser. The latter conflicts with the stdlib-only constraint.

### `_local_config.read` returns only `dict[str, str]`

The parser doesn't recognize lists, nested keys, or anything beyond flat key-value pairs. If `.lattice.local.yaml` ever needs richer config (per-plugin overrides, lists of paths), the parser is the bottleneck. Same stdlib-only tradeoff applies.

### No `clean()` / uninstall path

There is no inverse of `init()`. Removing a plugin from `plugins:` requires manual edit of `.lattice.yaml`. Whether this matters depends on whether `plugins:` is consumed for behavior (currently it isn't — it's an audit log).

### No `WorkspaceConfig` validation

`LatticeConfig` (`config.py:20`) doesn't validate that the resolved paths exist. Consumers calling `paths.graph_dir(cfg.workspace) / "code.db"` get a path even if the workspace was never `init`-ed. There's no `is_initialized()` helper that checks for the manifest. Currently each consumer reimplements that check (`curator_init.py:14`).

## Features

### Migrate `lattice-wiki` to use `lattice-workspace`

[[wiki/plugins/lattice-wiki/lattice-wiki]] does not yet import `lattice-workspace`. Its skill scripts still take `--wiki <path>` directly. Migration would mean:

- Replacing the manual `--wiki` resolution with `lattice_workspace.config.resolve()`.
- Changing the default vault location to `paths.wiki_dir(workspace)` so the `.lattice.local.yaml` override applies to the wiki too.
- Adding `lattice-wiki` to its own `init()` call (currently test fixtures use it via `init(plugin="lattice-wiki")` but the plugin doesn't run `init` itself).

This is the single biggest consistency gap in the ecosystem today.

## Open questions

- Should `LatticeConfig` carry the resolved manifest data (parsed `.lattice.yaml`) so consumers can query "is plugin X registered?" without a second read?
- Should `paths.py` grow a `vault_dir(workspace)` (the inner `<wiki>/<vault-name>/` Obsidian-vault dir) or is that lattice-wiki's concern entirely?
- Will `.lattice.local.yaml` ever need more than a single key? If so, the parser limitation becomes load-bearing.
- Should `lattice-workspace` be published to PyPI to fix the `sys.path` munging issue in `lattice-work`?
