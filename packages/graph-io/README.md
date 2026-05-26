# graph-io

Code-graph backend for graph-wiki. Owns:

- SQLite schema + store at `<paths.graph_dir(workspace)>/code.db` (see `workspace_io.paths` for workspace-mode-aware resolution)
- Upsert from `source-parser`'s `GraphRecords`
- Manifest scanning (`pyproject.toml`, `package.json`) → `kind:package` nodes
- Cross-file edge resolution sweep
- Read-only query layer (`find`, `callers`, `callees`, `imports`, `describe_package`, `describe_path`)
- The `cg` CLI

The Claude Code plugin shell lives separately at `plugins/graph-wiki/`.

## Exit codes

Stable from v1 forward — script consumers can rely on these:

| Code | Name | Meaning |
|---|---|---|
| 0 | `SUCCESS` | command succeeded |
| 1 | `GENERIC` | unhandled error or "not found" for `describe-*` |
| 2 | `STALE` | `cg status` only — `last_indexed_commit != HEAD` |
| 3 | `NOT_INITIALIZED` | no `code.db` yet — run `cg update --full` |
| 4 | `SCHEMA_MISMATCH` | **reserved** — declared in `exit_codes.py`, not yet enforced. Wires up when v2 schema lands. |
| 5 | `NOT_IN_GIT_REPO` | `cg update`/`status` outside a git repo |
| 6 | `UPDATE_IN_PROGRESS` | **reserved** — declared in `exit_codes.py`, not yet enforced. Concurrent `cg update` invocations currently surface as `GENERIC` (1) due to SQLite write-lock contention. |

## Ignoring directories

The scanner skips a built-in set of directories by default:

`.git`, `node_modules`, `.worktrees`, `.venv`, `venv`, `dist`, `build`, `__pycache__`, `.tox`, `.nox`

To skip additional directories, create a `.cgignore` file at the repo root:

```
# example .cgignore
generated
vendor
fixtures
```

One directory name per line; `#` starts a comment; blank lines are ignored. A name matches any path component (e.g. `generated` skips both `generated/foo.py` and `packages/x/generated/foo.py`). Anchored / glob patterns are not supported.
