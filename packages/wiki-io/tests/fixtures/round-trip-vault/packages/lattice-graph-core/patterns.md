---
title: lattice-graph-core — Patterns
category: package
summary: Key patterns, conventions, tooling, and dependency notes for lattice-graph-core
updated: 2026-05-11
tokens: 1067
---

# lattice-graph-core — Patterns

## Key patterns

- **SQLite primary store** — nodes/edges/metadata at `<repo>/.lattice/graph/code.db`. Two-table + metadata schema with recursive CTEs for bounded traversal. See [[wiki/concepts/code-graph-schema]] and [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]].
- **`lattice-source-parser` as parsing substrate** — this library does not parse source directly; it calls `parse_file` + `to_graph_records` from [[wiki/packages/lattice-source-parser/lattice-source-parser]] and upserts the resulting `GraphRecords`. The parser package never sees integer ids — tuples in, ids out at the `upsert.py` boundary.
- **Single-writer DB** — only `cg update` writes to `code.db`; all queries open with `mode=ro` URI. SQLite write-lock structurally prevents concurrent writers; second `cg update` waits 30 s then exits `6` (`UPDATE_IN_PROGRESS`). Per [[wiki/adrs/0008-single-writer-code-db]].
- **Single SQLite transaction per update** — `cg update` wraps `git diff` → per-file (parse + project + upsert) → `packages.refresh` → `resolve.sweep` → metadata writes inside one `BEGIN…COMMIT`. Either the whole update lands or none of it; idempotent (re-running on a clean tree is a no-op).
- **Committed state only** — `cg update` indexes HEAD, not the working tree. `last_indexed_commit` would be meaningless if the index included uncommitted state, and it matches the parser's expectations (one file → one commit-stable tree). SessionStart staleness banner triggers when HEAD differs from `last_indexed_commit` and is silent about uncommitted changes by design.
- **Manifest scanning** — `packages.py` scans `pyproject.toml` and `package.json` to synthesize `kind:package` nodes and `contains` edges, making the graph aware of logical package boundaries in addition to file/symbol nodes.
- **Directory-skip model** — both `update.py` (file scanner) and `packages.py` (manifest scanner) consult a single skip set from `_ignore.py`. The default set covers VCS, build, and virtualenv directories; users extend it with `.cgignore` at the repo root. Match semantics: any path component equal to an entry is skipped. See `packages/lattice-graph-core/README.md` for the user-facing description.
- **Cross-file edge resolution** — `resolve.py` runs a post-upsert sweep to wire up unresolved edges (`dst_path IS NULL`) by joining on `(kind, name)` against `nodes`; ambiguous matches fan out with `attrs.resolution = "ambiguous"`. Idempotent; incremental updates re-sweep over the affected file set.
- **Stable exit codes** — `exit_codes.py` declares all exit codes from v1 forward; script consumers can rely on these. See [[wiki/packages/lattice-graph-core/api]] for the full table.
- **CLI as adapter** — `cli/` is a thin adapter over the query and operational modules. Query logic lives in `queries.py`; ops in `update.py`. A future MCP adapter shares the same library, so the boundary stabilizes by use before MCP lands. Per [[wiki/adrs/0007-cli-first-code-graph]].
- **Output discipline** — errors always go to stderr in plain text, regardless of `--json`. Human and JSON outputs share a common record-shape under the hood; the human formatter is `[json] -> [aligned columns]`. No two source-of-truth shapes.
- **Pytest from day one** — three layers: per-module unit tests (in-memory SQLite), integration tests against tiny fixture repos with real `.git` directories under `fixtures/repos/`, CLI tests via `subprocess.run([sys.executable, '-m', 'graph_io.cli.main', ...])`. Snapshots only for human-format CLI output and select large query results; updated only via explicit `--update-snapshots` flag.

## Conventions

- **uv workspace member** under the repo-root workspace coordinator (single `uv.lock`, `uv sync` from repo root). Per [[wiki/adrs/0009-uv-ruff-python-tooling]].
- **ruff** for lint and format (`E`, `F`, `I` rule sets; `line-length = 120`); configured in the root `pyproject.toml` with no per-package overrides.
- **pytest** uniform across all packages; testpaths declared per-package.
- **`hatchling`** build backend, consistent with all other workspace packages.
- Dev dependencies (`pytest`, `pytest-snapshot`) are declared in the package's `pyproject.toml` under `[project.optional-dependencies]` and are not promoted to the workspace root.
