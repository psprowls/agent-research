---
title: lattice-graph-core — API
category: package
summary: Public API, CLI surface, exit codes, and module layout for lattice-graph-core
updated: 2026-05-11
tokens: 1520
---

# lattice-graph-core — API

## Public API

Modules under `src/graph_io/`:

| Module | Purpose | Key boundary |
|---|---|---|
| `schema.py` | Two-table + metadata schema, `schema_version` constant, migration runner | The wiki spec is the contract; bumps force full rebuild |
| `store.py` | `connect()` / `read_only_connect()` + transaction context manager | All other modules talk to SQLite only through this |
| `upsert.py` | `GraphRecords` → `nodes`/`edges` rows; tuple-key → integer id allocation; `attrs_json` serialization | Tuples in, ids out; parser package never sees ids |
| `packages.py` | Walks repo, reads `pyproject.toml` and `package.json`, synthesizes `kind:package` nodes + `contains` edges | Only manifest-aware module; everything else is language-agnostic |
| `_ignore.py` | Default directory-skip set + `.cgignore` loading + path-component match | Single source of truth for both `packages.refresh` and `update._process_files` |
| `resolve.py` | Post-upsert sweep: joins edges with `dst_path IS NULL` against `nodes` on `(kind, name)`; ambiguous matches fan out with `attrs.resolution = "ambiguous"` | Single pass per update; idempotent |
| `update.py` | `git diff` → per-file (parse + project + upsert) → `packages.refresh(affected_dirs)` → `resolve.sweep()` → write `metadata` rows | Only place that reads git state; only place that mutates `metadata` |
| `queries.py` | One function per query (typed args, dataclass results); read-only connection | All read-only; uses `read_only_connect()` |
| `exit_codes.py` | Stable exit-code constants (from v1) | Script consumers depend on these |
| `cli/main.py` | Argparse top-level dispatch → subcommand modules | Adapters only — query logic in `queries.py`, ops in `update.py` |
| `cli/_format.py` | `render(records, fmt)` — `fmt ∈ {'human', 'json'}`; human formatter is `[json] -> [aligned columns]` | Stderr always plain text regardless of `--json` |
| `cli/ops_update.py`, `ops_status.py`, `ops_dump.py` | Operational subcommand glue | Thin wrappers over `update.py` / `queries.py` |
| `cli/q_find.py`, `q_callers.py`, `q_callees.py`, `q_imports.py`, `q_imported_by.py`, `q_exports.py`, `q_exported_by.py`, `q_describe_package.py`, `q_describe_path.py` | Query subcommand glue | One module per query; thin wrappers |
| `sync_wiki.py` | Wiki-link resolver: load `kind:package` nodes, try three path conventions (packages / apps / domain-scoped glob), upsert `wiki_page` + `documents`, cleanup pass for vanished files, drift-report builder | One-way dependency on the wiki filesystem layout; no import from `lattice-wiki-core` |
| `cli/ops_sync_wiki.py` | CLI dispatch for `cg sync-wiki` | Thin wrapper over `sync_wiki.run()`; same shape as `ops_update.py` |

## CLI

v1 is **CLI-first**; MCP slips to v1.1.

| Operation | Command | Notes |
|---|---|---|
| Update | `cg update [--full]` | Incremental by default (git diff); `--full` rebuilds; single SQLite transaction; honours `.cgignore` at repo root |
| Status | `cg status [--json]` | Cardinalities, `last_indexed_commit`, `schema_version`, staleness; exit `2` when stale |
| Dump | `cg dump` | Raw SQL dump for debugging |
| Sync wiki | `cg sync-wiki` | Walk `kind:package` nodes, try `wiki/packages/<n>/<n>.md`, `wiki/apps/<n>/<n>.md`, `wiki/domains/*/packages/<n>/<n>.md` in order; upsert `wiki_page` nodes + `documents` edges; cleanup pass removes nodes whose file no longer exists; prints **undocumented / newly linked / stale** drift report. See [[wiki/sources/2026-05-lattice-graph-core-documents-edge]]. |
| Find | `cg find <name> [--kind …] [--package …]` | Definitions matching name |
| Callers | `cg callers <name> [--depth N]` | Recursive CTE traversal, depth-bounded |
| Callees | `cg callees <name> [--depth N]` | Recursive CTE traversal, depth-bounded |
| Imports | `cg imports <target>` | What this file/package imports |
| Imported by | `cg imported-by <path> [--symbol …] [--depth N]` | Inverse of `imports`; default depth 1; `--symbol` narrows to importers of a specific name. See [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]]. |
| Exports | `cg exports <path>` | Public symbols a file declares as exported; single-hop. See [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]]. |
| Exported by | `cg exported-by <name>` | Which file owns this exported symbol name. See [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]]. |
| Describe package | `cg describe-package <name>` | Structured digest (files, exports, deps, counts) |
| Describe path | `cg describe-path <path>` | Resolve a path (with or without `:line`) |

> [!info] Deferred to v1.1
> `cg describe-type` (needs `extends`/`inherits` edge kind not in v1 schema), `cg query` (raw-SQL escape hatch; lands with MCP).

### Stable exit codes (from v1 forward)

Script consumers (the SessionStart hook, the `prefer-graph-over-grep` skill, CI checks) depend on these.

| Exit code | Name | Meaning |
|---|---|---|
| 0 | `SUCCESS` | command succeeded |
| 1 | `GENERIC` | unhandled error |
| 2 | `STALE` | `cg status` only — `last_indexed_commit != HEAD` |
| 3 | `NOT_INITIALIZED` | no `code.db` yet — run `cg update --full` |
| 4 | `SCHEMA_MISMATCH` | `metadata.schema_version != core.SCHEMA_VERSION` |
| 5 | `NOT_IN_GIT_REPO` | `cg update` / `status` outside a git repo |
| 6 | `UPDATE_IN_PROGRESS` | concurrent `cg update`; second invocation waits 30 s, then exits 6 |
