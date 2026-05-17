---
title: SourceTree model (parser intermediate)
category: concept
summary: Span-bearing intermediate produced by lattice-source-parser — a single domain model (SourceNode + Reference + Span) with all consumer outputs implemented as pure projections on top of it.
tags:
  - parsing
  - tree-sitter
  - lattice-source-parser
  - code-graph
  - architecture
updated: 2026-05-07
tokens: 1581
---

# SourceTree model (parser intermediate)

## Definition
The single domain model used inside [[wiki/packages/lattice-source-parser/lattice-source-parser]]: a tree of `SourceNode` objects rooted at a `kind='file'` node, each carrying a byte/line/column `Span`, plus per-node `Reference` lists for outgoing calls / imports / exports. All consumer-facing outputs (graph records, future chunks, future type-aware projections) are pure functions on top of this tree — the tree itself never reshapes for a projection.

## Motivation

One parsing pass should serve many consumers — graph upsert, chunking, RAG indexing, evals, ad-hoc queries. The classic mistake is to specialize the parser per consumer, giving each its own tree shape, then duplicating work or re-parsing. The SourceTree fixes this by being the *only* domain model: it is rich enough that any sensible projection can read it, narrow enough that adding a new consumer never requires changing the tree.

## Shape

```python
# packages/lattice-source-parser/src/lattice_source_parser/tree.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class Span:
    start_byte: int
    end_byte: int
    start_line: int        # 1-indexed
    end_line: int
    start_col: int         # 0-indexed
    end_col: int

@dataclass(frozen=True)
class Reference:
    kind: str              # 'call' | 'import' | 'export'
    target_name: str       # raw name as written in source
    target_module: str | None    # resolved module/file/package, if statically determinable
    site: Span             # where the reference appears in source
    attrs: dict[str, Any] = field(default_factory=dict)

@dataclass
class SourceNode:
    kind: str              # 'file' | 'class' | 'function' | 'method'
    name: str | None       # symbol name; None for files (file path is in `path`)
    span: Span
    path: Path             # file path; format (absolute or relative) is preserved as caller passes it
    language: str          # 'python' | 'javascript' | 'typescript'
    package: str | None    # opaque label set by caller; may be None
    attrs: dict[str, Any] = field(default_factory=dict)
    children: list["SourceNode"] = field(default_factory=list)  # contains-edges in graph projection
    refs: list[Reference] = field(default_factory=list)         # outgoing calls/imports/exports
```

## Key choices

1. **Hierarchy lives in `children`; cross-cutting refs live in `refs`.** Containment (file contains class, class contains method) is the tree spine; calls/imports/exports live as flat lists on the node that *sources* them. A function node carries its own outgoing calls — no whole-tree walk needed to enumerate them.

2. **Symbol kind is a string tag, not a subclass.** `kind` is a `str`. Adding new kinds (`block` for chunking, `namespace` for C# v1.1) is additive — no class hierarchy refactor, no isinstance ladders.

3. **No source text on the node.** Every node carries `span` + `path`. Consumers that need text read bytes once at the top of a file and slice by span. Stops trees from carrying redundant, refresh-prone copies of source.

4. **`package` is opaque.** The parser never reads `package.json`, `pyproject.toml`, or any manifest; the caller supplies the package label per file. Synthesizing graph package nodes is the consumer's job.

5. **`attrs` is the per-language extensibility seam.** Common fields (`is_exported`, `is_async`, `language`) appear when meaningful; language-specific fields (`type_params`, `decorators`, `is_default_export`) appear when meaningful and absent otherwise. Consumers do `node.attrs.get("type_params", [])` rather than assuming universal presence.

6. **No `package` node kind in the source-tree.** Each `parse()` call returns a tree rooted at one `kind='file'` node. Aggregating files into packages and emitting `kind='package'` nodes happens in the consumer's upsert layer.

## Projections on top

Projections are pure functions `SourceNode -> SomeOutput`. The tree never reshapes for them.

| Projection | Status | Output |
|---|---|---|
| `to_graph_records(tree)` | v1 (`projections/graph.py`) | `GraphRecords(nodes, edges)` aligned to the [[wiki/concepts/code-graph-schema]] |
| Chunking | deferred | token-counted source chunks for RAG / LLM context |
| Type-aware projection | deferred | nodes annotated with mypy / pyright type info |

The deferred projections do not require changes to the SourceTree — they consume it as-is.

## What v1 captures

- Top-level functions, classes; methods inside classes.
- Constructors (`__init__`, `constructor`) as `kind='method'` with `attrs.is_constructor = True` (not a separate kind).
- Nested functions/classes as `children` of the enclosing function — `kind` stays `'function'` / `'class'`; nesting is implied by tree position.
- Imports as `Reference(kind='import')` on the file node, one per imported binding.
- Exports as `Reference(kind='export')` on the file node, plus `attrs.is_exported` on the symbol nodes themselves.
- Calls as `Reference(kind='call')` on the function/method node that issues them.

## What v1 does NOT capture

- Block-level structure for chunking — added later as new `kind` values.
- Comments and standalone docstring nodes (docstrings reachable via `function.attrs.get('docstring')` if a parser cares to extract).
- Cross-file resolution — best-effort within one file; consumer joins unresolved edges across the global node table.
- Type-checker output.

## Tolerant parsing

Tree-sitter `ERROR` nodes do not abort. The walker emits a partial tree and records offending spans in `file_node.attrs['parse_errors']`. Consumers can choose to ignore, surface, or fail on parse errors.

## Used in

- [[wiki/packages/lattice-source-parser/lattice-source-parser]] — produced by `parse_file()` / `parse_bytes()`; consumed by `to_graph_records()`
- [[wiki/packages/lattice-graph-core/lattice-graph-core]] — primary downstream consumer (via `to_graph_records`)

## Related patterns

- [[wiki/concepts/code-graph-schema]] — the SQLite schema that `to_graph_records()` targets

## Decisions

- [[wiki/adrs/0005-sourcetree-sole-domain-model]]

## Open questions / gotchas

- Adding a `block` kind for chunking will be the first real test of the additivity claim — when chunking lands, verify no existing projections need changes.
