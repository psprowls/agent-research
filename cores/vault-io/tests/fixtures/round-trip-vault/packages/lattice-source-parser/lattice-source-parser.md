---
title: lattice-source-parser
category: package
summary: Tree-sitter-backed Python library that parses source files into a span-bearing SourceTree and projects them into GraphRecords aligned with the lattice-graph SQLite schema.
status: active
package_path: packages/lattice-source-parser
package_type: library
domain:
language: Python
depends_on: []
tags: [python, tree-sitter, parsing, code-graph]
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 2778
---

# lattice-source-parser

## Purpose

`lattice-source-parser` is a standalone Python library that uses `tree-sitter` and `tree-sitter-language-pack` to parse Python, JavaScript, and TypeScript source files into a span-bearing `SourceTree` — a lightweight intermediate representation composed of `SourceNode`, `Reference`, and `Span` dataclasses. A second-stage projection (`to_graph_records`) maps that tree onto `GraphNode` / `GraphEdge` / `GraphRecords` values aligned to the `lattice-graph` SQLite schema, producing `contains`, `calls`, `imports`, and `exports` edges ready for upsert. The package exists as a sibling library (not a plugin) so that any consumer — chunkers, indexers, RAG pipelines, evals, or future language-aware tools — can `pip install lattice-source-parser` and get tree-sitter-backed parsing without pulling in SQLite, MCP, or manifest-scanning logic. Those concerns live in [[wiki/packages/lattice-graph-core/lattice-graph-core]]. Three language parsers ship at v1: a custom hand-written walker for Python and config-driven `generic_walk` parsers for JavaScript and TypeScript. Cross-file edge resolution and git-diff incremental updates are explicitly out of scope.

## File map - lattice-source-parser

Root of the `lattice-source-parser` Python package: build manifest, developer docs, and pytest configuration.

- `CLAUDE.md` — Developer guide covering package boundaries, test instructions, and the stdlib-break rationale
- `conftest.py` — Adds `tests/` to `sys.path` so `_fixture_loader` is importable across all test modules
- `pyproject.toml` — Hatchling build config; declares `tree-sitter` and `tree-sitter-language-pack` runtime deps and a `test` extra for pytest
- `README.md` — Quick-start README with installation, API usage example, and test command

### lattice-source-parser/fixtures/

Per-language source fixtures paired with expected JSON outputs used by the parametrized parser tests.

#### lattice-source-parser/fixtures/javascript/

JavaScript source fixtures and expected parse / graph outputs covering ES modules, CommonJS, classes, imports, and re-exports.

- `basic_function.expected.json` — Expected parser output for basic_function.js
- `basic_function.graph.expected.json` — Expected graph projection output for basic_function.js
- `basic_function.js` — Source fixture — simple top-level JavaScript function definition
- `cjs_module.cjs` — Source fixture — CommonJS module using `require` and `module.exports`
- `cjs_module.expected.json` — Expected parser output for cjs_module.cjs
- `class_with_methods.expected.json` — Expected parser output for class_with_methods.js
- `class_with_methods.js` — Source fixture — JavaScript class with multiple method definitions
- `default_export.expected.json` — Expected parser output for default_export.js
- `default_export.js` — Source fixture — module using a default export declaration
- `esm_module.expected.json` — Expected parser output for esm_module.mjs
- `esm_module.graph.expected.json` — Expected graph projection output for esm_module.mjs
- `esm_module.mjs` — Source fixture — ES module with named exports
- `import_variants.expected.json` — Expected parser output for import_variants.js
- `import_variants.js` — Source fixture — module exercising named, namespace, and default import forms
- `re_export.expected.json` — Expected parser output for re_export.js
- `re_export.js` — Source fixture — module that re-exports names from another module
- `re_export_source.expected.json` — Expected parser output for re_export_source.js
- `re_export_source.js` — Source fixture — module whose exports are re-exported by re_export.js

#### lattice-source-parser/fixtures/python/

Python source fixtures and expected parse / graph outputs covering functions, classes, decorators, imports, and async methods.

- `async_methods.expected.json` — Expected parser output for async_methods.py
- `async_methods.py` — Source fixture — class with async method definitions
- `basic_function.expected.json` — Expected parser output for basic_function.py
- `basic_function.graph.expected.json` — Expected graph projection output for basic_function.py
- `basic_function.py` — Source fixture — basic top-level Python function definition
- `class_with_decorator.expected.json` — Expected parser output for class_with_decorator.py
- `class_with_decorator.graph.expected.json` — Expected graph projection output for class_with_decorator.py
- `class_with_decorator.py` — Source fixture — class and methods annotated with decorators
- `class_with_init.expected.json` — Expected parser output for class_with_init.py
- `class_with_init.py` — Source fixture — class with an `__init__` constructor method
- `import_variants.expected.json` — Expected parser output for import_variants.py
- `import_variants.py` — Source fixture — module exercising `import`, `from … import`, and aliased import forms
- `module_init.expected.json` — Expected parser output for module_init.py
- `module_init.py` — Source fixture — `__init__.py`-style module with `__all__` exports
- `multiple_inheritance.expected.json` — Expected parser output for multiple_inheritance.py
- `multiple_inheritance.py` — Source fixture — class with multiple base classes

#### lattice-source-parser/fixtures/typescript/

TypeScript source fixtures and expected parse / graph outputs covering functions, classes, generics, decorators, interfaces, imports, and re-exports.

- `basic_function.expected.json` — Expected parser output for basic_function.ts
- `basic_function.graph.expected.json` — Expected graph projection output for basic_function.ts
- `basic_function.ts` — Source fixture — basic top-level TypeScript function with type annotations
- `class_with_methods.expected.json` — Expected parser output for class_with_methods.ts
- `class_with_methods.ts` — Source fixture — TypeScript class with typed method definitions
- `decorators.expected.json` — Expected parser output for decorators.ts
- `decorators.ts` — Source fixture — TypeScript class and method definitions using decorators
- `default_export.expected.json` — Expected parser output for default_export.ts
- `default_export.ts` — Source fixture — TypeScript module using a default export
- `generics.expected.json` — Expected parser output for generics.ts
- `generics.ts` — Source fixture — functions and classes using TypeScript generic type parameters
- `import_variants.expected.json` — Expected parser output for import_variants.ts
- `import_variants.ts` — Source fixture — module exercising named, namespace, and type import forms
- `interface_call.expected.json` — Expected parser output for interface_call.ts
- `interface_call.graph.expected.json` — Expected graph projection output for interface_call.ts
- `interface_call.ts` — Source fixture — function calling methods on a typed interface argument
- `re_export.expected.json` — Expected parser output for re_export.ts
- `re_export.ts` — Source fixture — TypeScript module that re-exports names from another module
- `re_export_source.expected.json` — Expected parser output for re_export_source.ts
- `re_export_source.ts` — Source fixture — TypeScript module whose exports are re-exported by re_export.ts

### lattice-source-parser/src/

`src/`-layout root that isolates the installable package from tests and fixtures.

#### lattice-source-parser/src/lattice_source_parser/

Top-level package module: public API re-exports, version string, and sub-package entry points.

- `__init__.py` — Re-exports the full public API (`parse_file`, `parse_bytes`, `to_graph_records`, data model types, `UnsupportedLanguageError`) and sets `__version__`
- `errors.py` — Defines `UnsupportedLanguageError`, the single exception type raised for unrecognised file extensions or grammar names
- `grammars.py` — Loads and caches `tree_sitter.Language` objects from `tree-sitter-language-pack` via an LRU-cached `get_language(name)` helper
- `parse.py` — Implements `parse_file` and `parse_bytes`, the public entry points that dispatch to a registered `LanguageParser` by file extension or explicit language name
- `tree.py` — Defines the core data model: `Span` (byte + line + column bounds), `Reference` (call / import / export edge), and `SourceNode` (tree node carrying kind, name, span, children, and refs)

##### lattice-source-parser/src/lattice_source_parser/parsers/

Per-language parser implementations and the extension/language registry.

- `__init__.py` — Instantiates `PythonParser`, `JavaScriptParser`, and `TypeScriptParser`; builds the `PARSERS` (by language name) and `EXTENSIONS` (by file suffix) dispatch dicts
- `_base.py` — Declares the `LanguageParser` ABC with abstract `grammar` property and `parse` method; provides a no-op default `resolve_call_target`
- `_config.py` — Defines the `LanguageConfig` frozen dataclass — a declarative description of AST node type names, field names, and traversal boundaries consumed by the generic walker
- `_generic.py` — Config-driven `generic_walk` function that parses source bytes with tree-sitter and walks the AST into a `SourceNode` tree using a `LanguageConfig`; handles classes, functions, methods, imports, exports, and call extraction
- `javascript.py` — `JavaScriptParser` using `JAVASCRIPT_CONFIG` (a `LanguageConfig` for `.js/.jsx/.mjs/.cjs` files) delegating to `generic_walk`
- `python.py` — `PythonParser` with a hand-written AST walker that handles Python-specific import forms (`import`, `from … import`, aliased), decorators, and `__all__`-based exports
- `typescript.py` — `TypeScriptParser` built by extending `JAVASCRIPT_CONFIG` with TypeScript-specific node types (abstract classes, method/function signatures) and delegating to `generic_walk`

##### lattice-source-parser/src/lattice_source_parser/projections/

SourceTree-to-consumer-record projection layer.

- `__init__.py` — Re-exports `GraphNode`, `GraphEdge`, `GraphRecords`, `NodeKey`, and `to_graph_records` from `graph.py`
- `graph.py` — Implements `to_graph_records(tree)`, which recursively walks a `SourceNode` tree and emits `GraphNode` records (kind, name, path, line) and `GraphEdge` records (contains / calls / imports / exports) aligned to the `lattice-graph` SQLite schema

### lattice-source-parser/tests/

pytest test suite: fixture-parametrized parser tests, unit tests for each module, and smoke tests.

- `_fixture_loader.py` — Helper that discovers `*.py` / `*.js` / `*.ts` fixture files alongside their `*.expected.json` and `*.graph.expected.json` counterparts for parametrized test cases
- `test_generic_walker.py` — Unit tests for the `generic_walk` function in `_generic.py`, covering class/function/method traversal and call/import/export extraction
- `test_grammars.py` — Tests that `get_language` returns a cached `tree_sitter.Language` for known grammars and raises `UnsupportedLanguageError` for unknown names
- `test_parse_dispatch.py` — Tests that `parse_file` and `parse_bytes` dispatch correctly by file extension and explicit language name
- `test_parse_errors.py` — Tests that parse errors in source files are captured in `file_node.attrs["parse_errors"]` rather than raising
- `test_parser_javascript.py` — Fixture-parametrized tests asserting `JavaScriptParser` output matches all `fixtures/javascript/*.expected.json` files
- `test_parser_python.py` — Fixture-parametrized tests asserting `PythonParser` output matches all `fixtures/python/*.expected.json` files
- `test_parser_typescript.py` — Fixture-parametrized tests asserting `TypeScriptParser` output matches all `fixtures/typescript/*.expected.json` files

## Sub-pages

- [[wiki/packages/lattice-source-parser/api]]      — public API, architecture diagram, parse pipeline
- [[wiki/packages/lattice-source-parser/patterns]] — LanguageParser abstraction, two impl strategies, v1 scope, non-goals
- [[wiki/packages/lattice-source-parser/work]]     — bugs, tech debt, features, open questions
- [[wiki/packages/lattice-source-parser/context]]  — concepts, decisions, ADRs, sources
