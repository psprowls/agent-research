---
title: lattice-source-parser — API
category: package
summary: Public API, architecture, and module layout for lattice-source-parser
updated: 2026-05-09
tokens: 612
---

# lattice-source-parser — API

## Public API

```python
from pathlib import Path
from lattice_source_parser import parse_file, parse_bytes, to_graph_records

# 99% case — read bytes, dispatch by extension
tree = parse_file(Path("src/foo.py"), package="my-package")

# Escape hatch — already-loaded source (test harnesses, in-memory editors)
tree = parse_bytes(source_bytes, path=Path("src/foo.py"), language="python", package="my-package")

# Pure projection over the tree
records = to_graph_records(tree)
print(records.nodes)   # list[GraphNode]
print(records.edges)   # list[GraphEdge]
```

`parse_file` is the 99% case (read bytes, dispatch by extension). `parse_bytes` is the escape hatch for callers with already-loaded source — when `language` is None, dispatch is by `path` extension; passing it explicitly overrides extension inference.

Architecture:

```
   bytes/path/pkg ──►  parsers/<lang>.py       ──► SourceTree (rooted at file node)
                       (registry by extension)
                              │
                              ▼
                       projections/graph.py    ──► GraphRecords (nodes + edges)
                              │
                              ▼  (consumer-side, OUT OF PACKAGE SCOPE)
                       lattice-graph      ──► SQLite, MCP, CLI, lifecycle
```

The seam between package and plugin sits between `GraphRecords` and SQLite — the package emits records keyed by `(kind, name, path)` tuples; the plugin allocates integer IDs and performs the upsert.

Key modules under `src/lattice_source_parser/`:

- `parse.py` — `parse_file(path, *, package=None)` / `parse_bytes(source, *, path, language=None, package=None)`
- `tree.py` — `SourceNode`, `Reference`, `Span` dataclasses (the SourceTree model)
- `projections/graph.py` — `to_graph_records(tree) -> GraphRecords`; `GraphNode`, `GraphEdge`, `GraphRecords` dataclasses
- `parsers/_base.py` — `LanguageParser` abstract interface
- `parsers/_config.py` — `LanguageConfig` dataclass (declarative shape for config-driven walkers)
- `parsers/_generic.py` — generic config-driven walker
- `parsers/python.py` — custom walker (Python-specific shapes)
- `parsers/javascript.py` — config-driven via `_generic`
- `parsers/typescript.py` — config-driven; extends javascript config
- `parsers/__init__.py` — `PARSERS` and `EXTENSIONS` registries
- `grammars.py` — `tree-sitter-language-pack` adapter
- `errors.py` — `UnsupportedLanguageError`
