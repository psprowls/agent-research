# source-parser

Tree-sitter-backed Python package that turns source files into a span-bearing
intermediate `SourceTree`, with a graph projection aligned to the
`lattice-graph` SQLite schema.

## Status

v1 covers Python, JavaScript, and TypeScript with a single graph projection.
See `docs/lattice-graph/specs/2026-05-05-source-parser-design.md`
in the parent monorepo for the full design.

## Quick start

```python
from pathlib import Path
from source_parser import parse_file, to_graph_records

tree = parse_file(Path("src/foo.py"), package="my-package")
records = to_graph_records(tree)
print(records.nodes)
print(records.edges)
```

## Tests

```bash
python -m unittest discover
```
