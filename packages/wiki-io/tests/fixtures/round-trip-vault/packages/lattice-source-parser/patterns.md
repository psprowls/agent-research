---
title: lattice-source-parser — Patterns
category: package
summary: Key patterns, v1 scope, non-goals, concern split, tooling, and dependency notes for lattice-source-parser
updated: 2026-05-09
tokens: 1334
---

# lattice-source-parser — Patterns

## Key patterns

- **SourceTree as sole domain model** — two dataclasses (`SourceNode`, `Reference`) plus `Span`. Symbol kind is a string tag; per-language detail lives in `attrs` dicts. All consumer outputs are pure projections on top of the tree. See [[wiki/concepts/source-tree-model]].
- **[[wiki/concepts/language-parser-abstraction|LanguageParser abstraction]]** — each language is a self-contained module behind `_base.LanguageParser`. The registry (`PARSERS` / `EXTENSIONS`) lives in `parsers/__init__.py`; dispatch is by file extension or explicit `language=` arg.
- **Two implementation strategies, same output shape** — config-driven via `LanguageConfig` + `_generic.py` for C-family languages (JavaScript, TypeScript, future Java/Kotlin/Scala/C#); custom walkers for outliers (Python). Both emit identical `SourceNode` shape.
- **Span-bearing nodes** — every node carries `Span` (byte offsets + 1-indexed lines + 0-indexed columns). No source text on nodes; consumers slice by span.
- **Pure-function projection layer** — `projections/graph.py` converts `SourceTree` into `GraphRecords` aligned with the SQLite schema (see [[wiki/concepts/code-graph-schema]]). Identity is `(kind, name, path)` tuples; integer IDs are allocated by the consumer at upsert time. No I/O.
- **Tolerant parsing** — tree-sitter `ERROR` nodes do not abort; partial tree is emitted with offending spans recorded in `file_node.attrs['parse_errors']`.
- **Binary tree-sitter dep, isolated** — `tree-sitter` + `tree-sitter-language-pack` are binary wheels. Stdlib break is intentional and confined to this package and `lattice-graph-core`.
- **uv workspace member** — this package is a member of the repo-root uv workspace (sole `uv.lock` lives at the repo root). Lint/format via ruff with root-only config; tests via pytest; Python 3.12 pinned via root `.python-version`.

## Conventions

### v1 language scope

| Language | File extensions | Implementation strategy |
|---|---|---|
| Python | `.py` | Custom walker (`parsers/python.py`) — handles `from X import Y as Z`, decorators, `__all__`, `_name`/`__name` visibility |
| JavaScript | `.js`, `.jsx`, `.mjs`, `.cjs` | Config-driven via `_generic` |
| TypeScript | `.ts`, `.tsx` | Config-driven; extends JavaScript config (TS-only node types, `type_params`, `is_type_only` imports) |

Three languages at v1 stress-tests the abstraction against real cross-language divergence — single-language abstractions tend to leak the language's assumptions. C# committed for code-graph v1.1, **not** v1.

### Non-goals (v1)

Each item below was deliberately left out of v1:

- **Chunking, token counting, LLM-context projections.** Deferred — lands when a real chunking consumer appears (RAG indexer, eval harness).
- **Cross-file resolution as a built-in package feature.** Each `parse_file` sees one file; the plugin runs cross-file resolution as a post-pass with the global view.
- **SQLite, MCP, or any storage / transport concern.** The package emits records; consumers persist them however they like.
- **Manifest scanning** (`package.json`, `pyproject.toml`, `Cargo.toml`). The `package` label on each `SourceNode` is opaque — caller-supplied. Synthesizing `kind: package` graph nodes is the consumer's job.
- **Parallel parsing, file-level caching, performance benchmarks.** Plugin update is git-diff-driven (<100 files typical); per-file parallelism doesn't pay back yet.
- **Type-checker adapters** (mypy, pyright). Out of scope for the parser package.
- **C# parser.** Committed for code-graph v1.1, not v1.

### Concern split (package vs. lattice-graph plugin)

| Concern | Owner | Why |
|---|---|---|
| Tree-sitter setup, AST walk, SourceTree | package | Reusable; no SQLite or plugin context required |
| `to_graph_records()` projection | package | Schema is a stable contract; reusable |
| SQLite schema + migrations | plugin | Specific to graph storage |
| ID allocation, upsert, transactions | plugin | Storage layer concern |
| Manifest scanning → package nodes | plugin | Different file types, ecosystem-specific |
| Cross-file resolution sweep (v1) | plugin | Has the global view |
| Git-diff incremental update | plugin | Plugin owns the lifecycle |
| MCP server, CLI, query tools | plugin | Adapters to the storage layer |

### Distribution

During v1 development the plugin path-deps the package:

```toml
# plugins/lattice-graph/pyproject.toml
[tool.hatch.metadata]
allow-direct-references = true

[project]
dependencies = [
  "lattice-source-parser @ {root:uri}/../../packages/lattice-source-parser",
]
```

PyPI publishing is **not** part of v1. Decision deferred until the API stabilizes post-v1.

### Testing

Three test layers:

1. **Per-language fixture-driven parser tests** — fixtures at `fixtures/<lang>/<feature>.<ext>` paired with `<feature>.expected.json`. Test loader walks fixtures and asserts trees match.
2. **Projection tests** — `<feature>.graph.expected.json` fixtures asserting `to_graph_records(tree)` produces the expected `GraphRecords`.
3. **Negative / boundary tests** — hand-written test cases for parse-error tolerance, unknown extensions (`UnsupportedLanguageError`), empty files, and v1-not-handled limits documented as tests (e.g. polymorphic call resolution capped at the interface method).

Snapshot updates are explicit (`tests/update_fixtures.py`, parked for v1) — the test runner never auto-updates. Avoids the classic "snapshot tests that always pass because they re-snapshot" failure mode.
